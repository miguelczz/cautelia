/*
 * La captura de audio del navegador hacia el socket (U16, C-29, BR1.3).
 *
 * Es un `AudioWorklet` y no un `ScriptProcessorNode`: corre en el hilo de audio,
 * asi que ni un repintado ni una consulta lenta le hacen perder muestras. Un
 * corte de captura no se oye como un corte --se oye como una palabra que la
 * agente no entendio-- y eso es lo peor que puede pasar en esta pantalla.
 *
 * **No remuestrea.** El `AudioContext` se crea ya a 24 kHz, que es el unico
 * formato del aplicativo, y quien adapta la frecuencia del microfono es el propio
 * navegador al conectar la fuente. Un remuestreador escrito a mano aqui seria una
 * segunda implementacion de algo que el navegador ya hace mejor, y con un error
 * de redondeo propio.
 *
 * Manda dos cosas por su puerto:
 *
 * - `audio`: trozos de PCM de 16 bits con signo, 480 muestras --20 ms-- listos
 *   para el socket. El `ArrayBuffer` viaja **transferido**, no copiado.
 * - `level`: el nivel de la voz de ese mismo trozo, entre 0 y 1. No es
 *   telemetria y no sale del navegador: es el unico modo de que quien tiene el
 *   microfono silenciado por el sistema lo vea, en vez de hablar dos minutos
 *   contra una pared.
 */

/** Muestras por trozo: 20 ms a 24 kHz. */
const MUESTRAS_POR_TROZO = 480;

/** El maximo de una muestra de 16 bits con signo. */
const MAXIMO_16 = 32767;

class VoiceCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.pendientes = new Float32Array(MUESTRAS_POR_TROZO);
    this.escritas = 0;
  }

  /**
   * Un bloque de 128 muestras del microfono. Se acumulan hasta completar 20 ms.
   *
   * Devuelve siempre `true`: el nodo vive mientras la llamada viva, y devolver
   * `false` una sola vez lo apaga para siempre. Es asi como se pierde el
   * microfono a mitad de una frase sin que nada lo diga.
   */
  process(inputs) {
    const entrada = inputs[0];
    if (!entrada || entrada.length === 0) {
      return true;
    }
    const canal = entrada[0];
    if (!canal) {
      return true;
    }

    for (const muestra of canal) {
      this.pendientes[this.escritas] = muestra;
      this.escritas += 1;
      if (this.escritas === MUESTRAS_POR_TROZO) {
        this.emitir();
        this.escritas = 0;
      }
    }
    return true;
  }

  emitir() {
    const muestras = new Int16Array(MUESTRAS_POR_TROZO);
    let suma = 0;
    for (let i = 0; i < MUESTRAS_POR_TROZO; i += 1) {
      const valor = Math.max(-1, Math.min(1, this.pendientes[i]));
      muestras[i] = Math.round(valor * MAXIMO_16);
      suma += valor * valor;
    }
    // La raiz de la media de los cuadrados: lo que se ve como "esta entrando voz".
    const nivel = Math.sqrt(suma / MUESTRAS_POR_TROZO);
    this.port.postMessage({ type: "audio", buffer: muestras.buffer, level: nivel }, [
      muestras.buffer,
    ]);
  }
}

registerProcessor("voice-capture", VoiceCaptureProcessor);
