// Las superficies que el inicio y la barra enlazan, **solo cuando el servidor las
// declara montadas** (BR4.1, FD-U6-1).
//
// Es la tabla unica entre una superficie y lo que la interfaz dibuja de ella: su
// nombre y a donde lleva. Las rutas de destino son de las unidades que montan
// cada superficie (U13 el chat, U16 la consola, U17 la comparacion, U22 los
// paneles): se declaran aqui una vez para que el inicio no las invente en varios
// sitios, y un boton solo existe cuando su superficie esta montada, asi que
// ninguno lleva a algo no construido. Cuando cada unidad registre su ruta en el
// enrutador y en el arnes (BR7.1), la comprobacion de completitud la vigila.

import type { SurfaceId } from "../shared/api-client/site";
import type { Message } from "../shared/i18n/translate";

/** Las superficies publicas de la barra superior, en su orden, con su nombre y su ruta. */
export const NAV_LINKS: readonly {
  readonly surface: SurfaceId;
  readonly label: Message;
  readonly href: string;
}[] = [
  // Un solo enlace para el gasto y los resultados (2026-10-09): se muestra con la
  // superficie de cifras, que no depende de la base de datos.
  { surface: "metrics_panel", label: (t) => t("surface.telemetry"), href: "/telemetry" },
];

/**
 * La pestana de casos: siempre en la barra, porque no depende de ninguna superficie ni
 * de ningun proveedor --muestra el caso propio y los casos de ejemplo-- (2026-10-11).
 * Reemplazo a "Polizas" en la barra.
 */
export const CASES_LINK: { readonly label: Message; readonly href: string } = {
  label: (t) => t("cases.nav"),
  href: "/cases",
};

/** La pagina de casos con los de ejemplo de una aseguradora ya elegidos (la vuelta desde un caso). */
export function casesHref(tenantId: string): string {
  return `${CASES_LINK.href}?tenant=${encodeURIComponent(tenantId)}`;
}

/** Un caso de ejemplo de una aseguradora, como lo ve un ajustador (solo lectura). */
export function exampleCaseHref(tenantId: string, caseId: string): string {
  return `${CASES_LINK.href}/${encodeURIComponent(tenantId)}/${encodeURIComponent(caseId)}`;
}

/**
 * La pagina de polizas. Ya no esta en la barra (2026-10-11): se llega desde el boton
 * "Ver polizas" de cada aseguradora en el inicio.
 */
export const POLICIES_HREF = "/policies";

/** Las polizas de una aseguradora: la pestana de polizas con su aseguradora ya elegida. */
export function policiesHref(tenantId: string): string {
  return `${POLICIES_HREF}?tenant=${encodeURIComponent(tenantId)}`;
}

/** El inicio, para elegir otra aseguradora desde el chat o la llamada (D7). */
export const INSURERS_LINK: { readonly label: Message; readonly href: string } = {
  label: (t) => t("policies.nav_insurers"),
  href: "/home",
};

/** La comparacion entre aseguradoras, que el inicio enlaza bajo las filas. */
export const COMPARISON_HREF = "/compare";

/** La guia "Como funciona", que el inicio enlaza bajo las filas. No depende de ninguna superficie. */
export const GUIDE_HREF = "/how-it-works";

/** Las superficies de cada aseguradora y la ruta de cada una. */
export function tenantSurfaceHref(surface: "chat" | "voice_console", tenantId: string): string {
  const aseguradora = encodeURIComponent(tenantId);
  return surface === "chat" ? `/t/${aseguradora}/chat` : `/t/${aseguradora}/call`;
}

/** Las superficies que abren un canal con la agente (BR4.3). */
export function mountedChannels(surfaces: readonly SurfaceId[]): {
  readonly chat: boolean;
  readonly voice: boolean;
} {
  return { chat: surfaces.includes("chat"), voice: surfaces.includes("voice_console") };
}
