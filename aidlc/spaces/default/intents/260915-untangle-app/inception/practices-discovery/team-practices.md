# Prácticas del equipo — `practices-discovery`

> **Afirmadas.** Estas cinco secciones integran lo que Miguel decidió en la
> entrevista de esta etapa con las tres revisiones especializadas (calidad,
> desarrollo, seguridad de la cadena de entrega). Al aprobarse reemplazan las
> secciones homónimas de `aidlc/spaces/default/memory/team.md`. No queda nada
> pendiente: donde algo todavía no se puede decidir, la práctica nombra la
> obligación, el momento en que aterriza y quién la aterriza.
>
> Tres hechos condicionan todo lo que sigue. El equipo es **una persona**
> (Miguel), con 90 días y 5 USD de presupuesto. **No existe código de
> aplicación**: la única línea base es `site/`, una landing estática sin build,
> sin pruebas y sin lint, fuera del alcance del aplicativo (D-005, D-013). Y
> **el lenguaje del aplicativo no está elegido** (lo fija un ADR de
> `domain-design`). Por eso cada práctica nombra la obligación y no la
> herramienta, salvo donde el PRD ya decidió (Presidio, RLS en Postgres) o donde
> la herramienta es indiferente a esa elección (escaneo de secretos, auditoría
> de dependencias, registro de licencias, archivo de tareas).

## Way of Working

Trabajamos sobre tronco único, en su variante **sin rama intermedia**: el código
del aplicativo, la documentación y el registro del flujo (`aidlc/`) entran
**directos a `main`**. No abrimos rama corta ni pull request para el trabajo
propio. Esta es una afirmación explícita del equipo que reemplaza el default de
`org.md` ("All work merges to `main` via short-lived feature branches") para
este proyecto; sigue siendo desarrollo sobre tronco y no introduce ramas de
vida larga.

**GitHub Actions es nuestra integración continua y sus pruebas son la
compuerta.** La consecuencia es dura y la aceptamos con los ojos abiertos: la
compuerta corre **después** de que el cambio ya aterrizó en `main`. De ahí tres
obligaciones que no son opcionales:

- Un `main` en rojo es un incidente, no un estado de trabajo. Arreglar hacia
  adelante tiene prioridad sobre cualquier otra tarea.
- Ningún cambio nuevo se apila sobre un `main` en rojo salvo el que lo arregla.
- El escaneo de secretos es el **primer trabajo** del flujo, para que el aviso
  llegue en minutos y no al final de la corrida. Toda clave detectada se **rota
  en el proveedor**; borrarla del archivo no cierra el incidente.

Además activamos la **protección de inserción del propio GitHub** si está
disponible para el repositorio: rechaza el envío en el servidor y no depende de
nada instalado en la máquina.

Los controles automáticos viven en **un solo guion de verificación**
(`scripts/verify.sh`), que se crea en el mismo commit que el primer código de
aplicación. GitHub Actions lo invoca en lugar de mantener su propia lista de
pasos en línea, y el intent `infra` lo invocará también en vez de inventar un
segundo juego de chequeos. Orden de ejecución: escaneo de secretos, formato,
lint (con sus reglas de seguridad), chequeo de tipos, pruebas deterministas,
aserciones de esquema, chequeos de contenido, auditoría de dependencias,
golden sets de texto. Cualquier paso en rojo devuelve un código distinto de
cero.

Ese guion se puede correr en local con el mismo comando, y correrlo antes de
empujar es la forma barata de no ensuciar `main`. **No lo exigimos**: no
instalamos gancho previo al commit ni obligamos a ejecutarlo en la máquina. La
compuerta autoritativa, y la única, es GitHub Actions.

Los Bolts de Construcción que corran en worktree se mapean a la estrategia de
tronco: `--base main --target main --strategy squash`. Cada Bolt vuelve como un
único commit nombrado por su slug. El worktree es un dispositivo mecánico del
framework para aislar el trabajo de un Bolt, no una rama de revisión: no hay
pull request y no hay segundo revisor.

