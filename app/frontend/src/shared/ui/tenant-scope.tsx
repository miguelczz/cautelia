// El ambito de una aseguradora: dentro, el acento de su marca reemplaza al cobre de
// Cautelia en todo lo que lo usa (botones, burbujas, anillo de foco). Fuera --la barra,
// el pie-- sigue el cobre: la marca del aplicativo no cambia, cambia la pantalla de la
// aseguradora en la que esta la persona (decision de Miguel, 2026-10-07).
//
// `display: contents`: el ambito no es una caja, solo lleva las variables, asi que no
// altera ninguna distribucion (el chat llena la vista y depende de ello). Los dos
// valores del acento --claro y oscuro-- los elige `tokens.css` segun el modo.

import type { ReactNode } from "react";

import { tenantAccentStyle, type TenantAccent } from "../theme/tenant-accent";

export function TenantScope({
  brand,
  children,
}: {
  readonly brand: TenantAccent | null | undefined;
  readonly children: ReactNode;
}) {
  return (
    <div data-tenant-scope="" style={tenantAccentStyle(brand)} className="contents">
      {children}
    </div>
  );
}
