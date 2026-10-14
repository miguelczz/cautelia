// El nombre de la agente de una aseguradora. Cada aseguradora tiene la suya (decision
// de Miguel, 2026-10-11) y el nombre viaja en el directorio del sitio, igual que el
// nombre visible de la aseguradora: ninguna pantalla lo escribe.
//
// Mientras el directorio no llega, o si la aseguradora no esta en el, sale el nombre
// por omision del catalogo: una pantalla nunca queda con un hueco donde va el nombre.

import { useQuery } from "@tanstack/react-query";

import { siteQueryOptions } from "../api-client/site";
import { useLocale } from "../i18n/locale-provider";

export function useAgentName(tenantId: string | undefined): string {
  const { t } = useLocale();
  const { data } = useQuery(siteQueryOptions());
  const propia = data?.tenants.find((tenant) => tenant.tenant_id === tenantId);
  return propia?.agent_name ?? t("insurer.agent.name");
}
