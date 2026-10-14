# Preguntas — Diseño funcional de U2 `tenancy`

Segunda unidad: aseguradoras e identidad. Es el módulo del que depende todo lo
demás, porque es el único que abre sesiones de base de datos y el único que
decide quién ve qué. Este documento diseña **qué hace**, no cómo se programa:
entidades, reglas de negocio y comportamiento.

**Fuentes consumidas.** `../../../inception/units-generation/unit-of-work.md`
(qué contiene y qué no contiene U2),
`../../../inception/units-generation/unit-of-work-story-map.md` (sus dos
historias: US4.11 y US5.7),
`../../../inception/requirements-analysis/requirements.md` (FR8.7, FR9.1 a
FR9.6, NFR10), `../../../inception/domain-design/components.md` (el componente
`TenantIdentity` y sus entidades `Tenant`, `StaffPrincipal`, `CaseAccessLink` y
`VisitorKey`) y `../../../inception/contract-design/contract-summary.md` (los
contratos C-07 acceso por enlace firmado, C-10 sesión con la aseguradora fijada,
C-11 borrado de datos de visitante, C-25 configuración por aseguradora y C-30
migraciones).

Casi todo lo fijan documentos aprobados y lo aplico sin preguntar: las tres
aseguradoras y sus personas, el identificador legible de aseguradora, la lectura
de la variable de sesión con `NULLIF`, el rol de aplicación que no puede saltarse
el aislamiento, las tres cookies y sus atributos, la respuesta idéntica ante un
caso ajeno y uno inexistente, la vida de una hora del enlace, que las
credenciales nunca se publican, y que la revisión que crea una tabla trae su
aislamiento en la misma revisión.

Quedan **cinco decisiones de comportamiento** que ningún documento aprobado
resuelve y que cambian lo que se construye.

## Q1 — De dónde saca la aserción de esquema la lista de tablas que debe revisar

AC4.11.1 exige que la aserción falle si **alguna** tabla del aplicativo carece de
la política de aislamiento, incluidas las que agreguen las otras veinte
unidades. Para poder fallar, primero tiene que saber qué tablas existen.

A. **Del catálogo vivo de PostgreSQL** (recomendada): la aserción le pregunta a
   la base qué tablas hay en el esquema del aplicativo y exige de cada una las
   tres cosas —aislamiento habilitado, aislamiento forzado y al menos una
   política de aseguradora—. Una tabla que cree cualquier unidad futura queda
   cubierta el día que nace, sin que nadie tenga que acordarse de nada. Lleva una
   lista de exclusión versionada y corta (la tabla de versiones de migraciones),
   donde cada entrada escribe su razón
B. **De una lista declarada en la configuración**: la aserción compara contra un
   archivo con los nombres de tabla esperados. Es explícito y se lee de un
   vistazo; a cambio, una tabla nueva solo se revisa si alguien se acordó de
   añadirla a la lista, y una tabla que nadie añadió pasa la compuerta en verde
   sin estar aislada
C. **De las revisiones de migraciones**: leer los archivos de migración para
   deducir las tablas. No hay que mantener nada, pero comprueba lo que el archivo
   dice y no lo que la base tiene, que es distinto en cuanto algo se aplica a
   medias
X. Other (please specify)

[Answer]: A

## Q2 — Cuánto dura una credencial de la bandeja

AC5.7.1 pide que la credencial firmada lleve aseguradora, rol y **caducidad**,
pero ningún documento fija el número. Son credenciales para ti, el despliegue
local y las pruebas; se emiten con un comando y nunca se publican.

A. **Doce horas desde que se emite** (recomendada): cubre una sesión de trabajo o
   una demostración completa sin volver a emitir, y una credencial que se escape
   muere el mismo día. El comando de emisión es un solo paso, así que renovar no
   cuesta nada
B. **Hasta el siguiente reinicio nocturno**: la credencial nunca sobrevive a los
   datos que abre, que es más limpio conceptualmente; a cambio, una emitida a las
   11 de la noche dura diez minutos y la que se emite a primera hora dura un día
   entero, así que su vida es impredecible justo cuando la estás enseñando
