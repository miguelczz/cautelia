# Experimento 4 — Voces paisas

**Pregunta.** ¿Qué voz femenina suena de Medellín y suena real, conserva su
identidad en inglés y responde con poca latencia?

**Por qué importa.** La agente usa una sola voz paisa en los dos idiomas (D-016,
principio P10), y el supuesto A3 es que existe una usable por API. La guía de voz
fija la regla: prueba ciega con tres personas de Medellín que califican de 1 a 5
"suena de Medellín" y "suena real"; se adopta la primera voz que promedie 4 o más
en las dos. Si ninguna pasa, plan B (latinoamericana neutra con léxico paisa) o
plan C (clonado con consentimiento).

## Pasos

1. Pon `CARTESIA_API_KEY` y, si quieres incluir ElevenLabs, `ELEVENLABS_API_KEY`
   en `spikes/.env`.
2. Busca candidatas:

   ```bash
   python3 spikes/04-paisa-voices/find_voices.py
   ```

   Escribe `candidates.json` con cada voz y su enlace de muestra. Escucha las
   muestras y marca `"use": true` en hasta cinco.
3. Sintetiza las frases de audición (`texts.json`, unos 1.000 caracteres por voz):

   ```bash
   python3 spikes/04-paisa-voices/synthesize.py
   ```

   Antes de gastar créditos te dice cuántos caracteres va a usar y pide
   confirmación. Cada voz recibe un código al azar (V1, V2...) y los audios se
   guardan en `samples/` con ese código.
4. Escucha a ciegas. Crea la página de escucha y ábrela:

   ```bash
   python3 spikes/04-paisa-voices/listen.py
   ```

   ```bash
   open spikes/04-paisa-voices/samples/escuchar.html
   ```

   Cada persona escucha los audios en orden, marca los puntajes con clics y pulsa
   "Descargar mis puntajes": se guarda `puntajes-<iniciales>.csv` en Descargas.
   "Suena de Medellín" aparece solo en frases en español, "misma persona en
   inglés" solo en frases en inglés y "suena real" en todas. Si alguien escucha
   en otro computador, le compartes la carpeta `samples/` y te envía su archivo.
   **No abras `blind-key.csv` ni `results/` antes de terminar.**
5. Junta las planillas en `scores/` y revela:

   ```bash
   python3 spikes/04-paisa-voices/listen.py --collect
   ```

   ```bash
   python3 spikes/04-paisa-voices/reveal.py
   ```

## Qué pasó en la primera corrida (2026-09-16)

- La búsqueda encontró 127 voces. Siete de ElevenLabs se describen como de
  Medellín o paisas, pero **el plan gratuito de ElevenLabs no deja usar por API
  ninguna voz de su biblioteca**: una prueba de 5 caracteres devolvió 402, "Free
  users cannot use library voices via the API", aunque la voz estaba marcada como
  usable gratis. No se gastaron créditos.
- Cartesia no tiene voces paisas, pero sí dos **nativas de Colombia** (`es-CO`):
  Catalina y Mariana. Son las dos que se sintetizaron, con 2.020 caracteres del
  plan gratuito de Cartesia y sin errores.
- Si ninguna de las dos pasa la prueba ciega, las voces paisas de ElevenLabs solo
  se pueden probar pagando. Esa es una decisión de gasto de Miguel frente al tope
  de 5 USD, no del experimento: sus muestras públicas se escuchan gratis en los
  enlaces de `candidates.json` (relevancia 2) para decidir si vale la pena.
