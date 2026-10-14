# Preguntas de diseño funcional — U19 `quote`

Tres preguntas para Miguel, **ya contestadas**, y ocho decisiones que tomé yo. Las
tres preguntas cambiaban lo que lee o ve quien evalúa el proyecto; las ocho
decisiones las resuelve un criterio aprobado, una práctica afirmada o una convención
que ya existe en el código.

## Sources

- `../../../inception/user-stories/stories.md` — US6.1, US6.2, US6.3 y la decisión D4
- `../../../inception/requirements-analysis/requirements.md` — FR13.1, FR13.2, NFR13
- `../../../inception/units-generation/unit-of-work.md` — U19, sus cinco componentes
  parciales y la decisión UG-7
- `docs/reference/estructura-solicitud-cotizacion.md` — los cuatro bloques y sus campos
- El código: `rules/fields.py` (el vocabulario cerrado), `app/config/tenants/*/rules/`
  (las reglas de triage como forma), `case_record/models.py`
  (`RecordType.QUOTE_REQUEST`, ya declarado y sin campos), `tenancy/models.py`
  (`quote_enabled`, ya existe en `false`; `Role`, con dos valores),
  `app/config/compliance/*/guard.yaml` (los cuatro patrones de importe por idioma)

## Assumptions & Open Questions

None. Las tres preguntas están contestadas abajo.

---

## Q1 — ¿Qué es una "banda indicativa sin cifra"?

**Por qué hubo pregunta.** AC6.2.1 pide "una banda indicativa sin cifra" y AC6.2.2
prohíbe, como compuerta dura, todo importe y todo símbolo o código de moneda. El
problema es que "banda" en seguros significa banda de prima: decir "banda estándar"
sin número insinúa que hay un precio detrás, y esta demostración no calcula ninguno.

**Respuesta de Miguel (2026-09-30): opción A.** La banda habla de **riesgo**, no de
precio. Cuatro valores, conjunto cerrado, cada uno con su clave en el catálogo de
textos en los dos idiomas:

| Valor | Cuándo | Qué dice |
| --- | --- | --- |
| `standard_risk` | Elegible, sin siniestros con culpa y con tres años o más de licencia | El riesgo entra en lo habitual |
| `elevated_risk` | Elegible, con alguno de los dos | Entra, con más riesgo del habitual |
| `pending_review` | Derivación al suscriptor | **Todavía no se sabe**, y lo decide una persona |
| `outside_appetite` | No elegible | Queda fuera de lo que esta aseguradora asegura |

**`pending_review` no es un adorno.** Una derivación sin banda diría, por omisión, que
la banda es la peor; y ponerle una de las otras tres afirmaría algo que nadie ha
decidido todavía. Es la misma distinción que el proyecto ya hace en todas partes entre
"esto está mal" y "no lo sé".

---

## Q2 — ¿Hace falta un documento de estructura como el de la póliza ISO?

**Por qué hubo pregunta.** AC6.1.2 dice que los campos están "inspirados en la
estructura del formulario ACORD 90, sin su texto". Para la póliza ISO existe
`docs/reference/estructura-poliza-iso-pap.md`, que registra las secciones y deja
escrito por qué no hay texto de terceros. Sin el equivalente, el esquema de la
solicitud aparecería sin explicación de dónde sale.

**Respuesta de Miguel (2026-09-30): opción A.** Existe, y ya está escrito:
`docs/reference/estructura-solicitud-cotizacion.md`. Registra los cuatro bloques que
la historia nombra —conductor, vehículo, uso, historial— con nombres de campo propios,
y dice explícitamente que **no se consultó ni se guardó ningún specimen**: la parte
que se puede imitar es cómo se reparte una solicitud en bloques, y eso la historia ya
lo nombra.

---

## Q3 — ¿Qué hace a alguien no elegible?

**Por qué hubo pregunta.** Es contenido que se ve en la demostración: quien evalúa lee
la razón que la agente da. Y tiene que ser plausible para alguien de seguros sin
pretender ser una política real.

**Respuesta de Miguel (2026-09-30): la propuesta, sin cambios.**

| Salida | Condición | Campo que la decide |
| --- | --- | --- |
| No elegible | Uso comercial declarado | `use_type = commercial` |
| No elegible | Título de salvamento | `salvage_title = true` |
| Derivación | Dos o más siniestros con culpa en tres años | `at_fault_losses_3y >= 2` |
| Derivación | Menos de un año de licencia | `license_years < 1` |
| Derivación | Vehículo de más de 25 años | `vehicle_age_years > 25` |
| Elegible | Todo lo demás | — |

