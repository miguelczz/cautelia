// La pagina de casos dentro del enrutador.
//
//   /cases                      el caso propio y los casos de ejemplo
//   /cases/$tenantId/$caseId    un caso de ejemplo, solo lectura
//
// El parametro `tenant` de la primera elige la aseguradora cuyos casos de ejemplo se
// ven al abrir: lo usa el enlace de vuelta desde un caso. Sin el --o con una que no
// existe-- abre en la primera. Las pantallas reciben los identificadores y no leen la
// direccion.

import { getRouteApi } from "@tanstack/react-router";

import { CasesPage } from "./cases-page";
import { ExampleCasePage } from "./example-case-page";

const rutaDeCasos = getRouteApi("/cases");
const rutaDelEjemplo = getRouteApi("/cases/$tenantId/$caseId");

export function CasesRoutePage() {
  const { tenant } = rutaDeCasos.useSearch();
  return <CasesPage initialTenantId={tenant} />;
}

export function ExampleCaseRoutePage() {
  const { tenantId, caseId } = rutaDelEjemplo.useParams();
  return <ExampleCasePage tenantId={tenantId} caseId={caseId} />;
}
