<!-- CODEGRAPH_START -->
## CodeGraph

In repositories indexed by CodeGraph (a `.codegraph/` directory exists at the repo root), reach for it BEFORE grep/find or reading files when you need to understand or locate code:

- **MCP tool** (when available): `codegraph_explore` answers most code questions in one call — the relevant symbols' verbatim source plus the call paths between them, including dynamic-dispatch hops grep can't follow. Name a file or symbol in the query to read its current line-numbered source. If it's listed but deferred, load it by name via tool search.
- **Shell** (always works): `codegraph explore "<symbol names or question>"` prints the same output.

If there is no `.codegraph/` directory, skip CodeGraph entirely — indexing is the user's decision.
<!-- CODEGRAPH_END -->

## 📦 Convenciones de Commits y Flujo de Trabajo

Este proyecto sigue una estrategia de **commits atómicos por Historia de Usuario (Story-Driven Commits)**. Cada commit representa una entrega funcional completa (vertical slice) de una Historia de Usuario (HU), integrando código, base de datos, pruebas y documentación.

### 1. Filosofía de Atomicidad por HU
Cada commit de HU debe incluir:
- **Código y Arquitectura:** Routers, servicios, repositorios, schemas y modelos según el patrón modular (`router → service → repository`).
- **Persistencia y Migraciones:** Migración de Alembic versionada (`apps/api/migrations/versions/XXXX_hu<N>_*.py`) con soporte bidireccional (`upgrade` y `downgrade`) e integridad referencial (`ON DELETE CASCADE` en tablas de usuario).
- **Pruebas Automatizadas:** Pruebas unitarias e integración en `apps/api/tests/` que verifiquen los Criterios de Aceptación (AC) y Requisitos No Funcionales (NFR). Sin llamadas externas reales a APIs de terceros en la suite de tests (usar fakes/mocks).
- **Documentación de Trazabilidad:** Archivo `docs/HU<N>.md` con el diseño, tabla de criterios de aceptación vs pruebas, y guía de prueba manual.

### 2. Estructura y Plantilla del Mensaje de Commit

```text
HU<N>: <descripción concisa de la funcionalidad en minúsculas>

<Párrafo introductorio de 2 a 3 líneas explicando el propósito de negocio, decisiones arquitectónicas y alcance>

- <Endpoints HTTP nuevos o modificados con códigos de estado: VERBO /ruta (CÓDIGO)>
- <Módulos o componentes creados/actualizados (core, modules, ai, etc.)>
- <Migración de BD (número y tablas) con índices, FKs y restricciones>
- <Reglas de negocio, validaciones, rate limits, privacidad o seguridad>
- <Semillas, utilidades o scripts de prueba manual (si aplica)>
- <Métricas de pruebas: Total de pruebas pasando (X nuevas)>
- docs/HU<N>.md.

Co-Authored-By: <Nombre o Asistente> <<correo>> (opcional)
```

### 3. Estrategia de Ramas
- Ramas nombradas por Épica (ej. `E1`, `E7`) que agrupan las historias relacionadas.
- Integración hacia `main` una vez validado el CI (pruebas y linters en GitHub Actions).

### 4. Nomenclatura Estándar de Historias de Usuario
- Toda documentación técnica de Historias de Usuario debe nombrarse estrictamente bajo el formato **`docs/HU<N>.md`** (ej. `docs/HU1.md`, `docs/HU2.md`, ..., `docs/HU6.md`).
- **Prohibido duplicar archivos** o usar nomenclaturas abreviadas como `H<N>.md` (ej. no crear `H6.md` ni `docs/H6.md`). Las siglas `H<N>` y `HU<N>` son equivalentes y el único estándar oficial del proyecto es **`HU<N>`**.
- La documentación de las historias de usuario debe residir siempre dentro del directorio `docs/`, nunca en la raíz del repositorio.
