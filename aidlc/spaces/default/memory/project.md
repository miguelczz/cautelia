# Project-Level Rules

> Project-specific specialisation and corrections. Loaded after `org.md` and
> `team.md` as strict-additive guidance; contradictions with broader policy
> are rejected. Populated by practices-discovery and the self-learning loop.
>
> Use sparingly: most teams don't need a project layer. Reach for it
> only when this specific project needs stable, durable guidance beyond the
> team practice (for example, package-specific release checks or an additional
> regression suite for a legacy component).

## Way of Working

<!-- Project-specific specialisation. Example: -->
<!-- This monorepo requires package-scoped branch names and a package owner -->
<!-- review in addition to the team's normal merge policy. -->

## Walking Skeleton

<!-- Project-specific specialisation. Example: -->
<!-- The walking skeleton must exercise the legacy service adapter as well -->
<!-- as the new service boundary. -->

## Testing Posture

<!-- Project-specific specialisation. -->

- Los criterios de aceptación se escriben en Gherkin con las palabras clave en español (Dado / Cuando / Entonces / Y), cada paso empieza con la palabra clave sin coma y ningún "Dado" depende de lo que dejó otro criterio: es el formato Given/When/Then de la regla de fase, Gherkin lo reconoce y las pruebas se automatizan sin traducirlo. (learned 2026-09-16) <!-- cid:260915-untangle-app:user-stories:af3a9b4b1ef2248ea9a9a654d17c19fd9351de3bde972547851dc2cd52bd1f12 -->

- Las unidades que realizan M8 sin conducta propia que evaluar (corredor de evaluaciones, reporte, respondedor simulado y compuerta) siguen en la rama evaluada, pero su caso previo es una corrida de casos ya existentes de DS-2, DS-3 o DS-6 que se comprueba que falla antes de implementarlas: no se inventa un caso de golden set artificial, y lo declaran en su campo Rama. (learned 2026-09-16) <!-- cid:260915-untangle-app:user-stories:6e4de8c23093742b362d79549e2996ff63d21ffd06325d98c2fd6cc893096bb3 -->

- Todo escenario de red-team (RT-1 a RT-15) necesita al menos un criterio verificable en el canal de texto, porque DS-6 corre por el adaptador de texto en cada entrega; un escenario cubierto solo en la voz queda fuera de esa compuerta y se comprueba solo por hito. (learned 2026-09-16) <!-- cid:260915-untangle-app:user-stories:24e59fe1b2cebc971a70a00da3479f4c5b33cd2f258f1536aa772d484c3dce5c -->

- Las pruebas de límites de gasto y de cuota no consumen el presupuesto que protegen: el tope en el proveedor se comprueba con una clave de prueba de tope mínimo y la aplicación detenida, y el techo de gasto con un acumulado forzado en pruebas, nunca llevando una clave real hasta su tope. (learned 2026-09-16) <!-- cid:260915-untangle-app:user-stories:82cc77e24362d9f92d04f6ea14f681f2aaa6b7626fde6c3a15a2beb4c6c85907 -->

- La primera unidad de la rama evaluada que realiza M8 sin conducta propia (el corredor de evaluaciones) no tiene casos existentes que correr: se construye con la rama determinista y su caso previo es la primera corrida de los casos que escriban las unidades siguientes; nunca se inventa un caso de golden set para ella. Decisión de Units Generation (U1), 2026-09-17. (learned 2026-09-17) <!-- cid:260915-untangle-app:units-generation:5e1642c4c4a8079630451bc2d5e53a11528e3de9963826a4adf20b720ef112bf -->

## Change Control

<!-- Project-specific. Mode: strict or relaxed. Strict here holds for every intent and cannot be changed from chat. -->

## Deployment

<!-- Project-specific specialisation. -->

## Code Style

<!-- Project-specific specialisation. -->

- El código nuevo lleva comentarios solo donde la razón no es obvia (una decisión, una regla de negocio con su identificador, un riesgo); no se imita la densidad de comentarios largos del código existente ni se repite en prosa lo que el código ya dice. Mientras trabaja, el agente corre solo las pruebas de lo que toca; en la máquina de Miguel no se corre la verificación en ninguna de sus formas —ni scripts/verify.sh, ni su versión rápida, ni la suite completa—: la verificación la hace GitHub Actions en cada entrega. Única excepción, aprobada por Miguel el 2026-10-13: una corrida al día de las pruebas del servidor, justo antes de la única subida a `main`, en un solo proceso y sin navegadores, porque dos rojos ese día gastaron 110 minutos de GitHub. Decisión de Miguel del 2026-09-21 para reducir tiempo y tokens sin bajar la calidad, enmendada el 2026-10-13 («no quiero esa verificación, ni liviana, ni completa ni de ninguna forma»). (learned 2026-09-22) <!-- cid:260915-untangle-app:code-generation:7b8b94d659b0e90dce931e5a8a0ccdacbd8576b8e1b87e12b3bbbf3f150ed74b -->

## Tech Stack

<!-- Technology choices locked for this project. -->

## Decided

<!-- Decisions made in earlier stages that should not be re-asked. -->
<!-- Format: DECIDED: [decision] (Stage [slug], [date]) -->

- DECIDED: el chat público y la vista de comparación corren en el plan gratuito de Gemini con un aviso, antes de cualquier texto del visitante, de no escribir datos reales; es un riesgo aceptado por Miguel (ADR-006) y no se vuelve a preguntar salvo que cambien las condiciones del proveedor. (Stage domain-design, 2026-09-17) (learned 2026-09-17) <!-- cid:260915-untangle-app:domain-design:22cd89751549793836f66bd22c9541bd35d2c1d4ee860a393f715224af54725b -->

