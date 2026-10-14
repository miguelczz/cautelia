# Reglas duras afirmadas — `practices-discovery`

> **Afirmadas.** Estas reglas quedaron confirmadas en la entrevista de esta
> etapa y en la integración de las tres revisiones especializadas. Al aprobarse
> se escriben en `## Mandated` y `## Forbidden` de
> `aidlc/spaces/default/memory/team.md`.
>
> Cada una se apoya en una fuente dura —un Must del PRD (`M<n>`), un principio
> (`P<n>`), una feature (`F<n>.<n>`), una decisión del plan (`D-0<nn>`), un
> riesgo (`R<n>`), un escenario de red-team (`RT-<n>`), un item de deuda
> (`TD-<nn>`), una respuesta de la entrevista (`Q<n>`) o un default de
> `org.md`—; ninguna viene de preferencia personal.
>
> Solo entran aquí **restricciones duras**: cosas cuyo incumplimiento rompe un
> principio, una compuerta o el presupuesto. Lo que es preferencia de trabajo
> vive en `team-practices.md`, no aquí.

## Mandated

- ALWAYS ejecutar la compuerta en el flujo de GitHub Actions sobre `main`, con el escaneo de secretos como **primer trabajo**, invocando el guion único de verificación; un `main` en rojo es un incidente y arreglarlo hacia adelante tiene prioridad sobre cualquier otro trabajo, sin apilar cambios nuevos encima salvo el que lo arregla. *(Q1, Q7, P5, M8, PRD 11.3)*
- ALWAYS escribir o extender el caso de golden set y su criterio de aceptación **antes** de implementar un comportamiento que el PRD mide, y convertir todo ataque de red-team exitoso en caso de DS-6 que no se cierra hasta que pasa. *(Q3, P5, PRD 11.4)*
- ALWAYS mantener el piso de cobertura del 80 % agregado sobre el código del aplicativo y del 80 % en los módulos críticos (motor de reglas, verificador de citas, aislamiento por tenant, esquema del caso), medido por un comando que falla cuando no se alcanza y con lista de exclusión versionada; el piso es obligación propia del equipo y no depende de que el scope lo active. *(Q4, `org.md` — "Build and Test verifies defined coverage floors"; verificado: `classic` no activa ese piso en el contrato determinista)*
- ALWAYS registrar cada criterio `[bloquea]` de PRD 11.2 y cada umbral cuantificado del Segmento 10 como objetivo medible en `nfr-requirements`, con identificador estable, valor esperado y el comando que produce su valor real, de modo que aparezca como fila propia en la `## Target Verification Matrix` de `build-and-test`; ningún criterio `[bloquea]` se cierra con `N/A`. *(PRD 11.2, Segmento 10; contrato de `build-and-test`)*
- ALWAYS generar instrucciones de prueba de seguridad (aislamiento, redacción de PII, adversarial) y de rendimiento (latencias de turno y de parada, duración de la corrida de evals) con independencia de la estrategia de pruebas activa. *(PRD 10, 11.2; `Test Strategy: Standard` no las genera por sí sola)*
- ALWAYS versionar los casos de los golden sets como archivos de datos, uno por caso, con identificador estable, y mantener el generador sintético determinista y sembrado con su salida commiteada. *(P5, M8, F12.5, PRD 11.5)*
- ALWAYS aislar por `tenant_id` con Row Level Security en la base de datos, no solo en el código, **fijar el tenant de la sesión en un único punto de entrada** por el que pasa toda consulta del aplicativo, y mantener una aserción automática sobre el esquema que falla si alguna tabla del aplicativo carece de RLS habilitado o de política de tenant; cada tabla nueva llega con su test de aislamiento. *(M9, F9.1, F9.4, R8, PRD 12.2)*
- ALWAYS redactar los datos personales **antes de persistir** y en cada punto de salida —transcripción parcial y final, logs, trazas, exportaciones y reporte de evals—, con esos puntos de salida declarados en un solo lugar del código por el que pasa todo. *(M6, P6, F7.3, RT-14, M10)*
- ALWAYS usar dos detectores de datos personales de **mecanismos distintos**, con reconocedores propios para placa, cédula, teléfono y número de póliza en español y en inglés, y medir la redacción por idioma y por tipo de entidad, nunca como promedio. *(M6, RT-14, RT-15, P12)*
- ALWAYS tratar lo que entra por una superficie pública (chat en vivo, enlace de voz, formularios de demostración) como dato personal potencialmente **real**, con retención acotada por el reinicio nocturno de los datos de demostración y con el primer mensaje declarando que es una demostración con pólizas de ejemplo. *(M10, F8.7, P6, R7, R8)*
- ALWAYS pasar por `interrupt()` hacia la bandeja antes de que cualquier salida afirme cobertura, la deniegue o mencione montos: la decisión la firma una persona. *(P1, M2, M11)*
- ALWAYS hacer pasar por la guardia de salida todo texto que llegue al asegurado, incluidos los caminos de degradación y de error, emitido desde el catálogo de copy por idioma. *(M6, F7.5, P1, P12)*
- ALWAYS emitir una cita solo con identificadores de cláusula recuperados del tenant y verificados por el verificador exacto, y **distinguir el resultado verificado "no encuentro una cláusula que lo cubra" del fallo "no pude verificar"** como dos valores distintos en el estado, en la traza y en el reporte de evals. *(M4, F5.6, P2, P5, PRD 11.2, PRD 12.3)*
- ALWAYS versionar cada regla del motor de reglas y acompañarla de su test unitario. *(M5, PRD 12.2)*
- ALWAYS decidir la transición entre nodos en código: una función que recibe solo campos del estado tipado y devuelve un valor de un conjunto cerrado de nombres de nodo, sin ningún cliente de LLM en su cadena de llamadas, y con el módulo de orquestación sin importar canales ni SDK de proveedores. *(P3, M2, F2.1, F2.6, R10)*
- ALWAYS declarar la política de fallo de cada nodo como dato —tiempo máximo, un reintento, texto de degradación— aplicada por un ejecutor común; un nodo no captura su propio fallo para continuar, y todo fallo deja un valor distinguible en el caso y un evento en la traza. *(M2, F2.7, PRD 12.2, 12.3)*
- ALWAYS mantener el texto de origen externo (asegurado, corpus recuperado, documento adjunto) **fuera de la posición de instrucción del prompt**: entra como campo delimitado del estado tipado, nunca concatenado al prompt de sistema; la categoría y la derivación las deciden las reglas, no el modelo. *(RT-1, RT-2, RT-5, P3, F7.5)*
- ALWAYS registrar costo, latencia y tokens por caso y por nodo en la traza, con el modelo y el precio de lista usados. *(M7, M20, P9)*
- ALWAYS mantener paridad entre español e inglés: mismos casos de eval, mismas métricas y mismas metas, reportadas por idioma y nunca como promedio combinado. *(P12, M14, M15)*
- ALWAYS leer secretos y claves de proveedor desde variables de entorno o un gestor de secretos, con claves separadas por uso (voz, chat, evals), cada una con **su propio tope o cuota configurado en el proveedor**, y con el cliente de cada proveedor construido en un único lugar por uso. *(guardarraíl de `phases/construction.md`; PRD 12.2, D-015, R6)*
- ALWAYS correr un escáner de secretos sobre lo que se commitea y sobre el historial completo, desde antes del primer commit de código de aplicación, y activar la protección de inserción del propio GitHub si está disponible para el repositorio; un hallazgo bloquea. *(Q7, D-017 — repositorio candidato a público en la semana 12)*
- ALWAYS crear el código de aplicación con manifiesto, lockfile **con hashes de integridad**, toolchain fijado y configuración de formatter, linter y tipos con su alcance declarado al prefijo del aplicativo, todo en el **mismo primer commit**; la instalación usa el modo reproducible del gestor, nunca una resolución libre. *(TD-09; `dependencies.md` riesgo 3; Q6)*
- ALWAYS auditar las dependencias contra vulnerabilidades conocidas en cada corrida del guion de verificación; un hallazgo alto o crítico en una dependencia que el aplicativo ejecuta bloquea, y su excepción se escribe con fecha y razón. *(`dependencies.md` riesgo 3; D-017)*
- ALWAYS registrar la licencia de cada dependencia de terceros y de cada recurso (voces, modelos, fuentes) junto con la atribución que exija, y rechazar la que impida publicar el repositorio; la lista se revisa una vez antes de la decisión de publicar de la semana 12. *(R9, D-017, M17; precedente `site/PHOSPHOR-LICENSE.txt`)*
- ALWAYS declarar el identificador de modelo, el proveedor y sus parámetros en configuración versionada; cambiarlos es un cambio de código que dispara la compuerta de evals y se anota en el diff contra la línea base. *(P5, D-015, M20)*
- ALWAYS contar los veredictos del juez solo mientras su coincidencia con las etiquetas humanas de DS-7 esté en el 85 % o por encima; por debajo, o tras cambiar modelo o rúbrica sin recalibrar, los criterios que dependen de él se reportan como "no medida" y no bloquean, mientras las compuertas duras juzgadas por código siguen bloqueando. *(M8, P5, PRD 11.3)*
- ALWAYS marcar como **no comparable** la corrida cuya compuerta se pone roja por causa externa al cambio (proveedor caído, cambio de versión del modelo, cuota agotada), con la causa y el identificador de la corrida registrados, y repetirla; el umbral no se toca nunca y una compuerta que no se pudo ejecutar se declara "no medida", jamás se omite. *(Q8, P5, PRD 10; `org.md` — prohibición de bajar umbrales)*

