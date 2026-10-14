# Decisiones de stack — U19 `quote`

Versión corta: esta unidad **no introduce ninguna tecnología nueva**, y eso es la
decisión. Tampoco introduce un directorio nuevo.

| # | Qué | Por qué |
| --- | --- | --- |
| TECH-U19.1 | Sin directorio propio: cada pieza vive en el módulo dueño —captura, esquema del caso, reglas, bandeja— con el tipo de registro `quote_request` | MOD-13 no tiene componente propio en el diseño de dominio, y abrir un módulo por tipo de registro convertiría el árbol en una lista de casos de uso |
| TECH-U19.2 | Las reglas de elegibilidad son un archivo YAML más en la carpeta de reglas de cada aseguradora, con el mismo vocabulario y el mismo formato de `tests` que el triage | El motor ya es de datos. Un segundo formato de reglas sería un segundo cargador y un segundo sitio donde probarlas |
| TECH-U19.3 | Ningún detector de importes propio: la guardia de salida que ya existe | Un segundo umbral es un umbral que un día discrepa del primero |
| TECH-U19.4 | El rol y su permiso son datos: un valor de enum y una fila de la tabla de permisos | Es lo que `tenancy/models.py` ya pide para una acción nueva |

## Lo diferido a la pasada de publicación

Nada de esta unidad se difiere. La cotización queda activa solo en Sunmeadow Auto, y
publicar sus pantallas es la misma pasada que las demás.

## Sources

- `../functional-design/functional-design-questions.md` — FD-U19-1, FD-U19-5, FD-U19-8
- El código: `rules/`, `app/config/tenants/*/rules/`, `tenancy/models.py`

## Assumptions & Open Questions

None.