La revisión humana que sí practicamos no es de código: es la revisión semanal de
10 casos por idioma en la cola de anotación (PRD 11.3), la sesión de red-team
por hito y las compuertas de aprobación del propio flujo AI-DLC.

Por eso **toda convención de código que afirmemos tiene que ser comprobable por
una herramienta o por un grep**. Una convención que solo se sostiene en la
memoria del autor no es una práctica del equipo: es una intención, y a la semana
seis no está.

El repositorio es privado, bajo la cuenta personal `miguelczz` (D-017). La
máquina tiene dos cuentas en el CLI de `gh`: antes de cualquier operación contra
GitHub se verifica que la activa sea `miguelczz`.

## Walking Skeleton

El scope `classic` declara `skeleton: off`, así que **no corremos la ceremonia
de esqueleto del framework** (Bolt 1 en solitario con aprobación explícita antes
de los demás). El primer Bolt se ejecuta como cualquier otro.

Tampoco construimos un **esqueleto delgado de punta a punta**. La decisión de
Miguel, en sus palabras: *"la gracia de que tengamos una base construida la cual
sea solida. Después de eso haremos la creación de componente Uno A uno para mí
eso es lo más indicado en lugar de dejar un componente a medias"*. La práctica
afirmada es:

1. **Primero una base sólida y terminada**, no una rebanada mínima: esquema del
   caso, tenants con aislamiento verificado, corpus, grafo en modo texto, y el
   andamiaje completo del primer commit (manifiesto, lockfile, herramientas con
   su alcance, archivo de tareas, árbol por módulo, runner de pruebas y corredor
   de evals ejecutables).
2. **Después los componentes uno a uno**, cada uno completo antes de empezar el
   siguiente. El criterio explícito es **no dejar componentes a medias**.

Esto describe un recorrido **por componente** (cada pieza atraviesa todas sus
etapas antes de pasar a la siguiente) y no un recorrido por etapa. `delivery-planning`
secuencia los Bolts con ese recorrido y no con el otro.

La secuencia de componentes debe respetar una restricción que viene del PRD y
que esta decisión no cambia: el camino completo **en texto** existe antes de que
se toque la voz (mitigación de R1, línea base v0 de la semana 3). Es compatible,
porque la voz es un componente tardío en cualquier orden razonable; lo que el
PRD pide no es que la primera pieza sea delgada, sino que la voz no se adelante
al texto.

Heredamos del PRD la regla de corte: **se corta antes de que se rompa**. El
orden de corte es S2, S1, C1, S5, S4; M1 a M20 nunca se cortan, y el español se
reduce en alcance pero no se elimina.

## Testing Posture

- **Methodology**: custom
- **Ordering**: Clasifica cada unidad en una de dos ramas y no dejes ninguna sin rama. Rama evaluada: toda unidad cuyo comportamiento observable aparece en la tabla de criterios de PRD 11.2 o que realiza uno de M1, M4, M5, M6, M8, M9, M13 o M15; para ella se escribe o se extiende primero su caso de golden set (DS-2, DS-3, DS-5, DS-6) con su identificador estable, su criterio de aceptación y su veredicto esperado, se corre y se comprueba que falla, se implementa, y se vuelve a correr hasta que pase. Rama determinista: toda unidad restante sin excepción, recorrida capa por capa en el orden Data model / database behavior, Repository / data access, Business logic, API / endpoint, Frontend behavior; se implementa la capa y a continuación se escriben y corren las pruebas de esa capa antes de pasar a la siguiente. Una unidad de la rama evaluada usa además la rama determinista para las capas que la sostienen. El runner de pruebas, la configuración de cobertura y el corredor de evals se dejan instalados y ejecutables antes del primer caso de cualquiera de las dos ramas, porque no existe ninguno que verificar.

