# Correcciones tras la revisión — U2 `tenancy`, infraestructura

La revisión asesora devolvió `READY` con tres hallazgos: uno `Major` y dos
`Minor`. Los tres son correctos. Se aplican aquí porque `cicd-pipeline.md` queda
congelado en cuanto se registra el recibo de la revisión; este archivo no es
artefacto declarado de la etapa, así que no altera lo que la revisión certificó.

Regla permanente que Miguel fijó el 2026-09-20: cuando un hallazgo sea
corrección de hecho sin decisión de por medio, se aplica y se reporta.

## R-01 — La promesa de NFR21 descansaba en la suerte

`cicd-pipeline.md` afirma que el camino "del clon al reporte" sigue sin tocar la
base de datos. Hoy es cierto, pero **por accidente de cómo quedó cableado U1**,
no por una frontera declarada: `app/backend/src/untangle/evals/cli.py` no
importa la raíz de composición, que es donde la aserción de aislamiento va a
bloquear el arranque. Ningún documento decía que eso fuera una frontera de
diseño, así que la generación de código de U2 podía enganchar la aserción en la
raíz, engancharla al corredor sin querer, y empeorar una métrica publicada sin
que nadie lo notara.

Es el mismo error de fondo que el revisor encontró en el diseño de calidad:
afirmar que algo está garantizado cuando solo está ocurriendo.

**Rige:** la frontera se declara y se hace cumplir por herramienta. El corredor
de evaluaciones tiene su propio punto de entrada y **no pasa por la raíz de
composición**. `app/backend/.importlinter` gana un contrato prohibido:

| Contrato | Qué prohíbe | Qué protege |
| --- | --- | --- |
| `evals` sin raíz de composición | Que `untangle.evals` importe `untangle.server.composition` o `untangle.tenancy.session`, directa o indirectamente | Que el camino del clon al reporte siga sin necesitar base de datos, y con ello la cifra publicada de NFR21 |

El día que una unidad necesite base de datos dentro del subconjunto de arranque,
ese contrato fallará y obligará a decidirlo a la vista, con la cifra de NFR21
vuelta a medir. Que es exactamente lo que queremos que pase.

## R-02 — A SEC-U2.5 le faltaba su segundo comando, otra vez

La cobertura de `SEC-U2.5` en `cicd-pipeline.md` y en `traceability.json` cita
solo `env:check`. El documento autoritativo —
`../nfr-design/correcciones-tras-revision.md`, hallazgo R-01 — exige **dos**:

| Comando | Qué demuestra |
| --- | --- |
| `mise run env:check` | Que existen las dos variables y que el código lee exactamente esas |
| `mise run test:u2` | Que una clave **no valida** lo firmado por la otra |

**Rige:** los dos. Es la segunda vez en esta unidad que se cae la mitad
interesante del par, y la que se cae siempre es la misma: la que prueba el
rechazo. Declarar dos variables no prueba que estén separadas.

## R-03 — "Un contenedor" era singular y no lo es

`cicd-pipeline.md` habla del coste como "el arranque de un contenedor de
PostgreSQL". Son tres comandos los que necesitan base en la misma corrida.

**Rige:** así se reparten.

| Comando | Base de datos |
| --- | --- |
| `mise run test:u2` (y `cov`, que lo incluye) | **Una sola** por corrida de la suite, compartida por todas las pruebas de la unidad |
| `mise run migrate:check` | **La suya propia**, porque necesita una base virgen para subir, bajar y volver a subir |
| `mise run rls:check` | Reutiliza la de la suite cuando corre dentro de ella; levanta la suya cuando se invoca solo |

Una corrida completa del guion levanta por tanto **hasta dos** bases efímeras,
no una. El coste sigue sin estimarse: se mide en la primera corrida verde de U2
y entra en el resumen de la generación de código, como cualquier otro número.

## Qué tiene que hacer la generación de código de U2

Tomar este archivo como autoritativo donde contradiga a `cicd-pipeline.md`:
añadir el contrato prohibido de `evals`, comprobar `SEC-U2.5` con los dos
comandos, y repartir las bases efímeras como dice la tabla de R-03.
