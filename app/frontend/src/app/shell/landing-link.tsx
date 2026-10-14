// El icono que vuelve a la landing, al final de la barra (decision de Miguel,
// 2026-10-07: "muy grande" como boton con texto; solo un icono y en la ultima posicion).
//
// Un icono de 44 x 44 sin caja, como el resto de la barra. Sin texto, su
// nombre accesible es el completo y se repite en `title`, que es la ayuda que sale al
// dejar el puntero encima.

import { HouseSimpleIcon } from "@phosphor-icons/react";

import { useLocale } from "../../shared/i18n/locale-provider";
import { LANDING_URL } from "../../shared/site/landing";
import { NavLink } from "../../shared/ui/nav-link";

export function LandingLink() {
  const { t } = useLocale();
  return (
    <NavLink
      href={LANDING_URL}
      icon={<HouseSimpleIcon aria-hidden="true" focusable="false" size={18} />}
      aria-label={t("shell.nav.landing")}
      title={t("shell.nav.landing")}
      data-testid="nav-landing"
    />
  );
}
