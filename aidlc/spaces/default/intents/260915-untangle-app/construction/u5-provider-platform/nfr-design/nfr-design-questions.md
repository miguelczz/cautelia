# Preguntas — Diseño de calidad de U5 `provider-platform`

Los requisitos ya están fijados: 15 ms para la escritura facturable, 50 ms para
la consulta, corte cerrado para lo que se factura, ningún texto en un tramo.
Estas cuatro preguntas son **cómo** se consiguen, y cada una tiene dos formas
razonables de hacerlo que se comportan distinto el día que algo falla.

Miguel delegó las respuestas en la recomendación, igual que las de las dos
etapas anteriores ("me voy por las recomendaciones que haces, analiza lo lógico
y vete por ello", 2026-09-21).

---

## Q1 — Quién lleva el cortacircuitos del proveedor

La práctica del equipo dice que la política de fallo de cada nodo es un dato
—tiempo máximo, un reintento, texto de degradación— aplicada por un ejecutor
común, y que un nodo no captura su propio fallo para seguir adelante. Ese
ejecutor es de U12 `graph-runtime`.

Pero un cortacircuitos no es lo mismo que un reintento. El reintento es por
nodo: la captura tolera esperar otra vez, el turno de voz no. La **salud del
proveedor**, en cambio, es una sola para todos los nodos: si Gemini está caído,
lo está para los cuatro.

- A. **(Recomendada)** El cortacircuitos vive **en el adaptador, por proveedor y
  por uso**, y es lo único de política de fallo que esta unidad lleva. El tiempo
  máximo y el reintento siguen siendo del ejecutor de nodos. Con el circuito
  abierto, la llamada falla en el acto con `unavailable` y el nodo aplica su
  política sobre esa respuesta, igual que sobre cualquier otra.
- B. Sin cortacircuitos: solo el tiempo máximo de cada nodo. Con el proveedor
  caído, un turno que toca cuatro nodos paga cuatro tiempos máximos seguidos
  antes de degradar, y el visitante espera todos.
- C. El cortacircuitos en el ejecutor de nodos. Mezcla dos ejes que no se
  parecen: la salud de una dependencia externa no depende de qué nodo la llamó,
  y el ejecutor tendría que aprender de proveedores para hacerlo.
- X. Other (please specify)

**Por qué la A.** Cada mecanismo queda donde está su información. El adaptador
es el único que sabe cuántas veces falló **ese proveedor** en el último minuto;
el ejecutor es el único que sabe qué puede tolerar **ese nodo**. Y por uso, no
solo por proveedor, porque las claves están separadas justamente para que una
cuota agotada en el chat no apague la voz.

**Con qué números.** Cinco fallos consecutivos abren el circuito; treinta
segundos cerrado; una llamada de prueba para cerrarlo. Son los valores por
defecto del patrón, y se declaran en configuración versionada para poder
cambiarlos sin tocar código.

[Answer]: A

---

## Q2 — Cómo se toma la fila del acumulado

El techo depende de que dos llamadas simultáneas no lean el mismo acumulado. La
forma de conseguirlo cambia cuánto dura el bloqueo y cuántos viajes hace.

- A. **(Recomendada)** Una **actualización condicional en una sola sentencia**
  que incrementa el acumulado y devuelve el estado resultante, dentro de la misma
  transacción que inserta la fila de gasto. Sin lectura previa: el motor
  serializa las escrituras sobre la misma fila, y devolver el valor ya
  incrementado es lo que permite decidir en el acto si se cruzó un umbral.
- B. Leer con bloqueo y después escribir. Funciona igual de bien y hace dos
  viajes en vez de uno, con el bloqueo tomado durante los dos.
- C. Un bloqueo consultivo del motor alrededor de las dos operaciones. Añade un
  mecanismo más para conseguir lo que la fila ya garantiza por sí sola.
- X. Other (please specify)

**Por qué la A.** La ventana de carrera se abre entre leer y escribir; una sola
sentencia no tiene esa ventana. Además responde con el acumulado nuevo, que es
exactamente lo que hace falta para saber si esta llamada fue la que cruzó la
alerta —y por tanto la que tiene que emitirla, una sola vez—.

[Answer]: A

---

## Q3 — Qué pasa cuando la cola del registro diferido se llena

Lo que no se factura se escribe fuera del camino de la respuesta. Eso significa
una cola en memoria, y una cola en memoria tiene que decir qué hace cuando se
llena, porque si no lo dice hará lo peor.

- A. **(Recomendada)** La cola está **acotada**, y al llenarse la escritura pasa
  a **síncrona** en vez de descartarse. Se paga latencia en el chat justo en el
  peor momento —la base va lenta y además el chat espera— y a cambio no se pierde
  ninguna fila. El costo por caso es una de las cinco cifras que el proyecto
  publica; una cifra a la que le faltan filas no es una medición.
- B. Descartar y contar los descartes. La cifra publicada pasa a ser una
  estimación con un asterisco, que es justo lo que "no medido" existe para
  evitar.
- C. Cola sin límite. Convierte una base lenta en consumo de memoria sin cota, y
  el proceso es único: cuando cae, cae todo.
- X. Other (please specify)

**Por qué la A.** Degrada en la dimensión que se puede permitir. Este proyecto
tolera que el chat vaya lento un rato; no tolera publicar una cifra de costo a la
que le faltan llamadas.

[Answer]: A

---

## Q4 — Cómo se impide que un atributo de tramo lleve texto

El requisito dice que ningún tramo lleva el texto del asegurado, la respuesta del
modelo ni el contenido de una cláusula. La pregunta es si eso se sostiene por
disciplina o por construcción.

- A. **(Recomendada)** **Por construcción.** La única forma de emitir un tramo es
  un ayudante propio con una **lista cerrada de nombres de atributo**; el
  comprobador de tipos rechaza un nombre que no esté en ella. Y un chequeo
  estático —hermano de los dos que ya existen, el de la redacción y el del
  sellado del caso— falla si algún archivo fuera de este módulo llama al SDK de
  trazas directamente. Un atributo nuevo se añade a la lista, que es donde se ve
  en una revisión.
- B. Por revisión, con una prueba de canarios que busca datos sembrados en lo
  emitido. La prueba solo cubre los caminos que a alguien se le ocurrieron, y el
  que se olvide no falla.
- C. Redactar todo lo que salga a un tramo. Cuesta en el camino del turno, y
  hace que la ausencia de datos personales dependa de que la redacción funcione,
  en vez de que no haya nada que redactar.
- X. Other (please specify)

**Por qué la A.** Es el mismo patrón que el proyecto ya aplicó dos veces —el
tipo redactado de U3 y el tipo sellado de U4— y las dos veces el análisis
estático encontró agujeros reales que la disciplina no había visto. La prueba de
canarios de la opción B se hace igualmente: como segunda capa, no como única.

[Answer]: A
