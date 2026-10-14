// Una direccion que se puede abrir en otra pestana.
//
// Vive aqui y no en una pantalla porque la usan dos: la bandeja (el bloque de la
// respuesta) y el tablero de gasto, y las dos tienen que decidir lo mismo.

/**
 * Una direccion que se puede abrir en otra pestana: solo `https`. La manda el servidor, que ya
 * valida el host al arrancar; aqui se comprueba otra vez porque es lo ultimo antes de un
 * `href`, y un esquema distinto (`javascript:`) no tiene que llegar a pintarse nunca.
 */
export function isSafeExternalLink(direccion: string | null | undefined): direccion is string {
  return typeof direccion === "string" && /^https:\/\/[^\s]+$/.test(direccion);
}
