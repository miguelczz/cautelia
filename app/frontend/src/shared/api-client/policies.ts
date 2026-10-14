// La pestana de polizas: la unica puerta de la interfaz a `GET /api/policies/{tenant_id}`.

import type { EndorsementView, PolicyCatalog, PolicyView } from "../api";
import type { Locale } from "../copy/copy-keys";
import {
  getPoliciesOptions,
  getPolicyDocumentOptions,
  getPolicyDocumentsOptions,
} from "../api/@tanstack/react-query.gen";

export type { EndorsementView, PolicyCatalog, PolicyView };

/** Las polizas de ejemplo de una aseguradora. */
export function policiesQueryOptions(tenantId: string) {
  return getPoliciesOptions({ path: { tenant_id: tenantId } });
}

export type { ClauseView, DocumentDetail, DocumentsCatalog, DocumentView } from "../api";

/** Los documentos del corpus de una aseguradora (panel de documentos). */
export function documentsQueryOptions(tenantId: string) {
  return getPolicyDocumentsOptions({ path: { tenant_id: tenantId } });
}

/** Las clausulas de un documento. */
export function documentQueryOptions(tenantId: string, formId: string, language: Locale) {
  return getPolicyDocumentOptions({
    path: { tenant_id: tenantId, form_id: formId },
    query: { language },
  });
}
