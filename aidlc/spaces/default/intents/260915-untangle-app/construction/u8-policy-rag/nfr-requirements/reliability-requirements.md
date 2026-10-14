# Requisitos de confiabilidad — U8 `policy-rag`

Lo que tiene que seguir siendo cierto: que la cláusula correcta se encuentre,
que "no encuentro" sea la respuesta cuando no hay nada que encontrar, y que un
fallo de infraestructura no se disfrace de respuesta ni contamine una métrica
publicada.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| REL-U8.1 | Preguntas de DS-3 con cláusula esperada en las que esa cláusula está entre las recuperadas, por idioma, incluidas las pólizas con pocos fragmentos (AC2.1.3) | **95 % o más** en cada idioma | `mise run evals:gate` |
| REL-U8.2 | Las cinco preguntas sin cláusula por idioma que reciben "no encuentro una cláusula" sin cita forzada (AC2.5.4) | **90 % o más**, que con cinco preguntas significa **cinco de cinco** | `mise run evals:gate` |
| REL-U8.3 | Reintentos ante un fallo de recuperación antes de degradar (AC2.6.1) | **Exactamente 1** | Tarea nueva `mise run test:u8` |
| REL-U8.4 | Casos `unverifiable` contados dentro de la tasa de "no encuentro" correcto (AC2.6.4) | **Exactamente 0**: se publican aparte | `mise run evals:gate` |
| REL-U8.5 | Respuestas de cobertura duplicadas tras reanudar el grafo con la misma clave de caso y turno (ADR-003) | **Exactamente 0** | Tarea nueva `mise run test:u8` |
| REL-U8.6 | Ingestas que dejan el índice a medias tras un archivo inválido (AC5.2.2) | **Exactamente 0**: la base queda como estaba | Tarea nueva `mise run test:u8` |
| NFR5.1 | Precisión de citación sobre DS-3 y los casos de DS-2 con pregunta de cobertura, por idioma (NFR5, dueña U21; U8 implementa la conducta) | **95 % o más** en cada idioma | `mise run evals:gate` |
| NFR20.1 | Metas de esta unidad reducidas en uno de los dos idiomas (NFR20, dueña U21) | **Exactamente 0**: las mismas metas y los mismos casos en español e inglés | `mise run evals:gate` |

## Cómo se comporta cuando algo falla

| Qué falla | Qué pasa | Regla |
| --- | --- | --- |
| La recuperación no responde a tiempo | Un reintento; si vuelve a fallar, `unverifiable`, frase del catálogo y derivación | BR5.2 |
| El proveedor de embeddings no responde en la consulta | Igual que arriba: es un fallo de la recuperación, no una respuesta sin cláusula | BR3.4, BR5.2 |
| El proveedor de embeddings no responde en la ingesta | La ingesta falla entera y la base queda como estaba; no hay índice a medias | BR1.2, REL-U8.6 |
| El corpus no casa con su manifiesto | La ingesta no empieza, nombrando el archivo | BR1.1 |
| La póliza está fuera de vigencia | Conjunto vacío, que se traduce a `no_clause_found`; no es un fallo | BR2.2 |
| El juez no está calibrado | El respaldo se publica como "no medida" con su causa; las cuatro comprobaciones exactas siguen bloqueando | BR3.6 |

La distinción que sostiene toda la tabla: **`no_clause_found` es un resultado,
`unverifiable` es un fallo**, y una métrica que los sume cuenta caídas de
infraestructura como conducta de la agente (BR3.4).

## Sources

- `../functional-design/rules.md` — BR1.1, BR1.2, BR2.2, BR3.4, BR3.6, BR4.2,
  BR5.2.
- `../../../inception/user-stories/stories.md` — AC2.1.3, AC2.5.4, AC2.6.1,
  AC2.6.4, AC5.2.2.
- `../../../inception/units-generation/unit-of-work.md` — tabla de metas: NFR5 y
  NFR20 son de U21 y U8 las verifica con su conducta.

## Assumptions & Open Questions

- **[assumption]** REL-U8.1 y NFR5.1 solo se pueden medir cuando existan los 40
  casos de DS-3, que son alcance de esta unidad y se escriben antes del código.
  Hasta la primera corrida completa, las dos se publican como "no medida" con
  esa causa, nunca como verde.
