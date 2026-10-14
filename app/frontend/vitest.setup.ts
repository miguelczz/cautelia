// Lo que el documento de pruebas (`jsdom`) no trae y la interfaz usa.
//
// - `matchMedia`: el modo del dispositivo y el movimiento reducido. Por omision
//   responde que no a todo (claro, sin movimiento reducido); una prueba que
//   necesita otro valor lo reemplaza con `stubMatchMedia`.
// - `scrollIntoView`: `jsdom` no implementa el desplazamiento, y el chat lo usa
//   para dejar a la vista el ultimo mensaje. Un doble vacio basta: lo que hay
//   que comprobar del chat es lo que dice, no donde queda la barra.
// - Cada prueba empieza con el almacenamiento vacio y el documento sin modo ni
//   idioma: ninguna depende de lo que dejo otra (team.md, Forma de las pruebas).

import { afterEach, beforeAll, beforeEach } from "vitest";

import { loadLocale } from "./src/shared/i18n/catalog";
import { stubMatchMedia } from "./src/shared/theme/testing";

// Los dos idiomas cargados antes de cualquier prueba: en el navegador llegan antes
// de pintar y justo despues (`main.tsx`, 2026-10-09).
beforeAll(async () => {
  await Promise.all([loadLocale("es"), loadLocale("en")]);
});

beforeEach(() => {
  stubMatchMedia({});
  Element.prototype.scrollIntoView = () => {
    /* jsdom no desplaza nada */
  };
});

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  const raiz = document.documentElement;
  raiz.removeAttribute("data-theme");
  raiz.removeAttribute("data-theme-source");
  raiz.removeAttribute("data-theme-switching");
  raiz.removeAttribute("lang");
});
