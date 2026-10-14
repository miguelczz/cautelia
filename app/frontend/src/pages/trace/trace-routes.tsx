// El resumen de traza dentro del enrutador: `/t/$tenantId/trace/$traceId`.

import { getRouteApi } from "@tanstack/react-router";

import { TracePage } from "./trace-page";

const rutaDeTraza = getRouteApi("/t/$tenantId/trace/$traceId");

export function TraceRoutePage() {
  const { tenantId, traceId } = rutaDeTraza.useParams();
  return <TracePage tenantId={tenantId} traceId={traceId} />;
}
