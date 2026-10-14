// Las cuatro pantallas de la bandeja dentro del enrutador.
//
//   /t/$tenantId/inbox              la cola, con sus filtros en la busqueda
//   /t/$tenantId/inbox/$caseId      la vista de caso con credencial
//   /c                              el canje del enlace, con el token en el fragmento
//   /c/$tenantId/$caseId            el caso del visitante, ya con su cookie
//
// **Los filtros viven en la direccion** (BR1.3 y su razon): una cola filtrada que se
// pierde al recargar obliga a volver a filtrar en cada vuelta y no se puede compartir
// con nadie. Se leen y se escriben aqui, en la ruta, y la pantalla solo los recibe.
//
// **El canje limpia la direccion** (BR5.6). El token llega en el fragmento --que el
// navegador nunca manda al servidor ni en `Referer`-- y en cuanto se canjea la ruta
// se reemplaza por `/c/<aseguradora>/<caso>`, sin token. Se usa `replace` y no una
// navegacion normal a proposito: con historial, el boton de atras volveria a la
// direccion con el token dentro.

import { getRouteApi, Link, useRouter } from "@tanstack/react-router";
import { useCallback } from "react";
import { useQuery } from "@tanstack/react-query";

import type { QueueFilters } from "../../shared/api-client/inbox";
import type { ProblemView } from "../../shared/api-client/problems";
import { siteQueryOptions } from "../../shared/api-client/site";
import { Button } from "../../shared/ui/button";
import { statusKindForCaseProblem } from "../status/case-link-status";
import { StatusPage } from "../status/status-page";
import { CaseDetailPage } from "./case-page";
import { CasesQueuePage } from "./queue-page";
import { VisitorCasePage, type CaseSession } from "./visitor-page";

const rutaDeLaCola = getRouteApi("/t/$tenantId/inbox");
const rutaDelCaso = getRouteApi("/t/$tenantId/inbox/$caseId");
const rutaDelVisitante = getRouteApi("/c/$tenantId/$caseId");

/** Los cuatro filtros que la direccion admite. Nada mas entra. */
type Busqueda = Readonly<Record<string, unknown>>;

function filtrosDe(busqueda: Busqueda): QueueFilters {
  // Se construye anadiendo solo lo que hay, no poniendo `undefined`: el proyecto
  // trata una propiedad ausente y una puesta en `undefined` como cosas distintas
  // (`exactOptionalPropertyTypes`), y esa distincion es la que hace que un filtro
  // sin valor no viaje en la consulta.
  const leer = (clave: string): string | undefined => {
    const valor: unknown = Object.entries(busqueda).find(([k]) => k === clave)?.[1];
    return typeof valor === "string" && valor !== "" ? valor : undefined;
  };
  return Object.fromEntries(
    (["state", "channel", "language", "priority"] as const)
      .map((clave) => [clave, leer(clave)] as const)
      .filter(([, valor]) => valor !== undefined),
  );
}

/** El nombre de una aseguradora, del directorio del sitio; su identificador si no llego. */
function useInsurerLabel(tenantId: string): string {
  const consulta = useQuery(siteQueryOptions());
  // Mientras el directorio no ha llegado, el identificador: es lo que la direccion ya
  // dice, y es preferible a un hueco o a un nombre inventado. Es la misma decision
  // que tomo la ruta del chat.
  return (
    consulta.data?.tenants.find((tenant) => tenant.tenant_id === tenantId)?.display_name ?? tenantId
  );
}

export function InboxQueueRoutePage() {
  const { tenantId } = rutaDeLaCola.useParams();
  const busqueda: Busqueda = rutaDeLaCola.useSearch();
  const router = useRouter();
  const nombre = useInsurerLabel(tenantId);

  return (
    <CasesQueuePage
      tenantId={tenantId}
      insurerLabel={nombre}
      filters={filtrosDe(busqueda)}
      onFiltersChange={(filtros) => {
        void router.navigate({
          to: "/t/$tenantId/inbox",
          params: { tenantId },
          search: filtros,
          replace: true,
        });
      }}
      caseHref={(caseId) =>
        `/t/${encodeURIComponent(tenantId)}/inbox/${encodeURIComponent(caseId)}`
      }
    />
  );
}

export function InboxCaseRoutePage() {
  const { tenantId, caseId } = rutaDelCaso.useParams();
  return (
    <CaseDetailPage
      tenantId={tenantId}
      caseId={caseId}
      queueHref={`/t/${encodeURIComponent(tenantId)}/inbox`}
    />
  );
}

/** La pagina que se dibuja cuando el enlace no vale, la misma para las cuatro causas. */
function rechazo(problem: ProblemView) {
  const tipo = statusKindForCaseProblem(problem);
  return (
    <StatusPage
      kind={tipo}
      homeLink={(label) => (
        <Button asChild variant="primary">
          <Link to="/home">{label}</Link>
        </Button>
      )}
    />
  );
}

/**
 * El canje: `/c` con el token en el fragmento.
 *
 * El fragmento se lee de `window.location.hash` y no de la busqueda de la ruta,
 * porque **el enrutador no ve el fragmento** y eso es justo lo que se queria: lo que
 * el enrutador no ve tampoco viaja al servidor.
 */
export function CaseLinkRedeemRoutePage() {
  const router = useRouter();
  const token = window.location.hash.replace(/^#/, "");

  const limpiar = useCallback(
    (sesion: CaseSession) => {
      // El fragmento se borra a mano: `navigate` no lo toca, y dejarlo ahi mantendria
      // el token en la barra aunque la ruta ya fuera otra (BR5.6).
      window.history.replaceState(null, "", window.location.pathname);
      void router.navigate({
        to: "/c/$tenantId/$caseId",
        params: { tenantId: sesion.tenantId, caseId: sesion.caseId },
        replace: true,
      });
    },
    [router],
  );

  return (
    <VisitorCasePage
      token={token}
      onRedeemed={limpiar}
      conversationHref={(sesion) => `/t/${encodeURIComponent(sesion.tenantId)}/chat`}
      renderRejected={rechazo}
    />
  );
}

/** El caso del visitante con la direccion ya limpia: entra con su cookie. */
export function VisitorCaseRoutePage() {
  const { tenantId, caseId } = rutaDelVisitante.useParams();
  return (
    <VisitorCasePage
      tenantId={tenantId}
      caseId={caseId}
      conversationHref={(sesion) => `/t/${encodeURIComponent(sesion.tenantId)}/chat`}
      renderRejected={rechazo}
    />
  );
}
