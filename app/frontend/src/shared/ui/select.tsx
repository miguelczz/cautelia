// Selector: el `<select>` **nativo** tematizado con los tokens (el patron
// `native-select` de shadcn/ui), y no el menu de Radix.
//
// La razon es la politica de contenido: el menu de Radix bloquea el desplazamiento
// del fondo inyectando etiquetas `<style>` en linea, y `style-src 'self'`
// (CG-U6-2) las bloquea; el arnes fallaria con la violacion en la consola. El
// nativo ademas es el mas accesible en un telefono, donde abre el selector del
// sistema.
//
// Estados: los de `Input`, mas la flecha decorativa oculta al lector.

import { CaretDownIcon } from "@phosphor-icons/react";
import type { Ref, SelectHTMLAttributes } from "react";

import { cn } from "./cn";
import { fieldClasses } from "./input";

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  readonly invalid?: boolean;
  readonly loading?: boolean;
  readonly ref?: Ref<HTMLSelectElement>;
}

export function Select({
  className,
  invalid = false,
  loading = false,
  children,
  ...props
}: SelectProps) {
  return (
    <span className="relative block">
      <select
        className={cn(fieldClasses, "appearance-none pr-10", className)}
        aria-invalid={invalid || undefined}
        aria-busy={loading || undefined}
        {...props}
      >
        {children}
      </select>
      <CaretDownIcon
        aria-hidden="true"
        focusable="false"
        size={16}
        className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-fg-secondary"
      />
    </span>
  );
}
