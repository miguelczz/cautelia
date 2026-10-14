# Requisitos — Untangle

Convierte el alcance aprobado en enunciados verificables, cada uno con criterio
de aprobado o fallido. No re-descubre el producto: el PRD v1.1
(`docs/specs/prd.md`) ya fija los quince módulos, los veintiún Must, los doce
principios y las métricas con sus umbrales. Lo que aquí se añade es la forma
comprobable, más las siete decisiones de la entrevista de esta etapa
(`requirements-analysis-questions.md`) y su seguimiento.

Los identificadores `FR{n}`, `FR{n}.{m}` y `NFR{n}` son claves permanentes de
trazabilidad: las etapas siguientes las conservan tal cual, sin renumerar ni
sustituir por prosa.

**Insumos consumidos.** El mapa del código existente
(`aidlc/spaces/default/codekb/untangle/business-overview.md`,
`architecture.md`, `code-structure.md`) estableció que el aplicativo no tiene
código y que la landing de `site/` queda fuera de su alcance; las prácticas
afirmadas (`../practices-discovery/team-practices.md`, ya promovidas a la
memoria del espacio) fijan cómo se verifica todo lo que sigue.

## Análisis de intención

Miguel construye evidencia contratable, no un producto de seguros. El objetivo
real es que un ingeniero senior que evalúa su candidatura pueda **comprobar por
sí mismo**, en treinta minutos y sin confiar en nadie, que sabe construir
sistemas de agentes de producción. El dominio de seguros de auto existe para dar
un problema real donde la evidencia sea observable.

De ahí tres consecuencias que gobiernan todos los requisitos:

- **Verificable le gana a impresionante.** Una métrica publicada con su comando
  vale más que una demostración pulida. Cada afirmación del README debe tener un
  artefacto que la respalde.
- **Lo que no se puede tocar, no cuenta.** Por eso el chat, la bandeja y la voz
  se publican en vivo (D-018): un componente central mostrado solo en video es
  la promesa de una evidencia, no la evidencia.
- **Fallar en público es parte del producto.** Los fallos publicados, la
  degradación honesta y el "no encuentro cláusula" son características, no
  defectos que ocultar.

Como el mapa del código estableció, no hay nada que preservar: cada requisito se
construye desde cero, con su andamiaje en el mismo commit.

## Requisitos funcionales

Organizados por módulo del PRD 9.4. El origen cita el Must, el principio o la
respuesta de la entrevista que lo justifica.

### FR1 — Caso estructurado (MOD-01)

| ID | Requisito | Criterio de aprobado o fallido | Origen |
| --- | --- | --- | --- |
| FR1.1 | El sistema registra un caso con los siete campos centrales: identidad y póliza, fecha y hora, lugar, descripción, vehículo y conductor, otras partes, lesiones | El esquema valida un caso de ejemplo con los siete campos; un caso sin alguno falla la validación | M1 |
| FR1.2 | El caso admite grupos repetibles: lesionados, testigos, otras partes y vehículos | Un caso con dos lesionados y dos terceros valida y se recupera íntegro | M1 |
| FR1.3 | El sistema calcula completitud por campo y total, y marca cada bloque confirmado en voz alta | La completitud de un caso con cinco de siete campos es exactamente 5/7; el bloque sin confirmación no cuenta como confirmado | M1, P11 |
| FR1.4 | El caso transita entre estados: abierto, en captura, en verificación, en decisión, derivado, esperando al asegurado, cerrado | Toda transición no declarada es rechazada por el modelo de estado | M1, M16 |
| FR1.5 | Cada caso lleva un número legible con prefijo de la aseguradora y seis dígitos, que la agente dicta dígito a dígito | El número generado casa con el patrón; la transcripción del cierre contiene los seis dígitos separados | M1 |
| FR1.6 | El caso guarda su historial de cambios: qué cambió, quién, cuándo y desde qué canal | Una corrección del ajustador aparece en el historial con su autor y su marca de tiempo | M11 |
| FR1.7 | El caso adjunta transcripción, cláusulas citadas con identificador y versión, reglas disparadas con sus insumos, identificador de traza y resultado de los controles | Un caso derivado expone los cinco adjuntos; falta cualquiera y el caso no se puede cerrar | M11 |

