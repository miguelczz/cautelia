# Requisitos de observabilidad — U13 `chat`

Esta unidad es la primera que produce actividad de gente que no somos nosotros. Eso
cambia la pregunta: no es "qué querríamos ver", es **qué se puede ver sin que mirar se
convierta en la fuga**.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| OBS-U13.1 | Turnos del chat sin su tramo en la traza, con el canal marcado | **Exactamente 0** | Tarea nueva `mise run test:u13` |
| OBS-U13.2 | Rechazos por límite sin su evento, con el límite que se alcanzó y sin el texto del visitante | **Exactamente 0** | Tarea nueva `mise run test:u13` |
| OBS-U13.3 | Atributos de traza que contengan el texto del visitante o la clave de su navegador | **Exactamente 0** | `mise run redaction:report` |
| OBS-U13.4 | Divulgaciones mostradas sin su registro con hora, idioma y canal | **Exactamente 0** | Tarea nueva `mise run test:u13` |
| OBS-U13.5 | Avisos de decisión emitidos sin su evento con el identificador de la decisión | **Exactamente 0** | Tarea nueva `mise run test:u13` |

## Lo que se emite, y lo que no tiene dónde entrar

La lista de atributos de traza de U5 está **cerrada** y el comprobador de tipos la
impone: un nombre inventado no compila. Esta unidad no añade ninguno; usa los que hay
y marca el canal.

Lo que **no** entra en ningún evento de esta unidad, y no por disciplina sino porque no
hay atributo donde ponerlo:

- El texto del visitante. Lo que se conserva de un turno es su transcripción redactada
  en el caso, no una copia en la traza.
- La clave del navegador. Ni su resumen: el resumen identifica la conversación igual
  que la clave, y una traza pública no necesita saber de quién es.
- El comentario del ajustador. Va redactado en la traza y en el log (BR5.2), aunque
  llegue completo a la conversación.

## Por qué el rechazo por límite lleva evento

Sin él, el día que alguien diga "el chat no me responde" no habría forma de distinguir
tres cosas que se ven igual desde fuera: que se alcanzó un límite, que el proveedor no
respondió, o que el proceso está caído. Con el evento, la diferencia se lee en un
segundo, y además deja ver si los límites están puestos donde estorban.

El evento lleva **cuál** límite se alcanzó y no lleva el mensaje que lo provocó: para
entender el rechazo basta saber que fue el de sesión, el de origen o el del día.

## Lo que hereda y no vuelve a construir

- **El punto único de emisión de tramos** y el resumen de traza son de U5 (C-23).
- **La redacción antes de persistir y en cada punto de salida** es de U3.
- **El panel de cifras públicas** es de U22, y muestra solo recuentos y
  distribuciones: nunca números ni identificadores de casos de visitantes.
