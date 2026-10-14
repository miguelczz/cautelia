// "Saltar al contenido": el primer elemento que recibe el foco con Tab en cada
// pantalla (BR7.4). Invisible hasta que tiene el foco; entonces aparece arriba a
// la izquierda con el anillo del sistema y mide 44 de alto.

import { useLocale } from "../../shared/i18n/locale-provider";

export const MAIN_CONTENT_ID = "main-content";

export function SkipLink() {
  const { t } = useLocale();
  return (
    <a
      href={`#${MAIN_CONTENT_ID}`}
      data-testid="skip-link"
      className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-40 focus:inline-flex focus:min-h-11 focus:items-center focus:rounded-button focus:bg-brand focus:px-5 focus:font-medium focus:text-on-brand focus:no-underline"
      onClick={() => {
        // El destino es `<main>`, que no es interactivo: se le pasa el foco a mano
        // para que el siguiente Tab siga desde el contenido.
        document.getElementById(MAIN_CONTENT_ID)?.focus();
      }}
    >
      {t("shell.skip_to_content")}
    </a>
  );
}