### FR2 — Orquestación sobre el grafo (MOD-02)

| ID | Requisito | Criterio de aprobado o fallido | Origen |
| --- | --- | --- | --- |
| FR2.1 | El grafo tiene cuatro nodos con contrato de entrada y salida: Intake, Policy Verification, Decision, Compliance | Cada nodo tiene su contrato declarado y una prueba que lo verifica | M2, P3 |
| FR2.2 | El orquestador es código con rutas explícitas; la decisión de transición no la toma un modelo | La función de transición es pura, con enumeración cerrada, y el núcleo no importa el cliente de ningún proveedor | P3 |
| FR2.3 | El grafo distingue dos ritmos: el turno conversacional responde de inmediato; la verificación y las reglas trabajan de fondo con precarga | El turno nunca espera al trabajo de fondo; cuando lo necesita, emite una frase de espera antes de dos segundos de silencio | M12, P4 |
| FR2.4 | El grafo persiste un punto de control por caso después de cada turno | Matar el proceso a mitad de conversación y reanudar recupera el caso sin repetir preguntas ya confirmadas | M16 |
| FR2.5 | Compliance pausa el grafo hacia la bandeja y la decisión humana lo reanuda | Un caso derivado queda pausado; aprobar en la bandeja lo reanuda y lo cierra | M2, M11 |
| FR2.6 | El mismo grafo atiende voz y chat; el canal es un adaptador, no una ruta distinta | El mismo caso de prueba produce el mismo registro por los dos canales | M10, M12, P12 |
| FR2.7 | Cada nodo declara su política de fallo: tiempo máximo, un reintento y degradación honesta | Al forzar el fallo de la verificación, la agente dice que no puede verificar y deriva, sin inventar cobertura | M2 |

### FR3 — Canal de voz (MOD-03)

| ID | Requisito | Criterio de aprobado o fallido | Origen |
| --- | --- | --- | --- |
| FR3.1 | La llamada entra por el navegador, en inglés y en español, con la misma voz | Una llamada de prueba completa en cada idioma produce un caso válido | M12, M14, D-009 |
| FR3.2 | La primera frase declara que es inteligencia artificial y que la llamada se graba, en el idioma de la llamada | El caso registra la divulgación con su hora y su idioma; sin ella el caso no se puede cerrar | M6, P6 |
| FR3.3 | El asegurado cambia de idioma a mitad de llamada diciéndolo, y la agente sigue con la misma voz | La petición se atiende en el turno siguiente, sin reiniciar la llamada ni perder el caso | P12 |
| FR3.4 | La agente cede el turno cuando el asegurado la interrumpe y retoma sin repetir | En las grabaciones con interrupción marcada, la agente calla y no vuelve a leer lo ya dicho | M12, M13 |
| FR3.5 | Ante silencio del asegurado, la agente pregunta si sigue ahí y, al segundo silencio, ofrece devolver la llamada o pasar a una persona | Los casos de silencio del conjunto de audio producen ambas frases en orden | M12 |
| FR3.6 | Si la llamada se corta, el caso queda esperando al asegurado y se retoma al volver a llamar | Cortar a mitad y volver a llamar reanuda desde el último bloque confirmado | M16 |
| FR3.7 | El proveedor de síntesis de voz está detrás de una sola interfaz; proveedor, voz, modelo y límites viven en configuración | Cambiar de proveedor es editar configuración y desplegar; ningún archivo de lógica cambia en ese commit | M21, D-018 |
| FR3.8 | Agotado el presupuesto de la voz paisa, el sistema cambia solo a la voz de respaldo gratuita y sigue atendiendo, avisando al visitante | Al agotar el presupuesto en pruebas, la llamada siguiente se atiende con la voz de respaldo y el aviso aparece | Q2, M21 |
| FR3.9 | El enlace público de voz aplica límites: 3 minutos por llamada, 1 llamada por visitante al día, y un cupo diario del sitio **derivado del presupuesto que queda y los días que faltan**, con un tope máximo de 15 (enmienda del 2026-09-19) | Superar cualquiera devuelve un rechazo honesto; el cupo diario se recalcula cada día y nunca supera el tope; con el presupuesto a la mitad y la ventana a la mitad, el cupo permite llegar al día 90 | Q1, M21, NFR15 |
| FR3.11 | El presupuesto de voz reserva una porción intocable para grabar el video final y para la sesión de escucha, que el enlace público no puede consumir (enmienda del 2026-09-19) | Con el cupo público agotado, una llamada marcada como grabación sigue atendiéndose hasta agotar su reserva | NFR15, M18 |
| FR3.10 | Los límites están configurados también en el proveedor, no solo en la aplicación | Con la aplicación detenida, el proveedor sigue rechazando por encima de su propio tope | Q1, prácticas de despliegue |

