# MVP 2 — HU 6: Respaldo con voz del navegador y texto

Documentación técnica de la implementación frontend de la Historia de Usuario 6 del MVP 2 de FITIA: mecanismo de degradación elegante de tres niveles (IA → voz del dispositivo → texto en pantalla), detección de capacidades del navegador, cola de frases para síntesis de voz (`SpeechSynthesis`), temporizador de seguridad de 15 segundos y aislamiento de errores.

> **Estado:** Implementado y probado. 137 pruebas frontend pasando en suite completa (10 nuevas unitarias de `BrowserFallback` + 14 de integración en `voice.test.tsx`). Cero dependencias externas y cero llamadas de red reales en las pruebas automatizadas.

---

## 1. Propósito y Alcance

Garantiza la continuidad del entrenamiento de los estudiantes cuando el servicio de síntesis de voz con IA no esté disponible (por caída del servicio, saturación, límite de cuota o mala conectividad móvil). La experiencia del usuario se degrada de manera transparente sin bloquear la interfaz ni interrumpir su rutina:

1. **Nivel 1 (Ideal - IA):** Audio generado por Gemini TTS servido como WAV desde el backend (`GET /api/v1/plan/exercises/:id/audio`).
2. **Nivel 2 (Respaldo - Voz del Navegador):** Si la API responde con error (ej. `503 AI_UNAVAILABLE`) o supera 15 segundos sin responder, la aplicación lee los pasos y el aviso orientativo utilizando la síntesis nativa del dispositivo (`window.speechSynthesis`).
3. **Nivel 3 (Esencial - Texto en Pantalla):** Si el dispositivo carece de voces en español o de soporte de síntesis, el botón «Escuchar» queda deshabilitado con un aviso informativo claro, manteniendo el texto del ejercicio completamente visible y legible.

### Criterios de Aceptación
- **AC-6-1:** Si el endpoint de audio con IA falla o supera el temporizador de 15 segundos, la aplicación conmuta automáticamente a la voz del navegador en español, leyendo en orden: nombre del ejercicio → pasos numerados → aviso orientativo al final. Muestra una etiqueta visual discreta «Voz del dispositivo».
- **AC-6-2:** Si el navegador no soporta `speechSynthesis` o no dispone de voces en español (`lang` que inicie en `es`), el botón «Escuchar» se deshabilita mostrando el mensaje «Tu dispositivo no tiene voz en español disponible. Puedes leer la explicación en pantalla.» sin ocultar ni alterar las instrucciones textuales.
- **AC-6-3:** Si ocurre un fallo a mitad de la reproducción (evento `error` del audio o de la síntesis), la reproducción se detiene de inmediato (`stop()`), se muestra un aviso de error en español con opción de reintento, y la hoja no se bloquea ni congela.
- **AC-6-4:** Ningún fallo en la capa de audio (sea en IA o en voz local) afecta el funcionamiento del MVP 1: pantallas de Hoy (`/hoy`), Calendario semanal (`/plan`), Detalle de día (`/plan/dia/:fecha`), Explicación de ejercicio ni Perfil de usuario.

---

## 2. Arquitectura y Componentes Frontend

Se estructuró la solución dentro del módulo `apps/web/src/features/voice/`, respetando el desacoplamiento entre el motor de síntesis local y los componentes visuales:

```text
apps/web/src/
├── features/
│   ├── voice/
│   │   ├── BrowserFallback.ts      # Envoltura de SpeechSynthesis con cola de frases y workarounds móviles
│   │   ├── BrowserFallback.test.ts # Pruebas unitarias de disponibilidad, eventos y colas
│   │   ├── useExerciseAudio.ts     # Orquestador de motores (IA vs Browser), timeout de 15s y estado unavailable
│   │   ├── ListenButton.tsx        # Renderizado de estado unavailable con texto explicativo
│   │   ├── PlaybackControls.tsx    # Indicador «Voz del dispositivo» y controles universales
│   │   └── AudioPlayer.ts          # Integración de estado 'unavailable' en AudioPlayerState
│   └── plan/
│       └── ExerciseGuideSheet.tsx  # Inyección de propiedades isUnavailable e isFallback
└── test/
    └── flows/
        └── voice.test.tsx          # 14 pruebas de integración de flujo completo (HU 3 a HU 6)
```

