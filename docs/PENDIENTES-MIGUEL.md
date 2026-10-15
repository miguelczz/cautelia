# Pendientes de Miguel

Lo que solo puedes hacer tú, ordenado por cuánto trabajo destraba. Cada entrada
dice **qué destraba**, **por qué no puedo hacerlo yo** y **qué hacer**, en ese
orden, para que no tengas que reconstruir el contexto.

Última revisión: 2026-10-14. La sección que sigue es el estado de hoy, comprobado
contra el código; de ahí para abajo queda el registro como se escribió hasta el
2026-10-07, y varias de sus entradas ya no valen (se dice cuáles).

---

## Estado al 2026-10-13: qué falta para dar el aplicativo por terminado

Sale de cruzar este documento, la pasada de publicación, la auditoría del
2026-10-10, las correcciones del 12 y el 13 y la lista de obligatorias del PRD, y de
comprobar cada renglón contra el código. Lo de producción no se pudo mirar desde el
repositorio y va aparte.

### Tres fechas que ponen la revisión de GitHub en rojo si se pasan

| Fecha | Qué vence | De quién |
| --- | --- | --- |
| 2026-11-03 | El aviso de seguridad aceptado de `braces` (interfaz), en `app/frontend/DEPENDENCIES.md` | Mío: revisar si ya hay versión corregida, o renovar con su razón |
| 2026-11-13 | Los topes de los proveedores (párrafo de abajo) | Miguel: solo él entra a esas consolas |
| 2026-11-13 | El aviso de seguridad aceptado de `langgraph-sdk`, misma tabla | Mío: igual |


Los topes que guarda `app/config/providers/prices.yaml` se leyeron en las consolas el
2026-10-13 (Claude) y el 2026-10-14 (Deepgram, Cartesia y Gemini) y valen 30 días. Desde
el **2026-11-13 la revisión de GitHub sale en rojo** en cualquier subida hasta que se
vuelvan a leer y se actualice la fecha. Es de Miguel: solo él entra a esas consolas.

### Falta, y es trabajo de código

| Qué | Estado | Por qué importa |
| --- | --- | --- |
| **Conductor que no figura en la póliza, sin nombre completo** | Desde el 2026-10-13 se producen los seis datos de las reglas, y la agente pide una vez el nombre completo de quien conducía cuando no fue el titular. Si la persona no lo da, el dato queda sin leer y la regla no dispara. Si la confirmación de la póliza era lo último que faltaba, el reporte cierra en ese turno y la pregunta no llega a hacerse; el respaldo sin modelo tampoco la hace | Menor: la salida sin dato es la segura |
| **El cierre directo en la llamada, con una persona** | Probado de punta a punta en una llamada simulada el 2026-10-13 (el caso quedó cerrado y registrado y la despedida lo dijo). Falta que Miguel lo oiga en una llamada real | Es texto que oye la persona |
| **La espera de la llamada** | Bajó de 3,6 a 2,7 s de promedio el 2026-10-13. Lo que queda es el tiempo del modelo; bajarlo más pide empezar a hablar mientras el modelo escribe | Es la medida más lejos de su meta |
| **Línea base de evaluaciones** | No hay ninguna publicada. La última corrida completa (2026-10-11) tuvo 2 casos en rojo y 6 sin medir, y desde entonces cambió toda la conversación del chat | El README y la pestaña de calidad no pueden citar cifras con fecha y versión hasta que exista |
| **Calibrar al juez** | Desde el 2026-10-13 existe lo que arma la cola (`mise run evals:label:queue`) y las corridas con conversaciones guardan lo que dijo la agente, ya tapado. Faltan cuatro cosas: una corrida con conversaciones (gasta centavos, la aprueba Miguel); que Miguel confirme los tres criterios propuestos y sus preguntas (`evals/gates/judged_criteria.py`: guía de voz, alcance, relevancia); el juez mismo y su rúbrica, que no existen; y decidir cuántas etiquetas se ponen: con el umbral vigente hacen falta 16 «pasa» y 16 «falla» de prueba por criterio e idioma, y 40 etiquetas en total no alcanzan para encenderlo | Sin eso, lo que juzga el tono sigue «no medida», que es lo honesto |
| **Ataques contra el sitio publicado** | Solo los de acceso a un caso ajeno; falta la fuga por trazas y el resto del conjunto | Es criterio de publicación |
| **Latencia del chat en el panel público** | Construido el 2026-10-13: la corrida completa de evaluaciones mide cada turno del chat con la misma definición que el chat en vivo, resume por idioma (la mitad y 95 de cada 100 turnos, con su recuento; con menos de 20 turnos por idioma sale «no medida») y la línea base lo guarda en su propia sección. Falta correrla (`mise run evals:completa`, gasta centavos) y publicar la línea base desde ese reporte (`mise run evals:baseline -- --report <reporte>`, sin gasto), que solo publica una corrida en verde. La meta declarada es 95 de cada 100 turnos en menos de 3 s por idioma; se publica, no bloquea | Hasta entonces el panel dice «no medida: todavía no se ha publicado ninguna línea base», que es verdad |
| **Operación de producción** | Desde el 2026-10-13 el repositorio trae cómo se publica y cómo se vuelve atrás (`mise run deploy`, `mise run deploy:rollback`, `docs/reference/operacion-de-produccion.md`), probados solo en modo simulado. Falta ejecutarlos de verdad con la vuelta atrás, saber qué corta al llegar al tope de Google Cloud y anotar cómo se publica la landing. El aviso de gasto y de reinicio fallido ya existe (chequeo diario, abajo); falta verlo fallar una vez y confirmar que llega el correo | Un despliegue no está hecho hasta que su vuelta atrás está probada |
| **Langfuse en producción** | Conectado en local el 2026-10-14 (abajo). Para producción faltan las tres variables del proyecto `cautelia-produccion` en el gestor de secretos, puestas en el servicio y en el trabajo del reinicio nocturno, y leer sus condiciones de uso de datos antes de encenderlo | Sin ellas producción sigue sin enviar trazas, que es lo de hoy |
| **La etapa de verificación del flujo AI-DLC** | Nunca corrió; el estado quedó en «functional-design» | Es donde se arma la tabla de objetivos medibles |
| Detalles | En la llamada el caso sigue naciendo como reporte antes de la primera palabra. En la agencia nadie puede anotar para las reglas (solo el rol ajustador). Dos casos de comprensión fallaron una sola vez cada uno entre siete corridas del 2026-10-13 (`DS-2/es/understand-quote-other-words` y `DS-2/en/understand-license-years-computed`) y pasaron en todas las demás: quedan vigilados, sin marcarse inestables | Menores |

### Falta, y depende de Miguel o de terceros

- Volver a leer los topes en las consolas antes del 2026-11-13 (párrafo de arriba), si el proyecto sigue recibiendo cambios para entonces.
- El README ya está escrito (2026-10-14, con capturas, una animación y el video). Falta cambiar sus cifras cuando se publique la línea base, después de «publica».

**Decidido el 2026-10-15:** «publica»; el juez y las 20 grabaciones de la prueba de voz quedan fuera y sus criterios siguen saliendo «no medida» (se pueden agregar después sin tocar nada más); el repositorio se publica con el historial limpio (abajo); la imagen de cada versión la construye Cloud Build y no la Mac.

**Aprobado el 2026-10-14:** la frase del reporte incompleto (`intake.unfinished`), los textos de las anotaciones guiadas (`visitor.triage.*`) y la muletilla de la llamada («Okey…», «Listo…»), que se queda. **Descartado el 2026-10-14:** la validación con personas del sector («no es necesario»).

**Revisión para hacerlo público (2026-10-14).** Ninguna clave en los 786 commits (`gitleaks`, historial completo) y ningún archivo de entorno ni de llaves subido nunca. Lo que sí queda a la vista si se publica: el correo de la universidad como autor de 779 commits (dato de cada commit, no de un archivo); los dos correos personales que nombraba `docs/PLAN-AIDLC.md` --ya quitados del archivo, siguen en el primer commit--; la dirección directa del servicio de Cloud Run en `site/functions/[[path]].js` (pública de todos modos, no es secreta); y la ruta de usuario de la Mac en tres documentos. Quitar los dos primeros del historial exige reescribirlo (cambian todos los identificadores de commit) o publicar un repositorio nuevo sin historial; es decisión de Miguel. **Resuelto el 2026-10-15** («limpiemos los commits por si las moscas»): los 728 commits se reescribieron con el correo privado de GitHub como autor y los dos correos del plan como «[correo retirado]», con el mismo contenido final y las mismas fechas; `gitleaks` volvió a pasar sin hallazgos. Se publica en un repositorio nuevo y el anterior queda privado y archivado, porque en el mismo repositorio el registro de actividad y las corridas viejas de GitHub Actions seguirían enlazando a los commits de antes. En la Mac quedan la rama `historial-original` y las ramas `respaldo-nube/*`, que nunca se suben.

### Ya está hecho, aunque más abajo diga lo contrario

- La cotización de Autos Poblado, de punta a punta.
- Los botones de la landing: apuntan al mismo dominio; `app.cautelia.app` ya no hace falta.
- La voz de respaldo, por cupo agotado y por cualquier otro fallo.
- **La llamada oye mejor la póliza** (2026-10-13): el reconocedor recibe el español de Latinoamérica y una lista de términos clave por aseguradora (la póliza, municipios y vías del valle de Aburrá, carros comunes); un número de póliza mal oído («Paul 201 17») se reconoce como incompleto, se busca la póliza por el nombre completo del titular y la agente la confirma en voz alta; si no la encuentra, pide repetirla cifra por cifra una sola vez. Comprobado en una llamada simulada real. Falta oír en una llamada de verdad si los nombres de lugar («Itagüí») llegan bien: la simulación tapa los lugares antes de sintetizar y no lo puede probar.
- **Todo gasto en proveedores queda en el libro del proyecto** (2026-10-13). `evals:entender` y otros cuatro comandos anotaban su gasto en una base desechable que se borraba al terminar: entre el 7 y el 13 de octubre faltaron unos 0,29 USD de Claude, que no veían ni la pantalla ni el techo. Ahora escriben en el libro de la base del proyecto y no gastan si no pueden registrarlo. Lo que faltaba se anotó con `mise run spend:reconcile` (asiento de ajuste, con su nota). La consola del proveedor suma todos los entornos; cada despliegue muestra lo suyo.
- **Un ruido ya no deja abierto el turno de quien llama** (2026-10-13): una señal de voz sin palabras sostiene el turno 1,5 s como mucho y varias seguidas suman 2 s como máximo; antes cada una valía 2,5 s y se encadenaban. Miguel confirmó que en sus llamadas no sonaba música ni otro audio, así que la causa de la llamada que nunca contestó es esta y no palabras de fondo; ese otro caso (música con voz, otra persona hablando) sigue sin tope y no se toca sin un caso real. Falta que Miguel repita la llamada para confirmarlo.
- **La agente no promete lo que no pasó** (2026-10-13): mientras falten datos del reporte, una respuesta del modelo que lo dé por registrado o diga que un ajustador lo revisará se descarta y sale una frase fija que dice qué falta (`intake.unfinished`; el texto espera el visto bueno de Miguel). Ofrecer pasar el caso a un ajustador y decir que se anotó un dato siguen permitidos. Los casos de evaluación nuevos miden que la agente **diga** qué falta, no que lo pregunte.
- **Los seis datos de las reglas** (2026-10-13): heridos, terceros con datos pendientes y conductor que no figura en la póliza salen de la conversación y de la póliza; monto estimado, cobertura en duda y sospecha de fraude los anota el ajustador en la vista del caso. Las pólizas de ejemplo declaran sus conductores; una base ya poblada necesita subir la migración y volver a ingerir el corpus (`mise run corpus:ingest`, sin llamadas al proveedor) para tenerlos.
- Los casos de ejemplo traen su evaluación de reglas (los 20 que ya pasaron por la decisión); una base ya poblada las recibe con `mise run synthetic:seed` o con el siguiente reinicio.
- Un mensaje del chat que llega antes de abrirse su canal ya se atiende; una primera frase de la llamada que no dice a qué viene ya no abre un reporte (la agente pregunta); la excepción de seguridad de `langgraph-sdk` ya tiene fecha y la revisión la exige (2026-10-13).
- La llamada simulada puede terminar un reporte (`app/evals/fixtures/voice-sim/cierre-directo.json`), y con ella se oyó el cierre directo por voz de punta a punta.
- **Alguien se entera** (2026-10-13): un chequeo diario en GitHub Actions (7:30 de Bogotá, cerca de un minuto de GitHub al día) lee la salud del sitio, si el reinicio nocturno está al día y el estado del gasto, y falla cuando algo está mal; GitHub manda el correo del fallo. La salud pública dice ahora cuándo fue el último reinicio exitoso. A mano: `mise run ops:check`. Empieza a correr con la primera subida que lo traiga, y la parte del reinicio dice «no medida» hasta que se publique la versión que trae el dato. Se descartó Google Cloud Monitoring porque cobra cada mes por condición de alerta.
- **Quien hace de ajustador anota, con ayuda** (2026-10-13): en «Ver mi caso», antes de decidir, un paso opcional pregunta cuánto costaría el arreglo (en pesos, con la línea de desde qué montos cambian las reglas y tres montos de ejemplo que salen del archivo de reglas), si hay dudas de cobertura y si algo hace sospechar de fraude, cada una con un ejemplo; al guardar dice cómo quedó clasificado el caso. Solo sobre su propio caso, con tope de 30 cambios, sin ver ni pisar lo que anote un ajustador con credencial. Los textos (`visitor.triage.*`) esperan el visto bueno de Miguel.
- **Langfuse conectado** (2026-10-14, Langfuse Cloud, plan gratuito, región de Estados Unidos, proyecto `cautelia-local`): cada turno de chat y de llamada sale cada 15 segundos en segundo plano, con sus pasos, el modelo, los tokens, el tiempo y el costo, agrupado por caso y público por su enlace; nunca el texto de la conversación. «Ver mi caso» enlaza a esa traza («Ver en Langfuse cómo trabajó la agente»), y la vista de costo de Telemetría tiene un botón «Ver tu última conversación en Langfuse» (solo con las conversaciones de ese navegador: sin cuenta, Langfuse solo abre una traza por su enlace). El reinicio nocturno borra de Langfuse lo anterior a su corte; si Langfuse no responde, no cierra la demo y se reintenta la noche siguiente. Comprobado de verdad: un turno enviado llegó con modelo, tokens y costo, se listó y se borró. Se retiró el Langfuse para instalar a mano y sus variables. De paso apareció y se arregló que la redacción estropeaba a veces los identificadores de las trazas.
- **Dos fallos de la llamada del 2026-10-14, arreglados**: «quería preguntar por mi póliza» ya no se guarda como la pregunta de la consulta (la agente pregunta qué quiere saber en vez de revisar la póliza contra nada y pasar el caso a un ajustador), y una respuesta dudosa a «¿eres tú?» se pregunta otra vez, una sola, en vez de volver a pedir nombre y póliza. Además, la pantalla del caso va en dos paneles (el ajustador a la izquierda, los datos a la derecha, la conversación debajo) con menos texto, y un caso que ya no se decide dice «Estado de tu caso».
- **El saludo de la llamada ya no se corta** (decisión de Miguel, 2026-10-14: «mientras ella hable no debe escuchar, obviamente tampoco se puede interrumpir»). Suena entero una sola vez; lo que la persona diga mientras suena no se escucha ni se muestra, y la conversación empieza cuando la agente termina. Una frase que empieza encima del final y sigue después se oye entera, para no cortarle el principio. En el resto de la llamada la persona sigue pudiendo interrumpir. Cambia el criterio AC1.30.1, que pedía repetir entera la apertura cortada. Consecuencia para la prueba de voz: si se graban las 20 llamadas, cada grabación tiene que dejar sonar el saludo antes de hablar (unos 15 s de silencio al principio), o lo dicho encima se pierde. Las pruebas de la llamada que fijaban lo de antes se reescribieron; las de integración piden la base de pruebas en Docker y no se corrieron en la Mac.
- Los límites diarios de la llamada (3 por visitante, 15 del sitio, 4 minutos).
- El reinicio nocturno con sus casos sembrados, el aprovisionamiento y la ventana de 24 horas.
- El trabajo de fondo completo: cobertura, reglas y revisión, también al cerrar un reporte.
- **El cierre directo** (2026-10-13): al terminar un reporte el caso queda «en revisión»; las reglas y la revisión de cumplimiento corren con los datos finales y el caso se cierra solo como registrado o pasa a un ajustador, y la agente lo dice en un segundo mensaje. Solo cierra con «sin heridos» y «nadie más involucrado» dichos con claridad; cualquier fallo o duda lo manda a un ajustador. Un caso que se quede en revisión lo puede tomar un ajustador con credencial, y dos acciones simultáneas sobre un caso ya no se pisan.
- El idioma del chat según el selector, los rótulos de cláusulas por idioma y el cambio de idioma en la llamada.

