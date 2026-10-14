// La pagina que muestra una ruta de caso cuando el servidor no la sirve (F6,
// BR5.6, SEC-U6.6).
//
// Un enlace manipulado (`link_invalid`) y un caso que no existe (`not_found`)
// muestran **exactamente la misma pagina**: si fueran distintas, quien prueba
// enlaces podria adivinar que casos existen. La vista por enlace (U14) llama a
// esta funcion con el error que recibio y dibuja la pagina que devuelve.

import type { ProblemView } from "../../shared/api-client/problems";
import type { StatusPageKind } from "./status-kinds";

export function statusKindForCaseProblem(problem: ProblemView): StatusPageKind {
  if (problem.code === "link_invalid" || problem.code === "not_found") {
    return "link_invalid";
  }
  return "service_unavailable";
}
