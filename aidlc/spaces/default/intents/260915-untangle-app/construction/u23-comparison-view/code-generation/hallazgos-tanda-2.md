# Hallazgos de la tanda 2 — U23 `comparison-view`

La costura: las tres conversaciones reales, el idioma de la pregunta, la divulgación
registrada en los tres casos, el emisor de la agencia en el contrato, el reconocedor
de fuera de propósito y el aislamiento sobre las trazas. Escrita en la sesión
principal el 2026-10-02, porque el guardián del motor no deja delegar código de una
unidad que no es la que él cree activa (PENDIENTES 1.13).

**Reglas que cierra:** BR1.4, BR2.1, BR2.3, BR3.1 `[bloquea]`, BR3.2.

## El hallazgo que cambió la tanda: nadie registraba la divulgación del chat

BR1.4 pide registrar la divulgación de la vista en los tres casos. Al ir a añadir la
superficie a esa llamada, **la llamada no existía**: `chat/opening.py` tenía su
`record` desde U13 y **ninguna ruta lo llamaba**. La conversación quedaba marcada
como divulgada —`disclosed_at`, que es lo que impide atender un mensaje antes de la
apertura— pero `disclosure_record` se quedaba vacío.

Lo que eso costaba el día que el ritmo de fondo se cablee: `closure` **rechaza el
cierre** de un caso sin divulgación registrada (BR6.1 de U10). Todos los casos del
chat se habrían quedado sin poder cerrarse, por una divulgación que sí se mostró, y
el síntoma habría aparecido en el nodo de cumplimiento y no aquí.

Es la forma 13 del catálogo otra vez —la decisión pura que producción no llama— y la
cuarta vez que aparece en este proyecto.

## Las piezas

1. **`Surface`**, dato del mensaje y no rama por pantalla (FD-U23-8). Decide dos
   cosas: qué apertura se publica —ninguna, cuando la pantalla ya mostró la suya— y
   con qué clave queda registrada la divulgación. Tabla cerrada de dos filas.
2. **El registro, al nacer el caso**, con la clave de la superficie que lo mostró.
   Va en la entrega y no en la ruta porque hasta ahí no hay caso al que atarlo.
3. **Fuera de propósito en el servidor**, con el reconocedor determinista que ya
   existía, y **después de contar el mensaje**: tres mensajes se mandaron, así que
   tres se descuentan (BR2.3).
4. **`example_policy_issuer`** en la configuración, obligatorio en una agencia y
   prohibido en una emisora, con el chequeo que lo compara con el `issuer_tenant` de
   la póliza versionada. Se declara el identificador; el nombre visible lo resuelve
   el directorio del inicio, que es la única pieza con las tres a la vista.
5. **`askInsurer` cableado**: abre el flujo, manda con su superficie y su idioma, y
   espera la respuesta cerrada. Tres rechazos distintos y ninguno es un fallo.
6. **El aislamiento sobre las trazas**, por las rutas de las tres columnas.

## Lo que el idioma escondía, y que medir sacó

Mi primera prueba del idioma **no podía fallar**: aceptaba el 409 y después no
afirmaba nada, así que pasaba igual con el respaldo de idioma ignorado. Al medir
apareció el caso de verdad:

**`¿Cubre granizo?` es pregunta de cobertura en español y no trae señal de idioma**
—es demasiado corta para el umbral de confianza del detector—. Sin el idioma de la
pantalla como respaldo, cada columna cae en el idioma por omisión de su aseguradora
(`en`, `es`, `en`) y pasan dos cosas:

1. La misma pregunta vuelve contestada en dos idiomas, que es lo que BR2.1 prohíbe.
2. Y peor: en las dos aseguradoras de idioma inglés la juzga el reconocedor de
   cobertura **en inglés**, que no la reconoce, así que la vista responde «fuera de
   propósito» a una pregunta de cobertura legítima.

Con la rotura puesta, la prueba corregida da `[409, 202, 409]` donde debe dar
`[202, 202, 202]`. Por eso `MessageIn` lleva el idioma de la pantalla: quien decide
sigue siendo el detector, y esto solo cambia con qué empata.

## Las ocho roturas, y qué se cayó con cada una

