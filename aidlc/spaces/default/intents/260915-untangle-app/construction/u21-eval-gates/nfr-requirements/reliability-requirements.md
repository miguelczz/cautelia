# Confiabilidad — U21 `eval-gates`

La compuerta tiene una obligación que las demás unidades no tienen: **fallar
solo cuando el cambio es el culpable**. Un rojo que no distingue una regresión
de una caída del proveedor entrena a cualquiera a ignorarlo.

## Qué puede fallar y qué se hace

| Fallo | Qué hace la compuerta | Requisito |
| --- | --- | --- |
| El proveedor se cae o la cuota se agota | La corrida se marca **no comparable** con su causa y su identificador, y se repite. Si sigue roja, bloquea; el umbral no se toca nunca | REL-U21.1 |
| El backend de trazas no está corriendo | El reporte sale con el enlace de traza marcado como no disponible, no vacío ni inventado; la corrida sigue | REL-U21.2 |
| Un caso cambia de veredicto entre corridas idénticas | Se marca inestable con la evidencia de las dos corridas, sale aparte, no cuenta para la compuerta y sigue en el set | REL-U21.3 |
| Falta la línea base | La compuerta corre, publica y dice en la cabecera que no comparó | REL-U21.4 |
| El archivo de explicaciones está roto o vacío | La compuerta trata la regresión como no explicada y queda en rojo: el fallo es hacia el lado seguro | REL-U21.5 |

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| REL-U21.1 | Corridas rojas por causa externa que quedan registradas sin su causa y su identificador | **Exactamente 0** | Tarea nueva `mise run test:u21` |
| REL-U21.3 | Casos inestables que cuentan para la compuerta, o que se borraron del set | **Exactamente 0** | Tarea nueva `mise run test:u21` |
| REL-U21.5 | Regresiones que pasan sin explicación que las nombre | **Exactamente 0** | Tarea nueva `mise run evals:gate` |

## Sources

- `../functional-design/rules.md` — BR1.3, BR2.2 y BR2.4.
- `aidlc/spaces/default/memory/team.md` — compuerta en rojo por causa ajena al
  cambio y determinismo de la corrida.

## Assumptions & Open Questions

- **[assumption]** Repetir una corrida no comparable es una acción humana o de la
  tubería, no un reintento automático dentro del comando: reintentar solo
  escondería una caída sostenida del proveedor.
