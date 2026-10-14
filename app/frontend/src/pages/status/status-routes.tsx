// Las paginas de estado dentro del enrutador: `/status/$kind` y "no encontrada"
// para cualquier otra ruta (BR5.5, F1 paso 5).
//
// `/status/$kind` solo admite los cinco tipos a los que se llega navegando; un
// tipo desconocido --o "despertando" y "no disponible", que son estados de la
// espera y no direcciones-- es "no encontrada".

import { getRouteApi, Link, useRouter } from "@tanstack/react-router";

import { Button } from "../../shared/ui/button";
import { StatusPage } from "./status-page";
import { parseRoutedStatusKind } from "./status-kinds";

const rutaDeEstado = getRouteApi("/status/$kind");

function enlaceDelEnrutador(label: string) {
  return (
    <Button asChild variant="primary">
      <Link to="/home">{label}</Link>
    </Button>
  );
}

export function StatusRoutePage() {
  const { kind } = rutaDeEstado.useParams();
  const router = useRouter();
  const tipo = parseRoutedStatusKind(kind) ?? "not_found";

  // "Volver a la conversacion" y "Reintentar" vuelven a la pagina anterior si la
  // hay; si se llego directo, al inicio.
  const volver = () => {
    if (window.history.length > 1) {
      router.history.back();
    } else {
      void router.navigate({ to: "/home" });
    }
  };

  return <StatusPage kind={tipo} homeLink={enlaceDelEnrutador} onBack={volver} onRetry={volver} />;
}

export function NotFoundPage() {
  return <StatusPage kind="not_found" homeLink={enlaceDelEnrutador} />;
}
