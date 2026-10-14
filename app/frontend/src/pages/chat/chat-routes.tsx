// El chat dentro del enrutador: `/t/$tenantId/chat`.
//
// La ruta resuelve lo que la pantalla no debe saber buscar: el nombre de la
// aseguradora, que sale del directorio del sitio, y como enlazar al resumen de
// una traza. La pantalla recibe las dos cosas y no consulta nada por su cuenta.

import { getRouteApi } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";

import { siteQueryOptions } from "../../shared/api-client/site";
import { TenantScope } from "../../shared/ui/tenant-scope";
import { ChatPage } from "./chat-page";

const rutaDelChat = getRouteApi("/t/$tenantId/chat");

export function ChatRoutePage() {
  const { tenantId } = rutaDelChat.useParams();
  const { ask } = rutaDelChat.useSearch();
  const navegar = rutaDelChat.useNavigate();
  const consulta = useQuery(siteQueryOptions());
  // Mientras el directorio no ha llegado, el identificador: es lo que la
  // direccion ya dice, y es preferible a un hueco o a un nombre inventado.
  const presentacion = consulta.data?.tenants.find((tenant) => tenant.tenant_id === tenantId);
  const aseguradora = presentacion?.display_name ?? tenantId;

  // El acento de la aseguradora reemplaza al cobre dentro de la conversacion: asi se ve
  // de un vistazo en cual esta la persona (decision de Miguel, 2026-10-07).
  return (
    <TenantScope brand={presentacion?.brand}>
      <ChatPage
        tenantId={tenantId}
        insurerLabel={aseguradora}
        traceHref={(traceRef) =>
          `/t/${encodeURIComponent(tenantId)}/trace/${encodeURIComponent(traceRef)}`
        }
        initialMessage={ask}
        onInitialMessageSent={() => {
          // Fuera de la direccion: recargar la pagina no vuelve a enviarlo.
          void navegar({ search: {}, replace: true });
        }}
      />
    </TenantScope>
  );
}