### FR4 — Chat web (MOD-04)

| ID | Requisito | Criterio de aprobado o fallido | Origen |
| --- | --- | --- | --- |
| FR4.1 | Cada aseguradora tiene su página pública de chat, con la divulgación de inteligencia artificial en el primer mensaje | Las tres páginas cargan y el primer mensaje contiene la divulgación | M10, M6 |
| FR4.2 | El chat atiende tanto el primer aviso de siniestro como preguntas de cobertura, sobre el mismo grafo | Ambos flujos producen registro y traza desde el chat | M10 |
| FR4.3 | Cada cita se muestra con su identificador y el texto completo expandible, con enlace a la traza | Toda respuesta de cobertura del conjunto de prueba muestra identificador y texto | M4, M10 |
| FR4.4 | El chat responde en el idioma del mensaje, con selector visible | Un mensaje en español recibe respuesta en español sin tocar el selector | P12 |
| FR4.5 | El chat declara en el primer mensaje que es una demostración con pólizas de ejemplo | El texto aparece antes de cualquier pregunta del visitante | P7, prácticas de despliegue |
| FR4.6 | El chat aplica límite de mensajes por sesión y por día, con modo degradado honesto al alcanzar el tope | Superar el límite devuelve un mensaje claro, no un error genérico | M20, RT-13 |

### FR5 — Corpus y verificación de cobertura (MOD-05)

| ID | Requisito | Criterio de aprobado o fallido | Origen |
| --- | --- | --- | --- |
| FR5.1 | Cada aseguradora tiene su corpus: formulario base con la estructura de una póliza de auto personal, endosos, documento de jurisdicción y distractores | Los tres corpus existen, con al menos cuatro endosos y distractores declarados cada uno | M3 |
| FR5.2 | Cada cláusula tiene identificador estable y versión; la póliza emitida referencia formulario, versión y endosos vigentes | Toda cláusula del corpus tiene identificador único; una póliza sin versión falla la validación | M3, M4 |
| FR5.3 | La recuperación está filtrada por aseguradora y por póliza | Una consulta con la aseguradora equivocada no devuelve ninguna cláusula ajena | M4, M9 |
| FR5.4 | El sistema solo cita identificadores efectivamente recuperados, y verifica antes de emitir que existan, pertenezcan a esa póliza, estén vigentes, no los modifique un endoso vigente que la respuesta ignora (enmienda del 2026-09-17) y sostengan la afirmación | Cero citas inexistentes en el conjunto de citación; una cita inventada bloquea la entrega | M4, P2 |
| FR5.5 | "No encuentro una cláusula que lo cubra" es una salida válida, contada y evaluada, distinta de "no pude verificar" | Los dos resultados tienen valores distintos en el registro y en las métricas | M4, P2 |
| FR5.6 | La explicación muestra la cláusula completa en el chat y, en voz, el nombre de la parte más un resumen de una frase | Ambas formas aparecen en sus conjuntos de prueba respectivos | M4 |

### FR6 — Motor de reglas por aseguradora (MOD-06)

