# Instrucciones de pruebas — U9 `rules-decision`

U9 es de la **rama evaluada** (M5): los casos de DS-2 se escriben primero y se
ven fallar. Las capas que los sostienen (tabla, carga, evaluación y nodo) van
por la rama determinista, cada una con sus pruebas antes de la siguiente.
Estrategia `Standard`: de cinco a ocho pruebas por componente.

## Cómo correr solo lo de U9

| Qué | Comando | Lo que corre por debajo |
| --- | --- | --- |
| Pruebas de la unidad | `mise run test:u9`, tarea nueva del paso 1 | Las pruebas unitarias de `rules` y del nodo `decision`, más las de integración de la tabla |
| Casos de DS-2 de U9 | `mise run evals:run -- --subset smoke` | Los criterios de U9, uno por idioma |
| Aislamiento de la tabla | `mise run rls:check` | La aserción de esquema y de llaves compuestas |

Mientras trabaja, el agente corre solo `test:u9` y los casos de U9. La suite
completa y `scripts/verify.sh` corren una vez, al final de cada tanda.

## Coberturas esperadas

**80 % o más agregado** con `mise run cov`, y el motor de reglas en su piso
propio del 80 %, porque es módulo crítico. Sin exclusiones nuevas.

## Dobles de prueba

- **Sin modelo:** ninguna prueba ni sonda llama a un proveedor, y un espía en la
  fábrica lo comprueba.
- **Base:** la de pruebas de integración, con la transacción revertida al
  terminar.

## Datos de prueba

Los casos sembrados de U7 y los campos de cada caso de DS-2, sin datos
personales reales.
