# Cómo funciona Cautelia hoy

Escrito el 2026-10-07 a partir del código y de pruebas contra producción, no de los
documentos de diseño. Donde algo no se probó en producción, se dice.

## Las tres aseguradoras

Todo es inventado. Cada aseguradora tiene su propio carácter, su propio juego de pólizas
y sus propias cláusulas.

| Aseguradora | Carácter | Idioma por defecto | Póliza de ejemplo | Cotiza |
| --- | --- | --- | --- | --- |
| Seguros Aburrá | Un ajustador revisa todo caso | Español | POL-100042 | No |
| Autos Poblado | Cierra sola los reportes sencillos | Inglés | POL-200117 | Sí |
| Agencia Castilla | Agencia: no decide, pasa el caso a quien emitió la póliza | Inglés | POL-200341 (emitida por Autos Poblado) | No |

Cada una tiene 6 pólizas emitidas. Una póliza trae titular, vehículos, vigencia, y ocho
límites y deducibles: responsabilidad civil, gastos médicos, conductor sin seguro,
choque y otros daños.

**El visitante no crea pólizas.** Usa el número de ejemplo que la página le muestra.
Cuando lo escribe, la agente encuentra la póliza y le pregunta si es el titular. Si
escribe un número que no existe, la agente no confirma a nadie y sigue con lo que la
persona diga. Ninguna pantalla muestra hoy qué cubre cada póliza.

## Lo que la agente busca en las pólizas (RAG)

Cada aseguradora tiene sus documentos de póliza: el formulario base, el documento de
jurisdicción y cinco endosos. Hay 414 cláusulas en total, escritas desde cero con una
estructura inspirada en una póliza de autos estándar. Hay además una versión vieja de
cada formulario puesta a propósito como trampa para las evaluaciones.

Cómo funciona por dentro:

1. **Guardar.** Cada cláusula se convierte en un vector de números con el modelo de
   embeddings de Gemini y se guarda en la base de datos. Se hace a mano, con un comando;
   nunca solo.
2. **Buscar.** Ante una pregunta de cobertura, se buscan las 8 cláusulas más parecidas,
   solo entre las de la póliza de esa persona y sus endosos vigentes. Se combinan dos
   búsquedas, una por palabras y otra por significado.
3. **Verificar.** Cada cláusula que se cite pasa cuatro comprobaciones hechas con
   código: que se haya recuperado, que sea de esa aseguradora, que sea de esa póliza y
   que la póliza esté vigente. Si un endoso modifica la cláusula, también se exige citar
   el endoso.
4. **Responder.** Con citas verificadas, la agente muestra la cláusula. Sin ellas,
   dice que no encuentra una cláusula y no adivina. Nunca afirma que algo está
   cubierto: eso lo decide un ajustador.

**No se retroalimenta.** Las cláusulas cambian solo cuando alguien edita los archivos
fuente y vuelve a correr la carga. Las conversaciones no agregan documentos ni enseñan
nada a la búsqueda; quedan como registro de cada caso.

**Lo que hoy no funciona:** el paso que propone qué cláusulas citar nunca se construyó.
Por eso toda pregunta de cobertura termina en «no encuentro una cláusula», o ni
siquiera llega a responderse (ver `02-hallazgos.md`).

## Lo que pasa en una conversación de chat

1. La página muestra la apertura. Dice quién es Catalina, que es una demostración, que
   la conversación se borra cada noche, que no se escriban datos reales y qué sabe
   hacer.
2. El primer mensaje decide de qué se trata, con reglas de palabras y sin modelo:
   - si solo saluda, contesta «¿en qué le puedo ayudar?» y no abre caso;
   - si pide cotizar, y solo en Autos Poblado, se abre una cotización;
   - si dice «cobertura» o «cubre», se abre una consulta de cobertura;
   - cualquier otra cosa se abre como reporte de accidente.
3. **Reporte de accidente:** heridos, nombre y póliza, qué pasó, cuándo y dónde. Con eso
   el caso queda con un ajustador en el mismo turno. Ofrece agregar el vehículo y las
   otras personas, que son opcionales.
4. **Cotización:** 17 datos en cuatro bloques (conductor, vehículo, uso, historial),
   con una lectura de confirmación por bloque. Un motor de reglas dice si la solicitud
   sigue, no sigue o la revisa un suscriptor.
5. Lo que decide qué preguntar es siempre el código. Desde hoy, en el chat, Claude Haiku
   dice esa frase con naturalidad. Una comprobación con código y la guardia de salida
   revisan cada respuesta, y si algo falla sale la frase fija.
6. El caso lleva un enlace firmado de una hora («Ver mi caso»). En la demo, ese enlace
   deja al visitante ver su caso y decidirlo él mismo, como si fuera el ajustador.

## La llamada de voz

Misma lógica que el chat, por voz y solo para reportes de accidente. La apertura dice
quién habla y pregunta «¿todos están bien?». Transcribe con Deepgram, responde con la
voz de Cartesia y tiene un límite de llamadas por día. Las respuestas siguen siendo las
frases fijas del catálogo.

## Las otras pantallas

- **Inicio:** las tres aseguradoras, cada una con su póliza de ejemplo y los botones
  de chat y llamada.
- **Cómo funciona:** la guía de los pasos.
- **Resultados:** las cifras de las evaluaciones. Es técnica y no explica qué significa
  cada cifra.
- **Comparar aseguradoras:** hace la misma pregunta de cobertura a las tres a la vez.
  Existe, pero no hay ningún enlace hacia ella, y con la búsqueda rota mostraría «no
  encuentro cláusula» en las tres.
- **Bandeja del ajustador:** la cola de casos y la decisión. Solo entra quien tiene una
  credencial que se emite desde la terminal; no hay pantalla de ingreso.
- **Cómo se respondió:** la traza de un turno. Muestra nombres internos y no tiene
  botón para volver.