C. **Treinta días**: cómodo para el desarrollo local y el peor comportamiento que
   puede ver quien evalúe el repositorio, porque una credencial filtrada vive un
   mes
X. Other (please specify)

[Answer]: A

## Q3 — Si el enlace firmado de un caso se puede canjear más de una vez dentro de su hora

El contrato C-07 dice que la pantalla lee el token del fragmento, lo canjea y
limpia la dirección. Lo que no dice es qué pasa si el visitante cierra la
pestaña y vuelve a abrir el mismo enlace diez minutos después.

> **Corrección del 2026-09-20, después de la revisión.** Este encuadre estaba
> mal: presenté la pregunta como nueva cuando CD-5 de Contract Design, una de
> las siete decisiones que respondió Miguel, ya decía "el enlace firmado se
> canjea una vez". El revisor lo señaló y tenía razón. La pregunta se le volvió
> a plantear a Miguel con CD-5 delante, y su respuesta fue que esa frase
> describe el transporte —un canje por carga de pantalla— y no un token de un
> solo uso. La respuesta `A` de abajo queda confirmada con ese contexto, y la
> aclaración está escrita en `contract-summary.md`, en la fila CD-5 y en C-07.

A. **Reutilizable mientras no caduque** (recomendada): el token vale hasta su
   hora, y cada canje entrega una cookie nueva limitada a ese caso. El visitante
   que cierra la pestaña por accidente vuelve a entrar. La ventana de riesgo ya
   está acotada por la hora, y la revocación sigue disponible cuando haga falta
B. **Un solo canje**: el primer canje quema el token. Es más estricto ante un
   enlace que se filtre; a cambio, recargar la página deja fuera al visitante con
   un "enlace vencido" que, para quien está evaluando la demostración, se lee
   como un error nuestro y no como una medida de seguridad
C. **Reutilizable con un tope de canjes**: intermedio, y añade un contador y un
   caso de prueba por un beneficio que la hora de vida ya da
X. Other (please specify)

[Answer]: A

## Q4 — Qué decide qué puede hacer cada rol

AC5.7.3 exige que Priya Raman, con rol de agente de cuenta, no pueda aprobar ni
rechazar un caso, ni desde la pantalla ni con una petición directa. Hace falta
decidir dónde vive esa regla.

A. **Una tabla de permisos versionada, por rol y acción** (recomendada): una sola
   tabla dice qué acciones puede hacer cada rol, y cada fila es un caso de prueba.
   Un rol nuevo o una acción nueva se ven en un solo lugar, y una acción que
   nadie declaró se deniega por defecto
B. **En la carpeta de configuración de cada aseguradora**: sería coherente con la
   regla de que las diferencias entre aseguradoras viven en su carpeta, pero los
   permisos no son una diferencia entre aseguradoras: ponerlos ahí dejaría que
   una aseguradora se conceda a sí misma la aprobación, y eso contradice que la
   decisión la firme una persona con el rol adecuado
C. **Una comprobación en cada ruta que lo necesite**: directo de leer en cada
   sitio, y sin un lugar único es cuestión de tiempo que una ruta nueva se olvide
   de comprobarlo
X. Other (please specify)

[Answer]: A

## Q5 — Qué pasa cuando se pide una sesión para una aseguradora que no existe

C-10 ya fija un caso: una sesión **sin** aseguradora fijada no devuelve ninguna
fila, nunca las de otra. Falta el caso distinto: alguien pide una sesión para un
identificador de aseguradora que no está en la configuración.

A. **Falla en el acto, antes de abrir la transacción** (recomendada): una
   aseguradora inexistente es un error de quien llama, no un resultado vacío.
   Fallar en el punto único hace imposible que un módulo consulte la nada
   indefinidamente creyendo que no hay datos. La respuesta hacia afuera sigue
   siendo la misma que para un caso ajeno, así que no revela nada
B. **Devuelve una sesión sin aseguradora fijada**: es consistente con la regla de
   "sin aseguradora, ninguna fila", pero convierte un error del código en "no hay
   datos", que es exactamente la confusión que el proyecto prohíbe entre "no hay
   cláusula" y "no pude verificar"
X. Other (please specify)

[Answer]: A
