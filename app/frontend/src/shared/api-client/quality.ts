// La ruta del tablero "Que tan bien funciona", por el cliente generado (2026-10-11).
//
// Publica y sin credencial: son resultados del conjunto de prueba versionado, no
// casos de visitantes.

import type {
  DatasetResult,
  FailedCase,
  GateFamily,
  GateResult,
  NotMeasuredGroup,
  QualityBoard,
  Tally,
  TallyByLanguage,
} from "../api";
import { getQualityBoardOptions } from "../api/@tanstack/react-query.gen";

export type {
  DatasetResult,
  FailedCase,
  GateFamily,
  GateResult,
  NotMeasuredGroup,
  QualityBoard,
  Tally,
  TallyByLanguage,
};

/** La consulta de `GET /api/quality`: la ultima corrida completa, o nada. */
export function qualityQueryOptions() {
  return getQualityBoardOptions();
}
