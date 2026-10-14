// El selector de modo claro u oscuro, en la barra superior de todas las
// pantallas (interaction-spec.md, ThemeToggle; BR1.1, BR1.3).
//
// El nombre accesible es "Claro" u "Oscuro" con `aria-pressed`, puesto en
// `aria-label`: se ve solo el icono, en todos los anchos (decision de Miguel,
// 2026-10-09: la barra mas corta). El cambio es inmediato y el foco se queda en
// el boton pulsado.

import { MoonIcon, SunIcon } from "@phosphor-icons/react";

import { useLocale } from "../../shared/i18n/locale-provider";
import { useTheme } from "../../shared/theme/theme-provider";
import { SegmentedToggle } from "../../shared/ui/segmented-toggle";

export function ThemeToggle() {
  const { t } = useLocale();
  const { mode, setMode } = useTheme();

  return (
    <SegmentedToggle
      label={t("shell.theme.group")}
      value={mode}
      testId="theme-toggle"
      onChange={setMode}
      look="accent-icon"
      options={[
        {
          value: "light",
          label: t("shell.theme.light"),
          icon: <SunIcon aria-hidden="true" focusable="false" size={18} />,
          iconOnly: true,
        },
        {
          value: "dark",
          label: t("shell.theme.dark"),
          icon: <MoonIcon aria-hidden="true" focusable="false" size={18} />,
          iconOnly: true,
        },
      ]}
    />
  );
}
