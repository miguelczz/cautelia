# Correcciones del 2026-11-11

Miguel probó el ajustador de IA en producción y pidió cuatro arreglos. Estado: en `main`, sin publicar.

| # | Problema visto | Causa | Arreglo |
| --- | --- | --- | --- |
| 1 | Lo hablado con la agente antes de reportar el accidente no aparecía al recargar ni al volver a la conversación | Sin caso no hay transcripción: ese intercambio vivía solo en la memoria del proceso, con tope de 8 líneas | Tabla `chat_session_message` (migración `u25_chat_0001`), con aislamiento por aseguradora, la marca de dato de visitante y borrado por cascada con su conversación. `history.load` la devuelve primero y después los turnos del caso. Tope de 40 mensajes por conversación (se conservan los primeros) |
| 2 | Al pedir nombre y póliza no salía el botón de la póliza de ejemplo | La lista de datos del reporte y la repregunta tras decir «no soy yo» no lo ofrecían | `suggestions.asks_for_identity`: el botón sale cuando la lista incluye la línea de la identidad y en `intake.policy.declined` |
| 3 | El ajustador escribía respuestas muy largas, y «hace 20 minutos» quedaba sin hora | El prompt pedía «pocas frases» sin tope y el paso «Lee la póliza» volcaba deducibles, límites y condiciones; al modelo solo le llegaba la fecha de hoy, sin hora | Explicación de 2 o 3 frases (unas 60 palabras) y hasta 3 razones; tope de seguridad de 900 caracteres en el esquema; el paso de la póliza solo dice vigencia, vehículos y conductores. El modelo recibe fecha y hora de Colombia (`America/Bogota`), lo que además evita que después de las 7 p. m. «hoy» sea mañana |
| 4 | El enlace a Langfuse abría una página sin nada | La traza pública no lleva los textos de la conversación; solo pasos, tiempos y costo | Se quita el enlace de la página del caso y del panel de gasto (el de la última conversación ya se había quitado el 2026-11-02) y el texto del README. También se arregla el costo que se veía como `0E-12 USD` |

Sin correr: la evaluación `entender` con el modelo (necesita la base levantada) ni las pruebas de integración de la tabla nueva (las corre GitHub).
