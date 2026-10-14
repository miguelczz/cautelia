# Revisión de la tanda 2 — U18 `voice-spanish`

"El cambio de idioma". Toda la conducta nueva de la unidad: la lista cerrada de
peticiones, el orden entre las dos fuentes de idioma, el segundo peldaño de la
escalera, y las dos reglas `[bloquea]` que dicen lo que el cambio **no** puede
tocar.

80 pruebas en verde en `mise run test:u18`, 288 en `mise run test:u16`.

## 1. Lo que se rompió, y qué se cayó

Once roturas, once conductas caídas. Ninguna quedó sin tumbar nada.

| Regla | Qué se rompió | Qué se cayó |
| --- | --- | --- |
| BR2.2 | La detección se mira antes que la petición | 11, entre ellas las cuatro direcciones de la petición |
| BR2.4 | El cambio se aplica después de hablar | 6, empezando por el turno que llega al grafo |
| BR3.2 | `TURNOS_PARA_CAMBIAR_SOLO = 1` | 3 |
| BR3.3 | Sin piso de palabras | `test_una_palabra_suelta_nunca_cambia_nada` |
| BR3.2 | La cuenta de turnos seguidos no se reinicia | `test_un_turno_en_el_otro_idioma_y_otro_en_el_de_siempre...` |
| BR3.1 | La detección llega encendida por omisión | `test_la_deteccion_llega_apagada_en_todas_las_aseguradoras` |
| BR4.4 | La frase bilingüe se va al tercer peldaño | 5 |
| BR2.1 | Las negativas se miran después de las peticiones | 10 |
| ADR-013 | El evento del cambio lleva el turno | `test_el_evento_del_cambio_no_lleva_lo_que_se_dijo` |
| Frontera | El fallo del detector no se atrapa | `test_un_detector_que_levanta_conserva_el_idioma_y_deja_rastro` |

**La undécima no contó a la primera.** Quitar el `try` dejando el `except` colgando
es un error de sintaxis, y el rojo que sale de ahí no es conducta rota: es un
archivo que no carga. Se repitió quitando el bloque entero, y entonces sí cayó la
prueba que le toca. Es la condición que la propia skill pone y es fácil de saltarse
cuando la rotura "ya salió roja".

## 2. "I do not speak Spanish" no cambiaba nada

Lo encontró una frase de prueba, no una lectura. Tres pruebas del ciclo vencían por
tiempo con esa frase y no con otras, y la razón era que **"I do not speak Spanish"
contiene "speak spanish"**: la lista veía una petición de inglés y una de español en
el mismo turno, aplicaba la regla de las peticiones contrarias —no adivinar— y
dejaba la llamada en español.

Alguien pidiendo inglés en el inglés más claro posible seguía oyendo español.

Y es probablemente **la forma más frecuente de pedirlo**: quien no entiende nada
rara vez conoce la frase "in English, please"; dice que no habla el idioma en que le
están hablando. Así que la lista gana un segundo mapa, `NEGATIVAS`, donde la clave es
el idioma **al que se va** y no el que se nombra, y se mira **antes** que el de las
peticiones, cortando. La precedencia no es un gusto: sin ella la frase casa con los
dos y vuelve a no hacer nada.

Quien dice que no habla ninguno de los dos tampoco pide ninguno, y eso lo contesta la
escalera del idioma no atendido, que para eso existe.

## 3. El módulo decía haber evitado el falso positivo que tenía

`language_request.py` explicaba en su propio comentario por qué la lista lleva frases
y no palabras sueltas, y ponía el ejemplo: *"mi carro es un Ford, no sé si eso se dice
igual en inglés"*, que no pide nada. Pero la lista tenía la entrada `"en ingles"`, y
esa frase la contiene. El comentario describía una propiedad que el código no tenía
—forma 4 del catálogo, el módulo que miente sobre sí mismo—.

Se quitaron los dos espejos que **nadie había prometido**, `"en ingles"` e
`"in spanish"` sueltos, que existían por simetría y traían el falso positivo sin
ningún criterio detrás. Se quedan `"in english"` y `"en espanol"`, porque son los
literales que la agente promete en AC1.31.4: quitarlos sería prometer algo que no se
cumple. Su falso positivo —"¿cómo se dice eso in English?"— está escrito en el módulo
con su razón y su costo acotado, en vez de estar negado.

Lo comprueba una prueba que recorre las dos listas y exige que ninguna entrada sea
una palabra suelta. Esa es la que avisa el día que alguien añada `"ingles"`.

