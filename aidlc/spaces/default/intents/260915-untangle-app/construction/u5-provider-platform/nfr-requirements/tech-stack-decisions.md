# Decisiones de stack — U5 `provider-platform`

El lenguaje, el runtime, el gestor de dependencias y el comprobador de tipos los
fijó ADR-002 y no se revisitan. Lo que esta unidad decide es qué entra al
manifiesto por su culpa, y la regla del equipo para eso es corta: **una
dependencia nueva de runtime se justifica en una línea —qué hace, por qué no la
biblioteca estándar, y su licencia—**, y su licencia tiene que permitir publicar
el repositorio.

U5 añade **tres** dependencias de runtime y **dos** de desarrollo. Cada una va
abajo con su razón.

## Lo que entra al manifiesto

| Paquete | Grupo | Qué hace | Por qué no la biblioteca estándar | Licencia |
| --- | --- | --- | --- | --- |
| `google-genai` | runtime | El cliente oficial de Gemini: generación de texto con salida estructurada nativa y embeddings | Es una API HTTP propietaria con su propio protocolo de salida estructurada y su propio manejo de streaming. Escribirlo a mano sería reimplementar el cliente del proveedor y quedarse sin sus correcciones | Apache-2.0 |
| `opentelemetry-sdk` | runtime | Emite los tramos por turno, nodo y llamada con las convenciones `gen_ai.*` | La biblioteca estándar no tiene trazas distribuidas, y las convenciones `gen_ai.*` son lo que hace que el panel entienda modelo, tokens y costo sin configuración propia | Apache-2.0 |
| `opentelemetry-exporter-otlp` | runtime | Exporta al backend de trazas por OTLP, y a un archivo cuando no hay backend | Es el formato que el panel local lee y el que la tubería sube como artefacto | Apache-2.0 |
| `vcrpy` | dev | Graba la respuesta de cada proveedor una vez y la reproduce en cada entrega | Sin él, la prueba de contrato del adaptador o llama al proveedor en cada corrida —gastando el presupuesto que protege— o no existe | MIT |
| `respx` | dev | Inyecta los fallos del proveedor —tiempo máximo, 429, 5xx, JSON inválido— para comprobar la taxonomía cerrada | La única alternativa es esperar a que el proveedor falle de verdad, que no es una prueba | BSD-3-Clause |

Los cinco estaban ya nombrados en documentos aprobados —`google.genai` aparece
en la lista de módulos prohibidos fuera de su adaptador, y `vcrpy` y `respx` en
la confirmación de ADR-018—, así que esto los inscribe, no los elige.

## El dinero se calcula con decimales, nunca con coma flotante

Es la decisión de esta etapa que más se nota si se hace mal, y la que más fácil
sería no escribir.

**Qué se decide.** Todo importe —el precio unitario, el costo de una llamada, el
acumulado, el techo y la alerta— se representa con aritmética decimal exacta en
el código y con el tipo numérico exacto de la base, nunca con coma flotante.

**Por qué.** Con coma flotante, sumar veinte fracciones de centavo deja un
acumulado que depende del orden en que se sumaron. Eso tiene dos consecuencias, y
la segunda es la grave: el techo corta en un punto distinto según el orden de las
llamadas, y la cifra de costo que el proyecto publica deja de ser reproducible
desde el mismo commit. La práctica del equipo exige que dos corridas del mismo
commit vean lo mismo; con coma flotante no lo verían.

**Qué cuesta.** Nada perceptible: los importes de este proyecto caben de sobra en
la precisión que el tipo exacto ofrece, y la multiplicación decimal de una
llamada no aparece en ningún presupuesto de latencia.

**Cómo se comprueba.** El comprobador de tipos rechaza un importe en coma
flotante en la superficie del módulo, porque el tipo de dinero lleva su
representación exacta dentro y no admite el otro.

## El backend de trazas es opcional, y ya lo era

`docker-compose.yml` ya trae el perfil `traces` con Langfuse y su base, las dos
con imagen anclada por huella digital, y `settings.py` ya declara el endpoint de
trazas como variable **opcional**. Esta unidad no cambia nada de eso; lo que
añade es la conducta que ya estaba prometida: sin endpoint, el proceso funciona,
el gasto se registra, el corte corta y los resúmenes se declaran perdidos.

