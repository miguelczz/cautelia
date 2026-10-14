# Preguntas de diseño funcional — U23 `comparison-view`

Una pregunta para Miguel, **ya contestada**, dos que la tanda 1 destapó y que resolví
aquí, y ocho decisiones que tomé yo. La de Miguel cambiaba lo primero que lee quien abre
la vista; las demás las resuelve un criterio aprobado o algo que ya existe en el código.

## Sources

- `../../../inception/user-stories/stories.md` — US2.9 y su decisión D25 (accesibilidad)
- `../../../inception/units-generation/unit-of-work.md` — U23, su origen y UG-3
- El código: `chat/api.py` (las tres rutas del chat público), `chat/limits.py` (los
  cinco controles, puros), `chat/case_opening.py` (**una pregunta de cobertura abre un
  caso de consulta**), `chat/session.py` (la conversación es por aseguradora),
  `tenancy/purge.py` (el contrato de borrado y su registro)

## Assumptions & Open Questions

None. La pregunta está contestada abajo.

---

## Q1 — ¿Qué divulgación ve quien abre la vista, y qué pasa con las tres aperturas?

**Por qué hay pregunta.** AC2.9.1 pide que **la vista** diga, antes de la primera
pregunta, que responde una asistente de inteligencia artificial, que es una
demostración con pólizas de ejemplo, y **qué póliza de ejemplo usa cada columna** —algo
que ninguna apertura de aseguradora dice—. Pero la vista va a hablar por las tres
rutas del chat que ya existen, y el chat entrega **su** apertura en el primer mensaje
de cada conversación. Sin decidir, la vista muestra su divulgación **y** tres
aperturas debajo, cada una ofreciendo reportar un siniestro, que no es lo que esta
vista hace.

Y hay un detalle que cierra la puerta a la solución fácil: **una pregunta de cobertura
abre un caso** (de consulta, dos campos), y AC1.1.2 dice que un caso sin su registro de
divulgación **no se puede cerrar**. Así que "que la vista no muestre la apertura" no es
una opción: dejaría tres casos sin divulgación registrada.

**Respuesta de Miguel (2026-09-30): opción A.** La divulgación es la de la vista, y
**queda registrada en los tres casos** como entregada por esta superficie, con su hora,
su idioma y su clave del catálogo. Las columnas muestran respuestas y nada más.

Es la única que cumple AC2.9.1 y AC1.1.2 a la vez: la divulgación de la vista dice más
que las tres juntas —nombra la póliza de ejemplo de cada columna— y quien evalúa lee una
cosa en vez de cuatro.

**Lo que cuesta, y dónde:** el chat aprende **de qué superficie** viene la conversación.
Es un parámetro aditivo y no una ruta nueva, así que FD-U23-1 sigue en pie. Vive en la
tanda 2, porque registrar la divulgación toca la base.

La opción descartada era mostrar la divulgación de la vista **y** las tres aperturas en
sus columnas: no tocaba nada del chat, y dejaba a quien abre la vista leyendo cuatro
divulgaciones seguidas y tres ofertas de reportar un siniestro en una pantalla que
compara coberturas.

---

## Q2 — ¿De dónde sale el emisor de la póliza de una agencia? *(decidida el 2026-09-30)*

**Por qué apareció.** BR1.2 exige que la columna de Knotwell nombre a quien emitió su
póliza de ejemplo. La tanda 1 encontró que **ningún contrato lo trae**: `example_policy`
está en la configuración y viaja en `GET /api/site`, pero el emisor no.

**El dato existe en dos sitios y ninguno es el bueno.** Está en los datos versionados
(`app/data/tenants/knotwell/issued_policies/POL-200341.json`, campo `issuer_tenant:
sunmeadow`) y por tanto también en la base después de la ingesta. Pero `presentation()`
construye la respuesta del inicio **solo con lo que la carpeta de la aseguradora trae**,
y su docstring lo dice con esas palabras: es una frontera deliberada, no un descuido.
Leer un archivo de corpus desde la ruta del inicio la cruzaría.

**Decisión: un campo nuevo en la configuración, con un chequeo que lo compara con los
datos versionados.**

- `example_policy_issuer` va al lado de `example_policy` en `tenant.yaml`, viaja por
  `TenantPresentation` y llega a la vista como el resto. Sin base y sin cruzar la
  frontera del inicio.
- **Obligatorio cuando la aseguradora es una agencia**, y ausente cuando emite ella
  misma: una agencia sin emisor **no carga**, que es el patrón del proyecto —una carpeta
  rota se apaga sola— y es más fuerte que fallar cerrado en la pantalla.
- Y un chequeo compara lo declarado con `issuer_tenant` del archivo de la póliza. Es la
  única parte que hacía dudar de la configuración —dos fuentes que pueden discrepar— y
  es lo mismo que `synthetic:check` ya hace con `app/data/`: declarar y comprobar, en vez
  de elegir entre duplicar o acoplar.

**Lo que la pantalla ya hace bien y se queda:** fallar cerrado. Si el emisor llega vacío,
no se ofrece el campo de pregunta. Con el campo obligatorio eso no debería ocurrir nunca,
y por eso se queda: las dos defensas cubren cosas distintas.

---

## Q3 — ¿Quién decide que una pregunta es «fuera de propósito»? *(decidida el 2026-09-30)*

