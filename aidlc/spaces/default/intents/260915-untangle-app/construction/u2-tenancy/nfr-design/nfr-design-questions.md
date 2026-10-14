# Preguntas — Diseño de calidad de U2 `tenancy`

Esta etapa diseña **cómo** se consiguen los objetivos que fijó la anterior. Casi
todo quedó decidido allí, así que solo quedan dos decisiones de forma.

**Alcance de esta etapa para U2.** La unidad es de tipo `library`, así que el
contrato pide dos documentos: diseño de seguridad y componentes lógicos. Los de
rendimiento, escalabilidad, fiabilidad y observabilidad los piden las unidades
`service`.

**Fuentes consumidas.** `../nfr-requirements/security-requirements.md` (los
catorce controles y los objetivos medibles),
`../nfr-requirements/correcciones-tras-revision.md` (que rige donde contradiga al
anterior), `../nfr-requirements/tech-stack-decisions.md`,
`../functional-design/functional-spec.md` (los siete flujos) y
`../../../inception/contract-design/contract-summary.md` (C-07, C-10, C-30).

Aplico sin preguntar lo que ya está decidido: las dos claves de firma separadas
por uso, PyJWT para la credencial y biblioteca estándar para el enlace, la
rotación sin ventana de gracia, el evento de rechazo con aseguradora y rol, la
comparación del resumen del token en tiempo constante, y la aserción que
pregunta al catálogo vivo.

## Q1 — Qué forma tiene la política de aislamiento en cada tabla

Cada tabla del aplicativo necesita su política de aseguradora. Veintiuna
unidades van a escribir tablas detrás de esta, así que la forma que se elija
ahora se repite veintiuna veces.

A. **Cada migración escribe su política, con el mismo patrón literal**
   (recomendada): tres líneas de SQL explícito por tabla, iguales salvo el
   nombre. Se lee entera en la revisión de la migración, sin saltar a otro
   archivo, y quien añada una tabla copia el patrón de la anterior. La aserción
   comprueba el catálogo vivo, así que no depende de cómo se escribió
B. **Una función compartida que cada migración invoca**: una sola definición del
   patrón y migraciones de una línea. A cambio, leer una migración ya no dice
   qué política quedó: hay que ir a la función, y una función que cambie altera
   en silencio el aislamiento de tablas escritas hace meses
X. Other (please specify)

[Answer]: A

## Q2 — Qué hace el proceso si la aserción de aislamiento no se puede ejecutar al arrancar

La aserción corre en el guion de verificación y **al arrancar el proceso**. El
caso a decidir es el arranque con la base caída o inalcanzable: la aserción no
dice que falle, dice que no pudo ejecutarse.

A. **El proceso no arranca y lo dice** (recomendada): arrancar sin haber podido
   comprobar el aislamiento es exactamente el estado en el que una fuga pasa
   desapercibida. El aplicativo es una demostración que se despierta sola, así
   que reintentar y arrancar cuando la base responda es la conducta normal, no
   una caída
B. **Arranca y se declara no sano hasta que la aserción pase**: la superficie
   pública responde antes, con un estado honesto, y el chat en tier gratuito
   podría seguir vivo. A cambio, existe una ventana en la que el proceso está
   arriba sin haber verificado el aislamiento, y esa ventana es justo la que
   NFR10 existe para que no exista
X. Other (please specify)

[Answer]: A
