// El idioma de la pagina y su `t()` (entidad LanguageChoice; BR2.1 a BR2.4).
//
// El idioma vive en el estado de la pestana: cambia sin recargar. Cada eleccion se
// recuerda entre visitas, en todas las pantallas, y se comparte con la landing
// (decision de Miguel, 2026-10-06): los enlaces del inicio recargan la pagina y el
// idioma elegido no puede perderse ahi. Con el modo, es una de las dos preferencias
// que la interfaz guarda en el navegador (BR3.5).

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import type { Locale } from "../copy/copy-keys";
import {
  browserLanguages,
  initialLanguageChoice,
  storeLocale,
  type LanguageChoice,
  type LocaleSource,
} from "./initial-locale";
import { catalogVersion, loadLocale, subscribe } from "./catalog";
import { createTranslate, type Translate } from "./translate";

export interface LocaleContextValue {
  readonly locale: Locale;
  readonly source: LocaleSource;
  readonly t: Translate;
  /** La eleccion de la persona con el selector: se recuerda entre visitas. */
  readonly setLocale: (locale: Locale) => void;
  /**
   * Lo que hace una pagina de aseguradora al abrirse: toma su idioma por
   * defecto, **salvo** que la persona ya haya elegido en esta pestana (BR2.2).
   */
  readonly adoptTenantDefault: (locale: Locale) => void;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

interface LocaleProviderProps {
  readonly children: ReactNode;
  /** El idioma inicial; por omision, el del dispositivo (BR2.1). */
  readonly initial?: LanguageChoice;
}

export function LocaleProvider({ children, initial }: LocaleProviderProps) {
  const [eleccion, setEleccion] = useState<LanguageChoice>(
    () => initial ?? initialLanguageChoice(browserLanguages()),
  );
  // Las frases del idioma pueden llegar despues de elegirlo: al llegar, se redibuja.
  const catalogo = useSyncExternalStore(subscribe, catalogVersion, catalogVersion);
  useEffect(() => {
    void loadLocale(eleccion.locale);
  }, [eleccion.locale]);

  // El documento declara su idioma (BR2.4). Antes de pintar, para que un lector
  // de pantalla nunca lea la pagina con la pronunciacion del otro idioma.
  useLayoutEffect(() => {
    document.documentElement.lang = eleccion.locale;
  }, [eleccion.locale]);

  const setLocale = useCallback((locale: Locale) => {
    storeLocale(locale);
    setEleccion({ locale, source: "user" });
  }, []);

  const adoptTenantDefault = useCallback((locale: Locale) => {
    setEleccion((actual) =>
      actual.source === "user" || actual.source === "persisted"
        ? actual
        : { locale, source: "tenant_default" },
    );
  }, []);

  const valor = useMemo<LocaleContextValue>(
    () => ({
      locale: eleccion.locale,
      source: eleccion.source,
      t: createTranslate(eleccion.locale),
      setLocale,
      adoptTenantDefault,
    }),
    // `catalogo` cambia cuando llega un idioma: el `t` nuevo ya lo ve.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- el valor no se lee, solo invalida
    [eleccion, setLocale, adoptTenantDefault, catalogo],
  );

  return <LocaleContext.Provider value={valor}>{children}</LocaleContext.Provider>;
}

export function useLocale(): LocaleContextValue {
  const valor = useContext(LocaleContext);
  if (valor === null) {
    throw new Error("useLocale needs a LocaleProvider above it");
  }
  return valor;
}

/**
 * BR2.2: una pagina de aseguradora se abre en su idioma por defecto, el de su
 * configuracion, salvo eleccion hecha en la pestana. Lo llaman las pantallas de
 * canal (U13, U16) con el `default_language` de su aseguradora.
 */
export function useTenantDefaultLocale(defaultLanguage: Locale): void {
  const { adoptTenantDefault } = useLocale();
  useEffect(() => {
    adoptTenantDefault(defaultLanguage);
  }, [adoptTenantDefault, defaultLanguage]);
}
