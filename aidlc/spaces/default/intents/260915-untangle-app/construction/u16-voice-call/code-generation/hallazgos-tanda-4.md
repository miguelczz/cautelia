# Revisión de la tanda 4 — U16 `voice-call`

"El corte y la retoma". Dos módulos nuevos, cinco claves de catálogo en dos
idiomas y 202 pruebas.

## 1. Lo que se rompió, y qué se cayó

Cuatro roturas, **las cuatro tumbaron una prueba de conducta**. Todas deshechas.

| Regla | Qué se rompió | Qué se cayó |
| --- | --- | --- |
| BR6.2 | La oferta de retomar sale antes de la apertura | `test_la_oferta_de_retomar_no_sale_antes_de_la_apertura` |
| BR6.5 | La oferta sale antes del resultado de la decisión | `test_un_caso_ya_decidido_se_resume_antes_de_ofrecer` |
| BR6.4 | Decir que se llama por otro accidente retoma igual | `test_llamar_por_otro_accidente_no_retoma_ni_deja_marca` |
| BR8.3 | La marca de recuperación pierde el enlace al caso original | `test_aceptar_deja_la_marca_enlazada_al_caso_original` |

El criterio `[bloquea]` de esta familia —AC1.27.3, que la póliza de ejemplo no
abra casos ajenos— se rompió y se comprobó en la tanda 1, que es donde vive la
consulta.

## 2. Una decisión de forma que evita cuatro claves muertas

`chat/notice.py` mete el comentario del ajustador **dentro** de cada frase de
desenlace. Copiado tal cual, una decisión sin nota habría dicho *"Su comentario
fue."* y sonaría a frase cortada. La alternativa obvia —dos versiones de cada
frase, con y sin nota— son ocho claves por idioma para decir lo mismo.

Se resolvió con **una clave aparte para la nota**, que se dice solo si la hay.
Tres frases de desenlace, una de nota, y el caso vacío sale bien sin ninguna rama
en el texto.

## 3. Dónde vive el comentario, y por qué no en el caso

`CaseView` no lo lleva: el comentario de quien decidió vive en la entrada del
historial que cerró el caso, porque el comentario y el cierre son el mismo acto
(BR4.1 de U14). Se lee por `history.of_case`, el mismo camino que usa la vista de
la bandeja, y no por uno propio.

Es el tipo de dato que se habría inventado con un valor de relleno si nadie
mirara dónde está de verdad.

## 4. Decisiones tomadas al escribir

1. **La apertura completa va primero, siempre.** Saltarla porque "ya la oyó la
   vez pasada" es exactamente el atajo que la compuerta de divulgación existe
   para impedir. El motor lo comprueba y falla en el acto.
2. **El resultado va antes de la oferta.** La persona llama para saber qué pasó
   con su caso; preguntarle en qué se le puede ayudar antes de contárselo es la
   forma más segura de que lo pregunte ella.
3. **Un "no" significa otro accidente, no que no quiera hablar.** Por eso abrir
   un caso nuevo no es un camino de error: es el otro desenlace normal.
4. **La búsqueda del caso retomable pasa por el motor** (`look_for_resumable`) y
   no directamente desde la ruta. No es indirección: es que `resume.find` tenga
   un llamador dentro de la propia unidad, y no quede esperando a que la tanda 5
   se acuerde de él. Es la lección de la tanda 3.
5. **`pending` no promete un plazo.** La guía de voz prohíbe especular sobre
   tiempos y la demostración no garantiza ninguno. Hay una prueba que busca las
   palabras de plazo en los dos idiomas.

## 5. Lo que no se debilitó

Ninguna prueba existente se relajó ni se borró. Ningún umbral, ningún piso de
cobertura, ninguna compuerta. Ninguna supresión del linter nueva.

## 6. Formas del catálogo que se revisaron contra este diff

- **La pieza sin llamador** (la de la tanda 3). Se comprobó módulo por módulo
  antes de cerrar: `resume` y `notice` tienen su llamador en `call.py`, y
  `resume.find` lo tiene dentro de la unidad y no pendiente de la siguiente tanda.
- **La que solo se comprueba en un idioma.** Las cinco claves nuevas se prueban
  en los dos.
- **La aserción que no puede distinguir.** La prueba del caso decidido compara
  **posiciones** —que el resultado va antes que la oferta— y no solo que las dos
  frases estén: con una aserción de presencia, invertir el orden pasaría.

## 7. Estado

`mise run test:u16`: 202 pruebas en verde (139 unitarias, 63 de integración).
`mise run copy:check`, `mise run types`, `mise run lint`: en verde.
