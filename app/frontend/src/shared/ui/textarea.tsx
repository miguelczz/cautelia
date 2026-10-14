// Campo de texto de varias lineas: la misma primitiva que `Input`, con los mismos
// siete estados y la misma regla de etiqueta visible.

import type { Ref, TextareaHTMLAttributes } from "react";

import { cn } from "./cn";
import { fieldClasses } from "./input";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  readonly invalid?: boolean;
  readonly loading?: boolean;
  readonly ref?: Ref<HTMLTextAreaElement>;
}

export function Textarea({
  className,
  invalid = false,
  loading = false,
  rows,
  ...props
}: TextareaProps) {
  return (
    <textarea
      rows={rows ?? 4}
      className={cn(fieldClasses, "py-2 leading-[1.55]", className)}
      aria-invalid={invalid || undefined}
      aria-busy={loading || undefined}
      {...props}
    />
  );
}
