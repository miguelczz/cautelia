# Infraestructura — U5 `provider-platform`

Esta unidad es de tipo `service` por lo que hace —corre el corte de gasto, los
límites y la exportación de trazas del proceso, con metas propias de
confiabilidad y de observabilidad— y no por dónde corre: **corre embebida en el
proceso único**, como todas.

Así que este documento tiene poco que decidir y bastante que **declarar**: qué
usa de lo que ya existe, qué añade, y qué le deja encargado al intent `infra`.

## Despliegue

| Faceta | Elección | Razón |
| --- | --- | --- |
| Modelo de cómputo | Embebida en el proceso único del aplicativo | No hay nada en esta unidad que se beneficie de un proceso aparte: sus operaciones son transacciones cortas dentro del camino de otras unidades. Separarla añadiría una llamada de red al camino del turno |
| Topología de red | Ninguna propia. Salidas hacia la API del proveedor de modelo y hacia el backend de trazas cuando hay destino | Las dos son salientes; esta unidad no expone puerto ni ruta. Sus tres contratos son llamadas en proceso |
| Almacenamiento | Las cuatro tablas en la misma base del aplicativo, por el punto único de sesión de U2 | Una base aparte para el gasto obligaría a una segunda transacción y perdería la propiedad de que la fila de gasto y el acumulado se escriben juntos |
| Entornos | Local con `docker compose`; la tubería sin backend de trazas; el resto lo decide el intent `infra` | Es el reparto que el proyecto ya tiene, y esta unidad no lo cambia |
| Infraestructura como código | Ninguna propia. Las imágenes que usa ya están ancladas por huella en `docker-compose.yml` | El aprovisionamiento es del intent `infra` |
| Dimensionado | Sin requisitos propios de CPU ni de memoria más allá de la cola acotada del registro diferido | El volumen de esta unidad es de un dígito de llamadas de voz al día y los límites del chat |

## Servicios de infraestructura

| Servicio | Rol | Configuración | Notas |
| --- | --- | --- | --- |
| PostgreSQL | Base de datos | La misma del aplicativo, imagen anclada por huella; el pool lo dimensiona U2 | Cuatro tablas nuevas. La única exigencia propia de U5 es el tipo numérico exacto para el dinero, nunca coma flotante |
| Langfuse | Backend de trazas | Perfil `traces` de `docker compose`, con su propia base; imágenes ancladas por huella | **Ya existe** desde el primer commit. Dependencia opcional: sin destino, el aplicativo funciona y los resúmenes se declaran perdidos |
| API de Gemini | Proveedor de modelo | Un proyecto y una clave por uso; identificador de modelo exacto en configuración versionada | Cuatro usos: voz, chat, evaluaciones y operación. Gemini limita **por proyecto**, no por clave, así que separar solo claves no separaría cuotas |
| Archivo OTLP | Destino de trazas de la tubería | Artefacto de la corrida, retención corta, redactado | Es el camino sin backend, y no una excepción: sale por el mismo punto único |

## Infraestructura compartida

| Recurso compartido | Unidad dueña | Unidades consumidoras | Frontera de acceso |
| --- | --- | --- | --- |
| Punto único de sesión de base de datos | U2 `tenancy` | Toda unidad con tablas, incluida U5 | Contrato de importación: ningún módulo importa el driver directamente |
| Lista de exclusión del aislamiento y su aserción | U2 `tenancy` | U5 añade tres entradas con su razón | La lista vive en el manifiesto; la aserción la lee y comprueba el catálogo vivo |
| Punto único de salida redactada | U3 `pii-redaction` | U5 declara sus salidas ahí; no inventa una nueva | Registro cerrado de puntos de salida |
| Catálogo de textos | U1 `workspace` | U5 añade sus claves en los dos idiomas | Claves literales, comprobadas por paridad y por consumidor |
| Puertos de proveedor y fábrica por uso | **U5 y U15, en copropiedad** (C-16) | U7, U8, U10, U11, U15, U21 | `providers/ports.py`; el SDK no sale de `adapters/`. U5 declara los cuatro puertos e implementa los dos del modelo; U15 implementa los dos de la voz |
| Gasto, cuotas y techo | **U5** | U13, U16, U17, U22 | `telemetry/spend/api.py` |
| Trazas y resúmenes | **U5** | Todas | `telemetry/traces/api.py`, con lista cerrada de atributos |
| Backend de trazas local | Compartido; lo aprovisiona `docker compose` | U5 exporta; U21 lee para latencias | Opcional: su ausencia no detiene nada |

Las tres últimas filas son las superficies que **esta unidad** pasa a ofrecer, y
la primera de ellas **en copropiedad con U15**: C-16 declara dos dueños, U5 para
el modelo y los embeddings y U15 para la transcripción y la síntesis. En la
práctica eso significa que U5 escribe `ports.py` con los cuatro `Protocol` y
implementa dos; U15 implementa los otros dos sin volver a abrir el archivo.

Tres contratos son muchos para una unidad, y la razón de que no se puedan fundir
es que cada uno existe para que algo **no** dependa de otra cosa: los puertos,
para que el núcleo no conozca proveedores; la contabilidad, para que el corte no
dependa de la observación; las trazas, para que todas las unidades emitan igual.
Fundirlos dos a dos rompería justamente la independencia que compran.

## Lo que queda encargado al intent `infra`

| Encargo | Por qué no se decide aquí |
| --- | --- |
| El destino público del backend de trazas | No hay entorno público elegido; la preferencia escrita es exportar solo el resumen y una muestra redactada |
| El canal por el que sale la alerta de los 3 USD (PA-10) | Es una decisión de operación, no de esta unidad. Aquí se emite el evento y se escribe la marca |
| El origen del chequeo periódico y del disparador nocturno (PA-10) | Mismo motivo; U20 y U6 dejan los endpoints y el comando |
| El respaldo de la base | Es del proveedor que se elija. Lo que esta unidad aporta es **qué no se puede perder**: la fila del acumulado y el registro de gasto, que no se reconstruyen desde ningún otro sitio |
| El cifrado del almacenamiento en reposo | Ninguna tabla de U5 guarda un dato personal, así que aquí no hay cifrado por columna; la capa del disco es del proveedor |

## Sources

- `../nfr-design/logical-components.md` — las nueve piezas, los dominios de
  fallo y los recursos compartidos
- `../nfr-design/scalability-design.md` y `../nfr-design/reliability-design.md`
- `../nfr-requirements/tech-stack-decisions.md`
- `<record>/inception/domain-design/components.md` — los tres componentes de U5
- `<record>/inception/contract-design/contract-summary.md` — C-16, C-17, C-23
- `docker-compose.yml`, `app/backend/pyproject.toml`, `mise.toml` — el estado real

## Assumptions & Open Questions

- Esta unidad no exige nada del dimensionado del proceso. Si el intent `infra`
  eligiera un proveedor de base con latencia base mayor, los presupuestos de
  15 ms y 50 ms se revisan allí con su medición.
- El aprovisionamiento del backend de trazas en un entorno público no se diseña
  aquí. El exportador ya tiene sus dos caminos, y el que no tiene destino
  funciona.