### 2.1 Envoltura de Voz Local (`BrowserFallback.ts`)
- **Detección Asíncrona de Voces (`getSpanishVoices`):**
  En navegadores móviles (iOS Safari y Chrome Android), las voces se cargan de forma asíncrona. La clase escucha el evento `voiceschanged` de `speechSynthesis` y filtra aquellas cuyo código de idioma inicie en `es` (ej. `es-ES`, `es-MX`, `es-US`).
- **Arquitectura de Cola de Frases (`phrases: string[]`):**
  La función `buildExerciseFallbackPhrases(exercise)` descompone el ejercicio en:
  1. Nombre del ejercicio.
  2. Cada paso numerado con formato `Paso N: <texto>` (si el paso no viene ya numerado).
  3. El aviso de descargo de responsabilidad (*disclaimer*) al final una sola vez.
- **Workaround para Bugs de Pausa Móvil:**
  Las implementaciones nativas de `speechSynthesis.pause()` son notoriamente inestables en WebKit y Chrome Android (suelen congelar la cola o provocar silencio indefinido). Para garantizar compatibilidad total con **HU 4**:
  - **Pausar:** Ejecuta `speechSynthesis.cancel()` marcando una bandera `isCancellingExplicitly` y retiene el índice de la frase actual (`currentPhraseIndex`).
  - **Reanudar:** Instancia una nueva `SpeechSynthesisUtterance` a partir de `phrases[currentPhraseIndex]`, continuando la lectura sin perder el hilo.
  - **Repetir:** Cancela la locución actual, restablece `currentPhraseIndex = 0` y arranca nuevamente.
- **Soporte de Velocidades (HU 5):**
  Aplica la tasa configurada (`0.75`, `1`, `1.25`) mediante la propiedad `utterance.rate`. Si se cambia la velocidad en caliente durante la lectura, reinicia la frase actual con el nuevo ritmo.
- **Sincronización Reactiva:**
  Implementa el patrón de suscripción externa compatible con `useSyncExternalStore`, exponiendo `getSnapshot()` con referencias inmutables cacheadas para evitar bucles infinitos de renderizado.

### 2.2 Orquestador de Conmutación (`useExerciseAudio.ts`)
- **Temporizador de Respaldo (`AI_AUDIO_TIMEOUT_MS = 15000`):**
  Al pulsar «Escuchar», si el audio no está en la memoria caché local, se dispara un `setTimeout` a 15 segundos en paralelo a la petición de red con `fetchExerciseAudio`.
- **Conmutación Automática:**
  - Si transcurren 15 segundos sin respuesta, se aborta la espera de la IA y se invoca `startFallback()`.
  - Si la petición falla de inmediato (por ejemplo, con un `503 AI_UNAVAILABLE` o un error de red), se intercepta el estado de error y se activa `startFallback()`.
  - Si el navegador cuenta con voces en español, conmuta el motor a `browser` y reproduce la cola de frases.
  - Si el navegador carece de voces en español, conmuta el estado a `isUnavailable = true`.

### 2.3 Experiencia de Usuario Accesible
- **`ListenButton.tsx`:** Cuando `isUnavailable` es verdadero, el botón permanece deshabilitado (`disabled`) y debajo se renderiza un párrafo informativo accesible (`role="status"`) en color atenuado (`text-muted`).
- **`PlaybackControls.tsx`:** Cuando el audio activo proviene de la síntesis local (`isFallback === true`), se muestra una píldora visual sobria con el ícono de dispositivo y el texto **«Voz del dispositivo»**, comunicando al usuario que se está utilizando la voz del sistema sin generar alarma.

---

## 3. Trazabilidad: Criterios de Aceptación vs Pruebas