- DECIDED: desde el 2026-09-21, Construcción corre en modo ligero por decisión de Miguel, para que el proyecto quepa en un plan Pro: sin revisión automática por etapa (review none), profundidad Minimal, y sin las etapas nfr-design e infrastructure-design (recompose --skip); lo que esas etapas fijaban para una unidad se decide en su plan de generación de código. Se conservan el diseño funcional y los requisitos de calidad en versión corta, las pruebas, el piso de cobertura del 80 %, verify.sh, GitHub Actions y los golden sets: ninguna compuerta baja. Se revierte con config set review, config set depth y recompose --add. (Stage functional-design, 2026-09-21) (learned 2026-09-21) <!-- cid:260915-untangle-app:functional-design:b53a1c77e7b042581e83eba47fc8b2a59a002a9133005dbfb73f2a39029c314b -->

- DECIDED: desde el 2026-09-21 (DP-14), cada unidad construye su núcleo —su conducta con sus pruebas— y difiere a la pasada de publicación lo que solo importa al publicar (límites públicos, topes en el proveedor, telemetría de uso, chequeo periódico, reinicio nocturno, paneles públicos, mediciones contra el despliegue en vivo, checklist del segundo día), con cada criterio en inception/delivery-planning/pasada-de-publicacion.md. U17, U20 y U22 van completas a esa pasada. Nunca se difiere una compuerta dura de lo construido, ni las pruebas, el piso del 80 % o verify.sh, y nada se publica antes de cerrar la pasada. Reemplaza, para lo que falta, la regla de construir cada pieza completa antes de la siguiente. (Stage functional-design, 2026-09-21) (learned 2026-09-21) <!-- cid:260915-untangle-app:functional-design:c6ff263418c3614570c8dbf8ff3af79cf387403991fc404be9584db90eaa98dd -->

- DECIDED: desde U9 (2026-09-21) el agente que escribe el código usa Sonnet aunque Miguel siga en el plan Max, porque el cuello de botella pasó a ser el límite semanal de uso; enmienda DP-13, que ataba el cambio a pasar a Pro. Las tandas son más cortas y la sesión principal revisa cada una antes de subirla; el diseño, el plan, la revisión y el diagnóstico siguen en la sesión principal. Ninguna compuerta, prueba, piso de cobertura ni práctica de calidad cambia: se reduce el costo, no el estándar. (learned 2026-09-22) <!-- cid:260915-untangle-app:code-generation:03011f5014a7ade65d4722c9def4bec811c61be130842b2f3085bed39bdfee0f -->

- DECIDED: desde el 2026-10-07, por decision de Miguel tras ver que el chat sonaba a contestadora, la respuesta del chat la dice con naturalidad un modelo (Claude Haiku 5.5, uso `chat_reply`, saldo prepagado de 5 USD sin recarga automatica) a partir de la frase del catalogo que el codigo ya eligio. El codigo sigue decidiendo que se dice; el modelo solo como se dice. Toda reformulacion pasa una comprobacion por codigo (`orchestration/natural_reply.acceptable`: conserva cifras, codigos y la pregunta, no agrega preguntas, cifras ni enlaces) y despues la guardia de salida; si falla, tarda mas de 3 s o la comprobacion la rechaza, sale la frase del catalogo. La voz, las frases de divulgacion y las de error siguen saliendo literales del catalogo. Enmienda, para el chat, la convencion de `team.md` de que todo texto visible sale del catalogo. (learned 2026-10-07)

- DECIDED: desde el 2026-10-07, por decision de Miguel ("todo como recomiendas" sobre `docs/propuesta-2026-10/03-propuesta-y-diseno.md`), la agente entiende la conversacion con un modelo y no por palabras clave: en el chat, Claude Haiku lee cada mensaje con el contexto del caso y devuelve una salida estructurada y cerrada (que quiere la persona, de un conjunto fijo de intenciones; los datos ya interpretados; la pregunta que hizo, si hizo una). El codigo valida esa salida contra el esquema del caso y sigue decidiendo que falta, cuando se cierra y cuando se deriva; ninguna transicion del grafo sale de texto libre del modelo. Las reglas por palabras quedan solo como respaldo cuando el modelo falla o tarda. Enmienda, para el chat, el "la categoria y la derivacion las deciden las reglas, no el modelo" de Mandated: el modelo propone la intencion como opcion cerrada y el codigo la valida. Las otras seis decisiones del mismo documento: mostrar las 6 polizas por aseguradora; limites en pesos colombianos multiplicando por mil; usted en todas las pantallas; el visitante sigue pudiendo decidir su caso en la demo, explicado como "en esta demo usted puede hacer de ajustador"; preguntas de cotizacion adaptadas a Colombia; orden fase 0, 1, 2, 3. La apertura del chat queda con el texto exacto de Miguel y sin la mencion del borrado nocturno, lo que modifica AC1.1.1. (learned 2026-10-07)

- DECIDED: desde el 2026-10-12, por decision de Miguel («me voy por tus recomendaciones») tras ver que el chat respondia sin coherencia (`docs/propuesta-2026-10/06-correcciones-2026-10-12.md`, seccion 4), la conversacion la lleva el modelo y no un guion: en cada turno del chat, y despues de la llamada, Claude recibe la conversacion completa y el estado del caso como datos delimitados, redacta el la respuesta y propone acciones de un conjunto cerrado (anotar datos, consultar la poliza, pasar a un ajustador, abrir otro caso, cerrar el reporte). El codigo valida cada accion contra el esquema y el estado del caso antes de ejecutarla, por las rutas del grafo que ya existen; ninguna transicion sale de texto libre. No cambia nada de lo que sostiene el codigo: toda respuesta pasa la guardia de salida, una cita solo sale de una clausula recuperada y verificada, la categoria y la derivacion al cerrar las deciden las reglas, la decision la firma un ajustador, y los datos personales se tapan antes de guardar. Las frases fijas quedan para la divulgacion, los limites, los errores, lo que la guardia sustituye y el cierre con su numero de caso. Si el modelo falla o tarda, el turno cae al recorrido por reglas de antes. Enmienda la decision del 2026-10-07 («el codigo decide que se dice; el modelo solo como») y, para el chat y la llamada, la convencion de `team.md` de que todo texto visible sale del catalogo. (learned 2026-10-12)