### Solo se ve en las consolas, no en el repositorio

Qué versión corre en Cloud Run y con cuántas instancias mínimas; si el reinicio
nocturno está programado y corre; el presupuesto con su corte de facturación y a
quién le avisa; y si la ventana de gasto de producción sigue sembrada en cero.

---

## 0. El orden de lo que falta — acordado el 2026-10-03

Las 23 unidades están cerradas. Lo que queda no es construir piezas nuevas: es
cerrar costuras y abrir la demostración al público.

| | Qué | De quién | Depende de |
| --- | --- | --- | --- |
| 1 | ~~**La cotización**~~ — **cerrada el 2026-10-03**, en dos tandas: la elegibilidad se evalúa en el ritmo de fondo y queda guardada, y su respuesta **le llega a quien la pidió sin que tenga que volver a escribir**. Eso último pedía un puerto del núcleo hacia el canal que no existía en esa dirección | Mío | — |
| 2 | ~~**La transcripción de la voz** (1.18)~~ — **cerrada el 2026-10-03**. La llamada escribe sus dos lados, fuera del turno, y la regla vive en un solo sitio que usan los dos canales | Mío | — |
| 3 | ~~**Nombre**~~ y ~~**nombres de las aseguradoras**~~ — aplicados el 2026-10-03. Falta el **diseño y los textos de la landing** | Tuyo (el diseño) / mío (los textos) | — |
| 4 | ~~**El dominio**~~ — **`cautelia.app`** en Cloudflare, 8,20 USD el primer año. Decidido el 2026-10-03 | Tuyo | — |
| 5 | **Infra**: ~~las dos mediciones~~ (hechas el 2026-10-03, ver abajo) y el aprovisionamiento | Mío | De 4, porque sin nombre no hay certificado |
| 6 | **La pasada de publicación**: once criterios diferidos y el checklist del segundo día | Mío | De 5: la mitad se mide contra el despliegue vivo |
| 7 | **Las tres marcas de la bandeja** (monto, cobertura disputada, sospecha de fraude) e **`injuries_present`** con su clasificador | Mío | De 6 |
| 8 | **`unlisted_driver`** con su campo propio | Mío | De 6, para que el cambio de cifra se absorba en la misma republicación de métricas |

**Por qué el dominio no se compra ya:** el nombre del producto entra en los
cambios que quieres hacerle a la landing, y un dominio comprado con el nombre
viejo es dinero gastado dos veces.

**Las dos mediciones del contenedor, hechas el 2026-10-03.** Son las que decidían
el tamaño de la instancia y si el plan B cumplía tu exigencia.

| Qué | Medido |
| --- | --- |
| Arranque en frío, hasta responder «listo» | **2,3 s** |
| Memoria en reposo | **~155 MB** |
| Con 512 MB de límite | **El contenedor muere por falta de memoria** al cargar los detectores |
| Con 1 GB de límite | Pico de 173 MB, sin acercarse al límite |
| Tamaño de la imagen | 1,74 GB |

**Lo que esto decide:** la instancia necesita **1 GB**, no 512 MB. Y confirma hacia
atrás la decisión de hospedaje: el plan gratuito de Render da 512 MB fijos, así que
el aplicativo habría muerto allí al primer visitante que escribiera algo. En Oracle
el tamaño lo elegimos nosotros.

**Y los 2,3 segundos son buena noticia:** si algún día hay que caer al plan B, un
arranque de ese orden es invisible con la llamada de calentamiento al cargar la
página. Ya no es un riesgo abierto.

Lo que la imagen enseñó por el camino, y queda arreglado: faltaba un
`.dockerignore`, así que la imagen llevaba **la venv de tu Mac** con sus enlaces
apuntando a `/Users/...` y el contenedor arrancaba sin poder importar nada. Con él,
la imagen bajó de 2,86 GB a 1,74 GB.

**Las tres aseguradoras, renombradas el 2026-10-03.** Agencia Castilla (la
agencia, abre en inglés), Seguros Aburrá (abre en español) y Autos Poblado (abre
en inglés, la que cotiza). Son los nombres que están hoy en
`app/config/tenants/*/tenant.yaml`; esta línea decía otros dos y era de una vuelta
anterior de la búsqueda.

**Y una cosa que conviene que sepas, porque condiciona futuros cambios de nombre.**
Los dos primeros que elegiste —*Agencia Laureles* y *Vega Autos*— **no se pueden
usar**: el detector de datos personales los tapaba como nombre de persona, y la
apertura de la llamada habría dicho «Le habla [NOMBRE 1]». No es un defecto del
detector: «Vega» y «Laureles» **son** nombres de persona, y el modelo inglés los
etiqueta así.

No se tocó el detector. Es un módulo crítico con compuerta dura y piso de cobertura
propio, y relajarlo para que acepte un nombre de marca es exactamente la clase de
excepción que lo erosiona. Lo que se hizo fue elegir nombres que **sobreviven al
detector real**, comprobados en las cuatro combinaciones de plantilla e idioma que
la prueba exige.

Si algún día quieres cambiar uno, el filtro es ese: hay una prueba que lee los
nombres de la configuración y falla sola si el detector se traga alguno. De los que
probamos, estos pasan: Seguros Aburrá, Seguros Rionegro, Agencia Rionegro, Agencia
Jardín, Agencia Cedral, Agencia Cafetal, Agencia Cordial, Agencia Mirador, Agencia
Faro, Agencia Portal, Seguros Portal, Seguros Cedral, Agencia Naranjal, Agencia
Platanal y Pradera Seguros. **La forma «X Autos» no sirve con ninguna palabra**: el
detector toma siempre la primera como nombre de persona. Lo que sí funciona es
invertirla —**Autos Poblado**, que es la que quedó—, porque entonces la primera
palabra es la que marca que se trata de una organización.

**El nombre: Cautelia** (2026-10-03). *Cautela* es la prudencia de quien se guarda
de un riesgo antes de que ocurra, y *cautio* en latín es la garantía que se da para
responder por algo: las dos mitades del seguro en una palabra. Se eligió sobre
sesenta y tantos candidatos probados, por tres razones: suena a palabra real y no a
invento con costuras, no nombra ningún acto que el sistema no hace --peritar,
indemnizar, pagar-- y se dice igual en español y en inglés.

**El dominio es `cautelia.app`**, no `.com`: el `.com` está tomado, comprobado en
Cloudflare y en un segundo buscador. Son 8,20 USD el primer año y sube después;
Miguel lo acepta sabiendo que falta ver si el aplicativo sigue vivo en un año. El
`.app` **obliga a HTTPS por diseño** --está en la lista de precarga de seguridad de
los navegadores-- y eso aquí no cuesta nada: Cloudflare da el certificado y el túnel
ya iba por ahí. Si acaso, juega a favor.

**Lo que esto NO dispara:** un renombrado del repositorio ni de los identificadores
internos. `untangle` puede seguir siendo el nombre del repositorio y de los módulos;
lo que cambia es el nombre del producto, el dominio y los textos que una persona lee.

**Dónde comprar el dominio, y qué resuelve Cloudflare** (investigado el 2026-10-03).
Cloudflare vende a precio de costo —lo que paga al registro más la tasa de ICANN—
sin margen y **sin salto en la renovación**: unos 10 USD al año el `.com`, con
privacidad de WHOIS incluida. Porkbun cobra ~11 USD planos; Namecheap arranca en
~10 y renueva en ~18,50, que es el patrón de primer año barato.

La razón de elegir Cloudflare no es el dólar de diferencia: es que **el túnel de
Cloudflare resuelve el agujero del plan de Oracle**. Es gratis, soporta
WebSockets, y no necesita ni IP pública ni certificado en la máquina: Cloudflare
termina el TLS en su borde y el servidor solo abre una conexión **hacia afuera**,
sin un puerto expuesto a internet. Para una demostración cuyo argumento es el
aislamiento bien hecho, eso es sustancia y no comodidad. Y su registrador exige que
el DNS esté en Cloudflare, así que comprarlo en otro sitio sería mantener dos
cuentas para una sola cosa.

La contra, dicha: registrador y proxy quedan en la misma empresa, y mudarse algún
día sería mudar las dos a la vez. Porkbun por un dólar más al año es la
alternativa buena si eso incomoda.

**Lo que se comprobaba antes de dar el camino por bueno** (resuelto el 2026-10-03):
si el plan gratuito de Cloudflare aguanta los tres minutos que dura una llamada. Sí
los aguanta, y no por una medición de una sola llamada sino por dos hechos que valen
para todas. Cloudflare **no documenta ningún límite de duración** y soporta
WebSockets igual en el plan gratuito que en los de pago; lo único que corta es la
**inactividad**, y para eso recomienda un latido periódico. Ese latido **no hace
falta aquí**: el worklet de captura
(`app/frontend/public/voice-capture-worklet.js`) emite un trozo de audio cada
`MUESTRAS_POR_TROZO` muestras sin mirar si hay voz o silencio, así que mientras el
micrófono esté abierto viaja audio en la dirección navegador → servidor y la
condición que cortaría la conexión no llega a darse dentro de una llamada.

La consecuencia, por si algún día alguien quiere "optimizar": **recortar el envío
durante los silencios rompería esto**. Hoy el silencio es lo que mantiene viva la
conexión.

**PUBLICADO el 2026-10-06.** Las dos superficies están en vivo.

| Qué | Dónde | Cómo |
| --- | --- | --- |
| La landing | **`cautelia.app`** | Cloudflare Pages, mismo sitio que el dominio |
| El aplicativo | Cloud Run, `us-east1` | `app.cautelia.app` en cuanto emita el certificado |
| La base | Neon, Virginia | 72 casos, tres aseguradoras |

**Lo que mide, contra el despliegue real:** arranque en frío **5,6 s**; acuse del
mensaje con la instancia despierta **816 ms**; primera palabra de la agente
**546 ms**. Y responde de verdad: *«Hola, soy Catalina, la asistente de
inteligencia artificial de Seguros Aburrá…»*.

**La región se eligió midiendo, no por gusto.** El primer despliegue fue a Iowa y
**tres de las cuatro superficies salieron caídas** — chat, voz y bandeja, todas
con tiempo agotado a los 200 ms. La causa no era el aplicativo: las sondas leen
la base, la base está en Virginia, y ese límite se calibró contra una base local
de sub-milisegundo. Se movió el servicio a `us-east1`, pegado a la base, en vez
de aflojar el límite. Ahora tardan 165, 179 y 180 ms. **Van justas**: si Neon
duerme su cómputo, la primera sonda tras despertar podría pasarse, y entonces sí
tocará ajustar el límite con su medición al lado.

**El tope de gasto es duro y está probado.** Presupuesto de 4.000 pesos con
avisos al 50, 90 y 100 %, y una función que al llegar al 100 % **desvincula la
cuenta de facturación del proyecto**. Probado de verdad antes de desplegar nada:
por debajo del tope no toca nada, al tope apagó la facturación, y se volvió a
encender. La prueba encontró dos fallos silenciosos —el disparador no podía
invocar la función y la función no podía apagar nada— que habrían aparecido el
día que hiciera falta.

**Tres cosas que solo se vieron desplegando:**

1. **La demostración no aceptaba casos.** 503 al primer mensaje. Es el diseño:
   sin un reinicio exitoso conocido las superficies se cierran, porque «ninguna
   corrida» y «el reinicio lleva tres días caído» deben ser indistinguibles.
   `demo:reset` contra producción la abrió. **Es el último paso de cada
   despliegue y hay que recordarlo.**
2. **La ventana de presupuesto no existía en la base.** `budget_window: 0`, y
   ningún nodo del grafo había corrido nunca. El aplicativo se niega a gastar si
   no sabe cuánto lleva gastado. Sembrada con la misma función que siembra la
   base de pruebas, no con SQL a mano.
3. **El título del navegador seguía diciendo «Untangle»**: estaba escrito en
   línea en el HTML de la interfaz y no pasaba por el catálogo de textos.

**Lo que queda pendiente de esto:**

- **El certificado de `app.cautelia.app`.** El CNAME resuelve a Google y no está
  proxeado; Google reintenta cada cinco minutos y documenta hasta 24 horas.
  Mientras tanto **los cuatro botones de la landing apuntan a la dirección larga
  de Cloud Run**, que sí responde: una landing pública con un botón muerto es
  justo lo que la regla de no prometer lo no construido prohíbe. Se devuelven a
  `app.cautelia.app` en cuanto emita.
- **Vercel queda abandonado.** Cuatro despliegues atascados en «Building» con dos
  cuentas distintas, sin registros de construcción y con Vercel declarando todo
  operativo. Cloudflare Pages lo subió en 2,4 segundos.
- **La ventana de presupuesto se sembró en cero**, no con los ocho centavos
  acumulados desde el 2026-09-16. Es parte del criterio diferido de la pasada de
  publicación y sigue abierto.

