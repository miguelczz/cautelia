# Preguntas — Diseño funcional de U12 `graph-runtime`

Lo que ya está fijado y no se vuelve a discutir:

- **ADR-003:** LangGraph con estado tipado, puntos de control e interrupciones,
  y solo esta unidad lo importa.
- **ADR-004:** el trabajo de fondo son tareas asíncronas del mismo proceso, sin
  broker; cada ejecución de nodo lleva arrendamiento con latido y clave de
  idempotencia.
- **D22:** dentro del turno corren solo tres controles baratos, y son de U10.
- **C-14 y C-15:** la interfaz del turno y el contrato de un nodo ya están
  escritos, con sus firmas.

Queda **un** hueco que ningún documento resuelve, y el catálogo de unidades lo
manda explícitamente a esta etapa.

---

## Q1 — El aislamiento de los puntos de control: ¿quién abre la conexión?

Cada conversación deja un punto de control en la base de datos para poder
reanudarla. La regla dura del proyecto es que **toda consulta pasa por un único
punto que fija la aseguradora antes de devolver la conexión** — es lo que hace que
una aseguradora no pueda leer los datos de otra, y es compuerta dura.

El problema: los puntos de control no los escribe nuestro código, los escribe la
pieza del framework, y esa pieza **toma sus propias conexiones**, sin pasar por
ese punto único. Así que el aislamiento que protege todo lo demás no la cubre.

El ejemplo concreto de lo que hay que evitar: una conversación de Knotwell se
reanuda y el framework lee el punto de control más reciente de ese hilo; si la
conexión no lleva la aseguradora fijada, nada en la base impide que ese hilo sea
de Stonecroft.

- A. **(Recomendada)** **Envolvemos la pieza del framework.** Escribimos una capa
  delgada que intercepta sus cuatro operaciones de lectura y escritura y las corre
  dentro de una transacción tomada del punto único, con la aseguradora ya fijada.
  Es más código nuestro, pero no aparece una segunda forma de abrir una conexión.
- B. **Un grupo de conexiones por aseguradora.** Se deja la pieza del framework
  tal cual y se le entrega un grupo de conexiones distinto por aseguradora, cada
  uno con la aseguradora fijada al crearse. Menos código, pero hay un segundo
  camino hacia la base que el control de "una sola puerta" no vigila.

**Por qué A.** Porque la regla "ningún otro módulo abre una conexión" no es una
preferencia de estilo: es lo que hace que el control automático que revisa el
esquema pueda afirmar algo. Con B el control seguiría pasando y habría un camino
que no revisa — y un camino que nadie revisa es el que sigue ahí dentro de seis
semanas, cuando ya nadie recuerde que era especial.

**Lo que cuesta A, dicho antes de elegirla.** La pieza del framework trabaja hoy
en modo "cada operación se confirma sola", y envolverla en transacciones cambia
ese supuesto. Si al construirla resulta que la pieza no tolera que otro maneje sus
transacciones, la salida no es volver a B en silencio: es escribir nuestra propia
pieza de puntos de control, que es más trabajo y hay que decirlo cuando pase.

**[Answer]:** A — Envolver la pieza del framework. Decisión de Miguel, 2026-09-27.
