# Hallazgos del recorrido de flujos y pantallas

Revisión del 2026-10-07. Cada hallazgo dice cómo se confirmó:

- **Producción:** lo vi pasar en cautelia.app.
- **Código:** se lee en el código, pero no lo reproduje.
- **No reproducido:** el código lo sugería, y en producción no pasó.

## A. Lo que rompe la promesa principal: preguntar por cobertura

| # | Hallazgo | Confirmado en |
| --- | --- | --- |
| A1 | Una pregunta de cobertura nunca recibe respuesta. «¿Mi póliza cubre el granizo?» pide nombre y póliza, confirma la póliza y pasa a «¿es correcto lo que tenemos registrado?». Del granizo no dice nada. | Producción |
| A2 | La frase de cierre de la consulta sale con huecos vacíos: «Para cerrar: ; su pregunta es . ¿Es correcto?». | Producción |
| A3 | El paso que propone qué cláusulas citar nunca se construyó. Aun si la consulta llegara a la búsqueda, el resultado sería siempre «no encuentro una cláusula». | Código |
| A4 | La consulta de cobertura nunca termina: no se deriva, no entra a la bandeja y repite el cierre para siempre. | Código |
| A5 | En la consulta se pregunta «¿Es usted y conducía ese carro?», que no tiene sentido cuando no hubo accidente. | Producción |
| A6 | Una pregunta de cobertura en medio de un reporte muestra «Déjeme revisar su póliza, un momento» y no llega nada más. El cuadro de texto queda bloqueado hasta recargar la página. | Código |
| A7 | Si en un reporte todavía no se identificó la póliza, una pregunta de cobertura da «No pude preparar esta respuesta. ¿Me lo puede repetir?», y repetirla da lo mismo. | Código |
| A8 | La vista «Comparar aseguradoras» mostraría «no encuentro cláusula» en las tres columnas, porque la primera respuesta de una consulta es pedir la póliza. | Código |
| A9 | El análisis dijo que confirmar la póliza con «sí» siempre daba error. | No reproducido: en producción la conversación siguió normal dos veces |

## B. Lo que pasa después de que se decide el caso

| # | Hallazgo | Confirmado en |
| --- | --- | --- |
| B1 | Cuando el ajustador decide, al chat no llega nada. El aviso «Le avisamos por aquí en cuanto haya una respuesta» existe y nadie lo envía. | Código |
| B2 | La página del caso del visitante dice «La conversación continúa con esta respuesta», y la conversación no continúa. | Código |
| B3 | Si la persona escribe después de la decisión: un reporte responde «ya quedó con un ajustador», como si no estuviera decidido, y una consulta o una cotización dan error. | Código |
| B4 | La frase de cierre dice «Puede verlo y decidirlo con el enlace de arriba». Para quien reportó, «decidirlo» contradice «queda con un ajustador». En la demo es cierto, porque el visitante puede jugar a ser el ajustador, pero nada lo explica antes. | Producción |
| B5 | La página del caso dice «el grafo no ha pausado» a un visitante. | Código |

## C. Otros tropiezos de conversación

| # | Hallazgo | Confirmado en |
| --- | --- | --- |
| C1 | Todo lo que no es saludo, cotización ni cobertura se abre como accidente. «Necesito ayuda», «¿qué es un deducible?» o «¿cómo va mi caso?» reciben «¿Hubo alguien herido?». | Código |
| C2 | Quien chocó y pregunta «¿me cubre?» en el primer mensaje abre una consulta, y su accidente no queda reportado. | Código |
| C3 | «¿Es usted y conducía ese carro?» no admite «soy el titular pero manejaba mi hijo»: se anota que conducía el titular. | Código |
| C4 | Con dos insultos, la agente repite para siempre la frase de calma y no avanza. La frase de cierre por insultos promete que el caso queda con un ajustador, y no se deriva. | Código |
| C5 | En la llamada, la pregunta inicial es «¿todos están bien?». Un «sí» se guarda como heridos «Sí», y el ajustador lo leería al revés. | Código |
| C6 | La llamada cuelga justo después de preguntar «¿Quiere agregar algo, o lo dejamos para el ajustador?». | Código |
| C7 | En la cotización se pregunta cuántos meses estuvo sin seguro aunque la persona acaba de decir que tiene seguro vigente. Palabras normales como «aproximadamente» disparan «esta demostración no calcula precios». | Código |
| C8 | Una cotización que el motor manda a un suscriptor nunca llega a la bandeja. | Código |
| C9 | La pantalla habla de tú y la agente de usted. | Producción |

