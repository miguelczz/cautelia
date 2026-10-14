# Hallazgos de la tanda 2 — U17 `voice-public-link`

Los contadores y el cable. Escrita en la sesión principal el 2026-10-02, porque el
guardián del motor no deja delegar código de una unidad que no es la que él cree
activa (PENDIENTES 1.13).

**Reglas que cierra:** BR1.1, BR1.3, BR1.4, BR2.1, BR2.2, BR3.2, BR3.3 y BR3.4.
Con esto la unidad queda cerrada.

## Lo que el cableado dejó al descubierto

**Cinco piezas construidas, probadas y sin consumidor**, y las cinco en el mismo
camino: la decisión de admisión (`voice/admission.decide`), el contador de cuota de
U5 (`load_counter`), el modo de voz (`quota.voice_mode` por
`reserve_primary_voice`), el cupo diario derivado (`site_daily_quota`, de U5) y la ventana
de retoma. La ruta servía los dos carriles **en nulo**, abría llamadas sin contarlas
y escribía `VoiceMode.PRIMARY` a mano en cuatro sitios.

Es la forma 13 del catálogo, y aquí apareció con una vuelta de tuerca que no había
visto antes: **dos de esas piezas, al cablearlas, resultaron no poder funcionar.**

### 1. La reserva por llamada no se puede medir, no es que no esté medida

`call_reserve` pregunta el precio de los **segundos de audio del plan de la voz**, y
ese plan es el del modelo (`gemini / gemini-3.1-flash-lite`), que se cobra por
tokens. La tabla de precios nunca va a tener esa línea: los segundos de audio los
cobran la transcripción (`deepgram / nova-3`, que **sí** está en la tabla, a
0,000153 USD/s) y la síntesis (por caracteres).

Su docstring dice «puede quedar no medida: la tabla no publica hoy el precio por
segundo de la voz, porque lo fija el experimento 1». La diferencia importa: no es
que falte un dato, es que **se le pregunta al proveedor equivocado**.

**Qué efecto tiene ahora que está cableado:** la reserva sale sin medir → el cupo
diario del sitio sale **cero** (la regla del cupo derivado de U5 lo manda así: no se divide por lo
que no se sabe) → **el enlace público de voz no abre ninguna llamada**. Es el lado seguro y es
lo que la regla prescribe; también es una superficie publicada que no funcionaría.

### 2. La voz de respaldo es inalcanzable por el presupuesto

La aritmética no deja hueco: para que el cupo del sitio sea al menos uno hace falta
`restante >= días × reserva`, y con un día o más eso implica `restante >= reserva`,
que es exactamente lo que `covers_primary_voice` pregunta. **Siempre que una llamada
cabe, cabe con la voz principal.** El modo de respaldo solo aparece cuando el
presupuesto no se puede leer.

Quedó fijado como prueba en `tests/unit/telemetry/test_quota.py`: recorre una rejilla
de restantes y de días, y exige que todo cupo mayor que cero cubra la voz principal.
**Esa prueba se cae el día que alguien cambie la derivación** —por ejemplo, para que
el cupo se calcule con la reserva de la voz **de respaldo**, que es para lo que la
voz de respaldo existe— y ese es justo el día en que hay que volver a mirar el modo.

## Y el arreglo de las dos, decidido por Miguel el 2026-10-02

Su respuesta fue «arregla todo de una vez», así que las dos quedaron arregladas en
la misma tanda.

### La reserva ahora se suma de sus tres componentes

`providers.yaml` declara **lo que consume** una llamada pública de duración máxima
—no lo que cuesta, que eso lo dice la tabla de precios—, y la reserva es la suma:

| Componente | Consumo declarado | Con la voz principal | Con la de respaldo |
| --- | --- | --- | --- |
| Transcripción (`deepgram / nova-3`) | los 180 s de la llamada | 0,0276 | 0,0276 |
| Síntesis | 1.300 caracteres | 0,0650 (`cartesia`) | 0,0390 (`deepgram`) |
| Modelo (`gemini`) | 15.000 de entrada, 1.000 de salida | 0,0052 | 0,0052 |
| **Total** | | **0,0978** | **0,0718** |

Los segundos no se declaran dos veces: salen de `voice_limits.max_call_seconds`. El
número de caracteres sí es una suposición, y está escrita con su razón: la agente
habla la mitad de la llamada y una voz de atención dicta unos 850 caracteres por
minuto.

**Si a cualquier componente le falta su precio, la reserva no se sabe.** No se suma
lo medido ignorando el resto: una reserva incompleta es más barata que la de verdad,
y una reserva más barata reparte más llamadas de las que caben. Y un chequeo nuevo de
`schema:check` falla cuando la tabla no valora uno de los cinco pares, para que la
próxima vez el síntoma no sea un enlace cerrado sin explicación.

### Los minutos de grabación también se convertían, y nadie lo hacía

La reserva del video está declarada en minutos —45— y **nadie los pasaba a dólares**:
la fila de la ventana se sembraba con la reserva en nulo, y una reserva en nulo deja
el restante público sin medir, que cierra todo lo que cuesta dinero. Se convierte con
la misma aritmética que una llamada: 45 minutos son quince llamadas de duración
máxima a la voz principal, **1,468 USD**.

