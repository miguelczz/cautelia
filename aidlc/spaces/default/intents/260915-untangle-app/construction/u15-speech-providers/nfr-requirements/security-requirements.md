# Requisitos de seguridad — U15 `speech-providers`

U15 no registra metas propias del proyecto: aporta a las de otras unidades. Lo
que protege son tres cosas: que el protocolo de cada proveedor no salga de su
adaptador, que la voz no gaste más de lo que el techo permite ni con la
aplicación detenida, y que ni el audio ni el texto transcrito queden en ningún
sitio.

**`mise run test:u15` no existe todavía**: lo crea la generación de código de
esta unidad. Los demás comandos existen hoy.

## Modelo de amenazas

| Amenaza | Qué podría pasar | Control | Requisito |
| --- | --- | --- | --- |
| Fuga de protocolo | Otro módulo abre un WebSocket a un proveedor y se salta gasto y taxonomía | Contrato `forbidden` de importación | SEC-U15.1 |
| Clave cruzada | La voz usa la clave del chat y agota su cuota | Fábrica por uso | SEC-U15.2 |
| Gasto sin freno | Con la aplicación caída, una clave filtrada sigue gastando | Tope del lado del proveedor | PA-9.2 |
| Gasto por encima del techo | Una llamada sale con el techo ya cerrado | Techo antes de cada llamada | SEC-U15.3 |
| Retención de audio | El audio o la transcripción quedan en un log, una traza o el disco | El adaptador no escribe nada | SEC-U15.4, NFR19.5 |

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| SEC-U15.1 | Archivos fuera de los adaptadores que usan el protocolo de un proveedor de voz | **Exactamente 0** | `mise run lint` (contrato de importación) |
| SEC-U15.2 | Adaptadores de voz construidos con una clave distinta de la del uso `voice` | **Exactamente 0** | `mise run test:u15` |
| SEC-U15.3 | Llamadas a un proveedor de voz con el techo cerrado, con el acumulado forzado en la prueba | **Exactamente 0**; sale `BudgetExhausted` sin reintento | `mise run test:u15` |
| SEC-U15.4 | Eventos, logs o trazas del adaptador que contienen audio o texto transcrito | **Exactamente 0** | `mise run test:u15` |
| PA-9.2 | Filas de tope de Deepgram y de Cartesia para el uso `voice`, con su figura y su fecha de comprobación | **Las dos presentes y con menos de 30 días** | `mise run schema:check` |
| NFR11.9 | Datos personales en lo que emiten los adaptadores de voz | **Exactamente 0** (NFR11, dueña U3) | `mise run test:u15` |
| NFR14.4 | Llamadas de transcripción o de síntesis que quedan "no medidas" en el registro de gasto | **Exactamente 0**: las dos tienen precio de lista (NFR14, dueña U5) | `mise run test:u15` |
| NFR19.5 | Audio escrito en disco o en la base por el aplicativo | **Exactamente 0** (NFR19, dueña U20). El comando de demostración escribe en `tmp/voice/`, que git ignora y no es parte del aplicativo servido | `mise run test:u15` |
| NFR20.3 | Aseguradoras sin voz principal o sin voz de respaldo en alguno de los dos idiomas | **Exactamente 0** (NFR20, dueña U21) | `mise run test:u15` |

## Las dos filas de PA-9

La política la fijó U5: una alerta de presupuesto no cuenta como tope, y donde
no hay tope duro lo sustituye un saldo prepagado sin recarga automática. U15
llena sus dos filas en `app/config/providers/prices.yaml` al generar el código:

| Proveedor | Figura | Por qué |
| --- | --- | --- |
| Deepgram (transcripción y Aura-2) | `prepaid_balance` | La cuenta usa el crédito gratuito sin tarjeta y con la recarga automática apagada: cuando el saldo llega a cero, el proveedor deja de atender, también con la aplicación detenida |
| Cartesia (Catalina) | `monthly_cap` | El plan gratuito trae un cupo mensual de créditos que se detiene al agotarse, sin cobro de excedentes |

La fecha de comprobación es la del día en que se escriben, y la compuerta de los
30 días obliga a volver a mirarlas. Si Miguel pasa alguna cuenta a un plan de
pago, la fila cambia ese mismo día y su recarga automática sigue apagada
(`project.md`: ninguna cuenta con renovación, recarga ni excedentes).

## Sources

- `../functional-design/rules.md` — BR1.1 a BR6.3.
- `../../u5-provider-platform/nfr-requirements/security-requirements.md` — la
  política de PA-9 que U15 hereda.
- `../../../inception/requirements-analysis/requirements.md` — NFR11, NFR14,
  NFR19 y NFR20.
- `../../../inception/contract-design/contract-summary.md` — C-16 y C-17.
- `app/config/providers/prices.yaml` — tabla de topes.

## Assumptions & Open Questions

- **Las figuras de las dos filas salen de las páginas públicas de precios y de lo
  que Miguel configuró al crear las cuentas.** Si la consola de alguno muestra
  otra cosa, se corrige la fila, no la política.
