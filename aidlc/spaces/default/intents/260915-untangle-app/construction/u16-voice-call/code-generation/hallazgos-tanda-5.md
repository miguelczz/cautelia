# Revisión de la tanda 5 — U16 `voice-call`

"Las rutas, el contrato y la composición". Tres rutas de C-08, el socket de C-29,
la superficie pública del módulo, el ciclo de la llamada y 248 pruebas.

Es la tanda que le da **llamador de producción** a lo que las cuatro anteriores
dejaron construido: `CallEngine`, `session`, `tokens`, `wire`, `case_opening` y
`latency.first_audio` no los llamaba nadie hasta hoy.

## 1. Lo que se rompió, y qué se cayó

Once roturas, **las once tumbaron una prueba de conducta**. Todas deshechas.

| Regla | Qué se rompió | Qué se cayó |
| --- | --- | --- |
| BR1.5 | El motivo del rechazo sale en el código de cierre | `test_los_cuatro_tokens_malos_cierran_igual` (los cuatro casos) |
| BR1.4 | El token no se verifica | `test_los_cuatro_tokens_malos_cierran_igual` (los cuatro casos) |
| BR1.1 | La disponibilidad ignora el techo de gasto | `test_un_presupuesto_ilegible_cierra_la_voz_y_manda_una_clave` |
| CD-10 | Colgar no comprueba de quién es la llamada | `test_un_identificador_inventado_responde_igual` |
| P7 | Los carriles diarios salen con un número | `test_los_carriles_diarios_salen_nulos_porque_nadie_los_aplica` |
| BR7.2 | La transcripción sale sin redactar | `test_la_transcripcion_sale_redactada_hacia_la_consola` |
| BR4.3 | No se manda la orden de vaciar la cola | `test_interrumpir_manda_stop_audio_y_la_apertura_llega_a_terminar` |
| BR4.5 | Lo que interrumpió vuelve a la cola de escucha | `test_interrumpir_manda_stop_audio_y_la_apertura_llega_a_terminar` |
| BR6.1 | Colgar también deja el caso retomable | `test_un_corte_deja_el_caso_retomable_y_colgar_no` |
| BR6.4 | Llamar por otro accidente no abre caso nuevo | `test_decir_que_llama_por_otro_accidente_abre_un_caso_nuevo` |
| BR3.3 | El contrato de importación deja de vigilar la voz | `test_el_canal_de_voz_no_puede_importar_el_framework_del_grafo` |

## 2. La prueba de aislamiento que no aislaba nada

La primera versión de `test_la_llamada_de_otro_navegador_responde_como_una_que_no_existe`
abría una llamada con un cliente y la intentaba cerrar con otro. Pasaba en verde.
**También pasaba en verde con la comprobación de a quién pertenece la llamada
quitada**, y eso se comprobó rompiéndola.

La causa: el segundo cliente llegaba sin galleta, así que no había clave de
visitante que resolver y la ruta respondía 404 por *eso*, no por aislamiento. La
prueba medía "un navegador sin identidad no cierra nada", que es cierto y no es
la regla.

El arreglo es una línea: el segundo navegador **abre su propia llamada** antes de
intentarlo. Con identidad propia y llamada propia, lo único que lo separa de la
llamada ajena es la comprobación, y romperla la tumba.

Es la forma 2 del catálogo —la aserción que no puede distinguir— y en esta tanda
apareció en la prueba de una compuerta de aislamiento, que es el peor sitio
posible.

## 3. Tres defectos de verdad que salieron al cablear

**El bucle infinito de la apertura interrumpida.** BR4.5 dice que una apertura
cortada se repite entera. La primera versión devolvía el transcrito que
interrumpió a la cola de escucha; la apertura se repetía, volvía a encontrar el
mismo transcrito, y se interrumpía otra vez. Para siempre, con el proceso vivo y
sin un solo error en ningún log. Lo que lo destapó fue una prueba que se colgó,
no una que fallara.

Ahora el transcrito se guarda para el turno siguiente y el detector lo escucha al
abrirse. Que la frase con la que alguien corta a la agente **no se pierda** es la
mitad que no se ve mirando solo el `stop_audio`: callarla y después no oír lo que
dijo obliga a la persona a repetirlo, que es justo lo que interrumpir existe para
evitar.

**Lo que interrumpe no aparecía en la consola.** La misma frase se usaba para
decidir que había interrupción y después se descartaba, así que la persona veía
su propia corrección desaparecer justo cuando la dijo. Se pinta ahora, y lo que
se sigue descartando es el ruido que **no** interrumpe, que es lo correcto.

**Los cuadros de control salían en binario.** El transporte mandaba todo por
`send_bytes`: el JSON de un `stop_audio` habría llegado a la consola como
muestras de audio y se habría reproducido. Es el único rasgo que distingue
control de audio en el cable (C-29) y estaba perdido. Hay prueba.

## 4. Dos conjuntos cerrados gemelos, uno de más

`voice/models.py` declaraba su propio `VoiceMode` con los mismos dos valores que
el de la contabilidad, que es su dueño de verdad: quien elige el modo es U17 con
`reserve_primary_voice` (C-17), y la plataforma de voz de U15 ya recibe **ese**.

Dos conjuntos gemelos no se rompen el día que nacen: se rompen el día que uno
gana un tercer valor, y entonces la conversión en la frontera lo traduce a un
error en producción o —peor— lo redondea al que más se parezca. Ahora se importa.

## 5. Decisiones tomadas al escribir

