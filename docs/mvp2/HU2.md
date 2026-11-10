# MVP 2 — HU 2: Reutilizar audios y controlar el costo

Documentación técnica de la implementación backend de la Historia de Usuario 2 del MVP 2 de FITIA: estrategia de caché en memoria de proceso, coalescencia de peticiones concurrentes (single-flight), límites de frecuencia y control de costos para síntesis de audio.

> **Estado:** Implementado y probado. 645 pruebas backend pasando en suite completa (12 nuevas dedicadas a HU1 y HU2). Cero migraciones de base de datos añadidas (el audio nunca se persiste en PostgreSQL).

---

## 1. Propósito y Alcance

Garantizar la sostenibilidad económica y el rendimiento del servicio de audio mediante tres mecanismos de optimización:
1. **Caché en Memoria del Servidor:** Reutilizar audios ya sintetizados para el mismo texto, modelo y voz, evitando llamadas repetidas a la IA.
2. **Coalescencia de Solicitudes Concurrentes (Single-Flight):** Si dos o más solicitudes simultáneas piden el mismo audio, solo una realiza la llamada a Gemini mientras las demás esperan el resultado compartido.
3. **Control de Costo y Abuso:** Límite de frecuencia estricto por usuario y cabeceras HTTP de caché privada para el cliente.

```text
GET /api/v1/plan/exercises/{exercise_id}/audio
Header: Cache-Control: private, max-age=86400
```

---

## 2. Arquitectura y Componentes

### 2.1 Caché en Memoria y Single-Flight (`AudioCache`)
Ubicada en `apps/api/app/ai/use_cases/exercise_audio/cache.py`:
- **Algoritmo de Desalojo:** LRU (*Least Recently Used*) con `OrderedDict` y límite configurable (por defecto 128 audios sintetizados o tope en bytes).
- **Clave Canónica:** Hash criptográfico SHA-256 de la tupla `(modelo, voz, texto)`:
  ```python
  key = hashlib.sha256(f"{model}:{voice}:{text}".encode("utf-8")).hexdigest()
  ```
- **Mecanismo Single-Flight:**
  Mantiene un registro de futuros en vuelo `_in_flight: dict[str, asyncio.Future]`.
  - La primera petición crea un `Future` y ejecuta la llamada a la IA mediante `gateway.synthesize(...)`.
  - Las peticiones concurrentes con la misma clave detectan el `Future` en curso y hacen `await asyncio.shield(future)`.
  - Al completar la síntesis, el resultado se guarda en la caché LRU y el `Future` se resuelve para todas las solicitudes concurrentes.
  - En caso de error, el fallo se propaga a los observadores concurrentes sin envenenar la caché (`_in_flight.pop(key)` siempre se ejecuta en un bloque `finally`).

### 2.2 Política de Almacenamiento en Base de Datos (ADR-18)
- **Cero Persistencia de Audio en PostgreSQL:** El audio sintetizado es un archivo binario temporal que **no** se guarda en la base de datos para evitar degradación de rendimiento y costos innecesarios de almacenamiento relacional.
- **Sin Migraciones:** La tabla `ai_call_logs` admite libremente los campos `use_case="exercise_audio"` y `prompt_version="v1"` sin requerir modificaciones de esquema ni migraciones de Alembic.

### 2.3 Cabeceras HTTP y Compatibilidad con `NoStoreMiddleware`
- El middleware global de seguridad `NoStoreMiddleware` asigna `Cache-Control: no-store` a todas las respuestas autenticadas para proteger datos personales.
- Para el endpoint de audio, se implementó una excepción explícita y acotada:
  - Solo si la respuesta es `200 OK` y ya incluye una directiva `Cache-Control: private...`, el middleware respeta la cabecera del router (`private, max-age=86400`).
  - Si el endpoint responde con un error (`401`, `403`, `404`, `429`, `503`), el middleware fuerza `Cache-Control: no-store` para que ningún error sea almacenado en el navegador.

### 2.4 Límite de Frecuencia (Rate Limiting)
- Se reutiliza la infraestructura existente `InMemoryRateLimiter` en `apps/api/app/modules/plan/service.py`.
- **Regla:** 30 peticiones por usuario en una ventana de 15 minutos (`RATE_LIMIT_EXERCISE_AUDIO_PER_USER=30`, `RATE_LIMIT_EXERCISE_AUDIO_WINDOW_MINUTES=15`).
- Al exceder la cuota, responde `429 Too Many Requests` (`code: "RATE_LIMIT_EXCEEDED"`).

---

## 3. Trazabilidad: Criterios de Aceptación vs Pruebas

