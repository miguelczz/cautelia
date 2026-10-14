# Diseño: la conversación que convence en cinco minutos

Fecha: 2026-10-06. Pedido de Miguel: antes de cambiar la lógica del chat y de la
llamada, entender los flujos de hoy, ponerse en el lugar de quien recorre la
demostración y diseñar qué va a ver. Este documento es la versión para el
repositorio; la página con maquetas es el artefacto publicado el mismo día.

## 1. Los flujos de hoy, en sencillo

**Quién llega y a qué viene.** Quien evalúa el proyecto (una aseguradora, alguien
de selección) tiene cinco minutos. Quiere ver a la agente llevar un reporte con
criterio, ver el caso que produjo, decidirlo como lo haría un ajustador, y ver que
todo se mide. La demostración es bilingüe y todos los datos son sintéticos.

**El recorrido completo, pieza por pieza:**

1. **Landing** (`cautelia.app`): qué es y para quién. Botón al aplicativo.
2. **Inicio** (`/home`): tres aseguradoras ficticias, cada una con su póliza de
   ejemplo y su idioma por omisión (Stonecroft inglés, Sunmeadow inglés,
   Knotwell/«Agencia Castilla» inglés en la pantalla, español en la póliza).
   Botones «Abrir chat» y «Llamar». Abajo, «Comparar coberturas» entre las tres.
3. **Chat** (`/t/<aseguradora>/chat`): Catalina se presenta (divulgación de IA y
   de demostración), y la captura pide **siete datos** de un siniestro en un
   orden fijo: heridos, identidad y póliza, qué pasó, cuándo y dónde, vehículo y
   conductor, otras partes; tres de ellos (heridos, lugar, vehículo) se leen de
   vuelta para confirmarlos. Al final, un resumen y «¿está todo correcto?».
   Si la persona pregunta por cobertura a mitad, la agente responde citando la
   cláusula (con «Ver cómo se respondió», el resumen de traza). Si pide hablar
   con una persona, deriva el caso.
4. **Llamada** (`/t/<aseguradora>/call`): lo mismo por voz. Al colgar, «Dónde
   quedó su caso»: número y enlace al caso.
5. **Trabajo de fondo**, invisible: verificación de la póliza en el corpus,
   motor de reglas (la categoría del caso: cierre directo, revisión de
   ajustador, etc.), revisión de cumplimiento.
6. **Bandeja** (`/t/<aseguradora>/inbox`): el ajustador ve la cola, abre el caso,
   lo aprueba o rechaza con una nota. Necesita credencial de personal.
7. **Aviso al visitante**: la decisión del ajustador llega a la conversación
   («Un ajustador revisó su caso STO-000123 y lo aprobó…»).
8. **Mi caso** (`/c/...`): el visitante abre su propio caso con un enlace firmado
   de una hora y puede decidirlo él mismo, «como lo haría un ajustador».
9. **Resultados medidos** (`/metrics`): recuentos, latencias y completitud por
   aseguradora e idioma, siempre visible en la barra. **Gasto** (`/spend`): con
   clave de operador.

**Lo que traba el recorrido rápido hoy, verificado en el código:**

- Para ver el caso hay que terminar los siete datos (≈ 10 a 12 turnos con las
  confirmaciones). La portada del inicio promete «al terminar recibes un enlace a
  tu caso», pero **el chat nunca emite ese enlace**: solo la llamada lo hace al
  colgar (`voice_routes._desenlace`); en el chat el evento de derivación lleva el
  campo `case_link` vacío.
- La póliza de ejemplo vive en el inicio; para dársela a la agente hay que salir
  del chat, copiarla y volver.
- Si la persona da solo la póliza, la agente da la identidad por completa (el
  campo `identity_and_policy` es uno solo) y nunca pregunta el nombre: lo que vio
  Miguel.
- El idioma: la agente responde en el idioma por omisión de la aseguradora, y
  solo cambia cuando un mensaje trae cuatro o más palabras con señal clara
  (BR2.2, decisión medida). En Knotwell, «Hola» y «No, todos están bien» salieron
  contestados en inglés y la persona no sabe por qué.

## 2. El fallo de la llamada, diagnosticado

El ciclo de la llamada (`voice/loop.py`) sintetiza la apertura y la **envía** al
navegador en uno o dos segundos; el navegador la **reproduce** durante quince o
veinte. El reloj de silencio arranca cuando termina el envío
(`callo_a = self.now()` tras `_decir`), así que a los cinco segundos de empezar a
sonar la apertura la agente ya cree que la persona calló: «¿Sigue ahí?», la oferta
de guardar, la despedida, y cuelga. Es exactamente la secuencia de la captura.

