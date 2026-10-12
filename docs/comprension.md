# Comprensión: cómo entiende el bot lo que le escriben

Un mensaje pasa por varias capas antes de llegar al modelo. Cada una es barata (sin modelo) y
resuelve una parte; el modelo solo entra cuando hace falta.

```
mensaje ─► normalizar ─► ¿comando? ─► ¿pregunta frecuente? ─► router ─► herramientas / documentos / charla
              │                                                            (modelo, con memoria y lo aprendido)
              └─ solo para entender: al modelo y a la memoria va el texto original
```

## 1. Normalizar: faltas, abreviaturas y repeticiones (`mente/normalizar.py`)

La gente escribe «resrva pa el jueves k hora abris?¿?¿». Antes de decidir nada, el mensaje se
normaliza:

| Paso | Ejemplo |
|---|---|
| Abreviaturas de chat | «k» → «que», «xfavor» → «por favor», «mñn» → «mañana», «kiero» → «quiero» |
| Puntuación y letras repetidas | «?¿?¿?» → «?», «holaaaa» → «hola» |
| Faltas, con el vocabulario del dominio | «resrva» → «reserva», «presio» → «precio», «korte» → «corte», «aparcamineto» → «aparcamiento» |

**Reglas para no corregir de más.** Un diccionario general del castellano corrige palabras que
no debe («quiero» → «quieto», «Paula» → «jaula», «apunta» → «punta»). Por eso:

- Solo se corrigen palabras que **no existen** (se comprueba con `pyspellchecker`, MIT, diccionario
  de frecuencias en español) y que no están ya en el vocabulario.
- El candidato tiene que estar en el **vocabulario del dominio**: lo que el bot sabe hacer
  (reservas, agenda, precios, horarios, días…) más las palabras del **perfil de cada negocio**
  (nombre, descripción, nombre del asistente) y sus **preguntas frecuentes**. Así «keratna» se
  corrige a «keratina» en la peluquería que lo ofrece y no en otro sitio.
- A una edición de distancia (Norvig: borrar, cambiar, transponer, insertar); a dos solo en
  palabras de 7 letras o más y con parecido ≥ 0,85.
- Palabras de menos de 4 letras, con números, nombres propios y palabras reales se dejan igual.

El texto normalizado se usa para el router, las preguntas frecuentes, la consulta a los
documentos y los disparadores de aprendizaje. **Al modelo y a la memoria va el original**, para
respetar nombres y la forma de escribir de cada persona.

Coste: unos milisegundos por mensaje; el diccionario se carga una vez por proceso (0,1 s).

## 2. Comandos (`bot/comandos.py`)

`/hoy`, `/semana`, `/tarea`, `/agenda`, `/recordatorio`, `/reserva`… Sin modelo.

## 3. Preguntas frecuentes (`inquilino/preguntas.py`)

Las respuestas exactas del dueño. Parecido por palabras útiles (raíces, sin vacías): con dos
palabras en común y parecido ≥ 0,75 se contesta al momento; entre 0,34 y 0,75 se le pasa al
modelo como «respuesta oficial».

## 4. Router (`mente/decidir.py`)

Sin modelo, por palabras y forma de la frase:

- **Herramientas** (reservar, apuntar, recordar, cancelar, «pedir hora», «mesa para»…): el modelo
  con function calling ejecuta la acción real.
- **Consulta** (precio, horario, «cuánto cuesta», «aceptáis tarjeta»… y una pregunta): se buscan
  los documentos del negocio y contesta el modelo rápido, en directo.
- **Charla**: el modelo rápido con la memoria de la conversación.

Las palabras ambiguas («mañana», «libre», «hecho») no cuentan solas: «hasta mañana» es una
despedida, no una reserva.

### Construcciones, no solo palabras (`PATRONES_HERRAMIENTAS`)

Algunas órdenes personales no llevan una palabra suelta fiable, así que se reconocen por la
construcción de la frase. Son estrechas a propósito, para no mandar charla a las herramientas:

| Qué se dice | Ejemplos que sí | Ejemplos que siguen siendo charla |
|---|---|---|
| Consultar la agenda | «qué tengo hoy», «¿qué tengo mañana?», «qué tengo el jueves», «algo libre el jueves» | «qué tengo que decirte» |
| Completar o quitar | «tacha lo de…», «quítalo de la lista», «borra la tarea…», «ya está hecho lo del banco» | «quita esa cara», «ya está hecho un lío» |
| Diario y avisos sin palabra clave | «quiero dejar constancia de…», «no me dejes olvidar…» | — |
| Cita dicha como afirmación | «el viernes tengo veterinario a las 11» | «tengo sueño a las tantas» |

**Limitación conocida:** una entrada de diario sin ninguna palabra de acción («hoy he caminado con el
perro por la sierra») sigue yendo a charla. Arreglarlo con más palabras clave daría falsos
positivos; lo correcto es que el bot pregunte «¿lo apunto en tu diario?» (pendiente, issue #33).

## 5. Documentos (RAG) y aprendizaje

Ver [rag.md](rag.md) y [aprendizaje.md](aprendizaje.md). La consulta a los documentos va
normalizada («korte» encuentra «corte»); lo aprendido se guarda ya corregido.

## 6. Medir el acierto del router

`tests/datos/casos_router_mvp.csv` tiene 65 frases coloquiales (las 6 acciones básicas del MVP y
charla, con faltas y abreviaturas) y la ruta que debe tomar cada una. `scripts/medir-router.py`
las pasa por `normalizar` y por las reglas y muestra el acierto por acción y los fallos:

```bash
python scripts/medir-router.py
```

Solo informa, no falla. Medida de referencia (issue #33, entorno sin `pyspellchecker`):

| Momento | Aciertos |
|---|---|
| Reglas anteriores | 53/65 (48/60 en las 60 frases originales) |
| Con `PATRONES_HERRAMIENTAS` | 63/65; solo fallan dos entradas de diario sin palabra de acción |

Cuando el bot falle con un mensaje real, añádelo al CSV con la ruta correcta: así el conjunto
crece con el uso.

## Probarlo

```bash
python -m pytest tests/test_normalizar.py tests/test_comprension.py tests/test_velocidad.py tests/test_router_agenda.py -q
python scripts/medir-router.py
```

Y a mano: `PYTHONPATH=src python -c "from femix.mente.normalizar import normalizar; print(normalizar('resrva pa el jueves k hora abris?¿?¿'))"`.
