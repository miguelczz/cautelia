# Decisiones de diseño — U18 `voice-spanish`

Esta unidad llega en una situación cómoda y con una trampa dentro.

Cómoda, porque **la mitad del español ya está escrita**: U16 escribió el catálogo
en los dos idiomas y copió literal las frases que sus criterios fijaban, así que
la apertura, los silencios, la oferta, la interrupción y la retoma ya dicen en
español lo que los criterios de esta unidad piden. Se comprobó una por una contra
AC1.28.1, AC1.30.1, AC1.30.2 y AC1.30.3, y coinciden.

La trampa es que eso hace fácil dar el resto por hecho. Lo que **no** está es
justamente lo que esta unidad existe para construir: el cambio de idioma, lo que
se dice cuando no es ninguno de los dos, y que el idioma con el que arranca una
llamada sea el de la aseguradora y no el que el navegador tenga puesto.

Las decisiones de abajo son técnicas y la norma del proyecto es que la sesión
principal recomienda y avanza. **La única que es de Miguel está al final, marcada,
y es una corrección mía**: le dije que una frase no tenía criterio aprobado y sí lo
tenía.

---

## D1 — El detector de idioma sube a un módulo hoja, y no se copia

**El problema.** `chat/language.py` ya hace exactamente lo que esta unidad
necesita: dos umbrales distintos —uno para decidir dentro del turno y otro para
medir la adherencia—, un piso de cuatro palabras que impide que un nombre propio
cambie el idioma, y un detector amplio aparte para distinguir "no hay señal" de
"esto es portugués". Y está **medido**: 0,726 de confianza para una frase en
portugués, 0,168 para "Marcela Rios".

Lo que no se puede es usarlo desde la voz: `untangle.chat` y `untangle.voice` son
hermanos en el contrato de capas, así que ninguno importa al otro.

**Decisión.** El detector sube a **`untangle/language.py`**, módulo hoja en la raíz
del paquete, y los dos canales lo consumen desde ahí. Es el mismo movimiento que
U6 hizo con `surface_spec.py` y por la misma razón: una pieza que varias unidades
necesitan y que no pertenece a ninguna.

**Lo que no se hace, y es la parte que importa.** No se copia. Un segundo detector
con los mismos umbrales es dos números que se separan el día que alguien afina uno,
y los dos umbrales de este archivo no son magia: son medidas. La alternativa
—dejar el chat como está y escribir otro para la voz— habría dado dos definiciones
de "qué es una señal suficiente" en un proyecto que publica adherencia de idioma
por idioma.

**Lo que se mueve tal cual:** los dos detectores, los dos umbrales, el piso de
palabras y el conjunto cerrado de desenlaces. Lo que cambia es dónde vive y quién
puede llamarlo. `chat/language.py` desaparece y sus consumidores apuntan al nuevo;
no se deja un reexportador, porque dos caminos al mismo sitio es como uno de los
dos se queda atrás.

## D2 — Pedir el cambio y hablar en otro idioma son dos cosas distintas

**El problema.** "In English, please" está dicho **en inglés**, así que el detector
lo va a leer como inglés. Pero "¿me lo puede decir in English?" está dicho en
español y también es una petición. Y al revés: alguien que dice "el Toyota
Highlander" no está pidiendo nada (AC1.32.2).

Si el cambio de idioma dependiera solo del detector, la petición funcionaría por
accidente en un sentido y no en el otro.

**Decisión.** Dos caminos, en este orden, y el primero manda:

1. **La petición explícita** (AC1.31.1, AC1.31.2). Una lista cerrada y versionada
   de formas de pedirlo en los dos idiomas —"in English", "en español", "hablemos
   en inglés", "switch to Spanish"— reconocida por código, sin modelo. Si la hay,
   el idioma cambia **aunque el detector diga otra cosa**.
2. **La detección automática** (US1.32), solo si la aseguradora la tiene activa, y
   solo con **dos turnos seguidos** en el otro idioma (AC1.32.1).

**Por qué la petición no se detecta con el modelo.** Es la misma razón por la que
la transición del grafo no la decide un LLM: una petición de cambio de idioma
cambia el estado de la conversación, y eso se decide en código con una lista que
se puede leer en un diff.

## D3 — El cambio empieza en el turno siguiente, no a mitad de frase

**Decisión.** Cuando un turno pide el cambio, **ese turno se contesta en el idioma
nuevo** y la llamada queda en él (AC1.31.1: "el turno siguiente es en inglés").

La frase que la agente ya está diciendo cuando llega la petición **no se corta**:
si la interrumpieron, la interrupción ya la calla por su propio camino (BR4.1 de
U16), y si no, termina. Cortar la síntesis a mitad de palabra para cambiar de
idioma suena a fallo y no a atención.

## D4 — El idioma de la llamada cambia; el del caso no

**El problema.** `CallSession.language` y `CaseRecord.language` son dos campos
distintos y un cambio a mitad de llamada los pone en tensión. RT-10 —un caso que
cambia de idioma a mitad para esquivar un control— dice que el caso queda
registrado en el idioma **en que se atendió**.

