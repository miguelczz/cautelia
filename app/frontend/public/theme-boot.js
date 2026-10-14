/*
 * El paso que aplica el modo claro u oscuro antes del primer pintado (BR1.2).
 *
 * Es un archivo propio, pequeno y bloqueante en la cabecera, y no un script en
 * linea (CG-U6-1): asi la politica de contenido se queda en `script-src 'self'`
 * sin excepciones ni huellas que regenerar. Corre antes que la hoja de estilos y
 * que la aplicacion, y por eso la pagina nunca pinta el modo contrario.
 *
 * Lo que decide (BR1.1, enmendada el 2026-10-06 por decision de Miguel):
 *   - con una eleccion guardada valida (`light` o `dark`), esa;
 *   - sin eleccion, con una ilegible o con el almacenamiento bloqueado, **oscuro**,
 *     que es el modo de la landing: quien llega desde ella no cambia de mundo.
 *     La preferencia del dispositivo ya no decide; el modo claro sigue a un clic
 *     en el selector. Un valor ilegible deja constancia en la consola, nunca un
 *     mensaje para la persona.
 *
 * Deja el resultado en dos atributos del documento, que es donde lo lee el
 * proveedor de modo de la aplicacion: `data-theme` (el modo) y
 * `data-theme-source` (`user` o `default`). La misma decision, escrita en
 * TypeScript, vive en `src/shared/theme/preference.ts`; una prueba corre las dos
 * con los mismos escenarios y exige el mismo resultado.
 *
 * La clave de almacenamiento es la unica que la interfaz escribe por su cuenta
 * (BR3.5, SEC-U6.5).
 */
(function () {
  "use strict";

  var CLAVE = "untangle.theme";
  var raiz = document.documentElement;
  var guardado = null;

  try {
    guardado = window.localStorage.getItem(CLAVE);
  } catch (error) {
    console.info("untangle: the stored theme preference cannot be read; using the default", error);
  }

  var elegido = guardado === "light" || guardado === "dark" ? guardado : null;
  if (guardado !== null && elegido === null) {
    console.info("untangle: the stored theme preference is not light or dark; using the default");
  }

  raiz.setAttribute("data-theme", elegido !== null ? elegido : "dark");
  raiz.setAttribute("data-theme-source", elegido !== null ? "user" : "default");
})();
