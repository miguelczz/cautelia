# Especificación funcional — U15 `speech-providers`

Fuente de verdad de los flujos de U15. La forma de los datos está en
`entities.md` y las decisiones en `rules.md`. Respuestas aplicadas: protocolo
WebSocket y HTTP propio de cada proveedor (Q1), configuración en el bloque
`voice` de `tenant.yaml` (Q2) y un comando para oír a Catalina (Q3).

## 1. Qué hace esta unidad

Tres adaptadores detrás de las interfaces de C-16: transcripción con Deepgram
`nova-3` en modo `multi`, síntesis principal con Catalina de Cartesia
`sonic-3.6`, y síntesis de respaldo con Aura-2 de Deepgram. Más la configuración
de voz por aseguradora con su validación, las pruebas de contrato y el comando
para oír a Catalina.

No hace, y quién lo hace: la llamada que usa estos adaptadores, las frases de
espera ya sintetizadas que dan el primer audio (hallazgo del experimento 1) y la
consola (U16); la decisión antes de cada llamada entre la voz principal y la de
respaldo, y su aviso (U17, US5.11).

## 2. Flujos

### F1 — Arranque

1. Se lee el bloque `voice` de cada `tenant.yaml` (BR2.1).
2. Para cada aseguradora se comprueba que su proveedor tiene adaptador y prueba
   de contrato, y que su modelo y su voz existen en la lista del adaptador
   (BR2.3).
3. Si algo falla, esa aseguradora queda con la voz apagada y un motivo del
   catálogo; el proceso y el chat arrancan igual (BR2.2).
4. La fábrica de U5 construye los adaptadores con la clave del uso `voice`
   (BR1.3).

### F2 — Transcribir en streaming

1. U16 entrega el audio de la persona como una secuencia de bloques.
2. El adaptador abre el WebSocket de Deepgram con `nova-3` en modo `multi`,
   después de pasar por el techo de U5 (BR5.1).
3. Por cada mensaje devuelve un `Transcript` parcial o final, con cada palabra,
   su confianza (nula si falta, nunca cero) y el idioma detectado (BR3.1).
4. Al cerrar, pide la finalización que documenta Deepgram, espera la respuesta
   forzada y registra los segundos de audio en el gasto (lección del
   experimento 1).
5. Ni el audio ni el texto salen a un log o a una traza (BR3.2).

### F3 — Sintetizar en streaming

1. Llega un texto ya redactado y una `VoiceRef` (C-16).
2. Se pasa por el techo de U5 (BR5.1).
3. El adaptador de Cartesia, o el de Aura-2 si la voz pedida es la de respaldo,
   abre su WebSocket y devuelve bloques de audio en el formato único (BR4.1).
4. Se registran los caracteres en el gasto con el precio de lista.
5. Cualquier fallo sale en la taxonomía cerrada; el saldo agotado, como parada
   sin reintento (BR1.4).

### F4 — Pruebas de contrato

1. **En cada entrega:** cada adaptador corre contra su respuesta grabada, que se
   capturó una vez con una llamada real y está versionada; se comprueba el
   formato del audio y la forma de la respuesta, incluida la de la confianza por
   palabra (BR6.1, PA-2).
2. **En cada hito, a mano:** la misma prueba contra el proveedor real mide la
   latencia al primer audio con un texto fijo (BR6.2).

### F5 — Oír a Catalina (demostración de B18)

1. El comando nuevo `mise run voice:say`, que se crea con la generación de código, recibe la aseguradora, el idioma y la frase.
2. Recorre el camino real: configuración, fábrica, techo, adaptador y gasto.
3. Guarda el audio en `tmp/voice/` y lo reproduce si la máquina tiene
   reproductor (BR6.3).

## 3. Reglas (resumen derivado de `rules.md`)

| Familia | Reglas |
| --- | --- |
| Interfaces y adaptadores | BR1.1 a BR1.4 |
| Configuración | BR2.1 a BR2.3 |
| Transcripción | BR3.1, BR3.2 |
| Síntesis | BR4.1, BR4.2 |
| Gasto | BR5.1 |
| Pruebas de contrato y demostración | BR6.1 a BR6.3 |

## 4. Decisiones de esta etapa

| # | Decisión | Por qué |
| --- | --- | --- |
| FD-U15-1 | WebSocket y HTTP propio de cada proveedor, sin SDK (Q1) | Es la API principal que documentan los dos y el camino que midió el experimento 1 |
| FD-U15-2 | La configuración de voz vive en el bloque `voice` de `tenant.yaml` (Q2) | C-25 ya la puso ahí; una sola fuente |
| FD-U15-3 | Un comando nuevo, `mise run voice:say`, para oír a Catalina (Q3) | La demostración de B18 aprobada en DP-14 |
| FD-U15-4 | La confianza por palabra (PA-2) la fija la respuesta grabada; si falta, nula | Se decide con el dato del proveedor, no con una suposición |
| FD-U15-5 | `websockets` pasa de dependencia de desarrollo a dependencia de ejecución | Hoy solo la usa el experimento 1; ahora la usa el aplicativo |

## Sources

- `../../../inception/units-generation/unit-of-work.md` — sección U15.
- `../../../inception/user-stories/stories.md` — US5.10 y US5.11.
- `../../../inception/contract-design/contract-summary.md` — C-16, C-17 y C-25.
- `../../../inception/domain-design/decisions.md` — ADR-007, ADR-008 con sus
  enmiendas del 2026-09-21, y ADR-018.
- `scripts/experimento-1.py` — el camino medido.
- `../../../inception/requirements-analysis/requirements.md` — FR3.7 (cambiar de voz por configuración) y FR3.8 (voz de respaldo).

## Assumptions & Open Questions

- **La voz de respaldo en inglés** se elige al construir el adaptador, entre las
  voces de Aura-2 en inglés, comprobada contra la lista del proveedor. En español
  es `aura-2-celeste-es`, la que se midió.
- **PA-9, el tope por clave para los proveedores de voz,** se llena en los
  requisitos de calidad de esta unidad con la política que fijó U5: saldo
  prepagado sin recarga automática.
