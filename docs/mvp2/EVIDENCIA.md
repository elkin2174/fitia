# FITIA — MVP 2: Audio y Modo Guiado por Voz
# Informe de Evidencia, Regresión, Seguridad y Verificación Técnica

> **Fecha:** Marzo 2026  
> **Rama de Trabajo:** `mvp2`  
> **Estado General:** Verificado en suite de pruebas automatizadas completa. Listo para despliegue y validación manual post-despliegue en dispositivos móviles reales.

---

## 1. Resumen Ejecutivo y Resultados de Regresión

El MVP 2 incorpora la síntesis de audio de instrucciones técnicas mediante Gemini TTS, controles de reproducción interactivos (pausa, reanudación, repetición y velocidad dinámica), un sistema resiliente de degradación a tres niveles (IA → voz del navegador → texto), y una experiencia de entrenamiento guiado manos libres (anuncio de ejercicios, cuenta regresiva de descansos con frases sonoras, y retención de pantalla encendida mediante Screen Wake Lock).

Todo el desarrollo se implementó bajo la premisa de **cero mutaciones en la persistencia**:
- **0 migraciones de base de datos** creadas (`apps/api/migrations/versions/` intacto).
- **0 tablas o columnas nuevas o alteradas** en el esquema de PostgreSQL.
- **0 llamadas externas reales a APIs de terceros** en las suites de pruebas automatizadas (aislamiento estricto con `FakeSpeechAdapter` y mocks de Service Worker en MSW).
- **Cero alteraciones de contratos** existentes de los endpoints del MVP 1 (`/auth`, `/onboarding`, `/plan`, `/profile`).

### Métricas de Suites Automatizadas

| Entorno / Componente | Suites / Archivos | Pruebas Totales | Pruebas MVP 1 (Línea Base) | Pruebas Nuevas MVP 2 | Estado |
|---|---|---|---|---|---|
| **Backend (FastAPI / pytest)** | 27 archivos | **659** | 633 | **26** | **100% Pasando** |
| **Frontend (React 19 / Vitest + MSW)** | 21 archivos | **164** | 99 | **65** | **100% Pasando** |
| **Chequeo de Tipos Web (`tsc -b`)** | Proyecto completo | — | — | — | **0 Errores** |
| **Compilación Web (`vite build`)** | Bundle de producción | — | — | — | **Exitoso (936 ms)** |

---

## 2. Verificación de Esquema de Base de Datos y Contratos MVP 1

Ejecutando la inspección de diferencias contra la rama principal (`origin/main...HEAD`):

1. **Persistencia y Migraciones:**
   - La carpeta `apps/api/migrations/versions/` contiene exactamente las 8 revisiones del MVP 1.
   - El archivo `apps/api/app/modules/plan/models.py` y demás modelos ORM SQLAlchemy permanecen inalterados.
   - El estado de la sesión guiada y el temporizador residen exclusivamente en la memoria del cliente (`guidedMachine.ts`), garantizando el principio de solo lectura (`ADR-20`).
2. **Caché en Servidor:**
   - Implementado como estructura en memoria LRU en proceso (`AudioCache` con capacidad de 512 clips de audio y coalescencia de promesas *single-flight*).
3. **Contratos HTTP del MVP 1:**
   - Los endpoints `GET /api/v1/plan/today`, `GET /api/v1/plan/week`, `POST /api/v1/plan/generate`, `POST /api/v1/onboarding/complete`, etc., mantienen intactas sus firmas, esquemas Pydantic de entrada/salida y códigos de estado.
   - El middleware `NoStoreMiddleware` fue ajustado de forma quirúrgica para preservar la cabecera `Cache-Control: private, max-age=86400` en respuestas binarias exitosas bajo `/api/v1/plan/exercises/*/audio` y `/api/v1/plan/audio/cues/*`, manteniendo `Cache-Control: no-store` para todos los demás endpoints del sistema.

---

## 3. Variables de Entorno de Producción e Infraestructura

### 3.1 Nuevas Variables de Entorno

| Variable | Valor por Defecto / Configurado | Tipo | Propósito |
|---|---|---|---|
| `GEMINI_TTS_MODEL` | `gemini-3.8-flash-tts` | Configuración pública | Identificador del modelo Gemini optimizado para síntesis de voz (*Text-to-Speech*). |
| `GEMINI_TTS_VOICE` | `Aoede` | Configuración pública | Nombre de la voz predeterminada en español (timbre neutro, prosodia deportiva clara). |