**Por qué apareció.** AC2.9.6 pide que, cuando alguien escribe el reporte de un siniestro,
la vista explique que compara respuestas de cobertura y enlace el chat de cada
aseguradora. La tanda 1 recibió esa decisión por un parámetro y **no inventó una
heurística en el cliente**, que es exactamente lo correcto.

**Decisión: la decide el reconocedor determinista que ya existe**,
`coverage_detour.is_coverage_question(text, language)` — el mismo que
`chat/case_opening.py` usa para decidir si el primer mensaje abre una consulta de dos
campos o un siniestro de siete. Fuera de propósito es, literalmente, «no es una pregunta
de cobertura».

Tres razones por las que no hay nada que inventar:

1. **La regla del proyecto es literal**: la categoría la deciden las reglas, no el
   modelo. Y una heurística en el cliente sería una tercera cosa, ni regla ni modelo.
2. **Ya está escrito y es compartido.** `case_opening` lo usa «el mismo, no una copia»,
   según su propio docstring.
3. **Decide antes de abrir nada.** Sin eso, una pregunta fuera de propósito abriría
   **tres casos de siniestro** desde una vista que compara coberturas.

**Dónde corre:** en el servidor, sobre la superficie de la comparación, que es el dato
que FD-U23-8 ya introduce. Un mensaje que el reconocedor no clasifica como pregunta de
cobertura **no se admite** en esa superficie: la respuesta es el texto de fuera de
propósito del catálogo, y no se abre caso. Sin ruta nueva y sin heurística en el cliente.

**Y sí cuenta como tres mensajes contra los límites**, porque tres mensajes se mandaron.
Es lo que BR2.3 ya dice y por la razón que ya da: un contador propio sería un segundo
sitio donde el límite puede discrepar del que de verdad protege.

---

## Las ocho decisiones que tomé yo

| # | Qué | Por qué no es pregunta |
| --- | --- | --- |
| FD-U23-1 | **No hay ninguna ruta nueva en el servidor.** La vista habla tres veces por las rutas del chat que ya existen, una por aseguradora, y abre tres flujos | La galleta del visitante es una por navegador y la conversación se resuelve **por aseguradora** (`find_live(tenant_id=..., visitor_key_digest=...)`), así que un navegador sostiene tres conversaciones vivas. Y con esto tres cosas dejan de ser reglas que alguien tiene que cumplir y pasan a ser hechos: el aislamiento por columna, que cada pregunta cuente como tres contra los límites (AC2.9.6), y la carga y el fallo por columna |
| FD-U23-8 | **La superficie es un dato de la conversación**, no un caso especial: el chat recibe de dónde viene y marca la apertura como entregada con la clave de esa superficie. La divulgación queda con su hora, su idioma y su superficie, como ya queda la del chat | Sale de la respuesta A. Un caso especial para la vista de comparación sería una rama por pantalla en el camino de apertura; un dato es una columna y una clave. Y deja la puerta abierta a la consola de voz, que tiene el mismo problema y hoy lo resuelve con su propia apertura |
| FD-U23-2 | **El aislamiento no se comprueba con una regla nueva**: cada llamada va dirigida a una aseguradora y la recuperación ya es por aseguradora. Lo que la unidad añade es la prueba que lo lee **en las trazas** de las tres columnas | AC2.9.3 es `[bloquea]` y dice "reviso sus trazas". Un segundo mecanismo de aislamiento sería un segundo sitio donde puede fallar |
| FD-U23-3 | **Las tres columnas responden en el idioma de la pregunta**, detectado por el detector determinista que ya existe, y la vista abre las tres conversaciones en ese idioma | AC2.9.2 es literal. Y hace falta decirlo porque **las tres aseguradoras tienen idioma por defecto distinto** (Sunmeadow `en`, Stonecroft `es`, Knotwell `en`): sin esto, la primera pregunta saldría contestada en dos idiomas |
| FD-U23-4 | La vista vive en `app/frontend/src/pages/comparison/`, entra al registro de pantallas del arnés como **pública**, y se apila a 360 px con el nombre de la aseguradora visible en cada columna | AC2.9.5, y la convención de las ocho pantallas que ya existen |
| FD-U23-5 | **Los datos del visitante de esta vista los borra el contrato que ya existe**, no uno propio: las tres conversaciones y sus tres casos son casos de visitante como los del chat | UG-3 y `tenancy/purge.py`: el registro de purgadores es explícito y una prueba le pregunta al catálogo de la base qué tablas llevan la marca. Esta vista no crea ninguna tabla |
| FD-U23-6 | **Las preguntas de ejemplo y el texto de "fuera de propósito" salen del catálogo** por idioma, y el enlace al chat de cada aseguradora es la dirección que ya existe | AC2.9.6; ninguna cadena visible se escribe en línea |
| FD-U23-7 | **La diferencia entre columnas no la explica la vista**: la explica cada respuesta con su cláusula citada, que es lo que el chat ya devuelve | AC2.9.4. Una vista que redactara la diferencia estaría afirmando cobertura, que es justo lo que la guardia de salida impide |

## Lo que esta unidad no construye

- **La respuesta de cobertura ni su verificación de citas**: son de U13 y U8. Aquí se
  reúnen tres.
- **La bandeja**: no aparece en esta vista.
- **Ninguna tabla ni ningún contrato de borrado nuevo.**
- **Publicar la vista**: es la pasada de publicación.
