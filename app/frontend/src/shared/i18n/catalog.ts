// Las frases de cada idioma, cargadas cuando hacen falta (2026-10-09).
//
// El catalogo es lo mas pesado de lo que se descarga antes de la pagina de espera
// (PERF-U6.1, 200 KB), y con los dos idiomas juntos la pasaba. Ahora cada idioma es
// su propio modulo: `main.tsx` carga el del arranque antes de pintar y el otro justo
// despues, asi que cambiar de idioma sigue siendo inmediato. Si se pide uno que
// todavia no llego, `translate` usa el que ya esta y la pantalla se vuelve a dibujar
// en cuanto llega (`subscribe`).

import type { CopyKey, Locale } from "../copy/copy-keys";

type Phrases = ReadonlyMap<CopyKey, string>;

const CARGADORES: Record<Locale, () => Promise<{ default: Phrases }>> = {
  es: () => import("../copy/copy-texts.es"),
  en: () => import("../copy/copy-texts.en"),
};

const cargados = new Map<Locale, Phrases>();
const enCamino = new Map<Locale, Promise<void>>();
const oyentes = new Set<() => void>();
let version = 0;

/** Carga las frases de un idioma; si ya estan, no hace nada. */
export function loadLocale(locale: Locale): Promise<void> {
  if (cargados.has(locale)) {
    return Promise.resolve();
  }
  const pendiente = enCamino.get(locale);
  if (pendiente !== undefined) {
    return pendiente;
  }
  const cargador = locale === "es" ? CARGADORES.es : CARGADORES.en;
  const carga = cargador().then((modulo) => {
    cargados.set(locale, modulo.default);
    enCamino.delete(locale);
    version += 1;
    for (const oyente of oyentes) {
      oyente();
    }
  });
  enCamino.set(locale, carga);
  return carga;
}

/** Las frases de ese idioma, o las del otro mientras ese no ha llegado. */
export function phrasesFor(locale: Locale): Phrases | undefined {
  return cargados.get(locale) ?? cargados.values().next().value;
}

/** Para `useSyncExternalStore`: avisa cuando llega un idioma. */
export function subscribe(oyente: () => void): () => void {
  oyentes.add(oyente);
  return () => {
    oyentes.delete(oyente);
  };
}

/** Cuantos idiomas han llegado: cambia cuando llega uno. */
export function catalogVersion(): number {
  return version;
}
