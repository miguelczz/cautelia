# Preguntas — Diseño funcional de U10 `compliance`

U10 es lo que impide que la agente diga lo que no debe: que un caso está
cubierto, cuánto se paga, de quién fue la culpa, que es una persona. También
atiende en el mismo turno a quien pide hablar con una persona o reporta heridos
graves, y no deja cerrar un caso sin su revisión completa.

Casi todo está fijado. La interfaz la fija C-20; qué corre dentro del turno, D22
(solo tres controles baratos); las frases exactas, los criterios de US1.6, US1.9,
US1.10 y US1.11; y la frase de emergencia pública, D14. Quedan tres huecos con dos
respuestas legítimas.

**Cómo se respondieron.** Miguel delegó las decisiones de construcción en la
recomendación el 2026-09-21 ("la gracia es de que hagas una verificacion de cual
es la mejor opcion, la mas logica y por esa misma te vayas"). Cada respuesta es la
recomendada, con su razón.

---

## Q1 — Con qué detectan los tres controles del turno

La guardia, la petición de persona y la emergencia corren **dentro del turno**,
antes de emitir cada frase. Tienen que acertar en paráfrasis y con los dos
idiomas mezclados (AC1.9.3, AC1.11.5), y sin inventar alarmas (AC1.6.5).

- A. **(Recomendada)** **Reglas deterministas por idioma**, versionadas como
  datos: patrones sobre texto normalizado (minúsculas, sin tildes, espacios
  colapsados), con negación para no disparar la emergencia ante "todos estamos
  bien". Se aplican **los dos idiomas a cada frase**, no solo el del turno. Un
  fallo encontrado en evaluación se corrige agregando el patrón **y** su caso al
  golden set.
- B. Un modelo de lenguaje que clasifique cada frase. Entiende mejor las
  paráfrasis, pero agrega una llamada por frase dentro del turno —tiempo y costo—
  y su veredicto no es reproducible, justo en la compuerta que más bloquea.
- X. Other (please specify)

**Por qué la A.** AC1.11.6 ya lo dice: "el detector por reglas bloquea siempre".
Es reproducible, cabe en el turno y cada fallo se vuelve un caso. Aplicar los dos
idiomas a cada frase es la lección de U3 con RT-15: cargar solo el del turno es
exactamente el agujero.

[Answer]: A

---

## Q2 — Qué hace la guardia cuando una frase promete algo

AC1.11.3 pide evaluar **cada frase** antes de enviarla, sin esperar la respuesta
completa. Queda por decidir qué sale en lugar de la frase mala.

- A. **(Recomendada)** La frase se **reemplaza** por la frase permitida del
  catálogo para su categoría (cobertura, monto, culpa, consejo legal, afirmación
  de ser humana, revelación de configuración), **una sola vez por turno y
  categoría**, y el resto del turno sigue. Cada reemplazo deja una intervención
  registrada en el caso y un evento en la traza.
- B. Descartar el turno entero y emitir solo la frase permitida. Es más simple,
  pero si la primera mitad del turno ya salió en streaming, no se puede
  descartar, y el resultado se oye cortado.
- X. Other (please specify)

**Por qué la A.** Es la única compatible con el streaming frase a frase de la
voz y el chat. La repetición se evita con el límite por categoría.

[Answer]: A

---

## Q3 — Qué revisa la revisión completa al cierre, y con qué

FR7.7 pide revisar los cuatro controles sobre la conversación entera antes de
cerrar: divulgación registrada, ruta a persona respetada, datos personales
redactados y explicabilidad. El catálogo de componentes le permite pedir una
clasificación al modelo "cuando las reglas no bastan".

- A. **(Recomendada)** Los cuatro controles son **deterministas**, leídos del
  registro del caso: que existe la divulgación; que si se pidió una persona, el
  caso se derivó en el turno siguiente; que la transcripción pasa el detector de
  U3 sin hallazgos; y que el caso tiene sus adjuntos (transcripción, citas,
  reglas disparadas, traza y resultado de los controles). U10 **no** llama al
  modelo: la relectura de la conversación con un juez para encontrar lo que las
  reglas no vieron ya es trabajo de U21, que tiene el juez calibrado.
- B. Agregar una relectura con el modelo en cada cierre. Duplica el juez de U21
  sin su calibración, y un veredicto sin calibrar no puede bloquear un cierre.
- X. Other (please specify)

**Por qué la A.** Cada control tiene una respuesta verificable en el registro, y
la parte que necesita juicio ya tiene dueño y calibración en otra unidad.

[Answer]: A
