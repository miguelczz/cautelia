# Instrucciones de prueba — U1 `workspace`

Cómo se corren las pruebas de **esta unidad**, con qué se montan y qué se espera
de ellas. Es el archivo que Build and Test ejecuta después, así que cada comando
está acotado a U1 y ninguno barre el proyecto entero.

## Marco y configuración

| Pieza | Herramienta | Dónde se configura |
| --- | --- | --- |
| Runner de Python | `pytest` con `pytest-cov` | `app/backend/pyproject.toml` |
| Runner de TypeScript | `vitest` con su cobertura | `app/frontend/vitest.config.ts` |
| Cobertura de Python | `coverage.py` a través de `pytest-cov`, salida en formato común | `app/backend/pyproject.toml` |
| Cobertura de TypeScript | `v8` a través de Vitest, salida en el mismo formato común | `app/frontend/vitest.config.ts` |
| Agregación de las dos | Comando propio del archivo de tareas | `mise.toml`, tarea `cov` |

**El runner queda ejecutable antes de la primera prueba.** Es el paso 5 del plan
y el contrato de pruebas lo exige: no existe ningún runner que verificar, así que
se crea y se comprueba con un caso trivial antes de escribir la primera prueba
real.

## Cómo se corren las pruebas de esta unidad

Las rutas están acotadas a U1. Build and Test corre los comandos de cada unidad,
así que un comando sin rutas volvería a correr la suite entera una vez por
unidad.

**Python, las 36 pruebas de U1:**

```bash
uv run --project app/backend pytest app/backend/tests/unit/server app/backend/tests/unit/copy_catalog app/backend/tests/unit/evals app/backend/tests/integration/u1 -q
```

**TypeScript, las 2 pruebas de U1:**

```bash
pnpm --dir app/frontend exec vitest run src/shared/copy
```

**Las dos juntas, desde el archivo de tareas:**

```bash
mise run test:u1
```

La tarea `test:u1` encadena exactamente los dos comandos de arriba y no añade
nada. Existe para que nadie tenga que recordar las rutas, no para esconderlas.

## Cobertura esperada

| Meta | Valor | Cómo se comprueba |
| --- | --- | --- |
| Agregado sobre el código del aplicativo | **80 % o más** de líneas | `mise run cov`, que combina los dos reportes ponderando por líneas y devuelve distinto de cero si no se alcanza |
| Módulos críticos | 80 % o más por módulo | El mismo comando. **Hoy no aplica:** los cuatro módulos críticos (aislamiento, caso, corpus y citas, reglas) llegan con U2, U4, U8 y U9 |
| Exclusiones | `site/`, corpus y datasets generados, migraciones | Lista versionada en la configuración de cobertura |

**El umbral no se baja para que un paso pase.** Si U1 no llega al 80 %, se
escriben más pruebas o se dice que no se alcanzó, con el número real.

## Qué se simula y qué no

| Frontera | Cómo se prueba |
| --- | --- |
| Proveedor de modelo | **Nunca se llama.** El corredor no invoca modelos (BR1.11), y las pruebas del corte por cuota inyectan la respuesta del proveedor, jamás llevan una clave real a su tope |
| Conductor de canal | Con un conductor de prueba registrado por la propia prueba, que devuelve turnos fijos. Es lo que hace que el determinismo del corredor se pueda probar sin gastar nada |
| Backend de trazas | Apagado. La prueba comprueba que el reporte sale con los enlaces marcados como no disponibles |
| Base de datos | **No se usa.** U1 no crea tablas (decisión CG-1 del plan) |
| Sistema de archivos | Real, sobre un directorio temporal con un catálogo y un conjunto de casos de prueba |
| Reloj | Solo en los campos de la corrida, nunca en una comparación |

**Ninguna prueba de esta unidad necesita red, base de datos ni credenciales.**
Es lo que permite que corran en la máquina de cualquiera y en la tubería sin
configuración previa.

## Datos de prueba

- Los catálogos y casos de prueba viven en `app/backend/tests/fixtures/`, uno por
  escenario, con nombres que dicen qué rompen: `copy_missing_en.yaml`,
  `case_bad_schema.yaml`, `subset_unknown_case.yaml`.
- **No se mezclan con los golden sets.** Los de `app/evals/cases/` son datos del
  producto con identificador estable; los de `tests/fixtures/` son andamiaje de
  prueba y no aparecen en ningún reporte.
- Cada prueba es independiente del orden y del estado compartido, y se puede
  correr sola.

## Forma de las pruebas

- Cada una afirma **un comportamiento**, no una implementación: se prueba lo que
  la regla exige, no cómo se codificó.
- Ninguna pasa con independencia de la implementación. Una prueba que pasaría con
  el cuerpo de la función vacío no cuenta.
- El camino feliz y **al menos dos casos de error o de borde** por archivo de
  prueba, como pide el guardarraíl de la fase.
- Los mensajes de fallo nombran la clave, el archivo o la variable culpable: una
  prueba que solo dice "falló" no ayuda a nadie a las seis semanas.

## Reparto por componente

| Componente | Pruebas | Archivo |
| --- | --- | --- |
| Modelos de las seis entidades | 5 | `tests/unit/evals/test_models.py` |
| Carga desde archivos | 4 | `tests/unit/evals/test_loading.py` |
| Catálogo de textos | 6 | `tests/unit/copy_catalog/test_catalog.py` |
| Chequeos del catálogo | 7 | `tests/unit/copy_catalog/test_checks.py` |
| Asegurado simulado | 6 | `tests/unit/evals/test_scripted_insured.py` |
| Corredor de evaluaciones | 8 | `tests/unit/evals/test_runner.py` |
| Raíz de composición | 3 | `tests/integration/u1/test_composition.py` |
| Chequeos de contenido | 3 | `tests/unit/evals/test_content_checks.py` |
| Módulo tipado de claves | 2 | `app/frontend/src/shared/copy/copy-keys.test.ts` |
| **Total** | **44** | |

Cinco a ocho por componente es lo que pide la estrategia `Standard`, más las de
integración en las fronteras. Los dos componentes con menos de cinco —carga
desde archivos y chequeos de contenido— son deliberadamente pequeños: uno es un
lector y el otro una expresión regular con su lista de exclusiones; forzar ocho
pruebas ahí produciría repetición, no cobertura.