**Decisión.** El cambio escribe `CallSession.language`, que es el idioma en que se
está hablando, y **no toca el del caso**. El del caso es el que tenía al abrirse y
es lo que la bandeja lee para filtrar por idioma.

**Por qué, dicho con su consecuencia.** Un caso abierto en español y terminado en
inglés aparece en la bandeja como español. Eso es deliberado: la alternativa —que
el caso cambie de idioma con el último turno— deja que una persona mueva su caso
de cola diciendo dos palabras, que es exactamente la forma de RT-10. Lo que sí
queda en los dos idiomas es la **transcripción**, turno por turno, que es donde la
ajustadora ve lo que de verdad pasó.

## D5 — El idioma con el que arranca la llamada es el de la aseguradora

**El problema.** Hoy la consola manda el idioma que el navegador tiene puesto, y
eso no distingue "la persona eligió español" de "la pestaña está en español porque
sí". AC1.28.4 pide que llamar a Stonecroft **sin elegir** abra en español porque es
su configuración, no porque el navegador lo diga.

**Decisión.** La consola manda el idioma **solo cuando la persona lo eligió**. El
selector de U6 ya distingue las tres procedencias —`user`, `persisted`,
`tenant_default`—, así que la consola omite el campo cuando la procedencia es la
tercera, y el servidor usa `default_language` de la aseguradora.

El campo `language` del cuerpo de abrir pasa a ser **opcional**, que es un cambio
aditivo al contrato y por tanto permitido dentro de `/api`.

## D6 — En la voz, un tercer idioma **no se puede distinguir** de no haber entendido

**Corregido el 2026-09-29, al leer los puertos de U15.** La primera versión de esta
decisión decía que el detector amplio reconocería el tercer idioma, como hace el
chat. En la voz no puede, y la razón está en el transporte:

- El reconocedor corre en modo **multiidioma**, así que el idioma lo detecta el
  modelo palabra por palabra y lo devuelve en cada transcrito.
- Pero `Transcript.language` es `Locale | None`: el adaptador de U15 traduce `es` y
  `en`, y **cualquier otro idioma lo colapsa a nulo**, que es lo mismo que "el
  proveedor no lo dijo".
- Y lo que llega transcrito de alguien hablando portugués no es texto en
  portugués: son palabras en español o inglés que se le parecieron. Pasarle el
  detector amplio a eso no diría "portugués": diría cualquier cosa.

**No se amplía el puerto de U15.** Es la misma decisión que U16 tomó con el
`speech_final` de Deepgram: un dato que un proveedor da y el puerto no lleva se
deriva aquí o no se usa, pero el contrato de C-16 no se toca por comodidad de un
consumidor.

**Decisión.** En la voz, lo que dispara la frase de los dos idiomas es lo mismo que
dispara "no le escuché bien": **confianza baja dos turnos seguidos**. Es
literalmente lo que AC1.31.4 escribe en su *Dado* --"el reconocedor simulado
devolviendo baja confianza dos turnos seguidos, como cuando alguien habla
portugués"--, así que el criterio ya describía el mecanismo real; lo que estaba mal
era mi lectura.

La frase es una clave nueva por idioma con **las dos lenguas dentro**, no dos
claves que alguien concatene: quien la oye la oye una vez, y componerla de trozos
deja que un día salga media.

## D7 — La detección automática es un dato de la aseguradora, no una rama

**Decisión.** Un campo nuevo en la configuración de la voz de cada aseguradora,
con valor por omisión **apagado**. AC1.31.5 escribe explícitamente la conducta
"si la detección automática no está activa", así que las dos ramas existen en el
criterio y la que decide es la carpeta versionada, nunca un `if` por aseguradora
en el código (convención 9 del equipo).

Apagado por omisión porque US1.32 es la única historia Should de la unidad y la
última en la regla de corte del PRD: si se corta, lo que queda es AC1.31.5, que es
la conducta con la detección apagada, y ya está escrita.

## D8 — El registro paisa se comprueba por código donde se puede

**Decisión.** AC1.28.3 tiene dos mitades y solo una es de código: la lista de
formas de tuteo y la frecuencia de "pues" se comprueban con un chequeo de
contenido sobre el catálogo en español y sobre las transcripciones de las
corridas; la rúbrica de calidez la juzga el juez y depende de su calibración.

Se construye la mitad de código **ahora** y se declara la otra como medida del
juez, con su dependencia escrita. Un criterio que solo pudiera comprobar el juez
quedaría sin compuerta el día que el juez se descalibre, y este tiene una mitad
que no lo necesita.

## D9 — Las metas por idioma se reportan lado a lado, nunca promediadas

**Decisión.** No hay nada nuevo que construir: el corredor de evaluaciones ya
reporta por idioma y el reporte no admite un promedio combinado (P12). Lo que esta
unidad añade es **casos en español** para que la columna exista, y esos casos son
las grabaciones de DS-5 en español, que llegan en la semana 9.

