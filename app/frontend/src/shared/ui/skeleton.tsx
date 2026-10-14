// Esqueleto de carga: el lugar que ocupara un contenido que todavia no llego.
// Decorativo y oculto al lector; quien lo usa anuncia la carga con un texto
// (por ejemplo, `aria-busy` y una etiqueta en la region). Con movimiento
// reducido no late.

import type { HTMLAttributes } from "react";

import { cn } from "./cn";

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn("rounded-control bg-surface-alt motion-safe:animate-pulse", className)}
      {...props}
    />
  );
}
