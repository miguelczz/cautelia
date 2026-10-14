// La ruta de la telemetria dentro del enrutador (`/telemetry`, 2026-10-09).

import { useSearch } from "@tanstack/react-router";

import { TelemetryPage } from "./telemetry-page";

export function TelemetryRoutePage() {
  const { view } = useSearch({ from: "/telemetry" });
  return <TelemetryPage view={view === "quality" ? "quality" : "cost"} />;
}
