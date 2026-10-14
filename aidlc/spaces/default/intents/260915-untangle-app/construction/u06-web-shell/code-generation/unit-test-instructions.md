# Instrucciones de pruebas — U6 `web-shell`

U6 es de la **rama determinista**: se recorre capa por capa (datos, acceso a
datos, lógica, API, interfaz) y cada capa se prueba antes de pasar a la
siguiente. La estrategia es `Standard`: de cinco a ocho pruebas por componente,
unitarias más integración en las fronteras.

## Cómo correr solo las pruebas de U6

Los tres comandos quedan como tareas de `mise.toml` en el paso 2 del plan, antes
de la primera prueba. Mientras no existan, estas son sus formas exactas:

| Qué | Comando de la tarea | Lo que corre por debajo |
| --- | --- | --- |
| Servidor (unitarias e integración) | `mise run test:u6` | `uv run --project app/backend pytest -c app/backend/pyproject.toml app/backend/tests/unit/web app/backend/tests/unit/activation app/backend/tests/integration/u6` |
| Interfaz (componentes) | `mise run test:u6` (segunda línea) | `pnpm --dir app/frontend exec vitest run src/app src/pages src/shared/theme src/shared/i18n src/shared/api-client src/shared/ui` |
| Arnés de accesibilidad y escenarios de tiempo | `mise run a11y` | `mise run web:build` y después `pnpm --dir app/frontend exec playwright test --config e2e/playwright.config.ts` |

Las pruebas de integración y el arnés necesitan la base de datos local:
`mise run services:up`. Los navegadores del arnés se instalan una vez con
`mise run browsers:install`, que **no** forma parte de `mise run bootstrap`
(NFR21.3).

## Herramientas y configuración

- **Servidor:** pytest con la configuración existente de
  `app/backend/pyproject.toml`; cobertura con la misma configuración y la misma
  lista de exclusión.
- **Interfaz:** Vitest con `jsdom` y Testing Library; la configuración de
  cobertura existente de `app/frontend/vitest.config.ts` se amplía al código
  nuevo, sin exclusiones nuevas (NFR18.4).
- **Arnés:** Playwright con `@axe-core/playwright`, en
  `app/frontend/e2e/`. Chromium corre todo; Firefox y WebKit corren la prueba de
  dibujo de cada pantalla registrada (Q1 de NFR Requirements).

## Coberturas esperadas

- **80 % o más agregado** sobre el código del aplicativo, con el comando de
  siempre: `mise run cov`. El código nuevo de U6, incluido el cliente generado de
  la API, entra al cálculo.
- U6 no toca ninguno de los cinco módulos críticos con piso propio.

## Dobles de prueba

- **Proveedores:** los puertos de proveedor se reemplazan por espías que fallan
  la prueba si se les llama. Así se prueba que la salud, las sondas y el
  directorio del sitio no llaman a ninguno (NFR16.6, SEC-U6.9).
- **Reloj:** la máquina de estados de la espera se prueba con temporizadores
  simulados de Vitest: 5 segundos entre consultas y 60 hasta "no disponible"
  (NFR16.5), sin esperar de verdad.
- **Salud en el arnés:** el escenario de espera intercepta la ruta de listo en
  Playwright y responde 503; el resto del arnés corre contra el proceso real.
- **Almacenamiento del navegador:** en Vitest, un almacenamiento que lanza al
  leer y otro con un valor corrupto (REL-U6.2).
- **Sin datos inventados:** las pruebas del inicio usan la configuración real de
  las tres aseguradoras, no filas escritas a mano.

## Datos de prueba

- La activación se prueba con claves de navegador creadas por la propia prueba
  con la función de U2, en dos aseguradoras, para comprobar el aislamiento.
- Cada prueba crea lo suyo y lo borra; ninguna depende del orden ni de otra.
- Las superficies se prueban con un módulo de prueba que declara una superficie
  con su sonda (SCALE-U6.1) y otro que la declara sin sonda (REL-U6.4).