### 3.2 Ubicación de Configuración en Render

- **Servicio:** `fitia-api` (Servicio Web en Render).
- **Ruta de Configuración:** `Dashboard Render` → `fitia-api` → `Environment` → `Add Environment Variable`.
- **Declaración en Infraestructura como Código (`render.yaml`):**
  Actualizado para declarar las variables no sensibles dentro de `envVars`:
  ```yaml
  services:
    - type: web
      name: fitia-api
      env: python
      rootDir: apps/api
      buildCommand: pip install -r requirements.txt
      startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
      envVars:
        - key: PYTHON_VERSION
          value: 3.11.9
        - key: TZ
          value: America/Bogota
        - key: GEMINI_TTS_MODEL
          value: gemini-3.8-flash-tts
        - key: GEMINI_TTS_VOICE
          value: Aoede
  ```
- **Claves Secretas:** La clave `GEMINI_API_KEY` continúa siendo administrada exclusivamente mediante la interfaz de variables secretas de Render, sin registrarse en el repositorio.

### 3.3 Proxy y Rewrites en Vercel (`apps/web/vercel.json`)

El archivo de configuración de Vercel declara:
```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://fitia-api-liyx.onrender.com/api/:path*"
    }
  ]
}
```
**Confirmación de comportamiento:**
- Vercel Edge Network actúa como proxy inverso transparente para peticiones a `/api/*`.
- **Cuerpo binario:** Las respuestas `audio/wav` son transmitidas de forma binaria sin transcodificación ni corrupción de bytes.
- **Cabeceras HTTP:** Las cabeceras `Content-Type: audio/wav` y `Cache-Control: private, max-age=86400` se preservan íntegramente hacia el navegador del cliente.

---

## 4. Auditoría de Seguridad y Privacidad (Evidencia Técnica)

| Ítem | Requisito de Seguridad / Privacidad | Evidencia y Prueba Automatizada | Estado |
|---|---|---|---|
| **(a)** | **Autenticación Obligatoria:** El endpoint de audio exige sesión válida (`401 UNAUTHORIZED`). | `test_plan_audio.py::test_exercise_audio_requires_session` y `test_plan_audio_cues.py::test_cue_audio_requires_session`. Peticiones anónimas reciben 401 y formato uniforme de error. | **Verificado** |
| **(b)** | **Control de Acceso / Pertenencia:** Un ejercicio ajeno o inexistente devuelve 404 (`404 EXERCISE_NOT_FOUND`). | `test_plan_audio.py::test_exercise_audio_other_user_exercise_returns_404`. No se permite que un usuario consulte ejercicios de otros planes. | **Verificado** |
| **(c)** | **Ausencia de PII en Texto a la IA:** El texto enviado a Gemini TTS contiene exclusivamente nombre y pasos técnicos del ejercicio. | `test_exercise_audio_builder.py::test_exercise_audio_builder_no_pii`. Se verifica que `user_id`, correo, apodo o diagnósticos médicos no se concatenan en la solicitud. | **Verificado** |
| **(d)** | **Telemetría sin PII en `ai_call_logs`:** La tabla de logs de IA registra latencia, estado y tokens estimados sin almacenar texto ni `user_id`. | `test_plan_audio.py::test_exercise_audio_logs_ai_call_without_pii`. La columna `user_id` permanece en `NULL` y no hay columnas de contenido de texto. | **Verificado** |
| **(e)** | **Sin Audio ni PII en Logs de Aplicación:** Ni los bytes de audio ni el texto se imprimen en logs del servidor. | `test_no_store.py::test_audio_endpoint_has_cache_control_and_no_body_in_logs`. La respuesta es un streaming binario de bytes WAV. | **Verificado** |
| **(f)** | **Cero Llamadas a Gemini desde Modo Guiado:** El modo guiado opera enteramente en cliente; solo pide audio sintetizado. | Inspección de `guidedMachine.ts`, `useGuidedSession.ts` y pruebas en `guided.test.tsx`. No se ejecutan llamadas LLM generativas dinámicas durante el entrenamiento. | **Verificado** |

---

## 5. Matriz de Trazabilidad Completa: HU $\to$ AC $\to$ Pruebas Automatizadas $\to$ Pruebas Manuales

