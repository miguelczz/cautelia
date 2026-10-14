# Requisitos de confiabilidad — U5 `provider-platform`

La pregunta de confiabilidad de esta unidad no es "¿sigue en pie?". Es **"¿sigue
cortando?"**. Un proceso vivo cuyo techo dejó de funcionar es peor que uno caído:
el caído no gasta.

Por eso lo que sigue no habla de nueves de disponibilidad —esta unidad corre
embebida en el proceso único, y la disponibilidad del enlace en vivo es NFR16, de
U6— sino de qué tiene que seguir siendo cierto cuando algo alrededor falla.

## Objetivos medibles

> **Corrección del 2026-09-21, aplicada en la compuerta de la unidad.** Este
> párrafo decía que los dos comandos que la tabla cita —`mise run test:u5` y
> `mise run spend:report`— **no existían todavía**. Ya existen: los creó la
> generación de código de esta unidad, están en el archivo de tareas y los
> nueve pasos del guion de verificación pasan con ellos dentro. Se corrige
> porque la regla del equipo es que la documentación describe lo construido, y
> una nota de "esto llegará" que sobrevive a su llegada es la deuda TD-03 que
> `team.md` nombra por su nombre.

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| NFR15.1 | Acumulado facturable de la ventana frente al techo, con el acumulado forzado al borde | **El techo no se pasa** por más del costo de la llamada al proveedor que estaba en vuelo | `mise run test:u5` |
| NFR15.2 | Alertas emitidas al cruzar los 3 USD, con veinte incrementos seguidos después del cruce | **Exactamente 1** | `mise run test:u5` |
| NFR15.3 | Acumulado de la ventana después de correr el reinicio nocturno y después de cruzar un cambio de mes con reloj inyectado | **No cambia** en ninguno de los dos casos | `mise run test:u5` |
| NFR15.4 | Llamadas facturables que se completan mientras el backend de trazas está caído, y estado del corte en ese momento | **Todas** se registran y el corte **sigue funcionando** | `mise run test:u5` |
| NFR15.5 | Llamadas facturables que pasan cuando la base no responde | **Exactamente 0**, y el chat en plan gratuito sigue respondiendo | `mise run test:u5` |
| NFR15.6 | Minutos de reserva de grabación disponibles con el cupo público agotado | **Los declarados**, intactos; y una llamada marcada como grabación se atiende | `mise run test:u5` |
| NFR15.7 | Llamadas facturables que pasan cuando la ventana tiene alguna llamada facturable sin valorar | **Exactamente 0**, y el chat en plan gratuito sigue respondiendo | `mise run test:u5` |
| REL-U5.1 | Reintentos tras una señal de saldo o cuota agotados | **Exactamente 0** intentos adicionales, y una señal explícita de parada | `mise run test:u5` |

## Qué tiene que seguir siendo cierto cuando algo falla

| Qué falla | Qué pasa | Qué sigue funcionando | Regla |
| --- | --- | --- | --- |
| El backend de trazas | Se registra la pérdida; los resúmenes de ese rato quedan `lost` | El caso, el registro de gasto, el acumulado y el corte | BR4.8, BR6.7 |
| La base de datos | Las llamadas facturables se rechazan con el motivo de presupuesto | El chat en plan gratuito, que no consume el techo | NFR-U5-3, Q5 |
| El proveedor del modelo | El error se traduce a uno de los cuatro tipos y el nodo decide según su política | Todo lo demás; el intento queda en la traza con su número | BR2.1, BR2.4, BR2.5 |
| El saldo o la cuota del proveedor | **No hay reintento**: sale la señal de parada, se nombra qué se acabó, y nadie recarga por iniciativa propia | El resto de los usos, porque cada uno tiene su clave y su proyecto | BR2.3, BR1.3 |
| El techo del proyecto | El carril público de la voz se cierra con el texto del catálogo antes de pedir el micrófono | El chat, y la reserva de grabación con su propio carril | BR4.4, BR4.9 |
| El precio de un modelo falta en la tabla y la llamada **no** se factura | El costo se registra "no medido", nunca cero, y viaja con el conteo | Todo; la cifra publicada dice cuánto no se midió | BR3.3, BR3.5 |
| El precio de un modelo falta en la tabla y la llamada **sí** se factura | Además de registrarse "no medido", el restante público queda sin medir y el carril público se cierra | El chat en plan gratuito, y la reserva de grabación con su propio carril | BR3.3, BR4.9, decisión del 2026-09-21 |
| El precio de la voz falta al convertir la reserva | Se corta el carril público y se deja abierto el de grabación | La grabación del video, que no se puede repetir cuando el presupuesto se acabó | Q2 |