La metodología es `custom` porque la cadencia es mixta a propósito, y decir
`tdd` o `test-after` a secas sería falso. Lo que el PRD evalúa (extracción,
citación, adherencia a la guía de voz, conducta adversarial) se define **antes**
de implementarlo, porque está prohibido publicar una métrica sin su golden set
(P5) y porque un ataque de red-team exitoso se convierte en caso de DS-6 que
debe pasar. El código determinista que sostiene esos comportamientos se prueba
por capa, con la prueba escrita junto a la capa y no semanas después.

**Punto de partida.** No existe ningún runner de pruebas, ninguna configuración
de cobertura y ningún corredor de evals: la línea base es cero. El flujo declara
`Project Type: Brownfield` porque la landing existe, pero **el aplicativo es
greenfield y su andamiaje se crea, no se verifica**. El primer Bolt que toque
código de aplicación deja instalados y ejecutables, antes de su primera prueba,
el runner del lenguaje, la configuración de cobertura y el corredor de evals de
un solo comando (M17), y registra ese comando exacto en el README.

**Piso de cobertura.** 80 % de líneas **agregado** sobre el código del
aplicativo, con piso del 80 % también en los módulos críticos: motor de reglas,
verificador de citas, aislamiento por tenant y esquema del caso. La interfaz y
los adaptadores de proveedor pueden quedar por debajo mientras el agregado se
cumpla. La medición se hace con la herramienta de cobertura del lenguaje
elegido, con un umbral configurado en el manifiesto que **haga fallar el
comando** cuando no se alcanza, y ese comando es el mismo que corren
`build-and-test` y el flujo de GitHub Actions. Se excluyen del cálculo, mediante
una **lista de exclusión versionada** en la configuración: la landing (`site/`,
fuera del alcance por D-005 y D-013), el corpus y los datasets generados, y las
migraciones. El piso es obligación propia del equipo, con su comando y su lista;
no se apoya en que el scope lo active, y no se baja para que un paso pase.

**Datos de prueba.** Los casos de los golden sets viven versionados en el
repositorio como archivos de datos, **un archivo por caso**, con identificador
estable (`DS-2/es/017`), nunca generados en tiempo de corrida. El generador
sintético (MOD-12) es determinista y sembrado: su salida (corpus DS-1, fixtures
DS-8) se regenera solo con un comando explícito y el resultado se commitea, de
modo que dos corridas del mismo commit vean el mismo corpus. Los identificadores
son la moneda de todo el sistema: el reporte por caso, el diff contra la línea
base, la sección "Cómo falla" del README y los casos nacidos de un red-team o
del muestreo del chat en vivo los usan sin traducción.

**Forma de las pruebas.** Cada prueba es independiente del orden de ejecución y
de estado compartido, y se puede correr sola. Cada prueba afirma un
comportamiento, no una implementación: se prueba lo que el requisito exige, no
cómo se codificó. Ninguna prueba pasa con independencia de la implementación.
Cada caso de red-team exitoso entra a DS-6 con el identificador `RT-<n>` en su
nombre, y el hallazgo no se cierra hasta que ese caso pase (PRD 11.4).

**Pruebas deterministas no negociables**, cada una atada a un Must:

- Motor de reglas por tenant: reglas versionadas, cada una con su test unitario (M5).
- Verificador exacto de citas: existencia, pertenencia al tenant y a la póliza, vigencia (M4, P2).
- Aislamiento entre tenants: RLS en la base de datos **y** punto único de adquisición de sesión que fija el `tenant_id` antes de devolverla, con fixtures que provocan colisiones detectables y una aserción sobre el esquema que falla si alguna tabla del aplicativo carece de RLS o de política (M9, F9.1, F9.4, DS-8).
- Redacción de PII en cada punto de salida, con un segundo detector de **mecanismo distinto** al primero y reconocedores propios para placa, cédula, teléfono y número de póliza en los dos idiomas; se mide por idioma y por tipo de entidad, nunca como promedio (M6, RT-14, RT-15, P12).
- Esquema del caso: JSON válido, y solo se citan identificadores recuperados (M1).
- Chequeos de contenido con identificador estable (frases prohibidas, ausencia de texto de cláusula de ISO o ACORD, paridad de claves EN↔ES), para que aparezcan en el reporte por caso y en el diff contra la línea base como cualquier otra prueba.

