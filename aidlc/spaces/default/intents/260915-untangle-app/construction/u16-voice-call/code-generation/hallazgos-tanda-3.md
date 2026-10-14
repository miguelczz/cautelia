# Revisión de la tanda 3 — U16 `voice-call`

"Interrumpir, deletrear y cerrar". Cuatro módulos nuevos, una lista versionada
añadida a una tabla de U11, y 175 pruebas.

## 1. Lo que se rompió, y qué se cayó

Nueve roturas, **las nueve tumbaron una prueba de conducta**. Todas deshechas.

| Regla | Qué se rompió | Qué se cayó |
| --- | --- | --- |
| BR3.5 | La lista de letras confundibles deja de mirarse | 2 pruebas, una por idioma |
| BR3.7 | El número de caso se dice de corrido | 8 pruebas |
| BR3.7 | El cero pasa a decirse "oh" | 2 pruebas, una por idioma |
| BR4.1 | Cualquier parcial calla a la agente | 4 pruebas, incluida la del ruido |
| BR4.3 | La parada por interrupción deja de marcarse en la traza | `test_la_parada_por_interrupcion_deja_su_marca` |
| BR4.5 | Una apertura cortada se da por dicha | `test_la_apertura_cortada_se_repite_entera` |
| Tabla | La lista de confundibles pierde el inglés | 55 pruebas, y el cargador falla al arrancar |
| BR3.5 | El cableado deja de mirar si hay código que leer | 4 pruebas del recorrido |
| BR3.7 | El cableado deja de cerrar un caso completo | `test_un_caso_completo_cierra_con_su_numero...` |

## 2. El hallazgo: tres módulos sin llamador, en mi propio código

Antes de commitear me hice la pregunta que este proyecto ha pagado cuatro veces:
*¿quién llama a esto en producción?*

```
readback     llamadores en produccion:
closing      llamadores en produccion: voice/case_number.py
case_number  llamadores en produccion: voice/closing.py
barge_in     llamadores en produccion: voice/latency.py voice/call.py
```

`readback` no lo llamaba nadie. `closing` y `case_number` se llamaban **entre
ellos**: un lazo cerrado sin ninguna entrada desde el motor de la llamada. Tres
módulos construidos, documentados, con sus pruebas en verde, y ninguno conectado
a nada. Es exactamente la forma que dejó el chat sin poder atender a un visitante
con 2.363 pruebas pasando.

La quinta instancia, y la primera en código mío dentro de la misma sesión en la
que la estaba vigilando.

**Lo que se hizo.** Cablear los tres en `CallEngine`, con sus pruebas de
conducta: una placa con letra confundible ya no llega al grafo sin confirmarse, y
un caso que queda completo cierra con su número dicho dígito a dígito. Se rompió
el cableado a propósito después, y las pruebas se caen.

## 3. Dos correcciones de diseño que aparecieron al cablear

**El cierre no puede armar el resumen.** `closing.build` recibía los valores del
caso para componer las tres frases. En la base esos valores están **sellados**,
así que armarlo en el canal de voz habría obligado a descifrar campos del caso
solo para leerlos en voz alta, y un segundo sitio que descifra es un segundo
sitio que puede dejar de redactar. El resumen ya lo arma el nodo de captura de
U11 con los valores en claro del grafo. `closing` se redujo a lo que de verdad es
de la voz: qué sigue, el número y la despedida. Las dos claves de resumen que
había escrito salieron del catálogo.

**Al conjunto de motivos de final le faltaba uno.** `call_session` nació con
cinco --colgar, silencio, duración agotada, corte y fallo-- y ninguno dice *el
reporte quedó completo y la agente cerró*. `hangup` es "la persona colgó", que no
es lo que pasa cuando la agente termina de leer el número y se despide;
`silence` dejaría el caso esperando al asegurado justo cuando ya no espera nada.
Un conjunto cerrado que no puede expresar un desenlace real no está protegiendo:
está escondiendo, y la fila acabaría diciendo algo que no ocurrió. Entra
`completed`, con su migración aditiva.

## 4. La pieza que llevaba una unidad entera sin llamador