## Forbidden

- NEVER incluir datos de personas reales, ni texto de cláusula, formularios o specímenes de ISO o ACORD, en el repositorio o en el corpus: los datos son 100 % sintéticos y las pólizas son originales con estructura inspirada. *(P8, W6, R9)*
- NEVER afirmar "cumple con" una norma (NAIC, TCPA, EU AI Act, SOC 2, HIPAA) en código, README, copy, landing o cualquier salida del sistema; se dice "inspirado en". *(P6, W3, R9)*
- NEVER retirar un caso fallido de un golden set para mejorar una métrica, ni publicar una métrica sin su golden set, ni construir un set donde los casos fáciles sean mayoría. *(P5)*
- NEVER bajar un umbral, relajar un piso de cobertura ni saltar una compuerta dura para que un paso pase. *(P5; `org.md` — "they may not be weakened to make a step pass")*
- NEVER silenciar un hallazgo de seguridad del linter con una supresión en línea sin una razón escrita al lado. *(guardarraíl de `phases/construction.md`; PRD 12.2)*
- NEVER hacer trabajo de verificación, de reglas o de cumplimiento dentro del turno de voz; ese trabajo va en el ritmo de fondo. *(P4, R2)*
- NEVER dejar que un LLM decida con texto libre a qué nodo del grafo ir, ni ejecutar una acción sobre el caso fuera de una ruta del grafo, ni hacer que el grafo dependa del framework de voz. *(P3, M2, R10)*
- NEVER escribir un `tenant_id` literal en el código del aplicativo fuera del cargador de configuración y de las fixtures, ni ramificar por tenant dentro del código de decisión: las diferencias entre tenants viven en su carpeta de configuración versionada, incluida la política de derivación siempre de la agencia. *(M5, M9, F9.2, F9.6, F6.3, P1)*
- NEVER importar el SDK de un proveedor externo (STT, LLM, TTS, almacén vectorial) fuera de su adaptador, ni construir su cliente fuera de la fábrica que separa las claves por uso. *(P3, P9, M20, PRD 12.2)*
- NEVER abrir una conexión a la base de datos fuera del punto único que fija el tenant de la sesión, ni construir SQL por concatenación. *(M9, F9.1, R8, PRD 12.2)*
- NEVER escribir en un log, en una traza o en una exportación fuera del punto único de salida que aplica la redacción: un punto de salida nuevo sin redacción debe ser imposible por construcción, no detectable por disciplina. *(M6, P6, RT-14, PRD 12.2 — "Nuevo punto de salida sin redacción")*
- NEVER publicar una superficie pública que invoque al LLM sin límite por sesión, por origen y por día, sin el modo degradado probado, y sin el tope configurado **también en el proveedor**: un límite que vive solo en la aplicación falla abierto cuando lo que falla es la aplicación. *(Q5, RT-13, M20, D-015, R6, P9)*
- NEVER publicar el enlace en vivo de la voz antes de que `requirements-analysis` reconcilie con el PRD la promoción de `C5` y el tope de gasto: esta etapa afirma la condición de publicación, no el cambio de alcance. *(Q5, D-015, M20, PRD 8 clasificación `C5`; `phases/inception.md` — prohibido arrastrar contradicciones sin resolverlas)*
- NEVER incurrir en un gasto que no esté escrito como excepción: el tope vigente es 5 USD en 90 días, con alerta en 3 USD y modo degradado al llegar al tope. *(P9, D-015, M20, R6)*
- NEVER "arreglar" una clave filtrada borrándola del archivo: una clave que llegó a un commit se considera comprometida y **se rota en el proveedor** antes de cerrar el incidente. *(Q7, D-017, D-015)*
- NEVER usar la landing (`site/`) como insumo de diseño del aplicativo, ni incluirla en el piso de cobertura, ni realinearla antes de que la arquitectura esté aprobada. *(D-005, D-013, TD-01)*
- NEVER prometer en la landing, el README o la voz de la agente una capacidad que no está construida. *(P7, M17, M19)*
