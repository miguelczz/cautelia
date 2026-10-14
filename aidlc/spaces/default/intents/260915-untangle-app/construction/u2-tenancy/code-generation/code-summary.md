# Resumen de la generación — U2 `tenancy`

El aislamiento entre aseguradoras, la identidad del personal de la bandeja y el
acceso del visitante. Los 36 pasos del plan aprobado están hechos y el guion de
verificación corre en verde en sus nueve pasos.

## Lo que se midió, de verdad

Cifras de corridas reales del 2026-09-20, repetidas por el conductor después de
que el desarrollador entregara. Ninguna es estimación.

| Qué | Resultado | Cómo se obtuvo |
| --- | --- | --- |
| Pruebas de Python | **142 pasan**, 0 fallan, 7,53 s | `uv run --project app/backend pytest -c app/backend/pyproject.toml app/backend/tests -q` |
| Pruebas de TypeScript | 2 pasan, 0 fallan | `mise run cov` |
| Aporte propio de U2 | **76 pruebas** — 69 de la unidad más 7 de la sonda de RT-4 | `mise run test:u2` y `pytest .../test_live_probes.py` |
| Cobertura agregada (NFR18.1) | **86,43 %** (2179/2521 líneas), piso 80 % | `mise run cov` |
| Cobertura del módulo de aislamiento (NFR18.2) | **92,30 %** (743/805 líneas), piso 80 % | El mismo comando |
| Guion de verificación | **Los nueve pasos en verde**, código 0, 19,29 s | `./scripts/verify.sh` |
| Bases efímeras por corrida completa | **4** | Contando `tenancy.ephemeral_database_started` en el guion y en la suite con `-s` |
| Subconjunto de arranque | 12 casos, 6 por idioma, 0 fallan, 0 no medidos, 0,11 s | `mise run evals:run -- --subset smoke` |

La rama evaluada cerró con evidencia de rojo a verde, no con una afirmación: las
pruebas de aislamiento fallaron antes de existir la pieza
(`ImportError: cannot import name 'ephemeral'`) y el caso RT-4 falló antes de
registrarse su criterio (`LookupError: el criterio 'rt4_foreign_case_denied' no
esta registrado`). Las 7 de aislamiento pasan ahora.

El plan esperaba **entre 35 y 50 pruebas** para la unidad. Salieron 76. La
diferencia está en los contratos de importación —cada uno pide su violación
plantada y su línea base sin violación— y en la sonda de RT-4, que no estaba
contada como componente.

## Lo que quedó construido

### Aislamiento en la base de datos

| Pieza | Dónde |
| --- | --- |
| Las dos tablas, con aislamiento habilitado, forzado y su política **literal en la misma revisión** | `app/backend/migrations/versions/u2_tenancy_0001_tenancy_tables.py` |
| Punto único de sesión que fija la aseguradora antes de devolver | `app/backend/src/untangle/tenancy/session.py` |
| Aserción que le pregunta al catálogo vivo y al rol vivo | `.../tenancy/rls_assertion.py` |
| Rol del aplicativo sin privilegio de salto, creado por el **mismo guion** que monta el entorno local y la base efímera | `scripts/db-init/01-app-role.sh` |
| Base efímera con la imagen anclada a la del entorno local | `.../tenancy/ephemeral.py` |
| Comandos `rls-check` y `migrate-check` | `.../tenancy/cli.py` |

### Identidad y acceso

| Pieza | Dónde |
| --- | --- |
| Credencial de bandeja: cuatro campos, doce horas, firmada | `.../tenancy/staff_identity.py` |
| Tabla versionada de rol y acción; toda pareja no declarada se deniega | `app/config/role-permissions.yaml` |
| Enlace de caso: una hora, un caso, reutilizable mientras valga | `.../tenancy/visitor_access.py` |
| Clave de navegador, una fila por aseguradora | `.../tenancy/visitor_access.py` |
| Purgadores de datos de visitante, declarados explícitamente | `.../tenancy/purge.py` |
| Superficie única del módulo | `.../tenancy/api.py` |

