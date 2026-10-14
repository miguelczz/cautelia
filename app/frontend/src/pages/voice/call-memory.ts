// Lo que se dijo en la llamada, guardado en este navegador (C5, 2026-10-12).
//
// La base guarda cada turno con los datos personales tapados, y quien abre despues "Ver
// mi caso" veia "Soy [NOMBRE 1], mi poliza es [POLIZA 1]". La consola, en cambio, recibe
// lo que la persona dijo tal como lo dijo (`loop.py`, `_mostrar`, decision del
// 2026-10-09), asi que la copia se hace aqui, con el mismo mecanismo que el chat
// (`shared/own-text`), y la pantalla del caso la pone de vuelta en su turno. Desde el
// 2026-10-13 lo mismo vale para la agente: la consola recibe lo que dijo sin tapar
// (`CallEngine.on_screen`), y la base lo guarda tapado.
//
// **Cada linea de la agente es, entera, lo que guarda la base.** La respuesta de cobertura
// que llega del fondo se manda en dos lineas --la respuesta y "volviendo al reporte" con su
// pregunta-- por eso: pegadas, la copia no encajaria con el turno de la base y el caso
// mostraria la etiqueta.
//
// **Un turno de la base es todo lo que la persona dijo antes de que la agente contestara**
// (el servidor junta los finales con un espacio), mientras la consola muestra cada final
// por separado. Por eso se guarda cada final y, cuando son varios seguidos, tambien el
// turno entero: una copia solo reemplaza un texto tapado si encaja con su forma, asi que
// guardar de mas nunca pone un texto donde no va.

import { remember, rememberAgent } from "../../shared/own-text/own-text";
import type { WireFrame } from "./voice-events";

/** Quien recibe los cuadros de una llamada y anota lo que se dijo. */
export type CallMemory = (frame: WireFrame) => void;

export function callMemory(tenantId: string): CallMemory {
  // Lo que la persona lleva dicho desde la ultima vez que hablo la agente.
  let seguidos: string[] = [];
  return (frame) => {
    if (frame.type !== "transcript" || !frame.final || frame.text.trim() === "") {
      return;
    }
    if (frame.speaker === "agent") {
      rememberAgent(tenantId, frame.text);
      seguidos = [];
      return;
    }
    remember(tenantId, frame.text);
    seguidos = [...seguidos, frame.text];
    if (seguidos.length > 1) {
      remember(tenantId, seguidos.join(" "));
    }
  };
}
