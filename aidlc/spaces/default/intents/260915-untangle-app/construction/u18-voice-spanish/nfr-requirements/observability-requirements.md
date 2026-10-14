# Observabilidad — U18 `voice-spanish`

Dos eventos nuevos, y los dos llevan **el idioma y el motivo, nunca el texto**.

| Evento | Cuándo | Qué lleva |
| --- | --- | --- |
| `voice.language_switched` | En cada cambio, pedido o automático | La llamada, el idioma de origen, el de destino y el motivo (`requested` o `detected`) |
| `voice.language_unsupported` | Al decir la frase de los dos idiomas (BR4.2) | La llamada y el idioma que el detector amplio reconoció |

## Por qué el motivo va en el evento

Sin él, el reporte del hito no puede separar dos cosas que se miden distinto: los
cambios que la persona pidió --que deben ser el 100 %-- y los que la detección
decidió sola, que es una métrica de acierto. Un solo contador de "cambios de
idioma" mezclaría una compuerta con una estimación.

## Por qué el idioma reconocido, y no el texto

`voice.language_unsupported` dice "portugués", no la frase. Es ADR-013 y es lo que
cierra RT-14: un evento de traza que imprimiera el turno sería el punto de fuga que
la redacción existe para evitar, y el idioma solo es exactamente lo que hace falta
para saber qué se está encontrando la demostración.

## Lo que no se añade

Ningún contador de turnos por idioma: ya está en la transcripción del caso, que
guarda el idioma de cada turno. Una segunda cuenta se desincroniza.

## Sources

- `../functional-design/rules.md` — BR2.4, BR4.2
- ADR-013; RT-14

## Assumptions & Open Questions

None.