### Configuración y fronteras

| Pieza | Dónde |
| --- | --- |
| Carga por aseguradora; una carpeta rota no tumba a las otras | `.../tenancy/config.py` |
| Las tres carpetas de aseguradora | `app/config/tenants/{stonecroft,sunmeadow,knotwell}/tenant.yaml` |
| Chequeo de identificadores literales fuera de sitio | `.../workspace/tenancy_literals.py` |
| Los tres contratos de importación, con violación plantada | `app/backend/.importlinter`, `app/backend/tests/integration/u2/test_import_contracts.py` |
| Sonda de RT-4 contra un despliegue vivo | `.../evals/live_probes.py` |

## Decisiones de implementación que conviene conocer

- **Tres chequeos nuevos interrogan a la herramienta**, no leen el archivo donde
  se escribió la intención: `rls:check` le pregunta al catálogo y al rol vivos,
  `migrate:check` sube, baja y vuelve a subir contra una base virgen, y
  `tenancy:literals` busca identificadores de aseguradora fuera de sitio. El
  tercero **se encontró a sí mismo** en un comentario la primera vez que corrió,
  que es exactamente lo que tenía que hacer.
- **Dos detalles de seguridad por encima del plan**, cada uno con su razón
  escrita: las claves de firma exigen 32 bytes mínimo (RFC 7518 §3.2 — PyJWT
  solo avisa, y un aviso en un registro que nadie lee no es un control), y la
  política lleva `WITH CHECK` además de `USING`, porque sin él el aislamiento
  sería de solo lectura y cualquiera podría sembrar filas en la aseguradora de
  al lado.
- **Los identificadores de regla son de la unidad, no del proyecto.** El `BR1.1`
  de U1 (un solo comando corre las evaluaciones) y el `BR1.1` de U2 (toda
  consulta pasa por el punto único de sesión) son reglas distintas con el mismo
  número. Es el formato `BR{grupo}.{secuencia}` que pide la etapa y que el
  comprobador de trazabilidad reconoce, y lo que los desambigua es el campo
  `unit` del mismo `traceability.json`. Queda dicho aquí para que nadie lo trate
  como colisión cuando `build-and-test` junte las 22 unidades.

## Huecos y desviaciones, dichos

### 1. RT-4 queda "no medida", no en verde

`mise run evals:run -- --subset rt4-live` devuelve los dos casos como
`not_measured / target_unavailable` y marca la corrida **no comparable**. La
causa es de alcance y no de código: la decisión CG-U2-1 deja la ruta HTTP a U14,
así que todavía no hay despliegue vivo al que apuntar.

Lo que sí está probado es **la sonda**: siete pruebas en
`app/backend/tests/unit/evals/test_live_probes.py` la ponen en verde contra un
despliegue correcto y en rojo ante las tres formas de responder mal —conceder
acceso, distinguir causas, responder algo que no es un 404—. La evidencia de
rojo a verde que exige el contrato de pruebas la cargan DS-8 y las pruebas de
aislamiento; RT-4 se mide por hito, como dice BR1.9.

En `traceability.json` esto queda como `Deferred` con su objetivo, no como `OK`.

### 2. Las bases efímeras son cuatro, no dos

`../infrastructure-design/correcciones-tras-revision.md`, hallazgo R-03, dice que
una corrida completa levanta "hasta dos". Medidas, son cuatro:

| Quién la levanta | Cuántas |
| --- | --- |
| La suite: una compartida por la sesión de pruebas | 1 |
| La suite: la prueba del comando `migrate-check`, que necesita una base virgen | 1 |
| El paso 6 del guion: `rls:check` invocado solo | 1 |
| El paso 6 del guion: `migrate:check` invocado solo | 1 |

El reparto por comando de la tabla R-03 es correcto; lo que no cuadraba era la
suma, porque no contaba que el guion invoca los dos comandos **además** de
correr la suite. Dos de las cuatro no se ven en la salida del guion porque el
runner de pruebas captura su registro; aparecen al correr la suite sin captura.

