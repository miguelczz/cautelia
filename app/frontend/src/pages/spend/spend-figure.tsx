// Una cifra grande que cabe en su tarjeta, sea cual sea (2026-10-11).
//
// "0,000684 US$" y "38,33 US$" no miden lo mismo, y con un tamano fijo la larga se
// salia de la tarjeta. El tamano sale del ancho de la tarjeta dividido entre cuantos
// caracteres tiene la cifra: la tarjeta es un contenedor (`@container`) y `cqi` es
// el ancho de su contenido. Nunca pasa de `MAXIMO`, la escala de la pagina, y nunca
// baja de `MINIMO`; si aun asi no cupiera, parte la linea en vez de salirse, y no la
// recorta con puntos suspensivos: una cifra cortada dice otra cosa.

import type { CSSProperties } from "react";

import { cn } from "../../shared/ui/cn";

/**
 * El tamano: `MAXIMO` cuando cabe, menos cuando no. 0,62 em es lo que mide, como
 * mucho, un caracter de la fuente de las cifras; ir por encima deja margen.
 */
const TAMANO = "text-[length:clamp(1.25rem,calc(100cqi/(var(--figure-chars)*0.62)),2.5rem)]";

/** La clase que vuelve contenedor a la tarjeta que contiene una `Figure`. */
export const CONTENEDOR_DE_CIFRA = "@container";

export function Figure({
  children,
  className,
}: {
  readonly children: string;
  readonly className?: string;
}) {
  return (
    // El renglon de la cifra mide siempre lo mismo (2,5 rem: el tamano maximo, o dos lineas
    // del minimo) y la cifra se apoya abajo: la que se encoge para caber no sube lo que
    // tiene debajo, y las cifras de una fila de tarjetas quedan en el mismo nivel.
    <span className="flex min-h-10 items-end">
      <span
        // `leading-none` va despues del tamano: `cn` descarta el interlineado que precede a
        // un tamano de letra (un `text-*` lo trae incluido), y sin el la cifra heredaba el
        // 1,55 del cuerpo y su renglon crecia o encogia con ella.
        className={cn(
          "block font-display font-light text-fg tabular-nums [overflow-wrap:anywhere]",
          TAMANO,
          "leading-none",
          className,
        )}
        style={{ "--figure-chars": children.length } as CSSProperties}
        data-testid="spend-figure"
      >
        {children}
      </span>
    </span>
  );
}
