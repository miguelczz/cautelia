# Preguntas — Diseño funcional de U4 `case-record`

U4 es el registro del caso: qué campos tiene un siniestro, en qué estado está
cada uno, qué turno lo respalda y por qué transiciones puede pasar. De él
cuelgan siete unidades posteriores, así que lo que se decida aquí no se cambia
barato.

Casi todo está decidido. El esquema de siete campos lo fija FR1.1, los siete
estados y la única vuelta atrás los fija ADR-005, los cinco adjuntos los fija
FR1.7 y la superficie que ofrece la unidad la fija el contrato C-12. Estas
cuatro preguntas son los huecos que quedaron: cada una tiene dos respuestas
legítimas y cada una cambia algo que se ve.

---

## Q1 — Con qué prefijo se escribe el número de caso

FR1.5 y ADR-005 piden "el prefijo de la aseguradora y seis dígitos", y la
agente lo dicta dígito a dígito al cerrar. Ninguno de los dos dice **cuál** es
ese prefijo; lo único escrito está en las maquetas, que usan `SMU-482913` para
Stonecroft Mutual y `SMA-731045` para Sunmeadow Auto.

El problema es que `SMU` y `SMA` se diferencian en una sola letra y nombran a
dos aseguradoras distintas. Dictados por teléfono suenan casi igual, y el propio
diseño de la voz reconoce ese riesgo: la guía obliga a deletrear con una palabra
las letras que se confunden. Además el número de póliza quedó en `POL-100042`
—seis dígitos también—, así que un caso `SMU-482913` y una póliza `POL-100042`
se parecen lo bastante como para que alguien dicte uno creyendo dictar el otro.

- A. Tres letras que no chocan: `STO-482913` (Stonecroft), `SUN-731045`
  (Sunmeadow), `KNO-118844` (Knotwell). Mantiene la forma que pide FR1.5 y
  quita la colisión; las maquetas se corrigen cuando se construya la interfaz.
- B. Dejar las de las maquetas: `SMU-`, `SMA-`, `KIA-`. Ningún documento se
  toca, y la colisión se asume.
- C. El nombre de la aseguradora escrito y seis dígitos: "Stonecroft 482913".
  Nadie tiene que descifrar nada, pero deja de ser un código de ancho fijo y
  se alarga en pantalla y en voz.
- X. Other (please specify)

[Answer]: A

---

## Q2 — Qué cuenta como campo completo en la cifra de completitud

FR1.3 pide "completitud por campo y total", y AC4.10.3 exige que un siniestro
con cinco de sus siete campos dé exactamente 5/7. Por separado, ADR-005 dice que
cada campo tiene tres estados —no dicho, dicho y confirmado en voz alta— y que
**solo tres campos** exigen confirmación antes de anotarse: lesiones, conductor
y lugar.

Lo que nadie decidió es si un campo que la persona dijo pero que no se leyó en
voz alta cuenta en esa cifra. La diferencia se ve: es el número que aparece en
la barra de completitud y el que decide si un caso se cierra o queda a medias.

- A. Cada campo cuenta cuando alcanza el estado que **su propio campo** exige:
  confirmado para lesiones, conductor y lugar; dicho para los otros cuatro.
  Es lo único que hace verdaderas a la vez a ADR-005 y a AC1.8.4.
- B. Solo cuentan los confirmados. Cifra más estricta, pero obligaría a leer en
  voz alta los siete campos, que es justo lo que ADR-005 decidió no hacer.
- C. Cuentan dicho y confirmado por igual, y la confirmación se reporta aparte
  como una segunda cifra.
- X. Other (please specify)

[Answer]: A

---

## Q3 — Qué estado toma un campo que corrige el ajustador desde la bandeja

Los tres estados del campo describen lo que dijo el asegurado. FR1.6 y el
historial de cambios, en cambio, permiten que una persona de la aseguradora
corrija un campo desde la bandeja, con su nombre y su marca de tiempo. Nadie
dijo en qué estado queda ese campo, ni qué es su evidencia: un campo corregido
no tiene turno que lo respalde.

- A. Queda confirmado, y su evidencia deja de ser un turno y pasa a ser la
  entrada del historial con el nombre de quien lo escribió. Una persona
  identificada que teclea un valor es la evidencia más fuerte que hay.
- B. Conserva el estado que tenía y solo cambia el valor. El historial guarda
  quién lo tocó, pero la cifra de completitud no se mueve.
- C. Un cuarto estado, "corregido", distinto de los tres del asegurado. Es el
  más explícito y el más caro: todo consumidor del caso tendría que tratarlo.
- X. Other (please specify)

[Answer]: A

---

## Q4 — Si los cinco adjuntos se exigen para cerrar cualquier tipo de registro

FR1.7 dice que el caso adjunta transcripción, cláusulas citadas, reglas
disparadas con sus insumos, identificador de traza y resultado de los controles,
y que "falta cualquiera y el caso no se puede cerrar". Leído al pie de la letra,
una consulta de cobertura que no disparó ninguna regla nunca podría cerrarse,
porque le faltaría uno de los cinco.

- A. Los cinco se exigen siempre, y un conjunto **vacío cuenta como presente**:
  "ninguna regla disparó" es un valor, distinto de "no se evaluaron las reglas".
  Es la misma distinción que la convención 8c del equipo ya obliga a mantener
  entre "no hay cláusula" y "no pude verificar".
- B. Los cinco se exigen solo al siniestro; la consulta de cobertura y la
  solicitud de cotización cierran con los adjuntos que su tipo puede tener.
- X. Other (please specify)

[Answer]: A
