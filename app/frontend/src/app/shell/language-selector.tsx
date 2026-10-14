// El selector de idioma (interaction-spec.md, LanguageSelector; BR2.5).
//
// Se ven los codigos ES y EN, como en la pastilla de la landing; el nombre
// accesible sigue siendo el completo, cada uno en su propia lengua y con su
// atributo de idioma (U-04, BR2.4). El cambio se anuncia **una vez**, en el
// idioma nuevo, y el foco se queda en el selector. La eleccion se recuerda entre
// visitas en todas las pantallas: la guarda el proveedor de idioma.

import type { Locale } from "../../shared/copy/copy-keys";
import { useLocale } from "../../shared/i18n/locale-provider";
import { createTranslate } from "../../shared/i18n/translate";
import { useAnnouncer } from "../../shared/ui/announcer";
import { SegmentedToggle } from "../../shared/ui/segmented-toggle";

export function LanguageSelector() {
  const { locale, setLocale, t } = useLocale();
  const { announce } = useAnnouncer();

  const elegir = (siguiente: Locale) => {
    setLocale(siguiente);
    const enElIdiomaNuevo = createTranslate(siguiente);
    announce(enElIdiomaNuevo("shell.language.changed"));
  };

  return (
    <SegmentedToggle
      label={t("shell.language.group")}
      value={locale}
      testId="language-selector"
      onChange={elegir}
      look="underline-copper"
      options={[
        { value: "es", label: t("shell.language.es"), lang: "es", short: "ES" },
        { value: "en", label: t("shell.language.en"), lang: "en", short: "EN" },
      ]}
    />
  );
}