**Golden sets en cada corrida del flujo**: DS-2 (60 conversaciones de texto, 30
por idioma), DS-3 (40 preguntas de citación con distractores) y DS-6
(adversarial). Corren en el tier gratuito del LLM, con duración objetivo de 10
minutos o menos, y producen un reporte por caso, por criterio y por idioma, con
enlace a su traza.

**Compuertas duras** (`[bloquea]` en PRD 11.2): cero citas inexistentes; cero
turnos que afirmen cobertura, montos o culpa, o den consejo legal; cero
hallazgos de seguridad (PII en trazas, fuga entre tenants, adversarial). Son
pasa o falla por caso y un solo fallo detiene la entrega. Cada criterio
`[bloquea]` y cada umbral cuantificado del Segmento 10 se registra además como
objetivo medible en `nfr-requirements`, con identificador estable, valor
esperado y el comando que produce su valor real, para que aparezca como fila
propia en la `## Target Verification Matrix` de `build-and-test`; ningún
criterio `[bloquea]` se cierra con `N/A`.

**Tipos de prueba obligatorios pese a la estrategia.** La estrategia activa es
`Standard` (cinco a ocho pruebas por componente; unitarias más integración en
las fronteras). Además, y con independencia de la estrategia, `build-and-test`
genera instrucciones de prueba de **seguridad** (aislamiento entre tenants,
redacción de PII en cada punto de salida, casos adversariales de DS-6) y de
**rendimiento** (latencias de turno y de parada sobre DS-5, duración de la
corrida de evals), porque el PRD las marca como compuertas duras y como umbrales
publicables, no como aspiraciones.

**Definición de regresión.** Bloquea la entrega: (a) cualquier compuerta dura en
rojo, sin excepción ni promedio; (b) en métricas de **denominador grande**
—extracción por campo, fidelidad de la lectura de confirmación, latencias— una
caída mayor de 2 puntos porcentuales frente a la línea base versionada sin
explicación escrita; (c) en métricas de **nivel de caso** sobre DS-2, DS-3 y
DS-6, donde el denominador por idioma es pequeño, **cualquier caso que pase a
fallar** sin explicación escrita. La explicación nombra los identificadores de
los casos que cambiaron y su causa raíz según la taxonomía del PRD 11.3; una
explicación que no nombre casos no cuenta como explicación.

El umbral porcentual se reserva para el denominador grande porque en los
conjuntos pequeños no distingue señal de ruido:

| Dataset | Casos por idioma | Cuánto mueve un caso |
| --- | --- | --- |
| DS-2 (golden set de texto) | 30 | 3,3 pp |
| DS-3 (citación) | 20 | 5,0 pp |
| DS-6 (adversarial, v0) | 10 | 10,0 pp |

**Determinismo de la corrida.** La corrida de evals fija todo lo que se pueda
fijar: temperatura en 0 y semilla fija donde el proveedor lo permita, versión
del modelo anclada por identificador exacto (nunca un alias móvil), prompts y
rúbricas versionados en el repositorio, y el respondedor del asegurado por
reglas indexado por campo del PRD 11.1. Cuando un caso siga siendo inestable
entre corridas idénticas, se marca como inestable con su identificador en un
archivo versionado, deja de contar para la compuerta, se reporta aparte con esa
etiqueta y su estabilización se abre como trabajo; nunca se borra del set (P5).

**Compuerta en rojo por causa ajena al cambio.** Cuando la compuerta se pone
roja por una caída del proveedor, un cambio de versión del modelo o una cuota
agotada, se registra la causa y el identificador de la corrida, la corrida se
marca como **no comparable** y se repite; si sigue roja, bloquea. **El umbral no
se toca nunca** y la marca queda en el registro. Una compuerta que no se pudo
ejecutar se declara "no medida" en el reporte, nunca se omite.