`spell_for_readback` existía en U11 desde entonces, versionada, con su tabla de
veintiséis letras en dos idiomas y con sus pruebas. **No la llamaba nadie en
producción**: su único consumidor era su propio módulo de prueba.

Es la quinta vez que aparece esta forma en el proyecto, y esta vez no se abre
como defecto porque U16 es justo quien tenía que consumirla: AC1.23.2 la
necesita. Ahora tiene llamador.

## 5. Lo que faltaba en la tabla, y dónde se puso

AC1.23.2 dice "cuando un carácter está en **la lista versionada de letras
confundibles**". Esa lista no existía.

**Se añadió al mismo archivo de U11**, no a uno nuevo: `spelling_alphabet.yaml`
ya es la tabla de cómo suenan las letras, y una segunda tabla sobre lo mismo se
separa de la primera. El propio encabezado de ese archivo lo dice para el caso
del texto y la voz: *"Es la misma tabla para texto y voz, sin una segunda copia"*.

**Y el cargador la exige entera, con los dos idiomas.** Una tabla a la que le
faltara un idioma dejaría ese idioma sin lectura de confirmación y nadie lo
notaría, porque no falla: solo deja de proteger. Se comprobó quitando el inglés,
y el cargador se cae con su motivo.

## 6. Decisiones tomadas al escribir

1. **Se lee el código entero, no el carácter dudoso.** Leer solo la letra
   sospechosa de una placa no ayuda a nadie a comprobarla: quien escucha necesita
   oír la placa completa para reconocer la suya.
2. **El prefijo de la aseguradora no se deletrea, se dice su nombre.** "SUN, ese,
   u, ene, cuatro, ocho…" es peor que "Sunmeadow, cuatro, ocho…", y el criterio
   pide lo segundo.
3. **Que nunca se diga "oh" no lo comprueba el módulo del número**: los nombres
   de los dígitos salen de la tabla de U11, donde el cero se llama `zero` y
   `cero` y no hay otra forma. Un módulo que tradujera dígitos por su cuenta
   sería la segunda tabla que un día dice "oh".
4. **La interrupción mira la mejor palabra; "no le entendí" mira la peor.** No es
   una incoherencia: buscan cosas contrarias. La primera busca una señal clara de
   que alguien habló; la segunda, si se puede dar por bueno lo que se oyó entero.
   Está escrito en los dos módulos.
5. **Una interrupción que ya trae la corrección no responde "sí, dígame".**
   Decírselo a quien ya dijo lo que quería corregir es hacerle repetirlo.
6. **El cierre no termina preguntando.** El resumen de U11 cierra el bloque de
   captura pidiendo confirmación; este cierra la llamada. Son dos claves y no una.
7. **La confirmación del código la reconoce U11**, no un segundo reconocedor de
   síes: BR3.1 de aquella unidad exige un sí explícito, y una segunda lista
   empezaría a adivinar donde la regla pide certeza.

## 7. Lo que no se debilitó

Ninguna prueba existente se relajó ni se borró. Se **añadió** una exigencia al
cargador de la tabla de U11 —la lista completa en los dos idiomas—, que es más
estricto que antes, no menos. Ningún umbral, ningún piso, ninguna compuerta.

## 8. Formas del catálogo que se revisaron contra este diff

- **Forma 9, la regla que solo vive en el tipo** (la que apareció en la tanda 2).
  Se revisó si alguna regla de esta tanda se apoyaba solo en tipos: ninguna.
- **La que solo se comprueba en un idioma.** Todas las pruebas de deletreo,
  cierre y número van parametrizadas por idioma: la lista de confundibles y los
  nombres de los dígitos son distintos en cada uno, y una prueba en inglés no
  dice nada del español.
- **La aserción que no puede distinguir.** `test_el_prefijo_no_se_deletrea`
  cuenta las comas —la aseguradora y seis dígitos— además de mirar el contenido:
  sin ese conteo, un deletreo del prefijo también pasaría.

## 9. Estado

`mise run test:u16`: 183 pruebas en verde (132 unitarias, 51 de integración).
`mise run migrate:check`: sube, baja y vuelve a subir con la revisión nueva.
`mise run copy:check`, `mise run types`, `mise run lint`: en verde.
