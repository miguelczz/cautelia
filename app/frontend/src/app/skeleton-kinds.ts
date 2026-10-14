// Que esqueleto le toca a cada direccion (plan-estilos-2026-10.md, seccion 4).
//
// La espera del proceso se dibuja **antes** del enrutador: todavia no sabe que
// pantalla va a venir, pero si cual pidio la persona. Con la direccion alcanza para
// dibujar el esqueleto de esa pantalla, de modo que el paso de la espera a la
// pantalla real es el mismo dibujo llenandose, no una pagina que se cambia por otra.
//
// Es una funcion pura sobre la direccion y no una consulta al enrutador, que aun no
// existe en ese momento. La prueba `skeleton-kinds.test.ts` recorre el registro de
// pantallas visitables y falla si una ruta con pantalla propia cae en el esqueleto
// generico.

import type { SkeletonKind } from "../shared/ui/page-skeletons";

/** La familia de esqueleto de una direccion (solo su ruta, sin busqueda ni fragmento). */
export function skeletonKindForPath(pathname: string): SkeletonKind {
  const ruta = pathname.split(/[?#]/, 1)[0] ?? "";
  const partes = ruta.split("/").filter((parte) => parte !== "");

  if (partes.length === 0) {
    // La raiz redirige al inicio.
    return "home";
  }
  const [primera, , tercera, cuarta] = partes;

  switch (primera) {
    case "home":
      return "home";
    case "how-it-works":
      return "guide";
    case "policies":
      return "policies";
    case "metrics":
    case "spend":
    case "telemetry":
      return "panel";
    case "cases":
      // La lista de casos (/cases) y un caso de ejemplo (/cases/<aseguradora>/<caso>).
      return partes.length === 1 ? "cases" : "case";
    case "compare":
      return "compare";
    case "c":
      // El canje del enlace (/c) y el caso del visitante (/c/<aseguradora>/<caso>).
      return "case";
    case "t":
      switch (tercera) {
        case "chat":
          return "chat";
        case "call":
          return "call";
        case "inbox":
          return cuarta === undefined ? "inbox" : "case";
        default:
          return "generic";
      }
    default:
      return "generic";
  }
}

/** Como se asienta el marco para esa familia: la misma que ya tendra la pantalla real. */
export function frameModeForKind(kind: SkeletonKind): {
  readonly fill: boolean;
  readonly onePage: boolean;
} {
  return {
    fill: kind === "chat",
    onePage: kind === "home" || kind === "guide" || kind === "policies",
  };
}
