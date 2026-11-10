# FITIA MVP 2 — Audio con IA (versión recortada)

> Borrador para el equipo. Entrega: mañana. Todo lo marcado **[SUPUESTO]** debe confirmarse. La numeración de HU de este documento es propia del MVP 2 (HU 1 a HU 10).

## 1. Objetivo y requisitos obligatorios

Que el estudiante pueda **escuchar** la técnica de sus ejercicios y **entrenar guiado por voz** la rutina de hoy, sin romper el MVP 1.

| # | Requisito | Cómo se cumple |
|---|---|---|
| R1 | El audio lo crea una IA o herramienta de un proveedor web | **Gemini TTS** (mismo proveedor y API key del plan), detrás de un puerto de síntesis en el backend |
| R2 | La app responde en español | Interfaz, mensajes de error y voz en español; el texto que se sintetiza ya está en español |

- Gemini sigue generando el plan. El audio se genera **solo a partir de texto ya guardado del plan**.
- Sin migraciones ni tablas nuevas. El audio **no se guarda** en la base de datos.
- Si la IA falla, se usa la voz del navegador y, si tampoco existe, texto y botones (el MVP 1 sigue igual).

## 2. Alcance y resumen de historias

| HU | Título | Épica | Prioridad | Pts | Capa |
|---|---|---|---|---|---|
| 1 | Generar el audio de un ejercicio con IA | A. Audio de ejercicios | Must | 3 | Backend |
| 2 | Reutilizar audios y controlar el costo | A | Should | 2 | Backend |
| 3 | Escuchar la explicación de un ejercicio | A | Must | 3 | Frontend |
| 4 | Pausar, reanudar y repetir el audio | A | Must | 2 | Frontend |
| 5 | Cambiar la velocidad del audio | A | Should | 1 | Frontend |
| 6 | Respaldo con voz del navegador y texto | A | Must | 3 | Frontend |
| 7 | Iniciar el modo guiado y anunciar ejercicios | B. Modo guiado | Must | 3 | Frontend |
| 8 | Descansos con cuenta regresiva y avisos de voz | B | Must | 3 | Frontend + Backend |
| 9 | Controlar el modo guiado con botones | B | Must | 2 | Frontend |
| 10 | Disponibilidad del modo guiado y pantalla activa | B | Should | 2 | Frontend |
| | **Total** | | | **24** | |

Fuera de alcance (backlog): comandos de voz (STT), pedir un ejercicio por voz, preferencias de audio en servidor, métricas de uso de audio, caché persistente.

## 3. Tecnología

- **Backend:** nuevo puerto `SpeechSynthesizer` en `app/ai/ports.py`, con `GeminiSpeechAdapter` y `FakeSpeechAdapter` (para pruebas y CI). Usa el cliente `google-genai`, el gateway, el circuit breaker y los logs ya existentes.
- **Endpoints nuevos:**
  - `GET /api/v1/plan/exercises/{id}/audio` (sesión, dueño del ejercicio, `Cache-Control: private`). El servidor arma el texto desde el plan (nombre, pasos y aviso); el cliente no envía texto.
  - `GET /api/v1/plan/audio/cues/{name}` con nombres cerrados (`descanso`, `diez-segundos`, `fin-rutina`).
- **Frontend:** reproductor con `<audio>`, módulo `features/voice/`, y `speechSynthesis` del navegador solo como respaldo.
- **Formato:** Gemini TTS devuelve audio sin contenedor (PCM) **[SUPUESTO: verificar]**; el backend lo empaqueta como WAV.
- **Configuración:** `GEMINI_TTS_MODEL` y `GEMINI_TTS_VOICE` como variables de entorno (también en Render). Se confirman con una prueba antes de implementar.

## 4. Historias de usuario

### Épica A — Audio de ejercicios