**Oracle gratuito queda descartado, el 2026-10-06, y por dos razones distintas.**
No se vuelve a intentar.

La primera es cupo: **unas 570 peticiones** de `VM.Standard.A1.Flex` a lo largo de
doce horas, repartidas en dos franjas horarias y alternando dos tamaños (6 GB y
2 GB), sin que entrara ni una. Cero errores, así que el guion funcionaba: no hay
máquinas ARM libres en esa región y no las hubo en todo un día.

La segunda cierra la puerta del todo. La otra máquina gratuita de Oracle, la x86
`VM.Standard.E2.1.Micro`, **no existe en Bogotá**. Preguntado al catálogo de la
región, ofrece ocho formas: `BM.Standard.A1.160`, `BM.Standard.E4.128`,
`BM.Standard.E5.192`, `BM.Standard3.64`, `VM.Standard.A1.Flex`,
`VM.Standard.E4.Flex`, `VM.Standard.E5.Flex` y `VM.Standard3.Flex`. La generación
E2 es de 2019 y a las regiones nuevas no la despliegan. De las ocho, la única
gratuita es la ARM que no tiene cupo; las otras siete son de pago. Y la región se
fija al crear la cuenta y no se cambia.

El guion que esperaba cupo (`deploy/esperar-cupo-oracle.sh`) y su servicio de
arranque quedaron **detenidos y desinstalados** a petición de Miguel. La bitácora
se conserva en `~/Proyectos/documentos/cautelia/cupo-oracle.log`.

**Lo que queda, y por qué Cloud Run.** El nivel gratuito factura **solo mientras
atiende peticiones**, no mientras espera: 360.000 GB-segundo al mes, de los que
una llamada de voz de tres minutos consume 180. Un ping cada cinco minutos
mantiene la instancia despierta y cuesta prácticamente nada, así que no hay
arranque en frío. La contra honesta: el nivel gratuito solo aplica en regiones de
Estados Unidos, así que el servidor queda a unos 80 ms de Colombia en vez de a
10 — asumible sobre un presupuesto de 800 ms por turno, pero peor que Bogotá.

**El tope de gasto no se deja en una promesa.** Google no trae tope duro de
fábrica, así que se monta: alerta de presupuesto que dispara una función que
**desactiva la facturación del proyecto**. Se monta y se prueba **antes** de dejar
nada corriendo.

**La portada de la landing, decidida por Miguel el 2026-10-05.** Se va el nudo
—la metáfora, el hilo del costado y el vídeo— y entra otra cosa, en cuatro tiempos
que el scroll recorre:

1. **El choque abre.** Dos vehículos de noche que se acercan hasta ocupar el plano.
   El golpe **no se ve**: el destello entra un instante antes del contacto. No es
   pudor, es técnica — la deformación del metal es justo lo que el vídeo generado
   no sabe hacer, y un choque falso desmentiría la página entera.
2. **Del destello sale la voz**, con la frase de quien llama.
3. **De la voz salen los campos** del expediente, uno a uno.
4. **Cierra la marca**, no una prueba: «Cautelia. Toma el reporte. Comprueba qué dice
   su póliza. Pasa a una persona.» En una sola línea, que se ajusta al ancho en vez
   de partirse: la frase es el titular y partirla la convierte en dos ideas.

**Por qué el choque abre y no cierra.** Si la portada termina en el impacto, el punto
más alto de la página es el accidente y todo lo que viene después baja. El accidente
no es el producto; lo que pasa en los diez minutos siguientes, sí.

**El reparto del trabajo, y la razón.** El primer tiempo es cine y lo genera
Higgsfield —noche, lluvia, faros, grano—, con los 130 créditos íntegros para ese
plano y margen para dos o tres intentos. **Del destello en adelante es código**,
porque los tres tiempos restantes son interfaz y el vídeo generado no sabe escribir
texto legible: devolvería letras que parecen letras. En cualquier otra página sería
feo; en esta es letal. El destello es la costura, y el ojo no puede comparar lo de
antes con lo de después.

**Lo que se conserva de la página de hoy**, reinterpretado: el mecanismo de resolver
al bajar, el hilo del costado —que pasa a ser la marca de la cita, anclándose en cada
sección— y el «mantén pulsado», que pasa de desatar un nudo a verificar.

**Boceto recorrible del movimiento**, hecho antes de gastar un solo crédito:
`https://claude.ai/artifact/5jXzHwB27q7nbQ7iYXUdmf`

**La voz del enlace público, decidido por Miguel el 2026-10-03.** El plan gratuito
de Cartesia da unas quince llamadas al mes y el cupo del sitio admite quince en un
día, así que la voz principal se agota mucho antes que el presupuesto. Su decisión:
**la de respaldo entra hasta que la de Catalina se recupere**, y no «Catalina se
reserva para el vídeo», que era la otra salida escrita.

Cómo se construye eso, y es la mitad que importa: **no llevamos la cuenta de los
caracteres de Cartesia**. Contarlos nos obligaría a que nuestra cuenta coincida con
la suya, y el día que se desviaran volveríamos al mismo fallo que esto arregla
—creer que queda cupo cuando no queda—. Lo que se hace es creerle al proveedor:
cuando conteste que no hay cupo, su voz queda marcada como no disponible y la de
respaldo atiende hasta que vuelva a contestar que sí. El cambio ocurre en la
frontera del adaptador, antes de que salga audio, así que quien llama no oye un
fallo: oye la otra voz.

Hoy el cambio de voz es **manual** (`voice:say -- --mode primary|fallback`); lo que
el sistema comprueba es que las dos estén configuradas, no cuál usar. Así que esto
es trabajo de U17, en la pasada de publicación.

**Por qué `unlisted_driver` va de último** (recomendación del 2026-10-03, aceptada):
hacerlo bien exige darle al conductor su propio campo, y un siniestro pasaría de
siete campos a ocho. El siete está en el PRD y se ve en la bandeja. Hecho junto a
la pasada de publicación, donde las métricas se vuelven a publicar de todos modos,
el movimiento de esa cifra ocurre una sola vez.

---

### La tarde del 6 de octubre — la landing rehecha y el aplicativo copiándola

Miguel vio la landing publicada y pidió cinco correcciones, por punto. Las cinco
están hechas y publicadas; esto es lo que cambió y lo que decidí por el camino.

**1. Fuera el nudo, entero.** El logotipo era una cuerda enlazada: ahora la marca
es una **C abierta hacia la derecha hecha de dos arcos y un punto** —una C que
escucha—, en el menú, el pie, la pestaña del navegador y como marca de agua en
la sección de barandas. El hilo que recorría el costado izquierdo desapareció
con su guion. Las cuatro fotos de nudo (`hero-ending`, `still-meet`,
`still-pull`, `still-row`) salieron del repositorio: dos fondos pasaron a ser
degradados dibujados y las dos figuras pasaron a ser **paneles del producto en
HTML**: la traza de un caso (orquestador, `intake`, `policy_verification` con su
cita verificada, `compliance`, `decision`, `interrupt → inbox`) y el reporte de
evaluaciones por caso y por idioma, con **un caso en rojo a propósito**
(`DS-2/023 · heridos capturados · EN`), que es el `injuries_present` que sigue
abierto en la lista de pendientes. Los dos llevan la etiqueta de ejemplo
guionizado que ya tenía la conversación de la sección de voz.

**2. Fuera las dos secciones** de mantén pulsado y de preguntas frecuentes, con su
HTML, su CSS, su guion, sus 44 claves del diccionario y el enlace del menú.

**3. El primer fotograma.** El concepto aprobado decía «sin texto hasta el
final». Miguel lo corrigió: quien llega no debe ver dos puntitos y nada más. La
frase de la versión estática —*Alguien acaba de chocar y no sabe qué cubre su
póliza*— entra desde el primer cuadro y se desvanece antes del destello. Es la
misma clave del diccionario, así que no hay dos versiones de la frase.

Y la escena entera se rehizo en código, sin imagen: hubo una propuesta de foto
generada de fondo (Higgsfield, 4 créditos gastados en cuatro candidatas que no
se descargaron) y Miguel prefirió no bajar nada; la escena dibujada tiene ahora
una vía mojada con perspectiva de un punto de fuga, el reflejo de los faros roto
por el agua, lluvia en tres capas que sigue cayendo mientras la vía está a la
vista, bruma en el horizonte y grano. Los textos que pinta el lienzo (la cita
de la voz y los campos del expediente) **salen del diccionario**: antes estaban
escritos en español dentro del guion y un visitante en inglés los veía así.

**4. El aplicativo copia a la landing, nunca al revés.** Los tokens del modo
oscuro ya eran los de la landing; lo que no coincidía era que el aplicativo
abría en **claro** en cualquier dispositivo con esa preferencia. Decisión de
Miguel, aplicada: **sin elección guardada, el aplicativo abre en oscuro** y no
sigue al dispositivo (BR1.1 enmendada el 2026-10-06; el modo claro sigue a un
clic). Cambia el paso de arranque, la regla en TypeScript, el proveedor, el
respaldo sin JavaScript de los tokens y sus pruebas. Comprobado al revés: con el
arranque diciendo «claro» se caen cinco pruebas.

**5. Los botones de probar** ya no abren pestaña nueva y apuntan a
`app.cautelia.app`, cuyo certificado se emitió a los 22 minutos. El de LinkedIn
sí conserva la pestaña aparte porque sale del sitio.

**Dos cosas que vi y no toqué, para que decidas:**

- **La aseguradora de demostración se llama `knotwell`** en los datos sintéticos
  y en la base. Es un nudo con nombre de empresa, visible en la bandeja. Cambiarlo
  es regenerar los datos sintéticos, resembrar la base de producción y tocar las
  fixtures; no entra en una tarde de landing. Si lo quieres fuera, es una tanda
  propia.
- **La primera sonda de salud tras despertar Neon tarda 261 ms** y el límite es
  200, así que tres superficies salen «caídas» unos segundos; despiertas, 70 ms.
  Es el riesgo que quedó escrito al elegir la región. Se arregla despertando la
  base antes de sondear, no subiendo el umbral.

**Y un incidente que no era mío pero era de `main`.** El flujo de GitHub Actions
del commit de la publicación salió **rojo** por una vulnerabilidad publicada
después: CVE-2026-104873 en `langgraph-sdk` 0.3.15, que entra por `langgraph`.
La falla vive en los decoradores de autorización de un servidor de la API de
LangGraph, que este aplicativo ni importa ni levanta. La versión corregida exige
`websockets<17` y la voz necesita `websockets>=17.1`, así que hoy no hay
resolución posible sin degradar una dependencia que sí se ejecuta. Quedó como
**excepción escrita con fecha y razón** en la tarea `audit` de `mise.toml`,
tal como manda la práctica, y el umbral no se tocó: cualquier hallazgo nuevo
sigue bloqueando. **Pendiente:** quitar la excepción cuando `langgraph-sdk`
admita websockets 17 (hoy va por 0.4.6 y sigue en `<17`).

La misma corrida destapó un segundo aviso, `source-map-js` < 1.2.2 en la cadena
de compilación de la interfaz; ese tenía versión corregida y se fijó
(`overrides`, con su fila en `DEPENDENCIES.md`), que es lo que manda la regla
cuando el parche existe.

**Pendiente que me apunto:** las excepciones de la auditoría de Python no tienen
hoy el mecanismo de caducidad que sí tienen las de la interfaz (fila con fecha
de revisión que `supply:check` exige y vence). La de `langgraph-sdk` vive solo
en un comentario con fecha. Hay que darle a `pip-audit --ignore-vuln` la misma
fila con fecha, para que la compuerta vuelva a preguntar sola.

**Las direcciones, decididas: B, y afinada esa misma tarde.** Miguel eligió,
con el costo delante, que todo viva bajo `cautelia.app` sin subdominio. Al verlo
pidió el ajuste natural: **la raíz es la landing** y el inicio del aplicativo
está en **`cautelia.app/home`**; el resto de rutas del aplicativo (`/t/…`,
`/metrics`, `/compare`…) quedan como estaban. Esto reemplaza a D-013 en lo que
decía del dominio. Cómo quedó hecho, para que la landing no pierda lo que la
hacía valiosa:

- `cautelia.app` sigue siendo el proyecto de Cloudflare Pages. La landing es un
  archivo estático en la raíz y sigue sin depender de que el aplicativo esté
  vivo. Todo lo demás pasa por una **función de Pages**
  (`site/functions/[[path]].js`) que reenvía la petición entera a Cloud Run;
  `site/_routes.json` excluye la raíz, la imagen social y la licencia. Sin
  cambio de DNS ni certificado nuevo, y la vuelta atrás es borrar la función.
- En el enrutador del aplicativo la raíz redirige a `/home`, para quien entre
  por el dominio directo de Cloud Run.
- Comprobado contra el despliegue: la salud responde JSON desde la raíz, la
  página del aplicativo abre en oscuro, y **la mejora a WebSocket de la voz
  cruza el proxy** (`101 Switching Protocols` en `/api/voice/…/socket`).
- Lo que cuesta, y Miguel aceptó: quien pasa de la landing al aplicativo espera
  a que la instancia despierte si estaba dormida (~6 s la primera vez).
- `app.cautelia.app` sigue mapeado en Cloud Run y funciona; ya nadie enlaza a
  él. Se puede quitar o redirigir a la raíz cuando quieras.

**Y la base del aplicativo con los estilos de la landing**, como pediste: los
selectores de idioma y de modo son ahora la pastilla de la landing (borde de
hilo, monoespaciada, `ES`/`EN`, el elegido sobre el panel, sin relleno cobre),
la barra se queda pegada arriba translúcida con desenfoque como la de la landing
al bajar, la marca va en la tipografía de títulos con su símbolo, y el botón
principal tiene el mismo relieve al pasar el puntero. Los nombres accesibles
siguen siendo los completos («Español», «Oscuro»…).

### La noche del 6 de octubre — la agente que se trababa, el micrófono y el chat

Miguel probó el chat y la llamada en producción y mandó tres cosas: la agente
repetía «Quiero ayudarle con calma…» ante cualquier mensaje, la llamada decía que
el navegador no dio el micrófono con el permiso concedido, y el chat necesitaba
otro diseño. La revisión encontró lo siguiente.

**1. La frase repetida no era conducta: era la degradación del nodo de captura.**
`INTAKE_SPEC` usaba como frase de degradación —la que sale cuando el nodo falla o
se pasa de tiempo— la frase de calma de BR5.4, que habla de insultos. Cada vez
que la extracción del modelo se pasaba del plazo, la agente decía eso y no decía
qué hacer. Ahora el nodo tiene su propia frase de degradación, honesta y que
guía: *«Perdón, no alcancé a procesar lo que me dijo. ¿Me lo repite, por
favor?»* (`intake.degraded`, en los dos idiomas).