### El piso de una llamada, que es lo que abrió el enlace

El cupo diario era el reparto del restante entre **todos** los días que faltan. Con
5 USD y noventa días eso da cero desde el primer día: el enlace no habría abierto ni
una llamada en toda la ventana, teniendo presupuesto para casi cincuenta.

Ahora, mientras el restante alcance para una llamada, el cupo es al menos una. Lo que
se acepta a cambio está escrito junto al cálculo: el presupuesto puede agotarse antes
de que la ventana termine. Se acepta porque **el tope diario del sitio ya acota la
ráfaga** —una llamada al día no se lleva el presupuesto en una tarde— y porque un
enlace cerrado los noventa días no demuestra nada.

### Y el cupo se calcula con la voz barata

El cupo con la reserva de **respaldo** y el modo con la de la **principal**. Eso abre
el tramo entre las dos —de 0,0718 a 0,0978— en el que la llamada cabe y la voz
principal no: ahí suena la de respaldo, que es exactamente para lo que está. Antes las
dos preguntas usaban la misma reserva y el tramo no existía.

**Con los números de hoy:** techo 5 USD, reserva del video 1,468, restante 3,53, que
son **49 llamadas**; el cupo del día es **una**, y la voz principal está cubierta. El
enlace público de voz abre llamadas.

## Las piezas

1. **`lanes_for(resumes)`**: el orden en que se cobran los carriles y la asimetría de
   la retoma, escritos **una vez**. Los usan los dos caminos: la disponibilidad, que
   lee, y la apertura, que consume.
2. **La disponibilidad decide de verdad**: lee los dos contadores sin tocarlos
   (`spend.quota_state`, nuevo y de solo lectura), llama a la decisión y responde el
   carril que paró la llamada con la clave de su frase. Y sirve los dos carriles con
   su número: el del sitio es **el cupo de hoy**, no el tope escrito.
3. **La apertura cobra** con `check_quota`, que consulta y consume en un solo acto
   (RT-13), en el orden de `lanes_for`.
4. **El modo lo decide la contabilidad**: `reserve_primary_voice` con el
   identificador de la llamada a la vista —de ahí que `open_call` acepte el
   identificador— y `expected_voice_mode` (nuevo) para el aviso de la consola, que es
   la misma política sin inventar un identificador.
5. **El invariante del carril del sitio se mudó** de la decisión a `VoiceLimits`: que
   el **tope escrito** no quede por debajo del de una conexión es un error de
   archivo; que el **cupo de hoy** quede por debajo, incluso en cero, es que hoy no
   caben más llamadas.

## Las seis roturas, y qué se cayó

| Rotura | Qué se cayó |
| --- | --- |
| Abrir no cobra ningún carril | 3 pruebas |
| Una retoma gasta la llamada del día | 5 pruebas |
| El carril del sitio se cobra antes que el de la conexión | 2 pruebas |
| Mirar la página gasta la llamada del día | 1 prueba *(ninguna, antes de corregirla)* |
| El modo esperado es siempre el principal | 1 prueba |
| El tope del sitio puede quedar por debajo del de una conexión | 1 prueba |
| La reserva suma lo medido e ignora el resto | 2 pruebas |
| El cupo se calcula con la voz cara | 1 prueba *(ninguna, antes de añadirla)* |
| Sin el piso de una llamada | 6 pruebas |
| La consola muestra una latencia que la traza no respalda | 1 prueba |
| El enlace viaja para cualquier estado del caso | 2 pruebas |
| La llamada se lee sin comprobar de quién es | 2 pruebas |
| El caso que espera se queda sin salida | 1 prueba |

**Y la segunda rotura que no tumbó nada:** calcular el cupo con la voz cara pasaba
todas las pruebas, porque con el presupuesto de hoy las dos reservas dan el mismo
cupo. La diferencia solo se ve en el tramo entre las dos, y ninguna prueba lo
ejercitaba: ahora hay una, de punta a punta, que pide `available: true` y modo
`fallback` con el restante en ese tramo.

**La rotura que no tumbó nada, otra vez por una prueba vacua.** La mía miraba la
disponibilidad **sin galleta**, y sin sujeto no hay contador que gastar: el defecto
pasaba por el retorno temprano. El caso real es el que la corrige: la galleta del
visitante es **la misma del chat**, así que quien llega a la consola después de
escribir en el chat ya la trae y sí tiene contador.

## Lo que hubo que corregir en pruebas de otras unidades

- **U16 exigía que los carriles salieran nulos**, con su razón escrita: «nadie los
  aplica, y servir un número diría que hay un límite que no existe». Ahora los
  aplica la apertura, así que la prueba dice lo contrario y nombra por qué cambió.
  Es la forma 14 del catálogo.
- **La foto del presupuesto de U16 no tenía reserva de grabación**, así que el
  restante público salía sin medir y el carril del sitio cerraba: ocho de sus
  pruebas dejaron de poder abrir una llamada. Ahora la trae medida, con la razón.