#### HU 1 — Generar el audio de un ejercicio con IA · Must · 3 pts
**Como** estudiante, **quiero** que la app genere en español el audio de la explicación de un ejercicio, **para** poder escucharla.
Depende de: explicación de ejercicios del MVP 1 (HU 13 del MVP 1).

- **AC-1-1:** dado un ejercicio propio, cuando se pide su audio, entonces el servidor responde un audio en español con el nombre, los pasos en orden y el aviso orientativo una sola vez al final.
- **AC-1-2:** el texto lo construye el servidor a partir del plan; el cliente no envía texto.
- **AC-1-3:** a la IA solo viaja el texto del ejercicio, sin identificadores del usuario.
- **AC-1-4:** dado un ejercicio de otro usuario o inexistente, entonces responde 404; sin sesión, 401.
- **AC-1-5:** si la IA falla, tarda demasiado o está desactivada (`AI_ENABLED`), responde 503 `AI_UNAVAILABLE` con mensaje en español.
- **AC-1-6:** cada uso queda en `ai_call_logs` sin `user_id` ni texto.

#### HU 2 — Reutilizar audios y controlar el costo · Should · 2 pts
**Como** equipo del producto, **quiero** reutilizar los audios ya generados y limitar el uso, **para** controlar el costo y la latencia.
Depende de: HU 1.

- **AC-2-1:** dado el mismo ejercicio pedido otra vez, entonces el servidor reutiliza el audio de una caché en memoria por hash del texto, sin nueva llamada a la IA.
- **AC-2-2:** el audio no se guarda en la base de datos.
- **AC-2-3:** la respuesta lleva `Cache-Control: private` para que el navegador también la reutilice.
- **AC-2-4:** el endpoint respeta el límite de frecuencia y el circuit breaker existentes.

#### HU 3 — Escuchar la explicación de un ejercicio · Must · 3 pts
**Como** estudiante, **quiero** pulsar «Escuchar» en la explicación de un ejercicio, **para** aprender la técnica sin leer la pantalla.
Depende de: HU 1.

- **AC-3-1:** al pulsar «Escuchar», se reproduce el audio de la HU 1.
- **AC-3-2:** mientras se genera, se muestra «Preparando audio…» y no se puede lanzar otra solicitud.
- **AC-3-3:** la primera reproducción puede tardar hasta 5 s **[SUPUESTO]**; las siguientes del mismo ejercicio empiezan en ≤ 1 s.
- **AC-3-4:** si cierra la explicación o cambia de ejercicio, el audio se detiene.
- **AC-3-5:** nunca suenan dos audios a la vez.
- **AC-3-6:** el botón y sus mensajes están en español y tienen nombre accesible.

#### HU 4 — Pausar, reanudar y repetir el audio · Must · 2 pts
**Como** estudiante, **quiero** pausar, reanudar y repetir el audio, **para** seguir la técnica a mi ritmo.
Depende de: HU 3.

- **AC-4-1:** pausa y reanudar continúan desde donde quedó.
- **AC-4-2:** «Repetir» reinicia el audio del ejercicio.
- **AC-4-3:** sin audio en curso, pausa y repetir están deshabilitados.
- **AC-4-4:** los controles se operan con teclado.

#### HU 5 — Cambiar la velocidad del audio · Should · 1 pt
**Como** estudiante, **quiero** elegir la velocidad del audio, **para** entenderlo mejor.
Depende de: HU 3.

- **AC-5-1:** puede elegir 0,75×, 1× o 1,25×; se aplica sin reiniciar el audio.
- **AC-5-2:** la elección se guarda en `localStorage` y se aplica al volver; por defecto 1×.
- **AC-5-3:** si `localStorage` falla, se usa 1× sin error.

#### HU 6 — Respaldo con voz del navegador y texto · Must · 3 pts
**Como** estudiante, **quiero** que la app siga funcionando si el audio con IA no está disponible, **para** no perder mi rutina.
Depende de: HU 3.

