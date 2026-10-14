# Decisiones de stack — U18 `voice-spanish`

**Ninguna dependencia nueva.** Es la decisión, y conviene decirla así.

| Qué | Con qué se hace | Por qué no otra cosa |
| --- | --- | --- |
| Detección de idioma | `lingua`, que ya está instalada y la usa el chat | Añadir un segundo detector sería dos definiciones de "señal suficiente" en un proyecto que publica adherencia de idioma por idioma |
| Reconocimiento de la petición | Código y una lista versionada | Un modelo para decidir un cambio de estado de la conversación es lo que ADR-003 prohíbe para la transición del grafo, por la misma razón |
| Voz en español | La misma de U15, ya configurada | AC1.28.2 pide una sola identidad para los dos idiomas |
| Frases | El catálogo por idioma que ya existe | Ninguna cadena visible se escribe en línea |

## Dónde vive el código

| Qué | Dónde |
| --- | --- |
| El detector, subido de `chat/` en la tanda 1 | `app/backend/src/untangle/language.py`, hoja y con su propio contrato de importación |
| La petición de cambio y la escalera del idioma no atendido | `app/backend/src/untangle/voice/` |
| El campo de configuración | `app/config/tenants/*/tenant.yaml` y su esquema |
| El chequeo del registro en español | `app/backend/src/untangle/evals/content_checks.py`, que ya existe |

## El único movimiento de código ajeno

`chat/language.py` desaparece y su contenido sube a `untangle/language.py`. Los
consumidores de U13 apuntan al nuevo en el mismo cambio, y **no queda
reexportador**: dos caminos al mismo sitio es como uno de los dos se queda atrás.

Es el mismo movimiento que U6 hizo con `surface_spec.py`, y por la misma razón: una
pieza que varias unidades necesitan y que no pertenece a ninguna.

## Sources

- `../functional-design/functional-design-questions.md` — D1, D2
- ADR-003, ADR-008
- `app/backend/src/untangle/language.py` — donde quedó tras la tanda 1

## Assumptions & Open Questions

None.
