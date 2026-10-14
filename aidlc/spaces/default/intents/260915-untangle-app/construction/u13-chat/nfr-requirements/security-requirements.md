# Requisitos de seguridad — U13 `chat`

Esta unidad es la puerta. Todo lo que las doce anteriores protegen queda detrás de
una página que cualquiera puede abrir sin credencial, así que **sus tres compuertas
duras son de seguridad** y aquí quedan como objetivos medibles con su comando, no
como prosa.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| SEC-U13.1 | Conversaciones donde algún texto del visitante se procesó antes de la divulgación (BR1.1, `[bloquea]`) | **Exactamente 0** | Tarea nueva `mise run test:u13` |
| SEC-U13.2 | Diferencias —en texto o en estado— entre la respuesta a un caso de otro navegador y la respuesta a un caso inexistente (BR6.2, `[bloquea]`) | **Exactamente 0**, por idioma | Tarea nueva `mise run test:u13` |
| SEC-U13.3 | Lo mismo para un caso de otra aseguradora (BR6.3, `[bloquea]`) | **Exactamente 0**, por idioma | Tarea nueva `mise run test:u13` |
| SEC-U13.4 | Claves de navegador guardadas en claro | **Exactamente 0**: solo el resumen | `mise run schema:check` |
| SEC-U13.5 | Datos personales sin redactar en el resumen de traza público | **Exactamente 0**, por idioma y por tipo de entidad | `mise run redaction:report` |
| SEC-U13.6 | Avisos de decisión emitidos sin un identificador de decisión humana registrada (BR5.2) | **Exactamente 0** | Tarea nueva `mise run test:u13` |
| SEC-U13.7 | Texto del visitante que llegó al prompt de sistema en vez de a un campo delimitado del estado | **Exactamente 0** | Tarea nueva `mise run test:u13` |
| SEC-U13.8 | Cuota del chat agotada que deja sin servicio a la voz o a las evaluaciones (BR3.3) | **Exactamente 0** | Tarea nueva `mise run test:u13` |
| NFR12.6 | RT-10 (cambio de idioma para esquivar los controles) resuelto en el canal de texto (NFR12, dueña U10) | **En verde**, por idioma | `mise run evals:gate` |

## Cómo se mide una compuerta de aislamiento

SEC-U13.2 y SEC-U13.3 no se miden comprobando que el dato ajeno no aparezca. Se miden
**comparando** la respuesta contra la de un caso que no existe, campo por campo y
carácter por carácter. La razón está escrita en el diseño de U12 y esta unidad la
hereda: la filtración no es el dato, es la distinción. Recibir algo distinto de lo que
recibe un desconocido ya dice que ese caso existe, aunque la frase sea inofensiva.

El control positivo va delante en las dos: la sesión legítima tiene que recibir una
respuesta **real** con la que comparar, porque si no, las dos aserciones pasan igual
con una implementación que no entregue nunca nada.

## Por qué el resumen de la clave y no la clave

SEC-U13.4 existe porque la clave del navegador es lo único que ata una conversación a
una persona. Guardarla en claro significa que un volcado de la base —o una consulta
mal hecha— sirve para hacerse pasar por cualquier visitante. Guardando el resumen, lo
que la base tiene no sirve para eso. Es la misma forma que U2 ya usa para los enlaces
firmados, y la aserción de esquema es lo que la mantiene.

## Lo que esta unidad hereda y no vuelve a implementar

- **La redacción** es de U3, y pasa por su punto único de salida. Un punto de salida
  nuevo sin redacción tiene que ser imposible por construcción.
- **La guardia de salida** es de U10. Todo texto pasa por ella, incluido el parcial
  del streaming y el de error: si el parcial la esquivara, bastaría leer rápido.
- **El aislamiento por aseguradora** es de U2, con su política de fila. Esta unidad no
  lo comprueba en código; lo que tiene que hacer es no reintroducir la distinción al
  componer la respuesta.
