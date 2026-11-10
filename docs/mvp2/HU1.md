# MVP 2 — HU 1: Generar el audio de un ejercicio con IA

Documentación técnica de la implementación backend de la Historia de Usuario 1 del MVP 2 de FITIA: generación de audio explicativo de técnica de ejercicios mediante síntesis de voz (Gemini TTS).

> **Estado:** Implementado y probado. 645 pruebas backend pasando en suite completa (12 nuevas dedicadas a HU1 y HU2). Cero llamadas externas reales en la suite de pruebas automatizadas (uso de `FakeSpeechAdapter`).

---

## 1. Propósito y Alcance

Permite al estudiante escuchar la explicación hablada en español de la técnica de cualquier ejercicio perteneciente a su plan de entrenamiento activo.

```text
GET /api/v1/plan/exercises/{exercise_id}/audio → 200 OK (audio/wav, Cache-Control: private, max-age=86400)
```

### Reglas de Negocio y Privacidad
1. **Construcción en Servidor:** El cliente únicamente envía el identificador del ejercicio (`exercise_id`). El servidor obtiene el nombre, los pasos técnicos ordenados y el aviso orientativo desde el repositorio local.
2. **Privacidad Estricta (NFR-24):** A la IA de Google Gemini solo viaja el texto pedagógico del ejercicio. Ningún identificador de usuario (`user_id`, correo, apodo) viaja al proveedor de IA.
3. **Estructura Sonora Determinista:** El texto sintetizado sigue el formato:
   `"<nombre>. Paso 1: <paso 1>. Paso 2: <paso 2>. Este contenido es orientativo y no reemplaza la guía de un profesional."`
   El aviso orientativo se incluye una sola vez al final.
4. **Seguridad y Control de Acceso:**
   - Requiere sesión activa (`401 UNAUTHORIZED` si no hay sesión).
   - Requiere perfil completo con diagnóstico (`403 ONBOARDING_REQUIRED` si no ha completado el onboarding).
   - Verificación de pertenencia: solo se pueden escuchar ejercicios de planes activos del usuario autenticado (`404 EXERCISE_NOT_FOUND` si es ajeno o inexistente).
5. **Resiliencia y Circuit Breaker (ADR-16):** Si Gemini falla, agota el tiempo límite o el circuit breaker está abierto, responde inmediatamente `503 AI_UNAVAILABLE` con mensaje en español amigable.
6. **Métricas sin PII (ADR-19):** Cada invocación registra una entrada en la tabla `ai_call_logs` con `use_case="exercise_audio"`, latencia, estado y tokens/coste estimado, sin almacenar texto ni `user_id`.

---

## 2. Arquitectura y Componentes

Se integró bajo el patrón arquitectónico modular `router → service → repository` y los puertos/adaptadores de IA existentes:

```text
apps/api/
├── app/
│   ├── ai/
│   │   ├── ports.py                   # Puerto abstracto SpeechSynthesizer y dataclass SpeechRequest
│   │   ├── gateway.py                 # AIGateway.synthesize(): breaker, recorder, timeout y retries
│   │   ├── adapters/
│   │   │   ├── gemini_speech.py       # Adaptador real google-genai (gemini-3.8-flash-tts, voz Aoede)
│   │   │   └── fake_speech.py         # Adaptador falso determinista para pruebas automatizadas
│   │   └── use_cases/
│   │       └── exercise_audio/
│   │           ├── builder.py         # Constructor de texto pedagógico sin PII
│   │           └── cache.py           # AudioCache en memoria (LRU + single-flight)
│   ├── core/
│   │   ├── config.py                  # GEMINI_TTS_MODEL, GEMINI_TTS_VOICE, RATE_LIMIT_EXERCISE_AUDIO_*
│   │   └── cache_control.py           # NoStoreMiddleware respetando Cache-Control: private en audio
│   └── modules/
│       └── plan/
│           ├── router.py              # Endpoint GET /exercises/{exercise_id}/audio
│           └── service.py             # PlanService.get_exercise_audio()
└── tests/
    ├── unit/
    │   ├── test_exercise_audio_builder.py
    │   ├── test_speech_packaging.py
    │   └── test_fake_speech.py
    └── integration/
        └── test_plan_audio.py
```

### Componentes Clave
- **`SpeechSynthesizer` (`ports.py`):** Interfaz asíncrona abstracta que define `synthesize(request: SpeechRequest) -> bytes`. Devuelve siempre un contenedor WAV listo para reproducir.
- **`GeminiSpeechAdapter` (`adapters/gemini_speech.py`):** Utiliza el SDK oficial `google-genai==2.29.0` con `client.aio.models.generate_content`. Configura `response_modalities=["AUDIO"]` y `speech_config` con voz predefinida. Si el modelo devuelve audio en contenedor RIFF/WAV lo entrega directamente; si devuelve PCM crudo, lo empaqueta automáticamente mediante el módulo estándar `wave`. Mapea excepciones `google.genai.errors.APIError` a `AIProviderError`.
- **`FakeSpeechAdapter` (`adapters/fake_speech.py`):** Genera cabeceras y muestras PCM WAV sintéticas y deterministas sin conexión a la red. Permite inyectar guiones de fallo (`FailSpeech`, `WaitSpeech`, `EmptyOutputSpeech`) para verificar resiliencia.
- **`build_exercise_audio_text` (`use_cases/exercise_audio/builder.py`):** Función pura que recibe `(name, steps, disclaimer)` y construye la cadena limpia en español, omitiendo pasos vacíos y normalizando espacios.

