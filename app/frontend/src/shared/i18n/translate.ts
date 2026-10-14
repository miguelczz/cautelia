// `t()`: la unica forma de poner texto en una pantalla (BR2.3, C-21).
//
// Recibe una clave del modulo generado --una clave que no existe es un error de
// tipos, no un texto vacio-- y devuelve su frase en el idioma de la pagina.
//
// Las claves se escriben **literales** en cada llamada: `t("home.title")`. El
// chequeo del catalogo (BR3.4) rechaza la llamada con una clave guardada en una
// variable, porque una clave que viaja como dato no se encuentra con un grep, y
// entonces nadie sabe si tiene consumidor. Cuando una pantalla necesita elegir
// el texto a partir de un dato --un tipo de pagina de estado, un codigo de
// error--, lo hace con una tabla de `Message`: funciones que reciben `t` y lo
// llaman con su clave literal.

import type { CopyKey, Locale } from "../copy/copy-keys";
import { phrasesFor } from "./catalog";

/** Las variables de una frase: `{insurer}` en "Abrir chat con {insurer}". */
export type CopyVars = Readonly<Record<string, string | number>>;

export type Translate = (key: CopyKey, vars?: CopyVars) => string;

/** Un texto elegido a partir de un dato, con su clave escrita literal dentro. */
export type Message = (t: Translate) => string;

/**
 * Una frase pide una variable que quien la resuelve no paso. Falla ruidosamente,
 * igual que el catalogo del servidor: una frase a medio sustituir que llega a
 * una persona es peor que un fallo, porque nadie la ve hasta que ya salio.
 */
export class MissingCopyVariableError extends Error {
  constructor(key: CopyKey, variable: string) {
    super(`copy key "${key}" needs the variable "${variable}", which was not given`);
    this.name = "MissingCopyVariableError";
  }
}

const VARIABLE = /\{(\w+)\}/g;

/** Sustituye las variables de una frase; una que falta lanza. */
export function formatCopy(key: CopyKey, text: string, vars?: CopyVars): string {
  return text.replace(VARIABLE, (_, nombre: string) => {
    const valor = vars === undefined ? undefined : Object.entries(vars).find(([k]) => k === nombre);
    if (valor === undefined) {
      throw new MissingCopyVariableError(key, nombre);
    }
    return String(valor[1]);
  });
}

/**
 * El resolvedor de un idioma. Si la entrada falta en ese idioma, devuelve **la
 * clave misma** y lo dice en la consola, nunca una cadena vacia (C-21): una
 * cadena vacia parece un problema de maquetacion y se busca donde no es.
 */
export function createTranslate(locale: Locale): Translate {
  return (key, vars) => {
    // Al llamar y no al crear: el idioma puede llegar despues (`catalog.ts`).
    const frase = phrasesFor(locale)?.get(key);
    if (frase === undefined) {
      console.warn(`untangle: copy key "${key}" has no entry for "${locale}"`);
      return key;
    }
    return formatCopy(key, frase, vars);
  };
}
