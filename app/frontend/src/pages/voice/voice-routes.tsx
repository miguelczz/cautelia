// La consola dentro del enrutador: `/t/$tenantId/call`.
//
// Misma forma que la del chat: la ruta resuelve lo que la pantalla no debe saber
// buscar --el nombre de la aseguradora, que sale del directorio del sitio-- y la
// pantalla recibe lo que necesita sin consultar nada por su cuenta.

import { useQuery } from "@tanstack/react-query";
import { getRouteApi } from "@tanstack/react-router";

import { policiesQueryOptions } from "../../shared/api-client/policies";
import { siteQueryOptions } from "../../shared/api-client/site";
import { TenantScope } from "../../shared/ui/tenant-scope";
import { VoicePage } from "./voice-page";

const rutaDeLaLlamada = getRouteApi("/t/$tenantId/call");

export function VoiceRoutePage() {
  const { tenantId } = rutaDeLaLlamada.useParams();
  const consulta = useQuery(siteQueryOptions());
  // Mientras el directorio no ha llegado, el identificador: es lo que la
  // direccion ya dice, y es preferible a un hueco o a un nombre inventado.
  const entrada = consulta.data?.tenants.find((tenant) => tenant.tenant_id === tenantId);
  const aseguradora = entrada?.display_name ?? tenantId;
  // El titular de la poliza de ejemplo, para decirlo junto al numero. Si la lista no llega,
  // la ayuda da solo el numero: no se inventa un nombre.
  const polizas = useQuery(policiesQueryOptions(tenantId));
  const titular = polizas.data?.policies.find(
    (poliza) => poliza.policy_number === entrada?.example_policy,
  )?.holder_name;

  // El acento de la aseguradora reemplaza al cobre dentro de la llamada (decision de
  // Miguel, 2026-10-07).
  return (
    <TenantScope brand={entrada?.brand}>
      <VoicePage
        tenantId={tenantId}
        insurerLabel={aseguradora}
        examplePolicy={entrada?.example_policy}
        exampleHolder={titular}
        chatHref={`/t/${encodeURIComponent(tenantId)}/chat`}
      />
    </TenantScope>
  );
}
