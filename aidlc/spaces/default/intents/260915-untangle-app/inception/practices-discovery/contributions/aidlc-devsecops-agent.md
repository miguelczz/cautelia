**Collaborator:** aidlc-devsecops-agent

## Contribution

Reviso lint como control, análisis estático y dinámico, escaneo de secretos y de
dependencias, y cadena de suministro. El borrador es sólido en **reglas** y
delgado en **controles**: casi todo lo que promete depende de que una persona se
acuerde, y esa persona es la única del equipo. Mi contribución es convertir lo
que ya está escrito en cosas que fallan solas, sin añadir un programa de
seguridad que nadie puede pagar.

Cada recomendación va marcada **[imprescindible]** o **[deseable]**. Nombro la
obligación y no la herramienta salvo donde el PRD ya decidió (Presidio, RLS en
Postgres) o donde la herramienta es indiferente al ADR de lenguaje.

---

### 1. El hueco estructural: no hay dónde colgar un control hasta la semana 3

Este es el hallazgo que cambia más cosas del borrador, y está implícito en su
propia evidencia sin que nadie saque la consecuencia.

Todos los controles del borrador terminan en "en CI antes del merge". CI no
existe y no existirá hasta el intent `infra` (D-014, semanas 3 y 4). El
calendario del PRD 11.5 pone en las **semanas 1 y 2** exactamente el código donde
la seguridad importa más: tenants con RLS, emisor de tokens, esquema del caso,
motor de reglas, verificador, DS-1 y DS-8. Es decir: **el código con mayor
superficie de riesgo se escribe entero antes de que exista la compuerta que
debía protegerlo**, y la práctica afirmada no dice nada sobre ese tramo.

La solución ya está medio decidida en el plan y no cuesta nada: `docs/PLAN-AIDLC.md`
paso 8 menciona `pre-commit`, y su punto 4 ("Verificación = generación") ya exige
`scripts/verify.sh` obligatorio antes de declarar done. Hoy no existe ninguno de
los dos (verificado: sin `scripts/`, sin `.pre-commit-config.yaml`, sin `.github/`).

**Propuesta concreta [imprescindible]** — añadir a `## Way of Working` de
`team-practices.md`:

> Los controles automáticos viven en **un solo script**, `scripts/verify.sh`, que
> corre idéntico en la máquina y en CI. Se crea en el mismo Bolt que el primer
> código de aplicación, antes de que exista CI, y el intent `infra` lo **invoca**
> en lugar de inventar un segundo juego de chequeos. Orden de ejecución: escaneo
> de secretos, formato, lint (incluidas sus reglas de seguridad), chequeo de
> tipos, pruebas deterministas, aserciones de esquema (RLS), chequeos de
> contenido, auditoría de dependencias. Cualquier paso en rojo devuelve un código
> distinto de cero.
>
> Mientras CI no exista, la compuerta es local: `verify.sh` en verde es condición
> para declarar done, y `pre-commit` corre su subconjunto barato (secretos,
> formato, lint) en cada commit. Cuando CI exista, **CI es la compuerta
> autoritativa**: el hook local es conveniencia, no garantía, porque
> `--no-verify` lo salta.

Esto no añade ceremonia: reemplaza una lista de intenciones por un archivo, y
hace que la promesa "corre en CI" siga siendo cierta durante las dos semanas en
que no hay CI.

---

### 2. Escaneo de secretos: la ausencia más grave del borrador

