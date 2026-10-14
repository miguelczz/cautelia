// La ayuda para dar la poliza de ejemplo en la llamada: un boton como las sugerencias del
// chat que, al tocarlo, muestra el nombre y el numero que hay que decir cuando la agente
// los pida (decision de Miguel, 2026-10-09). Reemplaza la ficha con el numero y el texto
// largo sobre datos reales, que ocupaban la pantalla antes de poder llamar.
//
// Sigue visible durante la llamada: es justo cuando la agente pregunta la poliza cuando
// hace falta. Sin titular --lo trae la lista de polizas, no el directorio-- se da solo el
// numero; no se inventa un nombre.

import { IdentificationCardIcon } from "@phosphor-icons/react";
import { useId, useState } from "react";

import { useLocale } from "../../shared/i18n/locale-provider";
import { Button } from "../../shared/ui/button";
import { AYUDA_DE_LLAMADA } from "./call-helper-style";

interface SamplePolicyHelperProps {
  readonly policy: string;
  readonly holder?: string | undefined;
}

export function SamplePolicyHelper({ policy, holder }: SamplePolicyHelperProps) {
  const { t } = useLocale();
  const [abierta, setAbierta] = useState(false);
  const panel = useId();
  const frase =
    holder === undefined
      ? t("voice.console.sample_say_number", { policy })
      : t("voice.console.sample_say", { name: holder, policy });

  return (
    <div className="flex w-full flex-col items-center gap-3" data-testid="sample-policy-helper">
      <Button
        type="button"
        variant="secondary"
        size="compact"
        className={AYUDA_DE_LLAMADA}
        aria-expanded={abierta}
        aria-controls={panel}
        onClick={() => {
          setAbierta((previa) => !previa);
        }}
      >
        <IdentificationCardIcon
          aria-hidden="true"
          focusable="false"
          size={18}
          className="text-tenant"
        />
        {t("voice.console.sample_button")}
      </Button>
      <div id={panel} hidden={!abierta} className="w-full">
        {abierta ? (
          <div className="flex flex-col gap-1 rounded-surface bg-selected p-4 text-center">
            <p className="text-small text-fg-secondary">{t("voice.console.sample_intro")}</p>
            <p className="font-mono text-body text-fg" data-testid="sample-policy-say">
              {frase}
            </p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
