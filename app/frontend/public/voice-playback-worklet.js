/*
 * La reproduccion de lo que la agente dice (U16, C-29, BR4.3).
 *
 * Una cola de muestras que el nodo consume a ritmo constante. Lo que importa de
 * este archivo no es reproducir --eso lo haria cualquier cosa-- sino **vaciar**:
 * cuando llega `stop_audio` la cola se tira entera en el mismo instante, y eso es
 * lo que pone la parada por debajo de 300 ms (NFR2).
 *
 * Por que el vaciado vive aqui y no en el servidor: el servidor no puede retirar
 * el audio que ya mando. Para cuando decide callarse, medio segundo de voz ya
 * viaja por el cable o espera en esta cola. Quien puede tirarlo es quien lo
 * tiene, y ese es el navegador. Por eso NFR2 se mide en el cliente.
 *
 * Cuando la cola se queda vacia el nodo emite **silencio**, no se apaga: una
 * pausa entre dos frases es normal, y un nodo que se apagara al final de la
 * primera dejaria la segunda sin donde sonar.
 */

/** El maximo de una muestra de 16 bits con signo. */
const MAXIMO_16 = 32768;

class VoicePlaybackProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    /** Los trozos pendientes, en orden de llegada. */
    this.cola = [];
    /** Cuantas muestras del trozo de la cabeza ya se consumieron. */
    this.consumidas = 0;
    /** Si hay que avisar cuando la cola quede vacia: el final de la llamada. */
    this.avisarAlVaciar = false;
    this.port.onmessage = (evento) => {
      const mensaje = evento.data;
      if (mensaje.type === "audio") {
        this.cola.push(new Int16Array(mensaje.buffer));
        return;
      }
      if (mensaje.type === "drain") {
        // El final de la llamada: lo que queda en la cola es la despedida, con el
        // numero de caso. Se deja sonar entera y se avisa al terminar, para que la
        // pagina cierre el audio entonces y no antes (2026-10-10).
        if (this.cola.length === 0) {
          this.port.postMessage({ type: "drained" });
        } else {
          this.avisarAlVaciar = true;
        }
        return;
      }
      if (mensaje.type === "flush") {
        // **Entera y ahora**, incluido el trozo a medio consumir: dejar sonar lo
        // que quedaba de la palabra en curso es exactamente lo que se siente como
        // "no me hizo caso".
        this.cola = [];
        this.consumidas = 0;
        this.port.postMessage({ type: "flushed" });
        if (this.avisarAlVaciar) {
          this.avisarAlVaciar = false;
          this.port.postMessage({ type: "drained" });
        }
      }
    };
  }

  /**
   * Llena el bloque de salida con lo que haya en la cola, y con silencio si no
   * hay nada. Devuelve siempre `true` por la misma razon que el de captura.
   */
  process(_inputs, outputs) {
    const salida = outputs[0];
    if (!salida || salida.length === 0) {
      return true;
    }
    const canal = salida[0];

    for (let i = 0; i < canal.length; i += 1) {
      const trozo = this.cola[0];
      if (trozo === undefined) {
        canal[i] = 0;
        continue;
      }
      canal[i] = trozo[this.consumidas] / MAXIMO_16;
      this.consumidas += 1;
      if (this.consumidas >= trozo.length) {
        this.cola.shift();
        this.consumidas = 0;
        if (this.avisarAlVaciar && this.cola.length === 0) {
          this.avisarAlVaciar = false;
          this.port.postMessage({ type: "drained" });
        }
      }
    }
    return true;
  }
}

registerProcessor("voice-playback", VoicePlaybackProcessor);