**2. Por qué se pasaba de tiempo: el plan gratuito de Gemini está saturado.**
Medido en producción (`node_run`, con el tenant puesto para que RLS muestre las
filas): de cinco corridas del nodo en 24 h, **cuatro degradadas por tiempo a los
8 s** y una que acabó en 3.653 ms. Medido desde aquí contra el proveedor, siete
llamadas de extracción a `gemini-3.1-flash-lite` en plan gratuito: 5,4 · 5,6 ·
5,6 · 8,8 · 11,7 · 13,3 · 17,8 s, un **503 «alta demanda»** y una que no respondió
en 20 s. No es el razonamiento del modelo (cero tokens de pensamiento) y no hay
alternativa gratuita: `gemini-2.5-flash` y `2.5-flash-lite` responden *«no longer
available to new users»* y `gemini-3.1-flash` no existe en la API. El plazo del
chat sube de 8.000 a **11.500 ms** —entran dos de las siete llamadas que antes se
perdían y queda bajo los 12.000 del transporte—, con la medida escrita al lado
en `orchestration/turn.py`. Lo que queda por encima no lo arregla ningún número.

**3. El micrófono lo prohibía el propio servidor.** La cabecera
`Permissions-Policy` decía `microphone=()` —«el micrófono lo abrirá U16», y U16
no lo abrió—, así que el navegador negaba `getUserMedia` aunque la persona lo
hubiera permitido. Ahora es `microphone=(self)`. Y la pantalla de voz solo dice
«negado» cuando el navegador niega; un micrófono ausente u ocupado va por la
frase general, para no mandar a nadie a buscar un permiso que ya dio.

**4. El chat, rehecho.** Ventana de alto fijo con la conversación desplazándose
por dentro; burbujas; la agente firma «Catalina» (`insurer.agent.name`) y no «la
agente», también en la consola de voz; indicador de «Catalina está escribiendo…»
mientras el turno está en curso; cuadro de escribir pegado abajo con el envío en
un botón de icono; fuera la pista de Enter y Mayús+Enter. La indicación de que es
una demostración se queda, porque es regla.

**5. Dos defectos más que salieron al probar la conversación por guion contra
producción**, después de desplegar lo anterior:

- El servidor resolvía la clave de degradación con una tabla cerrada que no
  conocía la nueva (`intake.degraded`) y caía en la frase genérica de la guardia;
  la pantalla sí la conocía. Ahora las dos la conocen y una prueba fija que la
  clave de cada nodo se resuelva a su propia frase (rota a propósito: se cae).
- **Dos turnos en vuelo sobre el mismo caso chocan**: el segundo intenta la
  transición «abierto → capturando» que el primero ya hizo y el servidor responde
  `InvalidTransitionError`, que la persona leía como «tuve un problema para
  responder eso». Pasa si alguien escribe mientras la agente aún responde. El
  chat ya no deja mandar un segundo mensaje mientras hay uno en curso, y el
  servidor trata esa colisión como lo que es —la transición ya estaba hecha— en
  vez de fallar.

Nota de paso: Cloudflare responde 403 a clientes que no son navegadores
(`Python-urllib`); los navegadores pasan. Para probar por guion hay que ir al
dominio directo de Cloud Run con cabecera `Origin`.

**6. La decisión de Miguel: seguir en lo gratuito, con otro modelo.** La misma
clave gratuita ve más modelos de los que suponía. Medidos todos con la misma
extracción, tres llamadas cada uno, la noche del 6 de octubre:

| Modelo | Resultado |
| --- | --- |
| `gemini-3.1-flash-lite` (el de hoy) | 5,4–17,8 s, 503 «alta demanda», una sin respuesta en 20 s |
| **`gemini-3.5-flash-lite`** | **12 de 12 bien, 0,9–3,7 s, mediana 1,9 s**, sin razonamiento, esquema respetado |
| `gemini-3.5-flash` | 10,4 s y dos sin respuesta (razona ~400 tokens) |
| `gemini-3.6 / 3.7 / 3.8-flash` | 503 «alta demanda» y sin respuesta; cuando responden, 5–6 s razonando |
| `gemini-3-flash-preview` | 3,4–4,0 s razonando, una sin respuesta |
| `gemma-4-26b`, `gemma-4-31b` | 500 interno / sin respuesta |
| `gemini-2.5-*` | «no longer available to new users» |

El turno (chat y voz) pasa a **`gemini-3.5-flash-lite`**, con su precio de lista
leído de la página pública de Gemini ese día (0,30 y 2,50 USD por millón; lista
de precios versión 3). El juez de las evaluaciones sigue en el 3.1 porque está
calibrado contra él (ADR-014). ADR-006 no cambia: mismo plan gratuito, mismo
aviso de no escribir datos reales, y Google sigue usando el contenido para
mejorar sus productos (lo dice su página).

**Lo que no valida este cambio y hay que decir:** el corredor de evaluaciones
mide la captura con un doble determinista, no con el modelo, así que la calidad
de extracción del 3.5 frente al 3.1 **no está medida**; queda para el etiquetado
de DS-7 y la línea base por hito. Lo que sí está medido es que responde.

**Para prestar buen servicio sin pagar, lo que queda por delante, en orden de
rendimiento por esfuerzo:**

1. **Vigilar la latencia del proveedor como métrica**, no como sorpresa: el panel
   de cifras ya guarda `node_run`; una fila «p95 del nodo de captura en 24 h» y
   un aviso cuando pase del plazo dirían a tiempo cuándo el gratuito vuelve a
   saturarse.
2. **Respaldo de modelo dentro de la misma clave**: si el 3.5-flash-lite falla por
   tiempo o 503, reintentar una vez con otro modelo de la lista (hoy sería el 3.1)
   antes de degradar. Es configuración más una rama en el adaptador.
3. **Respuestas sin modelo donde no hace falta modelo**: la primera pregunta
   («¿Hubo alguien herido?») y las respuestas de sí/no se pueden resolver con
   reglas antes de llamar al modelo, que es lo que ya hace la emergencia. Entra
   por la rama evaluada: caso de golden set primero.
4. **Un segundo proveedor gratuito** (Groq o Cerebras, con modelos abiertos y
   latencias de cientos de milisegundos) como respaldo real. Es un adaptador
   nuevo con su taxonomía de errores y sus pruebas, y una cuenta que abres tú y
   cuya clave pones tú; antes de elegirlo se leen sus condiciones de uso de
   datos, como manda la práctica.

**Lo que sí guía la agente, y lo que no.** Con el nodo respondiendo a tiempo, la
captura pregunta el siguiente campo en cada turno (es su diseño); cuando no llega,
ahora pide repetir en vez de soltar una frase sin salida. Lo que no puede hacer
ninguna frase es compensar un proveedor que no contesta.

### El cierre del 6 de octubre — la conversación que vuelve y la ventana que llena la vista

Miguel probó el chat rehecho y mandó cuatro cosas más: la agente no se presenta y
se siente como una contestadora, al salir y volver la conversación se pierde, no
quiere desplazamiento de página, y lo mismo vale para la voz. Esta tanda cierra
las dos del medio; las otras dos siguen abajo.

**1. La conversación vuelve.** El servidor siempre la tuvo entera —la sesión por
la galleta del navegador, el caso atado a la sesión, cada turno en la
transcripción del caso— y la pantalla nunca la pedía. Ahora hay una ruta más
(`GET /api/chat/{aseguradora}/history`, módulo `chat/history.py`) que devuelve la
apertura, los turnos guardados y el número del caso, y la pantalla la pide al
abrirse, justo después de que el flujo de eventos conecta (así la galleta ya
está puesta y las dos puertas caen en la misma conversación). Lo recuperado se
dibuja delante de lo que llegue por el flujo, sin repetir nada.

**2. La agente se presenta al cargar, no después del primer mensaje.** El
docstring de U13 lo daba por hecho desde el principio («la apertura sale al
cargar la página») y nadie lo hacía: la apertura se publicaba con el primer
`POST`. Ahora la entrega la ruta del historial y la ruta del mensaje solo la
publica si nadie la entregó antes (un guion, una corrida de evaluaciones). Es la
captura de Miguel: su «Hola» recibía la pregunta pendiente sin nada delante
porque su galleta ya tenía caso y la pantalla no mostraba el historial.

**3. Lo recuperado viene redactado, y la pantalla lo dice.** La transcripción se
guarda tapada (regla de redactar antes de persistir; el tipo lo impone), así que
quien vuelve lee «Mi póliza es [PÓLIZA 1]» donde escribió el número. No es un
defecto que esconder: es la regla vista desde el visitante. Una línea encima de
la conversación recuperada lo explica (`chat.page.history_restored`), para que la
etiqueta no parezca un error de maquetación. Probado por la puerta: el historial
no trae el número de póliza que se escribió.

**4. La ventana llena la vista.** La ruta del chat declara `fill` en su
`staticData` y el marco lo lee, como `persistLocale` en la bandeja: la barra, la
conversación y el pie caben en la ventana (`h-dvh`), y lo único que se desplaza
es la conversación por dentro. Fuera el alto fijo de `calc(100dvh - 11rem)` y el
mínimo de 30 rem que en pantallas bajas obligaba a desplazar la página.

**5. Lo que no se persiste todavía, dicho aquí:** los avisos de fondo (lo que
decidió el ajustador, publicado en la conversación por `chat.notice`) no se
escriben en la transcripción, así que al recargar no vuelven; la decisión sí está
en el caso. Y el idioma de la sesión es el de la aseguradora por omisión: la
apertura recuperada sale en ese idioma aunque la persona haya escrito en el otro.

**6. La agente contesta lo que le dicen antes de seguir** (misma noche, segunda
tanda). Lo que la hacía sonar a contestadora era que ante cualquier turno
preguntaba el campo pendiente: a «Hola» le contestaba «¿Cuál es su nombre completo
y el número de su póliza?», y a «gracias» también. Ahora el nodo de captura
reconoce, **sin modelo y por reglas versionadas**
(`app/config/intake/social_signals.yaml`, junto a las señales de tono), cuatro
cosas que la persona dice de paso, y las contesta desde el catálogo antes de lo
que tocaba:

| La persona dice | La agente contesta |
| --- | --- |
| «Hola» | «Hola, con gusto le ayudo. ¿Hubo alguien herido?» |
| «Gracias» ante «¿Es correcto?» | «Con gusto. Anotado: dos heridos. ¿Es correcto?» (antes borraba el bloque: cualquier cosa que no fuera un sí contaba como no) |
| «¿Cuánto falta?» | «Llevamos 3 de 7 datos; falta cuándo y dónde, el vehículo y quién conducía, las otras personas involucradas. ¿Cuándo y dónde ocurrió el accidente?» (leído del caso, no de un contador) |
| «Hasta luego» | «Hasta luego. Lo que llevamos queda guardado; cuando vuelva, seguimos donde quedamos.» (sola, sin pregunta; el caso queda como está) |
| «Sí» a una lectura | «Gracias. ¿Qué pasó?» en vez de la pregunta a secas |
| «No, yo no dije eso» | «Entendido, lo corrijo. ¿Hubo alguien herido?» |
| «No, así está bien» | Cuenta como **sí** (antes el «no» inicial lo leía como corrección y repetía el bloque) |

Un turno que solo trae lo social **no llama al modelo**: no hay nada que extraer
y la llamada gastaba varios segundos del plan gratuito para volver vacía. Todo
esto vale igual para la voz, porque la voz pasa por el mismo nodo.

**Y se entiende en el otro idioma.** Probado en producción con Sunmeadow (inglés
por omisión) hablándole en español: «Gracias» y «No, así está bien» no se
reconocían, porque un turno corto no cambia el idioma de la conversación (BR2.2,
decisión medida: menos de cuatro palabras no mueven nada) y los reconocedores
miraban un solo idioma. Ahora lo social y el sí/no se buscan en los dos idiomas a
la vez --las formas son cortas y ninguna significa otra cosa en el otro-- y la
respuesta sigue saliendo en el idioma de la conversación. Caso de DS-2
`intake-social-other-language` (dos idiomas); el manifiesto queda en 56.

Golden set primero: diez casos nuevos de DS-2 (cinco criterios, uno por idioma),
en el subconjunto de arranque; el manifiesto pasa de 44 a 54 casos. Roto a
propósito para ver caer las pruebas: sin el reconocimiento social caen cinco
pruebas del nodo; sin la excepción del «no, así está bien» caen la prueba
unitaria y los dos casos de DS-2 que la miden.

**Lo que no entra en esta tanda, y conviene decidir después:** variar la forma de
las preguntas (hoy cada una tiene una sola frase, y a la tercera vez se nota),
hablar de tú cuando la persona habla de tú (el catálogo entero está en usted), y
usar el nombre de pila en español. Las tres son decisiones de presentación tuyas,
y las dos primeras duplican o triplican el catálogo de la captura.

**Lo que sigue de esta misma petición:** la consola de voz con el mismo `fill`
(hoy su pantalla no es una ventana con desplazamiento propio, así que llenar la
vista podría recortarla en pantallas bajas: hay que rediseñarla antes).

**7. Incidente: `main` estuvo en rojo desde el cambio de modelo (`08ae07c`) hasta
`3378c14`.** Lo vi tarde, al revisar las corridas después de la tanda
conversacional; la corrida de `08ae07c` quedó en «verificar» y no se verificó.
Tres fallos, dos de ellos de pruebas que tenían cifras escritas a mano:

- `tests/integration/u5/test_wiring.py` comparaba el modelo del chat con el
  literal `gemini-3.1-flash-lite`. Ahora lo lee de `providers.yaml`.
- `tests/integration/u17/test_lanes.py` tenía escritas las dos reservas de una
  llamada (0,098 y 0,072 USD) y el gasto que dejaba el restante entre ellas; el
  modelo nuevo cuesta más por llamada y el restante escrito quedó por debajo de
  las dos. Ahora lee las reservas de la contabilidad y pone el restante a mitad.
- La ventana del chat se desplaza y no podía recibir el foco (regla
  `scrollable-region-focusable` del arnés de accesibilidad): quien navega con
  teclado no podía leer lo que quedó arriba. La lista lleva `tabIndex=0`, con la
  excepción del linter escrita al lado, porque el linter y el arnés discuten y
  manda el que mide a la persona.

Lección escrita en la memoria de trabajo: `verify:rapido` va antes de cada
**push**, no después. El arreglo del arnés de accesibilidad no se puede
comprobar en tu máquina sin calentarla; lo confirma la corrida de `3378c14`.

### La última tanda del 6 de octubre — el recorrido rápido (P4)

Lo que decidiste («no quiero que el chat pregunte si es correcto… que lo que le
digan lo guarde… que tenga la capacidad de corregir ese dato») quedó así, y el
detalle está en `docs/plan-conversacion-2026-10.md` («Cómo quedó P4»):

- Cuatro datos obligatorios después de la seguridad, sin ninguna lectura de
  «¿es correcto?». El avance dice «3 de 5 datos».