**Corrección propuesta.** El servidor conoce el formato del audio (PCM de 16 bits,
24 000 Hz, mono: 48 000 bytes por segundo) y cuántos bytes mandó, así que puede
calcular cuándo termina de sonar cada frase: el reloj de silencio y el estado
«Escuchando» arrancan en ese instante estimado, no al terminar el envío. Una
interrupción (la persona habla encima) sigue cortando como hoy. Sin cuadro nuevo
en el protocolo y sin cambios en el navegador. Prueba: una apertura de veinte
segundos no produce ningún peldaño de silencio antes de los veinticinco.

## 3. Propuestas, para decidir

Cada una dice qué ve la persona, por qué, y qué toca de lo aprobado.

**P1. Reiniciar conversación.** Botón «Reiniciar» en la esquina superior derecha
del panel. Al pulsarlo, una confirmación en línea («¿Empezar de cero? Lo de ahora
queda guardado con su número de caso.») y la conversación nueva arranca con la
apertura. Por detrás: se cierra la sesión del navegador; el caso anterior queda y
lo borra el reinicio nocturno. No toca requisitos.

**P2. El idioma lo decide la pantalla.** La agente habla el idioma del selector
ES/EN de arriba, salvo que el mensaje diga claramente otro. Bajo el título del
panel: «Te respondo en español · cambia el idioma arriba». Por detrás: el chat
manda el idioma de la pantalla como respaldo (la vista de comparación ya lo
hace). Alternativa: fijar el idioma por aseguradora y decirlo. Recomendada: la
pantalla.

**P3. La póliza a un toque, y la agente sabe quién eres.** Cuando la agente pide
la póliza, aparece una ficha sobre el cuadro de texto: «Usar la póliza de ejemplo
POL-200341»; tocarla la envía. Y al recibir una póliza válida la agente busca al
titular en el corpus y confirma: «Encontré la póliza POL-200341 a nombre de
Natalia Henao Rendón, con un Renault Logan 2024. ¿Es usted y era ese el carro?».
Un «sí» confirma identidad y vehículo a la vez. Son datos sintéticos y las
pólizas de ejemplo son públicas por diseño (F8.7). Toca el orden de bloques
(vehículo se confirma con la identidad), que es un criterio aprobado (AC1.5.x):
se registra como decisión.

**P4. Dos ritmos: recorrido rápido y reporte completo.** La agente pide lo mínimo
para que un ajustador pueda ver el caso (heridos, póliza con titular, qué pasó,
cuándo y dónde: cuatro turnos) y ofrece el resto en una sola pregunta: «¿Quiere
agregar los datos de las otras personas, o lo dejamos para el ajustador?». Las
lecturas de confirmación de lugar y vehículo se funden en el resumen final. Toca
BR3.1/FD-U11-8 (lecturas por bloque) y la completitud publicada (siete campos):
es la propuesta más fuerte y la que más decide Miguel. Alternativa menor: dejar
los siete campos y solo quitar las lecturas intermedias.

**P5. El caso visible desde el chat.** En cuanto nace el caso, el panel muestra
«Caso STO-000123 · Ver mi caso» (enlace firmado de una hora, el mismo que da la
llamada), y al terminar la agente lo dice: «Su caso es STO-000123; un ajustador
lo revisa. Puede verlo y decidirlo aquí». Cumple la promesa del inicio y destraba
el recorrido rápido. No toca requisitos: el enlace existe, falta emitirlo.

**P6. La llamada espera a terminar de hablar** (sección 2). Corrección.

**P7. Lo que no entra todavía**, y conviene decidir después: variar las frases
de las preguntas, hablar de tú cuando te hablan de tú, nombre de pila en español.

## 4. Lo que vería la persona después (guion propuesto, Knotwell en español)

| Quién | Dice |
| --- | --- |
| Catalina | Hola, soy Catalina, la asistente de IA de Agencia Castilla. Es una demostración con pólizas de ejemplo; no escriba datos reales. Antes que nada, ¿hubo alguien herido? |
| Tú | No, todos bien. |
| Catalina | Anotado: nadie herido. ¿Cuál es el número de su póliza? _(ficha: Usar POL-200341)_ |
| Tú | POL-200341 |
| Catalina | Encontré la póliza POL-200341 a nombre de Natalia Henao Rendón, con un Renault Logan 2024. ¿Es usted y era ese el carro? |
| Tú | Sí |
| Catalina | Gracias. Cuénteme qué pasó. |
| Tú | Me chocaron por detrás en un semáforo. |
| Catalina | Anotado. ¿Cuándo y dónde fue? |
| Tú | Ayer a las 3, en la 80 con 26. |
| Catalina | Listo: su caso es KNO-000124 y un ajustador lo revisa. Puede verlo y decidirlo aquí: _Ver mi caso_. ¿Quiere agregar los datos de las otras personas, o lo dejamos para el ajustador? |

Seis turnos de la persona en vez de diez o doce, y el caso visible desde el
tercero.
