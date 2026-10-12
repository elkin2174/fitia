"""Valores permitidos del diagnóstico inicial: ÚNICA fuente de verdad (NFR-13).

El cuestionario, el validador, los modelos y los tests se construyen a partir de aquí.
La migración 0002 replica estos valores en sus CHECK; el test anti-deriva verifica que coincidan.
"""

GOALS: tuple[str, ...] = ("general_health", "strength", "endurance", "weight_loss")
TERM_WEEKS: tuple[int, ...] = (4, 8, 12)
FITNESS_LEVELS: tuple[str, ...] = ("beginner", "intermediate", "advanced")
SESSION_MINUTES: tuple[int, ...] = (15, 30, 45, 60)
MACHINE_ACCESS: tuple[bool, ...] = (True, False)
WEEKDAYS: tuple[int, ...] = (1, 2, 3, 4, 5)  # 1 = lunes … 5 = viernes
