# Agentes y modelos — cómo funciona

Rama de origen: `feat/agentes-unificados`. Capa de **producción** (vive dentro de `femix`, en cada
mensaje de cada inquilino), no la orquestación de agentes de Claude Code — ver la nota de
arquitectura de `docs/ROADMAP.md`.

## Los tres caminos de `Femix.procesar()`

Un único punto de entrada, tres caminos de más barato a más caro:

1. **Comando** — `entender.clasificar_intencion()` devuelve `"comando"` → `comandos.ejecutar_comando()`.
   Sin LLM y sin `Memoria`, igual que antes.
2. **LLM rápido** — texto libre normal → `motor.generar(contexto, entrada)` con el modelo rápido.
3. **Subagente** — `decidir.necesita_agente()` dice que sí → cadena de agentes y, si nadie resuelve,
   LLM con el modelo complejo.

En los caminos 2 y 3 la respuesta se registra en `Memoria`.

`necesita_agente()` decide por reglas (`mente/decidir.py`), no con el LLM: mismo criterio que
`entender.py`. Dispara con palabras de acción o de apoyo (`busca`, `resume`, `analiza`, `apunta`,
`tarea`…) o con mensajes de 180 caracteres o más. Es una heurística barata y deliberadamente
conservadora: equivocarse solo cuesta usar el modelo grande de más, nunca dejar sin respuesta.

## La cadena

`CadenaDeAgentes` recorre sus agentes **en orden**. De cada uno:

- `puede_atender(peticion)` → si es `False`, se salta sin ejecutarlo.
- `ejecutar(peticion)` → `RespuestaAgente` o `None`.

El campo `final` decide qué pasa después:

| `final` | Significado | Efecto |
|---|---|---|
| `True` | `texto` es la respuesta para el usuario | la cadena se detiene ahí |
| `False` | `texto` es contexto que el agente aporta | sigue el siguiente, ya con ese contexto |

Por eso el orden importa: primero los agentes que resuelven y cortan, después los que solo aportan
información. De serie: `AgenteTareas` (resuelve) y, si hay `Buscador`, `AgenteBusqueda` (aporta).

Si nadie resuelve, `Subagente` llama al LLM pasándole el contexto de memoria **más** lo que hayan
aportado los agentes no finales. El resultado va en `ResultadoCadena` (`respuesta`, `contexto`,
`pasos`, `errores`).

**Un agente que falla no rompe nada:** la excepción se anota en `errores` y la cadena sigue con el
siguiente. Y si el subagente entero falla o devuelve vacío, `Femix` responde con el LLM de siempre.
Un agente caído nunca deja al usuario sin respuesta.

## Añadir un agente

```python
from femix.agentes.agente_base import Agente
from femix.agentes.peticion import RespuestaAgente

class AgenteAgenda(Agente):
    nombre = "agenda"

    def puede_atender(self, peticion):
        return "cita" in peticion.texto.lower()

    def ejecutar(self, peticion):
        return RespuestaAgente(self.nombre, "Tienes una cita el martes.")
```

Y se enchufa en la cadena: `Femix(subagente=Subagente(CadenaDeAgentes([AgenteAgenda(), ...])))`.

## Búsqueda documental: el puerto, no `rag/`

`AgenteBusqueda` depende de `puertos/busqueda.Buscador` (`buscar(inquilino_id, texto, maximo) -> str`),
no de `rag/`. Así los agentes no conocen embeddings ni índices, y el adaptador sobre
`IndiceEmbeddings` (que se escribe en `feat/rag-por-inquilino`) encaja después sin tocar nada de
`agentes/`. Sin `buscador` inyectado, simplemente no hay agente de búsqueda.

## Dos modelos: rápido y complejo

`llm/modelos.py`. `ConfiguracionModelos` elige solo el campo `modelo` sobre una única
`ConfiguracionLLM` base — proveedor, url, timeout y api key se heredan, así que añadir un modelo no
duplica la configuración de conexión. Precedencia, de más específica a menos:

```
por_usuario > por_tarea > base.modelo
```

Un usuario fijado a un modelo lo conserva también en tareas complejas: es lo más previsible cuando
alguien tiene un modelo asignado a propósito.

`SelectorDeModelos` entrega el motor que toca y **reutiliza una instancia por `(proveedor, modelo)`**,
para que cambiar de modelo no reconstruya el cliente en cada mensaje.

Variables de entorno:

| Variable | Para qué |
|---|---|
| `HUGIN_LLM_PROVEEDOR`, `HUGIN_LLM_MODELO`, `OLLAMA_URL`, `OPENAI_API_KEY` | las de siempre: configuración base |
| `HUGIN_LLM_MODELO_RAPIDO` | modelo del camino 2 (charla, preguntas cortas) |
| `HUGIN_LLM_MODELO_COMPLEJO` | modelo del respaldo del subagente |

Sin las dos últimas, todo usa un único modelo exactamente como antes.

```bash
HUGIN_LLM_MODELO_RAPIDO=qwen2.5:3b
HUGIN_LLM_MODELO_COMPLEJO=qwen2.5:7b
```

Ojo con la CPU: la nota de rendimiento de `docs/ROADMAP.md` documenta timeouts con `qwen2.5:3b` sin
GPU. Tener dos carriles configurables no los hace gratis — hay que medir antes de poner el modelo
grande en producción.

## Desactivar la delegación

`Femix(delegar=False)` restaura el comportamiento anterior exacto: comandos + LLM único, sin
agentes.