El borrador tiene la regla ("ALWAYS leer secretos desde variables de entorno o un
gestor de secretos") y **ningún control que la verifique**. El `.gitignore` con
`.env` y `.env.*` evita que se suba un archivo llamado `.env`; no evita nada de
lo que de verdad pasa: una clave pegada en un archivo de código, en un fixture,
en un `docker-compose.yml`, en un notebook de exploración o en un ejemplo del
README.

El argumento que hace esto **imprescindible y urgente**, no "bueno tenerlo": por
D-017 el repositorio es privado **hoy** y en la semana 12 se decide si se hace
público. El historial de git es permanente. Una clave commiteada en la semana 2
queda expuesta en la semana 12 salvo que se reescriba el historial, que a esas
alturas es una operación cara y arriesgada. El costo de prevenir es un hook; el
costo de remediar es rehacer el historial de todo el proyecto y rotar todo.

**Propuesta concreta [imprescindible]** — añadir a `## Mandated` de
`discovered-rules.md`:

> - ALWAYS correr un escáner de secretos sobre lo que se va a commitear y sobre
>   el historial completo, desde antes del primer commit de código de aplicación;
>   un hallazgo bloquea el commit y el merge. La herramienta es
>   independiente del lenguaje (`gitleaks` o `detect-secrets` vía `pre-commit`,
>   ambos gratuitos), así que no espera al ADR de `domain-design`. *(D-017 —
>   repositorio candidato a público en la semana 12; guardarraíl de
>   `phases/construction.md`)*

**Propuesta concreta [imprescindible]** — añadir a `## Forbidden`:

> - NEVER "arreglar" una clave filtrada borrándola del archivo: una clave que
>   llegó a un commit se considera comprometida y **se rota en el proveedor**
>   antes de cerrar el incidente. *(D-015 — el tope de 5 USD no protege contra
>   una clave filtrada; el tope vive en el código y la clave filtrada se usa
>   fuera de él)*

**Tres complementos concretos:**

- **[imprescindible]** Cada clave de proveedor lleva su **propio tope o cuota
  configurado en el proveedor**, no solo el tope de la aplicación. El borrador
  ya separa claves por uso (voz, chat, evals), lo cual es correcto y me parece
  el mejor detalle de seguridad que tiene; lo que falta es el radio de daño: un
  límite en el código de Untangle no aplica a quien use la clave desde fuera.
  Con D-015 (5 USD en 90 días) esto no es teórico — una sola clave filtrada
  agota el presupuesto del proyecto entero.
- **[deseable]** El `.gitignore` actual ignora `.env.*`, lo que incluye
  `.env.example`. Eso impide versionar la plantilla de variables requeridas, que
  es justo lo que M17 ("comando único", README que asume cero contexto)
  necesita. Añadir la negación `!.env.example` y exigir que la plantilla liste
  **nombres** de variables, nunca valores.
- **[deseable]** El escáner corre también sobre el corpus y los golden sets: son
  archivos generados que se versionan y que nadie relee entero.

---

### 3. Cadena de suministro: el lockfile es necesario y no es suficiente

La regla del borrador ("ALWAYS crear el código de aplicación con manifiesto,
lockfile y toolchain fijados desde su primer commit") es correcta y la respaldo.
Le faltan cuatro piezas, todas gratuitas.

**[imprescindible] Integridad, no solo versión.** Un lockfile fija versiones;
fijar **hashes** fija contenido. Es barato en los dos lenguajes candidatos
(`pip`/`uv` con hashes, `npm ci` con `integrity`) y es lo único que protege
contra que una versión ya publicada cambie bajo los pies. Redacción propuesta
para `## Mandated`, reemplazando la regla existente:

> - ALWAYS crear el código de aplicación con manifiesto, lockfile **con hashes de
>   integridad** y toolchain fijado desde su primer commit; la instalación en CI
>   y en `verify.sh` usa el modo reproducible del gestor (el que falla si el
>   lockfile no coincide), nunca una resolución libre. *(TD-09; `dependencies.md`
>   riesgo 3)*

**[imprescindible] Escaneo de vulnerabilidades de dependencias.** No existe en el
borrador. La versión proporcionada y gratuita: alertas de Dependabot activadas en
el repositorio (funcionan en repos privados de cuenta personal) más el auditor
nativo del lenguaje (`pip-audit`, `npm audit`) como un paso de `verify.sh`.
Regla propuesta para `## Mandated`:

> - ALWAYS auditar las dependencias contra vulnerabilidades conocidas en cada
>   corrida de `verify.sh`; un hallazgo de severidad alta o crítica en una
>   dependencia que el aplicativo ejecuta bloquea el merge, y su excepción se
>   escribe con fecha y razón en el pull request. *(`dependencies.md` riesgo 3;
>   D-017)*

El matiz de "que el aplicativo ejecuta" es deliberado: con Presidio (que arrastra
modelos de spaCy), LangGraph y un framework de voz, el árbol transitivo será
grande y el ruido puede matar el control. Mejor un umbral defendible que un
chequeo que se desactiva en la semana 2.

**[imprescindible] Licencias, porque el repositorio va a ser público.** El
borrador cubre propiedad intelectual de contenido (ISO, ACORD, voces) y no cubre
la de **código**. Un repositorio de portafolio que se publica con una dependencia
copyleft fuerte es exactamente el problema de la familia R9 que el equipo ya
decidió que le importa. Ya hay precedente bueno en el repo: el glifo de Phosphor
se vendorizó con su `site/PHOSPHOR-LICENSE.txt`. Regla propuesta para
`## Mandated`:

> - ALWAYS registrar la licencia de cada dependencia de terceros y de cada
>   recurso (voces, modelos, fuentes) junto con la atribución que exija, y
>   rechazar la que impida publicar el repositorio. La lista se revisa una vez
>   antes de la decisión de publicar de la semana 12. *(R9, D-017, M17
>   "atribuciones"; precedente `site/PHOSPHOR-LICENSE.txt`)*

**[imprescindible] El modelo y el proveedor son cadena de suministro.** El
borrador menciona "versiones de proveedores y modelos fijadas" en la prosa de
`## Code Style` pero no lo convierte en regla, y ahí hay un hueco real: hoy un
cambio de modelo puede ser la edición de una variable de entorno, invisible para
la compuerta. P5 ya dice que las evals corren "en cada cambio de código, modelo o
proveedor". Regla propuesta para `## Mandated`:

> - ALWAYS declarar el identificador de modelo, el proveedor y sus parámetros en
>   configuración versionada; cambiarlos es un cambio de código que dispara la
>   compuerta de evals y se anota en el diff contra la línea base. *(P5, D-015,
>   M20)*

**[deseable] Techo a la superficie.** Una dependencia nueva de runtime se
justifica en una línea del pull request: qué hace, por qué no la biblioteca
estándar, licencia. No es burocracia si son dos renglones; con una persona y
90 días, cada dependencia es superficie permanente en un repo que se va a
publicar.

---

### 4. Análisis estático: separar el lint de estilo del lint de seguridad

El borrador dice "formatter y linter del lenguaje elegido ... corriendo en CI y
bloqueando el merge". Correcto, y le falta distinguir dos cosas que se comportan
distinto: un hallazgo de estilo es una molestia, un hallazgo de seguridad es una
compuerta dura.

**[imprescindible]** Redacción para `## Code Style`, a continuación del párrafo
del linter:

> El linter corre con su **conjunto de reglas de seguridad activado** (Bandit o
> las reglas `S` de Ruff en Python; `eslint-plugin-security` en Node). Un
> hallazgo de seguridad se trata como compuerta dura, no como advertencia de
> estilo: no se silencia con una supresión en línea sin una razón escrita al
> lado.

**[deseable]** Un SAST genérico y gratuito (`semgrep` con su registro público) es
lo que más valor daría para los patrones de inyección de SQL y de concatenación
de prompts, y es independiente del lenguaje. Lo marco deseable y no
imprescindible porque su valor real depende de que alguien triaje los hallazgos,
y aquí ese alguien es la única persona del equipo.

**Las dos reglas propias que valen más que cualquier herramienta comprada
[imprescindible]:**

1. **Nada de SQL construido por concatenación, y ningún acceso a base de datos
   que salte el fijador de tenant de la sesión.** RLS solo es tan fuerte como la
   variable de sesión que F9.1 exige fijar "antes de cualquier consulta". Una
   sola ruta que abra una conexión sin fijarla convierte el aislamiento en
   decorativo, y ni el test de aislamiento de una tabla ni el RLS de la base lo
   detectan: el test pasa porque la política existe, y la política no aplica
   porque la sesión no declaró tenant. Es un chequeo de lint o un grep de una
   regla.
2. **Un solo punto de salida para trazas y logs.** Ver la sección 6.

---

### 5. Convertir tres reglas "de memoria" en controles automáticos

Estas tres reglas del borrador son correctas y comparten el mismo defecto: todas
terminan en "y acompañar cada X nuevo con su prueba". Eso depende de que alguien
recuerde, y el propio mapa de fallos del PRD 12.2 nombra el olvido como
disparador ("Nuevo punto de salida sin redacción (log nuevo, exportación)").
Para cada una propongo el control que no depende de la memoria.

**5.1 Aislamiento [imprescindible].** La regla dice "acompañar cada tabla nueva
con su test de aislamiento". El control que no se olvida es una **aserción sobre
el esquema**: consultar el catálogo de Postgres y fallar si existe una tabla de
la aplicación sin RLS habilitado y sin política. Es una consulta, corre en
`verify.sh`, y cubre la tabla que nadie recordó. Añadir a la regla existente de
`## Mandated`:

> ... y una aserción automática sobre el esquema que falla si alguna tabla del
> aplicativo carece de RLS habilitado o de política de tenant. *(M9, F9.1, R8)*

**5.2 Redacción de datos personales [imprescindible].** La regla dice "en cada
punto de salida ... y cubrir cada punto de salida nuevo con su caso de prueba".
Invertir el control: en vez de enumerar salidas, **hacer que solo exista una**.
Un único exportador o sumidero de logs por el que pasa todo, con la redacción
dentro, y una regla de lint que prohíbe llamar al logger, a `print` o al
exportador fuera de ese punto. Así "un punto de salida nuevo sin redacción" deja
de ser posible por construcción en vez de ser detectable por disciplina. Y el
escaneo del segundo detector corre **sobre las trazas exportadas de cada corrida
de evals**, no solo como caso por caso — cosa que el PRD 12.2 ya especifica
("Operación: escaneo en cada corrida de evals") y que el borrador no recoge.

**5.3 Datos sintéticos [deseable, casi gratis].** La regla `NEVER incluir datos
de personas reales` no tiene detección. El control barato ya está prometido: F12.5
exige semilla y determinismo. Entonces el chequeo es **regenerar y comparar**:
cualquier archivo del corpus o de los golden sets que el generador no reproduzca
desde su semilla fue editado a mano o vino de fuera, y ese es exactamente el
caso que la regla quiere prohibir. Convierte P8 de promesa en prueba por el
precio de un `diff`.

---

### 6. El punto donde "datos 100% sintéticos" deja de ser cierto

Este es el hueco que más me preocupa y el borrador no lo menciona en ninguna de
sus tres piezas.

P8 y el borrador afirman que los datos son 100% sintéticos. M10 publica un **chat
web abierto en internet**, sin autenticación, donde escriben personas reales.
Desde el día que ese enlace existe, el sistema recibe texto libre de humanos que
pueden teclear su propio teléfono, su placa o su nombre — y eso no es sintético.
El PRD lo intuye (11.3 muestrea "10 sesiones anónimas por semana, ya
redactadas"), pero la práctica del equipo debe decirlo como regla dura, porque
cambia el régimen de tratamiento.

**Propuesta concreta [imprescindible]** — añadir a `## Mandated`:

> - ALWAYS tratar todo lo que entra por una superficie pública (chat en vivo,
>   formularios de demo) como dato personal potencialmente **real**: la redacción
>   se aplica **antes de persistir**, no solo antes de exportar, y la retención
>   está acotada por el reinicio de los datos de demo. El primer mensaje declara
>   que es una demostración con pólizas de ejemplo. *(M10, F8.7, P6, R7, R8)*

Y tres precisiones sobre los detectores, que son lo que sostiene RT-14 y RT-15:

- **[imprescindible] Los dos detectores deben ser de mecanismos distintos.** El
  borrador hereda del PRD "un segundo detector como control" sin decir que no
  puede compartir punto ciego con el primero. Si ambos son modelos de NER con
  los mismos reconocedores, fallan juntos y la compuerta `[bloquea]` de RT-14 no
  significa nada. Propuesta: Presidio como primario y un detector por
  **expresiones regulares sobre los formatos conocidos del generador** (placa,
  cédula, teléfono, número de póliza) como control independiente. El segundo es
  trivial de escribir precisamente porque MOD-12 genera los formatos.
- **[imprescindible] Reconocedores propios en los dos idiomas.** La cobertura por
  defecto de Presidio no incluye placa colombiana ni cédula, y su rendimiento en
  español no es el mismo que en inglés. RT-15 (ataque bilingüe) existe justamente
  para esto. La regla del borrador debe decir: la redacción se mide **por idioma
  y por tipo de entidad**, con la misma meta en los dos, y nunca como promedio
  (es la aplicación literal de P12 al control de seguridad).
- **[deseable]** Un caso de eval que verifique que la redacción no destruye el
  caso: el registro bajo RLS conserva los datos que la operación necesita (lo
  dice PRD 9, línea 793), y solo la salida va redactada. Una redacción demasiado
  agresiva rompe la funcionalidad y se descubre tarde.

---

### 7. Inyección de instrucciones: dar forma verificable al invariante

La regla del borrador —"ALWAYS tratar el texto del asegurado y del corpus como
dato y nunca como instrucción"— es la correcta y no es verificable tal como está
escrita: nadie puede mirar un diff y decir si se cumplió. La forma verificable es
estructural.

**Propuesta concreta [imprescindible]** — reemplazar esa regla por:

> - ALWAYS mantener el texto de origen externo (asegurado, corpus recuperado,
>   documento adjunto) **fuera de la posición de instrucción del prompt**: entra
>   siempre como campo delimitado del estado tipado, nunca concatenado al prompt
>   de sistema. La categoría y la derivación las deciden las reglas, no el
>   modelo, y la guardia de salida por turno corre sobre todo texto emitido antes
>   de publicarlo. *(RT-1, RT-2, RT-5, P3, F7.5)*

Así la revisión es leer una función, y la prueba es un caso de DS-6 por cada una
de las tres posiciones (entrada del asegurado, texto recuperado, campo del caso).

**[deseable] El corpus generado por un LLM es una fuente de inyección
indirecta.** F12.6 genera el corpus con el LLM y revisa "una muestra por idioma".
Ese corpus después alimenta el RAG, que es exactamente el vector de RT-2. El
control barato: el corpus pasa el mismo escaneo de patrones de instrucción que
cualquier entrada no confiable **antes de ingerirse**, no por muestreo.

---

### 8. RT-13 y la superficie pública: el control que protege el presupuesto

El borrador menciona "límite de mensajes por sesión y por día" como ítem del
checklist de día 2, dentro de `## Deployment`. Es el lugar equivocado para algo
que protege una restricción dura (D-015, 5 USD). Un checklist se cumple una vez;
esto tiene que ser una precondición de publicación.

**Propuesta concreta [imprescindible]** — añadir a `## Forbidden`:

> - NEVER publicar una superficie pública que invoque al LLM sin límite por
>   sesión, por origen y por día, sin el modo degradado probado y sin el tope
>   configurado también **en el proveedor**. El límite de la aplicación falla
>   abierto cuando lo que falla es la aplicación. *(RT-13, M20, D-015, R6, P9)*

Relacionado, y en la frontera con otro especialista: F8.7 ("credenciales
publicadas por tenant") es una **excepción deliberada** a la regla de secretos del
borrador, y tal como está la práctica se lee como contradicción —
`phases/inception.md` prohíbe arrastrar contradicciones sin resolverlas. Hay que
nombrarla: las credenciales de demo son públicas a propósito, son por tenant, no
sirven fuera de su tenant, no se reutilizan para nada más y se rotan en el
reinicio nocturno.

---

### 9. Análisis dinámico proporcionado: no compren un escáner

Para un proyecto de una persona con una sola superficie pública, un programa DAST
es un impuesto sin pagador. La versión proporcionada ya existe y es gratis:

**[deseable, pero de alto valor]** El set adversarial DS-6 se corre **contra el
despliegue vivo** en cada hito (semanas 6, 9 y 12), no solo contra el arnés
local, y al menos RT-4 (acceso a caso ajeno) y RT-14 (fuga por trazas) se
ejecutan siempre en esa modalidad. Razón: las fallas de aislamiento y de tokens
son tan a menudo errores de configuración del despliegue como errores de código,
y un test local contra una base de datos local no los ve. Es DAST en la única
forma que este proyecto necesita, y el material ya está construido para otra
cosa.

---

### 10. Correcciones concretas al borrador

**10.1 Los dos chequeos de contenido, tal como están redactados, fallan el día
uno [imprescindible].** Los verifiqué contra el repositorio actual:

- El chequeo de frases prohibidas ("cumple con" / "complies with" junto a NAIC,
  TCPA, EU AI Act, SOC 2, HIPAA) tiene **cinco coincidencias legítimas hoy**:
  `docs/specs/prd.md` líneas 460 y 639 (el principio P6 y la fila W3, que son el
  texto que *define* la prohibición), `docs/pre_prb/idea.md` línea 199, y los
  propios `discovered-rules.md` y `team-practices.md` del borrador.
- El chequeo de ausencia de texto ISO/ACORD toca **17 archivos**, todos
  legítimos, incluido `docs/reference/estructura-poliza-iso-pap.md`, que contiene
  a propósito los nombres de sección del formulario ("Insuring Agreement",
  "Part D – Coverage for Damage to Your Auto") y declara explícitamente que el
  texto del formulario no se copia.

Un chequeo que arranca en rojo se desactiva en la primera semana, y un chequeo
desactivado es peor que no tenerlo porque da falsa confianza. La corrección es de
redacción, no de diseño. Propuesta para `## Code Style`:

> Los tres chequeos de contenido se aplican sobre **el alcance que se publica**:
> código del aplicativo, `README.md`, copy del producto, `site/` y salidas del
> sistema. La especificación y los artefactos del flujo de trabajo (`docs/`,
> `aidlc/`), que contienen esas frases porque las prohíben, quedan excluidos por
> una lista de exclusiones **versionada**, donde cada entrada lleva su razón.
> Para ISO y ACORD el chequeo distingue **estructura** (nombres de sección y
> numeración, permitidos y documentados en
> `docs/reference/estructura-poliza-iso-pap.md`) de **texto de cláusula**, que es
> lo prohibido.

**10.2 "Sin secretos en el repositorio" es una afirmación sobre el presente, no
una propiedad [imprescindible].** `evidence.md` registra la línea base como "sin
secretos en el repositorio (`.env*` ignorados)". Es cierto y verifiqué que no
existe ningún archivo `.env` hoy. Sugiero que la evidencia añada la frase que
evita la mala lectura: *eso es cierto porque todavía no hay código que necesite
credenciales; deja de ser una garantía en el momento en que lo haya, y el
`.gitignore` no es el control que lo mantiene.*

**10.3 Falta una fila en la tabla de deuda que el borrador hereda [deseable].**
`code-quality-assessment.md` registra TD-01 a TD-10 y ninguna es de seguridad de
proceso. La ausencia de escaneo de secretos, de auditoría de dependencias y de
registro de licencias, en un repositorio que en la semana 12 puede volverse
público, es deuda de severidad alta para Construcción con el mismo rango que
TD-09. Vale la pena que `evidence.md` lo nombre para que quede trazado.

---

### 11. Lo que explícitamente **no** recomiendo

Lo escribo porque callar esto es cómo se cuelan los impuestos. Para un equipo de
una persona con 90 días y 5 USD, **no** recomiendo: SAST comercial ni DAST
automatizado; SBOM firmado ni atestación de procedencia (SLSA); firma de commits;
un modelado de amenazas STRIDE formal por componente; ni política de seguridad
escrita como documento aparte. El PRD ya contiene el modelado de amenazas útil
—RT-1 a RT-15 con conducta esperada y severidad— y duplicarlo en notación STRIDE
no añadiría un solo control. Lo que sí falta es lo barato: secretos,
dependencias, licencias, y el sitio donde correr los chequeos antes de que exista
CI.

## Positions

- AGREE: separar las claves de proveedor por uso (voz, chat, evals) — es el mejor detalle de seguridad del borrador y limita el radio de daño de una cuota agotada o una clave filtrada.
- AGREE: exigir RLS en la base de datos "y no solo en el código" con test por tabla — es la formulación correcta de M9 y la única que sobrevive a un error en la capa de aplicación.
- AGREE: nombrar la obligación y no la herramienta mientras el ADR de lenguaje no exista — mantiene la práctica escrita hoy y viva después del ADR, y los controles que propongo (secretos, dependencias, licencias) son igualmente independientes del lenguaje.
- AGREE: manifiesto, lockfile y toolchain desde el primer commit — es el momento correcto; introducir reproducibilidad después es rehacer trabajo.
- OBJECT: todos los controles del borrador se apoyan en "en CI antes del merge" y CI no existe hasta el intent `infra` (semanas 3 y 4), justo después de que se escriba el código de mayor riesgo (RLS, tokens, esquema, reglas) en las semanas 1 y 2 — hace falta `scripts/verify.sh` más `pre-commit` desde el primer Bolt, con CI invocando el mismo script después.
- OBJECT: no hay escaneo de secretos en ninguna de las tres piezas, solo la regla de leerlos del entorno — y por D-017 el repositorio puede hacerse público en la semana 12, así que una clave commiteada hoy queda expuesta permanentemente salvo reescritura del historial.
- OBJECT: el lockfile sin escaneo de vulnerabilidades, sin hashes de integridad y sin registro de licencias no es una práctica de cadena de suministro completa — y la licencia importa porque el repositorio es candidato a publicarse, lo cual es el mismo riesgo R9 que el equipo ya decidió que le importa.
- OBJECT: P8 afirma datos 100% sintéticos, pero M10 publica un chat abierto donde personas reales teclean texto libre — desde ese día entran datos personales potencialmente reales y la redacción debe aplicarse antes de persistir, no solo antes de exportar.
- OBJECT: las reglas de aislamiento y de redacción terminan en "acompañar cada X nuevo con su prueba", que depende de la memoria de la única persona del equipo — faltan los controles que no se olvidan: aserción de esquema que exige RLS en toda tabla del aplicativo, y un único punto de salida de logs y trazas con lint que prohíba escribir fuera de él.
- OBJECT: el segundo detector de datos personales se hereda del PRD sin exigir que sea de **mecanismo distinto** al primero, y sin reconocedores propios para placa, cédula y póliza en los dos idiomas — si ambos detectores comparten punto ciego, la compuerta `[bloquea]` de RT-14 no prueba nada, y RT-15 existe precisamente porque el punto ciego suele ser el español.
- OBJECT: los dos chequeos de contenido, tal como están redactados, arrancan en rojo — el de frases prohibidas coincide hoy con cinco archivos legítimos (incluido el PRD que define la prohibición) y el de ISO/ACORD con diecisiete; sin alcance de rutas y lista de exclusiones versionada, el chequeo se desactiva en la primera semana.
- OBJECT: el límite de mensajes del chat público está como ítem de checklist de despliegue cuando protege una restricción dura (el tope de 5 USD de D-015) — debe ser precondición de publicación y estar también configurado en el proveedor, porque un límite en la aplicación falla abierto cuando lo que falla es la aplicación.
- OBJECT: F8.7 publica credenciales de demo por tenant, lo que contradice literalmente la regla de secretos del borrador — `phases/inception.md` prohíbe arrastrar contradicciones sin resolverlas, así que la excepción debe nombrarse con sus límites (por tenant, sin alcance fuera de él, rotadas en el reinicio nocturno).