## E. Lo que muestran las capturas de Miguel (cotización en Autos Poblado)

Todo confirmado en producción el 2026-10-07, caso SUN-465881.

| # | Lo que pasó | Por qué pasó |
| --- | --- | --- |
| E1 | «Dame una cotización» → «por ahora necesito registrar el reporte del accidente». Es falso: el caso sí se abrió como cotización (0 de 17 datos). | El prompt de redacción le dice al modelo que todo chat es un reporte de accidente, y no le dice de qué trata esta conversación. |
| E2 | Ante una fecha de nacimiento: «parece ser de hace muchos años y no tanto la del accidente». | La misma causa: el modelo cree que está en un accidente. |
| E3 | Al «en Itagüí» respondió «ya tengo anotado el lugar del accidente». | La misma causa. |
| E4 | «Desde el 2022, recién cumplidos los 18 años, ¿cuántos años es eso?» no recibió respuesta, y se anotaron 18 años de licencia en lugar de 4. | La extracción tomó el número que vio, nadie calcula, y el sistema no contesta preguntas de la persona: solo hace la siguiente pregunta de la lista. |
| E5 | «¿En qué estado se expidió la licencia?»: la pregunta está pensada para Estados Unidos y no tiene sentido para alguien en Colombia. | Las preguntas de cotización copian un formulario de EE. UU. |
| E6 | El nombre que escribió la persona aparece como «[NOMBRE 1]» en su propia burbuja. | Al recargar, el historial viene de la base, donde todo dato personal se guarda tapado. |
| E7 | La apertura es larga, y el saludo repite las mismas capacidades que la apertura acaba de decir. | El texto se armó para cumplir una lista de cinco cosas, y no para guiar. |
| E8 | La comprobación descartó 3 de 9 redacciones en esa conversación, y en esos turnos salió la frase fija. | Es el respaldo funcionando, pero confirma que el modelo trabaja sin contexto. |

**El fondo de todo:** el sistema clasifica por palabras clave, extrae datos con un
modelo gratuito lento que no razona, sigue una lista fija de preguntas y, desde hoy,
le pide a otro modelo que diga esa pregunta bonita sin contarle de qué va la
conversación. Nadie entiende la conversación entera. Por eso no responde preguntas,
no calcula, no se da cuenta de lo que la persona quiso decir y se equivoca de tema.

## D. Pantallas

| # | Hallazgo | Confirmado en |
| --- | --- | --- |
| D1 | Ninguna pantalla muestra qué cubre una póliza ni qué documentos consulta la agente. | Código |
| D2 | El inicio muestra «Póliza de ejemplo POL-100 042» sin decir para qué sirve. La instrucción solo aparece en «Cómo funciona». | Producción |
| D3 | «Comparar aseguradoras» existe y ningún enlace lleva a ella. | Código |
| D4 | La guía oculta los pasos del enlace del caso («ver y decidir tu caso»), aunque el chat sí entrega ese enlace. | Código |
| D5 | «Resultados» abre una página titulada «Cifras del sistema», técnica, que no explica qué significa cada cifra. | Producción |
| D6 | «Cómo se respondió» muestra nombres internos y no tiene botón para volver. | Código |
| D7 | Desde el chat o la llamada no hay botón para elegir otra aseguradora: solo el logo o la casita, que sale a la landing. | Producción |
| D8 | Bandeja y gasto responden «no encontramos lo que buscabas» sin decir que son solo para personal. | Código |