**Juez descalibrado.** Los veredictos del juez (LLM) solo cuentan mientras su
coincidencia con las etiquetas humanas de DS-7 esté en el 85 % o por encima. Si
cae por debajo, o si cambia el modelo del juez o la rúbrica sin recalibrar, sus
veredictos dejan de contar: los criterios que dependen de él se reportan como
"no medida" con esa causa, no bloquean, y la recalibración se abre como trabajo
con fecha. Las compuertas duras juzgadas por código —citas inexistentes,
aislamiento, PII en trazas, esquema— no dependen del juez y siguen bloqueando.

**Presupuesto de la corrida.** La corrida de evals de texto tiene un objetivo de
10 minutos y su duración se mide y se publica como métrica desde la línea base
v0 (Segmento 10.5). El corredor admite ejecutar un subconjunto declarado y
reproducible; si la corrida completa deja de caber en el presupuesto o en los
límites del tier gratuito, la compuerta corre ese subconjunto declarado —nunca
se apaga— y la corrida completa pasa a ser obligatoria por hito y antes de
publicar cualquier línea base.

**Dónde corre la compuerta.** El ejecutor autoritativo es el flujo de GitHub
Actions sobre `main`, invocando el guion único de verificación. Dentro de este
intent, la etapa `build-and-test` ejecuta ese mismo comando. Las prácticas no
cambian cuando cambia el ejecutor: solo cambia quién lo dispara.

**Lo que no corre en cada corrida**: los golden sets de audio (DS-5, 20
grabaciones) corren por hito, no por cambio, porque el costo de voz está topado
y las grabaciones dependen de terceros.

**Paridad por idioma**: los mismos casos, las mismas métricas y las mismas metas
en español e inglés; el reporte muestra los dos lados a lado y nunca un promedio
combinado (P12).

**Herramientas**: el runner de pruebas del lenguaje elegido, más un framework
ligero de evals para la compuerta (`promptfoo` o `DeepEval`; la elección es un
ADR de Incepción) y Langfuse para la anotación humana. El corredor de evals se
invoca con un solo comando y ese comando está en el archivo de tareas y en el
README (M17).

## Deployment

Publicamos en vivo **el chat web, la bandeja de demostración y un enlace en vivo
de la voz con límite por visitante** (decisión de Miguel en Q5, opción `B`). La
condición para publicar cualquiera de los tres es la misma: compuertas duras en
verde y checklist del segundo día cumplido.

El enlace de voz solo es viable con estas condiciones, que se afirman como parte
de la práctica y no como recomendación:

- **Límite duro por visitante** (una llamada, con duración máxima) y por día,
  configurado **también en el proveedor** y no solo en la aplicación: un límite
  que vive únicamente en la aplicación falla abierto cuando lo que falla es la
  aplicación.
- **Techo mensual de gasto con corte automático**: alcanzado el tope, la voz
  rechaza llamadas nuevas con un mensaje honesto y el chat sigue vivo en el tier
  gratuito.
- **Alerta de consumo antes del techo**, no al llegar a él.
- Cada clave de proveedor lleva además su **propio tope o cuota configurado en
  el proveedor**, con claves separadas por uso (voz, chat, evals), para que una
  cuota agotada no tumbe las otras dos ni una clave filtrada agote el
  presupuesto entero.

Esta decisión mueve el enlace de voz desde `C5` ("podría", fuera del MVP por
costo) hacia lo intencionado, y choca con el tope de 5 USD que fijan D-015 y
M20. Esta etapa afirma la **condición de publicación**; la promoción de alcance
y el ajuste del tope son trabajo de `requirements-analysis` (2.3), y el enlace de
voz no se publica antes de que esa reconciliación exista.

**Checklist del segundo día**, cumplido antes de considerar terminado cualquier
despliegue: ping periódico contra la instancia dormida, límites de mensajes y de
llamadas por sesión y por día verificados en la aplicación y en el proveedor,
alerta de cuota activa, modo degradado probado y vuelta atrás probada.

