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

## 5. Documentos (RAG) y aprendizaje

Ver [rag.md](rag.md) y [aprendizaje.md](aprendizaje.md). La consulta a los documentos va
normalizada («korte» encuentra «corte»); lo aprendido se guarda ya corregido.

## Probarlo

```bash
python -m pytest tests/test_normalizar.py tests/test_comprension.py tests/test_velocidad.py -q
```

Y a mano: `PYTHONPATH=src python -c "from femix.mente.normalizar import normalizar; print(normalizar('resrva pa el jueves k hora abris?¿?¿'))"`.