- Con el último, la agente cierra nombrando el número del caso, **el caso pasa a la
  bandeja en ese mismo turno** y ofrece una sola vez lo opcional (vehículo, otras
  personas). «No, así está bien» lo deja como está; «sí» pregunta; un dato se anota.
- «Perdón, no eran dos sino tres» → «Corregido: tres heridos.» y sigue.
- Si la persona sigue escribiendo después, oye dónde está su caso.

**Tres decisiones que tomé y puedes revertir:**

1. **El caso se deriva al decir la frase, no al contestar la oferta.** La frase dice
   «queda con un ajustador»: o es verdad cuando se dice o no se dice. La alternativa
   (derivar al contestar) dejaba sin caso en la bandeja a quien cierra la pestaña ahí.
2. **`intake-readback-leading-no` sale del golden set.** Medía la lectura de
   confirmación que tú quitaste; no fallaba, no es un caso retirado para subir una
   métrica, y su frase sigue medida —con el significado contrario— como respuesta a
   la oferta en `intake-fast-closing`. Entra también `intake-correction`.
3. **La guardia de salida deja pasar el número del propio caso.** Lo comparaba
   contra «nada» y tapaba la frase de cierre con «No puedo compartir esa
   información». Ahora el turno le dice qué caso es; cualquier otro número con forma
   de caso sigue tapado.

**Lo que comprobar en producción** (yo lo hago al desplegar, y tú cuando quieras):
abrir el chat, dar la póliza de ejemplo, contestar «sí», contar qué pasó, cuándo y
dónde, y decir que no hubo heridos; la agente debe cerrar con el número, el caso
debe aparecer en la bandeja de esa aseguradora, y «no, así está bien» debe
despedirse sin preguntar nada más.

**Comprobado en producción el 2026-10-06 (`7fb7897`), en Seguros Aburrá:** «Hola» →
¿heridos?; «no, nadie se lastimó» → nombre y póliza; «POL-100042» → la ficha del
titular; «sí, soy yo» → ¿qué pasó?; el choque → ¿cuándo y dónde?; el lugar y la hora
→ «Listo: su caso STO-088963 queda con un ajustador… ¿Quiere agregar las otras
personas involucradas, o lo dejamos para el ajustador?», y el caso ya estaba en
`derived` con 5 de 5 al preguntar por él; «No, así está bien» → «De acuerdo…»; «¿Y
ahora qué hago?» → «Su caso ya quedó con un ajustador…». Entre 1,2 y 2,4 s por turno
tras el primero. En una primera pasada un turno salió degradado tras 12 s: el
proveedor no contestó en los dos intentos del presupuesto del chat; no se repitió.
Como el vehículo ya quedó anotado al confirmar la póliza, la oferta solo nombra a las
otras personas.

**Un aviso de los logs, arreglado en el commit siguiente:** el punto de control no
declaraba la póliza en espera (P3) entre sus tipos permitidos; el serializador la
bloqueaba al leer y el turno la reconstruía del diccionario. Funcionaba, pero el
aviso dice que el bloqueo será definitivo en una versión futura; ya está declarada.


### La mañana del 7 de octubre — por qué repetía la pregunta, por qué la llamada no oía, y el letrero

Tus tres capturas, verificadas con logs, con el nodo real en local y con una llamada
de prueba contra el servidor. Lo que encontré y lo que cambié:

**1. «¿Hubo alguien herido?» repetido, y «Corregido: dos personas».** El nodo
funciona: en local, «Sí, dos personas» pasa a pedir la póliza. Lo que falló fue el
**modelo extractor**: no sabía qué pregunta acababa de hacer la agente, y guardó
«dos personas» en «otras personas involucradas» (que es opcional) en vez de en
«heridos». Por eso la pregunta volvía, la segunda vez decía «Corregido» (el campo
equivocado ya tenía valor) y el contador seguía en 0 de 5. Dos cambios:

- El extractor recibe ahora la pregunta anterior como turno previo de la
  conversación, y su instrucción dice que una respuesta corta contesta esa pregunta.
- Y, más importante, **una respuesta corta a una pregunta de un solo dato se guarda
  sin llamar al modelo**. Medí Gemini en el plan gratuito con las frases de tu
  prueba: de 0,7 s a 40 s por llamada, con vencimientos frecuentes, y cero tokens de
  razonamiento (no es que piense: es que está saturado). Con ese modelo en el camino,
  «Sí, dos personas» vencía el presupuesto del turno y salía «Perdón, no alcancé a
  procesar». Ahora: un dato pendiente → el texto se guarda tal cual; «cuándo y dónde»
  se reparte por regla (fecha u hora → cuándo; calle o lugar → dónde; los dos → los
  dos); el modelo solo entra en respuestas largas o sin ninguna señal, con 4 s de
  espera, y si vence, el texto queda en el dato pendiente en vez de perderse. Una
  frase con aire de corrección («perdón, no eran dos sino tres») sigue yendo al
  modelo, que es quien sabe a qué dato se refiere.

  La conversación completa de tu captura, en local y con la misma póliza de ejemplo,
  quedó en **0,1 s por turno** y el caso llegó derivado con 5 de 5 sin tocar el modelo.

**2. La llamada que no oía.** Abrí una llamada contra el servidor desde un guion y le
mandé una grabación en español por el socket, como hace el navegador: **el servidor
la transcribió entera y respondió**. Deepgram y su clave funcionan. Lo que respondió
fue «Perdón, no alcancé a procesar», por el mismo modelo lento del punto 1, que en la
voz tiene 1,6 s de presupuesto: con la regla nueva, «no, nadie se lastimó» ya no pasa
por él. Lo que no pude reproducir es que el audio **no saliera de tu navegador**: en
tu llamada el servidor no recibió ni un turno tuyo (ningún evento de fin de habla en
todo octubre), y en la mía sí. Sospecho del navegador (la captura es Brave, con sus
escudos) o del micrófono elegido por el sistema. Para que eso no vuelva a ser un
misterio, la pantalla de la llamada ahora **avisa cuando lleva seis segundos
escuchando sin que entre sonido**: «No está llegando sonido del micrófono…». Si lo
ves, es el navegador o el micrófono, no la agente. Prueba en Chrome o Safari y mira
que la barra bajo el botón se mueva al hablar.

**3. «Llegaste al límite de hoy».** Eran dos límites a la vez. El tuyo: **una llamada
por visitante al día** (`calls_per_visitor_per_day: 1`), que subí a tres; con una,
quien prueba dos veces ve ese letrero. Y el del sitio: el cupo diario se deriva del
presupuesto de 5 USD que queda en 90 días, y hoy ya estaba agotado (`rate_limited_site`):
por eso tampoco pude probar la voz en producción hoy. Ese cupo es la práctica
afirmada de no gastar más de lo escrito, y no la toqué. Si quieres probar la voz más
veces al día, la decisión es tuya y es de dinero: subir el presupuesto o aceptar que
el enlace público viva con una o dos llamadas diarias.

**4. La apertura más corta.** Voz: «Hola, le habla Catalina, la asistente de
inteligencia artificial de Autos Poblado. Esta llamada queda transcrita para registrar
su caso. Para empezar, ¿todos están bien?». Fuera la lista de capacidades y la oferta
de pasar a una persona. Chat: la divulgación en una frase y «Puedo ayudarle a reportar
un siniestro o a resolver dudas sobre su póliza». La síntesis de voz se paga por
carácter, así que cada llamada cuesta menos; en el chat la apertura no gasta tokens
(sale del catálogo, no del modelo).

**Pendientes que dejó esto:** la redacción de datos personales toma «Hola» por un
nombre y la consola de voz muestra «[NOMBRE 1] esta es una prueba…» (es solo lo que se
pinta; lo que va al caso es otro texto); y verificar la voz en producción cuando el
cupo del sitio vuelva a abrir mañana.

### La tarde del 7 de octubre — el dinero real, el tope a 40 y el reinicio que nadie programaba

**Lo que decían tus pantallas de los proveedores:** Gemini en nivel gratuito con seis
claves separadas (pico de ~120 peticiones en un día); Deepgram con **199,91 USD de
crédito prepagado** y la recarga automática apagada; Cartesia en plan gratuito con
18.836 de 20.000 créditos del mes (se renuevan el 31 de octubre). **Gasto real del
proyecto en tres semanas: 0,09 USD.** El tope de 5 USD del aplicativo era una
contabilidad a precio de lista, no una factura, y repartido entre los 69 días que
quedaban dejaba **una llamada pública al día para todo el sitio**: esa fue la que te
dejó fuera.

**Tu decisión: «Tope a 40».** Aplicado en la contabilidad de producción (alerta en 24
USD, la misma proporción) y en la regla del proyecto, con fecha y razón. El cupo del
sitio pasó de 1 a 7 llamadas por día. El costo real sigue saliendo del crédito de
Deepgram y de los planes gratuitos; ningún proveedor tiene recarga automática.

**Dos fallos que encontré al aplicarlo:**

1. La admisión de llamadas comparaba contra el límite **guardado al abrir el día** (1),
   no contra el vigente: la disponibilidad decía 7 y la apertura seguía rechazando.
   Corregido en la consulta que consume la cuota, y la fila de hoy actualizada a mano.
2. **El reinicio nocturno no estaba programado en producción.** El último exitoso fue
   el 6 de octubre a las 17:00 UTC (a mano), y la demo se cierra sola a casos nuevos
   —chat y voz— a las 24 horas sin reinicio. Creé el job `cautelia-reset` en Cloud Run
   con el mismo entorno del servicio, lo ejecuté, y Cloud Scheduler lo corre cada día a
   las 3:00 de Bogotá (`cautelia-reset-nocturno`). Es parte del checklist del segundo
   día que estaba pendiente.

**La voz, verificada en producción** con la grabación por el socket: la agente oyó
«hola», transcribió el resto y respondió «Hola, con gusto le ayudo. ¿Hubo alguien
herido?» en menos de dos segundos. En esa prueba vi que «¿Sigue ahí?» saltaba mientras
llegaban parciales sin un final: ahora un parcial cuenta como presencia para la
escalera de silencios (sigue sin cerrar el turno).

**Lo que la regla no cubre, y queda en el modelo:** quien no contesta lo que se le
preguntó (por ejemplo, cuenta el choque cuando se le preguntó por heridos) pasa por
Gemini, y con el plan gratuito eso tarda de uno a cuarenta segundos. En el chat hay
cuatro segundos de espera y luego el dato pendiente como red; en la llamada el
presupuesto del turno es 1,6 s y ahí sale «Perdón, no alcancé a procesar». Un «sí» a
secas a una pregunta abierta ya no va al modelo: la agente repite la pregunta en el
acto. Si quieres que la llamada nunca dependa del modelo, la decisión es de producto:
preguntar siempre de a un dato y guardar lo que digan tal cual, también los relatos.

**Deuda que vi de pasada:** las claves de producción están como variables de entorno
en claro en la revisión de Cloud Run, no en Secret Manager. No cambia nada hoy, pero
es lo que haría que una captura del panel de Cloud Run fuera un incidente.

### La noche del 7 de octubre — por qué la llamada no te oía (con pruebas, no suposiciones)

Lo probé como lo usas tú: **Brave con un perfil aparte, el micrófono y los parlantes
reales de la Mac**, la aplicación completa en local y una llamada contra producción. Seis
causas, todas reproducidas, corregidas y con su prueba que cae sin el arreglo:

1. **La carga del detector de datos personales congelaba la llamada.** Sus modelos se
   cargaban con el primer transcrito que había que tapar, y eso bloquea el servidor
   unos 7 segundos. En producción: hablé a los 17 s y no llegó nada hasta los 24 s, con
   «¿Sigue ahí?» en medio. Cada instancia nueva de Cloud Run lo pagaba en su primera
   llamada. Ahora se carga al arrancar el servidor.
2. **«Sigue ahí» con la frase ya transcrita.** La espera podía volver un instante antes
   del plazo del turno y caía en la rama del silencio, que además tiraba lo dicho.
3. **«No le escuché bien» a frases claras.** Se exigía que *todas* las palabras pasaran
   0,6 de confianza; una sola en 0,58 tumbaba «tuve un choque en la calle diez». Ahora se
   mira la confianza de la transcripción entera, que es lo que dice el criterio; el
   umbral no cambió.
4. **El aviso de micrófono era falso.** El ruido de un cuarto callado con el micrófono
   funcionando llega a 0,0013–0,0036; el aviso saltaba por debajo de 0,003, es decir, en
   cuanto no hablabas seis segundos. Ahora solo salta con silencio digital, que es lo que
   da un micrófono muerto o silenciado.
5. **Colgar no hacía nada.** El navegador cerraba el socket al mismo tiempo que mandaba
   «colgar» y la pantalla esperaba una respuesta que ya no podía llegar; y lo que el
   servidor seguía mandando la devolvía a la llamada. Ahora sale al pulsar.
6. **«hola» salía como [NOMBRE 1]**, porque el reconocedor transcribe en minúscula.

**Tu micrófono:** no puedo afirmar qué entregó en tus llamadas, porque el servidor no lo
registraba. Desde hoy cada llamada deja en la traza cuántos segundos de audio llegaron y
su volumen máximo (`voice.audio_received`), y cada frase descartada deja por qué
(`voice.not_understood`). Si vuelve a pasar, se sabe en un minuto.

**Lo que no probé en producción después del último arreglo:** la llamada de verificación
contra producción la hice antes de la carga al arrancar; después confirmé en el registro
de la revisión nueva que el detector se carga antes de aceptar conexiones, y repetí la
llamada contra un servidor local recién arrancado (primer transcrito a 1,9 s). No gasté
la última llamada del sitio de hoy para dejártela.

**La integración continua** se colgó hora y media instalando navegadores (tarda un
minuto) y se habría comido seis horas del plan gratuito. Le puse techo: 45 minutos al
trabajo y 10 a ese paso. La causa era el espejo de Ubuntu del corredor de GitHub, que
no respondía: `apt` ahora espera 15 s con tres reintentos y salta al espejo público.

**Dos rojos de `main` el mismo día, y qué fue cada uno:**

- **El arnés de accesibilidad** marcó que las pantallas de espera e indisponible se
  desplazaban en horizontal a 360 px. El hueco reservado para el botón «Resultados»
  medía 176 px y el botón mide 105. Corregido (`8b3fc55`).
- **El presupuesto de tiempo del arnés** (240 s, PERF-U6.3): la corrida 37690171491 lo
  pasó con 291 s con todas las pruebas en verde. La última corrida en verde ya iba en
  236 s, y ese día el corredor estaba lento en todo: las pruebas de backend tardaron
  1.013 s contra 745 s. Se marcó **no comparable** por causa externa y se repitió, sin
  tocar el umbral: el segundo intento pasó en verde, con el arnés en 189 s y el backend
  en 563 s. Si el arnés sigue rozando el límite, hay dos salidas y las dos son
  tuyas: paralelizar más o subir el presupuesto con una decisión escrita.

