// El titulo de un paso del panel del ajustador, con su marca numerica (2026-10-14).
//
// La marca es decoracion: el lector de pantalla lee el titulo y el orden lo dan los
// encabezados, asi que el numero va oculto para el y no se repite. Sale de los tokens de la
// marca --`bg-brand` con `text-on-brand`--, que en modo claro es la tinta y en oscuro el cobre:
// ninguno de los dos modos pone el cobre como letra sobre fondo claro. Sin numero (un panel
// con un solo paso) el titulo se dibuja igual, sin marca.

import type { ReactNode } from "react";

import { BLOCK_TITLE } from "../../shared/ui/page-layout";

export function StepHeading({
  id,
  step,
  children,
}: {
  readonly id: string;
  /** El numero del paso, o nada cuando es el unico del panel. */
  readonly step?: number | undefined;
  readonly children: ReactNode;
}) {
  return (
    <h3 id={id} className={`${BLOCK_TITLE} flex items-center gap-3`}>
      {step === undefined ? null : (
        <span
          aria-hidden="true"
          data-testid="step-mark"
          className="inline-flex size-7 shrink-0 items-center justify-center rounded-pill bg-brand font-body text-small font-medium text-on-brand"
        >
          {step}
        </span>
      )}
      {children}
    </h3>
  );
}
