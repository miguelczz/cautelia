# Resumen del código — U11 `intake`

U11 es la unidad que conversa. Deja construido:

- **La identificación sin filtraciones.** Una póliza de otra aseguradora y una
  inexistente responden igual, y no porque el código lo compruebe: porque la
  política de fila las filtró antes de que la consulta las viera, y el código
  nunca llega a saber cuál de las dos era. Un número mal formado se vuelve a
  pedir, nunca se completa.
- **La extracción con evidencia.** Solo lo dicho en el turno, cada campo con el
  turno del que salió, y el texto de la persona entrando como dato delimitado y
  nunca en la posición de instrucción del prompt.
- **El orden de las preguntas, deducido del caso.** Qué bloque toca sale de la
  completitud del caso y de nada más: sin un contador propio que hubiera que
  reconciliar al reanudar. Un dato adelantado no se vuelve a preguntar.
- **La confirmación por bloque.** Se lee lo anotado nombrando lesiones,
  conductor y lugar, y hasta el sí el bloque no cuenta. Un no abre la corrección
  y vuelve a leer.
- **El trato.** Reconocer primero y preguntar después, una idea por turno, el
  registro prohibido juzgado por código sobre el texto ya compuesto, y los
  umbrales de insultos en la configuración de cada aseguradora.
- **Las dos versiones.** El valor del caso es el primero confirmado; una versión
  que lo contradice se anota aparte con su propia clase de entrada en el
  historial, que dice que **no** se aceptó.
- **El quinto rol de `case_party`**, para quien reporta por otro, con su relación
  con el asegurado, redactada antes de persistirse.
- **El nodo con la forma de C-15**: su especificación —qué lee, qué escribe, en
  qué ritmo corre y su política de fallo como dato— y un `run` **puro** que pone
  las piezas en orden y devuelve su conjunto de escritura, sin abrir ninguna
  transacción.

Se construyó en dos tandas, las dos escritas en sesiones de la nube con Sonnet y
revisadas aquí.

## Resultados

| Compuerta | Resultado |
| --- | --- |
| `mise run test:u11` | 111 pruebas en verde, incluidas 11 de integración |
| `mise run cov` | 88,21 % agregado; los cinco módulos críticos entre 89 % y 99 % |
| `mise run rls:check` | 21 tablas con política, 20 llaves foráneas entre tablas aisladas |
| `mise run migrate:check` | Las dos migraciones suben, bajan y vuelven a subir contra base virgen |
| `mise run evals:gate -- --subset smoke` | 68 casos, 0 fallos |
| `mise run evals:run` (completa) | 116 casos: 72 pasan, 42 fallan por `not_built`, 2 no medidos |
| `scripts/verify.sh` | Los nueve pasos en verde |

**Los dieciséis casos previos de esta unidad están en verde**, ocho por idioma:
los cinco ejes de DS-2 y los tres escenarios de DS-6. Era el criterio escrito de
que la unidad estaba terminada.

Los 42 fallos de la corrida completa son todos `not_built` y ninguno es de U11:
40 casos de DS-3 y 2 de DS-6 esperan el conductor de canal que construye **U13**.

## Lo que salió de la revisión

Las dos tandas pasaron todas las compuertas automáticas que la nube podía correr.
Los defectos los vio solo la revisión, y el patrón se repitió en los dos: **la
prueba estaba escrita a la medida del código**, así que afirmaba el
comportamiento equivocado en vez de detectarlo.

### Tanda 1

**1. Dos operaciones nuevas en la superficie pública de U4 sin tocar la prueba
que la fija.** Esa prueba existe precisamente para que añadir una operación sea
una decisión visible. Se añadieron `register_party` y `parties_of` a la prueba.

**2. El ritual de rojo-verde declarado como no hecho.** El agente escribió las
pruebas de precedencia junto al código en vez de antes. Se comprobó a mano
rompiendo cada regla: las dos pruebas fallan con la regla rota y pasan cuando se
restaura.

