// El modo claro u oscuro de toda la aplicacion (ResolvedTheme; BR1.1 a BR1.4).
//
// El paso de modo (`/theme-boot.js`) ya lo aplico antes de pintar; el proveedor
// lo lee del documento y desde ahi lo gobierna: el selector lo cambia al
// instante y lo guarda. Mientras la persona no elija, el modo es el por defecto
// --el oscuro de la landing-- y no sigue al dispositivo (BR1.1 enmendada el
// 2026-10-06; antes seguia a la preferencia del sistema). Ninguna ruta declara
// un modo propio (BR1.3).

import {
  createContext,
  useCallback,
  useContext,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  applyTheme,
  storeTheme,
  themeFromDocument,
  type ResolvedTheme,
  type ThemeMode,
  type ThemeSource,
} from "./preference";

export interface ThemeContextValue {
  readonly mode: ThemeMode;
  readonly source: ThemeSource;
  /** La eleccion de la persona: se aplica a todo el documento y se guarda. */
  readonly setMode: (mode: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { readonly children: ReactNode }) {
  const [tema, setTema] = useState<ResolvedTheme>(() => themeFromDocument());

  // Si el paso de modo no corrio (una prueba, o un error antes de el), el
  // documento queda con el modo resuelto aqui antes de pintar.
  useLayoutEffect(() => {
    const raiz = document.documentElement;
    if (raiz.getAttribute("data-theme") !== tema.mode) {
      applyTheme(tema, raiz);
    }
  }, [tema]);

  const setMode = useCallback((mode: ThemeMode) => {
    const siguiente: ResolvedTheme = { mode, source: "user" };
    // Al documento primero y sin transicion (BR1.3); guardar es lo segundo, y si
    // el almacenamiento no esta, la eleccion vale para la pestana (BR1.4).
    applyTheme(siguiente);
    storeTheme(mode);
    setTema(siguiente);
  }, []);

  const valor = useMemo<ThemeContextValue>(
    () => ({ mode: tema.mode, source: tema.source, setMode }),
    [tema, setMode],
  );

  return <ThemeContext.Provider value={valor}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const valor = useContext(ThemeContext);
  if (valor === null) {
    throw new Error("useTheme needs a ThemeProvider above it");
  }
  return valor;
}