| ID | Requisito | Criterio de aprobado o fallido | Origen |
| --- | --- | --- | --- |
| FR6.1 | Cada aseguradora tiene entre diez y veinte reglas de triage versionadas, con prueba unitaria por regla | El recuento está en rango y cada regla tiene su prueba | M5 |
| FR6.2 | La salida es una categoría (cierre directo, revisión estándar, derivación) con las reglas disparadas, sus insumos y una explicación legible | Ningún caso produce categoría sin la regla que la justifica | M5, P1 |
| FR6.3 | Ningún puntaje de riesgo lo produce el modelo; la categoría la deciden las reglas | El código de decisión no invoca al modelo | P1, P3 |
| FR6.4 | La agencia deriva siempre, por regla y no por una rama de código escrita para ella | La política vive en su archivo de configuración; no existe ninguna condición por aseguradora dentro del código de decisión | M5, F9.6 |
| FR6.5 | Un cambio de reglas dispara el conjunto de evaluación antes de desplegarse | La tubería corre las evaluaciones cuando cambian los archivos de reglas | M8 |

### FR7 — Controles de cumplimiento (MOD-07)

| ID | Requisito | Criterio de aprobado o fallido | Origen |
| --- | --- | --- | --- |
| FR7.1 | La divulgación queda registrada en el caso con hora, idioma y canal | Sin ese registro el caso no se cierra | M6 |
| FR7.2 | La petición de hablar con una persona se atiende en cualquier turno y en cualquier idioma | Los casos adversariales de petición de persona derivan en el turno siguiente, sin excepción | M6, RT-3 |
| FR7.3 | Los datos personales se redactan antes de persistir y antes de exportar, en un punto único de salida | Un segundo detector, de mecanismo distinto al primero, no encuentra nada en las trazas exportadas | M6, RT-14, prácticas de despliegue |
| FR7.4 | Cada caso es explicable: qué se preguntó, qué se citó, qué regla se disparó, quién decidió y cuándo | La vista de caso muestra los cinco elementos | M6, P6 |
| FR7.5 | Una guardia por turno detecta promesas de cobertura, montos, culpa y consejo legal antes de emitir el texto | Cero respuestas fuera de alcance en los conjuntos de evaluación | M6, P1 |
| FR7.6 | El camino de degradación no puede ser una salida al asegurado que esquive esa guardia | Todo texto emitido al asegurado pasa por el mismo punto, incluido el de degradación | M6, prácticas |
| FR7.7 | Al cierre se ejecuta la revisión completa de los cuatro controles sobre la conversación entera, y su resultado se adjunta | Un caso sin resultado de esa revisión no se puede cerrar | M6 |

### FR8 — Bandeja del ajustador (MOD-08)

| ID | Requisito | Criterio de aprobado o fallido | Origen |
| --- | --- | --- | --- |
| FR8.1 | La bandeja lista los casos de su aseguradora, con filtros por estado, canal, idioma y prioridad | Un ajustador no ve ningún caso de otra aseguradora | M11, M9 |
| FR8.2 | La vista de caso muestra completitud por campo, transcripción, cláusulas expandibles, regla con sus insumos, resultado de los controles y traza con costo y latencia | Los seis bloques están presentes en un caso derivado | M11 |
| FR8.3 | El ajustador corrige un campo y la corrección queda registrada con autor y momento | La corrección aparece en el historial del caso | M11 |
| FR8.4 | Aprobar o rechazar exige comentario y reanuda el grafo desde su punto de control | Aprobar sin comentario es rechazado; aprobar con comentario cierra el caso | M11, P1 |
| FR8.5 | El asegurado recibe la actualización por el canal en que estaba | En el chat aparece el mensaje; al volver a llamar, la agente resume la decisión | M11 |
| FR8.6 | Los casos incompletos se ven con lo capturado y su punto de reanudación | Un caso cortado aparece en la bandeja con su último bloque confirmado | M16 |
| FR8.7 | Un visitante que crea su caso en el enlace público recibe un enlace firmado de una hora, ligado solo a ese caso, para entrar a la bandeja y aprobarlo | El enlace caduca a la hora; usado contra otro caso, no da acceso | Q5, Q6 |
| FR8.9 | Esa vista declara en pantalla, antes de cualquier acción, que se está mostrando la vista del ajustador como recurso de la demostración y que en la operación real esa firma es de otra persona (enmienda del 2026-09-19) | El texto aparece en la vista por enlace firmado y sale del catálogo, en los dos idiomas | P1, P7, M11 |
| FR8.8 | Los datos de demostración se reinician cada noche | Tras el reinicio, la bandeja pública queda sin casos de visitantes | Q4, Q5, prácticas |

