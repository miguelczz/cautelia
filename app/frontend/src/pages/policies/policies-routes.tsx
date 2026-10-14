// La pestana de polizas dentro del enrutador: `/policies`.
//
// El parametro `tenant` elige la aseguradora que se abre: lo usa el boton "Ver
// polizas" de cada fila del inicio. Sin el --o con una aseguradora que no existe--
// abre en la primera. La pantalla recibe el identificador y no lee la direccion.

import { getRouteApi } from "@tanstack/react-router";

import { PoliciesPage } from "./policies-page";

const rutaDePolizas = getRouteApi("/policies");

export function PoliciesRoutePage() {
  const { tenant } = rutaDePolizas.useSearch();
  return <PoliciesPage initialTenantId={tenant} />;
}