### 3. Dos defectos de U1 que U2 destapó, los dos corregidos

Ninguno era visible mientras U1 fuera lo único que había.

**El runner de pruebas no encontraba su configuración.** Invocado desde la raíz
sin decirle dónde está, corría en modo síncrono. U1 no tenía ninguna prueba
`async`, así que nadie lo notó; U2 tiene 25. Reproducido hoy con la invocación
vieja: **1 falla, 115 pasan, 26 errores**. Las tareas ahora pasan
`-c app/backend/pyproject.toml`.

**La cobertura tampoco encontraba la suya**, así que medía con los archivos de
prueba dentro —cubiertos al 100 % por construcción— y con la lista de exclusión
ignorada. Las tareas ahora pasan `--cov-config`.

**Esto significa que la cifra de cobertura que U1 publicó no era la real.**
Medido volviendo al commit de U1 (`de4d518`) en un árbol aparte y corriendo la
**misma puerta de cobertura del proyecto** con la configuración explícita:

| | Líneas | Cobertura |
| --- | --- | --- |
| Lo que U1 publicó | 1882/2090 | **90,05 %** |
| Lo real en ese mismo commit | 1260/1468 | **85,83 %** |

Las 622 líneas de diferencia en el denominador son los archivos de prueba, que
se estaban contando como código del aplicativo. La inflación fue de **4,22
puntos porcentuales**. El piso del 80 % se cumplía de las dos formas, así que
**no pasó nada que no debiera pasar**: lo que falló fue la cifra publicada, no la
compuerta. Aun así es exactamente el número maquillado que este proyecto no
quiere arrastrar, y por eso queda escrito con su medición.

### 4. `allow_indirect_imports = true` en dos contratos prohibidos

Sin esa línea, el contrato "ningún módulo abre una conexión fuera del punto único
de sesión" se habría roto con **la primera unidad que hiciera lo correcto**:
importar `tenancy.api`, que alcanza el mapeador por definición. Un contrato que
se rompe al usarlo bien se debilita bajo presión en vez de a la vista. Lo
prohibido sigue siendo el import directo, que es el que permite construirse un
motor por fuera. La razón está escrita al lado en `app/backend/.importlinter`.

## Lo que cambió tras la revisión

La revisión asesora devolvió `READY` con un hallazgo `Minor`, correcto: la fila
de `SEC-U2.5` en `traceability.json` apuntaba solo a la prueba que demuestra que
una clave no valida lo firmado por la otra, y se dejaba fuera la mitad que
comprueba que las dos variables existen. Es la tercera vez en esta unidad que se
cae la misma mitad del par. Aplicado: la fila lleva ahora su nota con los dos
comandos.

Al validar el archivo corregido apareció algo que la revisión no miraba: el
comprobador de trazabilidad esperaba siete identificadores más —`AC3.8.1` a
`AC3.8.6` y `NFR12.1`— que no son de esta unidad. En vez de dejarlos ausentes
sin rastro, se declaran con su razón y su dueño:

| Identificadores | Por qué no son de U2 |
| --- | --- |
| `AC3.8.1` a `AC3.8.6` | US3.8 está asignada a U14 `inbox`. U2 emite y valida el enlace; el recorrido de la pantalla y la ruta HTTP llegan con U14 |
| `NFR12.1` | No es de U2 según la corrección R-02 de `nfr-requirements`, comprobada contra `stories.md`. Sobrevive en el `reverse` de `nfr-design`, congelado por su revisión. Su dueño es U10 |

Una funcionalidad que simplemente no aparece es distinta de una excluida a
propósito, y la diferencia solo se nota cuando ya es tarde. Con esto el
comprobador pasa con 64 filas y cero hallazgos.

## Lo que esta unidad no construye

Las pantallas de la bandeja y del visitante (U14, U6), la ruta HTTP que canjea el
enlace (U14), el reinicio nocturno que llama a los purgadores (U20), el corpus y
las pólizas de ejemplo (U7) y el aislamiento de las tablas de puntos de control
del grafo (U12). Cada una llega con su unidad y con sus pruebas.