### FR9 — Aseguradoras e identidad (MOD-09)

| ID | Requisito | Criterio de aprobado o fallido | Origen |
| --- | --- | --- | --- |
| FR9.1 | Toda tabla lleva el identificador de aseguradora con política de aislamiento en la base de datos, no solo en el código | Una aserción de esquema falla si alguna tabla del aplicativo carece de la política | M9, R8 |
| FR9.2 | La sesión de base de datos fija la aseguradora en un punto único de entrada | No existe ninguna apertura de conexión fuera de ese punto | M9, prácticas de estilo |
| FR9.3 | La configuración por aseguradora vive en archivos versionados: nombre, idioma, voz, reglas, políticas, corpus, póliza de ejemplo y personas | Añadir una cuarta aseguradora no requiere cambiar código | M9 |
| FR9.4 | Las pruebas de aislamiento corren en cada entrega: consulta cruzada vacía, recuperación sin cláusulas ajenas, credencial ajena sin acceso a la bandeja | Las tres pasan; cualquiera en rojo bloquea la entrega | M9 |
| FR9.5 | Las tres aseguradoras sintéticas son Stonecroft Mutual, Sunmeadow Auto y Knotwell Insurance Agency, en la jurisdicción ficticia del Estado de Corvane | Los nombres aparecen así en corpus, bandeja y conjuntos de evaluación | PRD 9.1, Q7 |
| FR9.6 | Las personas de la bandeja son Diana en Stonecroft, Marcus Webb en Sunmeadow y Priya Raman en Knotwell | Los tres nombres están en la configuración y en los conjuntos de evaluación | Q7 |

### FR10 — Telemetría y costo (MOD-10)

| ID | Requisito | Criterio de aprobado o fallido | Origen |
| --- | --- | --- | --- |
| FR10.1 | Cada turno, nodo y llamada a proveedor emite una traza con modelo, tokens, latencia y costo | Un caso completo produce trazas en los tres niveles | M7 |
| FR10.2 | El canal de voz emite los eventos de latencia: fin del habla, primer audio, parada por interrupción y recuperación tras corte | Las cuatro marcas existen en la traza de una llamada | M13, M15 |
| FR10.3 | El sistema acumula costo por caso, por proveedor y por mes | El panel muestra las tres agregaciones | M20, D-018 |
| FR10.4 | Al alcanzar la alerta se avisa; al alcanzar el techo, la voz rechaza llamadas nuevas con mensaje honesto y el chat sigue vivo | Forzando el techo en pruebas, la voz rechaza y el chat responde | M20, Q3 |
| FR10.5 | Un panel resumen publica las cinco cifras del video: completitud, precisión de citación, latencias por idioma, costo por caso y casos por aseguradora | Las cinco aparecen con su fecha y su commit | M7, M18 |

### FR11 — Evaluación (MOD-11)

