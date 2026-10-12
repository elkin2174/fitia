# Frontend Web App Structure

- `app/`: Enrutamiento con React Router, layout global, guards de sesión y providers.
- `features/`:
  - `auth/`: Registro con @correounivalle.edu.co, verificación, login, logout, eliminación de cuenta.
  - `onboarding/`: Diagnóstico inicial y resumen interpretado por IA.
  - `profile/`: Consulta y actualización de datos de perfil y consentimiento.
  - `training/`: "Entrenar hoy" (sin alterar perfil), catálogo de bodega, rutinas y guías paso a paso.
  - `calendar/`: Calendario semanal, días de descanso y festivos.
  - `challenges/`: Reporte de reto diario si es incorrecto.
- `shared/`: Componentes UI reutilizables, hooks, utilidades y cliente OpenAPI tipado.
- `styles/`: Configuración y directivas de Tailwind CSS.