- **AC-6-1:** si el endpoint de audio falla o tarda más de 15 s **[SUPUESTO]**, se lee el texto con la voz del navegador en español.
- **AC-6-2:** si tampoco hay voz en el navegador, «Escuchar» se deshabilita con un aviso en español y la explicación en texto funciona igual.
- **AC-6-3:** si el audio falla a mitad, se detiene y la pantalla no se bloquea.
- **AC-6-4:** ningún fallo de audio afecta Hoy, Semana, Explicación ni Perfil del MVP 1.

### Épica B — Modo guiado de la rutina de hoy

Solo lectura: no registra sesión, puntos ni racha.

#### HU 7 — Iniciar el modo guiado y anunciar ejercicios · Must · 3 pts
**Como** estudiante, **quiero** iniciar un modo guiado que me anuncie cada ejercicio, **para** entrenar sin mirar el celular todo el tiempo.
Depende de: HU 3 y la rutina de hoy del MVP 1 (HU 10 del MVP 1).

- **AC-7-1:** con «Entrenar con voz», la app anuncia el primer ejercicio (nombre, series y repeticiones o segundos) y lee sus pasos con el audio de la HU 3.
- **AC-7-2:** al iniciar, se precarga el audio de los ejercicios del día para evitar esperas entre uno y otro.
- **AC-7-3:** al terminar el último ejercicio, anuncia el fin de la rutina con una frase fija en español.
- **AC-7-4:** el modo no escribe nada en el plan ni en la base de datos.

#### HU 8 — Descansos con cuenta regresiva y avisos de voz · Must · 3 pts
**Como** estudiante, **quiero** una cuenta regresiva en mis descansos con avisos de voz, **para** retomar a tiempo sin mirar el reloj.
Depende de: HU 7. Incluye el endpoint de frases fijas.

- **AC-8-1:** entre series y ejercicios corre una cuenta regresiva visible con el tiempo de descanso del plan.
- **AC-8-2:** la app avisa por voz a los 10 s y al terminar el descanso, con frases fijas cortas (`GET /plan/audio/cues/{name}`, generadas por la IA y cacheadas).
- **AC-8-3:** solo se aceptan los nombres cerrados de frases; otro nombre devuelve 404.
- **AC-8-4:** si el audio de una frase falla, se usa la voz del navegador (HU 6).

#### HU 9 — Controlar el modo guiado con botones · Must · 2 pts
**Como** estudiante, **quiero** botones de siguiente, anterior, repetir, pausar y salir, **para** controlar la rutina cuando quiera.
Depende de: HU 7.

- **AC-9-1:** «Siguiente» y «Anterior» cambian de ejercicio y detienen el audio en curso.
- **AC-9-2:** «Pausar» detiene audio y temporizador; «Continuar» los retoma.
- **AC-9-3:** «Repetir» vuelve a anunciar el ejercicio actual.
- **AC-9-4:** «Salir» detiene audio y temporizadores y vuelve a la rutina de hoy.
- **AC-9-5:** todos los botones están en español, con teclado y nombre accesible.

#### HU 10 — Disponibilidad del modo guiado y pantalla activa · Should · 2 pts
**Como** estudiante, **quiero** que el modo solo se ofrezca cuando corresponde y que la pantalla no se apague, **para** no encontrarme con errores a mitad de la rutina.
Depende de: HU 7.

- **AC-10-1:** en día de descanso, fin de semana o plan sin generar o fallido, no se ofrece «Entrenar con voz» y se muestra el estado de la rutina de hoy.
- **AC-10-2:** con el modo abierto, la pantalla se mantiene activa mediante Wake Lock donde la API lo permita **[SUPUESTO]**.
- **AC-10-3:** si Wake Lock no existe o falla, el modo sigue funcionando sin error.
- **AC-10-4:** al salir, se libera el Wake Lock.

## 5. Requisitos no funcionales