| ID | Requisito | Criterio de aprobado o fallido | Origen |
| --- | --- | --- | --- |
| FR11.1 | Existen los ocho conjuntos de datos del plan de evaluación, versionados como archivos por caso con identificador estable | Los ocho existen con su recuento declarado | M8, PRD 11.1 |
| FR11.2 | El generador de conjuntos es determinista y sembrado, con su salida versionada | Dos corridas con la misma semilla producen bytes idénticos | M3, prácticas de pruebas |
| FR11.3 | Un solo comando corre la evaluación y produce el reporte con aprobados, fallidos, causa raíz por caso y diferencia contra la línea base | El comando está en el archivo de tareas y en el README | M8, M17 |
| FR11.4 | Las compuertas duras son pasa o falla por caso: citas inexistentes, respuestas fuera de alcance, datos personales en trazas y aislamiento | Una sola falla bloquea la entrega, sin promedio que la disimule | M8, P5 |
| FR11.5 | En los conjuntos pequeños la regresión se cuenta por casos: cualquier caso que pase a fallar bloquea y exige explicación que nombre los identificadores | Una explicación sin identificadores no cuenta como explicación | Prácticas de pruebas |
| FR11.6 | El reporte publica los dos idiomas lado a lado, nunca un promedio combinado | El reporte no contiene ninguna cifra que mezcle idiomas | P12 |
| FR11.7 | Los conjuntos de audio corren por hito, no en cada entrega | La tubería de cada entrega no los invoca | M13, M15 |
| FR11.8 | El README publica la sección de cómo falla el sistema, generada desde el último reporte | La sección existe y cita el commit del reporte | M17, P5 |

### FR12 — Generador de datos sintéticos (MOD-12)

| ID | Requisito | Criterio de aprobado o fallido | Origen |
| --- | --- | --- | --- |
| FR12.1 | El generador produce pólizas, endosos, distractores, clientes, vehículos y casos para las tres aseguradoras | Un comando regenera todo el conjunto de datos | M3 |
| FR12.2 | Ningún texto proviene de formularios de terceros: la estructura se imita, el texto es propio | Un chequeo de contenido, con su alcance de rutas y exclusiones declarado, no encuentra texto de terceros | M3, P8 |
| FR12.3 | Los datos con forma de dato personal son ficticios y aun así se redactan en trazas | La comprobación de FR7.3 aplica también a los datos generados | P8, M6 |

### FR13 — Cotización con elegibilidad (MOD-13, Should)

| ID | Requisito | Criterio de aprobado o fallido | Origen |
| --- | --- | --- | --- |
| FR13.1 | La captura de la solicitud reutiliza los mismos nodos, sin añadir ninguno | El grafo no gana nodos al soportar cotización | S1 |
| FR13.2 | La salida es elegible, no elegible o derivación al suscriptor, más una banda indicativa sin cifra en moneda | Ninguna respuesta contiene un importe | D-012, S1 |

### FR14 — Evidencia pública (MOD-15)

| ID | Requisito | Criterio de aprobado o fallido | Origen |
| --- | --- | --- | --- |
| FR14.1 | El README declara lo que hace, lo que no hace y cómo falla, con arquitectura, diagrama del grafo, decisiones de arquitectura, tabla de principio a control a evidencia, reporte de evaluación, atribuciones y un comando único | Las ocho piezas están presentes | M17 |
| FR14.2 | El video de tres a cinco minutos muestra la llamada, el panel, la vista de caso con la cláusula citada y la bandeja | Las cuatro escenas aparecen | M18 |
| FR14.3 | La landing se realinea al producto real y enlaza los tres entregables | Ninguna afirmación de la landing contradice el README | M19, D-013 |
| FR14.4 | Ningún texto público promete una capacidad que no está construida | Cada promesa tiene su artefacto | P7, prácticas |

## Requisitos no funcionales

Cada uno lleva su valor esperado y cómo se obtiene el valor real. Por la
práctica afirmada, todos se registran además como objetivo medible en la etapa
de requisitos no funcionales de Construcción, con identificador estable, valor
esperado y comando, para que lleguen a la matriz de verificación.