---

## 3. Trazabilidad: Criterios de Aceptación vs Pruebas

| Criterio de Aceptación | Descripción | Pruebas Automatizadas |
|---|---|---|
| **AC-1-1** | Ejercicio propio devuelve audio en español (`audio/wav`) con cabecera `RIFF`, nombre, pasos en orden y aviso orientativo una sola vez. | `apps/api/tests/integration/test_plan_audio.py::test_ac_1_1_camino_feliz_genera_audio_wav_con_texto_correcto`<br>`apps/api/tests/unit/test_exercise_audio_builder.py` |
| **AC-1-2** | El texto lo construye el servidor a partir del plan; el cliente no envía texto ni modifica el guion. | `apps/api/tests/integration/test_plan_audio.py::test_ac_1_2_y_ac_1_3_servidor_construye_texto_sin_datos_de_usuario` |
| **AC-1-3** | A la IA solo viaja el texto del ejercicio, sin identificadores del usuario (`user_id`, email, apodo). | `apps/api/tests/integration/test_plan_audio.py::test_ac_1_2_y_ac_1_3_servidor_construye_texto_sin_datos_de_usuario` |
| **AC-1-4** | Ejercicio ajeno o inexistente responde `404 EXERCISE_NOT_FOUND`; petición sin sesión responde `401 UNAUTHORIZED`. | `apps/api/tests/integration/test_plan_audio.py::test_ac_1_4_seguridad_ejercicio_ajeno_inexistente_y_sin_sesion` |
| **AC-1-5** | Si la IA falla, tarda demasiado o `AI_ENABLED=false`, responde `503 AI_UNAVAILABLE` con mensaje en español. Circuit breaker previene llamadas subsecuentes. | `apps/api/tests/integration/test_plan_audio.py::test_ac_1_5_ia_fallo_breaker_y_disabled_devuelven_503` |
| **AC-1-6** | Cada uso se registra en `ai_call_logs` con `use_case="exercise_audio"`, sin `user_id` ni texto del prompt. | `apps/api/tests/integration/test_plan_audio.py::test_ac_1_6_registro_en_ai_call_logs_sin_usuario_ni_texto` |
| **Empaquetado WAV** | Manejo de PCM crudo a WAV con tasa de 24 kHz mono de 16 bits. | `apps/api/tests/unit/test_speech_packaging.py::test_pcm_to_wav_packaging` |

---

## 4. Guía de Prueba Manual

### 4.1 Requisitos Previos
1. Servidor API ejecutándose:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
2. Tener configurada la variable `GEMINI_API_KEY` en `.env` (si se va a probar con el adaptador real `AI_PROVIDER=gemini`) o usar `AI_PROVIDER=fake`.

### 4.2 Paso 1: Autenticación
Iniciar sesión con un usuario con plan de entrenamiento activo:
```bash
curl -i -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"estudiante.activo@correounivalle.edu.co","password":"Password123!"}' \
  -c cookies.txt
```

### 4.3 Paso 2: Obtener el ID de un Ejercicio
Consultar la rutina de hoy o el plan semanal:
```bash
curl -i -X GET http://localhost:8000/api/v1/plan/today \
  -b cookies.txt
```
Copiar un `exercise_id` (por ejemplo `d3b07384-d113-4632-a548-5c4a6b8f3b20`).

### 4.4 Paso 3: Descargar y Reproducir el Audio
Descargar el archivo WAV generado:
```bash
curl -i -X GET "http://localhost:8000/api/v1/plan/exercises/d3b07384-d113-4632-a548-5c4a6b8f3b20/audio" \
  -b cookies.txt \
  --output ejercicio.wav
```

Verificar en la respuesta:
- `HTTP/1.1 200 OK`
- `Content-Type: audio/wav`
- `Cache-Control: private, max-age=86400`

Para reproducir el audio en Windows (PowerShell):
```powershell
Start-Process .\ejercicio.wav
```
O abrirlo con cualquier reproductor multimedia (VLC, Windows Media Player).

### 4.5 Paso 4: Pruebas de Seguridad y Casos Límite
1. **Sin Sesión:**
   ```bash
   curl -i -X GET "http://localhost:8000/api/v1/plan/exercises/d3b07384-d113-4632-a548-5c4a6b8f3b20/audio"
   ```
   *Respuesta esperada:* `401 Unauthorized`.
2. **Ejercicio Inexistente o Ajeno:**
   ```bash
   curl -i -X GET "http://localhost:8000/api/v1/plan/exercises/00000000-0000-0000-0000-000000000000/audio" \
     -b cookies.txt
   ```
   *Respuesta esperada:* `404 Not Found` (`code: "EXERCISE_NOT_FOUND"`).

---

## 5. Limitaciones Técnicas

1. **Latencia del Servicio TTS:** Las llamadas directas a la API de Google Gemini TTS pueden demorar entre 1.5 y 3.5 segundos en completarse. La optimización y atenuación de esta latencia para peticiones repetidas se resuelve mediante la arquitectura de caché de la **HU 2**.
2. **Disponibilidad de Modelos:** El modelo `gemini-3.8-flash-tts` requiere conexión externa a Google GenAI. Si no hay conexión o se agotan las cuotas, el circuit breaker degrada de forma segura respondiendo `503 AI_UNAVAILABLE`.
