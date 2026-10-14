// Las puertas de la pagina "Casos" hacia el servidor: los casos de ejemplo de una
// aseguradora y el caso propio del visitante en cada una (2026-10-11).
//
// Igual que `policies.ts` y `site.ts`: ninguna pantalla importa el cliente generado.
//
// **Solo dos fuentes, y ninguna lista casos de otros visitantes.** Los casos de ejemplo
// son los que escribe el generador sintetico (`GET /api/examples/...`, sin credencial
// y de solo lectura: el servidor responde lo mismo ante un caso de visitante que ante
// uno que no existe). El caso propio sale de la sesion de chat de este navegador, por
// la misma consulta que usa el chat para su linea del caso. Los casos de las llamadas
// no se listan aqui.

import { queryOptions } from "@tanstack/react-query";

import type { CaseDetailOut, ChatCaseStatus, ExampleCaseItem, ExampleCaseList } from "../api";
import { getExampleCaseOptions, listExampleCasesOptions } from "../api/@tanstack/react-query.gen";
import { caseStatus } from "./chat";

export type { CaseDetailOut, ChatCaseStatus, ExampleCaseItem, ExampleCaseList };

/** Los casos de ejemplo de una aseguradora, ya por estado y por numero (orden del servidor). */
export function exampleCasesQueryOptions(tenantId: string) {
  return listExampleCasesOptions({ path: { tenant_id: tenantId } });
}

/** Un caso de ejemplo con sus seis bloques y sin ninguna accion posible. */
export function exampleCaseQueryOptions(tenantId: string, caseId: string) {
  return getExampleCaseOptions({ path: { tenant_id: tenantId, case_id: caseId } });
}

/**
 * El caso de este navegador en una aseguradora, o `null` si no hay: sin conversacion,
 * sin caso todavia o no se pudo leer. La pantalla no distingue las causas porque el
 * servidor tampoco (`caseStatus`).
 */
export function ownCaseQueryOptions(tenantId: string) {
  return queryOptions({
    queryKey: ["own-case", tenantId],
    queryFn: () => caseStatus(tenantId),
  });
}