| HU | Criterio de Aceptación (AC) | Pruebas Automatizadas (Archivo y Test) | Estado Prueba Manual |
|---|---|---|---|
| **HU 1** | **AC-1-1:** Endpoint `GET /api/v1/plan/exercises/{id}/audio` devuelve WAV `audio/wav`. | `apps/api/tests/integration/test_plan_audio.py::test_exercise_audio_success` | [Pendiente despliegue] |
| **HU 1** | **AC-1-2:** Texto contiene nombre, pasos y aviso orientativo final sin PII. | `apps/api/tests/unit/test_exercise_audio_builder.py::test_builder_output` | [Pendiente despliegue] |
| **HU 1** | **AC-1-3:** Exige sesión y ejercicio propio; 401 si no hay sesión, 404 si es ajeno. | `apps/api/tests/integration/test_plan_audio.py::test_exercise_audio_requires_session`, `::test_other_user_404` | [Pendiente despliegue] |
| **HU 1** | **AC-1-4:** Falla o circuit breaker abierto devuelve `503 AI_UNAVAILABLE`. | `apps/api/tests/integration/test_plan_audio.py::test_exercise_audio_circuit_breaker_503` | [Pendiente despliegue] |
| **HU 1** | **AC-1-5:** `ai_call_logs` registra latencia sin texto ni `user_id`. | `apps/api/tests/integration/test_plan_audio.py::test_exercise_audio_logs_ai_call_without_pii` | [Pendiente despliegue] |
| **HU 1** | **AC-1-6:** Sin llamadas externas en pruebas automáticas (`FakeSpeechAdapter`). | `apps/api/tests/unit/test_fake_speech.py::test_fake_speech_generates_valid_wav` | **Verificado local** |
| **HU 2** | **AC-2-1:** Caché en memoria devuelve audio idéntico sin re-invocar IA. | `apps/api/tests/unit/test_audio_cache.py::test_audio_cache_hit_and_eviction` | [Pendiente despliegue] |
| **HU 2** | **AC-2-2:** Solicitudes simultáneas consolidan en una sola llamada (*single-flight*). | `apps/api/tests/unit/test_audio_cache.py::test_audio_cache_coalescing_single_flight` | **Verificado local** |
| **HU 2** | **AC-2-3:** Respuesta exitosa incluye `Cache-Control: private, max-age=86400`. | `apps/api/tests/integration/test_plan_audio.py::test_exercise_audio_cache_control_header` | [Pendiente despliegue] |
| **HU 2** | **AC-2-4:** No se guardan archivos de audio en disco ni base de datos. | `apps/api/tests/integration/test_no_store.py::test_audio_endpoint_has_cache_control_and_no_body_in_logs` | **Verificado local** |
| **HU 3** | **AC-3-1:** Botón «Escuchar» en hoja de técnica inicia reproducción de audio. | `apps/web/src/test/flows/voice.test.tsx::"reproduce audio al pulsar Escuchar"` | [Pendiente celular] |
| **HU 3** | **AC-3-2:** Mientras prepara el audio, botón muestra «Preparando audio…» y se deshabilita. | `apps/web/src/test/flows/voice.test.tsx::"muestra estado de carga Preparando audio..."` | [Pendiente celular] |
| **HU 3** | **AC-3-3:** Primera reproducción $\le 5\text{ s}$; siguientes del mismo ejercicio $\le 1\text{ s}$. | `apps/web/src/features/voice/AudioPlayer.test.ts::"reproducción subsecuente en memoria"` | [Pendiente celular] |
| **HU 3** | **AC-3-4:** Cerrar la hoja de técnica o cambiar de ejercicio detiene el audio. | `apps/web/src/test/flows/voice.test.tsx::"cierra la hoja de técnica y detiene el audio"` | [Pendiente celular] |
| **HU 3** | **AC-3-5:** Nunca suenan dos audios en simultáneo (instancia singleton `globalAudioPlayer`). | `apps/web/src/features/voice/AudioPlayer.test.ts::"detiene audio previo al reproducir nuevo"` | [Pendiente celular] |
| **HU 3** | **AC-3-6:** Botón y mensajes en español con nombre accesible (`aria-label`). | `apps/web/src/test/flows/voice.test.tsx::"nombres accesibles y etiquetas en español"` | [Pendiente celular] |
| **HU 4** | **AC-4-1:** Botones «Pausar» y «Reanudar» continúan el audio desde la posición actual. | `apps/web/src/test/flows/voice.test.tsx::"pausa y reanuda el audio conservando posición"` | [Pendiente celular] |
| **HU 4** | **AC-4-2:** Botón «Repetir» reinicia el audio del ejercicio desde el segundo 0. | `apps/web/src/test/flows/voice.test.tsx::"repetir reinicia el audio desde el inicio"` | [Pendiente celular] |
| **HU 4** | **AC-4-3:** Sin audio en curso, botones de pausa y repetición están deshabilitados. | `apps/web/src/test/flows/voice.test.tsx::"controles deshabilitados en estado inactivo"` | [Pendiente celular] |
| **HU 4** | **AC-4-4:** Controles accesibles y operables con teclado (`Enter` / `Espacio`). | `apps/web/src/test/flows/voice.test.tsx::"operable mediante teclado"` | [Pendiente celular] |
| **HU 5** | **AC-5-1:** Selector de velocidad: 0,75×, 1× y 1,25× aplicable sin reiniciar audio. | `apps/web/src/features/voice/playbackRate.test.ts::"aplica velocidad 0.75, 1 y 1.25"` | [Pendiente celular] |
| **HU 5** | **AC-5-2:** La velocidad elegida se conserva durante toda la sesión del usuario. | `apps/web/src/test/flows/voice.test.tsx::"persiste la velocidad durante la sesión"` | [Pendiente celular] |
| **HU 5** | **AC-5-3:** La velocidad por defecto es 1×. | `apps/web/src/features/voice/playbackRate.test.ts::"valor inicial predeterminado es 1x"` | [Pendiente celular] |
| **HU 5** | **AC-5-4:** Selector accesible con etiquetas en español. | `apps/web/src/test/flows/voice.test.tsx::"selector de velocidad accesible"` | [Pendiente celular] |
| **HU 6** | **AC-6-1:** Si el endpoint de IA falla o tarda $>15\text{ s}$, degrada a voz del navegador. | `apps/web/src/test/flows/voice.test.tsx::"degrada a síntesis de voz de navegador ante 503 o timeout"` | [Pendiente celular] |
| **HU 6** | **AC-6-2:** Si tampoco hay voz en el navegador, deshabilita «Escuchar» con aviso en español. | `apps/web/src/test/flows/voice.test.tsx::"sin soporte de voz muestra aviso y mantiene texto"` | [Pendiente celular] |
| **HU 6** | **AC-6-3:** Si el audio falla a mitad, se detiene limpiamente sin bloquear la pantalla. | `apps/web/src/features/voice/BrowserFallback.test.ts::"detención segura ante error en cola"` | [Pendiente celular] |
| **HU 6** | **AC-6-4:** Ningún fallo de audio afecta las vistas Hoy, Semana, Perfil ni Explicación. | `apps/web/src/test/flows/voice.test.tsx::"fallo de audio no bloquea navegación"` | [Pendiente celular] |
| **HU 7** | **AC-7-1:** «Entrenar con voz» anuncia primer ejercicio (series, repeticiones) y técnica. | `apps/web/src/test/flows/guided.test.tsx::"inicia modo guiado y anuncia primer ejercicio"` | [Pendiente celular] |
| **HU 7** | **AC-7-2:** Precarga preventiva del audio de los ejercicios de la rutina. | `apps/web/src/test/flows/guided.test.tsx::"precarga audios de la rutina"` | [Pendiente celular] |
| **HU 7** | **AC-7-3:** Al finalizar el último ejercicio, anuncia fin de rutina con frase fija. | `apps/web/src/test/flows/guided.test.tsx::"anuncia fin de rutina al terminar último ejercicio"` | [Pendiente celular] |
| **HU 7** | **AC-7-4:** El modo no escribe en el plan ni en la base de datos (solo lectura). | `apps/api/tests/integration/test_plan_readonly.py`, `apps/web/src/test/flows/guided.test.tsx` | **Verificado local** |
| **HU 8** | **AC-8-1:** Cuenta regresiva visible con tiempo de descanso del plan entre series/ejercicios. | `apps/web/src/test/flows/guided.test.tsx::"muestra cuenta regresiva en descanso"` | [Pendiente celular] |
| **HU 8** | **AC-8-2:** Avisos de voz a los 10 s y al terminar descanso con frases fijas cacheadas. | `apps/web/src/test/flows/guided.test.tsx::"reproduce avisos de descanso a los 10s y al finalizar"` | [Pendiente celular] |
| **HU 8** | **AC-8-3:** Catálogo cerrado de frases; nombre inválido devuelve 404 en backend. | `apps/api/tests/integration/test_plan_audio_cues.py::test_cue_invalid_name_404` | [Pendiente despliegue] |
| **HU 8** | **AC-8-4:** Si el audio de una frase falla, degrada a síntesis de voz del navegador. | `apps/web/src/test/flows/guided.test.tsx::"frase con error degrada a síntesis del navegador"` | [Pendiente celular] |
| **HU 9** | **AC-9-1:** «Siguiente» y «Anterior» cambian de ejercicio y detienen audio en curso. | `apps/web/src/test/flows/guided.test.tsx::"siguiente y anterior cambian ejercicio y detienen audio"` | [Pendiente celular] |
| **HU 9** | **AC-9-2:** «Pausar» congela temporizador y audio; «Continuar» los retoma. | `apps/web/src/test/flows/guided.test.tsx::"pausa congela temporizador y continuar lo reanuda"` | [Pendiente celular] |
| **HU 9** | **AC-9-3:** «Repetir» vuelve a anunciar el ejercicio actual. | `apps/web/src/test/flows/guided.test.tsx::"repetir reinicia anuncio del ejercicio actual"` | [Pendiente celular] |
| **HU 9** | **AC-9-4:** «Salir» detiene audio/temporizadores y retorna a la rutina de hoy. | `apps/web/src/test/flows/guided.test.tsx::"salir detiene sesión y regresa a /hoy"` | [Pendiente celular] |
| **HU 9** | **AC-9-5:** Botones en español, accesibles con teclado y con contraste adecuado. | `apps/web/src/test/flows/guided.test.tsx::"botones accesibles y en español"` | [Pendiente celular] |
| **HU 10** | **AC-10-1:** En descanso, fin de semana o sin plan, no ofrece botón y bloquea `/hoy/guiado`. | `apps/web/src/test/flows/guided.test.tsx::"oculta botón en descanso y redirige en /hoy/guiado"` | [Pendiente celular] |
| **HU 10** | **AC-10-2:** Solicita mantener pantalla encendida (`navigator.wakeLock.request`). | `apps/web/src/test/flows/guided.test.tsx::"solicita wakeLock al ingresar a la sesión guiada"` | [Pendiente celular] |
| **HU 10** | **AC-10-3:** Sin soporte de Wake Lock, continúa la sesión sin errores ni alertas. | `apps/web/src/test/flows/guided.test.tsx::"continúa normalmente si wakeLock no es soportado"` | [Pendiente celular] |
| **HU 10** | **AC-10-4:** Al salir de la pantalla se libera el Wake Lock y renueva en visibilidad. | `apps/web/src/test/flows/guided.test.tsx::"libera wakeLock al desmontar"` | [Pendiente celular] |

