# Instrucciones de pruebas — U11 `intake`

U11 es de la **rama evaluada** y realiza M1 (`team.md`). Sus casos previos son
diez ejes de DS-2 y tres escenarios de DS-6, que **no existen todavía**: se
escriben en el paso 2, se corren y se comprueba que fallan antes de implementar
nada. Las capas que la sostienen van por la rama determinista. Estrategia
`Standard`: de cinco a ocho pruebas por componente.

## Cómo correr solo lo de U11

| Qué | Comando | Lo que corre por debajo |
| --- | --- | --- |
| Pruebas de la unidad | `mise run test:u11`, tarea nueva del paso 1 | Las unitarias del nodo y las de integración que escriben en el caso |
| Casos de arranque | `mise run evals:run -- --subset smoke` | Los 52 casos que ya existen |
| La corrida completa | `mise run evals:run` | Todo, incluidos los casos nuevos |

Mientras trabaja, el agente corre solo `test:u11` y el subconjunto de arranque.
La suite completa y `scripts/verify.sh` corren una vez, al final de cada tanda.

## Lo que cada regla de precedencia exige

Ajuste que salió de la evaluación de U9: **cada regla de precedencia o de
apagado lleva una prueba que la aísla**, escrita antes del código. En esta
unidad son siete:

- una póliza de otra aseguradora produce **exactamente** la misma salida y el
  mismo estado que una inexistente (BR1.2);
- una instrucción dentro del texto de la persona no cambia nada de lo que el
  sistema hace (BR2.3);
- el bloque que toca sale del estado del caso: con el mismo caso, dos corridas
  preguntan lo mismo, y un contador interno no existe (BR3.2);
- un dato que la persona adelantó **no se vuelve a preguntar** (BR3.3);
- la señal de emergencia rompe el orden en ese mismo turno, esté donde esté la
  captura (BR4.1);
- una pregunta de cobertura a mitad no mueve el bloque en curso (BR4.2);
- una versión que contradice un dato confirmado **no reemplaza** el valor del
  caso: se anota aparte con su turno y su hora (BR5.5, FD-U11-7).

## Coberturas esperadas

**80 % o más agregado** con `mise run cov`. U11 no es módulo crítico por la
lista de `team.md`, así que no lleva piso propio; aun así se espera que el nodo
quede al nivel de los otros tres.

## Dobles de prueba

- **Sin proveedor:** ninguna prueba llama al modelo. El extractor se sustituye
  por un doble determinista con respuestas sembradas por turno, elegidas para
  que la extracción sea conocida y se pueda afirmar sobre el orden y la
  confirmación, que es lo que esta unidad decide.
- **Con base de datos:** U11 escribe en el caso de U4, así que sus pruebas de
  evidencia, confirmación y dos versiones son de integración. Se **escriben** en
  la nube y se **corren** en la sesión local.
- **Sin canal:** el nodo se prueba sin el grafo y sin interfaz, que es lo que su
  tipo `library` significa.

## Datos de prueba

- Los diez casos de DS-2 y los seis de DS-6 que escribe el paso 2.
- Casos sembrados de U7 en los estados que cada prueba necesita: recién abierto,
  con la pregunta de seguridad respondida, con un bloque esperando confirmación.
- La póliza de ejemplo de cada aseguradora, y el número que existe en dos
  (`POL-480915`) para la prueba de BR1.2.

Nada de datos de personas reales: todo sale del generador sembrado de U7.