| Rotura | Qué se cayó |
| --- | --- |
| El caso nace sin su divulgación registrada | 2 pruebas |
| La vista registra la divulgación del chat | 1 prueba |
| La apertura del chat se publica también en la vista | 1 prueba |
| La vista admite lo que no es pregunta de cobertura | 2 pruebas |
| El corte se adelanta al conteo | 1 prueba |
| El idioma de la pantalla se ignora | 1 prueba *(ninguna, antes de corregirla)* |
| La traza se busca en todas las aseguradoras | 2 pruebas |
| Preguntar desde la comparación sale gratis | 2 pruebas |

Y una novena, en los datos: el emisor declarado que la póliza desmiente falla
`schema:check` nombrando a los dos.

## Decisiones que tomé

1. **La clave que se registra de la vista nombra el bloque** `comparison.disclosure`
   y no una de sus cuatro frases, porque lo que se mostró son las cuatro juntas. Una
   prueba comprueba que el catálogo siga trayendo claves bajo ese prefijo: una clave
   registrada que ya no existe apunta a algo que nadie puede leer.
2. **El 409 y no el 422** para fuera de propósito: el marco ya usa el 422 para un
   cuerpo mal tipado, y dos modelos en el mismo código dejarían al cliente generado
   sin poder distinguirlos.
3. **Una derivación a una persona se dibuja como fallo de la columna.** La vista no
   tiene estado para «alguien lo está revisando» e inventarlo es trabajo de diseño
   que esta tanda no hace. Lo que el visitante lee —«no se pudo revisar la póliza»—
   es lo que de verdad le pasa a la comparación de esa columna.
4. **`out_of_scope` devuelve la columna a vacío**, no a fallo: dibujarla como fallida
   diría que la póliza no se pudo revisar, y lo que pasó es que no se preguntó por
   una cobertura.
5. **El puerto no lleva plazo propio.** Cada camino de fallo del servidor publica
   algo —el turno roto publica su error antes de relanzar—, así que un plazo aquí
   solo podría cortar una respuesta que venía en camino. Lo que cierra la espera si
   la conexión muere es `onerror`.
6. **La pantalla dejó de decidir el alcance.** Su prueba cambió de «no se manda» a
   «se manda y el servidor lo rechaza», que es lo que Q3 decidió y lo que hace que
   descuente sus tres mensajes.

## Riesgos y límites que dejo dichos

1. **La cita de la cláusula dentro de la traza no está comprobada aquí.** BR3.1 es
   compuerta dura y se cumple por construcción —la recuperación es por aseguradora y
   U8 lo prueba donde ocurre, con su doble determinista—; lo que esta tanda añade es
   el otro lado: que la traza de cada columna solo se lea desde su columna, y que una
   ajena y una inexistente se respondan igual. Leer las tres trazas de una pregunta
   real necesita el corpus ingerido y el modelo, así que corre en la capa de
   evaluaciones y contra el despliegue vivo. **No lo simulé con un doble**: una
   prueba que leyera las trazas que escribió mi propio doble no probaría nada.
2. **Una pregunta de la vista roba el flujo del chat de esa aseguradora** si el
   visitante lo tenía abierto en otra pestaña: el registro de colas cierra la
   anterior, que es la regla «una pestaña, un flujo» que ya existía. No es nuevo y no
   lo toqué.
3. **El cableado del grafo de fondo** (PENDIENTES 1.8) sigue siendo lo que falta para
   que una columna responda de verdad: hoy la respuesta la da el manejador de turno
   que esté enchufado.

## Lo que corrí

- `mise run test:u23`: **12 pruebas de integración**, en verde, contra la base
  efímera.
- Las pruebas de integración de U13 y de U10, y las unitarias del chat y de
  cumplimiento: **344 en verde**. Toqué el chat y el registro de cumplimiento.
- La suite del frontend entera: **393**, en verde.
- Las **once compuertas baratas, las once**. Tres salieron rojas por el camino y se
  arreglaron: `fmt:check` dos veces, `types` por un valor de límite que no existe en
  el enum, y `schema:check` porque `tenant.yaml` es fuente del manifiesto generado.

## Lo que no pude correr

- `scripts/verify.sh`, `mise run cov` y la suite completa: es la máquina de Miguel.
- `mise run a11y`: el arnés de accesibilidad. La tanda 1 lo pidió para esta pantalla
  y sigue pendiente; lo que esta tanda cambia ahí es que la respuesta declarada del
  arnés ya trae el emisor, así que mide la vista llena.
- Las evaluaciones contra proveedores.
