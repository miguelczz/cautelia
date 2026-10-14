# Decisiones de stack — U17 `voice-public-link`

Versión corta: **ninguna tecnología nueva**, y la mayor parte del trabajo es cable.

| # | Qué | Por qué |
| --- | --- | --- |
| TECH-U17.1 | La decisión de admisión es una función pura en el módulo de la voz, con la forma de `chat/limits.py` | Presupuesto medible sin máquina, bordes cubiertos sin base de datos, y la frase resuelta en un solo sitio |
| TECH-U17.2 | Los dos carriles son campos de `CallConfig`, aditivos | Cambiarlos y desplegar no cambia código (AC5.12.4) |
| TECH-U17.3 | La elección de la voz se **cablea** a `quota.voice_mode`, que ya existe | Un segundo sitio donde decidir lo mismo es un sitio donde un día discrepan |
| TECH-U17.4 | La tabla de topes del proveedor es un archivo versionado de datos, no una tabla de la base | Es un registro que una persona mantiene y que una revisión lee; en la base no lo vería nadie y el reinicio nocturno tendría que aprender a no borrarlo |
| TECH-U17.5 | Los avisos de la consola son texto del catálogo y componentes que ya existen | Ninguna cadena visible en línea; ninguna alerta nueva |

## Lo diferido a la pasada de publicación

**Nada se difiere: esta unidad *es* la pasada de publicación de la voz.** Lo que queda
fuera de su alcance es configurar de verdad los topes en la consola de cada proveedor
—eso lo hace Miguel— y correr el simulacro del segundo día, que es del checklist.

## Sources

- `../functional-design/functional-design-questions.md` — FD-U17-1, FD-U17-5, FD-U17-8
- El código: `chat/limits.py`, `telemetry/spend/quota.py`, `tenancy/models.py`

## Assumptions & Open Questions

None.