### La noche del 7 de octubre — el chat deja de sonar a contestadora

**Tu decisión:** el chat habla con naturalidad, con Claude Haiku 5.5 y 5 USD de saldo
prepagado sin recarga automática. Antes de tocar el código lo medí con tu clave sobre
tu misma conversación, y en el aplicativo local completo:

| Medida | Resultado |
| --- | --- |
| Respuestas redactadas por el modelo | 8 de 8, ninguna cayó a la frase fija |
| Tiempo de la redacción | 1,0 a 1,35 s |
| Costo de la conversación completa | 0,00085 USD |

**Cómo quedó, y por qué es seguro:** el código sigue decidiendo qué se dice —qué dato
falta, qué pregunta toca, cuándo se pasa al ajustador— y Claude solo lo dice con
naturalidad, reconociendo lo que la persona escribió. Cada respuesta pasa por una
comprobación hecha con código antes de la guardia de salida: tiene que conservar los
números y códigos, mantener la pregunta y no agregar preguntas, cifras ni enlaces. Si
no la pasa, si el modelo falla o si tarda más de 3 s, sale la frase del catálogo. Lo
que escribe la persona viaja al modelo con los datos personales tapados. La voz sigue
con frases fijas, porque su turno tiene 1,6 s.

**Lo que queda pendiente:**

- **Poner la clave en producción.** El paso es tuyo, porque yo no introduzco
  credenciales. El comando está en el resumen de este cambio.
- **Una batería de evaluación con el modelo.** La integración continua no tiene claves,
  así que sus casos de chat siguen midiendo las frases del catálogo. Mientras no exista,
  las conversaciones con el modelo están cubiertas por las pruebas con dobles y por la
  medición de hoy, no por la compuerta.
- **El saldo.** Al ritmo medido, 5 USD alcanzan para miles de conversaciones. Cuando se
  acabe, el chat vuelve solo a las frases fijas.

### La noche del 7 de octubre — la agente entiende (fase 0 de la propuesta)

**Tu decisión:** «todo como recomiendas» sobre `docs/propuesta-2026-10/03-propuesta-y-diseno.md`.
La fase 0 quedó construida. Ahora Claude Haiku lee cada mensaje con el contexto del
caso y devuelve qué quiere la persona, los datos ya interpretados, si dijo sí o no y
qué preguntó. El código valida eso y sigue decidiendo qué falta y cuándo se cierra.
Si el modelo falla o tarda, el chat sigue por reglas como antes.

Medido en el aplicativo local con tu conversación de cotización de las capturas:

| Medida | Resultado |
| --- | --- |
| «Desde el 2022… ¿cuántos años es eso?» | Contestó «han pasado 4 años» y anotó 4 (antes, 18) |
| Cotización | Nunca habló de un accidente (antes, E1 a E3) |
| «En Itagüí» | Anotado como lugar de la licencia |
| Mensajes que cayeron a reglas | 0 de 14 |
| Tiempo de entender | 1,2 a 2,4 s; el turno completo, 2,6 a 2,9 s |

También quedaron hechos:
- tu apertura exacta;
- el saludo corto con las opciones;
- botones de respuesta rápida bajo cada pregunta;
- tu texto de vuelta en tu burbuja al recargar, mientras la base lo sigue guardando tapado.

**Lo que falta de ti:** una clave de Anthropic **para evaluaciones**,
`UNTANGLE_ANTHROPIC_API_KEY_EVALS`, separada de la del chat. Así una corrida de
evaluaciones no gasta el saldo que atiende a los visitantes. Va en tu `.env` local, no
en Cloud Run. Con ella corro `mise run evals:entender`, unos 0,02 USD por corrida: son
los 30 casos `understand-*` escritos antes del código, con tus capturas y con frases
dichas de formas que las reglas no reconocen. Sin la clave, esos casos quedan «no
medidos» y nunca en verde.

## 1. Lo que sigue abierto

### 1.2 ~~Los identificadores de póliza de ejemplo~~ — decidido el 2026-10-03

- Los de Sunmeadow y Knotwell se derivaron por analogía con el del contrato
  C-25. Cambiarlos es barato **hasta que U7 genere el corpus que los contiene**;
  después toca regenerar todo.
- **Decidido:** se quedan los que generó U7. Son identificadores sintéticos que
  nadie lee en voz alta fuera de la demostración, y cambiarlos ahora obliga a
  regenerar el corpus entero y los casos que los citan.

### 1.3 ~~El hallazgo de cobertura inflada de U1~~ — decidido el 2026-10-03

- Al construir U2 se descubrió que la cobertura publicada por U1 (90,05 %) era
  85,83 % real, porque el corredor medía con los archivos de prueba dentro.
- **Decidido:** se queda en el resumen de U2, donde está. Formalizarlo en el
  registro de U1 es reabrir los artefactos de una unidad cerrada para corregir una
  cifra que la compuerta de hoy ya mide bien; lo que vale del hallazgo --cómo se
  descubrió-- está escrito.

### 1.4 La red del entorno de la nube

El crédito de sesiones en la nube (250 USD, vence el 5 de noviembre) ya está
reclamado y funciona, pero ese contenedor solo puede salir a PyPI y a npm, así
que no se puede instalar `mise` y las tandas corren con los comandos a mano.
Se arregla en el editor del entorno → "Acceso a la red", agregando
`mise.jdx.dev`, `github.com` y `objects.githubusercontent.com` a los dominios
permitidos. Es tuyo porque es tu cuenta; el detalle está en
`docs/reference/sesiones-en-la-nube.md`.

### 1.6 El etiquetado de DS-7: tuyo, pero todavía no

Las 40 transcripciones etiquetadas a mano (20 por idioma) son tuyas, y el PRD te
las pone en las semanas 4 y 5. El comando existe y funciona —`mise run
evals:label`, que se puede dejar a medias y retomar— pero **hoy no puedes
empezar**, y conviene que sepas por qué en vez de descubrirlo corriéndolo.

Cada entrada de la cola lleva **un turno que la agente dijo de verdad**. El juez
se calibra contra lo que va a juzgar, no contra texto de ejemplo, así que la
cola solo se puede llenar a partir de una corrida de evaluaciones con
transcripciones — y eso necesita un conductor de canal, que construye **U13
`chat`**.

Revisado el 2026-09-27. Hasta entonces, los criterios que dependen del juez se
publican como "no medida" con esa causa, que es lo que la práctica exige y lo
contrario de omitirlos. El comando te lo dice ahora si lo corres.

---

### 1.12 ~~La agente repite la misma pregunta~~ — cerrado el 2026-09-29

Lo viste ese mismo día: contestaste "No, todos bien", diste tu nombre y tu póliza,
y la agente volvió a preguntar "¿Hubo alguien herido?" dos veces más. **Arreglado**,
con cuatro pruebas de punta a punta que fallan si vuelve.

**La causa era una que no está en el diagnóstico original, y era más sencilla.**
Esta entrada decía que faltaba cablear la confirmación y que "no hay decisión de
diseño pendiente". Lo primero era cierto y lo segundo no. Al mirarlo apareció que
el problema estaba **en el modelo de datos**: `Completeness.per_field` era un
booleano de "cuenta como completo", y con un booleano **no se puede distinguir
"nadie lo dijo" de "lo dijo y falta confirmarlo"**. Esa distinción es exactamente
la que separa preguntar de leer de vuelta, así que no había forma de escribir el
cable sin cambiar antes el dato.

Y había una segunda mitad, todavía más directa: la proyección del turno
(`_con_lo_extraido`) marcaba **completo** cualquier campo recién extraído,
incluidos los tres que exigen lectura en voz alta. En el turno en que se decía, el
nodo pasaba al bloque siguiente; al turno siguiente leía el caso de la base, lo
encontraba solo `stated` --que no cuenta-- y volvía al bloque anterior. Preguntar,
avanzar y volver: lo que se veía en pantalla.

**Qué se decidió, y es lo que no estaba escrito.**

1. **La completitud gana `awaiting_readback`**, aditivo: `per_field` sigue
   significando lo mismo y ningún consumidor suyo cambia. Con eso,
   `missing_fields_in_block` hace por fin lo que su propio docstring prometía
   desde el principio --"nada de lo ya dicho"--.
2. **Un bloque sin nada que preguntar y con algo esperando lectura se lee**, no se
   pregunta. Es el primer consumidor de producción de `confirmation.build_readback`,
   que llevaba desde U11 escrita y probada sin que nadie la llamara.
3. **Un sí confirma; lo que no es un sí es un no, y callar no confirma.** Es el
   mismo reconocedor que la voz usa para un código deletreado, y la misma razón: un
   dato que se anota porque nadie dijo lo contrario es un dato inventado.
4. **Un no devuelve el campo a `NOT_STATED` y sin valor.** La persona acaba de
   decir que lo anotado no es lo que dijo; conservarlo sería guardar un dato que
   nadie dio. Los campos que ese mismo turno volvió a decir no se tocan, porque
   quien rechaza una lectura suele corregirla en la misma frase.
5. **U4 gana una operación: abrir el valor de un campo.** Una lectura tiene que
   **nombrar** lo que confirma (FD-U11-8) y hasta ahora los valores se sellaban y
   nadie los volvía a abrir en producción --el modelo no exponía siquiera la clave
   con la que se cerraron--. Es la puerta simétrica de `set_field`: esta unidad
   cierra al escribir y abre al leer, abre solo las claves que le nombran, y omite
   la que no puede abrir.

**La forma de defecto, otra vez y en otro sitio.** `build_readback` sin llamador es
la sexta vez. Y la prueba que la unidad tenía --"un dato dicho en este turno no se
vuelve a preguntar"-- afirmaba el **mecanismo** (`next_block` cambia de bloque) y
no la regla (no se le vuelve a preguntar); pasaba en verde con el defecto puesto.
Se reescribió para mirar lo que el turno dice.

**Lo que sigue sin hacer, dicho:** un valor que no se puede abrir --clave rotada a
mitad de caso, o dato corrupto-- deja su hueco en la frase de la lectura. Es el
mismo escenario en que el caso entero ya está degradado, y no se construyó
maquinaria para él; queda escrito en `build_readback` en vez de heredarse en
silencio.

### 1.13 El motor del flujo AI-DLC va cinco unidades atrasado

**No afecta al producto.** Es contabilidad del flujo, no código. Ya estorbó dos
veces y por eso ahora trae una decisión tuya al final.

**Qué pasa.** `aidlc engine status` dice que Construcción va por U14 `inbox`, en
la etapa de diseño funcional. En realidad U14 a U18, U21 y U22 están cerradas,
subidas y en verde, y de las cuatro que quedan tres tienen su tanda 1 dentro. El
puntero se quedó atrás el 2026-09-28.

**Por qué.** El motor considera terminada una etapa cuando existen todos sus
artefactos declarados. A U14 le falta uno, `code-summary.md`: su cierre se
escribió como cuatro archivos `hallazgos-tanda-N.md` en vez del resumen que el
motor espera. Con esa etapa sin cerrar, el puntero nunca avanzó, y U15 se
construyó por fuera.

**Qué estorba hoy.** Una sola cosa: el guardián del motor no deja delegar la
escritura de código a un agente para una unidad que no es la que él cree activa.
El 2026-09-29 me bloqueó el arranque de U16 y el 2026-10-02 el de la tanda 2 de
U19; las dos las escribí en la sesión principal. Funciona igual; cuesta más
tokens tuyos por línea, porque las escribo con el modelo caro en vez de
delegarlas al barato.

**Qué haría falta.** Escribir el `code-summary.md` de U14 a partir de sus cuatro
archivos de hallazgos y dejar que el motor camine las etapas pendientes de U14 y
U15 hasta llegar a U16. Son varias idas y vueltas y algunas piden tu aprobación,
así que no lo hago a mitad de unidad.

**Qué haría falta ahora.** Lo mismo, pero más largo: el `code-summary.md` de U14
y caminar las etapas pendientes de U14 a U18 hasta llegar a U19. Son muchas idas
y vueltas y varias piden tu aprobación.

**Qué propongo: no hacerlo.** Quedan tres tandas 2 y las escribo yo aquí, como
las dos de arriba. Arreglar el puntero cuesta aprobaciones tuyas y varias
sesiones de ceremonia para destrabar una delegación que uso tres veces más; los
artefactos de cada unidad están completos y comprobados con
`scripts/check-artifacts.py`, que es lo que de verdad se lee, y el puntero no lo
lee nadie más que el motor. Si prefieres lo contrario, dilo y lo hago de una
sentada antes de la siguiente tanda.

### 1.7 ~~El plazo del turno contra el proveedor de verdad~~ — cerrado el 2026-09-28

Medido: la llamada real de extracción tarda entre **2.892 y 5.300 ms** y el plazo
del nodo de captura eran **1.600 ms**, que es el doble de la meta p95 **de la
voz**. El chat lo heredaba por compartir el mismo `NodeSpec`, y en la primera
conversación que tuviste por la pantalla **dos de tres turnos se degradaron**.

Cerrado tomando la opción (a) que te recomendé, sobre tu "da solución": **un plazo
por canal**. La voz conserva su 1.600 ms —la meta aprobada no se toca— y el chat
lleva 8.000 ms propios, que cubren la llamada más lenta medida y quedan por debajo
del plazo de lectura del proveedor (12.000 ms), para que el que corte siga siendo
el nodo y no el transporte. El número vive en `orchestration/turn.py` con su razón
y su prueba; cambiarlo es una línea si la medida cambia.

Iba con un segundo defecto que lo tapaba: la pantalla no conocía la clave de la
frase de degradación y la convertía en la de error, así que **una degradación y un
fallo se leían igual**. Ver la forma 8 del catálogo de revisión.

### 1.8 El ritmo de fondo: la cobertura ya responde, las reglas y el cierre no

**Cableado el 2026-09-29:** `policy_verification` corre de verdad. Preguntar por
cobertura lanza la verificación contra el corpus de la póliza y el turno siguiente
responde con la cláusula citada. Corre por el ejecutor directo y no dentro de un
grafo compilado, por la misma razón escrita para el nodo de captura: su entrada
depende del caso —el número de póliza y el idioma— y no solo del estado.

**Revisado el 2026-09-30, y la lectura anterior era media verdad.** Decía que esto
es "un hueco de diseño entre U9 y U11, no una línea de cableado". Son **dos huecos
distintos**, y el segundo es cableado:

**1. El cableado, que es código y ya no necesita ninguna decisión.** El grafo de
fondo completo —`policy_verification → decision → compliance`— existe, con su
enrutado y sus puntos de control, y lo cubren las pruebas de integración de U12.
Producción nunca lo compila: `compile_background_graph` aparece en un solo sitio
fuera de su archivo, y es un test. `ComplianceNode` se construye en la raíz de
composición con sus tres puertos **y nunca se le pasa al runtime**: se arma y se
tira.

