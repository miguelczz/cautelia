# Experimento 1 — Voz y grafo, y una llamada en hospedaje gratuito

**Pregunta.** ¿Se puede conectar la voz a un grafo de estado explícito con
LiveKit Agents o con Pipecat, cediendo el turno en menos de 300 ms, y sostener
una llamada de tres minutos en hospedaje gratuito?

**Por qué importa.** Tres riesgos del PRD dependen de esta respuesta: la
integración de voz y grafo con incidencias que obliguen a un adaptador propio
(R10), la latencia del turno (R2) y el supuesto de que existe hospedaje gratuito
que no se duerma a mitad de una llamada (A1), que es además el riesgo abierto del
enlace público de voz (D-018).

**Estado.** Plan escrito. El código lo escribo cuando arranquen los experimentos
2 a 4, verificando contra la documentación vigente las versiones de los dos
frameworks, que cambian rápido.

## Plan, en tres días como máximo

**Día 1: prototipo local con el primer framework.**

- Un grafo mínimo de dos nodos (pedir el nombre y confirmarlo) con una función de
  transición pura, sin cliente de modelo en su cadena de llamadas.
- El mismo grafo invocado desde un bucle de texto y desde la voz, para comprobar
  que el grafo no importa nada del framework de voz (principio P3).
- Transcripción con Deepgram en streaming y voz con la candidata del experimento
  4, o con una voz genérica gratuita mientras tanto.

**Día 2: el mismo prototipo con el segundo framework,** y la medición de los dos.

**Día 3: la llamada fuera de tu Mac,** con el framework que haya salido mejor.

## Qué se mide

| Medición | Cómo | Referencia |
| --- | --- | --- |
| Fin del habla al primer audio | 20 turnos por framework, p50 y p95 | p50 < 500 ms, p95 < 800 ms (NFR1) |
| Parada ante interrupción | 10 interrupciones por framework | < 300 ms (NFR2) |
| Independencia del grafo | Búsqueda de importaciones del framework de voz en el módulo del grafo | Cero |
| Estabilidad local | 5 llamadas de 3 minutos | Sin cortes |
| Hospedaje | Arranque en frío, comportamiento dormido, cortes, memoria y CPU en 5 llamadas de 3 minutos | Sin cortes y sin costo posible por encima del plan gratuito |

## Hospedaje

Los planes gratuitos cambian a menudo, así que ninguno se da por bueno antes de
probarlo. Se evalúan dos piezas por separado: quién transporta el audio en
tiempo real (por ejemplo, LiveKit Cloud o Daily) y dónde corre el proceso de la
agente (por ejemplo, Hugging Face Spaces, Koyeb, Oracle Cloud Always Free,
Render o Google Cloud Run). Criterios: que no se duerma durante una llamada o se
mantenga despierto con la comprobación periódica, que admita un proceso de larga
duración, que no pida tarjeta o no permita gastar por encima del plan gratuito, y
la latencia desde su región.

## Regla de corte

Si en tres días ningún framework cierra la integración, se aplica la mitigación
del PRD para R10: un adaptador propio aislado detrás de una interfaz de una sola
función. Si ningún hospedaje gratuito sostiene la llamada, el enlace público de
voz cae por una razón técnica y no presupuestal, y esa es una decisión nueva para
ti con estas cifras.

## Qué necesita de ti

Nada por ahora. Cuando el prototipo local funcione, te pediré abrir la cuenta del
hospedaje y del transporte que se vayan a probar.