| ID | Requisito | Valor esperado | Cómo se mide |
| --- | --- | --- | --- |
| NFR1 | Latencia de turno de voz, del fin del habla al primer audio, por idioma | p50 menor que 500 ms, p95 menor que 800 ms | Eventos de FR10.2 sobre las veinte grabaciones |
| NFR2 | Latencia de parada ante interrupción | Menor que 300 ms | Eventos de FR10.2, casos con interrupción marcada |
| NFR3 | Recuperación tras interrupción sin perder estado | Mayor que 90 % | Conjunto de audio, casos con interrupción |
| NFR4 | Latencia de respuesta del chat, del envío a la primera palabra | p95 menor que 3 s | Trazas del chat |
| NFR5 | Precisión de citación: la cláusula existe, pertenece a esa póliza y sostiene la afirmación | Mayor o igual a 95 % | Conjunto de citación, cuarenta preguntas con distractores |
| NFR6 | Citas inexistentes | Exactamente 0 | Verificador determinista; compuerta dura |
| NFR7 | Completitud del primer aviso de siniestro en los siete campos | Mayor o igual a 95 % | Conjuntos de texto y de audio |
| NFR8 | Exactitud de extracción por campo, tras normalizar fechas, placas y números | Mayor o igual a 95 % por campo | Conjunto de texto |
| NFR9 | Respuestas fuera de alcance | Exactamente 0 | Detector más revisión manual de la muestra; compuerta dura |
| NFR10 | Fuga entre aseguradoras | Exactamente 0 cláusulas ajenas y 100 % de pruebas de aislamiento en verde | FR9.4; compuerta dura |
| NFR11 | Datos personales en trazas, logs y exportaciones | Exactamente 0 hallazgos | Segundo detector, de mecanismo distinto al primero; compuerta dura |
| NFR12 | Resistencia adversarial: los quince escenarios de red-team | 0 respuestas que obedezcan una instrucción inyectada | Conjunto adversarial |
| NFR13 | Derivaciones correctas, y derivaciones innecesarias | 100 % correctas; menos o igual a 10 % innecesarias | Conjunto de texto |
| NFR14 | Costo por caso exitoso | Publicado por versión; voz menor o igual a 0,02 USD por llamada de cuatro minutos | Trazas de FR10.3 |
| NFR15 | Gasto acumulado del proyecto | Menor o igual a 5 USD en noventa días, con alerta en 3 USD | FR10.3; revisión en el día 30 |
| NFR16 | Disponibilidad mensual del enlace en vivo | Mayor o igual a 95 % | Ping periódico del checklist del segundo día |
| NFR17 | Duración de la corrida de evaluación de texto | Menor o igual a 10 minutos | Tiempo del trabajo en la tubería |
| NFR18 | Cobertura de líneas del aplicativo | Mayor o igual a 80 % agregado, y mayor o igual a 80 % en motor de reglas, verificador de citas, aislamiento, esquema del caso y redacción de datos personales | Comando de cobertura con su lista de exclusión declarada |
| NFR19 | Retención de datos de la demostración pública | Audio: no se persiste. Transcripción redactada: borrada en el reinicio nocturno | Inspección del almacenamiento tras el reinicio |
| NFR20 | Paridad por idioma: mismas metas en español e inglés | Sin excepción ni meta reducida para el español | Reporte con los dos idiomas lado a lado |
| NFR21 | Tiempo desde clonar el repositorio hasta ver el reporte de evaluación | Menor que 15 minutos en máquina limpia | Cronómetro en máquina limpia |

## Restricciones

| ID | Restricción | Origen |
| --- | --- | --- |
| C1 | Presupuesto de 5 USD en noventa días para proveedores de pago, con alerta en 3 USD; todo lo demás en tier gratuito o auto-hospedado | D-015, P9 |
| C2 | Equipo de una persona, noventa días, con las fechas del plan de entrega | PRD 13 |
| C3 | Datos cien por ciento sintéticos; ningún texto de formularios de terceros | P8, M3 |
| C4 | Jurisdicción ficticia; nunca se cita una ley real ni se afirma cumplimiento certificado | P6, PRD 9.1 |
| C5 | Un solo producto, seguro de auto personal: el primer aviso de siniestro es el camino pulido y la cotización el flujo delgado | D-007 |
| C6 | La landing de `site/` queda fuera del alcance del aplicativo hasta su realineación | D-005, D-013 |
| C7 | Los commits entran directo a la rama principal y la tubería de GitHub Actions es la compuerta | Prácticas de forma de trabajar |
| C8 | El lenguaje del aplicativo, y con él su formatter, linter y comprobador de tipos, lo fija una decisión de arquitectura posterior | Prácticas de estilo |
| C9 | Todo texto que una persona lee se escribe en español; código, identificadores y rutas en inglés | Memoria del proyecto |

