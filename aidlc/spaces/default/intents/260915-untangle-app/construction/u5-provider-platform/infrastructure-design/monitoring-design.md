# Monitoreo — U5 `provider-platform`

Lo que el diseño de observabilidad decidió, puesto en la plataforma que existe:
Langfuse en local, un archivo OTLP en la tubería, y ningún destino público
todavía.

Una aclaración antes de las tablas, porque cambia cómo se leen: **este proyecto
no tiene guardia de turno**. Las alertas no despiertan a nadie; llegan al canal
que el intent `infra` decida y las lee Miguel cuando las lee. Por eso hay una
sola alerta y no diez: una alerta que nadie va a atender de madrugada, puesta
entre otras nueve, es ruido con formato de aviso.

## Métricas e indicadores

| Métrica | De dónde sale | Umbral | Por qué importa |
| --- | --- | --- | --- |
| Acumulado facturable de la ventana | La fila única, nunca una suma | Alerta en 3 USD, corte en 5 USD | Es la cifra de la que depende que la voz siga publicada |
| Llamadas facturables no medidas | La misma fila | Sin umbral; se publica siempre junto al total | Un acumulado con veinte llamadas sin precio no significa lo mismo que uno sin ninguna |
| Costo por caso, por proveedor y por mes | `mise run spend:report` sobre el registro | Sin umbral; NFR14 lo publica por versión | Es una de las cinco cifras del video |
| Cupo del sitio del día | El contador, con el límite que regía al abrirlo | Cero es el corte, no un fallo | Permite explicar un rechazo meses después con el número que de verdad regía |
| Llamadas por tipo de error | Los eventos de intento | Sin umbral fijo | Ver que un proveedor se degrada **antes** de que el circuito abra |
| Aperturas de cortacircuitos | Sus eventos de cambio de estado | Cualquiera merece mirarse | Distingue "el proveedor va lento" de "el proveedor está caído" |
| Resúmenes de traza perdidos | Los que llegan a `lost` | Sin umbral | Dice si el backend de trazas está sano sin que eso detenga nada |
| Latencia de la transacción de gasto | El tramo de la escritura | 15 ms en p95 | Si se pasa, lo que se revisa es la base, no la decisión de que sea síncrona |

Ninguna se publica como promedio combinado de los dos idiomas donde el idioma
aplique. Es la regla de paridad del proyecto.

## Alertas

| Alerta | Condición | Severidad | A dónde va |
| --- | --- | --- | --- |
| Presupuesto en 3 USD | El acumulado facturable cruza la alerta y la marca de enviada está vacía | Atender el mismo día | El canal que fije el intent `infra` (PA-10) |

**Una y nada más**, y las razones de las que no están:

- **El techo alcanzado no alerta.** El sistema ya respondió por sí mismo: el
  carril público se cerró con el texto del catálogo. Alertar de algo resuelto es
  el ruido que hace que las alertas dejen de leerse.
- **El cortacircuitos abierto no alerta.** Es una respuesta de diseño a un
  proveedor caído, y se ve en su métrica. Si se abriera todos los días, lo que
  hace falta es mirar la métrica, no un aviso por vez.
- **Los resúmenes perdidos no alertan.** Es una señal de que el panel de trazas
  está caído, y el panel de trazas caído no detiene nada.

La alerta de prueba del checklist del segundo día tiene que llegar por **este
mismo canal**: una alerta que solo se prueba el día que importa no está probada.

## Indicadores de nivel de servicio

| Indicador | Objetivo | Ventana de medición |
| --- | --- | --- |
| Llamadas facturables que se registran | 100 % | Por corrida de pruebas; es una invariante, no una estadística |
| Exceso sobre el techo | A lo sumo el costo de la llamada en vuelo | Por corrida de pruebas |
| Alertas emitidas por cruce | Exactamente 1 | Por corrida de pruebas |
| Resolución del resumen de traza | 10 s o menos hasta `ready` o `lost` | Por respuesta |

**No hay objetivo de disponibilidad propio.** Esta unidad corre embebida en el
proceso único; la disponibilidad del enlace en vivo es NFR16 y es de U6, con el
chequeo periódico del intent `infra`. Declarar aquí un nueve sería inventar una
fila que nadie puede hacer verde.

## Registros y trazas

**Trazas.** Tres niveles anidados —turno, nodo, llamada—, con las convenciones
`gen_ai.*` y su versión anclada. Emitidas por el ayudante de esta unidad, con
lista cerrada de atributos. Exportadas por lotes, fuera del camino de la
respuesta, al backend cuando hay destino y al archivo de la corrida cuando no.
**Todo pasa por la redacción antes de salir.**

**Registros.** Esta unidad no introduce un canal de registro propio: usa el punto
único de salida que U3 declara, con las mismas reglas. Lo que sí aporta es una
lista de lo que **nunca** entra en un evento suyo: ninguna clave, ningún prompt
completo, ninguna respuesta del modelo, ningún texto del asegurado.

**Sin muestreo.** A este volumen —cupos diarios de un dígito— se traza todo.
Muestrear introduciría una fuente de error en cifras que se publican, y ahorraría
un espacio que nadie necesita. Si el volumen cambiara, es una decisión del intent
`infra` con su medición.

## Paneles

Esta unidad **no dibuja ninguno**. El panel de gasto y el de cifras son de U22
`public-evidence`; el resumen de traza junto a una respuesta lo dibuja U13
`chat`; la traza por nodo de un caso la enseña U14 `inbox`. Lo que U5 entrega son
los datos y las decisiones, con una obligación que viaja con ellos: **ningún
consumidor puede publicar un total de costo sin su conteo de no medidas**,
porque el tipo que devuelve la agregación lleva el conteo dentro.

En local, el panel de Langfuse existe y se usa para la cola de anotación de la
revisión semanal y de DS-7. No es de esta unidad; esta unidad lo alimenta.

## Sources

- `../nfr-design/observability-design.md` — el ayudante con lista cerrada, los
  tres niveles, el plazo de `lost` y la alerta
- `../nfr-requirements/observability-requirements.md` — OBS-U5.1 a OBS-U5.6
- `../nfr-design/reliability-design.md` — el cortacircuitos y sus eventos
- `<record>/inception/contract-design/contract-summary.md` — C-23 y C-13
- `docs/reference/arquitectura-y-tecnologia.md` — §11
- `docker-compose.yml` — el perfil `traces` que ya existe

## Assumptions & Open Questions

- El canal de la alerta lo fija el intent `infra` (PA-10). Sin él, el evento se
  emite y la marca se escribe; lo que falta es quién lo entrega.
- La versión exacta de las convenciones `gen_ai.*` se ancla en la generación de
  código: están en estado de desarrollo y sin anclarla un cambio del estándar
  movería los nombres de los atributos sin avisar.
- La retención del artefacto de la corrida y el destino público del backend de
  trazas los decide el intent `infra`.