- Esa corrida usó la apertura anterior ("Esta llamada se graba", "This call is
  recorded"). `texts.json` ya tiene la aprobada en User Stories ("queda
  transcrita", "is transcribed") para las próximas síntesis.

## Resultado preliminar de la escucha (2026-09-16)

Escuchó y calificó **una persona**. La regla pide tres personas de Medellín, así
que el resultado todavía no adopta ninguna voz.

| Código | Voz | Suena de Medellín | Suena real | Misma persona en inglés | Primer byte p50 | ¿Pasa la regla? |
| --- | --- | --- | --- | --- | --- | --- |
| V1 | Catalina (Cartesia, `es-CO`) | 4,25 | 4,5 | 3,0 | 604 ms | Sí |
| V2 | Mariana (Cartesia, `es-CO`) | 2,25 | 2,5 | 1,0 | 313 ms | No |

- **Catalina** sonó "totalmente paisa". En la apertura, solo el "Hola" sonó raro.
- **Mariana** sonó con "acento rolo, de Bogotá", y en inglés con acento británico.
- **El inglés de Catalina no fue parejo.** Su apertura en inglés sacó 5 en "misma
  persona", pero la confirmación sacó 1, y 3 en "suena real". D-016 pide
  exactamente la misma voz en los dos idiomas, así que se comprobó con más frases
  en inglés (sección siguiente): ahí sí conservó su identidad.
- **La latencia no está decidida.** Catalina tardó más en empezar que Mariana,
  medida con solo seis frases cada una, desde el Mac y sin conexión persistente.
  El tiempo que cuenta se mide en el experimento 1, desde el servidor.

## Comprobación del inglés

Para saber si el 1 de la confirmación en inglés fue casualidad o si Catalina
cambia de persona en inglés, `english_check.py` sintetiza seis frases más en
inglés con su voz (`english-check.json`, 492 caracteres del plan gratuito). Cinco
copian literal frases fijas aprobadas en User Stories y una repite la
confirmación que sacó 1.

```bash
python3 spikes/04-paisa-voices/english_check.py
```

```bash
open spikes/04-paisa-voices/samples/ingles/escuchar-ingles.html
```

La página pone arriba una referencia de Catalina en español y mezcla, en orden
al azar, las seis frases nuevas con los dos audios en inglés de la primera
escucha y un **control**: la apertura en inglés de Mariana. Quien escucha marca
si cada audio parece la misma persona de la referencia y si suena real, y
descarga `ingles-<iniciales>.csv`. Para ver el resultado:

```bash
python3 spikes/04-paisa-voices/english_check.py --collect
```

**Regla, fijada antes de escuchar.** Catalina conserva su identidad en inglés si
las frases nuevas promedian 4 o más en "misma persona" y en "suena real", y
ninguna baja de 3 en "misma persona": en una llamada basta una frase que suene a
otra persona para que se note. Los puntajes solo cuentan si el control, que es
otra voz, saca 2 o menos en "misma persona".

**Resultado del 2026-09-16, con una persona.** El control sacó 1 en "misma
persona", así que los puntajes distinguen voces. Las seis frases nuevas de
Catalina y sus dos audios de la primera escucha sacaron 5 en "misma persona" y 5
en "suena real". Por la regla, **Catalina conserva su identidad en inglés**.

- La confirmación que en la primera escucha sacó 1 es el mismo archivo que ahora
  sacó 5: la diferencia vino de la escucha, no del audio.
- Con una sola persona, los puntajes varían entre escuchas: la apertura de
  Mariana pasó de 1 a 5 en "suena real".
- Quien escuchó aclaró que su inglés no es nativo.

## Cómo leer el resultado

La tabla final ordena las voces que pasan primero, con sus promedios y la
latencia hasta el primer byte. La latencia se mide desde tu Mac: sirve para
comparar voces entre sí; el presupuesto real del turno se confirma en el
experimento 1.

## Costo

Todo corre en planes gratuitos. Algunas voces de la biblioteca de ElevenLabs no
se pueden usar por API en el plan gratuito. La columna "Usable gratis por API" es
lo que declara ElevenLabs, pero la prueba real es la síntesis: si el proveedor
pide pago, `synthesize.py` muestra un aviso `alto:`, deja esa voz y sigue con las
demás, sin cobrar nada. Si la mejor voz es una de esas, usarla es un gasto que
decides tú, no el experimento, y se mide contra el tope de 5 USD: la guía de voz
ya dejó esa decisión pendiente.

## Privacidad y licencias

`samples/`, `scores/` y `blind-key.csv` quedan fuera de git. Antes de publicar
cualquier audio sintetizado hay que revisar la licencia de la voz elegida.
