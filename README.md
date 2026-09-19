# HUGIN

## EL BOT VIVO COMPLETO

Conversa · entiende · decide · actúa
usa LLM · consulta RAG · llama agentes · guarda memoria · avisa
agenda · tareas · diario · negocio

│ │
┌──────────┘ └──────────┐
▼ ▼
Telegram Teléfono
cuerpo de texto, cuerpo de voz,
botones y archivos llamadas y webhooks

text

## Descripción

HUGIN es un bot conversacional autónomo que combina un modelo de lenguaje (LLM), un sistema de recuperación de información (RAG), memoria persistente y agentes especializados, con dos canales de interacción: Telegram (texto, botones, archivos) y Teléfono (voz, llamadas, webhooks).

## Componentes

- **LLM**: motor de razonamiento y generación de respuestas.
- **RAG**: consulta de conocimiento externo/documental. *(pendiente de implementar)*
- **Agentes**: ejecución de tareas y acciones delegadas. *(pendiente de implementar)*
- **Memoria**: persistencia de contexto y estado entre sesiones (`mente/memoria.py`).
- **Comprensión de intención**: clasificación básica por reglas del texto entrante
  en `comando` / `pregunta` / `charla` (`mente/entender.py`).
- **Dominio personal** (`dominio/personal/`): lógica de negocio real, persistida en
  JSON dentro de `datos/` (no versionado), siguiendo el mismo patrón que `memoria.py`:
  - `hoy.py` — resumen de la fecha/hora actual.
  - `tareas.py` — crear, listar y completar tareas.
  - `diario.py` — registrar entradas de diario con fecha/hora.
  - `recordatorios.py` — crear recordatorios y listar los pendientes (sin scheduler real todavía).
- **Canales**: Telegram (texto y voz) implementado en `conectores/telegram/`.
  Teléfono (llamadas/webhooks) todavía no está implementado.
