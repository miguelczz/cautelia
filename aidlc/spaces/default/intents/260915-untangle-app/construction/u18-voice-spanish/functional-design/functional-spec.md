# Especificación funcional — U18 `voice-spanish`

La segunda capa de la voz. No es "la llamada otra vez en español": es que el
español **no sea un servicio de segunda**, y eso se comprueba de dos maneras
distintas. Una es que lo ya construido se comporte igual —y eso son pruebas, no
código nuevo—. La otra es lo que solo existe cuando hay dos idiomas: poder
cambiar de uno a otro sin perder el caso, y saber qué decir cuando lo que llega
no es ninguno de los dos.

De ahí que la unidad sea pequeña en código y grande en pruebas.

## Sources

- `../../../inception/units-generation/unit-of-work.md` — U18, sus cinco historias
- `../../../inception/user-stories/stories.md` — US1.28 a US1.32 con sus criterios
- `../../u16-voice-call/functional-design/` — la llamada que aquí se habla en el segundo idioma
- `functional-design-questions.md` — las nueve decisiones de esta etapa

## Assumptions & Open Questions

None.

La única pregunta abierta es de Miguel y es una corrección mía: una frase del
catálogo que le llevé como propia estaba fijada por AC1.29.3. No bloquea nada;
está en `functional-design-questions.md`, Q1.

---

## Flujo 1 — La llamada arranca en el idioma de la aseguradora (US1.28)

Camilo abre la consola de Stonecroft Mutual sin tocar el selector de idioma.

1. La consola pide la disponibilidad y dibuja el botón, igual que en U16.
2. Camilo pulsa llamar. La consola **no manda idioma**: el selector de U6 dice que
   la procedencia del suyo es `tenant_default`, o sea que nadie eligió.
3. El servidor abre la llamada con `default_language` de la aseguradora, que para
   Stonecroft es español (AC1.28.4).
4. La agente dice la apertura en español, con Valentina, y la divulgación queda
   registrada con su hora, su idioma y el canal voz (AC1.28.1).

**Si Camilo sí eligió** —tocó el selector, o lo tenía guardado de otra visita— la
consola manda ese idioma y manda ese. La diferencia entre "eligió" y "así vino la
pestaña" la sabe el selector y no el servidor, y por eso la decide el navegador.

**Una sola identidad de voz.** La configuración de cada aseguradora declara la
misma voz para los dos idiomas (AC1.28.2). No es conducta de código: es una
propiedad de la carpeta versionada, y se comprueba como tal.

---

## Flujo 2 — Pedir el cambio (US1.31)

Camilo lleva dos bloques confirmados en español y dice "in English, please".

1. El turno se mira **primero** contra la lista cerrada de peticiones de cambio, en
   los dos idiomas. Hay coincidencia.
2. La llamada pasa a inglés: se escribe en `CallSession.language` y **ese mismo
   turno se contesta en inglés** (AC1.31.1).
3. El caso no se reinicia y los bloques confirmados siguen confirmados. El idioma
   del caso **no cambia** (D4).
4. La voz es la misma: la identidad no depende del idioma (AC1.31.3).

**En el otro sentido igual** (AC1.31.2): "en español" devuelve la llamada al
español desde el turno siguiente.

**La petición gana al detector.** "In English, please" está dicho en inglés y el
detector lo leería como inglés por su cuenta; "¿me lo puede decir in English?" está
dicho en español y el detector diría español. Los dos son la misma petición, y por
eso el reconocedor de peticiones corre antes y decide (D2).

**Lo que la agente está diciendo no se corta.** Si Camilo interrumpió, la
interrupción ya la calla por el camino de U16; si no, la frase termina. Cortar la
síntesis a mitad de palabra para cambiar de idioma suena a fallo.

---

## Flujo 3 — Que lo note sola (US1.32, Should)

Solo si la aseguradora tiene la detección automática activa (D7). Apagada por
omisión, y apagada es la conducta que AC1.31.5 describe.

1. Camilo viene hablando en inglés y su turno **t** llega en español, con señal
   suficiente: cuatro palabras o más y confianza por encima del umbral.
2. No pasa nada todavía. Un turno suelto no cambia el idioma.
3. Su turno **t+1** llega también en español. Entonces sí: la respuesta a t+1 ya es
   en español (AC1.32.1).

