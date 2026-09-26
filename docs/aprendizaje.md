# Aprendizaje: el bot mejora con el uso

El código está en `src/femix/mente/aprendizaje.py`. Funciona por reglas y no gasta llamadas al
modelo. Está activo en los inquilinos con la capacidad `memoria_largo_plazo`.

| Qué aprende | Ejemplo | Quién lo ve | Cuándo lo usa |
|---|---|---|---|
| Del cliente | "Recuerda que soy alérgico al tinte", "Que sepas que me llamo Ana" | Solo ese cliente | Al momento, siempre |
| Del negocio | "No, los sábados cerráis a las dos" | Todos | **Solo cuando el dueño lo aprueba** en su panel (lo puede corregir antes) |
| Preguntas sin respuesta | "¿Aceptáis bizum?" y no está en los documentos | El dueño | Al contestarla en el panel pasa a pregunta frecuente |

- "Olvídalo" borra lo último que ese cliente enseñó.
- Lo que alguien dice del negocio no cambia lo que el bot cuenta a los demás hasta que el dueño lo
  aprueba. Así nadie puede colarle datos falsos.
- Los datos del negocio aprobados mandan sobre todo lo demás. Al modelo solo le llegan los que
  vienen a cuento con cada pregunta.

## En el panel

La sección "Lo que el bot está aprendiendo" aparece en el panel del dueño (ficha de cada
inquilino) y en el del cliente (`/usuario/panel`). Desde ahí se puede:
- aprobar, corregir o descartar lo pendiente;
- contestar las preguntas que el bot no supo;
- enseñarle datos directamente;
- olvidar datos que ya sabe.

## Dónde se guarda

En el almacén del inquilino (JSON o Postgres), colección `aprendido`, siempre con su `inquilino_id`:

| Lista | Qué guarda |
|---|---|
| `_negocio` | Datos del negocio aprobados |
| `_pendientes` | Lo pendiente de aprobar |
| `_sin_respuesta` | Preguntas que el bot no supo contestar |
| ID de cada usuario | Lo que ha contado ese cliente |

Tests: `tests/test_aprendizaje.py`.