Y no compilarlo es deliberado, con su razón escrita: el grafo compilado fija la
fábrica de entrada de cada nodo al compilar, y la entrada de `policy_verification`
depende del caso —póliza e idioma—, no solo del estado. Así que la corrección no es
compilar el grafo: es **encadenar los otros dos por el ejecutor directo**, que es
como ya corre la cobertura. La secuencia no se duplica: la decide `transition()`,
que es pura y cerrada y ya existe.

**2. Los seis campos, que sí son diseño — y son menos urgentes de lo que parecían.**
`decision` lee seis campos del vocabulario del motor de reglas, y nadie los produce.
Pero **un campo ausente no dispara, por regla escrita** (BR2.1), así que sin ellos
cada caso cae en la regla por defecto: revisión estándar. Es la salida segura.

Y la primera regla de Knotwell, la agencia, es `always: true` → derivar, y no lee
ningún campo. **Con solo cablear, la agencia recorre el camino entero hoy**: captura,
cobertura con su cláusula citada, decisión con su regla y su explicación, y cierre de
cumplimiento.

De los seis, tres tienen fuente y tres no:

| Campo | ¿De dónde saldría? |
| --- | --- |
| `unlisted_driver` | Comparar el conductor capturado con los de la póliza, que tenemos |
| `other_parties_data_pending` | El bloque de terceros del caso |
| `injuries_present` | El bloque de heridos, que es texto libre: necesita clasificación |
| `claim_amount` | **Ninguna.** El esquema no captura ningún monto y nadie lo pregunta |
| `coverage_disputed` | Ninguna clara: es un juicio |
| `fraud_suspected` | Ninguna clara: es un juicio |

**Cableado el 2026-10-03, y la mitad 1 queda cerrada.** La cadena entera corre:
`policy_verification → decision → compliance`, encadenada por el ejecutor directo y
en el orden que decide `transition()`, la misma función pura que enrutaría el grafo.
Cada nodo deja su punto de control antes de que corra el siguiente, y un nodo que no
termina detiene la cadena sin perder lo ya calculado. **La agencia recorre hoy el
camino completo**: captura, cobertura con su cláusula citada, decisión con su regla y
su explicación, y cierre de cumplimiento.

El grafo compilado sigue sin compilarse, y eso no era lo que faltaba: su fábrica de
entrada se fija al compilar y la de la cobertura depende del caso.

**Decidido el 2026-10-03, y la mitad 2 queda repartida así:**

| Campo | Decisión |
| --- | --- |
| `other_parties_data_pending` | ~~Se deriva de las partes del caso~~ — **cableado el 2026-10-03**. Y son **tres** situaciones, no dos: nadie preguntó (campo ausente, la decisión va a ciegas y la traza lo cuenta), se preguntó y no había terceros (`false`, que es lo que deja cerrar directo un choque de un solo auto), y hay terceros a los que les falta algo (`true`). Colapsar las dos primeras cerraría directo un caso cuyos terceros nadie capturó |
| `unlisted_driver` | El generador declara los conductores de cada póliza y se deriva contra ellos. Aprobado, **pendiente**: es el único de los seis que necesita regenerar el corpus, así que va en su propia tanda |
| `claim_amount` | **La agente no lo pregunta.** Quien acaba de chocar casi nunca sabe cuánto cuesta arreglarlo, así que el campo volvería vacío y las tres reglas que lo leen seguirían sin disparar; y el monto lo estima el ajustador, no el asegurado |
| `coverage_disputed`, `fraud_suspected` | Dos marcas que pone el ajustador en la bandeja, **nunca el modelo**: la categoría la deciden las reglas, y el juicio de un modelo como insumo de una regla es lo mismo con un paso en medio |
| `injuries_present` | Espera su clasificador y, antes, su caso de golden set: es rama evaluada |

El monto entra con las dos marcas, que es la misma forma --tres datos que pone una
persona cuando mira el caso, y la evaluación siguiente los lee-- y van **después de
la pasada de publicación**: con las dos derivaciones de arriba el motor ya dispara
en la captura, así que no bloquean publicar.
Mientras no existan, cada caso cae en la regla por defecto --revisión estándar, la
salida segura-- y la traza lo dice con un evento por decisión, para que «todos los
casos en revisión estándar» no se lea como una propiedad del corpus.

Mientras tanto, una pregunta de cobertura sin póliza identificada —una conversación
que todavía no dijo quién es— responde con la frase de degradación del catálogo y
deja su evento `orchestration.coverage_without_policy`, en vez de prometer una
respuesta que nadie puede calcular.

### 1.9 Un mensaje que llega antes que su flujo se acepta y no se atiende

El navegador abre su flujo de eventos al cargar la página y una persona no le gana
esa carrera, pero si el flujo se cae y alguien escribe, la ruta responde `202` y
el turno no se entrega. Ahora **se ve** (`chat.message_without_stream`), que antes
no. Arreglarlo de verdad choca con una regla escrita: "como mucho un flujo por
pestaña", que hace que abrir un flujo cierre el anterior y descarte lo que tenía
en cola. **Qué decidir:** si el turno se atiende igual (y sus eventos se pierden,
que es lo que ya pasa cuando se cierra la pestaña) o si el mensaje se rechaza con
una frase honesta. Mi recomendación es atenderlo: el caso avanza, que es lo que
importa.

### 1.11 Lo que el arnés ya no comprueba en tu máquina

Decisión tuya del 2026-09-29: **un motor en local, tres en la tubería**. En tu Mac
el arnés corre Chromium y ejecuta las 79 pruebas en 39 s; en GitHub Actions se le
suman Firefox y WebKit con las de dibujo y son 109, que es el número de siempre.

Lo que **dejas de ver en local** es si una pantalla se dibuja distinto en Safari o
en Firefox. Eso sigue bloqueando en cada entrega, así que no se te puede colar a
producción; lo que cambia es cuándo te enteras: en la tubería y no al correr el
guion. Si alguna vez tocas algo visual delicado y quieres verlo antes de empujar:

```bash
CI=1 mise run a11y
```

El presupuesto de PERF-U6.3 (240 s) solo bloquea donde se mide entero, que es la
tubería: en local con un motor sobraría siempre, y un límite que nunca puede fallar
no vigila nada. La cifra que imprime el guion dice ahora con cuántos motores se
midió, para que no se comparen dos números distintos.

### 1.10 El idioma de Knotwell y Sunmeadow, y lo que ve quien escribe en español

Knotwell y Sunmeadow tienen `default_language: en`; solo Stonecroft arranca en
español. La conversación conserva su idioma cuando el turno no trae señal
suficiente —menos de un mínimo de palabras, o confianza por debajo del umbral—,
que es la regla aprobada (BR2.2) y está bien escrita.

El efecto en pantalla es el que viste: escribiste "Hola", "Me he accidentado" y
"No" a Knotwell, ninguna llegó al umbral, y la agente contestó en inglés todo el
rato. El encabezado lo dice —"Respondiendo en English"— así que no engaña, pero
**quien evalúe el proyecto probablemente escriba corto y en español**, y la primera
impresión será una agente que no le sigue el idioma.

- **Por qué no lo toco:** es diseño y es cómo se presenta el producto, que es tu
  excepción. Además hay tres salidas legítimas y eligen cosas distintas.
- **Qué decidir:** (a) las tres aseguradoras arrancan en español y cambian al
  inglés cuando hay señal —simple, y el inglés se sigue demostrando—; (b) el idioma
  de la conversación lo fija el selector de la pantalla, que la persona ya ve;
  (c) dejarlo, porque tres aseguradoras con idiomas distintos **es** parte de lo
  que se demuestra. Mi recomendación es la (b): el selector está ahí, la persona
  ya lo usó para leer la página, y es la única que no le pide adivinar nada.

### 1.14 ~~Dos decisiones de diseño, una por unidad~~ — cerradas el 2026-09-30

Escribí los diseños de las cuatro unidades que faltan y sus cuatro encargos de tanda 1.
Dos preguntas quedaron abiertas y **las dos las contestaste con la opción A**: quedan
aquí con lo que cada una decidió y con el compromiso que acepta.

**U23 `comparison-view` — la divulgación.** AC2.9.1 pide que la vista diga, antes de la
primera pregunta, qué es y **qué póliza de ejemplo usa cada columna**, algo que ninguna
apertura de aseguradora dice. Pero la vista habla por las tres rutas del chat, y el chat
entrega **su** apertura en el primer mensaje de cada conversación. Y una pregunta de
cobertura **abre un caso**, así que no mostrar la apertura dejaría tres casos sin su
divulgación registrada, que AC1.1.2 prohíbe.

**Elegiste A:** la divulgación es la de la vista y **queda registrada en los tres casos**
como entregada por esta superficie. Las columnas muestran respuestas y nada más. El chat
aprende de qué superficie viene la conversación —un parámetro aditivo, no una ruta
nueva— y eso vive en la tanda 2, porque registrar la divulgación toca la base.

**U20 `demo-operations` — qué pasa con lo abierto cuando el reinicio falla.** AC5.15.5
dice que sin un reinicio exitoso en 24 horas el chat y la voz dejan de aceptar **casos
nuevos**. No dice qué pasa con lo que ya está abierto.

**Elegiste A:** lo abierto termina normalmente y solo se dejan de aceptar casos nuevos.
El compromiso que eso acepta queda escrito en la regla: los datos de esa conversación se
quedan una noche más, y lo que mantiene la ventana acotada es que la alerta ya salió y el
reintento sigue corriendo. La demo se estrecha en vez de caerse.

---

### 1.15 ~~Tres tandas por revisar~~ — cerrada el 2026-09-30

**Las cuatro están revisadas y en `main`** (`5fa7636`). Quedó así:

| # | Rama | Unidad | Estado |
| --- | --- | --- | --- |
| 1 | U23 tanda 1 | `01f832d` | El puerto podía inventar un emisor: invariante fijado |
| 2 | U17 tanda 1 | `efe34cc` | Dos errores de mi diseño, corregidos; y la disponibilidad sin `.catch` |
| 3 | U20 tanda 1 | `71fb1f0` | Tres roturas mías, las tres cayeron. Ninguna prueba hubo que corregir |
| 4 | U19 tanda 1 | `1d5c21d` | La voz ofrecía cotizar y no puede. Puso `main` en rojo por una prueba que se apoyaba en que `quote_request` estuviera vacío (`5fa7636`) |

**Dos rojos de `main` salieron de estas revisiones, y los dos son míos.** Uno por correr
siete compuertas en vez de once —`tenancy:literals` era una de las cuatro que salté—, y
otro por no buscar quién se apoyaba en que `quote_request` estuviera vacío cuando U19 lo
llenó. Las dos lecciones están en el catálogo de revisión, formas 13 y 14.

**Dos defectos de mi diseño que U17 encontró, ya corregidos en sus documentos:**

- La tabla de topes del proveedor **ya existía** (`ProviderCapConfig` en `prices.yaml`,
  de U5, con fecha obligatoria). `entities.md` y TECH-U17.4 la describen como nueva.
- Los dos carriles diarios **no son de una aseguradora**: "quince llamadas del sitio"
  escrito en tres carpetas son cuarenta y cinco. Viven en `VoiceLimits`
  (`providers.yaml`), que ya los declaraba. FD-U17-2 decía lo contrario.

**Y dos riesgos que U19 trae, que son de producto y no de la tanda:**

- **Sunmeadow ofrecería cotizar sin poder terminar.** Tras la captura la agente dice que
  revisa y avisa, pero el cableado del grafo de fondo y la bandeja del suscriptor no
  existen: `compose_eligibility_reply` está escrita, probada, y **nadie la llama**.
- **La voz también ofrecería cotizar**, porque `voice/opening.py` lee `quote_enabled`, y
  la voz no abre solicitudes: solo el chat.

**Resueltas distinto de como las planteé, y cada una por su lado.** La de la voz no
esperaba a nada: ese canal no captura solicitudes ni después de la tanda 2, así que su
apertura dejó de ofrecerlo, con su prueba. La del chat **no se arregla apagando la
bandera** —hoy nada está publicado, y apagarla costaría rehacer las expectativas de DS-4,
que leen la configuración real—: quedó como criterio **bloqueante** de la pasada de
publicación, donde ya viven los otros cinco de su clase.

---

### 1.16 ~~La voz firma dos cosas distintas con la misma clave~~ — cerrado el 2026-10-03

**Lo encontró la tanda 2 de U17 al emitir el enlace del caso.** `Settings` declaraba
dos claves de firma y documentaba la del enlace de caso como «distinta de la
anterior»; la raíz de composición le pasaba **esa misma** a la voz, que la usaba
para firmar su token de socket. Rotar la clave del enlace invalidaba los sockets de
voz vivos, y un compromiso de esa clave abarcaba las dos superficies.

**Cerrado con la clave que pusiste en tu `.env`.** `UNTANGLE_VOICE_TOKEN_SIGNING_KEY`
es la tercera: está en `Settings`, en `.env.example`, y la raíz se la enchufa al
token de socket.

**La mitad que no estaba en el enunciado, y es la que podía salir mal.** Esa misma
ruta de la voz firma **dos** cosas: el token de socket y el enlace de caso que
entrega al colgar. Separar la clave sin separar los dos campos habría firmado el
enlace con la clave de la voz, y la bandeja lo habría rechazado al canjearlo —con
la misma forma `/c#…` de siempre, así que la comprobación que había no lo habría
visto. `VoiceDeps` lleva ahora los dos campos con su nombre, y hay dos pruebas que
se caen por separado: una canjea el enlace de verdad y exige que la clave de la voz
**no** lo abra; la otra verifica el token que el navegador recibe contra las dos
claves. Rompiendo cada cableado cayó la suya y solo la suya.

**Qué significa para el despliegue:** son tres variables de entorno y no dos. La de
la voz se rota sola, sin tocar los enlaces de caso.

---

### 1.17 ~~Nadie guarda en qué turno se derivó~~ — cerrado el 2026-10-03

**Lo encontró el cableado del ritmo de fondo.** La revisión completa de cumplimiento
necesita saber **en qué turno salió la frase de derivación**: es lo que decide si una
petición de persona se derivó en el turno siguiente, que es una de sus cuatro
comprobaciones (BR5.1 de U10).

Ese turno no está registrado en ningún sitio. Ni la fila de la pausa ni el historial
del caso lo guardan: los dos saben que el caso se derivó y por qué, y ninguno sabe
cuándo en la conversación.

**Las dos formas de inventarlo son peores que no revisar**, y por eso el cableado no
inventa ninguna: con el último turno, la revisión **absolvería** una derivación que
llegó tarde; con nada, **acusaría** de no haber derivado a un caso que sí se derivó.
Un hallazgo falso en una compuerta de cumplimiento es peor que una compuerta que
declara no haber corrido.

