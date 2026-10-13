# Guía de estilos del frontend de FITIA

Documenta el sistema de diseño tal como está implementado en `apps/web/` (HU 1 a HU 7). Sirve para construir pantallas nuevas (HU 8 en adelante) que se vean y se comporten igual que las existentes.

**Regla de esta guía:** solo describe lo que existe en el código. Cada valor cita su archivo (rutas desde la raíz del repositorio). Lo que se pidió y no se implementó, o lo que se implementó con una deficiencia, está en la sección [10. Pendientes y deficiencias conocidas](#10-pendientes-y-deficiencias-conocidas).

## Contenido

1. [Introducción](#1-introducción)
2. [Tokens de diseño](#2-tokens-de-diseño)
3. [Iconografía e ilustraciones](#3-iconografía-e-ilustraciones)
4. [Layout y navegación](#4-layout-y-navegación)
5. [Catálogo de componentes](#5-catálogo-de-componentes)
6. [Patrones de interacción](#6-patrones-de-interacción)
7. [Contenido y tono](#7-contenido-y-tono)
8. [Accesibilidad](#8-accesibilidad)
9. [Convenciones de código](#9-convenciones-de-código)
10. [Pendientes y deficiencias conocidas](#10-pendientes-y-deficiencias-conocidas)

---

## 1. Introducción

### Propósito

Que cualquier persona del equipo pueda agregar una pantalla sin decidir de nuevo colores, tamaños, mensajes ni patrones de error. Si algo que necesitas no está aquí, primero búscalo en `apps/web/src/shared/ui/`; si no existe, créalo ahí (no dentro de una pantalla) y documéntalo en esta guía.

### Principios de diseño

| Principio | Cómo se ve en el código |
|---|---|
| **Móvil primero** | Una sola columna de `max-w-xl` (36 rem); navegación inferior fija; se verificó sin desbordamiento horizontal a 360 px. |
| **Baja fricción para principiantes** | El diagnóstico va de una pregunta por pantalla con tarjetas grandes; el plan se genera solo al terminar; los textos explican qué pasó y qué hacer. |
| **Gamificación que motiva sin presionar** | Puntos, nivel y posición están en el perfil en un tono neutro; el estado sin puntos dice "Completa entrenamientos para sumar puntos"; el ranking permite ocultarse. No hay rachas, alertas ni avisos de "vas último". |
| **Tono cercano en español de Colombia** | Tuteo, oraciones cortas, sin jerga médica ni promesas de resultados (ver [sección 7](#7-contenido-y-tono)). |
| **Un solo elemento memorable** | Los carriles de la semana: el día de hoy lleva el rojo institucional con franjas de pista. Todo lo demás es sobrio. |

### Concepto visual

La identidad parte de la pista del CDU de Univalle: el **rojo institucional** hace de tartán y el **verde cancha** marca descanso y logros. La semana se muestra como cinco carriles (un día por carril). La paleta está en `apps/web/src/styles/index.css`.

### Stack de estilos

| Pieza | Versión | Dónde |
|---|---|---|
| Tailwind CSS (configuración "CSS-first", sin `tailwind.config.js`) | 4.3.3 | `apps/web/src/styles/index.css`, plugin en `apps/web/vite.config.ts` |
| Tokens como variables CSS, expuestos a Tailwind con `@theme inline` | — | `apps/web/src/styles/index.css` |
| Tipografías autoalojadas con Fontsource | Bricolage Grotesque Variable 5.3.0, Atkinson Hyperlegible Next 5.3.0 | `apps/web/package.json`, importadas en `index.css` |
| Modo oscuro | Sigue la preferencia del sistema (`prefers-color-scheme`); no hay interruptor manual | `index.css` |
| Utilidad `cx()` para unir clases condicionales | — | `apps/web/src/shared/lib/cx.ts` |

---

## 2. Tokens de diseño

Todos los colores son variables CSS `--c-*` definidas en `:root` y redefinidas en `@media (prefers-color-scheme: dark)`. `@theme inline` las publica como utilidades de Tailwind (`bg-surface`, `text-ink`, `border-line`, …). **Nunca uses un hex suelto en un componente**; usa la utilidad del token (ver [sección 9](#9-convenciones-de-código)).

Fuente de todos los valores de esta sección: `apps/web/src/styles/index.css`, salvo que se indique otra.

### 2.1 Colores

#### Primarios (marca)

| Utilidad | Variable | Claro | Oscuro | Uso previsto |
|---|---|---|---|---|
| `primary` | `--c-primary` | `#C8102E` | `#D61F3C` | Fondo del botón primario, carril de hoy, borde y relleno de lo seleccionado, barra de progreso, favicon. |
| `primary-strong` | `--c-primary-strong` | `#A50D26` | `#EF3A56` | Botón primario en `hover`. |
| `primary-text` | `--c-primary-text` | `#B00E29` | `#FF8494` | Texto en rojo sobre fondos neutros: enlaces, botón `ghost`, "Hola, {apodo}". Es más oscuro (claro) o más claro (oscuro) que `primary` para llegar a AA como texto. |
| `on-primary` | `--c-on-primary` | `#FFFFFF` | `#FFFFFF` | Texto e íconos sobre `primary`. |

#### Neutros

| Utilidad | Variable | Claro | Oscuro | Uso previsto |
|---|---|---|---|---|
| `bg` | `--c-bg` | `#F6F7F5` ("tiza") | `#15191E` | Fondo de la página. |
| `surface` | `--c-surface` | `#FFFFFF` | `#1E242B` | Tarjetas, campos, diálogos, menús. |
| `surface-2` | `--c-surface-2` | `#ECEEEB` | `#272E36` | Fondos secundarios: esqueletos, pista de la barra de progreso, carriles no destacados, hover. |
| `line` | `--c-line` | `#D5D9D6` | `#38414B` | Bordes de tarjetas y campos, divisores. |
| `ink` | `--c-ink` | `#1C2126` ("grafito") | `#EEF1F4` | Texto principal. |
| `muted` | `--c-muted` | `#565F69` | `#A8B1BC` | Texto secundario y de ayuda. |

#### Semánticos

| Utilidad (color / fondo suave) | Claro | Oscuro | Uso previsto |
|---|---|---|---|
| `success` / `success-soft` | `#146C5B` / `#E3F1EC` | `#5FC8A9` / `#173A32` | Confirmaciones, aviso de éxito. |
| `warn` / `warn-soft` | `#8F4B05` / `#FBF0DF` | `#F2B45C` / `#3A2A14` | Advertencias que no bloquean (plan vigente con fallo de actualización, correo ya registrado). |
| `danger` / `danger-soft` | `#B3132D` / `#FBE6E9` | `#FF8494` / `#3E1A20` | Errores, texto de error de campo, acciones destructivas. |
| `info` / `info-soft` | `#2563A6` / `#E5EEF8` | `#7FB2EC` / `#1A2C40` | Información neutra (plan desactualizado, "tu plan actual no cambia"). |
| `focus` | `#2563A6` | `#7FB2EC` | Anillo de foco visible. |

`success` y `rest` tienen el mismo valor a propósito: el verde de "logrado" y el de "descanso" son la misma familia.

#### Estados de los días del plan

Los define `WeekLanes` (`apps/web/src/features/plan/WeekLanes.tsx`) combinando tokens; no existen tokens propios para ellos.

| Estado de la API | Carril lateral (día y fecha) | Tarjeta | Contenido |
|---|---|---|---|
| `training` (hoy) | `bg-primary text-on-primary` + `lane-stripes`, texto "Hoy" | `border-2 border-primary bg-surface` | Título (hasta 2 líneas) y duración con ícono de reloj. |
| `training` (otro día) | `bg-surface-2 text-muted` | `border-2 border-line bg-surface` | Título y duración. |
| `rest` | `bg-rest-soft text-rest` | `border-2 border-line bg-surface` | "Descanso" en `text-rest` + "Recuperar también es parte del plan." |
| `unplanned` | `bg-surface-2 text-muted` | `border-2 border-dashed bg-transparent` | "Sin plan" + "Este día ya había pasado cuando armamos tu plan." |
| `completed` | `bg-surface-2 text-muted` | `border-2 border-line bg-surface` | "Completado" en `text-success`. La API todavía no lo emite. |

Si el día es **hoy**, el carril lateral usa siempre el rojo con franjas y la tarjeta lleva borde `primary`, sea de entrenamiento o de descanso. El estado nunca depende solo del color: cambian además el borde (continuo / punteado), el texto y la etiqueta "Hoy".

#### Otros valores de color

| Valor | Dónde |
|---|---|
| Tarjeta de opción seleccionada: `bg-primary/8` (8 % de `primary`) sobre `surface` | `apps/web/src/shared/ui/OptionCards.tsx` |
| Franjas de pista: blanco al 18 % sobre `primary` (utilidad `lane-stripes`) | `index.css` (`@utility lane-stripes`) |
| Telón de los diálogos: `bg-ink/50` | `apps/web/src/shared/ui/ConfirmDialog.tsx` |
| `theme-color` del navegador: `#C8102E` (un solo valor, no cambia con el modo) | `apps/web/index.html` |

### 2.2 Contraste

Relaciones de contraste WCAG calculadas a partir de los tokens de `index.css` para las combinaciones que realmente usa el código. Umbrales: 4.5:1 texto normal, 3:1 texto grande (≥ 24 px, o ≥ 18.7 px en negrita) y componentes de interfaz.

**Texto sobre fondo**

| Texto / fondo | Dónde se usa | Claro | Oscuro |
|---|---|---|---|
| `ink` / `bg` | Texto de página | 15.09 ✔ | 15.57 ✔ |
| `ink` / `surface` | Texto en tarjetas | 16.22 ✔ | 13.80 ✔ |
| `ink` / `surface-2` | Texto sobre superficie secundaria | 13.90 ✔ | 12.10 ✔ |
| `muted` / `bg` | Textos de ayuda | 6.04 ✔ | 8.14 ✔ |
| `muted` / `surface` | Ayuda dentro de tarjetas | 6.49 ✔ | 7.21 ✔ |
| `muted` / `surface-2` | Carril de día sin descanso | 5.56 ✔ | 6.33 ✔ |
| `muted` / `rest-soft` | Texto atenuado sobre verde suave | 5.58 ✔ | 5.74 ✔ |
| `primary-text` / `bg` | Enlaces y "Hola, {apodo}" | 6.64 ✔ | 7.55 ✔ |
| `primary-text` / `surface` | Enlaces en tarjetas | 7.14 ✔ | 6.69 ✔ |
| `primary-text` / `surface-2` | Botón `ghost` en hover | 6.12 ✔ | 5.87 ✔ |
| `on-primary` / `primary` | Botón primario, carril de hoy, podio | 5.88 ✔ | 5.10 ✔ |
| `on-primary` / `primary-strong` | Botón primario en hover | 7.82 ✔ | **3.88 ✘** (ver sección 10) |
| `on-primary` / `danger` (claro) · `bg` / `danger` (oscuro) | Botón de peligro (`dark:text-bg`) | 6.89 ✔ | 7.55 ✔ |
| `on-primary` / `rest` (claro) · `bg` / `rest` (oscuro) | Toast de éxito | 6.31 ✔ | 8.68 ✔ |
| `on-primary` / `danger` (claro) · `bg` / `danger` (oscuro) | Toast de error | 6.89 ✔ | 7.55 ✔ |
| `bg` / `ink` | Toast informativo | 15.09 ✔ | 15.57 ✔ |
| `rest` / `rest-soft` | "Descanso" en el carril | 5.43 ✔ | 6.12 ✔ |
| `rest` / `surface` | "Descanso" en la tarjeta | 6.31 ✔ | 7.69 ✔ |
| `danger` / `bg` · `danger` / `surface` | Error de campo | 6.41 · 6.89 ✔ | 7.55 · 6.69 ✔ |
| `ink` / `*-soft` (info, warn, danger, success) | Cuerpo de los banners | 13.59 – 14.39 ✔ | 10.98 – 13.49 ✔ |
| `success`, `warn`, `info`, `danger` / su `*-soft` | Glifo del banner | 5.25 – 5.87 ✔ | 6.12 – 7.53 ✔ |

**Componentes y elementos no textuales (mínimo 3:1, WCAG 1.4.11)**

| Elemento | Claro | Oscuro |
|---|---|---|
| Anillo de foco `focus` / `bg` · `surface` | 5.72 · 6.15 ✔ | 7.97 · 7.06 ✔ |
| Borde seleccionado `primary` / `bg` | 5.47 ✔ | 3.46 ✔ |
| Borde de campo con error `danger` / `bg` | 6.41 ✔ | 7.55 ✔ |
| Interruptor encendido `rest` / `surface-2` | 5.41 ✔ | 6.74 ✔ |
| **Borde de campos y tarjetas de opción `line` / `bg` · `surface`** | **1.33 · 1.43 ✘** | **1.70 · 1.51 ✘** |
| **Texto de ejemplo (`placeholder`, `muted` al 70 %) / `surface`** | **3.26 ✘** | 4.30 ✘ |
| **Texto pequeño sobre las franjas de pista** (blanco / franja) | 4.67 ✔ | **4.08 ✘** |

Las filas en negrita son deficiencias reales; están en la [sección 10](#10-pendientes-y-deficiencias-conocidas). Las pruebas con axe no las detectan porque axe no mide el contraste de bordes.

### 2.3 Tipografía

Fuente: `apps/web/src/styles/index.css` (`@theme inline`, `@layer base`).

| Rol | Familia | Pesos cargados | Dónde se usa |
|---|---|---|---|
| **Display** (`font-display`) | Bricolage Grotesque Variable (eje de peso variable) | 700, 800 (los usados) | Encabezados `h1`–`h3`, marca, cifras del perfil, letras de los carriles. |
| **Texto** (`font-sans`, por defecto en `body`) | Atkinson Hyperlegible Next | 400 y 700 | Todo el texto de lectura, etiquetas, botones. |

Ambas tienen respaldo `"Segoe UI", system-ui, sans-serif`. Se eligió Atkinson Hyperlegible por legibilidad en pantallas pequeñas.

**Base:** `body` usa `1.0625rem` (17 px) con altura de línea `1.55`, `antialiased` y `-webkit-text-size-adjust: 100%`. `h1`–`h3` usan `font-display`, `letter-spacing: -0.015em`, `text-wrap: balance`; los párrafos usan `text-wrap: pretty`.

| Nivel | Tamaño / altura de línea | Peso | Uso |
|---|---|---|---|
| Titular de bienvenida | `2.6rem` (41.6 px) / 1.05 en móvil; `text-5xl` 3 rem / 1.05 desde `sm` | 800 | `h1` de `apps/web/src/features/welcome/WelcomePage.tsx`. |
| `h1` de pantalla | `text-3xl` 1.875 rem / 1.2 | 800 | Título de cada pantalla. |
| `h2` de sección | `text-2xl` 1.5 rem / 1.33 | 700 | Pregunta del diagnóstico, "Cómo funciona", panel "Estamos armando tu plan…". |
| `h2` de tarjeta | `text-xl` 1.25 rem / 1.4 | 700 | "Mi diagnóstico", "Datos físicos", "Privacidad", "Cuenta". |
| Destacado | `text-lg` 1.125 rem / 1.56 | 700 (títulos) / 400 (introducciones) | Título del día en el carril, texto introductorio de la bienvenida. |
| Cuerpo | 1.0625 rem / 1.55 | 400 | Párrafos. |
| Cuerpo de banner | `0.975rem` (15.6 px) | 400 | `Banner`. |
| Secundario | `text-sm` 0.875 rem / 1.43 | 400–700 | Ayudas bajo campos, errores de campo, contador, meta. |
| Mínimo | `text-xs` 0.75 rem / 1.33 | 400–700 | Abreviatura de día en los chips y fecha corta del carril. |

Cuando un elemento lleva una utilidad `text-*`, esa utilidad trae su propia altura de línea y reemplaza la `1.15` base de los encabezados. Los pesos 700 (`font-bold`, la mayoría de etiquetas y botones) y 800 (`font-extrabold`, titulares) son los únicos usados fuera de 400. Las cifras del ranking usan `tabular-nums`.

Longitud de línea: la columna de contenido mide `36rem` (576 px), unos 60–65 caracteres, por debajo de los 80 recomendados.

### 2.4 Espaciado, radios, sombras, bordes y capas

**Espaciado.** Escala de Tailwind: `--spacing: 0.25rem`, es decir, múltiplos de 4 px (`apps/web/src/styles/index.css`, generado por Tailwind). Valores recurrentes:

| Uso | Valor |
|---|---|
| Margen lateral de página | `px-4` (16 px) |
| Margen vertical de página | `py-6` (24 px) |
| Relleno de `Card` | `p-5` (20 px), `sm:p-6` (24 px) |
| Separación entre campos de un formulario | `gap-6` (24 px) |
| Separación entre tarjetas de opción | `gap-3` (12 px) |
| Separación entre carriles de la semana | `gap-2.5` (10 px) |
| Espacio entre secciones del perfil | `gap-6` |

**Radios** (`index.css`):

| Utilidad | Valor | Uso |
|---|---|---|
| `rounded-[var(--radius-control)]` | `0.75rem` (12 px) | Botones, campos, tarjetas de opción, chips, banners, listas desplegables. |
| `rounded-[var(--radius-card)]` | `1.25rem` (20 px) | Tarjetas, carriles, diálogo, panel de generación, podio. |
| `rounded-lg` | `0.5rem` (8 px, valor de Tailwind) | Botones de menú, enlace de marca, botón "Ver/Ocultar". |
| `rounded-full` | círculo | Barra de progreso, interruptor, punto de la opción, insignias. |

**Sombras.** Un solo token, `--shadow-raised` (utilidad `shadow-raised`):

| Modo | Valor |
|---|---|
| Claro | `0 1px 2px rgb(28 33 38 / .06), 0 6px 18px -8px rgb(28 33 38 / .18)` |
| Oscuro | `0 1px 2px rgb(0 0 0 / .4), 0 8px 22px -10px rgb(0 0 0 / .6)` |

Se usa solo en elementos que flotan: lista del selector, menú de cuenta, diálogo y toast. Las tarjetas **no** llevan sombra: se separan con borde.

**Bordes.** `border` (1 px, `border-line`) en `Card`; `border-2` en controles, tarjetas de opción, carriles y banners; anillo de foco de 3 px (ver sección 8); `ring-3` para resaltar la posición propia en el podio.

**Capas (`z-index`)** — fuente: grep de `z-*` en `apps/web/src`:

| z | Elemento | Archivo |
|---|---|---|
| 20 | Lista del selector con búsqueda | `shared/ui/SearchSelect.tsx` |
| 30 | Menú de cuenta | `features/profile/AccountMenu.tsx` |
| 40 | Barra de navegación inferior | `shared/ui/BottomNav.tsx` |
| 50 | Diálogo de confirmación, toast, enlace "Saltar al contenido" | `shared/ui/ConfirmDialog.tsx`, `shared/ui/Toast.tsx`, `app/AppLayout.tsx` |

### 2.5 Breakpoints y anchos de contenido

Solo se usa el breakpoint `sm` de Tailwind (`@media (width >= 40rem)`, 640 px); no hay `md` ni `lg`. El diseño es una columna que se centra.

| Elemento | Móvil | Desde `sm` | Archivo |
|---|---|---|---|
| Contenido de página (`Page`) | `max-w-xl` (36 rem) | igual | `app/AppLayout.tsx` |
| Cabecera | `max-w-xl` | `max-w-2xl` (42 rem) | `app/AppLayout.tsx` |
| Barra de navegación inferior | `max-w-xl` | igual | `shared/ui/BottomNav.tsx` |
| Diálogo y toast | `max-w-md` (28 rem) | igual | `ConfirmDialog.tsx`, `Toast.tsx` |
| Opciones de 4+ elementos | 1 columna | 2 columnas (`sm:grid-cols-2`) | `shared/ui/OptionCards.tsx` |
| Diálogo | pegado abajo (`items-end`) | centrado (`sm:items-center`) | `ConfirmDialog.tsx` |
| Botones de acción de formulario | apilados (`flex-col-reverse`) | en fila (`sm:flex-row`) | pantallas de perfil |

`Page` acepta `wide` (usa `max-w-2xl`), pero **ninguna pantalla lo usa todavía**.

### 2.6 Movimiento

| Animación | Duración y curva | Dónde |
|---|---|---|
| Transición de color (hover, selección) | 150 ms, `cubic-bezier(.4, 0, .2, 1)` (valores por defecto de Tailwind) | `Button`, `OptionCards`, `Switch` |
| Relleno de la barra de progreso | 300 ms, curva por defecto (`duration-300`) | `ProgressBar` en `shared/ui/Feedback.tsx` |
| Indicador del panel "Estamos armando tu plan…" (`animate-runner`) | 1.6 s, `ease-in-out`, infinita | `index.css`, `features/plan/HomePage.tsx` |
| Spinner (`animate-spin`) | 1 s, lineal, infinita | `shared/ui/Spinner.tsx` |
| Esqueleto (`animate-pulse`) | 2 s, `cubic-bezier(.4, 0, .6, 1)`, infinita | `Skeleton` en `shared/ui/Feedback.tsx` |
| Mensajes rotativos al generar el plan | cambia cada 4 s, sin transición | `features/plan/HomePage.tsx` |
| Toast | aparece sin animación, dura 4.5 s | `shared/ui/Toast.tsx` |

**No hay animaciones de entrada ni al hacer scroll**; el movimiento solo responde a una acción o indica carga.

**`prefers-reduced-motion`:** se respeta globalmente con una regla en `@layer base` de `index.css` que deja `animation-duration` y `transition-duration` en `0.01ms` y `animation-iteration-count` en 1. Con esa preferencia el spinner y el indicador del panel dejan de moverse; por eso siempre van acompañados de texto ("Estamos verificando tu correo…", "Estamos armando tu plan…").

---

## 3. Iconografía e ilustraciones

**No hay librería de íconos ni imágenes.** Todo ícono es un SVG escrito a mano dentro del componente, con `currentColor` o con un token (`var(--c-*)`) para heredar el color y el modo oscuro.

| Ícono | Tamaño | Trazo | Archivo |
|---|---|---|---|
| Inicio, Ranking y Perfil (barra inferior) | 24 × 24 | `strokeWidth` 2, extremos y uniones redondeados, sin relleno | `shared/ui/BottomNav.tsx` |
| Reloj de duración del día | 16 × 16 | 2.2, extremos redondeados | `features/plan/WeekLanes.tsx` |
| Spinner | 20 por defecto (18 dentro de un botón) | 3, extremos redondeados | `shared/ui/Spinner.tsx` |
| Marca (`TrackMark`): cuadrado rojo con dos arcos de pista | 28 por defecto | 2.4, blanco sobre `primary` | `shared/ui/Brand.tsx` (y `apps/web/public/favicon.svg`) |
| Glifos de banner (`i`, `✓`, `!`) | círculo de 24 px (`size-6`) con borde de 2 px y letra en negrita | — | `shared/ui/Banner.tsx` |

**Reglas**
- Un ícono decorativo lleva `aria-hidden="true"`; si es el único contenido de un control, el control lleva `aria-label`.
- Para íconos nuevos: SVG de 24 px, `viewBox="0 0 24 24"`, `fill="none"`, `stroke="currentColor"`, `strokeWidth="2"`, `strokeLinecap="round"`, `strokeLinejoin="round"` (mismo formato que `BottomNav`).
- **Ilustraciones:** no se usan. La bienvenida muestra una **muestra de la semana** hecha con los mismos carriles (marcada `aria-hidden`), que sirve de ilustración del producto. Si se agregan ilustraciones, deben respetar la paleta de tokens.

---

## 4. Layout y navegación

### 4.1 Estructura de página

Definida en `apps/web/src/app/AppLayout.tsx`:

```
<AppLayout>                       min-h-dvh
  <AuthBridge/>                   (sin UI: 401/403 y foco al cambiar de ruta)
  <a "Saltar al contenido">       solo visible con el teclado
  <header>                        marca a la izquierda; "Iniciar sesión" si no hay sesión
  <main id="main" tabIndex=-1>    pb-28 con barra inferior, pb-12 sin ella
     <Page>                       mx-auto w-full max-w-xl px-4 py-6
  <BottomNav/>                    solo si hay sesión Y diagnóstico completo
```

- La cabecera usa `Brand` (marca + "FITIA"); el enlace lleva a `/inicio` con sesión completa y a `/` en los demás casos.
- Al cambiar de ruta, `AuthBridge` mueve el foco a `#main` y sube el scroll.
- Todas las pantallas se envuelven en `<Page>` (exportado de `AppLayout.tsx`).

### 4.2 Barra de navegación inferior

`apps/web/src/shared/ui/BottomNav.tsx`. Cuatro destinos: **Inicio** (`/inicio`), **Hoy** (`/hoy`), **Ranking** (`/ranking`) y **Perfil** (`/perfil`). Fija abajo (`z-40`), `max-w-xl` centrada, cuatro columnas iguales (`grid-cols-4`), cada destino `min-h-16` (64 px) con ícono SVG propio de 24 px y etiqueta en `text-xs sm:text-sm font-bold`. Cumple el tamaño objetivo táctil de ≥ 44 px sin desbordamiento a 360 px. Activo: `text-primary-text` y una barra de 4 × 24 px en `primary`; inactivo: `text-muted`. Respeta el área segura de iOS (`pb-[env(safe-area-inset-bottom)]`) y usa un fondo `surface/95` con desenfoque. Lleva `aria-label="Navegación principal"`.

No aparece mientras el usuario no tenga diagnóstico completo (diagnóstico, verificación, login, registro, eliminación de cuenta sin perfil).

### 4.3 Encabezados y márgenes

- Cada pantalla tiene un único `h1` (`text-3xl font-extrabold`).
- Margen lateral: 16 px en móvil; en pantallas anchas la columna se centra (la cabecera es más ancha que el contenido, ver sección 10).
- En el diagnóstico, el encabezado lleva a la derecha el menú `AccountMenu` (cerrar sesión / eliminar cuenta), porque ahí no hay barra inferior. En el perfil, esas acciones están en la sección "Cuenta".

### 4.4 Mapa de rutas y guards

Fuente: `apps/web/src/app/routes.tsx` y `apps/web/src/app/guards.tsx`. Cada pantalla se carga con `lazyPage()` (código dividido por ruta).

| Ruta | Pantalla | HU | Guard |
|---|---|---|---|
| `/` | Bienvenida (`WelcomePage`) | — | Pública |
| `/registro/revisa-tu-correo` | Confirmación de envío y reenvío | 1 | Pública |
| `/verificar-correo?token=…` | Verificación (un solo POST) | 1 | Pública |
| `/ranking` | Ranking público | 7 | Pública (con sesión muestra "Tu posición") |
| `/registro` | Registro | 1 | `PublicOnly` |
| `/iniciar-sesion` | Inicio de sesión | 2 | `PublicOnly` |
| `/diagnostico` | Diagnóstico inicial | 4 | `RequireSession` (S) |
| `/perfil/eliminar-cuenta` | Eliminar cuenta | 3 | `RequireSession` (S) |
| `/inicio` | Plan semanal (carriles enlazados a días) | 5, 12 | `RequireProfile` (S+P) |
| `/hoy` | Rutina de hoy | 10 | `RequireProfile` (S+P) |
| `/plan/dia/:fecha` | Detalle del día (solo lectura) | 12 | `RequireProfile` (S+P) |
| *(parámetro `?ejercicio=<id>`)* | Explicación técnica (hoja inferior) | 13 | Sin cambio de ruta (`BottomSheet`) |
| `/perfil` | Perfil | 6, 7 | `RequireProfile` (S+P) |
| `/perfil/historial` | Historial de peso y estatura | 7 | `RequireProfile` (S+P) |
| `*` | No encontrado (`NotFoundPage`) | — | Pública |

| Guard | Regla |
|---|---|
| `PublicOnly` | Con sesión, redirige a `/diagnostico` (sin diagnóstico) o a la ruta de `?volver=` / `/inicio` (con diagnóstico). |
| `RequireSession` | Sin sesión → `/iniciar-sesion?volver=<ruta>`. |
| `RequireProfile` | Sin sesión → login; sin diagnóstico → `/diagnostico`. |

Mientras `GET /me` carga, los guards muestran esqueletos; si `/me` falla (no por 401), muestran `ErrorState` con "Reintentar". Si el usuario cerró sesión a propósito (cerrar sesión o eliminar cuenta), el guard lleva a la bienvenida y no al login (`sessionEndNotice` en `apps/web/src/shared/session/session.ts`).

---

## 5. Catálogo de componentes

Los componentes base están en `apps/web/src/shared/ui/`. Los que pertenecen a una sola pantalla viven en su `features/`. Todos usan solo tokens.

### Botón

**Archivo:** `apps/web/src/shared/ui/Button.tsx` (`Button`, `ButtonLink`, helper `buttonClass`).

| Variante | Aspecto | Uso |
|---|---|---|
| `primary` | `bg-primary text-on-primary`, hover `primary-strong` | **Una** acción principal por pantalla o bloque ("Crear mi cuenta", "Confirmar y armar mi plan"). |
| `secondary` | Borde de 2 px, `bg-surface text-ink`, hover borde `ink/40` | Acción alternativa o cancelar ("Atrás", "Cancelar", "Editar"). |
| `ghost` | Solo texto `primary-text`, hover `surface-2`, `px-3` | Acción terciaria ("Cambiar", "Reintentar" en línea). |
| `danger` | `bg-danger`; texto `on-primary` (claro) o `bg` (oscuro) | Solo la acción que borra datos de forma definitiva ("Eliminar mi cuenta"). Descartar cambios usa `primary` en el diálogo. |

Tamaño único: `min-h-11` (44 px), `px-5 py-2.5`, `font-bold`, radio de control. No hay variantes de tamaño.

| Estado | Comportamiento |
|---|---|
| Normal / hover | Ver tabla de variantes. |
| Foco | Anillo global de 3 px (sección 8). |
| Deshabilitado | `opacity-55` y `cursor-not-allowed`. |
| Cargando | Reemplaza el ícono por un `Spinner` de 18 px, pone `aria-busy` y, si hay `loadingText`, cambia el texto ("Entrando…"). Queda deshabilitado. |

**Props:** `variant`, `loading`, `loadingText`, `fullWidth`, `icon` y todas las nativas de `<button>`. `type` por defecto es `"button"` (en formularios pásalo `"submit"`). `ButtonLink` es el mismo aspecto sobre `Link` de React Router.

**Cuándo sí:** acciones. Texto = verbo concreto ("Guardar diagnóstico", no "Enviar"). **Cuándo no:** para navegar entre pantallas sin acción de negocio usa `ButtonLink` o un enlace; no pongas dos `primary` juntos.

### Campo de texto y de contraseña

**Archivo:** `apps/web/src/shared/ui/TextField.tsx` (`TextField`, `PasswordField`, `inputClass`).

- Etiqueta visible arriba (`font-bold`), enlazada con `htmlFor`.
- Control: `min-h-12` (48 px), `border-2`, `px-4 py-2.5`, radio de control, fondo `surface`.
- Ayuda (`hint`) y error (`error`) debajo, en `text-sm`; el error va en `text-danger font-bold`. Ambos se enlazan con `aria-describedby`; con error el campo lleva `aria-invalid` y `border-danger`.
- `counter={{ value, max }}` muestra "n/20" a la derecha de la etiqueta (oculto a lectores de pantalla; en rojo si se pasa del máximo).
- `suffix` coloca un elemento dentro del campo a la derecha.
- `PasswordField` añade el botón "Ver" / "Ocultar" (`aria-pressed`, `aria-label` completo) y, si recibe `minLength` y `valueLength`, una ayuda "Mínimo 8 caracteres (n/8)" que pasa a "Longitud suficiente" en `text-success`.

| Estado | Aspecto |
|---|---|
| Normal | Borde `line` |
| Foco | Borde `ink/50` + anillo de foco de 3 px |
| Error | Borde `danger`, mensaje debajo, `aria-invalid` |

**Cuándo sí:** cualquier entrada de texto con etiqueta. **Cuándo no:** para elegir entre opciones cerradas usa `OptionCards`, `DayChips` o `SearchSelect`; nunca un campo libre (regla del diagnóstico).

### Selector con búsqueda

**Archivo:** `apps/web/src/shared/ui/SearchSelect.tsx`.

Combobox accesible (patrón ARIA 1.2: `role="combobox"`, `listbox`, `aria-activedescendant`). Filtra mientras se escribe, **sin tildes ni mayúsculas**. Teclado: flechas, `Enter` elige, `Escape` cierra. La lista mide como máximo `max-h-64` con desplazamiento, ítems de `min-h-11`; el activo lleva `bg-surface-2` y el elegido `font-bold text-primary-text`. Sin resultados dice "Sin resultados".

**Props:** `label`, `items: {value, label}[]`, `value`, `onChange(value | null)`, `placeholder`, `error`, `hint`, `loading` (muestra "Cargando programas…" y deshabilita), `disabled`, `emptyText`.

**Cuándo sí:** listas largas y cerradas (programas académicos). **Cuándo no:** para menos de ~6 opciones usa `OptionCards`.

### Tarjeta de opción

**Archivo:** `apps/web/src/shared/ui/OptionCards.tsx` (`OptionCards`, `sameCode`).

Grupo de selección única (`role="radiogroup"`; cada tarjeta es un botón `role="radio"`). Tarjeta de `min-h-14` (56 px), `border-2`, con un punto de radio a la izquierda y la etiqueta en `font-bold`. Seleccionada: `border-primary bg-primary/8` y punto relleno. Navegación con flechas (foco itinerante: solo la tarjeta activa está en el orden de tabulación). `columns={2}` usa dos columnas desde `sm`.

**Props:** `legend`, `hideLegend`, `options: {code, label}[]`, `value`, `onChange(code)`, `error`, `columns`.

**Regla clave:** los `code` se comparan y se emiten **con su tipo JSON original** (`sameCode` distingue `4` de `"4"` y `true` de `"true"`). No conviertas los códigos.

### Chips de días

**Archivo:** `apps/web/src/shared/ui/DayChips.tsx`.

Selección múltiple (`fieldset` con `legend`; cada chip es un botón `role="checkbox"` con el nombre completo del día en `aria-label`). Cinco columnas, cada chip `min-h-16` (64 px), la inicial grande (L M X J V) y la abreviatura de tres letras debajo. Seleccionado: `border-primary bg-primary text-on-primary`.

**Props:** `legend`, `hideLegend`, `options`, `value: number[]`, `onChange(days)`, `error`. Emite los días ordenados.

### Interruptor

**Archivo:** `apps/web/src/shared/ui/Switch.tsx`.

`role="switch"` con `aria-checked`, etiqueta y descripción asociadas. Pista de 56 × 32 px (`w-14 h-8`) con perilla de 24 px. Encendido: `border-rest bg-rest`; apagado: `border-line bg-surface-2`. Incluye texto `sr-only` "Activado" / "Desactivado". Deshabilitado: `opacity-55`.

**Props:** `label`, `description`, `checked`, `onChange(boolean)`, `disabled`.

**Cuándo sí:** una preferencia que se guarda al instante (privacidad en el ranking). **Cuándo no:** dentro de un formulario con botón "Guardar" usa un campo o casilla.

### Banner

**Archivo:** `apps/web/src/shared/ui/Banner.tsx`.

Aviso en línea con glifo, título opcional, cuerpo y acciones.

| `tone` | Fondo / borde | Glifo | Usar para |
|---|---|---|---|
| `info` | `info-soft` / `info/40` | `i` | Información neutra (plan desactualizado, "tu plan actual no cambia"). |
| `success` | `success-soft` / `success/40` | `✓` | Confirmaciones persistentes (diagnóstico actualizado, correo verificado). |
| `warn` | `warn-soft` / `warn/40` | `!` | Algo no salió del todo bien pero hay un camino (correo ya registrado, plan vigente con fallo de actualización). |
| `danger` | `danger-soft` / `danger/40` | `!` | Error que impide continuar. |

**Props:** `tone`, `title`, `children`, `actions`, `live`, `className`. `live="polite"` (por defecto) agrega `role="status"`; `"assertive"` agrega `role="alert"`; `"off"` no agrega rol (úsalo cuando el banner está dentro de una región `aria-live` que ya lo anuncia).

**Cuándo sí:** mensajes ligados al contenido de la pantalla. **Cuándo no:** confirmaciones momentáneas de una acción (usa `Toast`); errores de un campo concreto (van bajo el campo).

### Toast

**Archivo:** `apps/web/src/shared/ui/Toast.tsx` (`ToastProvider`, `useToast`).

Confirmación breve y no bloqueante. Se usa así: `const toast = useToast(); toast("Texto", "success" | "danger" | "info")`. Aparece centrado, 96 px sobre el borde inferior (por encima de la barra de navegación), `max-w-md`, `shadow-raised`, y desaparece a los **4.5 s**. Contenedor con `aria-live="polite"`. Tonos: `success` = `bg-rest`, `danger` = `bg-danger`, `info` = `bg-ink`; el texto es `on-primary` en claro y `bg` en oscuro (para mantener el contraste).

**Cuándo sí:** resultado de una acción que ya se ve reflejada en pantalla (cambiar la privacidad, error al cerrar sesión). **Cuándo no:** información que el usuario necesita releer (usa `Banner`).

### Diálogo de confirmación

**Archivo:** `apps/web/src/shared/ui/ConfirmDialog.tsx`.

Modal (`role="dialog"`, `aria-modal`, `aria-labelledby`). En móvil se pega abajo; desde `sm` se centra. Telón `bg-ink/50`. El foco inicial va a **"Cancelar"**, `Escape` cancela, `Tab` y `Shift+Tab` se mantienen dentro de los botones del diálogo y, al cerrar, el foco vuelve al elemento que lo abrió.

**Props:** `open`, `title`, `children`, `confirmLabel`, `cancelLabel` (por defecto "Cancelar"), `tone` (`primary` | `danger`), `onConfirm`, `onCancel`.

**Cuándo sí:** descartar cambios sin guardar. **Cuándo no:** acciones muy destructivas e irreversibles: usa una pantalla propia con casilla de confirmación (ver `DeleteAccountPage`).

### Barra de progreso, esqueleto, estados vacío y de error, tarjeta

**Archivo:** `apps/web/src/shared/ui/Feedback.tsx`.

| Componente | Descripción | Props |
|---|---|---|
| `ProgressBar` | Pista `h-2.5 rounded-full bg-surface-2`, relleno `bg-primary` con transición de 300 ms; `role="progressbar"` con `aria-valuenow/max`. Texto de apoyo arriba ("Pregunta 2 de 6"). | `value`, `max`, `label` |
| `Skeleton` | Bloque `animate-pulse bg-surface-2`, decorativo. | `className` |
| `PageSkeleton` | Título y bloques de esqueleto con un texto accesible de carga (`role="status"`). | `label`, `rows` |
| `EmptyState` | Recuadro de borde punteado, centrado, con título (`font-display text-lg`), explicación y una acción opcional. | `title`, `children`, `action`, `icon` |
| `ErrorState` | `Banner` `danger` asertivo con el título fijo "No pudimos cargar esta información" y botón "Reintentar". | `message`, `onRetry` |
| `Card` | `section` con `border border-line bg-surface`, radio de tarjeta y `p-5 sm:p-6`. | `as` (`section` | `div` | `article`), `className`, `aria-labelledby`, `id` |

### Spinner y marca

- `Spinner` (`shared/ui/Spinner.tsx`): `size` (20 por defecto) y `label` opcional (si existe, `role="status"` con el texto `sr-only`). Hereda el color del texto.
- `Brand` y `TrackMark` (`shared/ui/Brand.tsx`): marca de la cabecera.

### Barra de navegación inferior

Ver sección 4.2 (`shared/ui/BottomNav.tsx`).

### Componentes de pantalla (no genéricos)

| Componente | Archivo | Descripción y reglas |
|---|---|---|
| **Tarjeta de día del plan** (`WeekLanes`) | `features/plan/WeekLanes.tsx` | Lista `ol` de cinco carriles. Cada uno es un `article` con `aria-label` ("lunes 12 de octubre, hoy"). Carril lateral de 64 px con inicial (`text-3xl`) y fecha corta (`text-xs`; "Hoy" para el día actual). Altura mínima 80 px; el título ocupa hasta 2 líneas. Colores por estado en la sección 2.1. **Todavía no es navegable**: queda preparada para enlazar al detalle (HU 10). |
| **Ítem del ranking** | `features/ranking/RankingPage.tsx` (`RankingList`) | Podio de tres columnas (el primero en `bg-primary` con franjas, `min-h-40`; segundo y tercero en `surface-2`) y lista del resto con posición, apodo, "Nivel n" y puntos (`tabular-nums`). El usuario propio se resalta con `ring-3 ring-focus` en el podio o `bg-info-soft` y `aria-current` en la lista. Nunca muestra el correo. |
| **Panel de generación** (`GeneratingPanel`) | `features/plan/HomePage.tsx` | Título, indicador de carrera (`animate-runner`), mensaje rotativo cada 4 s (`aria-hidden`) y, a los 60 s, "Seguir esperando" / "Reintentar". El anuncio para lectores de pantalla es un `role="status"` aparte. |
| **Pregunta del diagnóstico** (`QuestionField`) | `features/onboarding/QuestionField.tsx` | Elige `DayChips` (tipo `multi`) u `OptionCards` (tipo `single`) según el cuestionario de la API. También exporta `isAnswered` y `answerLabel`. |
| **Menú de cuenta** (`AccountMenu`) | `features/profile/AccountMenu.tsx` | Botón "Cuenta" con menú de "Cerrar sesión" y "Eliminar mi cuenta". Solo en pantallas sin barra inferior (diagnóstico). |
| **Reenvío de verificación** (`ResendVerification`) | `features/auth/ResendVerification.tsx` | Botón con enfriamiento de 60 s y mensaje neutro; pide el correo si no se conoce. |
| **Secciones del perfil** | `features/profile/ProfileDiagnosticView.tsx`, `PhysicalSection.tsx`, `PrivacySection.tsx` | Cada una guarda por separado (ver sección 6). |
| **Hoja inferior** (`BottomSheet`) | `shared/ui/BottomSheet.tsx` | Diálogo modal accesible (`role="dialog"`, `aria-modal="true"`). Atrapa foco de teclado, cierra con `Escape`, botón de cierre (≥ 44 px) o clic en telón. Restaura foco al elemento disparador. Usado en `ExerciseGuideSheet`. |
| **Lista de ejercicios** (`ExerciseList`) | `features/plan/ExerciseList.tsx` | Lista ordenada solo lectura (`<ol>`); cada ítem es un botón táctil (≥ 44 px) con nombre, prescripción accesible e indicador "Ver técnica". |
| **Rutina del día** (`DayRoutine`) | `features/plan/DayRoutine.tsx` | Sección de rutina con título, duración estimada, lista de ejercicios o estado de descanso. Compartido por `/hoy` y `/plan/dia/:fecha`. |

---

## 6. Patrones de interacción

### 6.1 Formularios

| Aspecto | Regla | Dónde se ve |
|---|---|---|
| Validación en cliente | Refleja las reglas del backend con Zod + React Hook Form (`mode: "onTouched"`). El backend es la fuente de verdad. | `features/auth/RegisterPage.tsx`, `LoginPage.tsx` |
| Errores del backend | Se muestran **todos a la vez**, cada uno bajo su campo (`setError`), con el texto propio de `fieldMessage(field, code)`. | `shared/lib/fieldErrors.ts` |
| Mensaje general | Un `Banner` arriba para lo que no es de un campo (correo ya registrado, límite de intentos, error genérico). | `RegisterPage.tsx` |
| Botón de envío | `Button` con `loading` y `loadingText` ("Creando tu cuenta…", "Entrando…"); queda deshabilitado mientras envía. | todas |
| Datos que el backend normaliza | No se bloquean: correo con espacios o mayúsculas se recorta y baja a minúsculas en cliente. | `RegisterPage.tsx` |
| Tipos | Booleanos como booleano (`accepted_terms`), números como número, códigos con su tipo original. | `RegisterPage.tsx`, `DiagnosticPage.tsx` |
| Edición de perfil | Se envían **solo los campos que cambiaron** (`diffProfile`); sin cambios no hay petición; nunca se envían `points`, `level`, `ranking_position` ni `physical_updated_at`. | `features/profile/changes.ts` |
| Guardado | Todo o nada: si falla, el formulario conserva lo escrito y los valores guardados no cambian. | `ProfileDiagnosticView.tsx`, `PhysicalSection.tsx` |
| Guardado inmediato | El interruptor de privacidad guarda al tocar, con actualización optimista, `Toast` y reversión si falla. | `features/profile/PrivacySection.tsx` |

### 6.2 Estados de pantalla

Toda pantalla con datos remotos cubre los cuatro estados.

| Estado | Componente |
|---|---|
| Cargando | `PageSkeleton` (con `role="status"` y texto de carga) o `Skeleton` en bloques pequeños |
| Vacío | `EmptyState` (título + qué hacer; ej. "Aún no tienes registros", "El ranking está por arrancar") |
| Error | `ErrorState` con "Reintentar" que vuelve a pedir la consulta |
| Éxito | `Banner tone="success"` o `Toast`, según persistencia |

### 6.3 Confirmaciones destructivas y descarte de cambios

- **Eliminar cuenta** (`features/profile/DeleteAccountPage.tsx`): pantalla propia, no un diálogo. Explica que es definitivo, qué se borra (perfil, diagnóstico, plan, historial físico, puntos), que cierra todas las sesiones y que se puede volver a registrar con el mismo correo. Exige marcar la casilla "Entiendo que es definitivo." para habilitar el botón `danger`. **"Cancelar" no envía ninguna petición.** Envía `{ confirm: true }`. Un 401 se trata como éxito (la sesión ya no existía). Tras terminar lleva a la bienvenida con un aviso de despedida.
- **Cerrar sesión** (`features/auth/useLogout.ts`): un 401 significa "ya estaba cerrada" y se continúa igual; limpia el estado y lleva a la bienvenida con el aviso "Cerraste sesión."
- **Descartar cambios sin guardar** (`ProfilePage.tsx`, `ProfileDiagnosticView.tsx`, `PhysicalSection.tsx`): "Cancelar" con cambios abre `ConfirmDialog` "¿Descartar los cambios?" (botones "Descartar cambios" / "Seguir editando"). Salir de la página con cambios pendientes usa `useBlocker` de React Router con el mismo diálogo ("Salir sin guardar" / "Seguir editando") y `beforeunload` para cerrar la pestaña. Al descartar se muestran los valores guardados.

### 6.4 Sondeo del plan

Fuente: `apps/web/src/features/plan/HomePage.tsx` y `usePlanGeneration.ts`.

| Regla | Valor |
|---|---|
| Intervalo de consulta de `GET /plan/current` y `GET /plan/today` | 3 s (`POLL_INTERVAL_MS`), **solo** mientras `status` es `generating` o `regenerating` es `true`; con el plan listo se detiene. No bloquea el resto de la app. |
| Aviso de espera larga | A los 60 s (`SLOW_GENERATION_MS`): "Está tardando más de lo normal." con "Seguir esperando" (reinicia la cuenta) y "Reintentar". |
| `none` (Decisión 8) | Se genera automáticamente **solo** si el usuario llega directamente tras completar el diagnóstico (`location.state.fromDiagnostic`). En cualquier otro caso (`none` en semana nueva), muestra `EmptyState` con el botón "Generar mi plan". |
| `failed` | **Nunca** se reintenta solo: aviso con el motivo y botón "Reintentar". |

| Situación | Presentación |
|---|---|
| `generating` | Panel "Estamos armando tu plan…" con indicador y mensajes rotativos. |
| `ready` + `regenerating` | Plan vigente + banner `info` "Estamos actualizando tu plan…" (con "Seguir esperando" / "Reintentar" tras 60 s). |
| `failed` | Banner `danger` con el motivo y "Reintentar". |
| `ready` + `failure` | Banner `warn` "No pudimos actualizar tu plan." + "Tu plan anterior sigue vigente." |
| `ready` + `outdated` | Banner `info` "Cambiaste tu diagnóstico. ¿Quieres actualizar tu plan?"; el botón "Actualizar mi plan" solo aparece si `can_regenerate`. Si no, explica que el lunes podrá generar uno nuevo. |
| Plan sin días | `EmptyState` "No quedan días de entrenamiento esta semana". |
| Fin de semana | Título "Tu plan para la semana del 19 de octubre". |

Respuestas del `POST`: `409 PLAN_UP_TO_DATE` recarga el plan sin mostrar mensaje; `429 REGENERATION_LIMIT` dice cuándo podrá generar uno nuevo; `429 RATE_LIMITED` indica cuánto esperar. **No se escribe el número de generaciones semanales en ningún texto**; se usa `can_regenerate` y la respuesta 429.

### 6.5 `Retry-After`, 401 y 403

**Cliente HTTP único** (`apps/web/src/shared/api/client.ts`): `credentials: "include"` siempre; `X-Requested-With: fitia` en toda mutación; el formato uniforme de error se convierte en `ApiError { status, code, message, fields, retryAfter }`; una caída de red se convierte en `NETWORK_ERROR`.

| Situación | Comportamiento |
|---|---|
| `Retry-After` (segundos) en un 429 | `describeWait()` lo convierte: "en 45 segundos", "en 12 minutos", "en 2 horas", "en 2 días"; `describeWaitUntilDay()` da el día ("el lunes 19 de octubre") para el límite semanal (`shared/lib/retryAfter.ts`). |
| Login con 429 | Mensaje con la espera y botón deshabilitado con cuenta regresiva ("Espera 720 s"). |
| Reenvío con 429 | El enfriamiento pasa a la espera indicada. |
| 401 `UNAUTHENTICATED` en una ruta protegida | `AuthBridge` limpia la sesión y lleva a `/iniciar-sesion?volver=<ruta>`. |
| 403 `ONBOARDING_REQUIRED` | Marca el diagnóstico como pendiente y lleva a `/diagnostico`. |
| Excepción `silentAuth: true` | No dispara esas redirecciones: `/me` (un 401 significa "visitante"), login, verificación, logout, eliminar cuenta y las consultas opcionales con sesión (ranking). Úsala solo en esos casos. |
| Ruta de retorno | `safeReturnPath` solo acepta rutas internas (`/…`, no `//…`). |
| 500 | Mensaje del backend o, si la respuesta no trae el formato, "Algo salió mal. Intenta de nuevo en unos segundos." |

---

## 7. Contenido y tono

### 7.1 Voz

- **Español de Colombia, tuteo** ("Crea tu cuenta", "Tu semana"). Cercano y motivador, sin jerga médica ni promesas de resultados físicos.
- **Oraciones cortas** y en voz activa; mayúscula solo al inicio (estilo oración), sin signos de exclamación salvo el éxito de la verificación.
- **Los botones dicen qué hacen**: "Guardar diagnóstico", "Confirmar y armar mi plan", "Eliminar mi cuenta". Una acción conserva su nombre en todo el flujo.
- **Errores y vacíos orientan**: dicen qué pasó y qué hacer; no se disculpan ni son vagos.
- **Gamificación neutral:** "Completa entrenamientos para sumar puntos y subir de nivel."; el ranking dice "Constancia que se nota. Cada entrenamiento suma."
- **Privacidad visible:** el correo nunca aparece en el ranking ni en el perfil; la privacidad tiene su propia sección.

### 7.2 Fechas, números y etiquetas

Fuente: `apps/web/src/shared/lib/dates.ts`.

| Elemento | Formato |
|---|---|
| Zona horaria | `America/Bogota`; las fechas ISO del plan (`2026-10-12`) se interpretan al mediodía de Bogotá para evitar saltos de día. |
| Día completo | "lunes 12 de octubre" (`formatDayLong`) |
| Día y mes | "12 de octubre" (`formatDayMonth`) |
| Fecha con año (de un timestamp) | "12 de octubre de 2026" (`formatDateFromTimestamp`) |
| Fecha corta (gráfica) | "12 oct" (`formatShortFromTimestamp`) |
| "Hoy" | `todayInBogota()` (no la fecha del dispositivo) |
| Nombres de día | `WEEKDAY_NAMES`: lunes … domingo (minúscula). Las etiquetas de las opciones ("Lunes", "Miércoles") vienen del cuestionario de la API. |
| Abreviaturas | `WEEKDAY_SHORT`: 1 = L, 2 = M, 3 = X, 4 = J, 5 = V |
| Unidades | "30 min", "68,5 kg", "172 cm", "120 pts", "Nivel 3". El peso admite coma decimal al escribir. |
| Cifras que se comparan | `tabular-nums` (puntos del ranking, contadores) |

### 7.3 Mensajes por código del backend

Los textos de campo salen de `apps/web/src/shared/lib/fieldErrors.ts`; el resto, de cada pantalla. "Backend" significa que se muestra `error.message` tal como llega.

**Errores de campo (`VALIDATION_ERROR`, 422)**

| Campo : código | Texto en la interfaz |
|---|---|
| `nickname` : `NICKNAME_LENGTH` | Tu apodo debe tener entre 3 y 20 caracteres. |
| `program_code` : `PROGRAM_REQUIRED` | Elige tu programa académico. |
| `accepted_terms` : `TERMS_REQUIRED` | Debes aceptar el tratamiento de datos para continuar. |
| `password` : `WEAK_PASSWORD` | La contraseña debe tener al menos 8 caracteres. |
| `password` : `PASSWORD_TOO_LONG` | La contraseña no puede tener más de 128 caracteres. |
| `password` : `REQUIRED` | Escribe tu contraseña. |
| `email` : `INVALID_EMAIL` | Revisa el formato de tu correo. |
| `weight_kg` : `INVALID_OPTION` | El peso debe estar entre 20 y 400 kg. |
| `height_cm` : `INVALID_OPTION` | La estatura debe estar entre 50 y 270 cm. |
| `training_days` : `DAYS_REQUIRED` | Elige al menos un día para entrenar, de lunes a viernes. |
| `has_machine_access` : `MACHINE_ACCESS_REQUIRED` | Indica si tienes acceso a máquinas. |
| cualquiera : `REQUIRED` / `INVALID_OPTION` / `INVALID` | Responde esta pregunta. / Elige una de las opciones disponibles. / Revisa este dato. |

**Códigos de negocio**

| Código (HTTP) | Dónde | Texto en la interfaz |
|---|---|---|
| `DOMAIN_NOT_ALLOWED` (422) | Registro, campo correo | Backend: "Solo se admiten correos @correounivalle.edu.co" |
| `EMAIL_EXISTS` (409) | Registro | Banner `warn` "Este correo ya tiene cuenta." + "Si es tuyo, inicia sesión. Si aún no lo verificas, puedes pedir un enlace nuevo desde el inicio de sesión." + enlace "Iniciar sesión"; también marca el campo |
| `RATE_LIMITED` (429) | Registro y reenvío | Hiciste varios intentos seguidos. Intenta de nuevo {espera}. |
| `RATE_LIMITED` (429) | Login | Demasiados intentos. Intenta de nuevo {espera}. (botón "Espera n s") |
| `RATE_LIMITED` (429) | Generar plan | Hiciste varios intentos seguidos. Intenta de nuevo {espera}. |
| `INVALID_CREDENTIALS` (401) | Login | El correo o la contraseña no son correctos. (sin marcar campos) |
| `ACCOUNT_NOT_FOUND` (404) | Login | Backend: "Este correo no está registrado en FITIA. Crea una cuenta para empezar." + botón "Crear cuenta" (correo precargado) |
| `EMAIL_NOT_VERIFIED` (403) | Login | Backend: "Debes verificar tu correo antes de iniciar sesión…" + botón "Reenviar enlace de verificación" |
| `TOKEN_EXPIRED_OR_USED` (410) | Verificación | "Este enlace venció o ya se usó." + mensaje del backend + reenvío (o "Ir a FITIA" si ya hay sesión) |
| (sin token en la URL) | Verificación | "Este enlace no es válido." / "Abre el enlace completo que te enviamos por correo, o pide uno nuevo." |
| Otro error al verificar | Verificación | "No pudimos verificar tu correo." + mensaje + "Reintentar" |
| `PROFILE_EXISTS` (409) | Diagnóstico | Sin mensaje: se va a `/inicio` |
| `PLAN_UP_TO_DATE` (409) | Plan | Sin mensaje: se recarga el plan |
| `REGENERATION_LIMIT` (429) | Plan | Ya usaste tus actualizaciones de esta semana; podrás generar uno nuevo {el lunes 19 de octubre}. |
| `GENERATION_TIMEOUT` | Plan fallido | La generación tardó más de lo esperado. |
| `AI_UNAVAILABLE` | Plan fallido | El servicio de planes no está disponible ahora. |
| `AI_INVALID_OUTPUT` | Plan fallido | No pudimos armar un plan válido. |
| `STALE` | Plan fallido | La generación se interrumpió. |
| `UNAUTHENTICATED` (401) | Rutas protegidas | Sin mensaje: redirección al login |
| `ONBOARDING_REQUIRED` (403) | Rutas S+P | Sin mensaje: redirección al diagnóstico |
| `CONFIRMATION_REQUIRED` (400) | Eliminar cuenta | No tiene tratamiento propio: sale el mensaje del backend en un banner (la interfaz no debería provocarlo) |
| `CSRF_HEADER_MISSING`, `NOT_EDITABLE`, `EMPTY_UPDATE` | — | Sin tratamiento propio: no deben ocurrir con este cliente |
| `NETWORK_ERROR` | Cualquiera | No pudimos conectarnos. Revisa tu conexión e intenta de nuevo. |
| Respuesta sin formato / 500 | Cualquiera | Algo salió mal. Intenta de nuevo en unos segundos. |

**Mensajes de éxito y avisos**

| Situación | Texto |
|---|---|
| Correo verificado | ¡Listo, {apodo}! Tu correo quedó verificado. + "Ahora cuéntanos un poco de ti para armar tu plan. Te llevamos en un momento." |
| Reenvío de verificación (siempre igual) | Si hay una cuenta pendiente con ese correo, te enviamos un enlace nuevo. |
| Diagnóstico guardado en el perfil | Mensaje de la API: "Tu diagnóstico se actualizó correctamente. Los cambios se aplicarán al próximo plan que generes. Tu plan actual no ha cambiado." + botón "Ir a mi plan" |
| Datos físicos guardados | Tus datos físicos se guardaron. (la pantalla no usa el mensaje de la API, que habla del diagnóstico) |
| Privacidad | Ahora apareces en el ranking público. / Ya no apareces en el ranking público. (toast) · Error: No pudimos cambiar tu privacidad. Intenta de nuevo. |
| Cerrar sesión | Cerraste sesión. (en la bienvenida) |
| Cuenta eliminada | Tu cuenta y tus datos se eliminaron. Gracias por entrenar con FITIA; si vuelves, puedes registrarte con el mismo correo. |
| Cuenta eliminada: texto de la pantalla | Esta acción es definitiva y no se puede deshacer. |
| Error al cargar datos | No pudimos cargar esta información (+ mensaje + "Reintentar") |

---

## 8. Accesibilidad

| Práctica | Cómo se cumple | Dónde |
|---|---|---|
| **Foco visible** | `:focus-visible` global con contorno de 3 px `focus` y desplazamiento de 2 px; los campos suman `focus-visible:outline-3`. | `index.css` (`@layer base`), `TextField.tsx` |
| **Tamaño táctil** | Botones, enlaces de acción e ítems del menú de cuenta: `min-h-11` (44 px); campos 48 px; tarjetas de opción 56 px; chips de día 64 px; destinos de navegación 64 px; casillas con la etiqueta clicable de 44 px. (Excepciones en la sección 10.) | `Button.tsx`, `TextField.tsx`, `OptionCards.tsx`, `DayChips.tsx`, `BottomNav.tsx` |
| **Etiquetas** | Todo campo tiene `<label>` asociado; los grupos usan `legend` o `aria-labelledby`; los controles solo con ícono llevan `aria-label`. | `TextField.tsx`, `OptionCards.tsx`, `DayChips.tsx` |
| **Errores anunciados** | Errores de campo enlazados con `aria-describedby` y `aria-invalid`; banners con `role="alert"` (asertivo) o `role="status"`; regiones `aria-live` para los mensajes de formulario y el toast. | `TextField.tsx`, `Banner.tsx`, `Toast.tsx`, `RegisterPage.tsx`, `LoginPage.tsx` |
| **Teclado** | Radios con flechas y foco itinerante; chips y botones con `Enter`/`Espacio`; selector con búsqueda con flechas, `Enter` y `Escape`; diálogo con foco atrapado y `Escape`; enlace "Saltar al contenido". | `OptionCards.tsx`, `SearchSelect.tsx`, `ConfirmDialog.tsx`, `AppLayout.tsx` |
| **Foco al navegar** | Al cambiar de ruta el foco va a `<main id="main" tabIndex={-1}>`. | `app/AuthBridge.tsx` |
| **El color no es el único canal** | Los estados llevan también texto, borde (punteado/continuo), glifo o etiqueta ("Hoy", "Descanso", "Sin plan"); los errores llevan texto bajo el campo; el interruptor tiene texto `sr-only` de su estado. | `WeekLanes.tsx`, `Banner.tsx`, `Switch.tsx` |
| **Lector de pantalla** | Estado de carga como texto `sr-only` (`PageSkeleton`, `Spinner` con `label`); progreso con `role="progressbar"`; lista de la semana con `aria-label` por día; íconos decorativos con `aria-hidden`. | `Feedback.tsx`, `Spinner.tsx`, `WeekLanes.tsx` |
| **Idioma** | `<html lang="es-CO">`. | `apps/web/index.html` |
| **Movimiento** | Se respeta `prefers-reduced-motion` (sección 2.6). | `index.css` |
| **Responsive** | Sin desplazamiento horizontal a 360 px; `viewport-fit=cover` y áreas seguras de iOS. | `index.html`, `BottomNav.tsx` |

**Verificación hecha durante el desarrollo** (no está automatizada en el repositorio): un recorrido real de 23 pantallas con Playwright y axe-core (reglas WCAG 2 A/AA y 2.1 AA) en modo claro y oscuro a 390 px, y en modo claro a 360 px, sin violaciones y sin desbordamiento horizontal. Axe no mide el contraste de bordes ni el tamaño táctil: esos puntos se revisaron aparte y dieron las deficiencias de la sección 10.

---

## 9. Convenciones de código

### 9.1 Estructura de carpetas

Descrita también en `apps/web/src/README.md`.

```
apps/web/src/
├── app/            rutas (routes.tsx), guards, AppLayout, AuthBridge
├── features/       una carpeta por funcionalidad, con sus pantallas y su api.ts
│   ├── auth/  onboarding/  plan/  profile/  ranking/  welcome/
├── shared/
│   ├── api/        client.ts (cliente único), types.ts (contratos), queryClient.ts
│   ├── session/    session.ts (GET /me como fuente de verdad de la sesión)
│   ├── ui/         componentes base reutilizables
│   └── lib/        cx, dates, retryAfter, fieldErrors
├── styles/         index.css (tokens + Tailwind)
└── test/           MSW, fixtures y pruebas de flujo (test/flows/)
```

### 9.2 Nombres

| Elemento | Convención | Ejemplo |
|---|---|---|
| Componente | `PascalCase`, un componente por archivo con el mismo nombre | `WeekLanes.tsx` |
| Pantalla | Sufijo `Page` | `ProfilePage.tsx` |
| Cliente de una funcionalidad | `features/<x>/api.ts` exporta un objeto `xApi` y las llaves de caché `xKey` | `planApi`, `planKey` |
| Hook | `useAlgo` | `useLogout`, `useMe`, `useToast` |
| Constantes de tiempo | `MAYÚSCULAS_CON_UNIDAD` | `POLL_INTERVAL_MS` |
| Tipos del contrato | `shared/api/types.ts` (o `features/<x>/types.ts`, solo tipos) | `CurrentPlan` |
| Pruebas | `*.test.ts(x)` junto al módulo (utilidades) o en `src/test/flows/` (flujos) | `plan.test.tsx` |
| Textos | En español, en el mismo archivo de la pantalla; los de campo, en `fieldErrors.ts` | — |

### 9.3 Cómo se consumen los tokens

1. **Solo utilidades de token**: `bg-surface`, `text-muted`, `border-line`, `bg-primary`, `text-on-primary`… Nunca un hex ni un color de Tailwind (`bg-red-600`).
2. **Radios** con las variables: `rounded-[var(--radius-control)]` (controles) y `rounded-[var(--radius-card)]` (tarjetas).
3. **SVG**: `currentColor` o `var(--c-*)`.
4. **Un token nuevo** se agrega en tres sitios de `index.css`: `:root` (claro), el bloque oscuro y `@theme inline`. Calcula su contraste y regístralo en la sección 2.2 de esta guía.
5. **Modo oscuro**: los tokens se invierten solos. Solo si una combinación no cumple contraste en un modo se usa la variante `dark:` (que sigue el sistema), como en `Button` (`dark:text-bg`) y `Toast`.
6. **Unir clases** con `cx()`; no concatenes cadenas a mano.

### 9.4 Cliente HTTP

- Nunca llames a `fetch` fuera de `shared/api/client.ts`; usa `api.get / post / patch` desde el `api.ts` de la funcionalidad.
- No leas ni guardes la cookie de sesión ni uses `localStorage`/`sessionStorage`. La sesión es lo que devuelve `GET /me` (`useMe()`).
- Decide por consulta si lleva `silentAuth` (ver sección 6.5).
- Los datos del usuario se cachean con TanStack Query y se borran al cerrar sesión (`USER_DATA_KEYS` en `session.ts`). Si agregas una llave de datos del usuario, agrégala ahí.
- Reintentos: solo se reintenta una caída de red; un error de la API es definitivo.

### 9.5 Cómo agregar una pantalla nueva

1. **Contrato:** agrega los tipos de la respuesta en `shared/api/types.ts` o en `features/<x>/types.ts`.
2. **API:** crea `features/<x>/api.ts` con `xApi` y `xKey`. Si es una mutación, el cliente ya añade `X-Requested-With`.
3. **Pantalla:** crea `features/<x>/AlgoPage.tsx` y envuélvela en `<Page>`. Un `h1` (`text-3xl font-extrabold`) y las secciones en `Card` con `h2` (`text-xl font-bold`).
4. **Estados:** cubre cargando (`PageSkeleton`), vacío (`EmptyState`), error (`ErrorState` con "Reintentar") y éxito.
5. **Formularios:** React Hook Form + Zod, errores del backend bajo cada campo con `fieldMessage` (agrega ahí los textos nuevos), botón con `loading`. Envía solo lo necesario y con los tipos correctos.
6. **Ruta:** regístrala en `app/routes.tsx` con `lazyPage()` bajo el guard que corresponda (`PublicOnly`, `RequireSession` o `RequireProfile`).
7. **Textos:** tuteo, verbos concretos, sin número de límites; si hay `Retry-After`, usa `describeWait`.
8. **Componentes:** si falta uno, créalo en `shared/ui/` con tokens, estados de foco y deshabilitado, y documéntalo en la sección 5.
9. **Pruebas:** un flujo en `src/test/flows/` con `renderRoute()` y MSW; verifica los cuerpos y encabezados enviados, el camino de error y el estado vacío.
10. **Revisión:** foco visible, objetivos de 44 px, `aria-live` en mensajes dinámicos, contraste de cualquier color nuevo y 360 px sin desplazamiento horizontal.

---

## 10. Pendientes y deficiencias conocidas

### Deficiencias de accesibilidad (existen hoy en el código)

| Deficiencia | Detalle | Dónde |
|---|---|---|
| Borde de campos y tarjetas de opción con contraste insuficiente | `border-line` mide 1.33–1.43:1 en claro y 1.51–1.70:1 en oscuro; WCAG 1.4.11 pide 3:1 para el límite de un control. El texto y el contenido sí son legibles; el borde de la zona tocable es tenue. | `shared/ui/TextField.tsx` (`inputClass`), `OptionCards.tsx`, `DayChips.tsx` |
| Texto de ejemplo (`placeholder`) de bajo contraste | `muted` al 70 % da 3.26:1 en claro y 4.30:1 en oscuro. Hoy solo se usa para el ejemplo de correo. | `shared/ui/TextField.tsx` |
| Hover del botón primario en modo oscuro | Blanco sobre `#EF3A56` da 3.88:1, bajo 4.5:1 para texto de 17 px. | `shared/ui/Button.tsx` + `index.css` (`--c-primary-strong` oscuro) |
| Texto pequeño sobre las franjas de pista en modo oscuro | Blanco sobre la franja da 4.08:1 (la etiqueta "Hoy" y la fecha del carril de hoy, y el pie del primer lugar del podio). | `features/plan/WeekLanes.tsx`, `features/ranking/RankingPage.tsx`, utilidad `lane-stripes` |
| Interruptor apagado poco visible | La pista (`surface-2`) y el borde (`line`) tienen contraste bajo contra el fondo; el estado se transmite además por la posición de la perilla y por texto `sr-only`. | `shared/ui/Switch.tsx` |
| Objetivos táctiles menores de 44 px | Resuelto: El interruptor expande su zona táctil a ≥ 44 px con pseudo-elemento (`before:-inset-2`); el botón "Ver/Ocultar" mide 44 px (`min-h-11 h-11`). | `Switch.tsx`, `TextField.tsx` |
| Cabecera más ancha que el contenido en escritorio | Resuelto: La cabecera usa `max-w-xl`, alineándose con la columna principal en todas las resoluciones. | `app/AppLayout.tsx` |
| Foco del diálogo | Resuelto: La trampa de foco ahora atrapa todos los elementos interactivos (`button, [href], input, select, textarea`) y cierra con clic en el fondo. | `shared/ui/ConfirmDialog.tsx` |

### Lo pedido y no implementado

| Elemento | Estado |
|---|---|
| Interruptor manual de modo claro/oscuro | No existe; solo sigue la preferencia del sistema. |
| Librería de íconos e ilustraciones | No hay; los íconos son SVG propios (sección 3). |
| `theme-color` distinto por modo | Hay un único valor (`#C8102E`). |
| Tarjeta del día navegable al detalle del ejercicio | Los carriles están preparados, pero no enlazan: el detalle llega con las HU 10, 12 y 13. |
| Estado `completed` del día | Tiene estilo, pero la API aún no lo emite. |
| Texto definitivo de tratamiento de datos | La pantalla de registro lleva un texto **provisional** (HU 8). |
| Prop `wide` de `Page` | Existe, sin uso. |
| Pruebas automatizadas de contraste, accesibilidad y tamaños | La verificación con axe y Playwright se hizo a mano; no está en el repositorio ni en CI. |
| Mensajes propios para `CONFIRMATION_REQUIRED`, `NOT_EDITABLE`, `EMPTY_UPDATE` y `CSRF_HEADER_MISSING` | Sin tratamiento específico, porque este cliente no debería provocarlos. |
| Aviso al redirigir al login por sesión vencida | La redirección es silenciosa: la pantalla de login no explica por qué se llegó a ella. |
