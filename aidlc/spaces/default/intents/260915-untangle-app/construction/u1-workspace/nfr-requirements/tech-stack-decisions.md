# Decisiones de stack — U1 `workspace`

Qué herramientas fija esta unidad y por qué. Las elecciones grandes ya están
tomadas en los ADR de Domain Design y en su enmienda del 2026-09-17; aquí solo se
registra **lo que U1 instala en el primer commit** y la meta de cobertura que
Units Generation le asignó (NFR18).

**Fuentes consumidas.** `../functional-design/functional-spec.md` (el alcance del
andamiaje y el comando único), `../functional-design/rules.md` (BR1.1, BR3.2 y
BR3.3, que la herramienta tiene que poder comprobar),
`../../../inception/requirements-analysis/requirements.md` (NFR18 y NFR21),
`../../../inception/contract-design/contract-summary.md` (C-24 raíz de
composición, C-25 configuración, C-28 artefactos generados y su chequeo de
deriva) y `../../../../codekb/untangle/technology-stack.md` (el repositorio solo
tiene la landing estática; el andamiaje del aplicativo se **crea**, no se
verifica).

## Lo que U1 instala

| Pieza | Qué se fija | De dónde viene |
| --- | --- | --- |
| Versiones de herramientas | Python, gestor de paquetes de Python, Node y su gestor, todos anclados en un archivo de versiones en la raíz | ADR-002 y su enmienda |
| Dos proyectos | Uno de Python y uno de TypeScript, sin espacios de trabajo ni orquestador de monorepo | ADR-002 |
| Archivo de tareas | Un solo archivo en la raíz con el nombre de cada acción; la tubería invoca esos comandos y no mantiene su propia lista | BR1.1, convención 10 del equipo |
| Guion de verificación | Uno solo, en el orden que fija la práctica del equipo | `team.md`, Way of Working |
| Formatter, linter y comprobador de tipos | Con su alcance declarado al prefijo del aplicativo, y el conjunto de reglas de seguridad del linter activado | `team.md`, Code Style |
| Reglas de importación | Contratos comprobables por herramienta, con las capas y prohibiciones de ADR-001 | ADR-001, enmienda |
| Cobertura | Con umbral en el manifiesto que **hace fallar el comando** | NFR18 |
| Flujo de integración continua | Invoca el guion único, con el escaneo de secretos como primer trabajo | `team.md` |
| Servicios locales | Base de datos con su extensión vectorial y backend de trazas, **anclados por versión exacta de imagen**, no por etiqueta móvil | NFR21: una versión que cambia sola mueve el tiempo de arranque entre máquinas |

## NFR18 — El piso de cobertura

| ID | Qué mide | Valor esperado | Comando que produce el valor real |
| --- | --- | --- | --- |
| NFR18.1 | Cobertura de líneas **agregada** sobre el código del aplicativo | **80 % o más** | El comando de cobertura del archivo de tareas: corre las dos herramientas, combina sus reportes y compara el agregado contra el umbral; devuelve distinto de cero si no se alcanza |
| NFR18.2 | Cobertura de líneas en cada módulo crítico | **80 % o más** por módulo | El mismo comando, con el umbral por módulo; hoy no aplica porque los módulos críticos (aislamiento, caso, corpus y citas, reglas) llegan con U2, U4, U8 y U9 |
| NFR18.3 | Alcance del cálculo | Lista de exclusión **versionada**: la landing, el corpus y los datasets generados, y las migraciones | La propia configuración, revisada en el guion de verificación |

**Cómo se agrega** (decisión Q1 de esta etapa): un **solo número ponderado por
líneas**. Cada herramienta emite su reporte en un formato común, un paso los
combina sumando líneas cubiertas sobre líneas totales de los dos proyectos, y ese
número se compara contra el 80 %. No se promedian porcentajes: un proyecto de 200
líneas no puede pesar lo mismo que uno de 20.000.

El piso agregado y el piso por módulo crítico **son dos comprobaciones distintas
y ambas bloquean**. La interfaz y los adaptadores de proveedor pueden quedar por
debajo del 80 % mientras el agregado se cumpla; los módulos críticos, no.

## Lo que esta unidad no decide

El lenguaje, los proveedores, el framework web, la base de datos y la librería
del grafo ya están decididos en los ADR de Domain Design. U1 los **instala**; no
los reabre. Si uno resulta mal fundado, se reabre el ADR, no este documento.

## Pendiente que hereda Construcción

| Pregunta | Dónde se resuelve |
| --- | --- |
| Lista exacta de navegadores declarados (PA-4), con el dato de WebRTC del experimento de voz | `nfr-requirements` de U6 |
| Subconjunto declarado de la corrida de la compuerta (PA-11) | `nfr-requirements` de U21 |
