# Experimento 2 — Modelo Flash-Lite

**Pregunta.** ¿Qué modelo Flash-Lite de Gemini extrae bien los datos de un turno
del asegurado, sin inventar lo que no se dijo, y empieza a responder lo bastante
rápido para una llamada? ¿Cuánto costaría por llamada?

**Por qué importa.** El PRD eligió Gemini 2.5 Flash-Lite (D-015) y marcó como
riesgo que no alcance (R3, supuesto A2). Desde entonces salieron 3.1 y 3.5
Flash-Lite, más capaces y más caros. El experimento compara esos dos.

**2.5 Flash-Lite ya no es opción.** El 2026-09-16 la API respondió 404 a las dos
corridas con el mensaje "This model models/gemini-2.5-flash-lite is no longer
available to new users". No es un problema de la clave: Google cerró ese modelo
a cuentas nuevas. D-015 tiene que cambiar en Domain Design.

| Modelo | Entrada (USD por millón de tokens) | Salida (USD por millón de tokens) |
| --- | --- | --- |
| `gemini-3.1-flash-lite` | 0,25 | 1,50 |
| `gemini-3.5-flash-lite` | 0,30 | 2,50 |

Precios de lista de texto consultados el 2026-09-16 en la página de precios de la
API de Gemini. El plan gratuito no cobra; los precios sirven para estimar el
costo de la voz, que sí usa el plan de pago.

## Qué mide

1. **Extracción.** 22 turnos sintéticos (11 en español y 11 en inglés) en
   `cases.json`: fechas relativas, placas y pólizas dictadas, correcciones a mitad
   de frase, heridos, conductor distinto al asegurado. Cuenta los campos correctos
   y los **valores inventados** (un campo que debía quedar vacío y el modelo
   llenó).
2. **Latencia del turno.** El tiempo hasta el primer token de una respuesta corta
   de la agente, en streaming, y el tiempo total.
3. **Costo estimado** por turno y por llamada de tres minutos (15 turnos), con los
   tokens reales de cada respuesta y el precio de lista.

## Cómo correrlo

```bash
python3 spikes/02-flash-lite/measure.py --dry-run
```

```bash
python3 spikes/02-flash-lite/measure.py
```

Tarda entre 10 y 12 minutos por la pausa entre llamadas, que respeta los límites
del plan gratuito. Para probar un solo modelo: `--models gemini-3.5-flash-lite`.

Qué significan los avisos de la consola:

- `aviso: HTTP 429`: se pasó el límite de peticiones por minuto. El script
  espera y reintenta; si se repite mucho, súbele la pausa con `--sleep 8`.
- `aviso: HTTP 503`: Google está saturado ("high demand"), casi siempre por
  poco tiempo. El script reintenta tres veces; si sigue, anota ese caso como
  `unavailable` y continúa con el siguiente.
- `alto:`: se acabó la cuota diaria gratuita o un saldo. El script no reintenta,
  detiene ese modelo y dice qué se acabó. No se recarga nada: se revisa y se
  decide.

## Cómo leer el resultado

La tabla final muestra, por modelo e idioma, los campos correctos, los valores
inventados, el primer token en p50 y p95 y el costo estimado por llamada.

Referencias para la decisión, que son **hipótesis** hasta el experimento 1:

- La meta del turno de voz es p50 menor que 500 ms y p95 menor que 800 ms, del fin
  del habla al primer audio. Ese tiempo reparte detección de fin de habla,
  primer token del modelo y primer byte de la voz; si el modelo solo ya se lleva
  más de unos 300 ms en p50, la meta queda muy apretada.
- La extracción debe llegar al 95 % por campo en cada idioma (NFR8), y un valor
  inventado es más grave que un campo vacío.
- La meta de costo de la voz es 0,005 USD por minuto de llamada (decisión D7 de
  las historias).

La regla que propongo para la decisión: el modelo más barato que no invente
valores y cumpla el tiempo. Si ninguno cumple el tiempo, no se sube de modelo a
ciegas: se revisa el diseño del turno, como fija el PRD (Segmento 12).

## Resultados del 2026-09-16

Cuatro corridas en el plan gratuito, desde el Mac de Miguel, con el nivel de
razonamiento mínimo. Las corridas 1 y 2 se solaparon siete minutos y compartieron
los límites por minuto, así que sus tiempos son los menos limpios. En la corrida
2 un caso en inglés de 3.1 falló por saturación de Google (503) y quedó fuera.

