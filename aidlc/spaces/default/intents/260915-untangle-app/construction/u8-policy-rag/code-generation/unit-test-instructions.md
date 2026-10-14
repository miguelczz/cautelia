# Instrucciones de pruebas — U8 `policy-rag`

U8 es de la **rama evaluada** y realiza M4 y M9 (`team.md`). Sus casos previos
son los **40 casos de DS-3**, que no existen todavía: se escriben en el paso 2,
se corren y se comprueba que fallan antes de implementar nada. Las capas que la
sostienen van por la rama determinista, cada una con sus pruebas antes de pasar
a la siguiente. Estrategia `Standard`: de cinco a ocho pruebas por componente.

## Cómo correr solo lo de U8

| Qué | Comando | Lo que corre por debajo |
| --- | --- | --- |
| Pruebas de la unidad | `mise run test:u8`, tarea nueva del paso 1 | Las unitarias de `policy_rag/` y las de integración de U8 |
| Ingerir el corpus | `mise run corpus:ingest`, tarea nueva del paso 3 | Manifiesto, validación e indexación |
| Casos de arranque | `mise run evals:run -- --subset smoke` | Los 52 casos que ya existen |
| La compuerta | `mise run evals:gate` | Corrida, comparación y segundo detector |

Mientras trabaja, el agente corre solo `test:u8` y el subconjunto de arranque.
La suite completa y `scripts/verify.sh` corren una vez, al final de cada tanda.

## Lo que cada regla de precedencia exige

Ajuste que salió de la evaluación de U9: **cada regla de precedencia o de
apagado lleva una prueba que la aísla**, escrita antes del código. En esta
unidad son seis:

- una cláusula de otra aseguradora que puntuaría primero **no aparece**, porque
  el filtro corre antes de ordenar (BR2.1);
- un identificador que existe en el corpus pero no se recuperó para esa
  respuesta **se rechaza** (BR3.1);
- una cláusula citada que un endoso vigente modifica **se rechaza** si la
  respuesta no cita también el endoso (BR3.5);
- una pregunta sin cláusula da `no_clause_found` y un fallo de recuperación da
  `unverifiable`, y **ninguna métrica los suma** (BR3.4);
- una cláusula que entró por el cierre de relaciones **no cuenta** en la métrica
  de recuperación (BR2.4);
- una pregunta en el idioma que no es el del corpus recibe la cláusula en su
  idioma, el resumen en el de la pregunta y el aviso, **y el texto de la
  cláusula no se traduce** (BR5.8).

## Coberturas esperadas

**80 % o más agregado** con `mise run cov`, y **80 % o más en
`policy_rag/citations/`**, que es módulo crítico por la lista de `team.md`. Sin
exclusiones nuevas.

## Dobles de prueba

- **Sin proveedor:** ninguna prueba llama al modelo de embeddings ni al
  generador. El `Embedder` se sustituye por un doble determinista con vectores
  sembrados, elegidos para que el orden de la búsqueda vectorial sea conocido y
  se pueda afirmar sobre la fusión. La ingesta real con la clave se corre en la
  sesión local, una vez.
- **Con base de datos:** U8 crea siete tablas, así que sus pruebas de
  aislamiento, borrado y migración son de integración y necesitan PostgreSQL con
  pgvector. Se **escriben** en la nube y se **corren** en la sesión local.
- **Sistema de archivos:** las pruebas de ingesta leen corpus sembrados en un
  directorio temporal, nunca `app/data/` directamente, salvo la prueba de
  CG-U8-2, que es justamente la que lo comprueba.

## Datos de prueba

- Los 40 casos de DS-3, escritos en el paso 2 contra el corpus real.
- Corpus sembrados mínimos en directorio temporal para la ingesta: un formulario
  base, dos endosos, una versión anterior y un distractor declarado.
- El corpus de inyección nuevo, en `app/evals/fixtures/injection-corpus/`, que
  se crea en el paso 7 con su inquilino efímero y que ninguna corrida ordinaria
  toca.
- Fixtures de colisión entre aseguradoras, incluido el número de póliza que
  existe en dos (`POL-480915`), que ya vienen de U7 en `ds8_isolation.json`.

Nada de datos de personas reales: todo sale del generador sembrado de U7.
