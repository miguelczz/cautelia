# Decisiones de herramientas — U15 `speech-providers`

**Ninguna dependencia nueva.** `websockets` ya está en el manifiesto como
dependencia de desarrollo, porque la usó el experimento 1; pasa a dependencia de
ejecución con su línea de justificación (qué hace, por qué no alcanza la
biblioteca estándar, licencia BSD-3-Clause). `httpx` ya es de ejecución. Sin SDK
de proveedores (FD-U15-1).

| Pieza | Con qué | Por qué |
| --- | --- | --- |
| Transcripción en streaming | WebSocket de Deepgram con `nova-3` en modo `multi` | ADR-007; el camino medido |
| Síntesis principal | WebSocket de Cartesia con `sonic-3.6` y Catalina | ADR-008 |
| Síntesis de respaldo | API de Aura-2 de Deepgram | ADR-008, enmienda del 2026-09-21 |
| Respuestas grabadas | Archivos versionados junto a las pruebas de contrato, capturados una vez con una llamada real | AC5.10.3 |

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| TECH-U15.1 | La prueba de contrato de cada proveedor contra su respuesta grabada | **En verde en cada entrega** | `mise run test:u15` |
| TECH-U15.2 | Latencia al primer audio de cada voz con un texto fijo, contra el proveedor real | **Publicada en cada hito, sin umbral propio**: la meta del turno es NFR1, de U16 | Tarea nueva `mise run voice:contract-live`, a mano |
| TECH-U15.3 | La demostración de B18: oír a Catalina por el camino del aplicativo | **Se oye** | Tarea nueva `mise run voice:say` |

## Sources

- `../functional-design/functional-spec.md` — FD-U15-1 a FD-U15-5.
- `../../../inception/domain-design/decisions.md` — ADR-007 y ADR-008.
- `aidlc/spaces/default/codekb/untangle/technology-stack.md` — stack del
  aplicativo.
- `scripts/experimento-1.py` — el camino medido.

## Assumptions & Open Questions

- Ninguna.