## Supuestos

| ID | Supuesto | Por qué se cree | Cuándo se valida | Si es falso |
| --- | --- | --- | --- | --- |
| A1 | Existe hospedaje gratuito capaz de sostener una llamada de voz por el navegador sin dormirse | Los proveedores de transporte de voz publican tiers gratuitos | Spike de la semana 1 | El enlace de voz cae por razón técnica, no presupuestal; se decide de nuevo con datos |
| A2 | Gemini 2.5 Flash-Lite da latencia y extracción suficientes para el turno conversacional | Referencias de terceros | Spike de la semana 1 | Sube solo el nodo que falle, dentro del tope |
| A3 | Existe una voz femenina paisa utilizable por interfaz de programación en algún proveedor | Cinco voces de Medellín halladas en biblioteca | Prueba ciega, semana 1 o 6 | Plan B latinoamericano neutro, o clonado con consentimiento |
| A4 | El crédito gratuito de transcripción cubre el proyecto completo | Crédito de 200 USD frente al volumen previsto | Continuo, con el costo por proveedor | Se mide y se decide con el gasto real |
| A5 | El tráfico real del enlace queda muy por debajo de su cupo diario | Un enlace de portafolio recibe visitas esporádicas | Continuo, desde el día de publicación | **Ya no se asume:** con el cupo derivado de FR3.9, un día de tráfico alto reduce el cupo de los días siguientes en vez de adelantar el corte. La proyección anterior —"el techo corta hacia el día 67"— era el problema, no el plan: dejaba la voz apagada antes del video final de la semana 11 y de la publicación de la semana 12 |
| A6 | Los evaluadores premian las evaluaciones publicadas y los fallos a la vista | Guías de portafolio, no un estudio | Validación del día 30 | Se ajusta el README, no el sistema |

## Fuera de alcance

Integración con una aseguradora o un sistema de siniestros real; tarifas o
precios actuariales; afirmaciones de cumplimiento certificado; otros productos
de seguro; cualquier decisión de cobertura o dinero tomada por la inteligencia
artificial; datos de personas reales; modelo de negocio o facturación;
aplicación móvil nativa; voces distintas por idioma; traspaso real de un caso
entre aseguradoras; documentos al caso; identidad federada; interfaz de
administración; y la tubería de despliegue con el aprovisionamiento de entornos,
que pertenece a un segundo trabajo de infraestructura.

## Preguntas abiertas

| ID | Pregunta | Quién la resuelve |
| --- | --- | --- |
| OQ1 | Analítica de la landing: ninguna, la del proveedor de hospedaje en su tier gratuito, o una auto-hospedada | Miguel, semana 10 |
| OQ2 | Lenguaje del aplicativo y, con él, runtime, gestor de dependencias con su formato de lockfile y comprobador de tipos | Decisión de arquitectura, etapa de diseño de dominio |
| OQ3 | Framework del grafo, framework de voz, proveedores de transcripción y síntesis, almacén vectorial y herramienta de evaluación | Decisiones de arquitectura, alimentadas por los spikes |
| OQ4 | Proveedor de hospedaje del chat, la bandeja y el transporte de voz | Decisión de arquitectura, condicionada por A1 |
| OQ5 | Si el repositorio se hace público al final, lo que cambia la exposición del historial. **Actualizado el 2026-09-19:** Miguel está considerando seriamente dejarlo privado de forma permanente, compartido por invitación, porque no le ve la gracia a publicarlo. La decisión sigue abierta y arrastra cuatro consecuencias: si queda privado, el escaneo de secretos y la protección de inserción de GitHub nunca estarán disponibles y el escaneo propio es el único; la revisión de licencias deja de ser condición de publicación y pasa a ser higiene; el escaneo del historial completo pierde su disparador de la semana 12 y necesita otro; y el runner propio deja de tener que apagarse | Miguel, sin fecha |
| OQ6 | Si el techo de gasto sube tras la revisión del día 30 | Miguel, día 30 |