- DECIDED: desde el 2026-10-12, por decision de Miguel, la compuerta sigue en los servidores de GitHub y no en su Mac (la calienta y tarda): se sube a `main` como mucho una vez al dia, en una sola tanda, y antes se corren en local solo las pruebas de lo tocado. El gasto de minutos (unos 2.600 en doce dias de octubre, de 3.000) vino de subir varias veces por noche a 37 minutos cada una. El corredor propio queda documentado como opcion sin usar (`docs/reference/corredor-propio.md`). Acota, para el ritmo de subidas, el «entran directos a main» de `team.md`: sigue sin rama ni pull request. (learned 2026-10-12)

## Scope Overrides

<!-- Custom scope rules for this project. -->

## Forbidden

<!-- Populated by practices-discovery affirmation gate. -->
<!-- Format: NEVER [behavior] (affirmed [date]) -->
<!-- Example: NEVER throw exceptions across service layer boundaries (affirmed 2026-05-17) -->

- NEVER incluir datos de personas reales, ni texto de cláusula, formularios o specímenes de ISO o ACORD, en el repositorio o en el corpus: los datos son 100 % sintéticos y las pólizas son originales con estructura inspirada. *(P8, W6, R9)* (affirmed 2026-09-16)

- NEVER afirmar "cumple con" una norma (NAIC, TCPA, EU AI Act, SOC 2, HIPAA) en código, README, copy, landing o cualquier salida del sistema; se dice "inspirado en". *(P6, W3, R9)* (affirmed 2026-09-16)

- NEVER retirar un caso fallido de un golden set para mejorar una métrica, ni publicar una métrica sin su golden set, ni construir un set donde los casos fáciles sean mayoría. *(P5)* (affirmed 2026-09-16)

- NEVER bajar un umbral, relajar un piso de cobertura ni saltar una compuerta dura para que un paso pase. *(P5; `org.md` — "they may not be weakened to make a step pass")* (affirmed 2026-09-16)

- NEVER silenciar un hallazgo de seguridad del linter con una supresión en línea sin una razón escrita al lado. *(guardarraíl de `phases/construction.md`; PRD 12.2)* (affirmed 2026-09-16)

- NEVER hacer trabajo de verificación, de reglas o de cumplimiento dentro del turno de voz; ese trabajo va en el ritmo de fondo. *(P4, R2)* (affirmed 2026-09-16)

- NEVER dejar que un LLM decida con texto libre a qué nodo del grafo ir, ni ejecutar una acción sobre el caso fuera de una ruta del grafo, ni hacer que el grafo dependa del framework de voz. *(P3, M2, R10)* (affirmed 2026-09-16)

- NEVER escribir un `tenant_id` literal en el código del aplicativo fuera del cargador de configuración y de las fixtures, ni ramificar por tenant dentro del código de decisión: las diferencias entre tenants viven en su carpeta de configuración versionada, incluida la política de derivación siempre de la agencia. *(M5, M9, F9.2, F9.6, F6.3, P1)* (affirmed 2026-09-16)

- NEVER importar el SDK de un proveedor externo (STT, LLM, TTS, almacén vectorial) fuera de su adaptador, ni construir su cliente fuera de la fábrica que separa las claves por uso. *(P3, P9, M20, PRD 12.2)* (affirmed 2026-09-16)

- NEVER abrir una conexión a la base de datos fuera del punto único que fija el tenant de la sesión, ni construir SQL por concatenación. *(M9, F9.1, R8, PRD 12.2)* (affirmed 2026-09-16)

- NEVER escribir en un log, en una traza o en una exportación fuera del punto único de salida que aplica la redacción: un punto de salida nuevo sin redacción debe ser imposible por construcción, no detectable por disciplina. *(M6, P6, RT-14, PRD 12.2 — "Nuevo punto de salida sin redacción")* (affirmed 2026-09-16)

- NEVER publicar una superficie pública que invoque al LLM sin límite por sesión, por origen y por día, sin el modo degradado probado, y sin el tope configurado **también en el proveedor**: un límite que vive solo en la aplicación falla abierto cuando lo que falla es la aplicación. *(Q5, RT-13, M20, D-015, R6, P9)* (affirmed 2026-09-16)

- NEVER publicar el enlace en vivo de la voz antes de que `requirements-analysis` reconcilie con el PRD la promoción de `C5` y el tope de gasto: esta etapa afirma la condición de publicación, no el cambio de alcance. *(Q5, D-015, M20, PRD 8 clasificación `C5`; `phases/inception.md` — prohibido arrastrar contradicciones sin resolverlas)* (affirmed 2026-09-16)

- NEVER incurrir en un gasto que no esté escrito como excepción: el tope vigente es 40 USD a precio de lista en la ventana de 90 días que empieza el 2026-09-16, con alerta en 24 USD y modo degradado al llegar al tope. El costo real lo cubren el crédito prepagado de Deepgram (sin recarga automática) y los planes gratuitos de Gemini y Cartesia; ningún proveedor queda con recarga ni cobro automático. *(P9, D-015, M20, R6)* (affirmed 2026-09-16; enmendada 2026-10-07 por decisión de Miguel «Tope a 40», tras ver que el gasto real en tres semanas era 0,09 USD y el tope de 5 USD dejaba una llamada pública al día)

- NEVER "arreglar" una clave filtrada borrándola del archivo: una clave que llegó a un commit se considera comprometida y **se rota en el proveedor** antes de cerrar el incidente. *(Q7, D-017, D-015)* (affirmed 2026-09-16)

- NEVER prometer en la landing, el README o la voz de la agente una capacidad que no está construida. *(P7, M17, M19)* (affirmed 2026-09-16)

## Mandated

<!-- Populated by practices-discovery affirmation gate. -->
<!-- Format: ALWAYS [behavior] (affirmed [date]) -->
<!-- Example: ALWAYS use Result<T,E> for fallible operations in service layer (affirmed 2026-05-17) -->

