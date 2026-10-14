// Plegable: una seccion que se abre y se cierra en su sitio, sobre `Collapsible`
// de Radix (el patron de shadcn/ui), tematizado con los tokens.
//
// El disparador es un boton de al menos 44 de alto con `aria-expanded`; la flecha
// es decorativa y gira solo sin movimiento reducido. Estados del disparador: los
// del boton. El contenido aparece por opacidad en 200 ms, sin animar su altura
// (design-system-mapping.md, Movimiento).

import * as Collapsible from "@radix-ui/react-collapsible";
import { CaretDownIcon } from "@phosphor-icons/react";
import type { ComponentProps } from "react";

import { cn } from "./cn";

export const Disclosure = Collapsible.Root;

/** La flecha del disparador: gira al abrir. Decorativa. */
export function DisclosureCaret({ className }: { readonly className?: string }) {
  return (
    <CaretDownIcon
      aria-hidden="true"
      focusable="false"
      size={16}
      className={cn(
        "shrink-0 text-fg-secondary motion-safe:transition-transform motion-safe:duration-[200ms] group-data-[state=open]:rotate-180",
        className,
      )}
    />
  );
}

export function DisclosureTrigger({
  className,
  children,
  caret = true,
  ...props
}: ComponentProps<typeof Collapsible.Trigger> & {
  /** Con `false` la flecha no se dibuja al final: quien lo usa la pone con `DisclosureCaret`. */
  readonly caret?: boolean;
}) {
  return (
    <Collapsible.Trigger
      className={cn(
        "group inline-flex min-h-11 min-w-11 items-center gap-2 rounded-control px-2 text-left",
        "font-body text-body font-medium text-fg",
        "transition-colors duration-[160ms] ease-out hover:bg-surface-alt",
        "disabled:cursor-not-allowed disabled:opacity-60",
        className,
      )}
      {...props}
    >
      {children}
      {caret ? <DisclosureCaret /> : null}
    </Collapsible.Trigger>
  );
}

export function DisclosureContent({
  className,
  ...props
}: ComponentProps<typeof Collapsible.Content>) {
  return (
    <Collapsible.Content
      className={cn(
        "data-[state=open]:animate-[ut-fade-in_200ms_var(--ease-out)] motion-reduce:animate-none",
        className,
      )}
      {...props}
    />
  );
}