## 4. Tres defectos del arnés de prueba, no del código

Los tres dejaban el ciclo colgado o sin ejecutar lo que se creía, y los tres se veían
igual: "el cambio de idioma no funciona".

1. **El doble anota la frase cuando empieza a decirla, no cuando termina.** Esperar a
   que la agente hubiera dicho una frase ponía el transcrito a mitad de la apertura:
   el ciclo lo trataba como interrupción —correctamente—, la apertura se repetía
   entera (BR4.5 de U16), y el transcrito nunca llegaba a ser un turno. Con
   `voice.barge_in_stop` en la traza y el grafo sin recibir nada. La condición buena
   es `disclosed_at`, que se escribe cuando la apertura **terminó**.
2. **El reloj de la prueba no avanza.** El turno se cierra cuando vence el fin del
   habla, y con el reloj fijo y un plazo mayor que cero no vence nunca. Las pruebas
   del ciclo de U16 pasan `end_of_speech=timedelta(0)` por esto mismo; las de aquí no
   lo hacían y vencían por tiempo.
3. **Una corrida del linter fuera de su alcance borró una supresión con su razón.**
   `ruff check --fix` invocado desde `app/backend` no ve las exclusiones por archivo
   del proyecto, que están escritas con rutas relativas a la raíz: vio dieciocho
   problemas donde la compuerta ve uno y "arregló" dos, uno de ellos un `# noqa: S608`
   con su razón escrita al lado. Quedó escrito como forma 10 del catálogo, porque lo
   peligroso es que el resultado se ve igual que un arreglo.

## 5. Una cifra publicada que no dejaba ver que sube

PERF-U18.1 salía como **"0,0 ms"** con un decimal, porque el detector de dos idiomas
tarda centésimas de milisegundo y el presupuesto son 15. Una cifra que se publica por
entrega y que no puede subir visiblemente no sirve para lo que está: ahora lleva tres
decimales y el máximo al lado. Medido: **p95 0,044 ms, máximo 0,050 ms**.

Y el detector **se calienta antes de medir**, con su razón escrita. Cargar el modelo
cuesta una vez por proceso y no una vez por turno, así que dejarlo dentro del reloj
mediría el arranque; pero dejarlo dentro confiando en que el p95 descarta la peor
muestra sería peor: sería un número que sale bien porque se tira la muestra que
molesta.

## 6. La constante que partió el bloque de imports

`TURNOS_PARA_CAMBIAR_SOLO` quedó escrita en medio de los imports, con uno debajo.
`mise run lint` no lo vio —E402 no está activa— y `mypy` tampoco. No cambia ninguna
conducta; se arregló al leer el diff, que es el paso 2 y es para lo que sirve.

## 7. El chequeo de artefactos empujaba a escribir más vago

Citar una regla de otra unidad —"la apertura se repetía entera (BR4.5)"— salía como
hallazgo, porque el chequeo busca todo `BRx.y` en las reglas de **esta** unidad. La
salida honesta habría sido quitar el identificador y dejar prosa; es decir, un
chequeo que mejora el número empeorando el documento.

Ahora una regla citada con su unidad al lado —"BR4.5 de U16"— se busca en esa unidad.
Comprobado rompiéndolo por los dos lados: una regla inventada atribuida a una unidad
que sí existe, y una regla que sí existe atribuida a una unidad inventada. Las dos
salen como hallazgo.

Los dos identificadores falsos no se escriben aquí a propósito, y la razón es el
propio chequeo: no sabe distinguir un ejemplo de una afirmación, así que un
identificador inventado en esta frase sería un hallazgo de verdad. Es el precio de un
chequeo sin escapes, y se paga sin perder nada: lo que un lector necesita saber es que
se comprobaron las dos direcciones.

## 8. Lo que no se debilitó

- Las cuatro pruebas de U16 que se tocaron cambiaron **porque la regla cambió**
  (BR4.4, el segundo peldaño), y cada una lleva escrito en su docstring qué cambió y
  qué no: la intención —la escalera ayuda en vez de repetir, el tercero ofrece otra
  cosa— es la misma. Ninguna se relajó ni se borró.
- La supresión del linter que la corrida fuera de alcance borró se devolvió con su
  razón intacta.
- Ningún umbral, ningún piso de cobertura, ninguna compuerta dura. PERF-U18.1 se
  midió; no se ajustó.
- `mise run contracts:gen` se corrió y su salida entra en el commit: el esquema de la
  aseguradora con la clave nueva y la tabla de copy de la consola con la frase
  bilingüe.