- ALWAYS ejecutar la compuerta en el flujo de GitHub Actions sobre `main`, con el escaneo de secretos como **primer trabajo**, invocando el guion único de verificación; un `main` en rojo es un incidente y arreglarlo hacia adelante tiene prioridad sobre cualquier otro trabajo, sin apilar cambios nuevos encima salvo el que lo arregla. *(Q1, Q7, P5, M8, PRD 11.3)* (affirmed 2026-09-16)

- ALWAYS escribir o extender el caso de golden set y su criterio de aceptación **antes** de implementar un comportamiento que el PRD mide, y convertir todo ataque de red-team exitoso en caso de DS-6 que no se cierra hasta que pasa. *(Q3, P5, PRD 11.4)* (affirmed 2026-09-16)

- ALWAYS mantener el piso de cobertura del 80 % agregado sobre el código del aplicativo y del 80 % en los módulos críticos (motor de reglas, verificador de citas, aislamiento por tenant, esquema del caso y redacción de datos personales), medido por un comando que falla cuando no se alcanza y con lista de exclusión versionada; el piso es obligación propia del equipo y no depende de que el scope lo active. *(Q4, `org.md` — "Build and Test verifies defined coverage floors"; verificado: `classic` no activa ese piso en el contrato determinista)* (affirmed 2026-09-16; enmendada 2026-09-20 por decisión de Miguel: la redacción de datos personales entra a la lista de módulos críticos)

- ALWAYS registrar cada criterio `[bloquea]` de PRD 11.2 y cada umbral cuantificado del Segmento 10 como objetivo medible en `nfr-requirements`, con identificador estable, valor esperado y el comando que produce su valor real, de modo que aparezca como fila propia en la `## Target Verification Matrix` de `build-and-test`; ningún criterio `[bloquea]` se cierra con `N/A`. *(PRD 11.2, Segmento 10; contrato de `build-and-test`)* (affirmed 2026-09-16)

- ALWAYS generar instrucciones de prueba de seguridad (aislamiento, redacción de PII, adversarial) y de rendimiento (latencias de turno y de parada, duración de la corrida de evals) con independencia de la estrategia de pruebas activa. *(PRD 10, 11.2; `Test Strategy: Standard` no las genera por sí sola)* (affirmed 2026-09-16)

- ALWAYS versionar los casos de los golden sets como archivos de datos, uno por caso, con identificador estable, y mantener el generador sintético determinista y sembrado con su salida commiteada. *(P5, M8, F12.5, PRD 11.5)* (affirmed 2026-09-16)

- ALWAYS aislar por `tenant_id` con Row Level Security en la base de datos, no solo en el código, **fijar el tenant de la sesión en un único punto de entrada** por el que pasa toda consulta del aplicativo, y mantener una aserción automática sobre el esquema que falla si alguna tabla del aplicativo carece de RLS habilitado o de política de tenant; cada tabla nueva llega con su test de aislamiento. *(M9, F9.1, F9.4, R8, PRD 12.2)* (affirmed 2026-09-16)

- ALWAYS redactar los datos personales **antes de persistir** y en cada punto de salida —transcripción parcial y final, logs, trazas, exportaciones y reporte de evals—, con esos puntos de salida declarados en un solo lugar del código por el que pasa todo. *(M6, P6, F7.3, RT-14, M10)* (affirmed 2026-09-16)

- ALWAYS usar dos detectores de datos personales de **mecanismos distintos**, con reconocedores propios para placa, cédula, teléfono y número de póliza en español y en inglés, y medir la redacción por idioma y por tipo de entidad, nunca como promedio. *(M6, RT-14, RT-15, P12)* (affirmed 2026-09-16)

- ALWAYS tratar lo que entra por una superficie pública (chat en vivo, enlace de voz, formularios de demostración) como dato personal potencialmente **real**, con retención acotada por el reinicio nocturno de los datos de demostración y con el primer mensaje declarando que es una demostración con pólizas de ejemplo. *(M10, F8.7, P6, R7, R8)* (affirmed 2026-09-16)

- ALWAYS pasar por `interrupt()` hacia la bandeja antes de que cualquier salida afirme cobertura, la deniegue o mencione montos: la decisión la firma una persona. *(P1, M2, M11)* (affirmed 2026-09-16)

- ALWAYS hacer pasar por la guardia de salida todo texto que llegue al asegurado, incluidos los caminos de degradación y de error, emitido desde el catálogo de copy por idioma. *(M6, F7.5, P1, P12)* (affirmed 2026-09-16)

- ALWAYS emitir una cita solo con identificadores de cláusula recuperados del tenant y verificados por el verificador exacto, y **distinguir el resultado verificado "no encuentro una cláusula que lo cubra" del fallo "no pude verificar"** como dos valores distintos en el estado, en la traza y en el reporte de evals. *(M4, F5.6, P2, P5, PRD 11.2, PRD 12.3)* (affirmed 2026-09-16)

- ALWAYS versionar cada regla del motor de reglas y acompañarla de su test unitario. *(M5, PRD 12.2)* (affirmed 2026-09-16)

- ALWAYS decidir la transición entre nodos en código: una función que recibe solo campos del estado tipado y devuelve un valor de un conjunto cerrado de nombres de nodo, sin ningún cliente de LLM en su cadena de llamadas, y con el módulo de orquestación sin importar canales ni SDK de proveedores. *(P3, M2, F2.1, F2.6, R10)* (affirmed 2026-09-16)

- ALWAYS declarar la política de fallo de cada nodo como dato —tiempo máximo, un reintento, texto de degradación— aplicada por un ejecutor común; un nodo no captura su propio fallo para continuar, y todo fallo deja un valor distinguible en el caso y un evento en la traza. *(M2, F2.7, PRD 12.2, 12.3)* (affirmed 2026-09-16)

- ALWAYS mantener el texto de origen externo (asegurado, corpus recuperado, documento adjunto) **fuera de la posición de instrucción del prompt**: entra como campo delimitado del estado tipado, nunca concatenado al prompt de sistema; la categoría y la derivación las deciden las reglas, no el modelo. *(RT-1, RT-2, RT-5, P3, F7.5)* (affirmed 2026-09-16)