**En la tubería no hay Langfuse** —no cabe en su máquina—, así que las trazas de
cada corrida se exportan a un archivo OTLP que se sube como artefacto, y el
reporte enlaza a ese archivo y al identificador de traza. Esa decisión ya estaba
tomada en la investigación previa a Contract Design; se inscribe aquí porque es
lo que el exportador de esta unidad tiene que soportar.

## Lo que no entra, y por qué

| Descartado | Por qué |
| --- | --- |
| Una pasarela de modelos (LiteLLM, any-llm, Bifrost, Portkey, OpenRouter) | ADR-018 lo rechazó con evidencia: dos versiones de LiteLLM comprometidas en el índice de paquetes, dos CVE encadenadas, y ninguna ganancia con un solo proveedor de modelo. Un respaldo, si se activa, es un segundo adaptador |
| Una biblioteca de salida estructurada (Instructor, BAML, Pydantic AI) | La salida estructurada es nativa del proveedor y se valida con el mismo validador que el resto del aplicativo ya usa. Una capa más escondería dónde falla la validación |
| Instrumentación automática del cliente del proveedor | Captura el contenido de los mensajes por defecto, que es exactamente el dato que no puede salir. Los tramos se emiten a mano con la lista cerrada de atributos |
| OpenInference, OpenLLMetry | Mezclarían dos convenciones de atributos con `gen_ai.*` |
| Una biblioteca de límites de tasa | Los cuatro alcances de cuota son contadores por sujeto y periodo en la misma base que ya está, dentro de la misma transacción que crea la sesión. Una biblioteca con su propio almacén rompería esa transacción, que es lo que impide abrir dos llamadas a la vez |

## Comandos que esta unidad añade al archivo de tareas

| Comando | Qué hace | Cuándo corre |
| --- | --- | --- |
| `mise run test:u5` | Las pruebas de esta unidad | A petición; `mise run cov` ya corre la suite entera en el guion de verificación |
| `mise run spend:report` | Las cuatro agregaciones de gasto con su conteo de no medidas, y el costo por caso exitoso | A petición y al publicar una versión |

Y uno que **crece** en vez de nacer: `mise run rls:check` pasa a preguntar
además, por cada tabla de la lista de exclusión, qué columnas tiene, y falla si
encuentra texto sin longitud acotada o un nombre de la lista de dato personal.
Crece en vez de nacer aparte por una razón mecánica: un comando nuevo se olvida
de correr, y este ya está en el paso 6 del guion de verificación.

## La entrada de cobertura, más adelante

La declaración llevaría las rutas `app/backend/src/untangle/providers` y
`app/backend/src/untangle/telemetry`, que hoy contienen únicamente archivos
vacíos. La fila entra en `[tool.untangle.coverage]` en el mismo paso que crea los
módulos —mismo precedente que `tenancy` con U2, la redacción con U3 y el registro
del caso con U4—. Hasta entonces, el piso agregado del 80 % ya cubre lo que
exista.

## Sources

- `<record>/inception/domain-design/decisions.md` — ADR-002 (lenguaje, runtime,
  gestor y comprobador), ADR-006 (modelo y planes por uso), ADR-018 con su
  enmienda del 2026-09-17 (puertos, adaptadores, rechazo de las pasarelas, vcrpy
  y respx), ADR-019
- `docs/reference/arquitectura-y-tecnologia.md` — §11, observabilidad:
  OpenTelemetry con `gen_ai.*`, Langfuse en local, ausencia de Langfuse en la
  tubería, rechazo de OpenInference y OpenLLMetry
- `aidlc/spaces/default/memory/team.md` — la regla de una línea por dependencia
  nueva y el registro de licencias
- `app/backend/pyproject.toml` — las dependencias actuales y la configuración de
  cobertura; `docker-compose.yml` — el perfil `traces` con sus imágenes ancladas;
  `app/backend/src/untangle/settings.py` — el endpoint de trazas ya opcional
- `mise.toml` — el archivo de tareas al que se añaden los dos comandos

## Assumptions & Open Questions

- Las versiones exactas de los cinco paquetes las fija el lockfile en el commit
  que los añade, con la regla de espera de versiones que la cadena de suministro
  ya impone. Escribir aquí un número lo dejaría desactualizado al día siguiente.
- El adaptador de transcripción y el de síntesis los añade U15
  `speech-providers`, con sus propias dependencias y sus propias razones. Esta
  unidad deja el puerto y la fábrica listos para recibirlos.
- El despliegue público del backend de trazas lo decide el intent `infra`. La
  preferencia escrita en la investigación es exportar solo el resumen y una
  muestra redactada.
