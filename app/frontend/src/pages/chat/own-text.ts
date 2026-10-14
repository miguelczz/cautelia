// El texto propio vive ahora en `shared/own-text` (2026-10-12), porque lo leen tambien
// "Ver mi caso", el pensamiento de la agente y la consola de la llamada. Este archivo
// solo deja el nombre de siempre para el chat.

export {
  forget,
  isMasked,
  recall,
  recallAgent,
  remember,
  rememberAgent,
  restore,
} from "../../shared/own-text/own-text";