Con un solo integrante, lo que sustituye al segundo firmante de `org.md` no es
otra persona sino **evidencia**: compuertas duras en verde, línea base de evals
publicada con su commit y su fecha, y checklist del segundo día cumplido. Un
despliegue no está hecho hasta que una prueba de humo lo confirma vivo en su
entorno, y cada cambio de despliegue lleva escrito su paso de vuelta atrás.

**Superficie pública y datos reales.** Desde el día en que el chat público
existe, entran datos de personas reales aunque el corpus sea sintético: la
redacción se aplica **antes de persistir**, no solo antes de exportar; la
retención está acotada por el reinicio nocturno de los datos de demostración; y
el primer mensaje declara que es una demostración con pólizas de ejemplo.

**Credenciales de demostración por tenant.** F8.7 publica credenciales a
propósito, lo que contradice literalmente nuestra regla de secretos. La
excepción se nombra con sus límites y no se arrastra: son **por tenant**, no
sirven fuera de su tenant, no se reutilizan para nada más, y se **rotan en el
reinicio nocturno**.

**Análisis dinámico proporcionado.** El set adversarial DS-6 se corre contra el
**despliegue vivo** en cada hito (semanas 6, 9 y 12), no solo contra el arnés
local; al menos RT-4 (acceso a caso ajeno) y RT-14 (fuga por trazas) se ejecutan
siempre en esa modalidad, porque las fallas de aislamiento y de tokens son tan a
menudo errores de configuración del despliegue como errores de código.

**Reparto con el intent `infra`.** El flujo de verificación de GitHub Actions
—pruebas, compuertas, escaneo de secretos, auditoría de dependencias— nace en
este intent, junto al primer código de aplicación. La **tubería de despliegue**,
el aprovisionamiento de entornos y la observabilidad de plataforma siguen siendo
el intent `infra` (D-014, semanas 3 y 4), y ese intent **invoca el mismo guion**
en lugar de crear un segundo juego de chequeos.

La landing (`site/`) se sigue publicando a mano con la CLI de Vercel desde
`site/` y **no comparte pipeline con el aplicativo**; su realineación al producto
real ocurre en las semanas 7 y 11 (D-013, M19).

## Code Style

Adoptamos el **formatter, el linter y el comprobador de tipos del lenguaje
elegido**. Su configuración vive en la raíz del repositorio y **declara su
alcance en el mismo commit en que se crea**: el prefijo del aplicativo, y solo
ese. `site/`, `.claude/`, `aidlc/`, `docs/` y `review/` quedan fuera por
construcción, no por una lista de excepciones que crece. Los tres se invocan
desde el archivo de tareas, corren en el flujo de GitHub Actions y bloquean la
entrega cuando fallan. El lenguaje lo fija un ADR de `domain-design`; para que
esta sección sea aplicable, ese ADR debe fijar además **versión del runtime**,
**gestor de dependencias y formato del lockfile** y **comprobador de tipos**.
Las convenciones de nombres son las idiomáticas del lenguaje; no inventamos
reglas de renombrado propias ni límites numéricos de tamaño que el linter ya
trae.

El linter corre con su **conjunto de reglas de seguridad activado** (Bandit o
las reglas `S` de Ruff en Python; `eslint-plugin-security` en Node). Un hallazgo
de seguridad se trata como compuerta dura, no como advertencia de estilo: no se
silencia con una supresión en línea sin una razón escrita al lado.

**El mismo commit** que introduce el primer archivo de código del aplicativo
introduce también: manifiesto y lockfile, configuración de formatter, linter y
tipos con su alcance declarado, archivo de tareas, guion de verificación y el
esqueleto de directorios por módulo. No hay un commit intermedio con código y
sin andamiaje.

### Convenciones independientes del lenguaje

Diez convenciones que sobreviven al ADR porque hablan de estructura, de nombres
y de fronteras. Cada una es un grep, una regla de importación o una decisión de
directorio.

