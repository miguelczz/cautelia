# Preguntas del diseño funcional — U14 `inbox`

La bandeja del ajustador: la cola por aseguradora, la vista de caso con toda su
evidencia, la corrección con rastro, la decisión con comentario que reanuda el
grafo, y el recorrido del visitante que entra a su propio caso con un enlace
firmado.

**Lo que no se pregunta, porque ya está decidido.** El recorrido de la decisión
(F5) y el de la acción de la agencia (F6) los fijó `interaction-spec.md` en
Incepción; el orden de la cola, sus filtros, los seis bloques de evidencia y las
dos compuertas duras de aislamiento los fijan los criterios de aceptación. Nada
de eso se vuelve a abrir.

Se preguntan cuatro cosas, y las cuatro cumplen la misma condición: tienen dos
respuestas legítimas y cambian lo que ve quien evalúa el producto.

---

## Q1 — El contrato ofrece una tercera decisión que nadie describe

C-05 declara tres decisiones en la bandeja: `approve`, `reject` y
`request_more`. Las dos primeras tienen sus criterios (AC3.4.2, AC3.4.3) y su
resolución en el esquema del caso. **La tercera no tiene ninguna de las dos**:
ninguna historia la describe, ningún criterio la ejercita, y las cuatro
resoluciones que U4 declara —registrado, aprobado, rechazado, enviado a la
aseguradora— no incluyen nada parecido a "pedir más información".

Construirla obligaría a inventar su conducta: a qué estado lleva el caso, qué le
llega al asegurado, si el grafo se reanuda o se queda pausado. Eso es diseñar sin
criterio, que es lo que este proyecto no hace.

- **A. No se construye en esta unidad.** El contrato se enmienda con su razón: la
  tercera decisión queda fuera hasta que exista el criterio que la describa.
  Añadirla después es un cambio aditivo, que es lo que la regla de contratos
  permite.
- **B. Se construye ahora**, decidiendo aquí a qué estado lleva y qué ve el
  asegurado.

**Recomendada: A.** Un caso que necesita más información ya tiene su camino
construido y probado: queda en "esperando al asegurado" y el asegurado lo retoma
(AC3.5.3, AC3.5.4). Una tercera acción en la pantalla que lleve al mismo sitio
por otra puerta es una forma de que dos caminos se desincronicen.

[Answer]: A — no se construye en esta unidad; el contrato se enmienda con su razón (decisión de Miguel, 2026-09-28).

---

## Q2 — Dónde quedan las acciones de decidir en el teléfono

AC3.2.1 pide que el motivo, la categoría y la completitud sean lo primero que se
ve, y que las acciones de decidir queden **al alcance sin recorrer toda la
evidencia, también en el teléfono**. Con seis bloques de evidencia debajo, eso
tiene dos soluciones legítimas y se ven distinto:

- **A. Barra de acción fija abajo.** "Aprobar" y "Rechazar" viven en una barra
  pegada al borde inferior, siempre visible, como en una aplicación de teléfono.
  El encabezado se desplaza con la página.
- **B. Encabezado pegajoso arriba.** El motivo, la categoría, la completitud y
  las acciones viajan juntos en un encabezado que se queda arriba al desplazar.

**Recomendada: B.** Mantiene juntos el *por qué llegó* y el *qué hago*, que es la
pareja que AC3.2.1 nombra en la misma frase; con la barra abajo, quien decide ve
el botón sin ver el motivo. En pantalla ancha las dos se ven casi igual, así que
la diferencia se juega entera en el teléfono.

[Answer]: B — encabezado pegajoso: motivo, categoría, completitud y acciones viajan juntos (decisión de Miguel, 2026-09-28).

---

## Q3 — La vista por enlace: ¿la misma pantalla, o una propia?

AC3.7.2 dice que el visitante entra directo a la vista de su caso, sin la lista.
Pero AC3.8.1 a AC3.8.4 le añaden un recorrido que el ajustador no tiene: qué está
viendo al entrar, hasta cuándo vale el enlace, qué pasa después de decidir, qué
hacer si el enlace venció mientras escribía el comentario.

Es **la pantalla donde alguien que evalúa el proyecto decide un caso con sus
manos**, así que la decisión es de presentación y no de implementación.

- **A. La misma vista de caso, con un encabezado propio** que dice qué es esto y
  cuánto vale el enlace, y sin lo que un visitante no necesita (corregir campos,
  volver a la lista).
- **B. Una pantalla propia del visitante** que reúsa los bloques de evidencia
  pero está escrita para alguien que llega de una conversación, no para quien
  trabaja en la bandeja: menos bloques abiertos, sin jerga y con el enlace de
  vuelta a su conversación siempre visible.

**Recomendada: B.** `interaction-spec.md` ya trae la regla U-07: ninguna etiqueta
de una pantalla de visitante usa jerga del sistema —"bandeja" no significa nada
para quien reporta—. Con la opción A esa regla obliga a dos juegos de etiquetas
sobre la misma pantalla, que es la forma segura de que un día se cruce uno.

[Answer]: B — pantalla propia del visitante, que reúsa los bloques de evidencia (decisión de Miguel, 2026-09-28).

---

## Q4 — Seis bloques de evidencia: ¿abiertos o plegados?

AC3.2.2 exige seis bloques en la vista de caso: completitud por campo,
transcripción, cláusulas citadas, regla disparada, resultado de los cuatro
controles y resumen de traza por nodo. Todos tienen que estar; lo que se decide
es si se ven abiertos.

- **A. Los seis abiertos.** Nada que abrir, todo se encuentra desplazando. En el
  teléfono es una página muy larga.
- **B. Los tres primeros abiertos, los tres últimos plegados.** Completitud,
  transcripción y cláusulas se ven de entrada; regla, controles y traza se abren
  al pulsarlos, con su titular visible —"regla disparada", "cuatro controles en
  verde", "1,8 s · 0,003 USD"— para que se sepa qué hay dentro sin abrirlo.

**Recomendada: B.** AC3.2.5 pide decidir un caso en menos de tres minutos, y lo
que decide una aprobación es el motivo, la completitud y la cita; la regla, los
controles y la traza son la evidencia que se mira cuando algo no cuadra. El
titular visible es lo que impide que plegar esconda un dato: se ve el resultado
sin abrir, y se abre para ver el detalle.

[Answer]: B — tres abiertos y tres plegados, cada plegado con su titular visible (decisión de Miguel, 2026-09-28).