| Corrida (inicio UTC) | Modelo | Campos bien (es / en) | Valores inventados (es / en) | Primer token p50 en s (es / en) | Primer token p95 en s (es / en) |
| --- | --- | --- | --- | --- | --- |
| 1 (20:43) | 3.1 | 97,7 % / 97,7 % | 2 / 2 | 1,1 / 1,7 | 4,9 / 5,5 |
| 1 (20:43) | 3.5 | 97,7 % / 97,7 % | 2 / 2 | 1,1 / 1,0 | 30,5 / 16,0 |
| 2 (20:49) | 3.1 | 97,7 % / 97,5 % | 2 / 2 | 2,1 / 2,4 | 20,4 / 14,3 |
| 2 (20:49) | 3.5 | 97,7 % / 97,7 % | 2 / 2 | 1,1 / 1,2 | 1,8 / 2,1 |
| 3 (21:59) | 3.1 | 97,7 % / 97,7 % | 2 / 2 | 1,3 / 1,3 | 2,6 / 2,9 |
| 3 (21:59) | 3.5 | 97,7 % / 97,7 % | 2 / 2 | 1,6 / 1,1 | 15,5 / 2,9 |
| 4 (23:09) | 3.1 | 100 % / 100 % | 0 / 0 | 2,2 / 1,4 | 10,2 / 2,7 |
| 4 (23:09) | 3.5 | 100 % / 100 % | 0 / 0 | 1,0 / 1,0 | 1,7 / 2,1 |

| Modelo | Tokens por turno, mediana (entrada / salida) | USD por llamada de 3 min (es / en) | USD por minuto de llamada |
| --- | --- | --- | --- |
| 3.1 | 100 / 21 | 0,00090 / 0,00077 | 0,0003 |
| 3.5 | 100 / 16 | 0,00107 / 0,00098 | 0,0004 |

### Qué cambió antes de la corrida 4

En las corridas 1 a 3 los dos modelos fallaron igual y solo en `es-10` y `en-10`
("anoche se cayó una rama encima del carro"): dejaron la fecha vacía y
**inventaron** "sin lesiones" y "0 otras partes", que el asegurado nunca
mencionó. Antes de la corrida 4 se aclaró la instrucción de extracción en tres
reglas: la fecha se resuelve también para días relativos como "anoche", una hora
vaga da fecha pero no hora, y lesiones y otras partes quedan vacías si no se
habló de ellas, porque el silencio no es "ninguna" ni 0.

Con eso, los dos modelos acertaron todos los campos. **Ese 100 % no es una
medición independiente**: la aclaración se escribió después de ver los dos fallos
y se comprobó con los mismos 22 casos. Confirma que la aclaración funciona en
esos casos, no que el modelo deje de inventar en general. La medición real es el
golden set de texto (DS-2) en Construcción, con casos que este prompt no vio.

### Qué dice para Domain Design

1. **2.5 Flash-Lite no está disponible para esta cuenta**, así que D-015 tiene
   que nombrar otro modelo.
2. **Extracción: empate.** Los dos modelos fallaron y acertaron exactamente en
   los mismos campos en las cuatro corridas.
3. **Tiempo: ninguno cumple en el plan gratuito.** El primer token tardó en p50
   entre 1,1 y 2,4 s con 3.1 y entre 1,0 y 1,6 s con 3.5, frente a los unos
   300 ms que, como hipótesis, le deja al modelo la meta del turno de voz. Los dos tuvieron colas de más de 10 s.
   3.5 tuvo la mediana más baja en 6 de las 8 mediciones, pero también la peor
   cola (30,5 s). El plan gratuito no dice cuánto tardaría el plan de pago ni una
   región más cercana.
4. **Costo: depende de un tamaño de prompt que todavía no existe.** Con los
   prompts cortos del experimento, los dos quedan más de diez veces por debajo de
   la meta de 0,005 USD por minuto (NFR14). Pero D-015 estimó 1 centavo por
   llamada de 4 minutos con los precios de 2.5. Si los prompts reales llegan a ese
   tamaño, 3.1 cuesta entre 2,5 y 3,75 veces más (0,006 a 0,009 USD por
   minuto) y 3.5 entre 3 y 6,25 veces más (0,008 a 0,016): los dos pasarían la
   meta, y los 5 USD alcanzarían para entre 105 y 160 llamadas con 3.1, o entre
   65 y 135 con 3.5, en lugar de las 400 de D-015. Para quedarse en la meta con 15
   turnos cada 3 minutos, cada turno puede llevar como máximo unos 3.900 tokens
   de entrada con 3.1 y unos 3.200 con 3.5, sin contar el trabajo de fondo.
5. **Por la regla escrita antes de correr**, el candidato es 3.1: es el más
   barato, no inventa con la instrucción aclarada y, como ninguno cumple el
   tiempo, subir a 3.5 no resuelve el problema. Lo que queda abierto es el diseño
   del turno. Las opciones que ya aparecen en el plan y en el PRD son medir en el
   plan de pago
   (es gasto, lo decide Miguel), probar Groq como prevé D-015 (necesita cuenta y
   clave de Miguel) y un turno que no espere al modelo, con frase de espera o
   respuesta precargada.
6. **Una instrucción no garantiza que el modelo no invente.** Para lesiones y
   otras partes, el caso tiene que distinguir "no lo dijo" de "dijo que no", como
   ya se distingue "no hay cláusula" de "no pude verificar". Domain Design decide
   cómo se comprueba, por ejemplo exigiendo la frase del asegurado que lo
   respalda.

## Límites del experimento

- Mide desde tu Mac hasta Google, no desde la región donde se hospedará el
  sistema, y el plan gratuito puede sumar espera.
- Los prompts son más cortos que los del sistema real, así que el costo estimado
  es un piso, no un techo.
- Once casos por idioma dan una señal, no una evaluación: el golden set de texto
  (DS-2) llega en Construcción.
