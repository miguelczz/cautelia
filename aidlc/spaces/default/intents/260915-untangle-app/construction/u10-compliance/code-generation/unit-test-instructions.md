# Instrucciones de pruebas — U10 `compliance`

U10 es de la **rama evaluada** (realiza M6): primero se escriben sus casos de
golden set, se comprueba que fallan, se implementa y se corren hasta que pasan.
Las capas que la sostienen (tablas, repositorio, lógica) siguen la rama
determinista: cada capa con sus pruebas antes de la siguiente. Estrategia
`Standard`: de cinco a ocho pruebas por componente.

## Cómo correr solo lo de U10

| Qué | Comando | Lo que corre por debajo |
| --- | --- | --- |
| Pruebas unitarias e integración | `mise run test:u10` (tarea nueva del paso 2) | `uv run --project app/backend pytest -c app/backend/pyproject.toml app/backend/tests/unit/compliance app/backend/tests/integration/u10` |
| Casos de golden set de U10 | `mise run evals:run -- --subset smoke` | El corredor de U1 con los casos de U10 que entran al subconjunto de arranque |

La integración necesita la base local (`mise run services:up`), como las demás
unidades con tablas.

## Coberturas esperadas

- **80 % o más agregado** con `mise run cov`, sin exclusiones nuevas.
- U10 no está en la lista de módulos críticos con piso propio.

## Dobles de prueba

- **Proveedores:** el puerto del modelo se reemplaza por un espía que falla la
  prueba si se le llama, para comprobar que ningún control ni la revisión lo usan
  (BR5.3).
- **Configuración de aseguradoras:** la real de las tres, para la categoría de
  revelación (BR1.7); ningún identificador de aseguradora escrito en las pruebas
  fuera de las fixtures.
- **Patrones:** un archivo de patrones roto para comprobar que impide arrancar y
  que la guardia falla cerrado.

## Datos de prueba

- Frases de prueba por idioma, versionadas, una fila por frase con su veredicto
  esperado; los casos de DS-2 y DS-6 apuntan a ellas.
- Cada prueba crea sus casos con la API de U4 y los borra; ninguna depende del
  orden.
