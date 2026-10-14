# Requisitos de escalabilidad — U5 `provider-platform`

Conviene empezar por el tamaño real, porque determina todo lo demás y porque
inflarlo sería el error más fácil de cometer aquí.

**Este sistema no tiene que escalar. Tiene que no gastarse.** Es una
demostración de portafolio con un enlace de voz limitado a quince llamadas
diarias como mucho, un chat con límite por sesión y por día, y un techo de 5 USD
en noventa días. El cuello de botella de diseño no es la concurrencia: es el
dinero, y el límite de dinero está puesto a propósito muy por debajo de
cualquier límite técnico.

Lo que sigue, entonces, no es un plan de crecimiento. Es **dónde está el límite,
qué se degrada primero cuando se acerca, y qué crece sin que nadie lo mire**.

## Objetivos medibles

**Los dos comandos que esta tabla cita —`mise run test:u5` y `mise run
spend:report`— no existen todavía**: los crea la generación de código de esta
unidad y los declara su diseño de infraestructura, igual que U4 declaró los
suyos. Hasta entonces el comprobador de artefactos los marca, y esa marca es
correcta.

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| SCA-U5.1 | Llamadas facturables simultáneas que pasan el techo cuando el acumulado está a una llamada del borde | **A lo sumo 1**; la que pierde la carrera encuentra el acumulado ya incrementado | `mise run test:u5` |
| SCA-U5.2 | Sesiones de voz simultáneas del mismo visitante que consiguen abrir con un cupo de una | **Exactamente 1**; la otra recibe su motivo | `mise run test:u5` |
| SCA-U5.3 | Filas leídas para responder el estado del presupuesto y el cupo del día | **Exactamente 2**, sin recorrer el historial, con el registro de gasto sembrado con diez mil filas | `mise run test:u5` |
| SCA-U5.4 | Crecimiento del registro de gasto por llamada | **Una fila por llamada**, sin excepción y sin agregados intermedios | `mise run test:u5` |

## Dónde está el cuello de botella, y por qué está ahí a propósito

**La fila del acumulado se bloquea, y esa es su función.** Toda llamada
facturable toma el bloqueo de una fila única para incrementarla. Eso serializa
las escrituras facturables del proyecto entero, y es exactamente lo que compra la
cota del exceso: dos llamadas simultáneas no pueden pasar el techo cada una
creyendo que la otra no existe.

El costo de esa serialización es real y está acotado por el mismo diseño: el
carril público admite como mucho quince llamadas al día, así que la contención
máxima que este diseño puede producir es de unas pocas escrituras por minuto en
el peor momento imaginable. Cambiar la fila única por sumas o por particiones
compraría una concurrencia que nadie va a usar y vendería la única garantía que
el techo tiene.

**Lo no facturable no toma ese bloqueo.** El chat en plan gratuito escribe su
fila en diferido y no incrementa el acumulado, así que su volumen —que es el
único que puede crecer de verdad— no toca el punto serializado.

## Qué se degrada primero, en orden

1. **El cupo del sitio baja.** Antes que nada, un día de tráfico alto reduce el
   cupo de los días siguientes: la fórmula reparte lo que queda entre los días
   que faltan. Es una degradación por diseño, no un fallo, y es lo que sustituyó
   a la proyección vieja que dejaba la voz apagada hacia el día 67.
2. **El carril público de la voz se cierra.** Presupuesto público agotado: la
   consola lo dice antes de pedir el micrófono y el chat sigue.
3. **La reserva de grabación sigue intacta.** Es la última en caer porque es la
   única que no se puede volver a llenar cuando hace falta: el video de la semana
   doce se graba una vez.
4. **El chat entra en modo degradado** cuando su propio límite por sesión o por
   día se alcanza, con mensaje honesto y no con un error genérico.

Ninguno de los cuatro es una caída. Los cuatro son respuestas.

## Lo que crece sin que nadie lo mire

| Qué | Cuánto crece | Qué lo acota |
| --- | --- | --- |
| Registro de gasto | Una fila por llamada a proveedor, incluidas las de las evaluaciones | Nada lo borra, y así tiene que ser: es el histórico de costo. A este volumen —miles de filas en noventa días— no necesita partición ni archivado |
| Contadores de cuota | Una fila por sujeto, alcance y periodo | El purgador nocturno se lleva los de visitante y de sesión; queda el del sitio, uno por día |
| Resúmenes de traza | Uno por respuesta del chat | El purgador nocturno se los lleva con su caso |
| Acumulado de la ventana | Una fila por ventana | Noventa días por ventana |

**Lo único que crece sin cota es el registro de gasto**, y se deja crecer a
propósito: borrarlo perdería la única cifra histórica que el proyecto publica.
Si algún día molestara, lo que corresponde es archivar por ventana cerrada, no
borrar; queda escrito aquí para que esa decisión se tome mirando un número y no
por sorpresa.

## Sources

- `<record>/inception/requirements-analysis/requirements.md` — FR3.9 con su
  enmienda del 2026-09-19, FR3.11, FR4.6, NFR15, y la suposición A5 que dejó de
  asumirse
- `<record>/construction/u5-provider-platform/functional-design/rules.md` —
  BR4.5, BR4.6, BR4.9, BR5.4, BR5.6, BR7.5, BR7.6
- `<record>/construction/u5-provider-platform/functional-design/functional-spec.md`
  — §2.1 y los flujos F2, F3 y F6
- `<record>/inception/contract-design/contract-summary.md` — C-08, C-17

## Assumptions & Open Questions

- Los números de este documento describen una demostración de portafolio con
  cupos de un dígito diario. Si el alcance cambiara —un cliente real, tráfico de
  verdad—, la fila única del acumulado es lo primero que habría que rediseñar, y
  se dice aquí para que se sepa por dónde empezar.
- El archivado del registro de gasto por ventana cerrada no se diseña ahora: no
  hay volumen que lo justifique. Queda anotado como el camino correcto si algún
  día hiciera falta.