Queda diferido con su fila en `pasada-de-publicacion.md`, igual que las metas de
U16: es una medición contra proveedores de verdad y sin grabaciones no hay nada
que medir.

---

## Lo que esta unidad no construye

- **La llamada base**: es U16 y no se toca. Esta unidad no añade un segundo camino
  para nada que ya exista en inglés; si algo hiciera falta ramificar por idioma,
  es señal de que la pieza de U16 estaba mal construida y se corrige allí.
- **Los límites públicos y la voz de respaldo**: U17.
- **Las grabaciones de DS-5 en español**: las consigue Miguel con voluntarios en
  la semana 9, con consentimiento, y viven fuera del repositorio.
- **El acento**: lo juzga la prueba ciega de la semana 9 con tres personas de
  Medellín (S6), no esta unidad. Catalina es provisional hasta entonces y se cambia
  por configuración si no pasa (ADR-008).

---

## Para Miguel

### Q1 — ~~Una frase que te dije que no tenía criterio~~ — decidida el 2026-09-29

**Me equivoqué y quiero corregirlo antes de seguir.** Ayer te llevé tres frases
diciendo que las había escrito yo porque ningún criterio las fijaba, y las
aprobaste. Una de las tres **sí estaba fijada**, en un criterio de esta misma
unidad que no había leído todavía:

| | |
| --- | --- |
| Lo que dice el catálogo hoy, y aprobaste | "Perdón, no le entendí. ¿Me lo repite?" |
| Lo que fija AC1.29.3, aprobado en User Stories | "Perdón, no le escuché bien, ¿me repite?" |

Las otras dos —la despedida del tercer silencio y el aviso de tiempo— sí eran mías
y siguen aprobadas sin conflicto.

**Por qué no lo decido yo.** La regla del proyecto dice que una frase fija aprobada
se copia literal del criterio que la fija, así que por regla debería cambiarla. Pero
tú aprobaste la otra después, y el texto del producto es tuyo. Son dos cosas que
aprobaste y no coinciden, y elegir por ti cuál gana sería decidir en tu terreno.

**La diferencia de significado no es nula**, y por eso vale la pena elegir: "no le
escuché bien" dice que el problema fue del oído —que es lo que de verdad pasa, el
reconocedor no entendió— y "no le entendí" se puede leer como que lo que dijo no
tenía sentido. La del criterio es más precisa; la tuya suena algo más natural.

**Decisión de Miguel: (a).** El criterio manda y el catálogo ya dice **"Perdón, no
le escuché bien, ¿me repite?"**. La razón está escrita junto a la clave en
`app/config/copy/es.yaml`, que es donde alguien la leerá dentro de seis semanas.

La inglesa no se tocó: AC1.23.3 la fija como "Sorry, I didn't catch that. Could
you say it again?" y el catálogo ya la decía exacta.

### Q2 — Dos criterios aprobados describen el mismo momento con respuestas distintas

Salió al corregir D6, y es del mismo tipo que Q1: dos cosas aprobadas que no
encajan. **No bloquea**: la unidad se construye con mi recomendación y cambiarlo
después es una línea.

El momento es el mismo en los dos: **el reconocedor devuelve confianza baja dos
turnos seguidos**.

| Criterio | Qué dice que pasa entonces |
| --- | --- |
| AC1.29.3 | "Perdón, no le escuché bien, ¿me repite?" y a la tercera la oferta |
| AC1.31.4 | La frase que dice, en los dos idiomas, que solo se atiende español e inglés |

**Mi recomendación: la de AC1.31.4 en el segundo peldaño**, y la escalera de U16
sigue igual por lo demás --primero "no le escuché bien", tercero la oferta de
guardar o pasar a un ajustador--.

La razón es lo que le sirve a quien está al teléfono: si a la segunda vez se le
repite "no le escuché bien", no se le está ayudando; decirle que la demostración
atiende español e inglés y que puede pedir el cambio **sí**, y además incluye
implícitamente que no se le entendió. Repetir la misma frase dos veces es lo que
hace colgar a la gente.

### Q3 — La sesión de escucha de la semana 9

No es de ahora y no bloquea nada: Catalina es provisional hasta que tres personas
de Medellín la escuchen (S6, ADR-008). Lo digo aquí para que quede en el sitio donde
se decide el español, y no para que hagas nada hoy.

---

## Sources

- `../../../inception/units-generation/unit-of-work.md` — U18, sus cinco historias y sus dependencias
- `../../../inception/user-stories/stories.md` — US1.28 a US1.32 con sus criterios
- `../../u16-voice-call/` — la llamada que esta unidad habla en el segundo idioma
- `app/backend/src/untangle/language.py` — el detector, ya subido a módulo hoja en la tanda 1
- `app/config/copy/es.yaml` — lo que el español ya dice

## Assumptions & Open Questions

None.

Q1 es una corrección mía y no un supuesto: la discrepancia está comprobada contra
el catálogo y contra AC1.29.3. Mientras Miguel decide, la unidad se construye con
lo que hay hoy en el catálogo y cambiar la frase es editar una línea.
