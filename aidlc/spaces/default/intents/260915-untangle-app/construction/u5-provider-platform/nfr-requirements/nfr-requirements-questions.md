# Preguntas — Requisitos de calidad de U5 `provider-platform`

El diseño funcional dejó cuatro cosas explícitamente encargadas a esta etapa, y
al escribirla apareció una quinta. Las cinco tienen dos respuestas legítimas y
las cinco cambian algo que se ve o algo que se paga.

Miguel delegó estas respuestas en la recomendación, igual que las seis del
diseño funcional ("me voy por las recomendaciones que haces, analiza lo lógico y
vete por ello", 2026-09-21). Cada una lleva su razón escrita antes de la
respuesta.

---

## Q1 — Qué sustituye al tope por clave donde el proveedor no lo tiene (PA-9)

La práctica del equipo exige que cada clave lleve **su propio tope configurado en
el proveedor**, para que una cuota agotada no tumbe las otras y una clave
filtrada no agote el presupuesto entero. Y FR3.10 lo dice más fuerte: con la
aplicación detenida, el proveedor tiene que seguir rechazando por encima de su
tope.

El problema es que esa figura no existe en todos los proveedores. Lo que sí
existe casi siempre es una **alerta de presupuesto**, que avisa y no detiene
nada. `unit-of-work.md` dejó este hueco abierto con nombre propio —PA-9— y lo
asignó a esta etapa.

- A. **(Recomendada)** Donde el proveedor no ofrece un tope duro, lo que lo
  sustituye es un **saldo prepagado con la recarga automática desactivada**: el
  gasto se detiene solo cuando el saldo llega a cero, y eso sí ocurre con la
  aplicación detenida. La tabla versionada de topes declara, por uso, cuál de las
  cuatro figuras rige —saldo prepagado, tope mensual, límite de tasa o ninguna
  disponible— y **cuándo se comprobó por última vez**. Y se escribe sin adornos
  que **una alerta de presupuesto no cuenta como tope**: no se anota en esa
  columna y no se cuenta como control.
- B. Aceptar la alerta de presupuesto del proveedor como sustituto. Es la opción
  que parece equivalente y falla abierta: avisa mientras el gasto sigue.
- C. No usar ningún proveedor que no ofrezca tope duro. Deja la voz sin
  proveedor, porque ninguno de los candidatos lo ofrece hoy.
- X. Other (please specify)

**PA-9 es de dos unidades, y esta es la primera.** `unit-of-work.md` y
`contract-summary.md` lo asignan a las etapas `nfr-requirements` de U5 **y** U15.
Lo que se decide aquí es la política y el esquema de la tabla; U15 los hereda y
llena las filas de sus proveedores de voz, que son otros y pueden ofrecer otras
figuras. Esta respuesta no cierra la pregunta para U15: le fija la forma de
responderla.

**Por qué la A.** Es la única que produce la conducta que FR3.10 describe —con
la aplicación detenida, el gasto para— y es además la que ADR-006 ya eligió para
la voz sin llamarla así. Lo nuevo aquí no es el prepago: es **negarse a contar
una alerta como tope** y dejar la fecha de la última comprobación a la vista,
porque un tope que nadie miró en dos meses es una creencia.

[Answer]: A

---

## Q2 — Cuánto vale la reserva de grabación, y en qué unidad se declara

FR3.11 dice que existe y para qué —grabar el video final y la sesión de
escucha—, no cuánto. El diseño funcional dejó el número aquí.

Declararlo en dólares tiene un problema: el precio por minuto de la voz no está
medido todavía (lo fija el experimento 1), así que un número en dólares quedaría
desactualizado el día que se mida y nadie se enteraría.

- A. **(Recomendada)** La reserva se declara en **minutos de llamada de
  grabación**, no en dólares, y se convierte a dólares con la misma tabla
  versionada de precios que calcula todo lo demás. Valor inicial: **45 minutos**,
  que son quince llamadas de la duración máxima de tres minutos. La razón del
  número está a la vista: FR14.2 pide que el video muestre la escena de la
  llamada, el proyecto es bilingüe, y grabar una escena utilizable exige varias
  tomas por idioma; la sesión de escucha necesita material suficiente para juzgar
  el acento. A la meta de costo del modelo de D7 —0,005 USD por minuto— eso son
  0,225 USD, menos del 5 % del techo.
- B. Un número en dólares fijo. Se entiende de un vistazo y envejece mal: el día
  que el experimento 1 mida el precio real, la reserva cubre otra cantidad de
  minutos sin que nadie lo decida.
- C. Un porcentaje del techo. No se puede razonar sobre él —¿alcanza para el
  video o no?— que es justo la pregunta que hay que poder responder.
- X. Other (please specify)

**Por qué la A.** La reserva existe para que quepa una cosa concreta: la
grabación del video. Declararla en la unidad de esa cosa —minutos de llamada—
hace que la pregunta "¿alcanza?" se pueda responder sin una calculadora, y que
un cambio de precio ajuste los dólares sin tocar la decisión.

**Qué pasa si falta el precio.** La conversión queda "no medida". En ese caso se
corta el carril público y se deja abierto el de grabación: entre las dos cosas
que pueden perderse, la demostración se puede volver a encender mañana y la
grabación del video de la semana doce no.

[Answer]: A

---

## Q3 — Cuánto puede tardar el registro del gasto, y si puede ir por detrás

El registro de gasto está en un sitio incómodo: **después** de cada llamada a un
proveedor, y el techo depende de que esté escrito. Si se escribe en diferido,
dos llamadas simultáneas pueden leer un acumulado que todavía no incluye a la
otra, y el exceso deja de estar acotado por una llamada.

Pero el turno de voz tiene una meta de latencia dura (p50 menor que 500 ms del
fin del habla al primer audio), y todo lo que se ponga en ese camino la consume.

- A. **(Recomendada)** El registro es **síncrono para lo facturable** —que es lo
  único de lo que depende el techo— y **diferido para lo que no se factura**. El
  camino síncrono lleva presupuesto declarado: 15 ms en p95 para la transacción
  que escribe la fila e incrementa el acumulado. Si alguna vez se pasa, lo que se
  revisa es la base, **no** se convierte en diferido: hacerlo diferido rompe la
  cota del exceso, que es lo que esa transacción compra.
- B. Todo diferido. El turno queda más rápido y el techo deja de estar acotado.
- C. Todo síncrono. Paga latencia en el chat gratuito sin comprar nada, porque
  ningún techo depende de esas filas.
- X. Other (please specify)

**Por qué la A.** Reparte el costo donde está el riesgo. El chat gratuito no
puede pasar un techo que no consume, así que su fila puede esperar; la voz de
pago sí, así que la suya no.

**El camino de consulta, aparte.** La disponibilidad de la voz lleva 300 ms de
presupuesto en el contrato C-08, y dentro de ese presupuesto las consultas de
esta unidad —cuota y estado del presupuesto— llevan **50 ms en p95**: son dos
lecturas de fila única por clave primaria.

[Answer]: A

---

## Q4 — Cuánto se espera un resumen de traza antes de declararlo perdido

El diseño funcional dejó el estado `lost` definido y su espera sin fijar. La
espera importa porque lo que ve el visitante mientras tanto es "registrándose",
y una espera larga convierte esa etiqueta en un fallo silencioso.

- A. **(Recomendada)** **Diez segundos** desde que la respuesta terminó de
  salir. El número no es redondo por gusto: la meta del chat es p95 menor que
  3 s del envío a la primera palabra, así que diez segundos son más del triple de
  lo que tarda la respuesta entera. Un resumen que no llegó en ese plazo no está
  llegando tarde: no está llegando, y eso es lo que `lost` dice.
- B. Esperar indefinidamente. La etiqueta "registrándose" se queda para siempre
  en la pantalla y nadie sabe si el panel de trazas está caído.
- C. Un plazo mucho más corto, del orden del segundo. Declararía perdidos los
  resúmenes de un turno lento, que es contaminar una señal de infraestructura con
  una de carga.
- X. Other (please specify)

**Por qué la A.** Ata el plazo a una meta que ya existe y que ya se mide, en vez
de a una intuición. El día que la meta del chat cambie, este plazo se recalcula
en lugar de quedarse desactualizado.

[Answer]: A

---

## Q5 — Qué hace el corte cuando la base de datos no responde

El acumulado vive en una fila de la base. Si la base no responde en el momento
de decidir si una llamada de pago puede hacerse, hay que elegir entre dejarla
pasar y negarla, y las dos son defendibles: una protege la demostración, la otra
protege el bolsillo.

- A. **(Recomendada)** **Cerrado para lo que se factura, abierto para lo que
  no.** Sin poder leer el acumulado, una llamada de pago se rechaza con el mismo
  motivo de presupuesto y su mensaje honesto; el chat, que corre en plan gratuito
  y no consume el techo, sigue atendiendo. La razón está escrita en las prácticas
  del equipo antes que aquí: un límite que falla abierto cuando lo que falla es
  la aplicación no es un límite.
- B. Abierto para todo. Una caída de la base se convierte en gasto sin techo,
  que es exactamente el escenario que el techo existe para impedir.
- C. Cerrado para todo. Una caída de la base apaga también el chat, que no cuesta
  nada, y con él la demostración entera.
- X. Other (please specify)

**Por qué la A.** Cierra donde hay dinero y abre donde no lo hay. La asimetría no
es una excepción: es la misma distinción entre carriles que ya gobierna el
techo, aplicada al caso en que no se puede leer nada.

[Answer]: A