**Una palabra suelta nunca cambia nada** (AC1.32.2). "El Toyota Highlander" y
"okay" no llegan siquiera al detector: el piso de cuatro palabras los descarta
antes, que es la misma razón por la que "Marcela Rios" no cambiaba el idioma del
chat.

**Con la detección apagada**, hablar en el otro idioma sin pedirlo deja la llamada
donde estaba, y si la transcripción llega con confianza baja dos veces seguidas se
pide repetir y se recuerda que se puede pedir el cambio (AC1.31.5).

---

## Flujo 4 — Cuando no es ninguno de los dos (AC1.31.4)

Alguien habla portugués.

1. El detector amplio lo dice: es un idioma de verdad, con confianza, y no es
   ninguno de los dos.
2. **La primera vez no pasa nada especial**: la llamada sigue en su idioma y la
   agente pide que lo repita, que es la escalera de U16.
3. **A la segunda seguida**, la agente dice la frase de los dos idiomas: que la
   demostración atiende español e inglés, que se puede decir "in English" o "en
   español", y que una persona puede revisar el caso.

La frase es **una sola clave por idioma con las dos lenguas dentro**, no dos
claves que alguien concatene (D6): quien la oye la oye una vez, y componerla de
trozos deja que un día salga media.

---

## Flujo 5 — Lo mismo, en español (US1.29, US1.30)

Este flujo **no añade código**. Es el recorrido entero de U16 con la llamada en
español, y lo que aporta esta unidad son sus pruebas:

| Qué | Criterio | Dónde se comprueba |
| --- | --- | --- |
| El orden de los bloques, una pregunta por turno, 25 palabras | AC1.29.1 | Pruebas de la unidad con el reconocedor doblado |
| Cédula y placa dígito a dígito con confirmación | AC1.29.2 | Las mismas, con la tabla de deletreo de U11 |
| "No le entendí" y su escalera de tres | AC1.29.3 | Las mismas |
| La pregunta de cobertura con su frase de espera | AC1.29.4 | Las mismas |
| El cierre con su número dicho uno a uno | AC1.29.5 | Las mismas |
| Interrupción, silencios y retoma | AC1.30.1 a AC1.30.4 | Las mismas |
| Las metas de tiempo por idioma, lado a lado | AC1.30.5, AC1.29.x | **Por hito**, sobre DS-5 en español |

**Si alguna de estas pruebas obliga a ramificar por idioma, la corrección va en
U16 y no aquí.** Una rama `if language == "es"` dentro de esta unidad sería la
señal de que la pieza de U16 estaba escrita para un solo idioma, y taparlo aquí
dejaría el defecto donde nadie lo busca.

---

## Flujo 6 — El registro de la voz (AC1.28.3)

Dos mitades y solo una es de código (D8).

- **De código**: ninguna forma de tuteo en el catálogo en español ni en las
  transcripciones de las corridas, y "pues" como mucho una vez por turno. Es un
  chequeo de contenido con identificador estable, como los tres que ya existen.
- **Del juez**: la calidez del usted y el registro paisa ligero. Depende de su
  calibración, y si el juez se descalibra este criterio se reporta "no medida" y
  no bloquea, mientras la mitad de código sigue bloqueando.

---

## Lo que esta unidad no construye

- **La llamada base**: es U16. Aquí no se duplica ninguna pieza suya.
- **Los límites públicos y la voz de respaldo**: U17.
- **Las grabaciones de DS-5 en español**: las consigue Miguel con voluntarios en
  la semana 9, con consentimiento, y viven fuera del repositorio. Sin ellas, las
  metas por idioma se declaran "no medidas", nunca se omiten.
- **El acento de Catalina**: lo juzga la prueba ciega de la semana 9 (S6). Es
  provisional hasta entonces y se cambia por configuración (ADR-008).
- **El chat en español**: ya funciona; U13 lo construyó con el mismo detector que
  aquí sube a módulo hoja.

---

## Resumen de reglas (vista derivada)

Las reglas están en `rules.md`. Dos llevan `[bloquea]`: que el cambio de idioma no
pierda ningún bloque confirmado, y que el idioma del caso no lo mueva un turno.

## Modelo de entidades (vista derivada)

Esta unidad **no añade ninguna entidad**. Lo que cambia es que
`CallSession.language` deja de ser un dato de apertura y pasa a ser mutable, con
su regla. Los detalles están en `entities.md`.
