# Instrucciones de prueba — U3 `pii-redaction`

Cómo se prueba esta unidad, con qué comandos y contra qué metas. Todos los
comandos están **acotados a U3**: `build-and-test` ejecuta los de cada unidad, y
un comando que corriera la suite entera la repetiría veintidós veces.

## El comando de esta unidad

```bash
uv run --project app/backend pytest app/backend/tests/unit/redaction app/backend/tests/integration/u3 -q
```

Queda nombrado en el archivo de tareas como `test:u3`, igual que `test:u1` y
`test:u2`, y **no entra en el guion de verificación**: la compuerta ya corre
esas mismas pruebas en su paso 5, con `mise run cov`.

**Antes del primer caso** hay que comprobar que el comando es ejecutable y que
los dos modelos están instalados. Si no lo están, el cargador falla nombrándolos
y nombrando `mise run models:install`, no con un `ImportError` de spaCy.

## Qué necesita qué

| Comando | Modelos | Base de datos | Red |
| --- | --- | --- | --- |
| `mise run test:u3` | **Sí** | No | No |
| `mise run redaction:constructor` | No | No | No |
| `mise run redaction:report` | Sí | No | No |
| `mise run evals:run -- --subset rt14` | Sí | No | No |
| `mise run evals:run -- --subset smoke` | **No** | No | No |

Esta unidad **no toca la base de datos ni la red**. Que el subconjunto de
arranque siga sin necesitar modelos es lo que mantiene la cifra publicada de
NFR21.

## Qué se prueba, por capa

La unidad está en la rama evaluada, así que sus casos previos —RT-14 y RT-15 de
DS-6— se escriben, se corren y **se comprueba que fallan** antes de implementar
nada. Las capas que la sostienen siguen la rama determinista, en este orden.

| Capa | Archivo de pruebas | Qué afirma |
| --- | --- | --- |
| Configuración | `tests/unit/redaction/test_recognizers.py` | Un reconocedor sin uno de sus cinco campos no carga; uno que declare dos idiomas tampoco; añadir un formato es solo configuración |
| Detector | `tests/unit/redaction/test_detector.py` | Los cuatro tipos en los dos idiomas y en las tres formas; el turno mixto; el respaldo nunca gana un solape |
| Etiquetas | `tests/unit/redaction/test_labels.py` | La etiqueta va en el idioma de la conversación; dos datos distintos del mismo tipo se distinguen; nunca queda un dígito |
| Superficie | `tests/unit/redaction/test_api.py` | `redact` devuelve `Redacted`; si el detector falla, levanta en vez de devolver texto |
| Transcripción en vivo | `tests/unit/redaction/test_streaming.py` | Ningún fotograma intermedio contiene dos dígitos consecutivos del número sembrado; el aviso aparece pasado un segundo |
| Fronteras | `tests/integration/u3/test_import_contracts.py` | Los contratos fallan ante una violación plantada, y el árbol correcto pasa |
| El tipo | `tests/integration/u3/test_constructor_check.py` | El chequeo falla ante las **tres** formas de producir el tipo, y pasa con el árbol limpio |

Con la estrategia `Standard` —de cinco a ocho pruebas por componente— y seis
piezas, el orden de magnitud esperado es **entre 40 y 60 pruebas**. El número
exacto lo da la corrida, no esta estimación.

## Cómo se prueba lo que no se puede probar de frente

- **Que no exista una salida sin redacción.** No basta con que el contrato
  exista: la prueba **planta un escritor** que no pasa por la redacción y exige
  que falle. Y una segunda comprueba que el árbol correcto pasa, para que un
  fallo del andamiaje no se lea como éxito.
- **Que el tipo no se pueda falsificar.** No basta con buscar el constructor:
  como `NewType` se borra en tiempo de ejecución, la prueba planta también
  `cast(Redacted, texto)` y una anotación con `# type: ignore`, y exige que las
  tres fallen.
- **Que no se pueda evadir cambiando de idioma.** La prueba de RT-15 alimenta el
  dato en un idioma dentro de un turno del otro. Una segunda comprueba que el
  informe lo atribuye **al reconocedor que lo encontró**, no al idioma del
  turno: si no, la medición diría que el español funciona cuando quien atrapó el
  dato fue el juego inglés.
- **Que la consola no enseñe dígitos.** La prueba alimenta un teléfono dígito a
  dígito y exige que **ningún fotograma intermedio** contenga dos dígitos
  consecutivos del número sembrado. Comprobar solo el resultado final dejaría
  pasar el número que se vio medio segundo.
- **El coste frente al aviso.** Dos relojes distintos: el del sistema alrededor
  de la llamada real para el coste, el controlado para el aviso. Un reloj
  simulado no cronometra trabajo real.

## Metas de cobertura

| Meta | Valor | Comando |
| --- | --- | --- |
| Agregado del aplicativo (NFR18.1) | 80 % o más | `mise run cov` |
| Módulo de redacción, crítico (NFR18.2) | 80 % o más | `mise run cov` |

**La redacción entra a la lista de módulos críticos con esta unidad**, por
decisión de Miguel del 2026-09-20: su compuerta detiene la entrega con un solo
hallazgo y su fallo es silencioso.

El umbral **no se baja nunca** para que un paso pase. Si la cobertura no llega,
se escriben más pruebas o se explica por escrito qué quedó sin cubrir y por qué.

## Datos de prueba y dobles

- **Los casos de DS-6 viven versionados**, un archivo por caso, con
  identificador estable. No se generan en tiempo de corrida.
- **Sintéticos, pero con la forma real.** Un teléfono inventado que no parece un
  teléfono no prueba nada. Ningún dato de persona real, aquí ni en ningún sitio.
- **Los modelos no se simulan.** Lo que se prueba es qué detectan, y un doble no
  detecta nada.
- **El reloj se controla** solo donde se prueba temporización.
- **Cada prueba es independiente del orden** y se puede correr sola.

## Lo que esta unidad no prueba

El segundo detector (U21), las pantallas que muestran el texto tapado (U6, U14,
U16), la sonda de RT-14 contra el despliegue vivo —que no existe hasta U14— y
los puntos de salida de cada unidad dueña. Cada uno llega con su unidad.
