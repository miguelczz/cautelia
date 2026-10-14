# Decisiones de stack — U23 `comparison-view`

Versión corta: **ninguna tecnología nueva, y ninguna ruta nueva del servidor.**

| # | Qué | Por qué |
| --- | --- | --- |
| TECH-U23.1 | La vista habla por las tres rutas del chat que ya existen, tres veces | El aislamiento, el descuento triple de los límites y la carga por columna dejan de ser reglas que cumplir y pasan a ser hechos (FD-U23-1) |
| TECH-U23.2 | Tres flujos de eventos abiertos a la vez, uno por aseguradora | Es el transporte que el chat ya usa. Una conexión que multiplexara las tres sería una ruta nueva y un sitio nuevo donde el aislamiento puede romperse |
| TECH-U23.3 | La pantalla vive en `app/frontend/src/pages/comparison/`, con la base visual, el selector de idioma y el tema que ya existen | La convención de las ocho pantallas construidas |
| TECH-U23.4 | Ninguna biblioteca de tablas ni de comparación | Tres columnas de texto con citas no necesitan una, y una dependencia nueva de runtime hay que justificarla en una línea |

## Lo diferido a la pasada de publicación

Publicar la vista, con el checklist del segundo día. La unidad la construye y la deja
probada.

## Sources

- `../functional-design/functional-design-questions.md` — FD-U23-1 a FD-U23-4
- El código: `chat/api.py`, `app/frontend/src/pages/`

## Assumptions & Open Questions

None.
