// El monograma de una aseguradora: una forma geometrica sencilla, sin logotipos
// ilustrados (design-system-mapping.md, Aseguradoras ficticias).
//
// La configuracion elige la forma (`brand.monogram`) y el codigo solo sabe
// dibujar tres; no sabe que aseguradora usa cual (BR1.6, convencion 9). Se pinta
// con el acento de la aseguradora en el modo actual (`text-tenant`). Es
// decorativo y esta oculto para el lector de pantalla, porque el nombre va
// escrito al lado (BR7.7).

import type { Monogram as MonogramShape } from "../api-client/site";
import { cn } from "./cn";

interface MonogramProps {
  readonly shape: MonogramShape;
  readonly className?: string;
}

export function Monogram({ shape, className }: MonogramProps) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 48 48"
      width="48"
      height="48"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      data-monogram={shape}
      className={cn("shrink-0 text-tenant", className)}
    >
      <rect x="1.25" y="1.25" width="45.5" height="45.5" rx="12" strokeWidth="1.5" />
      {shape === "arch" ? (
        <path d="M14 36V24a10 10 0 0 1 20 0v12M10 36h28M19 36v-9a5 5 0 0 1 10 0v9" />
      ) : null}
      {shape === "horizon" ? (
        <>
          <path d="M9 31h30M13 36h22" />
          <path d="M16 31a8 8 0 0 1 16 0" />
          <path d="M24 14v3M14.5 18.5l2 2M33.5 18.5l-2 2" />
        </>
      ) : null}
      {shape === "rings" ? (
        <>
          <circle cx="19" cy="24" r="8" />
          <circle cx="29" cy="24" r="8" />
        </>
      ) : null}
    </svg>
  );
}