Así que hoy un caso ya derivado **no recibe su revisión de cumplimiento**, y la
cadena lo dice con su evento. La consecuencia que hay que ver: U14 no deja cerrar un
caso sin esa revisión, así que un caso derivado se queda esperando.

**Resuelto el 2026-10-03, con tu aprobación, y no en la pausa.** El dato vive donde
se crea el hecho: una columna del caso, escrita por la misma transición que escribe
el motivo, que es la puerta única por la que pasa toda derivación. La pausa se
resuelve cuando la decisión aterriza y no toda derivación abre una, así que el dato
tenía que sobrevivirla.

**Y resolverlo dejó a la vista dos cosas que no sabíamos**, las dos arregladas en la
misma tanda:

- **La transcripción del caso tenía un solo lado.** Ninguna línea del aplicativo
  escribía un turno de la agente: el chat persistía el del visitante y nada más. Por
  eso el control de la ruta humana de la revisión no podía pasar nunca --busca «el
  turno de la agente siguiente a la petición»-- y la evidencia de cierre prometía la
  mitad. Los casos sembrados sí traen los dos lados, que es por lo que la bandeja
  parecía funcionar.
- **Una petición de persona no derivaba el caso.** Abría la pausa, publicaba la frase
  y el caso se quedaba en captura; la cola del ajustador excluye ese estado a
  propósito, así que **quien pedía hablar con alguien no llegaba a la bandeja de
  nadie**, y el aviso de «alguien lo está revisando» que el chat sabe decir no se
  podía decir nunca.

Queda abierto solo lo que no ocurre en un turno --el botón de la consola de voz, la
decisión de la bandeja--: ahí no hay frase que acotar y la revisión lo dice en vez de
inventar un límite.

---

### 1.18 ~~La voz no guarda ningún turno del caso~~ — cerrado el 2026-10-03

**Lo encontró el arreglo de 1.17**, buscando quién escribía la transcripción. La
respuesta completa: el chat escribía la mitad (ya escribe las dos) y **la voz no
escribe nada**. `case_transcript_turn` solo la llena `append_turn`, y por el camino
de la voz nadie la llama.

Lo que eso significa para una llamada:

- su caso queda **sin transcripción**, así que la revisión de cumplimiento no se
  puede acotar --no hay turno hasta donde llegar-- y sin esa revisión U14 no deja
  cerrar el caso;
- su evidencia de cierre promete la transcripción y no hay ninguna;
- la bandeja muestra el caso de una llamada sin una sola palabra de lo que se dijo,
  que es justo lo que el ajustador necesita leer.

Hoy no se nota porque la voz no está publicada y sus casos son de prueba.

**Qué haría falta:** que el ciclo de la llamada anexe el turno final de cada lado
--el del asegurado cuando el reconocedor cierra su frase, el de la agente cuando
termina de hablar-- con su canal `voice` y por el punto único de redacción, igual que
el chat. No es pequeño: toca el ciclo del turno de voz, que es el camino con
presupuesto de latencia más estricto del proyecto, así que la escritura va fuera del
turno (en el ritmo de fondo) o se mide antes de meterla dentro.

**Cerrado el 2026-10-03, y la decisión de diseño fue dónde vive la regla.** La
llamada escribe sus dos lados con el canal `voice`, y la escritura va **fuera del
turno** —lanzada al ritmo de fondo— porque este es el camino con el presupuesto de
latencia más estricto del proyecto: una escritura a la base dentro de él gastaría
del tiempo que va del fin del habla al primer audio.

Lo que no se hizo fue copiar las dos funciones del chat al ciclo de la voz, que era
lo fácil. Eso son **dos guardias para la misma regla**, y el catálogo de revisión de
este proyecto ya tiene escrito lo que pasa: el día que una cambie, la otra seguirá
diciendo lo de antes. La regla vive ahora en un solo módulo y los dos canales la
llaman; lo que cada canal conserva es **cuándo** llama, que son momentos distintos
de dos ciclos distintos.

**Y una prueba movió el código.** La anotación estaba detrás de la comprobación de
confianza, así que un turno que el reconocedor oyó mal no quedaba escrito —
exactamente los turnos que un ajustador necesita leer para saber por qué se le
repreguntó a alguien. Ahora se anota antes. Un silencio sigue sin dejar línea: anotar
la vacía dejaría la transcripción contando silencios como si fueran frases.

---

### 1.5 Lo que no es de este intent, pero también es tuyo

Estas dos pertenecen al intent `infra` y no a este. Es cuestión de **cuándo**, no
de quién: en este proyecto no hay nadie más.

- **PA-10** — el canal por el que sale la alerta de los 3 USD, el origen del
  chequeo periódico que llama a la salud de U6 cada cinco minutos, y el
  disparador nocturno.
- **OQ4** — el hospedaje. **Decidido el 2026-10-03**, con la exigencia que lo
  fijó: la demostración existe para que alguien evalúe tu trabajo, y una espera
  al entrar es el fallo que no se puede permitir. Ejecutarlo sigue siendo del
  intent `infra`.

  | Pieza | Dónde | Por qué |
  | --- | --- | --- |
  | Landing (`site/`) | Vercel, como hoy, en `untangle-ai.vercel.app` | Sale del CDN, instantánea, y ya está hecha |
  | Interfaz del aplicativo | **El mismo proceso del aplicativo**, no Vercel | `app/frontend/dist/` lo sirve el backend (CG-U6-5). Es deliberado: la interfaz, la API y el socket de voz comparten **un solo origen**, que es lo que hace que la galleta del visitante viaje en el apretón de manos del WebSocket. Separarla obligaría a galletas entre sitios y a CORS, en la demostración cuyo argumento es el aislamiento bien hecho |
  | Aplicativo | **Oracle Always Free** | Es la única opción gratuita que **no se duerme**: una máquina encendida, sin arranque en frío que medir. Y una cuenta Always Free no puede facturar: se queda sin recursos en vez de cobrar |
  | Base de datos | **Neon**, plan gratuito | Postgres de verdad con pgvector y aislamiento por fila; **no factura excedentes**: cuando te pasas, las escrituras fallan |
  | Plan B | **Cloud Run + Neon** | Si Oracle no da capacidad ARM, que falla a menudo. Pide tarjeta, así que lleva el interruptor de facturación documentado por Google (alerta → Pub/Sub → función que apaga la facturación del proyecto), porque la alerta sola avisa mientras el gasto sigue |

  **Lo que hay que medir antes de aprovisionar nada**, porque de los dos números
  dependen las dos opciones: cuánta **memoria** consume el contenedor real en
  reposo, y cuánto tarda en **arrancar en frío**. El primero decide el tamaño de
  la instancia de Oracle --y con él si la regla de recuperación de instancias
  ociosas aplica--; el segundo decide si el plan B cumple la exigencia. Son dos
  mediciones, no un despliegue.

  **Dos riesgos de Oracle, nombrados:** recuperan las instancias cuyo CPU (p95),
  red **y** memoria estén los tres por debajo del 20 % durante 7 días, que es lo
  que parece una demo de portafolio; como las tres condiciones tienen que darse a
  la vez, una instancia más pequeña deja la memoria por encima del umbral y la
  regla no aplica --es consecuencia de la política, no una práctica
  documentada--. Y en junio de 2026 recortaron el cupo ARM de 4 núcleos / 24 GB a
  2 / 12, que sigue siendo de sobra pero hace la capacidad más escasa.

  **Lo que esto le hace a la página de espera de U6:** deja de ser el camino
  normal y pasa a ser la red de seguridad. Su presupuesto de 3 segundos no se
  toca; lo que cambia es que con una instancia encendida no debería verse nunca.
  Y la llamada de calentamiento al cargar la página sigue valiendo la pena: es lo
  que hace invisible un arranque de segundos si algún día se cae al plan B.

Y una de la semana 12: **revisar las licencias de dependencias y recursos**
antes de decidir si el repositorio se publica (D-017). Desde U6, las de la
interfaz están en `app/frontend/DEPENDENCIES.md`.

---

## 2. Cerrado el 2026-09-27

- **El modelo de español de spaCy es GPL-3.0** y se queda. Lo encontró el control
  de licencias nuevo, no la revisión a mano: los dos modelos entran por un extra
  con su URL y no aparecen en el árbol de dependencias que uno lee. No bloquea
  publicar el repositorio —el modelo no está en él, se descarga al instalar— y lo
  que sí toca queda dicho: quien empaquete el aplicativo con el modelo dentro
  distribuye un trabajo combinado y hereda la obligación. El registro entero, con
  la frase que el README de U22 tiene que llevar en los dos idiomas, está en
  `docs/reference/licencias-de-terceros.md`. Se descartó cambiar de modelo: los
  corpus de dependencias del español arrastran la misma licencia y el detector es
  un módulo crítico con compuerta dura que habría que volver a medir.
- **El presupuesto de tokens del turno se mide con el número del proveedor.**
  `usageMetadata.promptTokenCount`, que el adaptador de U5 ya lee gratis en cada
  respuesta y registra por nodo en la traza; se publica desde la primera corrida
  con el conductor de chat de U13, y hasta entonces se reporta como "no medida"
  con esa causa. La cuenta sin red que escribió la tanda 2 se queda como guardia
  previa —si un prompt ya no cabe ahí, no cabe— con su límite escrito: estimaba
  **por debajo**, no por encima, y el módulo afirmaba lo contrario. La enmienda
  está en `construction/u11-intake/nfr-requirements/performance-requirements.md`.
  Se descartó instalar un tokenizador: aproximaría lo que el proveedor ya dice.

## 3. Cerrado el 2026-09-21

- **Muestras de U7 revisadas:** las diez cláusulas de Stonecroft y las diez de Sunmeadow pasaron (texto propio y estructura respetada). U7 quedó cerrada.
- **Plan de Claude y ritmo de trabajo.** Sigues en Max, porque la renovación se cobró sola, pero el límite semanal es el cuello de botella. Desde U9, el agente de código usa Sonnet, los comentarios nuevos van solo donde la razón no es obvia, y la suite completa corre una vez por tanda. Ninguna compuerta cambia (DP-13, enmienda). Ya no hace falta avisar del cambio de plan.
- **Catalina oída desde el aplicativo** (demostración de B18 de U15). Con
  `mise run voice:say` confirmaste que suena como la voz elegida a ciegas;
  gastó 54 caracteres, 0,0027 USD a precio de lista.
- **Saldo de Deepgram leído en la consola:** 199,92 USD de crédito, plan Pay As
  You Go, con la recarga automática apagada. Quedó en la fila de tope de
  `app/config/providers/prices.yaml`.
- **Frases de U10 escritas sin un criterio que las fijara** (derivación en
  inglés, degradación y hallazgos para la bandeja): las leíste y se quedan como
  están.
- **Los dos formularios de referencia descargados** en `tmp/specimens/`, que
  git ignora, con tu autorización:
  - la edición de 1994, PP 00 01 06 94, que publica el regulador de Maine (79 KB);
  - la edición de 2018, PP 00 01 09 18, en la copia que publica CURE Auto
    Insurance (163 KB).

  El regulador de Virginia bloquea el acceso desde tu país, así que se usó la
  copia de CURE de la misma edición.
- **U5 cerrada.** El recibo de revisión no hacía falta para cerrar la unidad; lo
  pide la compuerta de la etapa, más adelante.
- **Las cuatro claves de Gemini**, una por proyecto.
- **Cuentas en Deepgram y en Cartesia**, en plan gratuito.
- **Experimento 1, corrido.** Hallazgo: transcripción y voz ya suman unos 449 ms,
  así que el modelo no puede ir entre el fin del habla y el primer audio en
  ningún plan; el primer audio sale de una frase de espera ya sintetizada (ADR-008).
- **Precios de lista de la voz**, leídos de las páginas públicas y cargados en
  `app/config/providers/prices.yaml`.
- **Voz principal: Catalina, definitiva.** Tus dos escuchas a ciegas y la
  comparación con la página oficial de Cartesia la confirmaron (ADR-008).
- **Voz de respaldo: Aura-2 de Deepgram.** Kokoro no se mide (ADR-008).
- **Orden de las unidades.** U6 se renombró `u06-web-shell` para construirse
  primero; el resto sigue el orden de la herramienta, que construye el motor de
  voz (U15) en segundo lugar y el chat dos unidades antes que la llamada
  (bolt-plan.md, DP-11).
- **El bloque de voz se queda.** No se corta: se construye en ese orden. La
  regla de corte del PRD sigue disponible solo si hace falta más adelante.
- **El núcleo ahora, lo de publicar después.** U17, U20 y U22 pasan al final y cada unidad difiere lo que solo importa al publicar; el chat llega en la unidad 9 y la voz en la 11 (bolt-plan.md, DP-14; lista en `pasada-de-publicacion.md`).
- **Construcción en modo ligero.** Sin revisión automática por etapa, profundidad
  mínima y sin las etapas de diseño de calidad e infraestructura; ninguna
  compuerta baja (bolt-plan.md, DP-12; `project.md`, Decided).

---

## 4. Decisiones que tomé por ti y puedes revertir

Bajo tu delegación del 2026-09-21. Ninguna está escondida: todas están en el
registro del flujo con su fecha y su razón.

- **El presupuesto de tokens por turno.** La meta de costo de D7 **no se movió**;
  lo que se corrigió fue la estimación de ADR-006, que no contaba los tokens de
  salida. Queda en 3.800 de entrada y 30 de salida por turno.
- **El techo cierra ante gasto facturable sin precio.** Antes se podían cruzar
  los 5 USD con el estado diciendo que todo va bien.
- **Una llamada de grabación sin precio ya no cierra el carril público.** Sin ese
  arreglo, la primera grabación de la semana 12 apagaba el chat y la voz públicos
  durante el resto de la ventana de 90 días.
- **Las respuestas de diseño de U6** (qué muestra el inicio sin canales, idioma de
  la primera visita, qué es una sesión para la activación, navegadores, los 3
  segundos en teléfono y el presupuesto del arnés): cada una con su razón en los
  archivos de preguntas de `construction/u06-web-shell/`.
- **La regla de seguridad apagada en el cliente HTTP generado**
  (`detect-object-injection`, solo en `client/` y `core/`), con sus 21 hallazgos
  revisados y la razón escrita al lado en `app/frontend/eslint.config.ts`.
- **El historial del chat muestra el número del caso bajo el título y una nota
  sobre la redacción** (2026-10-06). El número es lo que la persona puede anotar
  para retomar desde otro navegador; la nota evita que «[PÓLIZA 1]» parezca un
  error. Las dos frases están en `chat.page.case_number` y
  `chat.page.history_restored`, y se quitan borrando su uso en `chat-page.tsx`.
- **El pie se queda en la pantalla del chat aunque la ventana llene la vista**
  (2026-10-06). Ocultarlo daría más alto a la conversación en teléfono; se dejó
  porque es donde se dice que es una demostración con datos sintéticos. Se
  cambia en `Frame`, con el mismo `fill`.
