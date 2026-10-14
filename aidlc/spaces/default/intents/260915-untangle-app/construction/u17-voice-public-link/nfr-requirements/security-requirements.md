# Requisitos de seguridad — U17 `voice-public-link`

Versión corta. Cuatro requisitos. Aquí la seguridad es, sobre todo, **que nadie pueda
convertir un fallo en una factura**.

| # | Requisito | Cómo se comprueba |
| --- | --- | --- |
| SEC-U17.1 | Ninguna llamada pública se abre sin pasar los dos carriles, comprobado **en el servidor** y antes de pedir el micrófono | Prueba con los contadores forzados en cada borde: agotado el del visitante, agotado el del sitio, y los dos con margen (AC5.12.3, BR1.1) |
| SEC-U17.2 | Los topes están configurados **también en el proveedor**, con su tabla versionada y su fecha de comprobación | El simulacro del checklist del segundo día, con una clave de prueba de tope mínimo y la aplicación detenida. **Nunca llevando una clave real hasta su tope**: la prueba de un límite de gasto no consume el presupuesto que protege |
| SEC-U17.3 | El rechazo es el mismo sea cual sea su causa para quien lo recibe: dice cuál carril fue con la frase del catálogo, y nada del estado interno | Los cuatro motivos son una lista cerrada con su clave; ninguna frase se compone por interpolación |
| SEC-U17.4 | El techo de gasto no depende del carril por visitante | Prueba que el cálculo del techo no cuenta conexiones (AC5.12.6, BR1.4). Un visitante cambia de navegador, y un control de gasto que se puede esquivar cambiando de navegador no es un control |

**La galleta del visitante es la misma que la del chat**, y eso no cambia aquí: quien
llama y quien escribe son el mismo navegador, y dos galletas darían dos identidades a
la misma persona.

## Sources

- `../functional-design/rules.md` — BR1.1, BR1.4, BR4.1
- `../../../inception/user-stories/stories.md` — AC5.12.3, AC5.12.5, AC5.12.6
- La regla del proyecto sobre probar límites de gasto sin consumirlos

## Assumptions & Open Questions

None.