**3. Un error mío de diseño, no del código.** FD-U11-5 decía que U11 no podía
crear "ninguna entidad ni migración", y eso dejaba AC1.4.1 —registrar a quien
reporta **con su relación**— sin dónde aterrizar. La decisión se corrigió: U11 no
crea entidades nuevas, pero puede ampliar las de U4 de forma aditiva cuando un
criterio aprobado lo exige. Un criterio aprobado manda sobre una decisión de
diseño de esta etapa.

### Tanda 2

**1. AC1.6.1 y AC1.6.2, compuertas duras: el turno de emergencia iba a medias.**
Ante una emergencia, la composición devolvía solo *"podemos seguir con su reporte
después"*, sin la indicación de llamar a emergencias. El criterio pide las dos
frases en el mismo turno, la indicación primero. La prueba que existía afirmaba
exactamente el comportamiento incompleto. Ahora la indicación entra como dato
—la produce el control barato de U10, U11 sigue sin detectar nada (FD-U11-3)— y
con la señal levantada y sin frase la composición **falla**: medio turno de
emergencia es peor que ninguno. Que la indicación sea la primera frase del turno
lo comprueba U12 con el grafo, como dice el propio caso `rt-8-emergency`.

**2. Un reporte completo terminaba en una excepción.** El último bloque del orden
fijo de AC1.5.2, el resumen de cierre, no existía: `compose_question` levantaba
`ValueError` al llegar a él. La tanda lo declaró fuera de alcance "porque ninguno
de los dieciséis casos lo ejercita" —y un criterio aprobado no se cae porque
ningún caso lo mire. Se añadió con sus dos claves de catálogo, una por tipo de
caso, porque una consulta de cobertura tiene dos campos y no siete.

**3. BR3.4 era más laxa en inglés que en español.** Contaba `?` y `¿` juntos con
umbral de dos signos, así que dos preguntas en inglés pasaban y las mismas dos en
español fallaban. Ahora cuenta solo el signo de cierre, que es el que los dos
idiomas comparten (P12).

**4. Los umbrales de insultos llegaban un insulto antes de AC1.13.3**, que dice
"dado que insulto a la agente dos veces seguidas … y si vuelvo a insultar".
Terminar la sesión al segundo insulto le cuelga la llamada a quien todavía tenía
un turno. Y el caso de evaluación venía de la tanda 1 con esa lectura equivocada,
así que **la configuración se escribió para que ese caso pasara**: el caso medía
el código. El caso ganó su tercer turno y su progresión se comprueba entera,
incluido el turno que todavía no dispara nada.

**5. La versión alterna se anotaba como `FIELD_SET`**, que en el historial
significa "el campo se fijó a este valor". La línea de tiempo mostraba el segundo
valor como el vigente, lo contrario de lo que decide FD-U11-7. Es el argumento
con el que U4 justificó `transition_rejected` leído al revés —una entrada que no
distingue lo que pasó de lo que no pasó no sirve de historial— y se arregló igual:
un quinto `ChangeKind` con su migración aditiva, que se niega a bajar si queda
historial de esa clase.

**6. BR5.3 no plegaba el texto**, aunque su archivo declara en el encabezado que
los patrones se comparan plegados: `¿que mas?` coincidía y **`¿qué más?` —la
forma con tildes, que es la que AC1.13.4 nombra— no**.

Dos más, menores y del mismo tipo: *"Sí, no hubo heridos"* se leía como una
corrección —y es la forma normal de confirmar el bloque de seguridad, cuya lectura
pregunta justo por las lesiones—, dejando a la persona en un bucle sin salida; y
una contradicción se medía sobre el texto crudo, así que "12 de Marzo"
contradecía a "12 de marzo" y le ponía al caso una contradicción que nadie dijo.

Cada corrección se comprobó rompiéndola.

### El hueco que se vio al empezar U12

