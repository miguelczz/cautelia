// Las dos rutas que usa la base de la interfaz, por el cliente generado (BR3.1).
//
// Este modulo es la unica puerta de la interfaz hacia `src/shared/api/`: la
// regla de fronteras del linter no deja que ninguna pantalla importe el cliente
// generado directamente, asi que toda llamada pasa por aqui y por la tabla de
// errores.

import {
  getHealthReady,
  type Monogram,
  type SiteDirectory,
  type SiteLinks,
  type SurfaceId,
  type TenantPresentation,
} from "../api";
import { getSiteOptions } from "../api/@tanstack/react-query.gen";

export type { Monogram, SiteDirectory, SiteLinks, SurfaceId, TenantPresentation };

/** La consulta del directorio del sitio (F2). */
export function siteQueryOptions() {
  return getSiteOptions();
}

/** Lo que dijo una comprobacion de "listo". */
export type ReadyOutcome = "ready" | "not_ready";

/**
 * Una consulta de `GET /api/health/ready`. `not_ready` cubre las dos cosas que
 * la espera trata igual: un 503 y una falta de respuesta (red, o se agoto el
 * tiempo de `signal`).
 */
export async function checkReady(signal: AbortSignal): Promise<ReadyOutcome> {
  const { error, response } = await getHealthReady({ signal });
  if (error === undefined && response?.ok === true) {
    return "ready";
  }
  return "not_ready";
}
