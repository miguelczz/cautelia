// Volver a leer algo unas cuantas veces, y parar.
//
// Lo usan las dos pantallas que pueden abrirse justo en los segundos en que la agente
// todavia evalua el caso (el desenlace de la llamada y «Ver mi caso»): el resultado llega
// poco despues y la pantalla no tiene otro aviso. **No es un sondeo**: tiene un tope de
// lecturas, se detiene en cuanto el valor deja de pedir otra, y quien lo arranca recibe la
// forma de cancelarlo --el efecto la devuelve y el temporizador se limpia al desmontar--.
//
// Quien lo arranca ya hizo la primera lectura y sabe que pide otra: aqui solo se espera,
// se vuelve a leer y se decide si hay una mas.

export interface BoundedReread<T> {
  /** La lectura. La misma llamada que hizo la primera, sin variantes. */
  readonly read: () => Promise<T>;
  /** Lo que llego de cada lectura. No se llama si ya se cancelo. */
  readonly onResult: (value: T) => void;
  /** Cierto mientras lo leido pide otra lectura (por ejemplo, el caso sigue en revision). */
  readonly keepGoing: (value: T) => boolean;
  /** Cuanto se espera antes de cada lectura. */
  readonly everyMs: number;
  /** Cuantas lecturas, como mucho. Despues de la ultima no se vuelve a pedir nada. */
  readonly maxReads: number;
}

/**
 * Espera `everyMs`, lee, entrega el resultado y, si `keepGoing` lo pide y no se llego al
 * tope, repite. Devuelve la forma de cancelarlo: limpia el temporizador y descarta la
 * lectura que estuviera en vuelo, para que una respuesta tardia no pinte una pantalla que
 * ya no existe.
 */
export function startBoundedReread<T>({
  read,
  onResult,
  keepGoing,
  everyMs,
  maxReads,
}: BoundedReread<T>): () => void {
  let vigente = true;
  let temporizador: ReturnType<typeof setTimeout> | undefined;
  let hechas = 0;

  const programar = (): void => {
    temporizador = setTimeout(() => {
      temporizador = undefined;
      void read().then((valor) => {
        if (!vigente) {
          return;
        }
        hechas += 1;
        onResult(valor);
        if (hechas < maxReads && keepGoing(valor)) {
          programar();
        }
      });
    }, everyMs);
  };

  if (maxReads > 0) {
    programar();
  }

  return () => {
    vigente = false;
    if (temporizador !== undefined) {
      clearTimeout(temporizador);
      temporizador = undefined;
    }
  };
}
