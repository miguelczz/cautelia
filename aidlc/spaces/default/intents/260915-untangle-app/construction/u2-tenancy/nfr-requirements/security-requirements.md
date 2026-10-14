# Requisitos de seguridad — U2 `tenancy`

U2 **es** la superficie de seguridad del aplicativo. Es la única unidad que abre
sesiones de base de datos, la única que emite y verifica credenciales, y la
única que decide qué ve cada quien. Todo lo que las otras veinte unidades
construyan encima hereda lo que aquí se garantice o se deje sin garantizar.

**Fuentes consumidas.** `../functional-design/functional-spec.md` (los siete
flujos y el estado del enlace), `../functional-design/rules.md` (las veintisiete
reglas), `../../../inception/requirements-analysis/requirements.md` (FR9.1 a
FR9.6, FR8.7 y los objetivos NFR10, NFR12, NFR18 y NFR19),
`../../../inception/contract-design/contract-summary.md` (C-07, C-10, C-11,
C-25 y C-30) y `../../../../codekb/untangle/technology-stack.md`.

## Modelo de amenazas de esta unidad

Aplicado con STRIDE sobre lo que U2 expone: la base de datos, las credenciales y
los enlaces.

| Amenaza | Qué podría pasar aquí | Control |
| --- | --- | --- |
| Divulgación de información | Una consulta sin filtro devuelve filas de otra aseguradora, o una tabla nueva nace sin política | SEC-U2.1, SEC-U2.3, SEC-U2.12 |
| Elevación de privilegios | Una credencial de agente de cuenta decide un caso; o el rol de base de datos puede saltarse el aislamiento y toda la suite pasa midiendo nada | SEC-U2.4, SEC-U2.7 |
| Suplantación | Una credencial fabricada o alterada se acepta; una clave de firma filtrada sirve para las dos cosas | SEC-U2.5, SEC-U2.6, SEC-U2.10 |
| Manipulación | Una consulta armada por concatenación convierte un dato de entrada en instrucción | SEC-U2.2 |
| Repudio | Un intento de acceso a una aseguradora ajena no deja rastro y nadie lo detecta | SEC-U2.11 |
| Divulgación por persistencia | Un enlace o una clave de navegador sobreviven al reinicio nocturno | SEC-U2.13 |
| Denegación de servicio | Una carpeta de aseguradora rota impide arrancar a las otras dos | BR4.1 (diseño funcional) |

La amenaza con nombre propio en este proyecto es la segunda, y no por el
privilegio en sí: **un rol de base de datos que pueda saltarse el aislamiento
hace que las pruebas de aislamiento pasen sin que exista aislamiento.** Es el
fallo que no avisa, y por eso SEC-U2.4 comprueba el rol vivo y no el archivo
donde se escribió.

## Objetivos medibles heredados de Incepción

Seis filas, cada una con su valor esperado y el comando que produce su valor
real. Van a la matriz de verificación de `build-and-test` tal cual.

| ID | Objetivo | Valor esperado | Comando que produce el valor real |
| --- | --- | --- | --- |
| NFR10.1 | Filas de otra aseguradora en una consulta sin filtro, desde una sesión fijada | Exactamente 0 | `mise run test:u2` |
| NFR10.2 | Pruebas de aislamiento en verde | 100 %, sin promedio ni excepción | `mise run test:u2` |
| NFR10.3 | Casos o pólizas ajenas obtenidas por RT-4 contra el despliegue vivo, por idioma | Exactamente 0 en español y 0 en inglés | `mise run evals:run -- --subset rt4-live` |
| NFR12.1 | Escenario RT-4 del conjunto adversarial en cada entrega | 0 accesos concedidos | `mise run evals:run -- --subset smoke` |
| NFR18.2 | Cobertura de líneas del módulo de aislamiento (módulo crítico) | Mayor o igual a 80 % | `mise run cov` |
| NFR19.1 | Enlaces de caso y claves de navegador del día anterior que sobreviven al reinicio | Exactamente 0 | `mise run test:u2` |

**NFR10 es compuerta dura.** Un solo fallo detiene la entrega. No se promedia,
no se reporta como porcentaje agradable y el umbral no se toca nunca.

**NFR12.1 cubre solo la parte de RT-4.** El resto de NFR12 —que ninguna
respuesta obedezca una instrucción inyectada— es de U10 y U21. U2 no puede
verificarlo ni comprometerlo.

**NFR18.2 se enciende aquí.** U1 dejó escrito que el piso por módulo crítico
"hoy no aplica porque los módulos críticos llegan con U2, U4, U8 y U9". U2 es el
primero de los cuatro: a partir de esta unidad, el comando de cobertura compara
también el módulo de aislamiento contra su propio 80 %, además del agregado que
mide NFR18.1.

## Controles

