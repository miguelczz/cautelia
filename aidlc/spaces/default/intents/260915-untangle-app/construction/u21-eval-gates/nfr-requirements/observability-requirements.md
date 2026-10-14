# Observabilidad — U21 `eval-gates`

El reporte **es** la observabilidad de esta unidad: no hay un panel aparte ni
métricas de proceso que vigilar. Lo que se pide es que ese reporte sea legible
sin contexto y que su origen quede anclado.

| Qué se observa | Dónde | Por qué |
| --- | --- | --- |
| Condiciones de la corrida: commit, identificadores exactos de modelo, huellas de los prompts, subconjunto, duración y si es comparable | La cabecera del reporte, **antes** de la primera cifra | Son las condiciones bajo las que esa cifra vale; en un apéndice nadie las lee |
| Cada caso con su veredicto, su tipo de juicio, su causa raíz y su traza | El cuerpo del reporte | Es lo que permite pasar de "falló" a "por qué falló" |
| Qué cambió contra la línea base | Sección propia del reporte | Es la diferencia que decide si hay regresión |
| Lo que no se pudo medir | Marcado como "no medida" con su causa | Omitirlo se leería como verde |

Los eventos del comando salen por el mismo punto de observabilidad que ya usa el
corredor de U1, con el identificador de la corrida, y pasan por la redacción
como cualquier otra salida.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| OBS-U21.1 | Cifras publicadas sin cabecera con commit e identificadores de modelo | **Exactamente 0** | Tarea nueva `mise run test:u21` |
| OBS-U21.2 | Casos fallidos sin causa raíz de la taxonomía del PRD 11.3 | **Exactamente 0** | Tarea nueva `mise run evals:gate` |

## Sources

- `../functional-design/rules.md` — BR1.1 y BR1.3.
- `app/backend/src/untangle/evals/report.py` — la cabecera que dejó U1.

## Assumptions & Open Questions

- **[assumption]** La taxonomía de causa raíz es la del PRD 11.3 y se fija como
  enum cerrado; ninguna categoría nueva se inventa en esta unidad.