---

## 6. Lista de Verificación Manual Post-Despliegue (Checklist de Campo)

La siguiente lista de verificación debe ser ejecutada por el equipo de QA en el ambiente desplegado en producción tras configurar las variables en Render:

### Dispositivos y Navegadores Obligatorios
- [ ] **Móvil 1 (Android):** Google Chrome en Android 12+.
- [ ] **Móvil 2 (iOS):** Mobile Safari en iOS 16+.
- [ ] **Escritorio 1:** Google Chrome / MS Edge (Windows / macOS / Linux).
- [ ] **Escritorio 2:** Mozilla Firefox (Linux / Windows / macOS).

### Pasos de Verificación

#### Bloque A: Reproducción de Ejercicio Individual (HU 3, 4, 5)
1. **Primera Reproducción:** Iniciar sesión con un estudiante que tenga plan de entrenamiento activo. Navegar a `/hoy`, abrir la hoja de técnica de un ejercicio y pulsar «Escuchar».
   - [ ] Medir tiempo de espera: debe mostrar «Preparando audio…» y tardar $\le 5\text{ s}$ en iniciar.
   - [ ] Comprobar que el audio habla en español claro con voz femenina neutra (`Aoede`).
2. **Segunda Reproducción (Caché):** Cerrar la hoja, volver a abrirla y pulsar «Escuchar».
   - [ ] Medir tiempo: la reproducción debe comenzar de forma inmediata ($\le 1\text{ s}$).
