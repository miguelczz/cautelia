// Una aseguradora en el inicio (InsurerRow; BR1.6, BR4.1, BR4.2).
//
// **Fila, no tarjeta**: las tres muestran informacion distinta (caracter, emisora) y
// una rejilla de tarjetas iguales es justo el patron generico que el sistema de
// diseno descarta. Todo sale de su configuracion: el monograma y el acento de su
// marca, su nombre y su caracter. Lo que la configuracion no trae no aparece. Los
// botones de canal existen solo si su superficie esta montada y miden 44 x 44: el
// chat lleva el acento de la aseguradora de fondo y la llamada solo en el borde y la
// letra, para acompanarlo sin quitarle protagonismo. El tercero lleva a las polizas de
// esa aseguradora y no depende de ninguna superficie: la columna con el numero de la
// poliza de ejemplo se cambio por este boton (decision de Miguel, 2026-10-09).

import type { SurfaceId, TenantPresentation } from "../../shared/api-client/site";
import { TENANT_CHARACTERS } from "../../shared/copy/tenant-characters";
import { useLocale } from "../../shared/i18n/locale-provider";
import { tenantAccentStyle } from "../../shared/theme/tenant-accent";
import { Button } from "../../shared/ui/button";
import { Monogram } from "../../shared/ui/monogram";
import { INSURER_ROW_GRID } from "../../shared/ui/page-layout";
import { mountedChannels, policiesHref, tenantSurfaceHref } from "../../app/surfaces";

interface InsurerRowProps {
  readonly tenant: TenantPresentation;
  readonly surfaces: readonly SurfaceId[];
}

export function InsurerRow({ tenant, surfaces }: InsurerRowProps) {
  const { t } = useLocale();
  const canales = mountedChannels(surfaces);
  // El caracter llega como clave desde la configuracion y se resuelve por la
  // tabla cerrada generada: una clave que no esta ahi no se dibuja (BR4.2).
  const caracter =
    tenant.character_key === undefined || tenant.character_key === null
      ? undefined
      : TENANT_CHARACTERS.get(tenant.character_key);
  const nombre = tenant.display_name;

  return (
    <li
      data-tenant-scope=""
      data-testid="insurer-row"
      style={tenantAccentStyle(tenant.brand)}
      className={INSURER_ROW_GRID}
    >
      <div className="flex items-start gap-4">
        {tenant.brand ? <Monogram shape={tenant.brand.monogram} /> : null}
        <div className="flex min-w-0 flex-col gap-1">
          <h3 className="text-lead font-medium text-fg" elementtiming="insurer-name">
            {nombre}
          </h3>
          {caracter === undefined ? null : (
            <p className="text-small text-fg-secondary">{caracter(t)}</p>
          )}
        </div>
      </div>
      <div className="flex flex-wrap items-start gap-2 tablet:justify-end">
        {canales.chat ? (
          <Button asChild variant="tenant">
            <a
              href={tenantSurfaceHref("chat", tenant.tenant_id)}
              aria-label={t("home.action.chat_with", { insurer: nombre })}
            >
              {t("home.action.chat")}
            </a>
          </Button>
        ) : null}
        {canales.voice ? (
          <Button asChild variant="tenant-outline">
            <a
              href={tenantSurfaceHref("voice_console", tenant.tenant_id)}
              aria-label={t("home.action.voice_with", { insurer: nombre })}
            >
              {t("home.action.voice")}
            </a>
          </Button>
        ) : null}
        <Button asChild variant="secondary">
          <a
            href={policiesHref(tenant.tenant_id)}
            aria-label={t("home.action.policies_of", { insurer: nombre })}
          >
            {t("home.action.policies")}
          </a>
        </Button>
      </div>
    </li>
  );
}
