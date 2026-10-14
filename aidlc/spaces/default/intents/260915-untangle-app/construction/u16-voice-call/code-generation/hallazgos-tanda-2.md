# Revisión de la tanda 2 — U16 `voice-call`

"La apertura, el turno y los silencios". Siete módulos nuevos, veinte claves de
catálogo en dos idiomas y 123 pruebas.

## 1. Lo que se rompió, y qué se cayó

Once roturas. **Diez tumbaron una prueba de conducta. Una no**, y esa es el
hallazgo de esta tanda.

| Regla | Qué se rompió | Qué se cayó |
| --- | --- | --- |
| BR2.1 | Se quita la guarda de la divulgación en `speak_turn` | `test_ningun_turno_se_atiende_antes_de_la_apertura` |
| BR2.3 | Se registra la hora de empezar en vez de la de terminar | 2 pruebas del registro |
| BR3.1 | La marca del fin del habla pasa a ser la del vencimiento | `test_la_marca_es_la_del_ultimo_final...` y `test_subir_la_tolerancia_no_empeora_la_marca` |
| BR3.2 | El turno se entrega con `channel="chat"` | `test_el_turno_llega_al_grafo_por_el_mismo_contrato_que_el_chat` |
| BR3.4 | Una transcripción vacía se da por entendida | 3 pruebas de la escalera |
| BR3.6 | Se quita la rama de `Waiting` de la forma hablada | El comprobador de tipos **y** `test_los_cinco_eventos_de_c14_tienen_forma_hablada` |
| BR5.2 | La escalera de silencios cambia de orden | 3 pruebas |
| BR5.3 | La frase del segundo silencio ofrece devolver la llamada | 2 pruebas, una por idioma |
| BR8.1 | El turno deja de emitir el fin del habla | `test_cada_turno_deja_el_evento_de_fin_del_habla...` |
| **BR3.8** | **Se deja de redactar lo que se va a sintetizar** | **Nada. Ver abajo** |

## 2. El hallazgo: BR3.8 no estaba protegida

La regla dice que ningún texto se sintetiza sin haber pasado por el punto único
de salida, y el diseño la daba por cumplida **por tipos**: el puerto
`TextToSpeech` de C-16 recibe `Redacted` y no `str`, así que un texto crudo no
compila.

Es cierto y sigue siendo una buena barrera. Pero la rotura fue esta:

```python
def _redactado(self, text: str) -> Redacted:
    return text  # type: ignore[return-value]
```

El comprobador de tipos dijo `Success: no issues found in 594 source files`, las
123 pruebas quedaron en verde, y la agente habría dicho en voz alta la placa de
una persona.

**Una regla que solo vive en el tipo se apaga con un comentario.** El proyecto ya
exige que toda supresión del linter lleve su razón escrita al lado, pero eso lo
comprueba una persona revisando, no una compuerta.

**Lo que se hizo.** Dos pruebas de conducta que miran el texto que de verdad
saldría por el altavoz: una con una placa en la respuesta del grafo, que
comprueba que sale `[PLATE 1]` y no `ABC123`, y otra sobre lo que dice la propia
llamada —apertura y silencios—, porque un punto de salida que solo cubriera lo
que viene del grafo tendría un agujero del tamaño de la mitad de lo que la agente
dice.

Con las pruebas puestas se volvió a romper la regla igual, y ahora **sí** se cae.

Es una instancia nueva de una forma ya conocida del catálogo —la comprobación que
vive en un sitio donde una sola línea la desactiva— aplicada a un tipo en vez de
a una prueba. Va al documento de referencia.

## 3. Decisiones tomadas al escribir

1. **El caso de una llamada nace al conectar, no con el primer turno.** En el
   chat lo abre el primer mensaje; aquí no puede, porque la divulgación se
   registra contra un caso y va **antes** de cualquier pregunta. Sin caso no hay
   dónde registrarla y BR2.1 no se podría comprobar.
2. **Y nace siempre como siniestro.** El chat lee el primer mensaje con el
   reconocedor determinista de U12 para elegir entre siniestro y consulta de
   cobertura. Aquí no hay primer mensaje que leer: la agente habla primero. Se
   abre el camino de siete campos y, si lo que la persona dice resulta ser una
   pregunta de cobertura, el desvío dentro del siniestro que U12 ya construyó la
   atiende sin abrir otro caso. Inventar el tipo a partir de nada sería adivinar.
3. **`assert_never` cierra la forma hablada de C-14.** Quitar una rama no
   compila, y eso es mejor que descubrirlo en una llamada. La rotura lo comprobó:
   falló el comprobador de tipos *y* la prueba.
4. **La oferta de la decisión D8 es una sola clave** que usan los dos caminos —el
   segundo silencio y la tercera vez que no se entiende—, con una prueba que
   comprueba que las dos dicen literalmente lo mismo. Dos claves con el mismo
   texto es como una de las dos se queda vieja.
5. **La confianza que se mira es la peor palabra, no el promedio.** Una placa con
   cinco caracteres claros y uno dudoso es una placa dudosa; promediarla la daría
   por buena. Y una palabra **sin** confianza no cuenta en contra: nula significa
   "el proveedor no lo dijo", nunca "salió mal".

## 4. Dos frases que escribí y Miguel puede cambiar

Casi todo el texto nuevo es copia literal de un criterio aprobado o de la guía de
voz. **Dos no lo son**, porque no existían:

- **La despedida del tercer silencio**: "I'll keep your case saved. Take care." /
  "Le dejo el caso guardado. Que esté muy bien." Está compuesta de piezas
  aprobadas —la oferta de guardar el caso y la despedida de la guía de voz, punto
  9— en su variante que **no invita a volver a llamar**, porque el enlace público
  admite una llamada al día y prometer otra sería prometer lo que no se puede
  cumplir (AC1.23.4).
- **El "no le entendí" en español**: "Perdón, no le entendí. ¿Me lo repite?" Es la
  traducción al usted cálido de la frase aprobada en inglés.

## 5. Lo que no se debilitó

Ninguna prueba existente se relajó ni se borró. Ningún umbral, ningún piso de
cobertura, ninguna compuerta saltada. Una sola supresión del linter en toda la
tanda, con su razón al lado.

## 6. Formas del catálogo que se revisaron contra este diff

- **Forma 12, el doble más permisivo que la pieza real.** Es la tanda que estrena
  los dobles, así que se revisó primero. El manejador de turnos de la prueba
  **levanta si el turno llega sin caso**, igual que `handle_turn`: un doble que lo
  aceptara sería exactamente la forma que dejó el chat sin atender a nadie. El
  reconocedor entrega un guion con parciales, finales, silencios, confianza nula
  y transcripción vacía, porque uno que devolviera el texto completo de golpe no
  podría probar la detección de turno.
- **La aserción que no puede distinguir.** `test_subir_la_tolerancia_no_empeora_la_marca`
  existe por esto: sin ella, una marca puesta en el vencimiento pasaría siempre
  que la tolerancia no cambiara.
- **La prueba escrita desde la lectura equivocada del criterio.** Se revisó que
  la apertura termine con la pregunta **aunque** se ofrezca cotizar: sin esa
  prueba, activar la cotización dejaría la apertura terminando en una oferta.

## 7. Estado

`mise run test:u16`: 123 pruebas en verde (86 unitarias, 37 de integración).
`mise run copy:check`: los siete chequeos pasan.
`mise run types`, `mise run lint`: en verde.