## El techo, con su modo de fallo escrito

**Por qué el acumulado vive en una fila y no en una suma.** Dos razones, y las
dos son de fiabilidad. La primera: el corte tiene que funcionar aunque la
observación falle, y sumar el historial haría que el corte dependiera de que el
historial esté completo. La segunda, más dura: dos llamadas simultáneas que
sumaran cada una por su cuenta leerían un acumulado que no incluye a la otra, y
las dos pasarían creyendo que hay sitio. Una fila única se bloquea; una suma no.

**Cuánto se puede pasar, dicho con su cota.** El techo se consulta antes y el
costo se registra después, así que el exceso máximo es el costo de la llamada al
proveedor que estaba en vuelo cuando el acumulado cruzó. La alternativa
—reservar un estimado antes de llamar y conciliar después— nunca se pasa y exige
una tabla de reservas y una conciliación por llamada. Se eligió la cota y se
escribe, en vez de dejarla implícita.

**Qué no se relaja nunca.** El umbral. Cuando una corrida se pone roja por una
causa externa al cambio —proveedor caído, cambio de versión del modelo, cuota
agotada— se registra la causa y el identificador de la corrida, la corrida se
marca **no comparable** y se repite. Si sigue roja, bloquea. Una compuerta que no
se pudo ejecutar se declara "no medida", nunca se omite.

## Durabilidad y retención

| Qué | Sobrevive al reinicio nocturno | Sobrevive al cambio de mes | Por qué |
| --- | --- | --- | --- |
| Acumulado de la ventana | Sí | Sí | AC5.14.4 lo exige literalmente; es la cifra que no se puede perder |
| Filas de gasto | Sí, perdiendo el caso que nombraban | Sí | Son el histórico de costo; el caso borrado deja la columna vacía (BR7.5) |
| Contador de cuota del sitio | Sí | Sí, se renueva cada día por su periodo | Su sujeto es el sitio, no un visitante |
| Contadores de cuota de visitante y de sesión | No | — | Son dato de visitante y los borra el purgador (BR7.6) |
| Resúmenes de traza | No | — | Son dato de visitante y cuelgan del caso (BR7.4) |

**Ventana nueva.** Al abrir una ventana, el acumulado vuelve a cero y la marca de
alerta se vacía; la ventana anterior se conserva. Dentro de una ventana no hay
camino de vuelta desde `exhausted`, y eso es deliberado: un camino de vuelta
sería un camino para desbloquear el gasto sin decidirlo.

## Sources

- `<record>/inception/requirements-analysis/requirements.md` — NFR15, FR3.9,
  FR3.10, FR3.11, FR10.4
- `<record>/inception/user-stories/stories.md` — US5.14 con AC5.14.2, AC5.14.3 y
  AC5.14.4; decisión D11
- `<record>/inception/contract-design/contract-summary.md` — C-16 (parada sin
  reintento), C-17 (el corte no depende de la observación), C-23
- `<record>/construction/u5-provider-platform/functional-design/rules.md` —
  BR2.3, BR3.3, BR3.5, BR4.1 a BR4.10, BR6.7, BR7.4 a BR7.6
- `aidlc/spaces/default/memory/team.md` — la corrida no comparable y la
  prohibición de tocar el umbral
- `<record>/construction/u5-provider-platform/nfr-requirements/nfr-requirements-questions.md`
  — Q2 y Q5

## Assumptions & Open Questions

- Esta unidad no declara un objetivo de disponibilidad propio: corre embebida en
  el proceso único y la disponibilidad del enlace en vivo es NFR16, de U6
  `web-shell`, con el chequeo periódico del intent `infra`.
- El corte del reinicio nocturno —cuántas horas atrás borra— lo fija U20
  `demo-operations`; esta unidad expone su purgador y acepta el corte.
- La recuperación tras una caída de la base no tiene objetivo de tiempo aquí: el
  proceso es único y su reinicio lo decide el intent `infra`. Lo que sí se exige
  es que, mientras no responda, no pase ninguna llamada facturable.
