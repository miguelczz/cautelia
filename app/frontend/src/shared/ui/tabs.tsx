// Pestanas sobre `Tabs` de Radix (el patron de shadcn/ui), tematizadas con los
// tokens. Radix pone los roles y el teclado (flechas entre pestanas); aqui van el
// aspecto y los 44 x 44 de cada pestana (BR7.3).
//
// La pestana elegida se marca con un borde inferior, con el peso del texto y con el
// tinte de "elegido" de fondo (2026-10-09: la sombra sola se perdia contra el fondo),
// no solo con color (BR7.6). Cambiar de pestana con el teclado no se anima.

import * as TabsPrimitive from "@radix-ui/react-tabs";
import type { ComponentProps } from "react";

import { cn } from "./cn";

export const Tabs = TabsPrimitive.Root;

export function TabsList({ className, ...props }: ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn("flex flex-wrap gap-1 border-b border-hairline", className)}
      {...props}
    />
  );
}

export function TabsTrigger({ className, ...props }: ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "-mb-px inline-flex min-h-11 min-w-11 items-center justify-center rounded-t-button border-b-2 border-transparent px-4",
        "font-body text-body text-fg-secondary",
        "transition-colors duration-[160ms] ease-out hover:bg-surface-alt hover:text-fg",
        "data-[state=active]:border-brand data-[state=active]:bg-selected data-[state=active]:font-medium data-[state=active]:text-fg",
        "disabled:cursor-not-allowed disabled:opacity-60",
        className,
      )}
      {...props}
    />
  );
}

export function TabsContent({ className, ...props }: ComponentProps<typeof TabsPrimitive.Content>) {
  return <TabsPrimitive.Content className={cn("pt-4", className)} {...props} />;
}
