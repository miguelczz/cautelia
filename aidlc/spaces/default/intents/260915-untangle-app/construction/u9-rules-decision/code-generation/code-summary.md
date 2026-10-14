# Resumen del código — U9 `rules-decision`

U9 deja el motor de reglas del aplicativo y el nodo `decision`:

- **Las reglas viven en la carpeta de cada aseguradora**, diez por aseguradora,
  versionadas y con sus propias pruebas, en un lenguaje cerrado de operadores
  que el código valida al cargar. Ninguna rama del código conoce a ninguna
  aseguradora.
- **La evaluación es determinista y sin modelo**: devuelve la categoría del caso
  —cierre directo, revisión estándar o derivación—, las reglas que dispararon,
  los insumos que leyeron y la clave de la explicación que ve una persona.
- **El nodo `decision`** evalúa, guarda el resultado con un identificador
  determinista y entrega el turno a `compliance` por una función pura.

Se construyó por la **rama evaluada**: primero los doce casos de DS-2 con sus
cuatro sondas, vistos fallar, y después el motor que los pone en verde. En dos
tandas: los pasos 1 a 5 en `42f6e58` y los pasos 6 a 9 en `ee8d21d`.

## Resultados

| Compuerta | Resultado |
| --- | --- |
| `mise run test:u9` | 63 pruebas en verde (50 unitarias, 13 de integración) |
| `mise run evals:run -- --subset smoke` | 52 casos, 0 fallan, 1,37 s; los 12 de U9, en los dos idiomas |
| `mise run cov` | **88,79 %** agregado; **89,44 %** en el motor de reglas, que entra como módulo crítico |
| `lint`, `types`, `schema:check`, `copy:check`, `rls:check`, `tenancy:literals` | En verde |
| `mise run contracts:check` | En verde después del commit de cada tanda |
| `scripts/verify.sh` | Los nueve pasos en verde |
| GitHub Actions (`verify`) | En verde sobre `42f6e58` y sobre `ee8d21d`, al primer intento |

## Las reglas de las tres aseguradoras

Cada conjunto trae exactamente **una regla por defecto**: la única que dispara
siempre con revisión estándar. Una regla que dispara siempre y no es la por
defecto solo puede derivar, y así se escribe la política de la agencia.

| Aseguradora | Perfil | Cómo lo hace |
| --- | --- | --- |
| Stonecroft | Estricta | Derivan heridos, terceros con datos pendientes, monto, cobertura disputada, sospecha de fraude y conductor no listado. Ninguna regla cierra directo |
| Sunmeadow | Flexible | Cierra directo solo cuando heridos y terceros pendientes están **capturados y en falso**; conserva las reglas de severidad y de dinero |
| Knotwell | Agencia | Su primera regla deriva siempre; trae además las reglas de severidad para que la evaluación registre la señal concreta |

Un campo ausente nunca dispara, así que un caso sin datos no cierra directo: cae
en la regla por defecto y lo mira una persona.

## Dos correcciones de la revisión

La primera tanda llegó con las 44 pruebas en verde y dos fallas de lógica que
ninguna de ellas cubría. Las dos son del mismo tipo: el código hacía algo
razonable que el diseño no pedía.

1. **El cierre directo no podía ganar nunca.** La regla por defecto, que dispara
   siempre, competía con las demás, y su revisión estándar es más prudente que
   un cierre directo. Corregido: la regla por defecto solo entra cuando ninguna
   otra disparó, y solo entonces aparece entre las disparadas (BR2.2).
2. **La regla de la agencia no era "siempre".** Dependía de que un campo
   estuviera lleno, así que un caso sin datos no derivaba. Se enmendó BR1.3 para
   que `always: true` sea la marca de una regla que dispara siempre, y no solo
   de la regla por defecto.

De la segunda tanda salió un hallazgo menor: un comentario de Knotwell afirmaba
que la explicación siempre sale de la regla de la agencia, y no es cierto cuando
dispara una regla de dinero. Corregido en el mismo commit.