| Criterio de Aceptación | Descripción | Pruebas Automatizadas |
|---|---|---|
| **AC-6-1** | Si el endpoint de audio con IA falla (503 / red), conmutar a voz del navegador en español leyendo nombre, pasos y aviso en orden. | `apps/web/src/test/flows/voice.test.tsx::AC-6-1: si la IA falla (503), conmuta automáticamente a la voz del navegador en español`<br>`apps/web/src/test/flows/voice.test.tsx::AC-6-1: si la IA tarda más de 15 s, se aborta y conmuta a la voz del dispositivo` |
| **AC-6-2** | Si tampoco hay voz en el navegador, «Escuchar» se deshabilita con aviso explicativo y el texto de la guía permanece visible. | `apps/web/src/test/flows/voice.test.tsx::AC-6-2: si tampoco hay voz en el navegador, «Escuchar» se deshabilita con aviso explicativo y el texto permanece` |
| **AC-6-3** | Si el audio o la voz fallan a mitad de reproducción, se detiene (`stop()`), muestra error en español con botón de reintento y no bloquea la hoja. | `apps/web/src/test/flows/voice.test.tsx::AC-6-3: si el audio falla a mitad, se detiene, muestra mensaje en español y la hoja no se bloquea` |
| **AC-6-4** | Ningún fallo en el sistema de audio degrada ni rompe las vistas existentes del MVP 1 (Hoy, Calendario, Detalle de Día, Perfil). | `apps/web/src/test/flows/voice.test.tsx::AC-6-4: la degradación de audio no afecta las demás funciones de la aplicación`<br>Verificado por la suite completa de 137 pruebas pasando. |
| **Compatibilidad HU 4 y 5** | Pausa, reanudación, repetición y selector de velocidad funcionan idénticamente con el motor de respaldo del navegador. | `apps/web/src/test/flows/voice.test.tsx::pausa, repetir y velocidad funcionan con el motor de respaldo del navegador`<br>`apps/web/src/features/voice/BrowserFallback.test.ts` (10 pruebas unitarias) |

---

## 4. Diferencias con el Diseño Original y Limitaciones Técnicas

1. **Inconsistencia de Voces entre Sistemas Operativos:**
   - La calidad y el timbre de las voces de `speechSynthesis` dependen enteramente del sistema operativo del usuario:
     - En iOS/macOS suele usarse «Mónica» o «Jorge» (alta fidelidad).
     - En Android suele utilizarse el motor de Google TTS (voz neutra y fluida).
     - En Windows puede variar entre «Microsoft Helena», «Microsoft Laura» o voces locales sintéticas.
   - La aplicación selecciona automáticamente la voz marcada como `default` o la primera coincidencia que empiece con `es` para garantizar que la locución sea comprensible en español.
2. **Estrategia para Pausa/Reanudación Móvil:**
   - Como se documentó en la sección de arquitectura, en lugar de invocar `speechSynthesis.pause()`, se diseñó un ciclo de cancelación y reanudación por puntero de frase (`currentPhraseIndex`), asegurando que «Pausar» y «Reanudar» funcionen de forma infalible en Safari iOS y Chrome Android.

---

## 5. Guía de Prueba Manual (Dispositivo Móvil / Celular Real)

### Requisitos Previos
1. Celular conectado a la misma red local que la computadora de desarrollo.
2. Servidor web corriendo con `npm run dev -- --host` dentro de `apps/web`.

### Pasos de Verificación

#### Escenario A: Degradación por Fallo del Servidor (AC-6-1)
1. Detén el backend de FITIA o simula un error 503 en la ruta de audio.
2. En el celular, abre la aplicación y navega a `/hoy`.
3. Toca un ejercicio para desplegar la hoja inferior (`ExerciseGuideSheet`).
4. Pulsa el botón «Escuchar».
5. **Resultado esperado:** Tras un breve instante, la aplicación conmuta al respaldo del dispositivo. El ejercicio comienza a leerse en voz alta con la voz en español de tu teléfono, aparece la insignia **«Voz del dispositivo»** y se lee primero el título, luego los pasos en orden y finalmente el aviso legal orientativo.

#### Escenario B: Controles de Reproducción con Voz del Dispositivo (HU 4 y HU 5)
1. Durante la lectura con la voz del dispositivo, pulsa el botón **«Pausar»**. La locución se detiene de inmediato.
2. Pulsa **«Reanudar»**. La voz continúa desde el paso en el que se encontraba.
3. Pulsa **«Repetir»**. La voz recomienza desde el nombre del ejercicio y el Paso 1.
4. Toca la velocidad **1,25×**. La velocidad de habla aumenta inmediatamente.

#### Escenario C: Dispositivo sin Voces en Español (AC-6-2)
1. En un navegador de pruebas o perfil sin voces en español instaladas:
2. Abre la explicación de un ejercicio.
3. Intenta escuchar o simula la ausencia de voces.
4. **Resultado esperado:** El botón «Escuchar» se muestra deshabilitado y se aprecia el mensaje: *«Tu dispositivo no tiene voz en español disponible. Puedes leer la explicación en pantalla.»* Las instrucciones en texto permanecen totalmente legibles.
