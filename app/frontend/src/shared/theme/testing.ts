// Solo para pruebas: un `matchMedia` controlable. El documento de pruebas no lo
// trae, y la interfaz lo usa para el modo del dispositivo (BR1.1) y para el
// movimiento reducido.

type Escucha = (evento: MediaQueryListEvent) => void;

export interface MatchMediaControl {
  /** Cambia la respuesta de una consulta y avisa a quien la escucha. */
  readonly set: (query: string, matches: boolean) => void;
}

export function stubMatchMedia(inicial: Readonly<Record<string, boolean>>): MatchMediaControl {
  const valores = new Map<string, boolean>(Object.entries(inicial));
  const escuchas = new Map<string, Set<Escucha>>();

  const matchMedia = (query: string): MediaQueryList => {
    const lista = {
      get matches() {
        return valores.get(query) ?? false;
      },
      media: query,
      onchange: null,
      addEventListener: (_tipo: string, escucha: Escucha) => {
        const conjunto = escuchas.get(query) ?? new Set<Escucha>();
        conjunto.add(escucha);
        escuchas.set(query, conjunto);
      },
      removeEventListener: (_tipo: string, escucha: Escucha) => {
        escuchas.get(query)?.delete(escucha);
      },
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => true,
    };
    return lista as unknown as MediaQueryList;
  };
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: matchMedia,
  });

  return {
    set: (query, matches) => {
      valores.set(query, matches);
      for (const escucha of escuchas.get(query) ?? []) {
        escucha({ matches, media: query } as MediaQueryListEvent);
      }
    },
  };
}

export const DARK_QUERY = "(prefers-color-scheme: dark)";