3. **Pausa y Reanudación:** Pulsar «Pausar» a mitad de la explicación.
   - [ ] El audio se detiene de inmediato.
   - [ ] Al pulsar «Reanudar», continúa desde el segundo exacto donde se detuvo.
4. **Repetición:** Pulsar «Repetir».
   - [ ] El audio vuelve a comenzar desde el inicio (`0:00`).
5. **Velocidad de Reproducción:**
   - [ ] Cambiar a `0.75×`: la voz habla más lento sin cortes ni reinicios.
   - [ ] Cambiar a `1.25×`: la voz habla más rápido de forma fluida.
   - [ ] Cambiar a `1×`: retorna a velocidad normal.

#### Bloque B: Respaldo y Degradación (HU 6)
1. **Simulación de Falla de IA:**
   - Desconectar temporalmente la conexión o configurar una API key inválida en un entorno de pruebas, o forzar error en DevTools (bloquear `/api/v1/plan/exercises/*/audio`).
   - [ ] Pulsar «Escuchar».
   - [ ] Se activa la voz del navegador (`speechSynthesis`) en español leyendo los pasos secuencialmente.
   - [ ] No aparece ningún cuadro de error crítico ni se bloquea la navegación de la app.

#### Bloque C: Modo Guiado Completo (HU 7, 8, 9, 10)
1. **Inicio de Sesión Guiada:** Desde `/hoy`, pulsar «Entrenar con voz».
   - [ ] Navega a `/hoy/guiado`.
   - [ ] Se anuncia el ejercicio actual (nombre, series y repeticiones prescritas) seguido de la explicación técnica.
