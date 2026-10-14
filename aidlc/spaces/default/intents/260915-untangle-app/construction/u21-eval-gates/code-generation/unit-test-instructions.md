# Instrucciones de pruebas — U21 `eval-gates`

U21 es de la **rama evaluada** sin conducta propia (`project.md`): su caso previo
es una corrida de los casos que ya existen —los 52 del subconjunto de arranque—
que se comprueba que falla antes de implementar la compuerta. No se inventa
ningún caso de golden set nuevo. Las capas que la sostienen van por la rama
determinista, cada una con sus pruebas antes de la siguiente. Estrategia
`Standard`: de cinco a ocho pruebas por componente.

## Cómo correr solo lo de U21

| Qué | Comando | Lo que corre por debajo |
| --- | --- | --- |
| Pruebas de la unidad | `mise run test:u21`, tarea nueva del paso 1 | Las unitarias de `evals/gates/` |
| La compuerta completa | `mise run evals:gate`, tarea nueva del paso 3 | Corrida, comparación contra la línea base y segundo detector |
| Casos de arranque | `mise run evals:run -- --subset smoke` | Los 52 casos que ya existen |

Mientras trabaja, el agente corre solo `test:u21` y el subconjunto de arranque.
La suite completa y `scripts/verify.sh` corren una vez, al final de cada tanda.

## Lo que cada regla de precedencia exige

Ajuste que salió de la evaluación de U9: **cada regla de precedencia o de
apagado lleva una prueba que la aísla**, escrita antes del código. En esta unidad
son cuatro:

- un caso que pasaba y falla, sin explicación, deja la compuerta en rojo;
- el mismo caso, con explicación que lo nombra, la deja en verde;
- el mismo caso, marcado inestable, no cuenta para la compuerta;
- un criterio con el juez descalibrado sale "no medida" y **no** apaga las
  compuertas juzgadas por código.

## Coberturas esperadas

**80 % o más agregado** con `mise run cov`. `evals/gates/` no es módulo crítico
por la lista de `team.md`, pero la compuerta no se puede sostener con menos que
las demás: se espera 80 % o más también ahí, sin exclusiones nuevas.

## Dobles de prueba

- **Sin modelo:** ninguna prueba llama al juez de verdad. La calibración se
  prueba con veredictos grabados y etiquetas sembradas; el intervalo de Wilson,
  contra valores conocidos calculados a mano.
- **Sin base de datos:** esta unidad no toca PostgreSQL. Todo son archivos.
- **Sistema de archivos:** las pruebas escriben en un directorio temporal, nunca
  en `app/evals/`.

## Datos de prueba

Los 52 casos del subconjunto de arranque, líneas base y calibraciones sembradas
en el directorio temporal, y canarios con forma de teléfono, cédula y placa, sin
datos de personas reales.