Un noveno defecto, y el más grande, apareció al arrancar el diseño de U12: **la
unidad no había entregado el nodo.** Estaban sus piezas —qué bloque toca, cómo se
lee un bloque, si un turno insulta, cómo se compone una frase— y ninguna sabía en
qué orden se aplican. No había `NodeSpec` ni `run`, mientras los otros tres nodos
tienen los dos, y el propio `functional-spec.md` de esta unidad prometía en su
tabla "U11 entrega el nodo con la forma de C-15".

Se vio porque U12 compone el estado tipado desde las cuatro especificaciones y
solo encontró tres. No lo vio la revisión de la tanda 2 porque el plan de la
unidad —que yo aprobé— dejaba "el ejecutor del nodo y su política de fallo" a
U12, y eso es cierto del **ejecutor**; la especificación y el `run` son del nodo.

El nodo se escribió en la revisión, con el orden del turno como conducta
comprobada: la emergencia primero y sin gastar una llamada al modelo, el abuso
después, la extracción antes de elegir el bloque —al revés se le pregunta a la
persona por el dato que acaba de dar— y la frase con su clave del catálogo al
final. Cada uno de los tres órdenes se comprobó rompiéndolo.

Dos correcciones más salieron de escribirlo:

- **`compose_turn` devolvía solo el texto**, sin la clave del catálogo, cuando el
  diseño de la unidad promete entregar las dos ("U11 entrega la clave y el texto
  compuesto"). La clave es lo que identifica la frase en la traza y en el reporte
  por caso; deducirla del texto sería adivinar cuál la produjo.
- **El conjunto de escritura chocaba con `policy_verification`**, que ya escribe
  `response_key` y `response_text`. Dos nodos no comparten ningún campo del
  estado (convención 6). Los campos de este nodo llevan el prefijo `intake_`, y
  hay una prueba que compara los cuatro conjuntos entre sí, porque `NodeSpec` no
  puede verlo solo. Si U12 decide unificarlos al diseñar el estado, que sea una
  decisión escrita.

## Las dos decisiones de Miguel del 2026-09-27

**El presupuesto de tokens del turno lo cuenta el proveedor.** La tanda 2 lo
contaba con una regla propia sin red y el módulo afirmaba que era un límite
conservador. Es al revés: un tokenizador de subpalabras parte las palabras
largas, y en español da más tokens que palabras, así que estimaba **por debajo**.
PERF-U11.1 se mide con `usageMetadata.promptTokenCount`, que el adaptador de U5
ya lee gratis en cada respuesta, y se publica desde la primera corrida con el
conductor de U13; hasta entonces se reporta como "no medida" con esa causa. La
cuenta sin red se queda como guardia previa, con lo que sí certifica escrito en su
módulo: si un prompt ya no cabe ahí, no cabe. La enmienda está en
`nfr-requirements/performance-requirements.md`.

**El modelo de español de spaCy es GPL-3.0 y se queda.** No lo encontró esta
unidad sino el control de licencias nuevo, y no bloquea publicar el repositorio.
El registro está en `docs/reference/licencias-de-terceros.md`.

## Lo que queda con dueño

- **La indicación de emergencia como primera frase del turno, antes de cualquier
  pregunta:** **U12**, con el grafo. U11 compone el turno con las dos frases en
  orden; que ese turno salga antes que cualquier petición de datos es del
  ejecutor.
- **Cuántas llamadas al modelo caben en un turno:** **U12**, que lleva el
  presupuesto del turno. U11 publica su medición y se ajusta.
- **La regla que deriva un caso por contradicción:** **U9** o U19, en el ritmo de
  fondo. Mira si **existe** una versión alterna, nunca el valor del campo. Y hay
  un límite escrito en `versions.py`: dos redacciones distintas del mismo hecho
  siguen contando como versiones distintas, y decidir cuándo dos textos libres se
  contradicen de verdad es de la regla que las lee.
- **La frase del README sobre el modelo GPL:** **U22**, que construye el README.
  Está escrita y lista para pegar, en los dos idiomas, en
  `docs/reference/licencias-de-terceros.md`.
- **Las conversaciones de punta a punta de DS-2:** **U13**. Los diez casos de esta
  unidad miden los controles del turno, no la conversación completa.
