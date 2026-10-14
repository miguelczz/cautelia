// El proxy que pone el aplicativo bajo cautelia.app (decision de Miguel,
// 2026-10-06, afinada esa misma tarde: la landing en la raiz y el inicio del
// aplicativo en /home).
//
// Cloudflare Pages sirve la landing como archivos estaticos --la raiz, su
// imagen social y la licencia, que _routes.json excluye-- y todo lo demas pasa
// por aqui hacia Cloud Run, con el metodo, las cabeceras y el cuerpo intactos. Las dos cosas que importan y que esto respeta:
//
// - Los flujos no se cortan: la respuesta se devuelve tal cual llega, asi que
//   el flujo de eventos del chat y la mejora a WebSocket de la voz pasan enteros
//   (fetch devuelve el 101 con su socket y se reenvia sin tocar).
// - El visitante sigue siendo el visitante: Cloudflare agrega CF-Connecting-IP
//   y X-Forwarded-For con su direccion real, y la cabecera Origin del navegador
//   viaja sin cambios.
//
// Lo que si cambia, y Miguel lo acepto al elegir esta disposicion: quien pasa
// de la landing al aplicativo espera a que la instancia despierte si estaba
// dormida. La landing, en la raiz, sigue siendo estatica y no depende de que el
// aplicativo este vivo.

const ORIGEN = "https://cautelia-930269717946.us-east1.run.app";

export async function onRequest({ request }) {
  const url = new URL(request.url);
  const destino = new URL(url.pathname + url.search, ORIGEN);
  const peticion = new Request(destino.toString(), request);
  return fetch(peticion);
}
