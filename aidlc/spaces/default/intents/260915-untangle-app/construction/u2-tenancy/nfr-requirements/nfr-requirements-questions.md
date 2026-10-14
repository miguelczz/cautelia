# Preguntas — Requisitos de calidad de U2 `tenancy`

U2 es la unidad de seguridad del proyecto: es la única que abre sesiones de base
de datos y la única que decide quién ve qué. Esta etapa fija sus **objetivos
medibles**, cada uno con su valor esperado y el comando que produce su valor
real, para que aparezcan como fila propia en la matriz de verificación final.

**Alcance de esta etapa para U2.** La unidad está declarada de tipo `library`,
así que el contrato de la etapa solo pide dos documentos: requisitos de
seguridad y decisiones de stack. Los de rendimiento, escalabilidad, fiabilidad y
observabilidad los piden las unidades de tipo `service`, y a U2 no le aplican.

**Fuentes consumidas.** `../functional-design/functional-spec.md` (los siete
flujos), `../functional-design/rules.md` (las veintisiete reglas, y en
particular BR1.2, BR1.7, BR2.2, BR2.4 y BR3.5),
`../../../inception/requirements-analysis/requirements.md` (FR9.1 a FR9.6 y
NFR10, que es compuerta dura),
`../../../inception/contract-design/contract-summary.md` (C-07, C-10, C-11,
C-25, C-30) y `../../../../codekb/untangle/technology-stack.md`.

Casi todo lo fijan documentos aprobados y lo aplico sin preguntar: el
aislamiento en la base y no solo en el código, el rol sin privilegio de salto,
la caducidad de doce horas, el enlace de una hora reutilizable, el rechazo
indistinguible, los secretos leídos del entorno con claves separadas por uso, y
que cero fuga entre aseguradoras es compuerta dura sin promedio ni excepción.

Quedan **cuatro decisiones** que ningún documento aprobado resuelve.

## Q1 — Una clave de firma o una por uso

La regla del proyecto exige claves separadas por uso, y nombra tres: voz, chat y
evaluaciones. No nombra estas dos, que son de U2: la que firma las credenciales
de la bandeja y la que firma los enlaces de caso.

A. **Una clave por uso, dos en total** (recomendada): quien obtenga la clave de
   los enlaces puede abrir casos cuyo identificador ya conozca; quien obtenga la
   de la bandeja puede fabricarse una credencial de ajustador en cualquier
   aseguradora. Son radios de daño muy distintos y separarlas los mantiene
   separados. Cuesta una variable de entorno más
B. **Una sola clave con un campo que distinga el uso**: menos variables que
   manejar, y el campo impide que un enlace se presente como credencial de
   bandeja. A cambio, una sola filtración da las dos capacidades a la vez
X. Other (please specify)

[Answer]: A

## Q2 — Qué se registra cuando alguien intenta entrar con una credencial ajena

Hacia afuera, una credencial caducada, una alterada y una de otra aseguradora
responden exactamente igual y no dicen cuál fue (BR2.4). Eso es deliberado.
Hacia adentro hace falta decidir qué queda escrito.

A. **Un evento estructurado con la aseguradora que se intentó abrir, el rol que
   afirmaba la credencial y la causa real del rechazo** (recomendada): una fuga
   entre aseguradoras que no deje rastro es indetectable, y el identificador de
   aseguradora no es un dato personal. El evento sale por el punto único de
   salida, como todo lo demás
B. **Solo un contador por causa, sin identificadores**: dice que pasó, no contra
   quién. Sirve para una alarma y no sirve para investigar
X. Other (please specify)

[Answer]: A

## Q3 — Qué pasa con lo firmado cuando se rota una clave de firma

Una clave que llegue a un commit se rota en el proveedor: es regla del proyecto
y no se discute. Lo que falta decidir es qué pasa con lo que ya estaba firmado
en el momento de rotar.

A. **Rotar invalida en el acto todo lo firmado con la clave anterior**
   (recomendada): las credenciales duran doce horas y los enlaces una, así que
   el costo real es volver a emitir con un comando. Cero código extra, y una
   clave comprometida deja de servir en el instante en que se rota
B. **Ventana de gracia: se acepta también la clave anterior durante un rato**:
   nadie pierde su sesión al rotar, a cambio de una variable de entorno más, una
   rama de verificación más y —lo importante— de que una clave comprometida siga
   valiendo durante esa ventana
X. Other (please specify)

[Answer]: A

## Q4 — Con qué se firman las credenciales y los enlaces

Decisión de stack, así que la miro con el criterio que ya fijaste: la forma
documentada por el proyecto oficial del ecosistema antes que la opción mínima.
El stack es Python con FastAPI.

A. **PyJWT para la credencial de la bandeja y firma propia con la biblioteca
   estándar para el enlace de caso** (recomendada): el tutorial de seguridad de
   la documentación oficial de FastAPI usa PyJWT, así que es lo que reconoce
   quien evalúe el repositorio, y la credencial de bandeja es exactamente el
   caso de uso para el que existe. El enlace de caso no necesita un formato
   estándar —nadie externo lo interpreta, se busca su fila por el resumen del
   token— así que ahí una firma con la biblioteca estándar es menos superficie y
   menos dependencia
B. **PyJWT para las dos cosas**: un solo mecanismo, un solo juego de pruebas. A
   cambio, el enlace lleva una carga útil legible que no necesita, y el token
   del fragmento se hace más largo de lo que hace falta
C. **Biblioteca estándar para las dos cosas**: cero dependencias nuevas, y
   pierde el formato que cualquiera reconoce en la credencial de bandeja
X. Other (please specify)

[Answer]: A