| Criterio de Aceptación | Descripción | Pruebas Automatizadas |
|---|---|---|
| **AC-2-1 (Caché)** | El mismo ejercicio pedido sucesivamente reutiliza el audio en memoria sin realizar nuevas llamadas a la IA. | `apps/api/tests/integration/test_plan_audio.py::test_ac_2_1_reutilizacion_cache_y_single_flight`<br>`apps/api/tests/unit/test_audio_cache.py::test_cache_hit_and_eviction` |
| **AC-2-1 (Single-Flight)** | Dos peticiones concurrentes para el mismo ejercicio se combinan en una única llamada a la IA. | `apps/api/tests/integration/test_plan_audio.py::test_ac_2_1_reutilizacion_cache_y_single_flight`<br>`apps/api/tests/unit/test_audio_cache.py::test_single_flight_coalescing` |
| **AC-2-2** | El audio no se persiste en base de datos. Ninguna tabla o columna nueva fue añadida. Pruebas de migración pasan. | `apps/api/tests/integration/test_plan_audio.py::test_ac_2_2_el_audio_no_se_persiste_en_base_de_datos`<br>`apps/api/tests/integration/test_migrations.py` |
| **AC-2-3** | Cabecera `Cache-Control: private, max-age=86400` presente en 200 OK. Errores y resto de rutas mantienen `no-store`. | `apps/api/tests/integration/test_plan_audio.py::test_ac_2_3_cabecera_cache_control_private`<br>`apps/api/tests/integration/test_no_store.py` |
| **AC-2-4** | Exceder el límite de 30 llamadas en 15 minutos devuelve `429 RATE_LIMIT_EXCEEDED`. El circuit breaker existente se respeta. | `apps/api/tests/integration/test_plan_audio.py::test_ac_2_4_limite_de_frecuencia_responde_429` |

---

## 4. Guía de Prueba Manual

### 4.1 Prueba de Caché Secuencial (Latencia y Ahorro)
1. Realizar una primera llamada y medir el tiempo de respuesta:
   ```bash
   time curl -i -X GET "http://localhost:8000/api/v1/plan/exercises/{exercise_id}/audio" \
     -b cookies.txt \
     --output audio1.wav
   ```
   *Resultado 1ª llamada:* Se invoca a Gemini TTS (latencia ~1.5s - 2.5s). Se registra en `ai_call_logs`.
2. Realizar inmediatamente una segunda llamada para el mismo ejercicio:
   ```bash
   time curl -i -X GET "http://localhost:8000/api/v1/plan/exercises/{exercise_id}/audio" \
     -b cookies.txt \
     --output audio2.wav
   ```
   *Resultado 2ª llamada:* Respuesta casi instantánea (< 10 ms). No se generan nuevas llamadas en `ai_call_logs`.
3. Comparar los archivos generados:
   ```powershell
   Get-FileHash .\audio1.wav, .\audio2.wav
   ```
   Los hashes SHA-256 de ambos archivos deben ser idénticos.

### 4.2 Prueba de Peticiones Concurrentes (Single-Flight)
En PowerShell, lanzar dos llamadas concurrentes mediante trabajos en segundo plano:
```powershell
$job1 = Start-Job -ScriptBlock { curl.exe -s "http://localhost:8000/api/v1/plan/exercises/$using:exercise_id/audio" -b cookies.txt -o test1.wav }
$job2 = Start-Job -ScriptBlock { curl.exe -s "http://localhost:8000/api/v1/plan/exercises/$using:exercise_id/audio" -b cookies.txt -o test2.wav }
Wait-Job $job1, $job2
Receive-Job $job1, $job2
```
*Verificación:* Ambas peticiones completan con éxito `200 OK`, pero en la tabla `ai_call_logs` solo se registró una única invocación a la IA.

### 4.3 Prueba del Límite de Frecuencia (Rate Limiter)
Ejecutar un ciclo que supere las 30 peticiones:
```powershell
1..35 | ForEach-Object {
    $res = curl.exe -s -o /dev/null -w "%{http_code}`n" "http://localhost:8000/api/v1/plan/exercises/$exercise_id/audio" -b cookies.txt
    Write-Host "Petición $_ : $res"
}
```
*Resultado:* Las primeras 30 peticiones devuelven `200 OK`. A partir de la petición 31, el servidor responde `429 Too Many Requests`.

---

## 5. Limitaciones Técnicas

1. **Caché Local al Proceso:** La instancia de `AudioCache` reside en la memoria RAM del proceso de la aplicación (`uvicorn`). Si el servidor se reinicia o se despliega una nueva versión, la memoria se vacía y las primeras peticiones volverán a consultar a la IA.
2. **Topología Multi-Worker:** En caso de desplegar múltiples workers de Uvicorn (o réplicas horizontales de contenedores) sin afinidad de sesión (*sticky sessions*), cada worker mantendrá su propio `AudioCache` independiente. Si se requiere persistencia distribuida a largo plazo en futuras iteraciones, se recomendará una capa externa como Cloudflare R2 o almacenamiento S3/Redis conforme a la ADR correspondiente.
