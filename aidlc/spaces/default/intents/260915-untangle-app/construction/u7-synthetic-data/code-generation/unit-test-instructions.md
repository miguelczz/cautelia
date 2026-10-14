# Instrucciones de pruebas — U7 `synthetic-data`

U7 es de la **rama determinista**: cada capa se implementa y se prueba antes de
la siguiente. No tiene tablas propias; sus capas son:
- los modelos de la salida;
- el núcleo determinista;
- la redacción;
- la composición;
- las huellas;
- la siembra por la API de U4.

Estrategia `Standard`: de cinco a ocho pruebas por componente.

## Cómo correr solo lo de U7

| Qué | Comando | Lo que corre por debajo |
| --- | --- | --- |
| Pruebas de la unidad | `mise run test:u7`, tarea nueva del paso 2 | `uv run --project app/backend pytest -c app/backend/pyproject.toml app/backend/tests/unit/synthetic_data` y las de integración de la siembra |
| Lo versionado es lo que se genera | `mise run synthetic:check`, tarea nueva | Regenera en un directorio temporal y compara byte a byte con `app/data/`; lo corre `scripts/verify.sh` |
| Texto propio | `mise run content:check` | Las huellas contra cada cláusula, con umbral cero |

`mise run test:u7` **no llama a ningún proveedor**: la redacción se prueba con
el doble de la fábrica. Solo `synthetic:draft` llama al modelo, a mano y una
vez por parte, y nunca corre en GitHub Actions.

## Coberturas esperadas

**80 % o más agregado** con `mise run cov`, sin exclusiones nuevas.

## Dobles de prueba

- **Modelo:** el doble de la fábrica de U5; ninguna prueba abre una conexión de
  red.
- **Specimens:** un texto inventado para la prueba, con secuencias conocidas;
  nunca un specimen real.
- **Base:** la de pruebas de integración de U4, con la transacción de cada
  prueba revertida al terminar.

## Datos de prueba

Los textos fuente reales de `app/data/sources/`, carpeta nueva, más fuentes
mínimas escritas para cada prueba que necesita romper una regla.
