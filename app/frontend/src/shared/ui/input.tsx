// Campo de texto de una linea: primitiva del patron de shadcn/ui tematizada con
// los tokens. La etiqueta visible la pone siempre quien lo usa, con `<label>`
// (frontend-components.md, seccion 4): nunca solo un marcador de posicion.
//
// Estados: por defecto, encima, foco, activo (escribiendo), deshabilitado,
// cargando (`aria-busy`) y error (`invalid`, asociado a su mensaje con
// `aria-describedby`). Mide al menos 44 de alto (BR7.3).

import type { InputHTMLAttributes, Ref } from "react";

import { cn } from "./cn";

export const fieldClasses = [
  "min-h-11 w-full rounded-control border border-control bg-surface-alt px-3",
  "font-body text-body text-fg placeholder:text-fg-tertiary",
  "transition-[border-color,background-color] duration-[160ms] ease-out",
  "hover:border-fg-secondary",
  // Con foco, la propia raya del campo cambia al color de foco --el acento de la
  // aseguradora dentro de su ambito, el cobre fuera-- y se hace de 2 px hacia adentro: no
  // se dibuja un anillo aparte alrededor (decision de Miguel, 2026-10-07). Sigue siendo
  // un contorno de 2 px, que es lo que el arnes exige de todo lo que recibe el foco.
  "focus-visible:-outline-offset-2 not-aria-invalid:focus-visible:border-focus",
  "aria-invalid:focus-visible:outline-danger",
  "disabled:cursor-not-allowed disabled:opacity-60",
  "aria-busy:cursor-progress",
  "aria-invalid:border-danger aria-invalid:border-2",
].join(" ");

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  readonly invalid?: boolean;
  readonly loading?: boolean;
  readonly ref?: Ref<HTMLInputElement>;
}

export function Input({ className, invalid = false, loading = false, ...props }: InputProps) {
  return (
    <input
      className={cn(fieldClasses, className)}
      aria-invalid={invalid || undefined}
      aria-busy={loading || undefined}
      {...props}
    />
  );
}
