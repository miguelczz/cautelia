# Preguntas — Requisitos de calidad de U4 `case-record`

Esta etapa tiene una sola decisión pendiente de verdad, pero es grande y lleva
año y medio de documentos apuntando a ella: **el cifrado en reposo de los campos
del caso**. Tres documentos aprobados se la asignan por nombre a esta etapa —la
tabla de preguntas abiertas de Incepción (PA-8), el contrato C-12 y el propio
diseño funcional de U4— y ninguno dice qué mecanismo.

Todo lo demás de la etapa se deduce de documentos aprobados y se resuelve sin
preguntar: qué requisitos de calidad hereda U4, cuáles registra como propios,
qué comandos los miden y qué controles los sostienen.

---

## Q1 — Con qué mecanismo se cifra en reposo

Lo que está establecido, con su archivo:

- El PRD lo pide: *"el caso guarda los datos personales que la operación
  necesita, cifrados en reposo y bajo RLS; lo que sale a trazas, logs y evals va
  redactado"* (`docs/specs/prd.md`).
- No es lo mismo que la redacción. U3 dejó escrito como regla que **los campos
  del caso no se redactan**: guardan el dato en claro con la protección que fije
  la tabla de almacenes. Si esta etapa no fija el mecanismo, esos campos quedan
  sin ninguna protección propia más allá del aislamiento por aseguradora.
- El presupuesto es de 5 USD en noventa días, y todo lo demás en plan gratuito o
  auto-hospedado. Eso descarta cualquier servicio de gestión de claves de pago.
- No hay proveedor de hospedaje elegido: sigue siendo pregunta abierta delegada
  al intent `infra`. Así que **no se puede apoyar la decisión en el cifrado de
  disco del proveedor**, porque no hay proveedor cuyo cifrado nombrar ni comando
  que produzca su valor real.
- La biblioteca `cryptography` ya es dependencia directa del backend, fijada por
  una auditoría de seguridad. Cifrar desde el aplicativo no añade dependencia
  nueva.
- Nada en el repositorio menciona hoy `pgcrypto`, KMS, AES ni Fernet como
  decisión del proyecto. Lo que hay son guías genéricas del framework.

- A. **Cifrar desde el aplicativo, con la biblioteca que ya está.** La clave sale
  de una variable de entorno, separada por uso como las otras dos que ya existen.
  Se comprueba con un comando: se siembra un caso, se lee la columna cruda por el
  punto único de sesión y se exige que el valor sembrado no aparezca. Su costo
  real, que hay que nombrar: una columna cifrada así no se puede filtrar ni
  ordenar en SQL. Además, el intent `infra` recibe el encargo de exigir cifrado
  de almacenamiento al proveedor de base que elija.
- B. **Cifrar dentro de la base, con `pgcrypto`.** También cuesta cero y es la
  lectura más literal de "cifrado en reposo" en PostgreSQL. Pesa en contra: no
  está comprobado que la imagen anclada traiga esa extensión, y la clave viaja
  hacia el proceso de la base en cada sentencia, es decir, hacia el mismo sitio
  que se quiere proteger.
- C. **Declararlo fuera de esta versión, con su razón.** El argumento existe: un
  caso de visitante real vive como mucho hasta el reinicio de esa noche, y el
  corpus es sintético. Pero contradice al PRD y al catálogo de componentes, que
  dicen "cifrado en reposo", así que la razón escrita tendría que enmendar esos
  dos documentos en vez de ignorarlos.
- X. Other (please specify)

[Answer]: A

---

## Q2 — Qué se cifra

Si la respuesta a Q1 es A o B, falta decir sobre qué columnas. Los datos
personales del caso viven en tres sitios distintos:

1. **Los atributos de las otras partes**: nombre, contacto y placa del otro
   conductor, del testigo o del lesionado. Son dato personal libre, tecleado o
   dictado, de gente que ni siquiera es el asegurado.
2. **Los valores de los campos del caso**: la descripción de lo que pasó, el
   lugar y las lesiones. También son dato personal, y también van en claro.
3. **La transcripción**: ya va redactada por construcción, así que el dato
   sensible ya no está dentro.

- A. **Los dos primeros**: atributos de las otras partes y valores de los campos
  del caso. La transcripción no, porque ya va redactada y cifrar lo que ya está
  tapado añade costo sin añadir protección.
- B. **Solo los atributos de las otras partes.** Es el dato de terceros que no
  dieron su consentimiento, y el más acotado. Los campos del caso se quedan en
  claro bajo aislamiento.
- C. **Los tres**, transcripción incluida, por uniformidad.
- X. Other (please specify)

[Answer]: A
