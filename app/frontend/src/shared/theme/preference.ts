// La preferencia de modo y como se resuelve (entidades ThemePreference y
// ResolvedTheme; BR1.1, BR1.4).
//
// BR1.1 quedo enmendada el 2026-10-06 por decision de Miguel: sin eleccion
// guardada, el aplicativo abre en **oscuro**, que es el modo de la landing, y no
// sigue a la preferencia del dispositivo. La regla que fija el diseno es la de
// la landing; el aplicativo la copia, nunca al reves. El modo claro sigue siendo
// un modo completo, a un clic en el selector (BR1.3).
//
// Es la misma decision que toma `/theme-boot.js` antes de pintar, escrita en
// TypeScript para el proveedor de modo y para las pruebas. Una prueba corre las
// dos con los mismos escenarios y exige el mismo resultado: si alguien cambia una
// sin la otra, falla.

export type ThemeMode = "light" | "dark";
export type ThemeSource = "user" | "default";

export interface ResolvedTheme {
  readonly mode: ThemeMode;
  readonly source: ThemeSource;
}

/**
 * La unica clave que la interfaz escribe en el almacenamiento por su cuenta
 * (BR3.5, SEC-U6.5). Una sola para todo el aplicativo: ninguna pantalla guarda
 * la suya.
 */
export const THEME_STORAGE_KEY = "untangle.theme";

/** Cualquier valor distinto de `light` o `dark` se trata como ausente (BR1.4). */
export function parseThemeMode(value: string | null | undefined): ThemeMode | null {
  return value === "light" || value === "dark" ? value : null;
}

/**
 * Lee la eleccion guardada. Un almacenamiento bloqueado o un valor corrupto dan
 * `null` --el modo por defecto-- y dejan constancia en la consola, nunca un
 * mensaje para la persona (BR1.4, REL-U6.2).
 */
export function readStoredTheme(
  storage: () => Storage = () => window.localStorage,
): ThemeMode | null {
  let guardado: string | null;
  try {
    guardado = storage().getItem(THEME_STORAGE_KEY);
  } catch (error) {
    console.info("untangle: the stored theme preference cannot be read; using the default", error);
    return null;
  }
  const modo = parseThemeMode(guardado);
  if (guardado !== null && modo === null) {
    console.info("untangle: the stored theme preference is not light or dark; using the default");
  }
  return modo;
}

/**
 * Guarda la eleccion. Si el almacenamiento no esta disponible, la eleccion vale
 * para la pestana y no hay error visible (F3, BR1.4): se devuelve `false` y la
 * consola lo dice.
 */
export function storeTheme(
  mode: ThemeMode,
  storage: () => Storage = () => window.localStorage,
): boolean {
  try {
    storage().setItem(THEME_STORAGE_KEY, mode);
    return true;
  } catch (error) {
    console.info("untangle: the theme choice cannot be stored; it lasts for this tab", error);
    return false;
  }
}

/** El modo sin eleccion guardada: el de la landing. */
export const DEFAULT_THEME: ThemeMode = "dark";

/** BR1.1 (enmendada): con eleccion guardada, la guardada; sin ella, el modo por defecto. */
export function resolveTheme(stored: ThemeMode | null): ResolvedTheme {
  return stored !== null
    ? { mode: stored, source: "user" }
    : { mode: DEFAULT_THEME, source: "default" };
}

/**
 * Lo que dejo el paso de modo en el documento, si corrio. Si no corrio --en una
 * prueba, o si fallo antes de llegar--, se resuelve aqui con la misma regla.
 */
export function themeFromDocument(root: HTMLElement = document.documentElement): ResolvedTheme {
  const modo = parseThemeMode(root.getAttribute("data-theme"));
  const origen = root.getAttribute("data-theme-source");
  if (modo !== null && (origen === "user" || origen === "default")) {
    return { mode: modo, source: origen };
  }
  return resolveTheme(readStoredTheme());
}

/**
 * Aplica un modo a todo el documento a la vez y sin transicion (BR1.3): mientras
 * cambia, `data-theme-switching` apaga las transiciones, y se quita en el cuadro
 * siguiente.
 */
export function applyTheme(
  theme: ResolvedTheme,
  root: HTMLElement = document.documentElement,
): void {
  root.setAttribute("data-theme-switching", "");
  root.setAttribute("data-theme", theme.mode);
  root.setAttribute("data-theme-source", theme.source);
  window.requestAnimationFrame(() => {
    root.removeAttribute("data-theme-switching");
  });
}
