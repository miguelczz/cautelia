# Requisitos de rendimiento — U5 `provider-platform`

Esta unidad no atiende peticiones del visitante, pero está **dentro del camino
de todas**: cada turno pasa por su fábrica de clientes, por su consulta de
presupuesto y por su registro de gasto. Lo que cuesta aquí se le cobra a la
latencia de la voz, que es la meta más dura del proyecto.

También es la unidad que produce la cifra de costo que el proyecto publica, así
que este documento tiene dos mitades que no se parecen: **cuánto puede tardar**
y **cuánto puede costar**.

## Una aclaración sobre NFR14 que conviene leer antes de la tabla

NFR14 dice "voz menor o igual a 0,02 USD por llamada de cuatro minutos". D7, que
es la decisión de la que salió esa cifra, dice "el modelo cuesta 0,005 USD o
menos por minuto de llamada; la transcripción y la síntesis se publican aparte,
a precio de lista y en gasto efectivo, **sin meta**".

Son el mismo número dicho dos veces: 0,005 USD por minuto durante cuatro minutos
son 0,02 USD. Y de ahí se sigue algo que conviene no descubrir al final:
**la meta de NFR14 cubre el modelo y nada más**. La transcripción y la síntesis
no tienen meta, se publican aparte, y su costo sale del mismo registro con su
propia fila. Esta unidad no las mezcla en una sola cifra, ni siquiera cuando
quedaría más limpia de leer.

## Objetivos medibles

**Los dos comandos que esta tabla cita —`mise run test:u5` y `mise run
spend:report`— no existen todavía**: los crea la generación de código de esta
unidad y los declara su diseño de infraestructura, igual que U4 declaró los
suyos. Hasta entonces el comprobador de artefactos los marca, y esa marca es
correcta.

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| NFR14.1 | Costo por caso exitoso a precio de lista, con su conteo de llamadas no medidas al lado | Publicado por versión; **nunca un total sin su conteo** | `mise run spend:report` |
| NFR14.2 | Costo del **modelo** por minuto de llamada sobre las grabaciones de DS-5 | **0,005 USD o menos** por minuto | `mise run evals:run` sobre DS-5; **hoy no medida**, porque DS-5 no está construido |
| NFR14.3 | Costo de transcripción y de síntesis por minuto de llamada, publicado aparte del modelo | **Sin meta** (D7); se publica a precio de lista y en gasto efectivo, en filas propias | `mise run spend:report`; **hoy no medida**, misma causa |
| PERF-U5.1 | Duración de la transacción que escribe la fila de gasto e incrementa el acumulado, en el camino facturable | **15 ms o menos en p95** | `mise run test:u5` |
| PERF-U5.2 | Duración de las dos consultas de esta unidad en el camino de disponibilidad de la voz: cuota y estado del presupuesto | **50 ms o menos en p95**, dentro de los 300 ms que C-08 da a ese endpoint | `mise run test:u5` |
| PERF-U5.3 | Exceso sobre el techo tras forzar el acumulado al borde y lanzar una llamada facturable | **A lo sumo el costo de la llamada al proveedor que estaba en vuelo**, nunca más | `mise run test:u5` |
| PERF-U5.4 | Trabajo de esta unidad en el camino de respuesta del turno, medido como diferencia con y sin el registro diferido activo | **Cero** para los usos no facturables: su fila no está en el camino de la respuesta | `mise run test:u5` |

## Presupuestos de latencia, y por qué caen donde caen

**El camino de consulta: 50 ms en p95.** Antes de pedir el micrófono, la consola
pregunta si la voz está disponible, y C-08 le da 300 ms a esa respuesta. Dentro
de ellos, lo que esta unidad aporta son dos lecturas de fila única por clave
primaria —el contador de cuota del día y el acumulado de la ventana— y la
aritmética del cupo. Cincuenta milisegundos son holgados para eso a propósito:
si alguna vez no caben, el problema no es el presupuesto sino que algo empezó a
recorrer el historial.

**El camino de escritura facturable: 15 ms en p95, y síncrono.** La fila de gasto
y el incremento del acumulado van en la misma transacción, y esa transacción
**no se puede diferir** para lo que se factura: si se difiere, dos llamadas
simultáneas leen un acumulado que todavía no incluye a la otra y el exceso deja
de estar acotado por una llamada. Quince milisegundos son un inserto y una
actualización de fila única con su bloqueo; si un día no caben, lo que se revisa
es la base, no la decisión.

**Lo no facturable, diferido.** El chat en plan gratuito no puede pasar un techo
que no consume, así que su fila se escribe fuera del camino de la respuesta. Es
la mitad barata de la decisión Q3: se paga latencia solo donde compra algo.

**Lo que esta unidad no promete.** No declara una meta de latencia para la
llamada al proveedor. No la controla: la fija el proveedor, la mide la traza y
la política de fallo por nodo —tiempo máximo, un reintento, texto de
degradación— es de U12 `graph-runtime`. Declarar aquí una meta sobre algo que no
se controla produciría una fila de la matriz que nadie puede hacer verde.

## Recursos y crecimiento del cálculo

**La tabla de precios se lee, no se consulta.** El precio por proveedor, modelo y
unidad vive en configuración versionada y se carga una vez al arrancar. Calcular
el costo de una llamada es una búsqueda en memoria y una multiplicación de
decimales, no una consulta.

**El acumulado se lee, no se suma.** Todas las cifras del corte salen de una fila
única. La única operación que recorre filas es el reporte de gasto, que no está
en el camino de ningún turno y corre cuando alguien lo pide.

**Decimales, nunca coma flotante.** El dinero se calcula y se guarda con
aritmética decimal exacta. No es purismo: con coma flotante, veinte incrementos
de fracciones de centavo dejan el acumulado a una distancia del techo que
depende del orden en que se sumaron, y el corte se vuelve no reproducible. La
decisión entera está en `tech-stack-decisions.md`.

## Sources

- `<record>/inception/requirements-analysis/requirements.md` — NFR14, NFR15,
  FR3.9, FR10.3
- `<record>/inception/user-stories/stories.md` — US5.14 con AC5.14.5 y AC5.14.6;
  decisión D7
- `<record>/inception/contract-design/contract-summary.md` — C-08 (300 ms de
  disponibilidad, 1 s de creación de sesión), C-17
- `<record>/construction/u5-provider-platform/functional-design/rules.md` —
  BR3.2, BR3.5, BR3.6, BR3.7, BR4.5, BR4.6
- `<record>/construction/u5-provider-platform/nfr-requirements/nfr-requirements-questions.md`
  — Q3

## Assumptions & Open Questions

- El precio por minuto de la voz —modelo, transcripción y síntesis— no está
  medido: lo fija el experimento 1. Hasta entonces la tabla de precios lleva el
  precio de lista publicado de cada proveedor, y las cifras que dependan de él se
  publican como tales.
- DS-5 no está construido, así que NFR14.2 y NFR14.3 se reportan **no medidas**
  con esa causa, nunca `N/A`.
- Los presupuestos de 15 ms y 50 ms se fijan sobre una base local en
  contenedor, que es donde corre la suite. El intent `infra` decide el proveedor
  de base gestionada; si su latencia base fuera mayor, estos números se revisan
  ahí con su medición, no se relajan aquí.
