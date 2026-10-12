# La oficina de Femix

Femix es un chatbot que funciona como una oficina: cada pieza tiene su puesto y todas se reparten el
trabajo para organizar a una persona o a un negocio. Cada negocio es una oficina distinta y su perfil
(capacidades) decide qué puestos están ocupados.

| Puesto | Pieza | Dónde está |
|---|---|---|
| Recepción | Conectores (Telegram, app) y `Femix.procesar()` | `conectores/`, `bot/femix.py` |
| Portero | Comandos y atajos de agenda, sin modelo | `bot/comandos.py`, `mente/atajos.py` |
| Secretaria | Corrector de faltas y abreviaturas con el vocabulario del negocio | `mente/normalizar.py` |
| Archivo | Memoria, aprendizaje y preguntas frecuentes del dueño | `mente/`, `inquilino/preguntas.py` |
| Biblioteca | RAG con los documentos de cada negocio | `rag/` |
| Gerente | Coordinador de la colmena: decide qué especialistas atienden | `colmena/coordinador.py` |
| Especialistas | Personal, reservas, documental, externo | `colmena/especialistas.py` |
| Contabilidad | Plan, límites y suscripción por inquilino | `saas/` |
| Registro | Actividad e incidencias para el panel | `infraestructura/actividad.py` |

## Cómo se arma una oficina

`bot/fabrica.py` monta el bot de cada inquilino según sus capacidades. Con la capacidad `colmena`
(experimental, apagada por defecto y solo en el plan interno) construye `FemixColmena`; sin ella, el
`Femix` de siempre.

## Lo que falta para que se complementen del todo

1. **Pasar trabajo entre puestos:** ejecutar el plan por pasos (`colmena/plan.py`) para peticiones
   compuestas, con confirmación de las acciones destructivas.
2. **Tablón compartido:** estado que ven todos los puestos (preferencias, lo aprendido, contexto).
3. **Proactividad:** que la oficina se adelante (avisos, resumen del día) sin esperar al usuario.

Ver `docs/MVP.md` (vías A y B) y `docs/AUDITORIA.md`.