## Enmiendas de contrato

**C-19.** Lo construido difiere del boceto en tres puntos, todos registrados en
`inception/contract-design/contract-summary.md`: `evaluate` recibe la
aseguradora y los insumos en vez del caso, porque `rules` está por debajo de
`case_record` en el contrato de capas; los campos que leen las reglas son un
vocabulario propio del motor, más fino que los bloques de captura; y la
superficie suma `save_evaluation` y `evaluations_for`. Una cuarta, de la segunda
tanda: `RuleEvaluationView` gana `ruleset_version`, que el nodo necesita para
guardar.

## La evaluación del modo ligero

U9 era la prueba del modo ligero (Sonnet en el agente de código, comentarios
cortos, suite completa una vez por tanda). Estas son las cuatro condiciones que
fijó el plan, medidas.

| Condición | Meta | Resultado |
| --- | --- | --- |
| **Pasa** | Todo en verde; GitHub Actions al primer intento | **Cumplida.** Las dos tandas, al primer intento |
| **Queda alineado** | Cero hallazgos de los chequeos automáticos | **Cumplida** en lo que miden esos chequeos; `tenancy:literals` señaló un caso legítimo (el subconjunto de arranque nombra aseguradoras) que se resolvió declarándolo, como ya estaba declarado para los casos de golden set |
| **Queda bien escrito** | Cero hallazgos bloqueantes en mi revisión | **No cumplida.** Dos fallas de lógica bloqueantes en la primera tanda, más una menor en la segunda |
| **Sale más barato** | ≤ 1,0 millón de tokens y ≤ 1 h 30 min de agente | **Cumplida.** Tanda 1: 652.000 tokens y 54 minutos. Tanda 2: corrió en una sesión en la nube, con crédito y no con el plan |

**La conclusión honesta es que el modo ligero funciona, pero solo con la
revisión puesta.** Las cifras de costo son buenas —la mitad de tokens que U15
por tanda— y todas las compuertas quedaron en verde, incluidas las duras. Lo que
no se cumplió es la condición de "bien escrito": las dos fallas de la primera
tanda habrían entrado a `main` con CI en verde, porque las pruebas del agente no
cubrían la interacción entre la regla por defecto y el cierre directo. Ninguna
compuerta automática las habría visto.

Eso no es un argumento contra Sonnet: es la medida de cuánto vale la revisión, y
la razón por la que el diseño y la revisión se quedan en la sesión principal.
Para U21 se mantiene el reparto y se añade una obligación al encargo: **por cada
regla de precedencia del diseño, una prueba que la aísle**, escrita antes que el
código que la implementa.

**Densidad de comentarios**, comparada con U7 como pedía el plan:

| Unidad | Líneas de código | Comentarios | Docstrings | Total |
| --- | --- | --- | --- | --- |
| U7 `synthetic-data` | 4.228 | 4 % | 20 % | 24 % |
| U9 `rules-decision` | 937 | 7 % | 24 % | **31 %** |

**Subió, no bajó.** La regla de escribir comentarios solo donde la razón no es
obvia sí se siguió —los comentarios explican una decisión o citan la regla que
aplican—, pero los archivos de U9 son cuatro veces más cortos, y los docstrings
de módulo, que en este proyecto cargan la justificación de contrato, pesan mucho
más en un archivo de 80 líneas que en uno de 400. Para U21: el docstring de
módulo se limita a lo que hace el módulo, y la justificación de una desviación
de contrato va al registro del flujo, que es donde se busca.

## Lo que U9 no hace, y quién lo hace

- El grafo que encadena los nodos: **U12**.
- La captura que escribe los campos que las reglas leen: **U11**.
- Mostrar la regla y sus insumos en la bandeja: **U14**.
- La meta de derivaciones sobre DS-2 completo: **U21**.
- Las reglas de elegibilidad y la banda de cotización: **U19**.
