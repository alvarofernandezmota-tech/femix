# Conectores MCP

**MCP** (Model Context Protocol) es el estándar abierto para dar herramientas a un modelo de IA.
Un servidor MCP publica sus herramientas y femix se las ofrece al modelo igual que las suyas:
el bot las usa solo cuando detecta la intención. Ejemplos de servidores: Google Calendar, Gmail,
Notion, una base de datos o el sistema de gestión del negocio.

## Activarlo para un inquilino

1. **Capacidad** `conectores_mcp` en su ficha. Está incluida en el plan Pro y en el interno.
2. En la ficha del inquilino (solo el panel del dueño), en *Conectores MCP*, una línea por
   servidor:
   ```
   calendario | https://mcp.ejemplo.com/mcp | Bearer TOKEN
   ```
   - **nombre**: minúsculas, cifras, `-` y `_`. Va delante del nombre de cada herramienta.
   - **url**: la del servidor MCP por HTTP (*Streamable HTTP*).
   - **cabecera**: el valor de `Authorization`, si el servidor lo pide. Es secreta: nunca se
     enseña, y si dejas la línea sin ella se conserva la que había.
3. Guardar. El bot lo relee en cada mensaje, así que no hace falta rearrancar nada.

## Seguridad

- Solo el dueño de la plataforma puede ponerlos: un servidor MCP puede hacer cosas reales en
  cuentas externas.
- El cliente no los ve ni los puede borrar desde su panel.
- Cada servidor aporta como mucho 20 herramientas: un modelo pequeño se lía con demasiadas.
- Sus resultados pasan por el mismo ejecutor que las herramientas propias:
  - no admite argumentos inventados;
  - los errores vuelven al modelo como texto;
  - el resultado se recorta a 1.500 caracteres.
- Un servidor caído se salta y queda en el log. El bot sigue con sus propias herramientas.
- Los mensajes que hablan de calendario, correo, eventos, reuniones o Notion van al camino de
  herramientas.

## Detalles técnicos

- Cliente propio y mínimo en `src/femix/llm/mcp.py`: JSON-RPC 2.0 con `initialize`, `tools/list` y
  `tools/call`.
- Acepta respuestas en JSON o en SSE y reutiliza la sesión (`Mcp-Session-Id`).
- La lista de herramientas se guarda en caché 10 minutos.

Tests: `tests/test_mcp.py`, con un servidor MCP simulado.
