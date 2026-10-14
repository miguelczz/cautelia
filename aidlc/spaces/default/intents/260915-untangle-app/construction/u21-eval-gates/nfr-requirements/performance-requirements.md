# Metas medibles y rendimiento — U21 `eval-gates`

U21 es donde se registran las metas de calidad que miden las evaluaciones
(UG-13): no las produce, las **mide y las publica**, con el comando exacto que
da su valor real. Su propia meta de rendimiento es una sola: cuánto tarda la
corrida.

## Las metas que esta unidad mide

Cada una nace en `requirements-analysis`; aquí queda su comando y la regla que
la sostiene. Todas se publican **por idioma**, nunca combinadas (NFR20).

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| NFR5.1 | Precisión de citación sobre DS-3: la cláusula existe, es de esa póliza y sostiene la afirmación | **95 % o más** por idioma | Tarea nueva `mise run evals:gate` |
| NFR7.1 | Completitud del primer aviso en los siete campos, sobre DS-2 | **95 % o más** por idioma | Tarea nueva `mise run evals:gate` |
| NFR8.1 | Exactitud de extracción por campo, tras normalizar | **95 % o más** por campo e idioma | Tarea nueva `mise run evals:gate` |
| NFR13.2 | Derivaciones correctas e innecesarias sobre DS-2 completo | **100 %** correctas y **10 % o menos** innecesarias | Tarea nueva `mise run evals:gate` |
| NFR17.1 | Duración de la corrida de texto en la tubería | **10 minutos o menos** | Tarea nueva `mise run evals:gate` |
| NFR20.1 | Metas o casos que existen en un idioma y no en el otro | **Exactamente 0** | Tarea nueva `mise run test:u21` |

Ninguna de estas metas se mide todavía de punta a punta: las conductas que
evalúan llegan con U11, U12 y U13. U21 deja **el medidor y la compuerta**; hasta
entonces cada una se publica como "no medida" con esa causa, que es exactamente
lo que BR1.3 exige y lo contrario de omitirla.

## El presupuesto de la propia corrida

| Qué | Meta | Cómo se sostiene |
| --- | --- | --- |
| Duración de la corrida de texto | 10 minutos o menos | El subconjunto declarado corre en cada entrega; la corrida completa, por hito |
| Sobrecosto de la compuerta sobre la corrida | Menos de 5 segundos | Comparar contra la línea base es leer archivos y contar; el segundo detector es determinista y no llama a ningún modelo |
| Determinismo | Dos corridas del mismo commit dan el mismo veredicto por caso | Temperatura en cero, semilla fija, modelo anclado por identificador exacto; lo que siga moviéndose se marca inestable y se reporta aparte |

## Sources

- `../../../inception/requirements-analysis/requirements.md` — NFR5, NFR7, NFR8,
  NFR13, NFR17 y NFR20.
- `../../../inception/units-generation/unit-of-work.md` — UG-13 y la sección U21.
- `../functional-design/rules.md` — BR1.3, BR2.4 y BR5.1.

## Assumptions & Open Questions

- **[assumption]** El sobrecosto de 5 segundos es una meta propia de esta unidad,
  no un umbral heredado: sale de que la comparación no llama a ningún proveedor.
