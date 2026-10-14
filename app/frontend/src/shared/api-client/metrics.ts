// La ruta del panel de cifras, por el cliente generado (U22, BR3.1).

import type {
  Figure,
  FigureKey,
  FigureSource,
  LatencyEvent,
  LatencyMeasure,
  LatencyReading,
  Measurement,
  MetricsSnapshot,
  NotMeasuredCause,
} from "../api";
import { getMetricsOptions } from "../api/@tanstack/react-query.gen";

export type {
  Figure,
  FigureKey,
  FigureSource,
  LatencyEvent,
  LatencyMeasure,
  LatencyReading,
  Measurement,
  MetricsSnapshot,
  NotMeasuredCause,
};

/** La consulta de `GET /api/metrics`: sin credencial y de solo lectura. */
export function metricsQueryOptions() {
  return getMetricsOptions();
}
