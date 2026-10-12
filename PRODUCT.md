# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

React + Vite + TypeScript, Tailwind CSS, TanStack Query, React Hook Form + Zod, FastAPI, Supabase (PostgreSQL), Google Gemini

## Users

Estudiantes de la Universidad del Valle (Univalle). Arquetipos principales:
- **Principiante:** Requiere un entorno seguro, técnica explicada paso a paso y rutinas iniciales no intimidantes.
- **Intermitente:** Requiere sesiones cortas y flexibles que encajen entre clases y entregas académicas.
- **Activo orientado a metas:** Desea progresión estructurada, medición de métricas deportivas y retos constantes.

## Product Purpose

Entrenamiento personal inteligente con gamificación e Inteligencia Artificial para convertir la intención de entrenar en un hábito sostenible, adaptándose a los horarios cambiantes y a la infraestructura deportiva (CDU) de los estudiantes.

## Positioning

Solución hiperlocalizada para la comunidad estudiantil de Univalle: rutinas filtradas por tiempo y disponibilidad real de máquinas en el campus, soporte de días hábiles y festivos de Colombia/Univalle, y gamificación social privada (ranking con apodos y programas académicos, sin exponer correos ni nombres reales).

## Operating Context

- Uso cotidiano desde dispositivos móviles y web mientras el estudiante está en el campus o entrenando en sus horas libres.
- Registro y acceso exclusivo con correo institucional `@correounivalle.edu.co`.
- Operación en huso horario `America/Bogota` para corte de días, retos diarios y cálculo de festivos.

## Capabilities and Constraints

- **Capacidades clave:**
  - Registro institucional con apodo, programa académico y verificación por enlace de un solo uso.
  - Diagnóstico inicial de metas y disponibilidad física.
  - Resumen interpretado por IA (Google Gemini) con fallback transparente.
  - "Entrenar hoy": selección de rutinas por tiempo y máquinas sin modificar el perfil guardado.
  - Bodega de ejercicios con 15 guías técnicas paso a paso.
  - Calendario semanal de entrenamiento con descansos y festivos programados.
  - Sistema de gamificación completo: XP, niveles progresivos, rachas de días hábiles, recuperación de racha y ranking global.
- **Restricciones confirmadas:**
  - Supabase como Postgres puro sin Auth ni PostgREST en cliente (ADR-02).
  - Autenticación propia en servidor con tokens opacos, cookies HttpOnly y contraseñas Argon2id (ADR-03).
  - Proxy de reescritura en Vercel (`/api/*` hacia Render) para eliminar CORS (ADR-04).
  - Privacidad estricta: DTO cerrado con zero PII enviado a Gemini (ADR-07).

## Brand Commitments

- **Nombre:** FITIA (Fit-AI).
- **Tono:** Empático, motivador, claro, estructurado y enfocado en la salud y bienestar estudiantil.

## Evidence on Hand

- Documento oficial de descubrimiento, backlog (33 Historias de Usuario con criterios de aceptación Gherkin) y 13 Decisiones de Arquitectura de Software (ADRs) documentadas en `docs/ADRS.md`.

## Product Principles

1. **Cero fricción para entrenar:** Menos decisiones previas y rutinas claras listas en segundos.
2. **Gamificación centrada en el hábito:** Premiar la constancia y el esfuerzo real mediante rachas, XP y niveles progresivos.
3. **Privacidad institucional innegociable:** La identidad académica y los datos personales están totalmente protegidos; los LLMs externos solo reciben datos deportivos abstractos.
4. **Contexto universitario real:** Todo el diseño operativo responde al calendario, espacios y dinámicas de la Universidad del Valle.
