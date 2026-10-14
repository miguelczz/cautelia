// La marca de Cautelia: una onda de voz de un solo trazo, la misma que lleva la
// landing (`site/index.html`), que es el diseno que manda. Es el icono
// `audio-waveform` de Lucide (ISC); su atribucion esta en `DEPENDENCIES.md` y el
// texto de la licencia en `site/LUCIDE-LICENSE.txt`. Decision de Miguel del
// 2026-10-11: la anterior, una C de dos arcos, parecia el sello de una entidad.
//
// Se pinta con el cobre de la marca del modo actual y es decorativa: el nombre va
// escrito al lado.

import { cn } from "./cn";

interface BrandMarkProps {
  readonly className?: string;
}

export function BrandMark({ className }: BrandMarkProps) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 24 24"
      width="28"
      height="28"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.25"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn("shrink-0 text-brand", className)}
    >
      <path d="M2 13a2 2 0 0 0 2-2V7a2 2 0 0 1 4 0v13a2 2 0 0 0 4 0V4a2 2 0 0 1 4 0v13a2 2 0 0 0 4 0v-4a2 2 0 0 1 2-2" />
    </svg>
  );
}
