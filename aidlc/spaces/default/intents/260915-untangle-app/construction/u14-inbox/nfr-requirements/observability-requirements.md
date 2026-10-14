# Requisitos de observabilidad — U14 `inbox`

Lo que hay que poder responder después: quién decidió qué, quién corrigió qué, y
quién intentó entrar a donde no debía.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| OBS-U14.1 | Decisiones sin evento de traza con actor, caso, resolución y momento | **Exactamente 0** | Tarea nueva `mise run test:u14` |
| OBS-U14.2 | Correcciones sin evento con el campo, el actor y el canal | **Exactamente 0** | Tarea nueva `mise run test:u14` |
| OBS-U14.3 | Canjes de enlace rechazados sin evento con su causa | **Exactamente 0** | Tarea nueva `mise run test:u14` |
| OBS-U14.4 | Eventos de esta unidad que contengan el token del enlace, un comentario sin redactar o texto del asegurado | **Exactamente 0** | `mise run redaction:report` |
| OBS-U14.5 | Pausas y reanudaciones del caso ausentes de su traza (BR4.2) | **Exactamente 0** | Tarea nueva `mise run test:u14` |

## La causa del rechazo va a la traza, no a la respuesta

OBS-U14.3 y BR5.2 tiran en direcciones opuestas a propósito. Quien abre un enlace
inválido recibe **siempre el mismo mensaje**, sin saber si la firma estaba mal o
el caso no existe. Quien lee la traza sí ve cuál de las dos fue.

Es la misma forma que U13 usa para el resumen de traza: la distinción existe
donde sirve para investigar y no existe donde serviría para adivinar.

## El comentario de la decisión

El comentario va entero al asegurado —es la decisión de una persona dirigida a
él— y **redactado a la traza**: puede nombrar a terceros, y quien lee una traza
no necesita eso. Es la misma regla que U13 aplicó al aviso del ajustador.
