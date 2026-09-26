# Comprensión: documentos, búsqueda y preguntas frecuentes

Cómo entiende el bot lo que sabe el negocio. Código en `src/femix/rag/` y `src/femix/inquilino/preguntas.py`.

## 1. Qué se le puede dar

| Fuente | Cómo | Lector |
|---|---|---|
| PDF, Word (.docx), Excel (.xlsx), CSV, HTML, Markdown, texto | Panel (dueño o cliente) o `python -m femix.bot.ingerir` | `rag/lectores.py` |
| Una página web pública (la del negocio, su carta) | Panel: "Añadir web" | `lectores.leer_web` |
| Preguntas frecuentes (pregunta + respuesta exacta) | Panel: "Preguntas frecuentes" | `inquilino/preguntas.py` |

- Los PDF escaneados (solo imagen) no traen texto: se avisa al subirlos.
- `leer_web` solo abre webs públicas. Rechaza `127.0.0.1`, la red local y los metadatos de la
  nube, comprobando también cada redirección.

## 2. Troceo con sentido (`fragmentos.fragmentar_por_secciones`)

- Corta por apartados: títulos `# `, líneas en MAYÚSCULAS o terminadas en `:`, títulos de Word,
  `<h1>`–`<h4>` y hojas de Excel.
- Dentro de cada apartado junta frases hasta unos 700 caracteres, sin partir ninguna.
- Cada trozo lleva delante el título de su apartado. Así "¿cuánto cuesta el tinte?" encuentra el
  apartado *Precios* aunque la palabra "precio" no esté en la frase.

## 3. Búsqueda híbrida (`indice.buscar`)

Por cada pregunta se hacen dos búsquedas y se juntan sus órdenes con fusión por rango recíproco (RRF):

- **Significado**: embeddings. Con `FEMIX_EMBEDDINGS=ollama` usa `nomic-embed-text` o el modelo de
  `FEMIX_EMBEDDINGS_MODELO`. Entiende sinónimos.
- **Palabras exactas**: BM25 (`rag/palabras.py`), sin palabras vacías y sin tildes ni plurales.
  Acierta precios, nombres y referencias.

Un trozo llega al modelo si se parece en significado (umbral del motor) o si comparte alguna
palabra útil con la pregunta.

## 4. Preguntas de seguimiento (`agente_busqueda.consulta_de_busqueda`)

"¿y los sábados?" no dice de qué habla. Si la pregunta es corta o empieza como continuación
("y…", "eso…"), se busca junto con la pregunta anterior del usuario. No gasta una llamada al
modelo.

## 5. Citar la fuente

Lo que se encuentra llega al modelo con el nombre del documento y la instrucción de decir de dónde
sale el dato y no añadir datos que no estén ahí.

## 6. Preguntas frecuentes

| Parecido con una pregunta frecuente | Qué pasa |
|---|---|
| Muy parecida (≥ 0,75) | El bot contesta la respuesta exacta del dueño, al momento y **sin usar el modelo** |
| Algo parecida (≥ 0,34) | Se pasa al modelo como "respuesta oficial" para que la use |

El parecido son las palabras útiles en común: Jaccard sobre raíces, sin palabras vacías. Se guardan
en el almacén del inquilino (JSON o Postgres), colección `preguntas`, siempre con su `inquilino_id`.

## Tests

`tests/test_comprension.py`, más los de panel en `tests/test_web_saas.py`.
