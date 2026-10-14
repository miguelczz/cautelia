// El anunciador compartido para lectores de pantalla (BR7.5, AC1.33.4).
//
// Cada pantalla tiene **uno** cortes y **uno** de alerta, y viven aqui, en la
// raiz: un componente que necesita decir algo lo pide con `announce()` en lugar
// de montar su propia region en vivo. Dos regiones en vivo que hablan a la vez se
// pisan, y el lector dice la mitad de cada una.
//
// Un texto que llega por partes --una respuesta que se transmite palabra por
// palabra-- se anuncia **una sola vez, completo, al terminar** (`stream()`):
// anunciar cada parte seria leer la misma frase diez veces.

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type AnnouncementKind = "status" | "alert";

export interface StreamedAnnouncement {
  /** Agrega una parte del texto. No anuncia nada todavia. */
  readonly push: (part: string) => void;
  /** Termina el texto y lo anuncia completo, una vez. */
  readonly end: () => void;
}

export interface AnnouncerContextValue {
  readonly announce: (text: string, kind?: AnnouncementKind) => void;
  readonly stream: (kind?: AnnouncementKind) => StreamedAnnouncement;
}

interface Anuncio {
  readonly id: number;
  readonly text: string;
}

const AnnouncerContext = createContext<AnnouncerContextValue | null>(null);

export function AnnouncerProvider({ children }: { readonly children: ReactNode }) {
  const [cortes, setCortes] = useState<Anuncio | null>(null);
  const [alerta, setAlerta] = useState<Anuncio | null>(null);
  const siguiente = useRef(0);

  const announce = useCallback((text: string, kind: AnnouncementKind = "status") => {
    if (text.trim() === "") {
      return;
    }
    siguiente.current += 1;
    // Un nodo nuevo por anuncio: el mismo texto dos veces seguidas se vuelve a
    // decir, porque cambia el nodo aunque no cambie la frase.
    const anuncio = { id: siguiente.current, text };
    if (kind === "alert") {
      setAlerta(anuncio);
    } else {
      setCortes(anuncio);
    }
  }, []);

  const stream = useCallback(
    (kind: AnnouncementKind = "status"): StreamedAnnouncement => {
      const partes: string[] = [];
      let terminado = false;
      return {
        push: (part) => {
          if (!terminado) {
            partes.push(part);
          }
        },
        end: () => {
          if (terminado) {
            return;
          }
          terminado = true;
          announce(partes.join(""), kind);
        },
      };
    },
    [announce],
  );

  const valor = useMemo(() => ({ announce, stream }), [announce, stream]);

  return (
    <AnnouncerContext.Provider value={valor}>
      {children}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
        data-testid="announcer-status"
      >
        {cortes === null ? null : <p key={cortes.id}>{cortes.text}</p>}
      </div>
      <div
        role="alert"
        aria-live="assertive"
        aria-atomic="true"
        className="sr-only"
        data-testid="announcer-alert"
      >
        {alerta === null ? null : <p key={alerta.id}>{alerta.text}</p>}
      </div>
    </AnnouncerContext.Provider>
  );
}

export function useAnnouncer(): AnnouncerContextValue {
  const valor = useContext(AnnouncerContext);
  if (valor === null) {
    throw new Error("useAnnouncer needs an AnnouncerProvider above it");
  }
  return valor;
}