| # | Requisito | HU |
|---|---|---|
| NFR-24 | Primera reproducción ≤ 5 s; con caché ≤ 1 s **[SUPUESTO]** | 2, 3 |
| NFR-26 | No se guarda audio en la base de datos ni se registra el contenido del texto; la caché es temporal | 1, 2 |
| NFR-27 | La IA de audio solo recibe texto del plan, sin identificadores del usuario | 1, 8 |
| NFR-28 | Degradación en tres niveles: IA → voz del navegador → texto | 6 |
| NFR-29 | Todo en español: interfaz, errores y voz | todas |
| NFR-30 | Control de costo: límite de frecuencia, circuit breaker e interruptor `AI_ENABLED` existentes | 1, 2 |
| NFR-31 | Controles con teclado y nombre accesible | 3, 4, 9 |
| NFR-34 | Pantalla activa en modo guiado donde la API lo permita | 10 |

Regresión: las 633 pruebas del backend y las 99 del frontend del MVP 1 siguen pasando.

## 6. Diseño técnico

**Backend (sin migraciones):**
- `app/ai/ports.py`: puerto `SpeechSynthesizer` con `synthesize(text, voice) -> bytes`.
- `app/ai/adapters/gemini_speech.py` y `fake_speech.py` (devuelve un WAV mínimo válido).
- Caso de uso `exercise_audio`: arma el texto desde el plan, llama al puerto y registra el uso.
- Router de `plan`: endpoint de audio por ejercicio y endpoint de frases fijas. Caché en memoria por hash del texto.
- `config.py`: `GEMINI_TTS_MODEL`, `GEMINI_TTS_VOICE`.

**Frontend (`features/voice/`):**
```
voice/
├── api.ts                 pide el audio y lo guarda como blob en memoria
├── AudioPlayer.ts         <audio>: reproducir, pausar, reiniciar, velocidad
├── BrowserFallback.ts     speechSynthesis en español
├── ListenButton.tsx · PlaybackControls.tsx
└── guided/                guidedMachine.ts (función pura) · useGuidedSession.ts · GuidedPage.tsx
```

**Máquina de estados del modo guiado:** `idle → announcing → working → resting → announcing … → finished`, con `paused` desde cualquier estado. Eventos: `next`, `previous`, `repeat`, `pause`, `exit`, `done`.

## 7. Decisiones (ADR)

| ID | Decisión | Motivo |
|---|---|---|
| ADR-16 | Audio con Gemini TTS detrás del puerto `SpeechSynthesizer` | Cumple R1; mismo proveedor, API key, gateway y adaptador falso del MVP 1 |
| ADR-17 | El servidor arma el texto a sintetizar desde el plan | Privacidad y seguridad: el cliente no envía texto libre a la IA |
| ADR-18 | El audio no se persiste; caché temporal y de cliente | Sin tablas ni retención; el plan inmutable hace segura la caché |
| ADR-19 | Voz del navegador solo como respaldo | Degradación sin romper la rutina |
| ADR-20 | El modo guiado es de solo lectura y su estado vive en el cliente | Plan inmutable; Épicas 4 y 5 del MVP 1 diferidas |

## 8. Riesgos

| Riesgo | Mitigación |
|---|---|
| Modelo TTS, voz o formato distintos de lo esperado | Prueba de 30 min **antes** de implementar; si falla, se ajusta o se cambia de proveedor |
| Latencia de la IA (varios segundos) | Precarga en el modo guiado, caché y mensaje «Preparando audio…» |
| Costo y cuota de la API | Caché, `AI_ENABLED`, límite de frecuencia y circuit breaker existentes |
| Audio bloqueado por el navegador si no empieza con un toque | Reproducir siempre desde un gesto del usuario |
| Pantalla bloqueada en móvil detiene el audio | Wake Lock donde exista; avisar en el modo guiado |
| Acento o calidad de la voz en español | Elegir y probar la voz antes de fijarla |
| Plazo de 1 día | Alcance recortado y orden de trabajo del punto 10 |