2. **Descanso y Avisos Sonoros:** Pulsar «Terminé la serie» o «Siguiente».
   - [ ] Aparece la cuenta regresiva con el tiempo de descanso estipulado en el plan (ej. 30 s o 60 s).
   - [ ] Se escucha la frase de descanso (*"Descansa y recupera el aliento."*).
   - [ ] Al llegar el contador a los 10 segundos, se escucha la alerta (*"Quedan diez segundos."*).
   - [ ] Al llegar el contador a 0, se escucha el aviso (*"Termina el descanso. ¡A seguir!"*) y avanza automáticamente.
3. **Controles del Modo Guiado:**
   - [ ] «Pausar» congela el temporizador de descanso y silencia cualquier audio.
   - [ ] «Continuar» reanuda el cronómetro y la sesión.
   - [ ] «Siguiente» avanza de ejercicio de inmediato.
   - [ ] «Anterior» retrocede al ejercicio anterior.
   - [ ] «Repetir» reproduce nuevamente la explicación del ejercicio en pantalla.
   - [ ] «Salir» regresa inmediatamente a `/hoy` deteniendo el audio y los temporizadores.
4. **Finalización:** Avanzar hasta el último ejercicio y concluirlo.
   - [ ] Se escucha la frase final (*"Terminaste la rutina de hoy. ¡Buen trabajo!"*).
   - [ ] La pantalla muestra la felicitación y permite salir a `/hoy`.

#### Bloque D: Pantalla Activa y Disponibilidad (HU 10)
1. **Screen Wake Lock en Móvil:** Con el modo guiado activo, dejar el teléfono sobre una superficie durante 3 minutos sin tocar la pantalla.
   - [ ] La pantalla del dispositivo no se atenúa ni se bloquea mientras la sesión esté activa.
2. **Día de Descanso:** Acceder con una cuenta en día de descanso o durante el fin de semana.
   - [ ] No se muestra el botón «Entrenar con voz».
   - [ ] Si se ingresa directamente a `/hoy/guiado` en la barra de direcciones, redirige a `/hoy` de inmediato.

---

## 7. Limitaciones y Pruebas Pendientes

1. **Pruebas en Hardware Móvil Físico:**
   - Las pruebas de flujo locales se ejecutaron en Vitest con emulación DOM (`happy-dom`), Web Audio API mocks y Web Speech API mocks. Las pruebas en dispositivos físicos (Android / iOS) quedan marcadas como **[Pendiente]** para validación post-despliegue en producción.
2. **Medición de Latencia en Red Real:**
   - En el entorno local de desarrollo y tests automatizados se utilizó `FakeSpeechAdapter` determinista ($\sim 2\text{ ms}$). Los tiempos reales con Gemini TTS (`gemini-3.8-flash-tts`) dependen de la conexión del servidor Render a la infraestructura de Google GenAI y quedan marcados como **[Pendiente]** para la verificación manual tras el despliegue.
3. **Persistencia Distribuida:**
   - El almacenamiento de caché de audio es en memoria del proceso (`LRU in-memory`). Un reinicio del contenedor en Render purgará la caché del servidor; sin embargo, los clientes conservan su copia local mediante la cabecera `Cache-Control: private, max-age=86400`.
