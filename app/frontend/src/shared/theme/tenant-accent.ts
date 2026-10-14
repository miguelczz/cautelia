// El acento de una aseguradora, inyectado desde su configuracion (BR1.6).
//
// El codigo no sabe que aseguradora usa que color: recibe los dos valores de su
// marca (`brand.accent` para el modo claro y `brand.accent_on_dark` para el
// oscuro) tal como los sirve `GET /api/site`, y los deja como variables en el
// elemento que la representa. `tokens.css` elige cual vale segun el modo. Sin
// marca, no se inyecta nada y el acento es el de Cautelia (CG-U6-4).
//
// Las variables se ponen por el objeto de estilos de React, que las escribe por
// el modelo de objetos de CSS y no como atributo `style` en el marcado: la
// politica de contenido (`style-src 'self'`, CG-U6-2) no lo bloquea.

import type { CSSProperties } from "react";

export interface TenantAccent {
  readonly accent: string;
  readonly accent_on_dark: string;
}

/** El estilo del elemento que abre el ambito de una aseguradora. */
export function tenantAccentStyle(
  brand: TenantAccent | null | undefined,
): CSSProperties | undefined {
  if (brand === null || brand === undefined) {
    return undefined;
  }
  return {
    "--tenant-accent": brand.accent,
    "--tenant-accent-on-dark": brand.accent_on_dark,
  } as CSSProperties;
}