1. **Tres desviaciones de C-08, dichas en la cabecera del módulo.** La ruta sigue
   la forma de las nueve construidas (`/api/voice/{tenant}/...`) y no la del
   boceto; el cuerpo de abrir **no admite `case_id`**, porque aceptarlo dejaría
   que quien llama nombre un caso ajeno —el criterio `[bloquea]` AC1.27.3—; y los
   carriles diarios salen nulos porque hoy no los aplica nadie.
2. **El campo sobrante se rechaza, no se ignora.** Mandar `case_id` responde 422
   y no abre ninguna llamada. Ignorarlo habría dejado a la consola creyendo que
   la retoma se pide así.
3. **El ciclo va en su propio archivo.** Las rutas son tres verbos y sus códigos;
   el ciclo es una conversación con tres relojes a la vez. Juntarlos daría un
   archivo donde el apretón de manos y el turno hablado se leen como si fueran la
   misma clase de cosa.
4. **El transporte, la voz y el socket entran por puertos.** `CallChannel`,
   `CallVoice`, `VoicePlatform` y `Socket`. No es indirección: es lo que permite
   probar la llamada entera con los dobles de esta unidad —que heredan de los
   `Protocol` de C-16— sin construir un cliente, sin red y sin servidor.
5. **La cola de audio está acotada a cinco segundos.** Es la mitad de D1 que se
   paga aquí: el transporte es TCP, así que en una red mala no se pierden
   paquetes, se **acumula retraso**. Una cola sin límite convertiría ese retraso
   en memoria y en una agente que contesta a lo que se dijo hace medio minuto.
6. **`switch_case` es una escritura nueva y nombrada.** `attach_case` sigue
   escribiendo solo sobre nulo: esa guarda existe contra que el grafo abra un
   segundo caso sin que nadie lo pida, y aflojarla habría tapado justo lo que
   vigila. Llamar por otro accidente es un camino distinto, con su regla escrita.
7. **La divulgación se registra también contra el caso nuevo.** Sin eso, el caso
   con el que la llamada termina no tendría divulgación registrada y BR2.1
   quedaría rota por la puerta de atrás, con la compuerta en verde porque mira el
   caso viejo. Hay prueba que consulta la fila.
8. **El techo se lee con la misma función que la compuerta de U15**
   (`ceiling_closed`), para que la respuesta de disponibilidad y lo que pasará de
   verdad con la primera llamada no puedan discrepar. Un fallo de lectura cierra,
   igual que allí.

## 6. La superficie no se monta hasta que exista su pantalla

`voice_console` se monta en la tanda 6, con la consola. El inicio dibuja el botón
de una superficie en cuanto está montada (U6 ya lo tiene construido), y ese botón
llevaría hoy a una ruta que la interfaz no tiene. Es literalmente lo que prohíbe
la regla del proyecto: no se ofrece una capacidad que no está construida.

La sonda de esa superficie nace con ella, en el mismo cambio, por la otra regla
de esta unidad: una función sin llamador de producción es la forma de defecto que
más ha costado aquí, y escribirla una tanda antes de su uso sería repetirla a
sabiendas.

## 7. Los tres textos sin criterio aprobado, ahora aprobados

Tres frases de la agente no salían de ningún criterio: las escribí yo. Miguel las
leyó las tres y las aprobó el 2026-09-29. **Quedan cerradas y no se vuelven a
preguntar**; cambiarlas más adelante es editar el catálogo, no el código.

| Clave | Frase | De dónde venía |
| --- | --- | --- |
| `voice.silence.farewell` | "Le dejo el caso guardado. Que esté muy bien." | Tanda 2 — la despedida del tercer silencio |
| `voice.retry.not_understood` (es) | ~~"Perdón, no le entendí. ¿Me lo repite?"~~ → **"Perdón, no le escuché bien, ¿me repite?"** | Tanda 2 — ver la corrección de abajo |
| `voice.notice.time_running_out` | "Ya estamos cerca del límite de tiempo de la llamada. Le guardo el caso antes de que termine." | Esta tanda — el aviso de duración máxima |

Ninguna promete otra llamada ni da un plazo, que es lo que la guía de voz prohíbe
y lo que hacía falta comprobar antes de llevárselas.

**Corrección del 2026-09-29, y es mía.** De las tres, una **sí tenía criterio**:
AC1.29.3 la fijaba, en las historias de U18, que no había leído al llevárselas. Se
la presenté a Miguel como escrita por mí y la aprobó sobre esa base. Al diseñar
U18 apareció la discrepancia, se le llevaron las dos frases y eligió la del
criterio. El catálogo dice ahora **"Perdón, no le escuché bien, ¿me repite?"**, y
dice mejor lo que pasa: el problema fue del oído --el reconocedor no entendió-- y
"no le entendí" se puede leer como que lo dicho no tenía sentido.

Lo que esto enseña no es sobre la frase: **antes de llevar un texto como propio
hay que buscarlo en los criterios de las unidades que faltan**, no solo en los de
la que se está construyendo. Una frase de voz en español vive en la unidad del
español, que entonces no existía ni como carpeta.

## 8. Lo que no se debilitó

Ninguna prueba existente relajada ni borrada. Ningún umbral ni piso de cobertura
bajado. Ninguna compuerta dura saltada. Dos supresiones del linter nuevas, cada
una con su razón escrita al lado: la captura amplia del ciclo —cualquier fallo
termina la llamada con su motivo, y una lista de tipos dejaría escapar el
siguiente con él un socket colgado— y la espera del doble de voz en las pruebas.

## Sources

- `code-generation-plan.md` — tanda 5
- `../functional-design/functional-spec.md`, `rules.md`
- `../../../inception/contract-design/contract-summary.md` — C-08, C-29, C-01
- `docs/reference/como-se-revisa-el-codigo.md`

## Assumptions & Open Questions

None.
