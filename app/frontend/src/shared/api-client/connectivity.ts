// El aviso de que se perdio la conexion con el proceso (functional-spec 2.1).
//
// Cualquier llamada del cliente que falla por red avisa aqui, y la espera de
// "listo" --que vive en otra rama del arbol-- escucha y vuelve a comprobar. Un
// emisor minimo en lugar de un contexto: la cache de datos se crea antes que la
// espera, y no tiene por que conocerla.

type Listener = () => void;

const escuchas = new Set<Listener>();

/** Suscribe a la perdida de conexion. Devuelve como darse de baja. */
export function onConnectivityLost(listener: Listener): () => void {
  escuchas.add(listener);
  return () => {
    escuchas.delete(listener);
  };
}

/** Avisa que una llamada perdio la conexion con el proceso. */
export function reportConnectivityLost(): void {
  for (const escucha of escuchas) {
    escucha();
  }
}
