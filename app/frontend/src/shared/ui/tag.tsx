// Etiqueta: una marca corta que clasifica algo (un estado, un idioma). Es
// presentacional, no interactiva, y por eso no tiene foco ni encima; su tono
// sale de los tokens semanticos y **nunca** del acento de una aseguradora
// (BR1.6). El tono nunca es la unica senal: la etiqueta siempre lleva su texto
// (BR7.6).

import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "./cn";

export const tagVariants = cva(
  "inline-flex items-center gap-1 rounded-control border px-2 py-0.5 font-body text-small font-medium",
  {
    variants: {
      tone: {
        neutral: "border-hairline text-fg-secondary",
        brand: "border-brand text-brand",
        success: "border-success text-success",
        warning: "border-warning text-warning",
        danger: "border-danger text-danger",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export interface TagProps
  extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof tagVariants> {}

export function Tag({ className, tone, ...props }: TagProps) {
  return <span className={cn(tagVariants({ tone }), className)} {...props} />;
}