- ALWAYS registrar costo, latencia y tokens por caso y por nodo en la traza, con el modelo y el precio de lista usados. *(M7, M20, P9)* (affirmed 2026-09-16)

- ALWAYS mantener paridad entre español e inglés: mismos casos de eval, mismas métricas y mismas metas, reportadas por idioma y nunca como promedio combinado. *(P12, M14, M15)* (affirmed 2026-09-16)

- ALWAYS leer secretos y claves de proveedor desde variables de entorno o un gestor de secretos, con claves separadas por uso (voz, chat, evals), cada una con **su propio tope o cuota configurado en el proveedor**, y con el cliente de cada proveedor construido en un único lugar por uso. *(guardarraíl de `phases/construction.md`; PRD 12.2, D-015, R6)* (affirmed 2026-09-16)

- ALWAYS correr un escáner de secretos sobre lo que se commitea y sobre el historial completo, desde antes del primer commit de código de aplicación, y activar la protección de inserción del propio GitHub si está disponible para el repositorio; un hallazgo bloquea. *(Q7, D-017 — repositorio candidato a público en la semana 12)* (affirmed 2026-09-16)

- ALWAYS crear el código de aplicación con manifiesto, lockfile **con hashes de integridad**, toolchain fijado y configuración de formatter, linter y tipos con su alcance declarado al prefijo del aplicativo, todo en el **mismo primer commit**; la instalación usa el modo reproducible del gestor, nunca una resolución libre. *(TD-09; `dependencies.md` riesgo 3; Q6)* (affirmed 2026-09-16)

- ALWAYS auditar las dependencias contra vulnerabilidades conocidas en cada corrida del guion de verificación; un hallazgo alto o crítico en una dependencia que el aplicativo ejecuta bloquea, y su excepción se escribe con fecha y razón. *(`dependencies.md` riesgo 3; D-017)* (affirmed 2026-09-16)

- ALWAYS registrar la licencia de cada dependencia de terceros y de cada recurso (voces, modelos, fuentes) junto con la atribución que exija, y rechazar la que impida publicar el repositorio; la lista se revisa una vez antes de la decisión de publicar de la semana 12. *(R9, D-017, M17; precedente `site/PHOSPHOR-LICENSE.txt`)* (affirmed 2026-09-16)

- ALWAYS declarar el identificador de modelo, el proveedor y sus parámetros en configuración versionada; cambiarlos es un cambio de código que dispara la compuerta de evals y se anota en el diff contra la línea base. *(P5, D-015, M20)* (affirmed 2026-09-16)

- ALWAYS contar los veredictos del juez solo mientras sus dos tasas contra las etiquetas humanas de DS-7 —la de fallos que detecta (TNR) y la de aciertos que confirma (TPR)—, medidas por criterio y por idioma sobre la partición de prueba y con intervalo de confianza, alcancen el umbral que fija `nfr-requirements`; por debajo, o tras cambiar modelo o rúbrica sin recalibrar, los criterios que dependen de él se reportan como "no medida" y no bloquean, mientras las compuertas duras juzgadas por código siguen bloqueando. *(M8, P5, PRD 11.3)* (affirmed 2026-09-16; enmendada 2026-09-17 por decisión de Miguel: TPR y TNR en lugar del 85 % de acuerdo, ADR-014)

- ALWAYS marcar como **no comparable** la corrida cuya compuerta se pone roja por causa externa al cambio (proveedor caído, cambio de versión del modelo, cuota agotada), con la causa y el identificador de la corrida registrados, y repetirla; el umbral no se toca nunca y una compuerta que no se pudo ejecutar se declara "no medida", jamás se omite. *(Q8, P5, PRD 10; `org.md` — prohibición de bajar umbrales)* (affirmed 2026-09-16)

## Corrections

