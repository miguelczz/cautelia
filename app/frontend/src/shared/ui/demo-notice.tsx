// El aviso fijo de demostracion de las pantallas de canal (interaction-spec.md,
// DemoNotice). Lo construye U6 y lo usan el chat, la consola, la comparacion y la
// vista por enlace, que traen su propio texto.
//
// - Por defecto: una linea bajo la cabecera.
// - Compacto (`compact`): la linea corta con "Mas informacion", que abre el texto
//   completo en su sitio. Nunca desaparece.
// - Region con nombre, leida en el orden natural tras la cabecera; **no** es una
//   region en vivo.

import { useId, useState } from "react";

import { useLocale } from "../i18n/locale-provider";
import type { Message } from "../i18n/translate";
import { cn } from "./cn";

interface DemoNoticeProps {
  /** El aviso completo, con la clave del catalogo que trae cada canal. */
  readonly message: Message;
  /** La version corta del aviso, para el modo compacto. */
  readonly shortMessage?: Message;
  /** Compacto: la pantalla lo pide en telefono al desplazarse. */
  readonly compact?: boolean;
  readonly className?: string;
}

export function DemoNotice({ message, shortMessage, compact = false, className }: DemoNoticeProps) {
  const { t } = useLocale();
  const [abierto, setAbierto] = useState(false);
  const detalle = useId();
  const plegado = compact && shortMessage !== undefined && !abierto;

  return (
    <section
      aria-label={t("demo.notice.label")}
      data-testid="demo-notice"
      className={cn(
        "sticky top-0 z-20 border-b border-hairline bg-bar px-4 py-2 text-small text-fg-secondary",
        className,
      )}
    >
      <div className="mx-auto flex max-w-content flex-wrap items-center gap-x-3 gap-y-1">
        <p id={detalle}>{plegado ? shortMessage(t) : message(t)}</p>
        {compact && shortMessage !== undefined ? (
          <button
            type="button"
            aria-expanded={abierto}
            aria-controls={detalle}
            onClick={() => {
              setAbierto((actual) => !actual);
            }}
            className="inline-flex min-h-11 items-center rounded-control px-2 font-medium text-link underline underline-offset-4"
          >
            {abierto ? t("demo.notice.less") : t("demo.notice.more")}
          </button>
        ) : null}
      </div>
    </section>
  );
}
