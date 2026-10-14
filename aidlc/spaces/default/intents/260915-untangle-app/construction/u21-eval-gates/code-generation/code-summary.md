# Resumen del código — U21 `eval-gates`

U21 le da memoria y autoridad al reporte de evaluación que U1 dejó:

- **Compara** cada corrida contra la línea base versionada y decide si hay
  regresión, con la regla que corresponde al tamaño del conjunto.
- **Distingue una compuerta dura de una regresión.** Una regresión se puede
  explicar por escrito; una compuerta dura, jamás.
- **Audita con un segundo detector** de mecanismo propio lo que ya se redactó.
- **Apaga al juez** donde su calibración no llega, sin tocar las compuertas que
  juzga el código.
- **Cierra la entrega**: el paso 9 del guion de verificación ya no corre las
  evaluaciones a secas, corre la compuerta.

Se construyó en dos tandas, las dos escritas en una sesión en la nube con
Sonnet, revisadas y cerradas aquí.

## Resultados

| Compuerta | Resultado |
| --- | --- |
| `mise run test:u21` | 88 pruebas en verde |
| `mise run evals:gate -- --subset smoke` | 52 casos, 0 fallos, compuerta en verde, diciendo que no hay línea base vigente |
| `mise run cov` | Ver la corrida de `scripts/verify.sh` de esta unidad |
| `lint`, `types`, `schema:check`, `copy:check` | En verde; 32 contratos de importación |
| `scripts/verify.sh` | Los nueve pasos en verde, con el paso 9 corriendo ya la compuerta |

## La corrección que salió de la revisión

La primera tanda llegó con todo en verde y **un hueco de diseño**: había fundido
en una sola regla las regresiones y las compuertas duras. Su lógica era "un caso
que falla bloquea, salvo que una explicación lo nombre", lo que dejaba una
puerta abierta — una cita inventada, un dato personal en una traza o una fuga
entre aseguradoras se volvían verdes escribiendo el identificador del caso en un
archivo de explicaciones.

Su razonamiento —"la línea base solo se publica en verde, así que todo fallo es
una regresión"— vale para las métricas, que se miden contra el pasado, y no para
los criterios `[bloquea]`, que son absolutos por caso.

La corrección, hecha en la segunda tanda:

- `EvalTarget` gana `blocking`, y los criterios que el PRD marca `[bloquea]` lo
  declaran: la regla de dinero de U9, los ocho escenarios de red-team de U10 y
  los dos de redacción de U3.
- La compuerta tiene ahora **dos fuentes de bloqueo separadas**: las duras, que
  ninguna explicación levanta, y las regresiones, que sí.
- Un caso marcado inestable sigue sin contar, pero si falló un criterio
  bloqueante sale listado en su propia línea: nunca en silencio.

Las tres pruebas que aíslan esa regla se escribieron antes del arreglo y se
vieron fallar contra el código viejo. **Es el ajuste que salió de la evaluación
de U9 funcionando:** la regla de "una prueba que aísle cada regla de
precedencia" es justo la que hizo visible este hueco.

## Decisiones y desviaciones registradas

| Qué | Por qué se acepta |
| --- | --- |
| `scan_report` devuelve siempre vacío | El esquema del reporte no guarda texto libre: cada campo es un identificador, un enum o un número, y serializarlo entero dispararía falsos positivos contra los hashes hexadecimales. Queda escrito que añadir un campo de texto libre obliga a revisarlo ahí |
| Los chequeos de contenido (ISO/ACORD, frases prohibidas) no se marcaron bloqueantes | No están registrados como objetivos de evaluación y su compuerta es un comando aparte, `content:check`, que ya bloquea por su cuenta |
| Publicar una línea base exige cero fallos, incluidos los de un criterio sin calibrar | Es la lectura más conservadora de BR2.1: una línea base es la referencia de todo lo que viene después |
| Un criterio bloqueante juzgado por el juez y sin calibrar no contaría | No existe hoy —las compuertas duras las juzga el código— y el reporte lista siempre los criterios sin calibrar, así que no puede pasar en silencio. Queda anotado como interacción a vigilar si algún día se marca bloqueante un criterio del juez |

De la revisión salieron además dos arreglos menores: un comentario del contrato
de importación citaba una regla que no existe, y el flujo de GitHub Actions subía
el reporte de la corrida desde una ruta equivocada —`app/evals/reports/` en vez
de `tmp/evals/reports/`—, un desajuste que venía de U1 y que hacía que el
artefacto de cada corrida llegara vacío.

## Lo que necesita a Miguel

La calibración del juez está construida y probada con veredictos grabados, pero
**no medida**: para eso hacen falta las 40 transcripciones de DS-7 etiquetadas a
mano, 20 por idioma, y una corrida del juez real con la clave, que no sale de su
máquina. Hasta entonces, todo criterio juzgado por el juez se publica como "no
medida" con esa causa, que es exactamente lo que la regla exige y lo contrario
de omitirlo. El comando `mise run evals:label` existe para hacerlo llevadero: se
puede dejar a medias y seguir después.

## Lo que U21 no hace, y quién lo hace

- El panel de cifras y las secciones del README: **U22**.
- Las conductas que estas metas miden —extracción, citación, derivaciones—:
  **U8, U11, U12 y U13**. U21 deja el medidor y la compuerta.
- La medición contra el despliegue vivo (AC4.14.3): la pasada de publicación.
