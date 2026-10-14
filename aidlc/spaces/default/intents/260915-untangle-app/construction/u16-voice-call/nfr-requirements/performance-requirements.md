# Requisitos de rendimiento — U16 `voice-call`

Esta unidad es la única del proyecto cuya razón de ser es el reloj. Tres metas
—NFR1, NFR2 y NFR3— y todas se sienten: una llamada que tarda en responder se
oye incómoda aunque diga lo correcto, y una agente que no se calla cuando la
interrumpen se oye peor que una que se equivoca.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| NFR1 | Del evento de fin del habla al primer audio, por idioma | **p50 < 500 ms y p95 < 800 ms** | `mise run voice:call-live`, de hito, sobre DS-5 y a mano (ver la enmienda de abajo) |
| NFR2 | De la marca de interrupción a que la reproducción pare, medido en el cliente | **< 300 ms en cada interrupción** | El mismo comando de hito, y `mise run test:u16` con el reloj inyectado |
| NFR3 | Turnos que siguen tras una interrupción sin perder estado | **> 90 %** | El mismo comando de hito, sobre las interrupciones marcadas de DS-5 |
| PERF-U16.1 | Lo que esta unidad añade entre el fin del habla y el primer audio, sin proveedores | **p95 ≤ 60 ms** | `mise run test:u16` (cronometrado). Medido el 2026-09-29: **p95 3,9 ms** sobre veinte turnos |
| PERF-U16.2 | Del cuadro `stop_audio` a la orden de vaciar, en el cliente | **p95 ≤ 50 ms** | Prueba del transporte de la consola (`vitest`). Ver el alcance en la enmienda |
| PERF-U16.3 | `GET /voice/availability` con la base tibia (C-08) | **p95 ≤ 300 ms** | `mise run test:u16` (cronometrado) |
| PERF-U16.4 | `POST /voice/sessions` (C-08) | **p95 ≤ 1 s** | `mise run test:u16` (cronometrado) |

## Enmienda del 2026-09-29, al cerrar la unidad

Tres cosas de esta tabla no eran ciertas al terminar la sexta tanda, y se
descubrieron al preguntar qué faltaba para cerrar. Se dicen aquí en vez de
corregir la tabla en silencio.

**1. La tarea de hito se llama `voice:call-live`, no `evals:voice`.** Lo que se
construyó corre **una** grabación por el transporte de verdad y no el conjunto.
Un corredor del conjunto hoy no tendría nada que correr --DS-5 no existe: son
veinte grabaciones de personas reales que llegan en las semanas 6 y 9-- y sería
una pieza sin datos y sin llamador, que es la forma de defecto que más ha costado
en este proyecto. El corredor del conjunto llega con las grabaciones, y queda
anotado como diferido en `pasada-de-publicacion.md`.

**2. PERF-U16.1 y PERF-U16.2 no se medían.** Estaban declaradas con su comando y
nadie producía su valor: es exactamente lo que la regla del equipo prohíbe --un
umbral cuantificado sin el comando que da su valor real--. Ya se miden, y las dos
imprimen su cifra en cada corrida y no solo cuando fallan: un número que solo se
ve cuando está mal no sirve para notar que va subiendo.

**3. PERF-U16.2 mide menos de lo que su nombre decía.** Decía "al vaciado de la
cola" y lo que se mide es **hasta que la orden de vaciar sale por el puerto del
nodo de audio**. Lo que pasa dentro del `AudioWorklet` --tirar la cola y el trozo
a medio consumir-- corre en el hilo de audio, y el documento de pruebas del
navegador no lo tiene. Eso se mide contra el despliegue vivo, por hito, junto a
NFR2. La prueba comprueba además **el orden**: la orden de vaciar sale antes de
que la pantalla se entere, porque al revés el vaciado esperaría un cuadro de
dibujo entero.

## Por qué hay un presupuesto propio además de NFR1

NFR1 es una meta de punta a punta y la mayor parte de su presupuesto se la comen
tres cosas que esta unidad no escribe: el reconocedor, el modelo y la síntesis.
U15 ya midió su parte en vivo —697 ms al primer audio con Catalina en inglés,
549 ms con Aura-2— y esa cifra sola ya se come el presupuesto de p95.

Así que la meta de punta a punta se mide por hito y se publica como es, y lo que
esta unidad vigila **en cada entrega** es su propia contribución: PERF-U16.1,
que es todo lo que pasa entre que el detector de turno decide que la persona
terminó y que el primer byte sale hacia la síntesis. Ese número sí depende solo
de este código, y es el que se pone rojo cuando alguien mete trabajo en el camino
del turno.

Es la misma lógica que la regla del proyecto sobre el turno de voz: dentro del
turno solo van los tres controles baratos, y el resto va al ritmo de fondo. Si
PERF-U16.1 sube, algo se coló.

## Dónde empieza el reloj de NFR1

En el evento de **fin del habla**, que esta unidad define (BR3.1, decisión D4):
un transcrito final seguido de `end_of_speech_ms` sin nada nuevo, con la marca
del último final y no la del vencimiento del temporizador.

AC1.23.5 pide que, si el fin del habla se mide también como "última palabra
audible", se publiquen las dos variantes. Se publican: la segunda sale de
`WordHypothesis.end_s` del último final, y el reporte del hito lleva las dos
columnas nombradas. No se elige la más favorable.

## Por qué NFR2 se mide en el cliente

El servidor no puede retirar el audio que ya mandó. Cuando detecta la
interrupción, el navegador tiene cientos de milisegundos encolados, así que un
cronómetro en el servidor mediría "cuándo dejé de generar" y no "cuándo dejó de
oírse", que es lo que le importa a la persona.

Lo que se mide es el camino completo: detección, viaje del cuadro `stop_audio` y
vaciado de la cola. PERF-U16.2 aísla el último tramo para que, cuando NFR2 se
pase de presupuesto, se sepa cuál de los tres fue.

## Lo que no se mide aquí

- **La latencia del turno de chat** es de U13, con otro presupuesto: un turno
  escrito admite ocho segundos y uno hablado no admite uno.
- **La latencia de cada proveedor por separado** es TECH-U15.2, ya medida.
- **La duración de la llamada y los límites públicos** son de U17.
- **Las mismas metas en español** son de U18: los números no cambian, el idioma
  sí, y la paridad se reporta por idioma y nunca como promedio.
