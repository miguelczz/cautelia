# Instrucciones de pruebas — U15 `speech-providers`

U15 es de la **rama determinista**: cada capa se implementa y se prueba antes de
la siguiente. No tiene tablas; sus capas son la configuración, los adaptadores y
el cableado en la raíz de composición. Estrategia `Standard`: de cinco a ocho
pruebas por componente.

## Cómo correr solo lo de U15

| Qué | Comando | Lo que corre por debajo |
| --- | --- | --- |
| Pruebas de la unidad | `mise run test:u15` (tarea nueva del paso 2) | `uv run --project app/backend pytest -c app/backend/pyproject.toml app/backend/tests/unit/voice_providers` |
| Prueba de contrato contra el proveedor real, a mano en cada hito | `mise run voice:contract-live` (tarea nueva) | La misma prueba de contrato, contra Deepgram y Cartesia, con las claves del uso `voice` del `.env` local |
| Oír a Catalina | `mise run voice:say` (tarea nueva) | Una frase por el camino real del aplicativo |

`mise run test:u15` **no llama a ningún proveedor**: corre contra las respuestas
grabadas. Las dos tareas a mano sí llaman, gastan unos pocos caracteres o
segundos del saldo gratuito y nunca corren en GitHub Actions.

## Coberturas esperadas

**80 % o más agregado** con `mise run cov`, sin exclusiones nuevas.

## Dobles de prueba

- **Proveedores:** respuestas grabadas, capturadas una sola vez con una llamada
  real y versionadas; ninguna prueba abre una conexión de red.
- **Gasto y techo:** el acumulado se fuerza al borde en la prueba, sin consumir
  el presupuesto real (`project.md`).
- **Errores:** respuestas grabadas de error por cada tipo de la taxonomía.

## Datos de prueba

Frases fijas, cortas, sin datos personales, en los dos idiomas.