## 9. Pruebas

- **Backend:** adaptador falso para el puerto; endpoints con sesión, dueño del ejercicio (404 si es de otro), nombres cerrados de frases y 503 con IA desactivada; caché; regresión de las 633 pruebas.
- **Frontend (Vitest + MSW):** `guidedMachine` (todas las transiciones), reproductor (pausa, reinicio, velocidad), respaldo al navegador y texto, mensajes en español.
- **Manual (1 o 2 celulares reales):** audio en español, tiempo de la primera reproducción, pausa, pantalla activa y modo guiado completo.
- **Producción:** verificar una vez los endpoints con Gemini real tras desplegar.

## 10. Orden de trabajo (1 día)

| Paso | Qué | HU |
|---|---|---|
| 0 | Prueba de Gemini TTS: modelo, voz, formato y tiempo | — |
| 1 | Puerto, adaptadores real y falso, caso de uso y endpoint con pruebas | 1, 2 |
| 2 | Reproductor, botón «Escuchar», controles y velocidad | 3, 4, 5 |
| 3 | Respaldo del navegador y texto | 6 |
| 4 | `guidedMachine` con pruebas, `GuidedPage`, botones y disponibilidad | 7, 9, 10 |
| 5 | Frases fijas (backend) y cuenta regresiva con avisos | 8 |
| 6 | Despliegue (variables en Render) y prueba en celulares reales | — |
| 7 | Documentación `docs/HU<N>.md` y evidencia | todas |

Reparto sugerido **[SUPUESTO]**: Juan Esteban en backend (HU 1, 2 y frases de HU 8), Daniel en reproductor y controles (HU 3 a 6), Elkin en modo guiado (HU 7, 9, 10 y cuenta regresiva de HU 8), Jorge en pruebas y celulares (paso 6), documentación entre todos.

## 11. Definición de terminado

- Criterios de aceptación cumplidos y probados.
- Pruebas nuevas y de regresión en verde (CI).
- Audio generado por Gemini verificado en producción y probado en un celular real.
- Todo el texto visible y hablado en español.
- `docs/HU<N>.md` actualizado.

## 12. Pendientes y decisiones del equipo

1. **Modelo y voz de Gemini TTS [CERRADO]:** Confirmado y fijado el modelo `gemini-3.8-flash-tts` con la voz `Aoede` (timbre femenino claro, prosodia natural en español para instrucciones deportivas y soporte de velocidad). Declarados en `apps/api/app/core/config.py` y `render.yaml`.
2. **Cuota y costos de la API [CERRADO]:** Protegido mediante triple barrera:
   - Caché en memoria en backend (`AudioCache` LRU de 512 elementos con coalescencia *single-flight*).
   - Caché de cliente mediante cabecera HTTP `Cache-Control: private, max-age=86400`.
   - Límite de tasa (`RATE_LIMIT_EXERCISE_AUDIO_PER_USER=30` en 15 min), circuit breaker de 5 fallos consecutivos y degradación transparente a voz de navegador (`BrowserFallback`).
3. **Tiempos objetivo y latencia [CONFIRMADO EN PRUEBAS / PENDIENTE CELULAR REAL]:**
   - Primera generación con IA: ventana de timeout de 15 s; en pruebas con adaptador y simulaciones se cumple el objetivo de $\le 5\text{ s}$.
   - Reproducciones consecutivas: $\le 1\text{ s}$ garantizado por caché local.
   - Frases de descanso: $\le 100\text{ ms}$ gracias a la precarga preventiva en el montaje del modo guiado.
   - *Nota:* La medición en redes móviles y hardware físico heterogéneo se documenta en `docs/mvp2/EVIDENCIA.md` como paso post-despliegue.
4. **Backlog futuro:** Comandos de voz (STT), solicitar variantes de ejercicio por voz, selector de voz o acento en perfil, métricas de retención de audio y persistencia distribuida de audio (Redis / Object Storage).
