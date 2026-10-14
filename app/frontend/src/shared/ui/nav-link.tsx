// Los enlaces de la barra (decision de Miguel, 2026-10-09): texto en la fuente de titulos,
// en negrita, sin caja y siempre en la tinta de mayor contraste (blanco en oscuro). Debajo de la palabra crece, de izquierda a derecha, una linea en el
// cobre de la marca al pasar el puntero o enfocar con teclado, y queda entera bajo la
// pagina actual. Sin movimiento (`prefers-reduced-motion`) la linea aparece de golpe.
//
// El enlace entero es el objetivo tactil (44 de alto). La pagina actual se marca con
// `aria-current` y con la linea, no solo con color.
//
// Sin texto --solo un icono, como el que vuelve a la landing-- es un cuadrado de 44 x 44
// con el tinte de la barra al pasar el puntero, y tiene que llevar su nombre en
// `aria-label`.

import type { AnchorHTMLAttributes, ReactNode } from "react";

import { cn } from "./cn";

interface NavLinkProps extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "children"> {
  readonly href: string;
  readonly icon?: ReactNode;
  /** La pagina actual: se marca con `aria-current` y con la linea entera. */
  readonly current?: boolean;
  readonly children?: ReactNode;
}

export function NavLink({ icon, current = false, className, children, ...props }: NavLinkProps) {
  const soloIcono = children === undefined || children === null;
  return (
    <a
      aria-current={current ? "page" : undefined}
      className={cn(
        "group inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center gap-1.5 no-underline",
        "transition-colors duration-[160ms] ease-out",
        soloIcono
          ? "rounded-button text-fg hover:bg-surface-alt"
          : [
              "px-2 font-display text-body font-semibold tracking-tight whitespace-nowrap",
              "text-fg",
            ],
        className,
      )}
      {...props}
    >
      {icon}
      {soloIcono ? null : (
        <span className="relative">
          {children}
          <span
            aria-hidden="true"
            className={cn(
              "pointer-events-none absolute inset-x-0 -bottom-0.5 h-0.5 origin-left bg-copper",
              "motion-safe:transition-transform motion-safe:duration-[240ms] motion-safe:ease-out",
              current
                ? "scale-x-100"
                : "scale-x-0 group-hover:scale-x-100 group-focus-visible:scale-x-100",
            )}
          />
        </span>
      )}
    </a>
  );
}
