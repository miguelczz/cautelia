# Requisitos de confiabilidad — U11 `intake`

Lo que tiene que seguir siendo cierto: que lo anotado sea lo que la persona
dijo, que el caso quede completo sin hacerla repetirse, y que el trato no se
degrade cuando está alterada.

Es la unidad con más metas del hito del proyecto, y ninguna es suya: **todas son
de U21 y U11 las realiza con su conducta.** Aquí se declaran con identificador
propio para que la matriz de verificación no cuente dos veces lo mismo.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| REL-U11.1 | Campos escritos sin evidencia del turno del que salieron (BR2.2) | **Exactamente 0** | Tarea nueva `mise run test:u11` |
| REL-U11.2 | Bloques contados como confirmados sin un sí de la persona (AC1.7.1, AC1.7.2) | **Exactamente 0** | Tarea nueva `mise run test:u11` |
| REL-U11.3 | Bloques cuya lectura de confirmación no nombra los campos de lesiones, conductor o lugar cuando existen (FD-U11-8) | **Exactamente 0** | Tarea nueva `mise run test:u11` |
| REL-U11.4 | Campos que se vuelven a preguntar habiéndose dicho ya (AC1.5.4) | **Exactamente 0** | `mise run evals:gate` |
| REL-U11.5 | Versiones que contradicen un dato confirmado y se pierden en vez de anotarse aparte (AC1.12.1, FD-U11-7) | **Exactamente 0** | Tarea nueva `mise run test:u11` |
| NFR7.2 | Casos de DS-2 con los siete campos correctos, sobre los no marcados incompletos por diseño (NFR7, dueña U21; AC1.7.5) | **95 % o más** por idioma | `mise run evals:gate` |
| NFR8.2 | Exactitud de extracción tras normalizar, en **cada uno** de los siete campos por separado (NFR8, dueña U21; AC1.7.5) | **95 % o más** por campo y por idioma | `mise run evals:gate` |
| NFR7.3 | Fidelidad de la lectura de confirmación contra lo que la persona dijo, normalizada (AC1.7.4) | **98 % o más** por idioma | `mise run evals:gate` |
| NFR13.3 | Turnos de la agente hasta cerrar o derivar, en los casos completos simples de DS-2 (AC1.5.6) | **14 o menos** por idioma | `mise run evals:gate` |
| NFR20.2 | Metas de esta unidad reducidas en uno de los dos idiomas (NFR20, dueña U21) | **Exactamente 0** | `mise run evals:gate` |

## La forma del turno, que juzga el código

Estas cuatro no dependen del juez, y por eso **se publican aunque el juez esté
descalibrado** (AC1.13.5). Es la mitad de la rúbrica de estilo que no hace falta
calibrar.

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| STYLE-U11.1 | Turnos con más de una pregunta, o de más de 25 palabras, fuera de las excepciones declaradas (AC1.5.3) | **Exactamente 0** | `mise run evals:gate` |
| STYLE-U11.2 | Turnos del chat con marcadores orales de la voz (AC1.5.3) | **Exactamente 0** | `mise run evals:gate` |
| STYLE-U11.3 | Turnos con una frase de la lista versionada que culpa o minimiza, con una forma con género de esa lista, o con el registro prohibido en español (AC1.13.2, AC1.13.4) | **Exactamente 0** | `mise run evals:gate` |
| STYLE-U11.4 | Turnos que siguen a una señal de emoción y no empiezan con una frase de reconocimiento (AC1.13.1) | **Exactamente 0** | `mise run evals:gate` |
| NFR20.3 | Rúbrica de estilo completa sobre DS-2, con el subconjunto con emoción publicado aparte (AC1.13.5, la juzga el juez) | **90 % o más** por idioma | `mise run evals:gate` |

## Cómo se comporta cuando algo falla

| Qué falla | Qué pasa | Regla |
| --- | --- | --- |
| El modelo no responde al extraer | Sube: la política de fallo la aplica el ejecutor común de U12, como en `decision` y `compliance` | convención 8b |
| La persona insulta | Frase de calma y oferta de que una persona revise; al siguiente, cierre por abuso y el caso queda "esperando al asegurado" | BR5.4 |
| La persona da un dato que contradice uno confirmado | Se guardan los dos, cada uno con su turno y su hora; la agente no cambia de tono | BR5.5 |
| Llega una señal de emergencia | La captura deja su orden en ese mismo turno | BR4.1 |
| Llega una pregunta de cobertura a mitad | La responde U8 en el ritmo de fondo; la captura retoma donde iba | BR4.2 |

## Sources

- `../functional-design/rules.md` — BR2.2, BR3.1, BR3.4, BR4.1, BR4.2, BR5.2 a
  BR5.5.
- `../functional-design/functional-spec.md` — FD-U11-4, FD-U11-7, FD-U11-8.
- `../../../inception/user-stories/stories.md` — AC1.5.3 a AC1.5.6, AC1.7.1 a
  AC1.7.5, AC1.12.1, AC1.13.1 a AC1.13.5.
- `../../../inception/units-generation/unit-of-work.md` — tabla de metas: NFR7,
  NFR8, NFR13 y NFR20 son de U21, y U11 las realiza.

## Assumptions & Open Questions

- **[assumption]** NFR7.2, NFR8.2, NFR7.3 y NFR13.3 solo se pueden medir cuando
  DS-2 corra de punta a punta, lo que necesita el conductor de chat de U13.
  Hasta entonces se publican como "no medida" con esa causa, igual que hizo U8
  con las suyas.