1. **Un solo prefijo de ruta para el aplicativo.** El código del aplicativo vive
   bajo un único directorio de primer nivel en la raíz, hermano de `site/`,
   `docs/`, `.claude/` y `aidlc/`. Todo alcance de herramienta —formatter,
   linter, tipos, runner, cobertura— se declara como ese prefijo y nunca como
   una lista de exclusiones.
2. **Un módulo del PRD es un módulo del árbol, con el nombre del PRD.** Cada
   módulo del Segmento 9 (`MOD-01` a `MOD-15`) tiene directorio propio bajo el
   prefijo, nombrado por el módulo y no por la capa técnica. Un archivo
   pertenece a exactamente un módulo; cuando necesitaría pertenecer a dos, la
   razón se escribe en el ADR de la unit.
3. **Una sola grafía para los cuatro nodos.** Los nodos se llaman `intake`,
   `policy_verification`, `decision` y `compliance`. El mismo token nombra el
   directorio del módulo, el valor del enum de transición, el nombre del span en
   la traza y la etiqueta por nodo del reporte de evals y del dashboard.
4. **Tres registros de idioma, declarados una vez.** Identificadores, nombres de
   archivo, enums, campos del esquema, claves de configuración, `tenant_id` y
   logs técnicos: **inglés**. Todo texto que lee una persona no técnica:
   **catálogo de copy por idioma**, español e inglés, nunca en línea. Artefactos
   del flujo AI-DLC, comentarios y ADR: **español**. Los estados del caso y las
   categorías de decisión se escriben como enum en inglés, con la tabla de
   correspondencia con el término del PRD en un solo archivo junto a la
   definición del enum; la etiqueta que ve una persona se resuelve por el
   catálogo, nunca imprimiendo el valor del enum.
5. **Cuatro reglas de dirección de dependencias.** (a) El núcleo no importa
   canales: los canales importan el núcleo, nunca al revés. (b) El núcleo no
   importa proveedores: el SDK de STT, LLM, TTS o del almacén vectorial se
   importa únicamente dentro del adaptador de ese proveedor, y el núcleo depende
   de un puerto propio. (c) La función de transición es pura y cerrada: recibe
   solo campos del estado tipado, devuelve un valor del conjunto cerrado de
   nombres de nodo, y ningún cliente de LLM aparece en su cadena de llamadas.
   (d) El camino del turno no llama al trabajo de fondo: el manejador de turno
   de voz no invoca sincrónicamente verificación, reglas ni cumplimiento; lee lo
   precargado en el estado o emite una frase de espera.
6. **Conjunto de escritura por nodo.** Cada nodo declara qué campos del estado
   tipado escribe. El estado se modifica solo por el valor de retorno del nodo;
   ningún nodo muta el objeto compartido en el lugar, y dos nodos no escriben el
   mismo campo.
7. **Punto único de sesión de base de datos.** Toda consulta pasa por un único
   punto de adquisición de sesión que fija el `tenant_id` antes de devolverla.
   Ningún otro módulo abre una conexión, y no se construye SQL por
   concatenación.
8. **Manejo de errores en cuatro piezas.** (a) Taxonomía cerrada en la frontera
   del proveedor: cada adaptador traduce los errores de su SDK a `timeout`,
   `rate_limited`, `unavailable`, `invalid_response`, y el tipo del proveedor no
   cruza hacia el núcleo. (b) La política de fallo de cada nodo es un dato
   —tiempo máximo, un reintento, texto de degradación— aplicada por un ejecutor
   común; un nodo no captura su propio fallo para seguir adelante. (c) **"No hay
   cláusula" y "no pude verificar" son valores distintos** en el estado, en la
   traza y en el reporte de evals, y nunca se colapsan: colapsarlos contamina
   una métrica publicada con fallos de infraestructura. (d) Todo fallo deja
   rastro doble: un valor distinguible en el caso y un evento en la traza con el
   nodo, el tipo de error y el intento.
