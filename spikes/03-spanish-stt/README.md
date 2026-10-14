# Experimento 3 — Transcripción en español paisa

**Pregunta.** ¿Deepgram transcribe bien el español con acento paisa y deja
exactos los datos que se dictan en un reporte (placas, pólizas, cédulas,
teléfonos, números de caso)?

**Por qué importa.** El PRD marca como riesgo un español degradado (R4) con un
disparador concreto: un error por palabra (WER) mayor que 15 % con acento paisa
en la semana 1. Y la redacción de datos personales depende de que esos datos
lleguen bien escritos.

## Qué mide

- **WER** en 12 frases conversacionales en español y 6 en inglés, sin formato
  inteligente, para contar palabras.
- **Datos exactos** en 8 frases de datos en español y 3 en inglés, con formato
  inteligente, que es como los usaría el sistema.
- Tres modos para el español: `nova-3` con `es`, con `es-419` y con `multi`
  (cambio de idioma). Dos para el inglés: `en` y `multi`.

El guion está en `script.json`. Todos los datos son ficticios.

## Pasos

1. Pon `DEEPGRAM_API_KEY` en `spikes/.env`.
2. Graba en un lugar silencioso (unos 15 minutos). Lee cada frase como la dirías
   por teléfono; si te equivocas, sáltala y repítela al final.

   ```bash
   python3 spikes/03-spanish-stt/record.py --speaker miguel --take quiet
   ```

   El script usa el micrófono integrado del Mac y dice cuál eligió al empezar;
   los dispositivos virtuales, como el de Teams, graban silencio y nunca se
   eligen solos. Después de cada frase revisa que la toma tenga voz y, si salió
   vacía o en silencio, te deja repetirla. La primera vez, macOS pide permiso de
   micrófono para la app desde donde lo corres.

3. Si quieres usar otro micrófono, mira la lista y añade `--device <número>`:

   ```bash
   python3 spikes/03-spanish-stt/record.py --list-devices
   ```

4. Opcional, y muy valioso: otra toma con ruido de fondo (`--take noise`) y
   grabaciones de una o dos personas de Medellín (`--speaker <nombre>`), con su
   permiso para enviar su voz a Deepgram.
5. Transcribe:

   ```bash
   python3 spikes/03-spanish-stt/transcribe.py --dry-run
   ```

   ```bash
   python3 spikes/03-spanish-stt/transcribe.py
   ```

## Cómo leer el resultado

La tabla final muestra, por modo e idioma, el WER, si se dispara R4 y cuántos
datos llegaron exactos. Si el mejor modo en español supera el 15 %, se dispara
R4 y la decisión de transcripción se revisa en Domain Design con esta cifra.

## Resultados del 2026-09-16

Una sola persona (Miguel), en un cuarto silencioso, con el micrófono del
MacBook Air: 20 frases en español y 9 en inglés, 2,3 minutos de audio. Miguel
aclaró que su inglés no es nativo, así que las cifras en inglés mezclan los
errores del servicio con los de pronunciación. Las 78 llamadas salieron sin
errores.

| Modo | Idioma | Error por palabra (WER) | ¿Pasa del 15 % (R4)? | Datos exactos |
| --- | --- | --- | --- | --- |
| `nova-3:multi` | es | 5,6 % | No | 8 de 8 |
| `nova-3:es` | es | 8,6 % | No | 8 de 8 |
| `nova-3:es-419` | es | 8,6 % | No | 8 de 8 |
| `nova-3:en` | en | 9,3 % | — | 2 de 3 |
| `nova-3:multi` | en | 13,3 % | — | 2 de 3 |

`es` y `es-419` devolvieron exactamente la misma transcripción en las 20 frases.

**Corrección de la calificación.** La primera corrida
(`spanish-stt-20260916T235827Z.json`) dio 1 de 3 datos exactos en inglés. Deepgram
transcribió bien la póliza, pero con el formato inteligente pegó la palabra dicha
"dash" al código (`SUNDash610447`), y el calificador solo quitaba "dash" cuando
venía suelta. Se corrigió el calificador y se recalculó con las mismas
transcripciones, sin volver a llamar a Deepgram
(`spanish-stt-20260916T235943Z.json`, con `rescored_from`).

### Qué dice para Domain Design

1. **R4 no se dispara con esta voz.** El mejor modo en español se equivoca en el
   5,6 % de las palabras, lejos del 15 %. No cierra el riesgo para el acento paisa
   en general: es una sola persona, habla leída, cuarto silencioso y micrófono del
   Mac, no una llamada desde el navegador.
2. **Los datos dictados en español llegaron exactos** en los tres modos: placa,
   placa parcial, póliza, dos cédulas, dos teléfonos y número de caso.
3. **El WER esconde errores que cambian el sentido.** Con `es` y `es-419`, "no
   hubo que llevarla a urgencias" quedó como "hubo que llevarla a urgencias",
   "no era la salida doce, era la catorce" quedó como "a las doce… a las
   catorce", y "me lo cubre el seguro" quedó como "me lo ocurre el seguro". Con
   `multi`, "iba manejando mi esposo" quedó como "iba manejando a mi esposo", que
   cambia quién manejaba. Cada uno cuenta como una o dos palabras, pero cambia un
   dato de seguridad o del caso. Por eso la agente tiene que confirmar en voz alta
   lesiones, conductor y lugar antes de anotarlos, y una transcripción sola no
   basta para esos campos, igual que en el hallazgo 6 del experimento 2.
4. **`multi` es el candidato para español.** Tuvo el menor error, acertó la
   negación y la salida, y es el modo que permite detectar el idioma solo. En
   inglés salió peor que `en`, pero con un hablante no nativo esa diferencia no
   se puede atribuir al servicio. El precio de cada modo no se midió aquí: se
   revisa en Domain Design.
5. **En inglés, la K de la placa llegó como Q.** Es el caso que cubre la
   confirmación de letras confundibles ("B as in boy", AC1.23.2). Y el sistema
   tiene que limpiar los separadores dichos que el formato inteligente pega a los
   códigos, como ahora hace el calificador.

## Límites del experimento

- Es habla leída, que se transcribe mejor que una llamada espontánea: el WER real
  será algo mayor.
- Con una sola persona grabando, el resultado dice más de esa voz que del acento.
- El micrófono del Mac no es el del navegador de quien llame.
- Las frases en inglés las grabó un hablante no nativo: sus cifras no sirven para
  comparar el servicio con hablantes nativos.

## Privacidad

Las grabaciones quedan en `recordings/`, que git ignora. Son voz de personas
reales: bórralas cuando termine el experimento.
