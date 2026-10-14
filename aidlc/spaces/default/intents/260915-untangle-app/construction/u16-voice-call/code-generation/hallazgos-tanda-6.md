# Revisión de la tanda 6 — U16 `voice-call`

"La consola y el conductor de evaluaciones". La pantalla de la llamada, los dos
nodos de audio, el conductor de DS-5 y 288 pruebas: 256 del servidor y 32 del
navegador.

Con esta tanda U16 queda cerrada.

## 1. Lo que se rompió, y qué se cayó

Siete roturas del lado del navegador, **las siete tumbaron una prueba de
conducta**. Todas deshechas.

| Regla | Qué se rompió | Qué se cayó |
| --- | --- | --- |
| BR1.2 | La sesión se abre antes de pedir el micrófono | `un microfono negado no abre ninguna llamada` |
| BR4.2 | El micrófono se pide sin cancelación de eco | `con las tres correcciones del navegador activadas` |
| BR4.3 | La interrupción marca la última línea y no la de la agente | `marca la linea de la agente y no la ultima a secas` |
| BR7.2 | El parcial se acumula en vez de sustituirse | tres, entre el reductor y la pantalla |
| C-29 | Un cuadro desconocido se acepta como si fuera bueno | `un cuadro que este protocolo no conoce se descarta sin romper la pantalla` |
| BR1.6 | Los seis finales comparten frase | tres, entre la tabla y la pantalla |
| C-29 | Una clave desconocida inventa una frase de repuesto | `una clave desconocida devuelve nulo y no una frase de repuesto` |

Del lado del servidor, lo que esta tanda añadió —el conductor de evaluaciones—
lleva sus cinco pruebas, incluida la que separa **no medida** de **fallida**.

## 2. El arnés de romper y correr daba falsos positivos

La primera versión del guion de esta revisión invocaba a `vitest` con un reportero
que no existe. El proceso salía con código distinto de cero **siempre**, así que
las siete roturas se anotaron como "se cayó una prueba" y ninguna se había caído
por la razón que decía.

Se descubrió mirando una de ellas a mano: BR4.2 —el micrófono con cancelación de
eco— no tenía **ninguna** prueba, y el arnés decía que sí. Es la forma 2 del
catálogo, la aserción que no puede distinguir, aplicada esta vez al instrumento en
vez de al código: un arnés que no distingue un fallo de una invocación mal escrita
convierte la revisión entera en teatro.

Corregido el guion, seis de siete cayeron y la séptima quedó descubierta. BR4.2
tiene ahora su prueba, y es la única de las siete que nació de esto.

## 3. El ciclo de la llamada se mudó a la unidad

`voice_loop.py` nació en `untangle.server` en la tanda 5, porque recibía la
plataforma de voz entera y eso son los adaptadores, que solo la raíz importa. Al
reducir esa dependencia al puerto `CallVoice` —cuatro líneas— dejó de haber
ninguna razón para tenerlo arriba, y apareció una para bajarlo: **el corredor de
evaluaciones está debajo de la raíz y no podía alcanzarlo**.

Un ritmo de llamada que el corredor de evaluaciones no puede ejecutar es un ritmo
que solo se mide en producción. Ahora vive en `untangle/voice/loop.py`, que es
donde el plan de generación lo ponía desde el principio, y los 35 contratos de
importación siguen en verde.

## 4. Un cuarto estado que no existía

El diseño listaba cuatro estados visibles y el cuarto era "un momento", la frase
de espera. El protocolo no tiene tal estado: lo que `State` lleva son
`connecting`, `live`, `listening`, `speaking` y `ended`.

Lo que ese cuarto estado quería —que la frase de espera **se lea** y no solo se
oiga— ya se cumple, porque cada cosa que la agente dice viaja también como
transcripción. Se quitó la clave del catálogo en vez de inventarle un productor, y
el chequeo de claves sin consumidor fue quien lo señaló. Una etiqueta genérica en
su lugar habría dicho menos que la frase.

## 5. Un chequeo nuevo, en la dirección que faltaba

`mise run voice:frases`, hermano del que ya existía para el chat. El del catálogo
mira que toda clave escrita se use en algún sitio; este mira la contraria: que
**toda clave que el servidor puede mandar por el socket, la consola sepa decirla**.
Ninguna de las dos implica la otra.

Hace falta precisamente porque la consola devuelve nulo ante una clave que no
conoce, y eso es deliberado: los avisos son un conjunto cerrado, así que una clave
desconocida es un contrato roto y no un caso de ejecución. Sin este chequeo, ese
contrato roto sería un hueco en pantalla; con él, es una compuerta.

Sale de las tablas de cada dueño —las cuotas de U5, la voz apagada de U15, el
aviso de tiempo de U16— y no de una lista escrita a mano, que se quedaría atrás
justo el día en que U17 añada su carril.

## 6. Decisiones tomadas al escribir

1. **El `AudioContext` se crea a 24 kHz y nadie remuestrea.** Quien adapta la
   frecuencia del micrófono es el navegador al conectar la fuente. Un
   remuestreador escrito a mano sería una segunda implementación de algo que el
   navegador ya hace mejor, con un error de redondeo propio.
2. **Los dos nodos devuelven siempre `true`.** Devolver `false` una sola vez apaga
   el nodo para siempre, y así es como se pierde el micrófono a mitad de una frase
   sin que nada lo diga.
3. **La cola se vacía en el transporte y no en React.** Pasar `stop_audio` por un
   estado y esperar al siguiente pintado metería un cuadro de dibujo entero en el
   camino de lo único que NFR2 mide.