9. **Configuración por inquilino, sin ramas.** Ningún archivo del aplicativo
   contiene un `tenant_id` literal fuera del cargador de configuración y de las
   fixtures. Toda diferencia entre tenants —idioma por defecto, voz, reglas,
   políticas de cumplimiento, corpus, póliza de ejemplo, incluida la política de
   derivación siempre de la agencia— vive en la carpeta de configuración
   versionada del tenant. El cliente de cada proveedor se construye en un único
   lugar por uso, para que las claves separadas por uso sigan separadas en el
   código.
10. **Un solo archivo de tareas, contrato entre local y la tubería.** Toda acción
    que ejecuta una persona o el flujo de GitHub Actions —arrancar, correr
    pruebas, correr evals, generar datos, aprovisionar un tenant, formatear,
    analizar, verificar— tiene un comando nombrado en un solo archivo de tareas
    en la raíz. La tubería invoca esos mismos comandos y no mantiene su propia
    lista en línea.

Todo texto dirigido a una persona sale del **catálogo de copy por idioma**, con
un solo espacio de claves: apertura con divulgación, frases de espera, frases de
derivación, mensajes de degradación y de error, etiquetas de la bandeja. Ninguna
cadena visible se escribe en línea en un nodo o en un adaptador. La paridad
EN↔ES y las claves sin consumidor se comprueban sobre ese catálogo (es el fallo
que TD-01 y TD-02 muestran en la landing).

### Chequeos de contenido

Tres chequeos independientes del lenguaje, porque protegen principios y no
estilo. Se aplican sobre **el alcance que se publica**: código del aplicativo,
`README.md`, copy del producto, `site/` y salidas del sistema. La especificación
y los artefactos del flujo (`docs/`, `aidlc/`), que contienen esas frases
precisamente porque las prohíben, quedan fuera por una **lista de exclusiones
versionada** donde cada entrada lleva su razón. Sin ese alcance los dos primeros
arrancarían en rojo: hoy el de frases prohibidas coincide con cinco archivos
legítimos —incluido el PRD que define la prohibición— y el de ISO/ACORD con
diecisiete.

- **Frases prohibidas**: "cumple con" y "complies with" junto a NAIC, TCPA,
  EU AI Act, SOC 2 o HIPAA (P6, R9).
- **ISO y ACORD**: el chequeo distingue **estructura** (nombres de sección y
  numeración, permitidos y documentados en
  `docs/reference/estructura-poliza-iso-pap.md`) de **texto de cláusula**, que es
  lo prohibido (P8, W6).
- **Paridad de claves EN↔ES** en el copy visible, y claves sin consumidor (P12).

### Secretos y cadena de suministro

Los secretos y las claves de proveedor se leen siempre de variables de entorno o
de un gestor de secretos, nunca del código ni del repositorio, con claves
separadas por uso. La plantilla de variables requeridas se versiona como
`.env.example` —hoy el `.gitignore` ignora `.env.*` y hay que añadir la negación
`!.env.example`— y lista **nombres** de variables, nunca valores.

Todo código de aplicación nace con **manifiesto y lockfile con hashes de
integridad**; la instalación usa el modo reproducible del gestor, el que falla si
el lockfile no coincide, nunca una resolución libre. Las dependencias se auditan
contra vulnerabilidades conocidas en cada corrida del guion de verificación. La
licencia de cada dependencia y de cada recurso (voces, modelos, fuentes) se
registra con su atribución, porque el repositorio es candidato a publicarse en la
semana 12 (D-017); hay precedente bueno en `site/PHOSPHOR-LICENSE.txt`. El
identificador de modelo, el proveedor y sus parámetros viven en configuración
versionada: cambiarlos es un cambio de código que dispara la compuerta de evals.
Una dependencia nueva de runtime se justifica en una línea: qué hace, por qué no
la biblioteca estándar, y su licencia.

Los comentarios y la documentación describen **lo construido**: TD-03
—comentarios que hablan de cinco compuertas cuando hay dos, y de un paso de
despliegue que ya se hizo— es el ejemplo local de lo contrario, y es deuda que no
queremos reproducir en el aplicativo.