- **Los contadores de cuota no se vaciaban entre pruebas.** No son de ninguna
  aseguradora —viven en el esquema del proyecto— y hasta ahora nada los consumía en
  esa carpeta; sin vaciarlos, la segunda prueba que abría una llamada con la misma
  galleta recibía el 503 de la anterior.

## Decisiones que tomé

1. **Los números no se leen dos veces.** Los dos carriles se le preguntan a U5, que
   los recibe de `providers.yaml` por la raíz de composición. La ruta no vuelve a
   leer el archivo: dos lecturas del mismo número es como se acaba prometiendo en la
   pantalla un cupo distinto del que la apertura aplica.
2. **Si el carril del sitio se agota justo después de cobrar el de la conexión, no se
   compensa.** Lo que U5 ofrece para devolver cupo está atado a una llamada que se
   abrió y se cerró sin gastar, y ahí no hay llamada. Cobrar el sitio primero movería
   la misma injusticia al carril caro, que entregaría un hueco del sitio a quien no
   puede usarlo. Queda un evento en el rastro que lo dice.
3. **El modo esperado falla cerrado ante cualquier fallo de lectura**, no solo ante el
   que U5 declara: es la misma razón por la que el techo se cierra ante cualquiera, y
   esta respuesta se dibuja en una pantalla antes de saber si hay voz.
4. **La disponibilidad no promete carriles cuando la voz está apagada.** Decirle «una
   llamada al día» a quien no va a poder llamar es decirle que podría.

## La consola, el punto 4 del plan

**BR3.2 — los tres a la vista.** Faltaba el tiempo. El estado en palabras y el botón
ya estaban; lo que no había era cuánto queda. Los tres viven ahora en la misma región
pegada al borde de abajo. El cronómetro es del navegador y no pretende medir nada —el
servidor corta la llamada por su cuenta— y lo que queda se **deriva** al dibujar:
escribirlo desde el efecto es una cascada de renderes que el linter de React señala
con razón.

Lo que jsdom no puede comprobar es la disposición; eso lo mide el arnés. Lo que sí
queda fijado es que ninguno de los tres se salga de esa región.

**BR3.3 — la latencia es la de la traza, no otra.** `first_audio` ahora **devuelve**
los milisegundos que acaba de escribir en la traza, y el ciclo manda esa misma cifra
a la consola en un cuadro nuevo del protocolo. Una sola función la calcula y dos la
consumen; la prueba compara el milisegundo del cuadro contra el del evento, no uno
parecido. Con la rotura puesta —sumarle siete al cuadro— se cae.

El cuadro lleva **su turno**: sin él, la consola tendría que suponer que el último
cuadro es del último turno.

**BR3.4 — dónde quedó el caso, y la salida del que espera.** Dos rutas nuevas: el
desenlace (`GET .../outcome`) y el traspaso (`POST .../handoff`). El desenlace trae el
número del caso, su estado, y **el enlace solo cuando hay algo que abrir con él**: un
caso derivado o cerrado tiene una página que leer; uno que espera datos no, y lo que
necesita son sus dos salidas.

- **El enlace se emite al terminar, no al abrir:** vive una hora, y uno emitido al
  principio de una llamada de tres minutos llega a la pantalla con la hora empezada.
- **La llamada de otro navegador responde igual que una que no existe**, y el resumen
  de la galleta viaja **dentro** de la consulta: comparar fuera dejaría la fila leída
  antes de saber si era suya. Romperlo tumba dos pruebas.
- **Traspasar dos veces no falla**: un caso que ya no admite la derivación no es un
  error de quien pide —su salida ya está tomada— y lo que se devuelve es dónde quedó.
- **Derivar es una transición de U4** con su motivo del conjunto cerrado, y el actor
  es el visitante: el registro no puede decir que lo derivó alguien de la bandeja.

## Un riesgo que no es de esta tanda y queda dicho

**La voz firma su token de socket con la clave del enlace de caso.** `Settings`
declara dos claves y documenta la segunda como «firma el enlace de caso (una hora de
vida), distinta de la anterior»; la raíz le pasa esa misma clave a la voz, que la usa
para su token de socket. Son dos familias de token con una sola clave: rotarla
invalida las dos a la vez, y el radio de un compromiso abarca las dos superficies. No
lo cambié —pide un ajuste nuevo y un despliegue— y el enlace que esta tanda emite usa
esa clave porque es la correcta para un enlace de caso.

## Lo que corrí

- `mise run test:u17`: 60 del backend (ahora con la carpeta de integración) y 47 de
  la consola, en verde.
- Las suites de U5, U16, la telemetría, la voz y los proveedores: **532 en verde**.
- Las **once compuertas baratas, las once**. Tres salieron rojas por el camino:
  `fmt:check`, `lint` (un `__all__` sin ordenar) y `types` (un enum importado del
  módulo que lo reexporta y no del que lo declara).

## Lo que no pude correr

- `scripts/verify.sh`, `mise run cov` y la suite completa: es la máquina de Miguel.
- El arnés de accesibilidad y las evaluaciones contra proveedores.