4. **El nivel del micrófono se calcula en el nodo de captura**, con las mismas
   muestras que ya se están mandando. No pide nada al servidor y no sale del
   navegador: existe porque sin él, quien tiene el micrófono silenciado por el
   sistema habla dos minutos contra una pared.
5. **La grabación del conductor entra a 20 ms por trozo y con su reloj.** Empujarla
   de golpe mediría otra cosa: el detector de fin de habla cuenta silencio, y un
   archivo entregado en un instante no tiene silencios que contar.
6. **El conductor de voz no se registra en el proceso servido**, a diferencia del
   de texto. DS-5 corre por hito y a mano; dejarlo registrado sugeriría que la
   compuerta lo ejecuta.
7. **Una grabación que falta no es un caso fallido.** Levanta su propio error
   nombrando el archivo, y el comando lo imprime como "no medida". Colapsarlas
   contaminaría una métrica publicada con fallos de infraestructura.

## 7. Un contrato de importación enmendado, con su prueba

El comando `voice:call-live` necesita a la vez **los adaptadores de proveedor**
—que solo `untangle.server` importa— y **el corredor de evaluaciones**, y no hay
ninguna capa donde esas dos cosas se encuentren. El contrato "el código de
producción no importa `untangle.evals`" lo prohibía, y prohibirlo no protegía
nada: dejaba la regla imposible de cumplir y el conductor de voz sin llamador de
producción, que es la forma de defecto que más ha costado aquí.

Es el mismo razonamiento y el mismo sitio que la enmienda del 2026-09-28, que
sacó a `untangle.server` del contrato de LangGraph.

**Se excluye una arista y no el paquete**, y esa diferencia es toda la enmienda:
`untangle.server.voice_cli -> untangle.evals.**`. `composition.py` —el proceso
servido— sigue sin poder ver el corredor de evaluaciones, ni directo ni por
cadena. Tres pruebas lo sostienen: que la arista permitida pasa, que una
importación desde la raíz de composición **no** pasa, y que el contrato sigue
nombrando a `untangle.server` entre sus orígenes. La tercera es la que se pierde
en silencio: sin ella, alguien podría sacar el paquete de la lista y las dos
primeras seguirían verdes, porque lo permitido es un subconjunto.

## 8. Una regla que no tiene prueba, dicha

**BR7.1 en el navegador no está defendida por ninguna prueba**, y conviene decirlo
en vez de dejarlo implícito. Que no se guarde audio es una **ausencia**: no hay
campo, no hay archivo, no hay arreglo que crezca. Lo que la sostiene es el diseño
—el nodo de captura entrega su búfer en la lista de transferencia, así que pierde
la propiedad y no puede retenerlo— y que ninguna pieza tenga dónde ponerlo.

Del lado del servidor sí hay prueba, en el conductor de evaluaciones, que es donde
más tentador sería guardarlo "solo para poder volver a oírlo". Del lado del
navegador, una prueba que leyera el texto del archivo buscando la palabra
prohibida sería un grep disfrazado de prueba, y no la escribo.

## 9. La tubería encontró lo que tres pasos locales no miran

La tanda se subió con `fmt:check`, `lint` y `types` en verde y falló en el paso 6,
las aserciones de esquema: las pruebas de la consola nombraban una aseguradora
real —`sunmeadow`— dieciocho veces, y ningún identificador de aseguradora vive
fuera del cargador y de las fixtures (BR4.2).

La lista de exclusiones de ese chequeo cubre `app/backend/tests` y
`app/frontend/e2e`, pero **no** las pruebas dentro de `app/frontend/src`. No se
tocó la lista: se cambió el identificador por uno inventado, que es lo que ya hacía
la prueba del chat. Aflojar el chequeo para que pasara mi prueba habría sido
exactamente lo que la regla existe para impedir.

La lección es de método y no de código: las tres comprobaciones baratas que corro
en local no son el guion entero. Desde esta tanda corro también `tenancy:literals`
y `contracts:check`, que son los dos pasos del 6 que no necesitan base de datos y
tardan segundos.

## 10. Lo que no se debilitó

Ninguna prueba existente relajada ni borrada. Ningún umbral ni piso de cobertura
bajado. Ninguna compuerta dura saltada. Dos reglas del linter apagadas, cada una
con su razón escrita al lado y ninguna de seguridad: `no-invalid-void-type` solo
sobre el cliente generado —una respuesta 204 se genera como `void`, y dejarla
activa significaría que ninguna ruta puede responder 204— y los globales del hilo
de audio declarados aparte para los dos nodos, que es lo contrario de aflojar: es
lo que impide que un `document.querySelector` se cuele en un archivo donde no
existe.

## Sources

- `code-generation-plan.md` — tanda 6
- `../functional-design/frontend-components.md`, `rules.md`
- `../../../inception/contract-design/contract-summary.md` — C-08, C-22, C-29
- `docs/reference/como-se-revisa-el-codigo.md`

## Assumptions & Open Questions

None.

La consola quedó aprobada tal como está. Miguel leyó las veintidós claves nuevas
—`voice.console`, `voice.state` y `voice.ended`— el 2026-09-29 y no pidió cambios:
*"referente al punto a no hay que cambiar nada, todo lo veo bien"*. **Queda
cerrada y no se vuelve a preguntar**; el aspecto se puede cambiar después sin
tocar el servidor, porque lo único que cruza el socket son estados y claves.
