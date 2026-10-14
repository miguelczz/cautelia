# Seguridad — U18 `voice-spanish`

Esta unidad no abre ninguna superficie nueva, no guarda nada nuevo y no toca
ninguna credencial. Lo que sí hace es tocar **dos cosas que ya eran sensibles**:
el idioma del caso y el texto de la persona.

| Identificador | Qué exige | Cómo se comprueba |
| --- | --- | --- |
| SEC-U18.1 | El idioma del caso no lo mueve un turno (BR5.1, `[bloquea]`) | Prueba de RT-10 en los dos sentidos |
| SEC-U18.2 | El texto del turno entra al reconocedor de peticiones como **dato**, nunca como instrucción | El mismo contrato que ya cumple el turno: campo delimitado del estado tipado |
| SEC-U18.3 | Ningún evento de traza del cambio de idioma lleva el texto del turno | Prueba sobre los eventos emitidos |

## SEC-U18.1 es RT-10 con otra ropa

Un caso que cambia de idioma a mitad para esquivar un control es un escenario de
red-team escrito. Si el idioma del caso siguiera al último turno, mover un caso de
cola costaría decir dos palabras en el otro idioma. Por eso el cambio escribe el
idioma de la **llamada** y el del caso se queda donde estaba.

**La consecuencia, dicha:** un caso abierto en español y terminado en inglés
aparece en la bandeja como español. Es deliberado, y lo que la ajustadora ve de lo
que de verdad pasó es la transcripción, turno por turno, que sí lleva los dos.

## SEC-U18.2 no añade nada, y por eso está escrito

El reconocedor de peticiones es código y una lista versionada: no hay prompt, no
hay modelo y no hay nada que inyectar. Se escribe como requisito para que quien
piense en "usar el modelo para detectar la petición" —que es la forma cómoda— se
encuentre con la razón antes que con la idea.

## Lo que esta unidad hereda y no repite

La redacción antes de persistir, el punto único de salida, el aislamiento por
aseguradora y que no se guarde audio son de U3, U4 y U16, y siguen aplicando sin
cambio. Esta unidad no introduce ningún punto de salida nuevo.

## Sources

- `../functional-design/rules.md` — BR5.1, BR2.1
- `../../../inception/requirements-analysis/requirements.md` — RT-10
- `../../u16-voice-call/nfr-requirements/security-requirements.md`

## Assumptions & Open Questions

None.
