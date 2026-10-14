// El idioma con el que se abre una pagina (entidad LanguageChoice; BR2.1, BR2.2).

import type { Locale } from "../copy/copy-keys";

/**
 * De donde salio el idioma: `device` es "sin eleccion" --el del dispositivo o el
 * que dejo la landing--, `tenant_default` el de una aseguradora, `user` la eleccion
 * de esta visita y `persisted` la de una visita anterior.
 */
export type LocaleSource = "device" | "tenant_default" | "user" | "persisted";

export interface LanguageChoice {
  readonly locale: Locale;
  readonly source: LocaleSource;
}

/**
 * La clave con la que se recuerda **la eleccion** del idioma entre visitas, en
 * todas las pantallas (decision de Miguel, 2026-10-06; reemplaza BR1.6, que solo
 * la dejaba a la bandeja). Es, con el modo, una de las preferencias que la
 * interfaz guarda (BR3.5, SEC-U6.5).
 */
export const LOCALE_STORAGE_KEY = "untangle.locale";

/**
 * La clave que comparte con la landing. Landing y aplicativo viven en el mismo
 * dominio, asi que quien elige ingles en la landing entra en ingles y quien lo
 * cambia aqui lo encuentra asi al volver.
 *
 * La landing la escribe tambien con el idioma que **detecta** en su primer
 * arranque, no solo con el que la persona elige; por eso aqui es una semilla y
 * no una eleccion: el idioma por defecto de una aseguradora sigue aplicando a
 * quien nunca ha elegido (BR2.2). Solo `LOCALE_STORAGE_KEY` dice que hubo eleccion.
 */
export const SHARED_LOCALE_KEY = "cautelia-lang";

/**
 * BR2.1: una pagina sin aseguradora se abre en espanol si el **primer** idioma
 * preferido del navegador empieza por espanol, y en ingles en cualquier otro
 * caso (Q2 de Functional Design: los dos idiomas se tratan igual; nadie busca el
 * selector antes de entender la pagina).
 */
export function deviceLocale(languages: readonly string[]): Locale {
  const primero = languages[0];
  return primero?.toLowerCase().startsWith("es") === true ? "es" : "en";
}

/** Los idiomas preferidos del navegador, en su orden. */
export function browserLanguages(): readonly string[] {
  if (navigator.languages.length > 0) {
    return navigator.languages;
  }
  return navigator.language ? [navigator.language] : [];
}

function readLocaleKey(key: string, storage: () => Storage): Locale | null {
  try {
    const valor = storage().getItem(key);
    return valor === "es" || valor === "en" ? valor : null;
  } catch (error) {
    console.info("untangle: the stored language cannot be read; using the page default", error);
    return null;
  }
}

/** Lee el idioma que la persona eligio; un valor ilegible o ajeno se trata como ausente. */
export function readStoredLocale(
  storage: () => Storage = () => window.localStorage,
): Locale | null {
  return readLocaleKey(LOCALE_STORAGE_KEY, storage);
}

/** Lee el idioma que comparte con la landing (una semilla, no una eleccion). */
export function readSharedLocale(
  storage: () => Storage = () => window.localStorage,
): Locale | null {
  return readLocaleKey(SHARED_LOCALE_KEY, storage);
}

/**
 * Recuerda la eleccion, en la clave propia y en la compartida con la landing. Si
 * no se puede, vale para la pestana y no hay error visible.
 */
export function storeLocale(
  locale: Locale,
  storage: () => Storage = () => window.localStorage,
): boolean {
  try {
    storage().setItem(LOCALE_STORAGE_KEY, locale);
  } catch (error) {
    console.info("untangle: the language choice cannot be stored; it lasts for this tab", error);
    return false;
  }
  try {
    storage().setItem(SHARED_LOCALE_KEY, locale);
  } catch (error) {
    console.info("untangle: the language cannot be shared with the landing", error);
  }
  return true;
}

/**
 * El idioma con el que se abre una pagina (BR2.1): la eleccion de la persona, si
 * la hay; si no, el de la landing; si no, el del dispositivo.
 *
 * Con eleccion, manda el valor compartido cuando existe, porque es el mas
 * reciente: la persona puede haberlo cambiado despues en la landing.
 */
export function initialLanguageChoice(
  languages: readonly string[],
  storage: () => Storage = () => window.localStorage,
): LanguageChoice {
  const elegido = readStoredLocale(storage);
  const compartido = readSharedLocale(storage);
  if (elegido !== null) {
    return { locale: compartido ?? elegido, source: "persisted" };
  }
  if (compartido !== null) {
    return { locale: compartido, source: "device" };
  }
  return { locale: deviceLocale(languages), source: "device" };
}