| ID | Control | Valor esperado | Cómo se comprueba |
| --- | --- | --- | --- |
| SEC-U2.1 | Aislamiento en la base de datos, no solo en el código | Toda tabla del aplicativo con aislamiento habilitado, forzado y política de aseguradora; la lista de exclusión lleva su razón por entrada | `mise run rls:check`, que pregunta al catálogo vivo |
| SEC-U2.2 | Punto único de sesión y cero SQL concatenado | Ninguna apertura de conexión fuera del punto único; ninguna consulta armada por concatenación | Contrato de importación y regla de seguridad del linter, dentro de `mise run lint` |
| SEC-U2.3 | Consulta cruzada vacía | 0 filas ajenas con la aseguradora fijada; 0 filas sin aseguradora fijada, con las colisiones a propósito de DS-8 | `mise run test:u2` |
| SEC-U2.4 | Rol de base de datos sin privilegio de salto | El rol del aplicativo no puede saltarse las políticas, y las pruebas se conectan con **ese** rol y no con el superusuario | `mise run rls:check`, consultando el rol vivo de la conexión |
| SEC-U2.5 | Dos claves de firma, una por uso | Dos variables distintas; la clave de enlaces no valida una credencial de bandeja y la de bandeja no valida un enlace | `mise run test:u2` y `mise run env:check` |
| SEC-U2.6 | Rechazo indistinguible | Credencial caducada, alterada y de otra aseguradora producen una respuesta idéntica, byte a byte, desde la pantalla y desde la interfaz programática | `mise run test:u2` |
| SEC-U2.7 | Permisos por rol y acción | Toda pareja no declarada se deniega; el rol de agente de cuenta no decide un caso, ni por pantalla ni por petición directa | `mise run test:u2` |
| SEC-U2.8 | Enlace de caso | Una hora de vida, un solo caso, reutilizable mientras valga, y cuatro causas de rechazo indistinguibles entre sí | `mise run test:u2` |
| SEC-U2.9 | Ninguna credencial publicada | 0 hallazgos en el repositorio, el README y las páginas públicas | `mise run secrets` y `mise run content:check` |
| SEC-U2.10 | Rotar invalida en el acto | Tras rotar una clave de firma, toda credencial y todo enlace firmados con la anterior se rechazan; no hay ventana de gracia | `mise run test:u2` |
| SEC-U2.11 | Rastro de cada rechazo | Todo rechazo deja un evento con la aseguradora que se intentó abrir, el rol que afirmaba la credencial y la causa real, por el punto único de salida | `mise run test:u2` |
| SEC-U2.12 | Migraciones con su aislamiento en la misma revisión | Una revisión que cree una tabla sin su política hace fallar la aserción; subir, bajar y volver a subir queda en verde contra una base efímera con el rol del aplicativo | `mise run migrate:check` |
| SEC-U2.13 | Borrado de datos de visitante | Los dos purgadores de U2 declarados explícitamente; una tabla con datos de visitante sin purgador hace fallar la prueba | `mise run test:u2` |
| SEC-U2.14 | Ningún identificador de aseguradora literal | 0 coincidencias fuera del cargador de configuración y de las fixtures | Chequeo del guion de verificación |

Tres de estos controles **interrogan a la herramienta en vez de leer el archivo
donde se escribió el ajuste**: SEC-U2.1 pregunta al catálogo de la base qué
tablas hay, SEC-U2.4 pregunta qué privilegios tiene el rol vivo, y SEC-U2.5
comprueba que una clave no valida lo de la otra probándolo. Es la lección del
2026-09-20, cuando dos ajustes de cadena de suministro estaban escritos en un
archivo que la herramienta no leía y nada avisaba.

## Decisiones de esta etapa

| ID | Decisión | Por qué | Origen |
| --- | --- | --- | --- |
| NFR-U2-1 | Dos claves de firma, una para credenciales de bandeja y otra para enlaces de caso | Radios de daño distintos: la de enlaces abre casos cuyo identificador ya se conozca, la de bandeja fabrica un ajustador en cualquier aseguradora | Respuesta Q1 |
| NFR-U2-2 | Cada rechazo deja un evento con aseguradora, rol afirmado y causa real | Una fuga entre aseguradoras sin rastro es indetectable, y el identificador de aseguradora no es un dato personal | Respuesta Q2 |
| NFR-U2-3 | Rotar una clave invalida en el acto lo firmado con la anterior, sin ventana de gracia | Las credenciales duran doce horas y los enlaces una: el costo real es volver a emitir, y una clave comprometida deja de servir al instante | Respuesta Q3 |
| NFR-U2-4 | PyJWT para la credencial de bandeja; firma con la biblioteca estándar para el enlace de caso | El tutorial de seguridad oficial de FastAPI instala `pyjwt` e importa `jwt`, así que es lo que reconoce quien evalúe el repositorio; el enlace no necesita formato estándar porque nadie externo lo interpreta | Respuesta Q4 |

## Datos personales

U2 **no guarda datos de personas**, y esa ausencia es deliberada:

- La clave del navegador guarda su resumen, el origen y dos instantes. Ni
  nombre, ni correo, ni dirección de red.
- El enlace de caso guarda el resumen de su token, nunca el token: quien lea la
  tabla no puede reconstruir ningún enlace.
- Las credenciales de la bandeja no se guardan en ninguna tabla.
- Los eventos de rechazo de SEC-U2.11 llevan identificador de aseguradora y rol,
  que no son datos personales, y salen por el punto único de salida como todo lo
  demás.

Los dos tipos de dato que **sí** son de visitante —enlaces y claves de
navegador— tienen su purgador declarado y mueren en el reinicio nocturno
(SEC-U2.13, NFR19.1).

## Lo que no le toca a esta unidad

La redacción de datos personales y su segundo detector (U3), la guardia de
salida y los escenarios adversariales de inyección (U10 y U21), los límites por
visitante y por día de las superficies públicas (U13 y U17), el aislamiento de
las tablas de puntos de control del grafo (U12, que elegirá su mecanismo) y el
reinicio nocturno que ejecuta el contrato de borrado (U20). U2 no puede
comprometerlos ni verificarlos.