Cada una es una regla versionada con sus propios casos de prueba dentro del YAML, en
la carpeta de cada aseguradora, como las de triage. Cada aseguradora puede tener las
suyas: **la única que hoy tiene la cotización activa es Sunmeadow Auto** (AC6.1.2), y
las otras dos la dejan apagada.

---

## Las ocho decisiones que tomé yo

| # | Qué | Por qué no es pregunta |
| --- | --- | --- |
| FD-U19-1 | **No se construye ningún detector de alcance nuevo.** AC6.2.2 se cumple con la guardia de salida que ya existe: tiene cuatro patrones de importe y de porcentaje por idioma (`guard.es.amount.001` a `004`), y ninguna respuesta la esquiva porque es el punto único de salida | Un segundo detector de importes sería un segundo umbral que un día discrepa del primero, y la regla del proyecto ya obliga a que todo texto al asegurado pase por la guardia. Lo que esta unidad añade son los casos de DS-4 que lo ejercitan |
| FD-U19-2 | **El grafo no gana nodos** (FR13.1): la solicitud es un tipo de registro más sobre los mismos cuatro. `RecordType.QUOTE_REQUEST` ya existe, declarado sin campos a propósito | FR13.1 es literal, y el comentario de `case_record/fields.py` dice que está así esperando a esta unidad |
| FD-U19-3 | **Ningún campo de elegibilidad existe sin el bloque de captura que lo escribe.** Los cinco que leen las reglas salen de los cuatro bloques, y `required_inputs()` es lo que se lo dice a la captura | Es el hueco que hoy tienen seis campos del triage de siniestros: están en el vocabulario y nadie los escribe, así que ninguna regla que los nombre llega a dispararse. Un campo sin fuente es una regla que nunca corre |
| FD-U19-4 | **`vehicle_age_years` es un campo derivado, calculado en un solo sitio** desde `vehicle_year` y el reloj que la captura ya inyecta | Una regla que comparara contra un año literal envejece sola: el año que viene significa otra cosa y no falla nada. Es la misma razón por la que las latencias declaran entre qué eventos se miden |
| FD-U19-5 | **El rol nuevo se llama `underwriter`**, es un valor más del enum de roles, y su permiso es una fila más en la tabla de permisos, no una rama en el código | `tenancy/models.py` dice que una acción nueva la añade la unidad que la introduce, con su fila y su prueba. Los dos roles que existen no sirven: AC6.3.3 pide que un ajustador **no** pueda decidir una solicitud |
| FD-U19-6 | **El suscriptor ve solo solicitudes de cotización derivadas**, y nada más: ni siniestros ni solicitudes no derivadas | AC6.3.1, literal. Y es la misma forma que ya tiene la bandeja: el filtro es del lado del servidor, no de la pantalla |
| FD-U19-7 | **La reanudación reusa el puerto que ya existe** (C-14): la decisión se registra primero y el grafo se reanuda de fondo, como en la decisión de un siniestro | `inbox/decision.py` ya lo hace así, y su docstring explica por qué en ese orden: al revés, un caso puede quedar reanudado sin decisión registrada |
| FD-U19-8 | **La unidad se parte en dos tandas por dónde puede correr**, no por tamaño: la solicitud, las reglas y sus casos de DS-4 van a la nube; la bandeja con el rol nuevo se queda aquí | La nube no tiene base de datos ni motor de contenedores. Las pruebas de la bandeja necesitan dos aseguradoras sembradas y las de aislamiento, colisiones detectables |

## Lo que esta unidad no construye

- **Tarifas ni precios actuariales**: fuera de alcance, y la compuerta dura de AC6.2.2
  existe para que ni por accidente aparezca una cifra.
- **Nodos nuevos del grafo**: FR13.1.
- **La cotización activa en Stonecroft o Knotwell**: se queda apagada en las dos.
  AC6.1.3 comprueba justamente qué pasa cuando alguien la pide donde está apagada.
- **El cableado del grafo de fondo** (PENDIENTES 1.8): es trabajo aparte y toca los
  mismos archivos, así que no corre al mismo tiempo que esta unidad.
