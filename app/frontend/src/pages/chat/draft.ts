// Lo que la persona tiene escrito en el cuadro y no ha enviado, guardado en su propio
// navegador (2026-10-12).
//
// Quien copiaba algo en el chat y salia de la pagina lo perdia al volver. El borrador se
// guarda por aseguradora --cada chat es una conversacion distinta-- y vuelve al regresar;
// se borra al enviar y al empezar de cero.
//
// **Una sola clave para todas las aseguradoras**: un objeto `{ aseguradora: texto }`. El
// arnes de pantallas comprueba que el navegador solo guarde claves conocidas
// (`ALLOWED_STORAGE_KEYS`), y una clave por aseguradora no se podria listar de antemano.
//
// Cada acceso va en `try/catch`: en una ventana privada, con los datos de sitio
// bloqueados o con el almacenamiento lleno, el cuadro sigue funcionando y solo deja de
// recordar. No es un error y no se avisa.

const CLAVE = "cautelia.chat-drafts";

function leer(): Map<string, string> {
  try {
    const crudo = window.localStorage.getItem(CLAVE);
    const valor: unknown = crudo === null ? {} : JSON.parse(crudo);
    if (typeof valor !== "object" || valor === null || Array.isArray(valor)) {
      return new Map();
    }
    return new Map(
      Object.entries(valor).filter((par): par is [string, string] => typeof par[1] === "string"),
    );
  } catch {
    return new Map();
  }
}

/** Lo que quedo escrito sin enviar en el chat de esa aseguradora, o vacio. */
export function recallDraft(tenantId: string): string {
  return leer().get(tenantId) ?? "";
}

/** Guarda el borrador tal como esta. Un cuadro vacio borra la entrada. */
export function saveDraft(tenantId: string, text: string): void {
  try {
    const todos = leer();
    if (text === "") {
      // Con el borrador vacio no queda nada que recordar, ni la clave.
      todos.delete(tenantId);
    } else {
      todos.set(tenantId, text);
    }
    if (todos.size === 0) {
      window.localStorage.removeItem(CLAVE);
    } else {
      window.localStorage.setItem(CLAVE, JSON.stringify(Object.fromEntries(todos)));
    }
  } catch {
    // Sin almacenamiento el cuadro funciona igual, sin recordar.
  }
}

/** Olvida el borrador de esa aseguradora: se envio o la conversacion empezo de cero. */
export function clearDraft(tenantId: string): void {
  saveDraft(tenantId, "");
}
