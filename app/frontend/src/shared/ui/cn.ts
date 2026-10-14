// Une clases de Tailwind resolviendo los conflictos: la utilidad `cn` del patron
// de shadcn/ui. `clsx` arma la lista y `tailwind-merge` deja la ultima de cada
// propiedad, para que una variante pueda sobrescribir la base sin `!important`.

import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// Los tamanos de texto del sistema de diseno no son los de Tailwind: sin
// declararlos, `tailwind-merge` confundiria `text-small` (tamano) con
// `text-fg` (color) y borraria uno de los dos.
const unir = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: ["caption", "small", "body", "lead", "title", "figure", "display"] }],
    },
  },
});

export function cn(...inputs: ClassValue[]): string {
  return unir(clsx(inputs));
}
