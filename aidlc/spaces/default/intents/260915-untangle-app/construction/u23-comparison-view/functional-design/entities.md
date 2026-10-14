# Entidades — U23 `comparison-view`

Esta unidad **no crea ninguna entidad persistida y ninguna tabla**. Su estado vive en
la pantalla, y lo que sí se guarda son las tres conversaciones y los tres casos que el
chat ya sabe crear y que el contrato de borrado ya sabe borrar.

## Lo que ya existe y se reusa

| Qué | Dónde | Cómo lo usa esta vista |
| --- | --- | --- |
| Las tres rutas del chat público | `chat/api.py` | Tres veces, una por aseguradora: abrir flujo, mandar mensaje |
| La conversación por aseguradora | `chat/session.py` | Un navegador sostiene tres vivas, porque se resuelve por aseguradora y galleta |
| Los cinco controles de entrada | `chat/limits.py` | Sin tocarlos: tres mensajes son tres descuentos |
| La apertura de caso de una consulta | `chat/case_opening.py` | Una pregunta de cobertura abre un caso de consulta por columna |
| El contrato de borrado y su registro | `tenancy/purge.py` | Sin añadir purgador: no hay tabla nueva |
| El detector de idioma | `language.py` | Para fijar el idioma de las tres conversaciones |

## `ComparisonColumn` — el estado de una columna en la pantalla

No se persiste. Es lo que la vista sabe de cada aseguradora mientras espera.

| Campo | Qué es |
| --- | --- |
| `tenant_id` | Cuál aseguradora |
| `display_name` | Su nombre, del catálogo de configuración |
| `example_policy` | La póliza de ejemplo que usa, y para la agencia, quién la emitió |
| `state` | `idle`, `loading`, `answered`, `failed` o `rejected`. Conjunto cerrado |
| `answer` | La respuesta con sus citas, o "no encuentro una cláusula" |
| `limit` | Cuál límite la rechazó, cuando `state` es `rejected` |

**`failed` y `rejected` son estados distintos y no se colapsan.** Uno dice "no se pudo
revisar la póliza" y el otro "se alcanzó un límite"; se arreglan en sitios distintos y
quien evalúa necesita distinguirlos. Es la misma distinción que el proyecto sostiene
entre "no hay cláusula" y "no pude verificar".

**`state` por columna y no uno para la vista**: un estado global haría imposible que una
columna apareciera mientras otra carga (BR2.2).

## Lo que esta unidad no añade

- **Ninguna tabla**, ningún purgador, ningún contador propio de límites.
- **Ninguna entidad de comparación guardada**: la vista no recuerda preguntas
  anteriores, y no tiene que hacerlo.

## Sources

- `rules.md` — BR1.1 a BR3.2
- El código: `chat/`, `tenancy/purge.py`, `language.py`

## Assumptions & Open Questions

None.