<!-- Project-specific corrections from human feedback. -->
<!-- Format: NEVER/ALWAYS [behavior] (learned [date]) -->
- En los escaneos del code knowledge base, `.claude/` y `aidlc/` (tooling del flujo de trabajo), el kit de metodología bajo `docs/` y los directorios ignorados por git (`review/`, `site/.vercel/`) se declaran en `shallow.paths`, y `site/` se documenta como landing estática fuera del alcance del aplicativo; el store se publica con `kind: full` sobre `./` para que otros intents lo reutilicen sin ocultar lo que no se leyó. (learned 2026-09-15) <!-- cid:260915-untangle-app:reverse-engineering:77f74bf406e6d37e2232f8b2c8db682a69f20fabad84cb261c03efe9bb5ffc5a -->
- Idioma de conversación: español. Los documentos del flujo de trabajo AIDLC (artefactos, preguntas, revisiones, diarios) se escriben en español, igual que la pre-incepción; el código, los nombres técnicos, las rutas y los tokens literales del framework siguen en inglés. Reemplaza la parte de D-003 del plan que decía inglés para los artefactos AIDLC (decisión de Miguel, 2026-09-15). (learned 2026-09-15) <!-- cid:260915-untangle-app:reverse-engineering:114404321123c4877f458eb7505b17b87a970b2e6a3fb370538e57849c7bb791 -->
- Construcción recorre el trabajo por componente y no por etapa: primero una base sólida y terminada (caso, inquilinos con aislamiento, corpus, grafo), y después cada componente completo antes de empezar el siguiente, sin dejar ninguno a medias. Es insumo directo de `delivery-planning` y del arranque de Construcción (decisión de Miguel en Practices Discovery, 2026-09-16). (learned 2026-09-16) <!-- cid:260915-untangle-app:practices-discovery:7549b72030de66f73423d60169a7f7c6836fd1b92f0293a3723382453c21a7e1 -->
- Con `- **Methodology**: custom`, la línea `- **Ordering**:` de la posture de pruebas deja de ser una nota y pasa a ser el plan de pruebas completo que recibe la generación de código; además se captura en una sola línea, así que reformatearla en viñetas perdería todo menos la primera. Al editarla, mantenerla en una línea y con ramas cerradas y exhaustivas. (learned 2026-09-16) <!-- cid:260915-untangle-app:practices-discovery:06e576bb336d1ae178347222a5b0761df75263503b4c0c367eb7ff03c31555e8 -->
- El piso de cobertura del 80 % no se activa automáticamente en este tipo de flujo aunque los defaults del espacio lo enuncien: hay que escribirlo como obligación propia del proyecto, con su comando y su lista de exclusión, o sobrevive solo como prosa que nadie hace cumplir. (learned 2026-09-16) <!-- cid:260915-untangle-app:practices-discovery:ad5e8b005fa54a39eb1c7e8c57a9039ee8c00d2e056b799d4c7d6ba0dd215057 -->
- Al convertir alcance en requisitos, todo lo que no entra debe quedar visible: o en `Fuera de alcance` con su razón, o en preguntas abiertas con su dueño. Una funcionalidad que simplemente no aparece es distinta de una excluida a propósito, y la diferencia solo se nota cuando ya es tarde. Detectado en la revisión de Requirements Analysis, donde tres funcionalidades Should del PRD desaparecieron sin rastro. (learned 2026-09-16) <!-- cid:260915-untangle-app:requirements-analysis:c842dd3d4e505a37431e6cc2af048143e61ea8d33fe9b40efd6e607a840fe719 -->
- El enlace firmado de una hora (FR8.7) abre solo la vista del caso del visitante, nunca la lista de la aseguradora: es la lectura literal de la respuesta Q6 de Requirements Analysis, y mostrar la lista expondría casos de otros visitantes. El diseño, los contratos y las pruebas de la bandeja parten de ahí. (learned 2026-09-16) <!-- cid:260915-untangle-app:user-stories:832ccf56b6d34e8dee83115ea798902c71bd08e94eaecd8d35237b3ba54633ef -->
- Las actividades del proyecto que no son conducta del sistema, como la validación del día 30 (S3) y la prueba ciega de la voz (S6), no se escriben como historias ni como unidades: se planifican en Delivery Planning, y sus resultados entran como criterios humanos o como casos de golden set. (learned 2026-09-16) <!-- cid:260915-untangle-app:user-stories:1dc64d33e477a19ff855866147f3f26bad744842a31ce25a4c2857fe11527552 -->
- Cuando las respuestas de una entrevista llegan sin ambigüedad ni contradicción, se registra así en el diario y no se inventan preguntas de seguimiento. Una capacidad que mezcla los dos idiomas por naturaleza, como la detección automática de idioma (S4), es una sola historia o unidad y no una por idioma. (learned 2026-09-16) <!-- cid:260915-untangle-app:user-stories:94f5b9049844194e33289630927ff8dfe9bf902266cd8743eec9feea718b198a -->
- Al integrar las revisiones del equipo o del revisor, se corrige sin preguntar lo que ya resuelve una regla del proyecto, una práctica afirmada o un requisito aprobado; solo se lleva a Miguel lo que tiene dos respuestas legítimas y cambia lo que ve quien evalúa el producto, siempre con una opción recomendada. (learned 2026-09-16) <!-- cid:260915-untangle-app:user-stories:58308305950a31c4372f98b63f80f1d64e2aac769cdaeee80122fbb92627ab3c -->
- Una meta de costo se aplica al componente del que salió la cifra: la de la voz (NFR14, 0,005 USD por minuto de llamada, decisión D7 de User Stories) mide el modelo, y la transcripción y la síntesis se publican aparte, a precio de lista y en gasto efectivo, sin meta hasta que los spikes den datos. (learned 2026-09-16) <!-- cid:260915-untangle-app:user-stories:06cfffda81329a954a16c0d3a13f03fa922391292d3c84885dd0c7917c548cc6 -->
- Una decisión que resuelve una contradicción entre documentos aplicando un requisito aprobado o una práctica afirmada se registra en la tabla de decisiones de la etapa sin pedir visto bueno; solo lo pide la que cambia una frase, un criterio o la aplicación de un principio ya aprobados. (learned 2026-09-16) <!-- cid:260915-untangle-app:user-stories:81eb9adbaf120f69a6ff10a6b67549d619bf630843fc8877b8e9ce88fceb97d7 -->
- En las preguntas a Miguel no se usa "persona" en el sentido de producto: se dice "tipo de usuario" o "perfil ficticio", porque Miguel es el único integrante del proyecto y el término se lee como gente que participa en él. (learned 2026-09-16) <!-- cid:260915-untangle-app:user-stories:009ea4ab2550a34423d546720c801e52638af93b3b7feb2aa6625c8c9c5df918 -->
- Toda superficie pública del aplicativo (panel de cifras, panel de gasto, páginas de estado) muestra solo recuentos, totales y distribuciones, nunca números ni identificadores de casos de visitantes: los casos son de personas que usaron la demo y la vista no pide credencial. Decisión de Refined Mockups sobre la respuesta Q7, 2026-09-16. (learned 2026-09-16) <!-- cid:260915-untangle-app:refined-mockups:91cd7bad6935a15f31d3857aee6f34b89f52cbaa91f4a2528eab5ef1da5438c8 -->
- El cobre de la marca (#E0873A) nunca se usa como texto sobre fondos claros: sobre blanco da 2,7:1 y no pasa el contraste mínimo. En fondos claros, el texto de marca usa la tinta #9A4F12. Decisión de Miguel en Refined Mockups, 2026-09-16. (learned 2026-09-16) <!-- cid:260915-untangle-app:refined-mockups:505d59ceeeec2fd2f7bf824a7ffcf8e956dc454a9df14830f8407251c4ab1d6c -->
- Claro y oscuro son modos completos del aplicativo que elige la persona con un selector de tema: ninguna pantalla impone el suyo y ninguna navegación salta de un tema al otro, porque el cambio brusco de oscuro a claro cansa la vista. Las aseguradoras conservan su acento en los dos modos. Decisión de Miguel en Refined Mockups (2026-09-16), que reemplaza el tema por superficie de la respuesta Q2. (learned 2026-09-16) <!-- cid:260915-untangle-app:refined-mockups:738ca05963f3af81d2cd6aee9b6271990f370f615d6c60675d70593f8b7ae752 -->
- Los textos de ejemplo de maquetas, videos, README y datos de demostración que reproducen una frase fija aprobada (apertura de voz, cierre directo, derivación) la copian literal del criterio que la fija, y la conversación de ejemplo sigue desde lo que esa frase ya dijo, sin repetir una pregunta que la frase ya hizo. (learned 2026-09-16) <!-- cid:260915-untangle-app:refined-mockups:20c91360db4dc1c392c12b851c8e596e04f7de080efa17893d6306315403bc49 -->
- Una regla de las memorias del proyecto solo se borra cuando Miguel lo pide explícitamente, y se hace editando el archivo, porque el ritual de aprendizajes solo agrega reglas. Nunca se borra por iniciativa propia ni para destrabar una etapa. (learned 2026-09-16) <!-- cid:260915-untangle-app:refined-mockups:4620cecd6571f4610a70c6cc5e4897ce58d9102b10360c6df3432ca56b8953b9 -->
- Ninguna cuenta de proveedor del proyecto (modelo, voz, transcripción, hospedaje, generación de imágenes) queda con suscripción que se renueva sola, recarga automática ni cobro de excedentes. Cuando se acaba un saldo o una cuota, el trabajo se detiene, se identifica qué se acabó y Miguel decide si recargar: nunca se recarga ni se contrata por iniciativa propia. Decisión de Miguel, 2026-09-16. (learned 2026-09-16) <!-- cid:260915-untangle-app:refined-mockups:7a9fa9c71e0e17dc3fda00b38a3e9c8d54b86706152316dc96d2acf1b973436b -->
- Los entregables de MOD-15 que no son software en ejecución (video y landing) no se convierten en componentes ni en unidades: en la trazabilidad se marcan N/A con su razón, y el README se asigna al componente que genera sus secciones comprobables. Decisión de Domain Design, 2026-09-17. (learned 2026-09-17) <!-- cid:260915-untangle-app:domain-design:861e2c04a853b8f70d9e1e9309a1b129955c81b621091f83d1dc6f7b8fe2f65f -->
- Cuando una práctica afirmada, un requisito aprobado o el plan asignan una decisión a una etapa concreta (por ejemplo, el lenguaje y los proveedores a Domain Design), esa asignación manda sobre la prosa genérica de la etapa y se registra como desviación en su diario. (learned 2026-09-17) <!-- cid:260915-untangle-app:domain-design:e508f04318333babefb91e01c5db82750d48643fe2dee9f209c1883a09d3957a -->
- Antes de fijar un proveedor para una superficie pública se revisan las condiciones de uso de datos del plan elegido; si permiten usar o leer lo que envían los visitantes, se lleva a Miguel como decisión con opción recomendada, porque lo que entra por esas superficies se trata como dato real. Detectado en Domain Design (Q5), 2026-09-17. (learned 2026-09-17) <!-- cid:260915-untangle-app:domain-design:21c8b4a5fb5e49d56e46ae8eadb333314eae7c577300a32dd8b3e5983376f620 -->
- En decisiones de stack y herramientas, Miguel prioriza buenas prácticas reconocibles para quien evalúa el repositorio: se investiga con fuentes y se recomienda la forma documentada por el proyecto oficial del ecosistema antes que la opción mínima. Decisión de Miguel en Domain Design (Q3), 2026-09-17. (learned 2026-09-17) <!-- cid:260915-untangle-app:domain-design:1b053d04d956e8dc0cccce19e08cb6e593d6332dc63781ebfc6028f79f969c9c -->
- En el mapa de dependencias entre unidades, "A depende de B" significa que A usa la interfaz pública de B o necesita datos o herramientas de B para probarse con datos sembrados; las comprobaciones de punta a punta entre unidades no agregan dependencias: se listan en el mapa de historias y se verifican en Build and Test, para que el mapa no se llene de dependencias falsas ni de ciclos. Decisión UG-8 de Units Generation, 2026-09-17. (learned 2026-09-17) <!-- cid:260915-untangle-app:units-generation:5a4f19ff90e2d86ee79948f19f849673f9ed95b1ac0e08e87df4a0e5f95ec6b2 -->
- El techo de gasto de la voz es acumulado en la ventana de 90 días que empieza el 2026-09-16 (40 USD a precio de lista con alerta en 24 USD desde el 2026-10-07; antes 5 USD con alerta en 3 USD) y nunca mensual, y su mensaje de corte no menciona el mes: donde `team.md` (Deployment) dice "Techo mensual", rige este acumulado. Decisión D11 de User Stories, recogida en Units Generation (PA-13), 2026-09-17. (learned 2026-09-17) <!-- cid:260915-untangle-app:units-generation:5b39448fe0681aae41e0d355d846849bcbe6e9641494cc7561399d31098047b3 -->
- Ninguna credencial de la bandeja se publica: el visitante entra solo a su propio caso con el enlace firmado de una hora, y las credenciales por aseguradora y rol son para Miguel, el despliegue local y las pruebas; reemplaza el párrafo "Credenciales de demostración por tenant" de `team.md` (Deployment). Decisión D23 de User Stories y ADR-012, recogida en Units Generation (PA-13), 2026-09-17. (learned 2026-09-17) <!-- cid:260915-untangle-app:units-generation:2e10470c5410dedbce6fd1bd4aa546056891688060e01a84d3883e250a7dd9cd -->
- Dentro del turno solo corren tres controles baratos de cumplimiento, cada uno con presupuesto de latencia declarado: la guardia de salida, la detección de petición de persona y la de emergencia; la verificación de póliza, las reglas y la revisión completa de cumplimiento van en el ritmo de fondo. Precisa la prohibición de `project.md` (Forbidden) sobre trabajo de cumplimiento en el turno de voz. Decisión D22 de User Stories, recogida en Units Generation (PA-13), 2026-09-17. (learned 2026-09-17) <!-- cid:260915-untangle-app:units-generation:6d2e78351b83ef678ec8942f2e843fb8216460c197f5ac2ea9dc2a884c11bf6b -->
- Toda cifra que aparece en una pregunta o en un plan para Miguel (número de unidades, historias por pieza, conteos) sale del mismo cálculo que genera los artefactos y se calcula antes de escribir la pregunta; si después no coincide, se corrige ante él antes de que decida. Detectado en Units Generation, 2026-09-17. (learned 2026-09-17) <!-- cid:260915-untangle-app:units-generation:0a8adf3c3eea725f80162d8820d0aadf29f3911cd6e393b78e1eff452c06efcb -->
- En Units Generation, el nombre de cada unidad en el bloque yaml de dependencias es su directorio de Construcción (`u{n}-{descripción}`), igual a la columna `Directory` de `unit-of-work.md`: con el nombre corto, la comprobación de trazabilidad no reconoce los `Unit ID` como unidades declaradas. Detectado en Units Generation, 2026-09-17. (learned 2026-09-17) <!-- cid:260915-untangle-app:units-generation:db10444b64f341d5fd47e6a1d584e243f0887923033b35c0519124106a172cdc -->
- La regla de construir componente por componente sin dejar ninguno a medias se aplica por unidad de trabajo: un componente del catálogo puede construirse en varias unidades cuando documentos aprobados obligan a hacerlo en momentos distintos (por ejemplo, la voz por capas de idioma o el corredor de evaluaciones antes del primer caso), siempre que cada unidad termine completa y el reparto quede declarado en `unit-of-work.md`. Decisión de Miguel en Units Generation, 2026-09-17. (learned 2026-09-17) <!-- cid:260915-untangle-app:units-generation:8c003c53a2abb3061682577f8d3186dca861bd8b1d4d6532cb8727ff39a7df6a -->
- Cuando Miguel delega la decision en la recomendacion ("usa la que mas se recomiende" o similar), no se auto-responde: se explica en una o dos frases por que esa opcion es la recomendada y se le vuelve a presentar la pregunta, para que la eleccion quede como decision suya. (learned 2026-09-18) <!-- cid:260915-untangle-app:contract-design:7fa41d30bb55e85a180490ffcddc899a7dd890672436c9e3cce899e7b1eda39a -->
- En las fronteras dentro del mismo proceso, el contrato se escribe como la firma del `api.py` del modulo (tipos congelados y `Protocol`), no como un documento OpenAPI: OpenAPI se reserva para lo que cruza por HTTP. (learned 2026-09-18) <!-- cid:260915-untangle-app:contract-design:7a82918c92aea3390b7462bbc0f767a9cc0093e35aee3ae6936c9a0708319beb -->
- La API HTTP no lleva version en la ruta mientras su unico consumidor sea la interfaz de este mismo repositorio, que se compila y se despliega con el servidor: la regla es solo cambios aditivos, y el disparador para versionar es que aparezca un consumidor fuera del repositorio. Decision de Miguel del 2026-09-18, que reemplaza el prefijo `/api/v1` propuesto en Contract Design. (learned 2026-09-18) <!-- cid:260915-untangle-app:contract-design:8821c1a9dd0ca0eda8833079dd730ba74fe590aa6483c9251a161deeba78462c -->
- Los contratos se escriben uno por superficie que ofrece una unidad, no uno por arista del mapa de dependencias: asi cada acuerdo tiene una sola copia autoritativa y el mapa de dependencias sigue siendo el que dice quien consume que. (learned 2026-09-18) <!-- cid:260915-untangle-app:contract-design:b575a217a29c901df187ded6cb2b4c4ab1a1d98d9eceb5ed021e337ed4a9f9c1 -->
- La clave de idempotencia se exige solo en las escrituras donde un doble envio causa dano real (enviar un mensaje, decidir un caso, corregir un campo), no en toda la API. (learned 2026-09-18) <!-- cid:260915-untangle-app:contract-design:be9e3ca800d1195fab5a11903fe2072062236e8f45a49e9ce1c2b7a3283ba352 -->
- El PRD y AI-DLC usan la palabra "unit" para cosas distintas: el PRD llama unit a cada capa de entrega (Core, Policy RAG, Agents, Bandeja y chat, Voz...), y AI-DLC llama unidad de trabajo a cada una de las 22 piezas que se construyen. Un Bolt es una unidad de AI-DLC; las capas del PRD son semanas del calendario, no Bolts. Al leer el Segmento 13 del PRD hay que traducir el termino antes de usarlo. (learned 2026-09-18) <!-- cid:260915-untangle-app:delivery-planning:663dccfc5cf31c0fd0812b59fa5eff2211a06162fb77b4bb2d11a6dd81062130 -->
- No se introduce un modelo de puntaje formal (WSJF o similar) para ordenar el trabajo cuando las dependencias y un calendario ya aprobado dejan poco margen: se escribe explicitamente por que no se usa, en lugar de calcular un puntaje que no cambia el orden. Decision de Delivery Planning, 2026-09-18. (learned 2026-09-18) <!-- cid:260915-untangle-app:delivery-planning:1656ba6fa4327938a01e7afe6959587faaa1459221aaf816fa7dc95f126ccc6a -->
- Excepción a UG-8, decisión de Miguel del 2026-09-21 (DP-14): el mapa de dependencias admite aristas de ORDEN DE ENTREGA cuando Miguel decide el orden y la herramienta del flujo solo ordena por dependencias. Cada una va nombrada, como no técnica y con su decisión, en la enmienda que precede al bloque de aristas (el bloque no admite comentarios), y solo se permite hacia unidades de las que nadie depende; las aristas técnicas siguen significando lo que dice UG-8. (learned 2026-09-21) <!-- cid:260915-untangle-app:functional-design:1960b3ac961a46325d862c70dec3103aeeaca9df7a86c63736a4d45442212929 -->
