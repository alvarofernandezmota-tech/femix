# ROADMAP — femix

| Fase | Qué se hace | Estado |
|---|---|---|
| 1. Núcleo genérico | LLM + memoria + entender.py + voz + Telegram | En marcha |
| 2. Estructura de inquilino | `inquilino/perfil.py`, `capacidades.py`, sin conectar al LLM | Pendiente |
| 3. Conexión inquilino → prompt | El perfil personaliza el PROMPT_SISTEMA dinámicamente | Pendiente |
| 4. Persistencia real por inquilino | Postgres + aislamiento, migrado de `hugin` | Pendiente |
| 5. Escalado a SaaS de bots | Múltiples inquilinos reales (empresa propia, terceros) | Visión a futuro |

## Capacidades futuras (evitar el error de Perplexica)
- `busqueda_web`: pendiente.
- `memoria_largo_plazo`: activa.
- `voz`: activa.
- `postgres_citas`: pendiente, migrar desde `hugin`.
