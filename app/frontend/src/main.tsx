// La entrada de la aplicacion. Monta la raiz y nada mas: el marco, los
// proveedores de modo e idioma y el enrutador viven en `app/`.

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App";
import "./app/styles.css";
import { loadLocale } from "./shared/i18n/catalog";
import { browserLanguages, initialLanguageChoice } from "./shared/i18n/initial-locale";

const contenedor = document.getElementById("root");
if (contenedor === null) {
  // Error de quien construye, no de quien visita: sin el contenedor no hay
  // donde montar, y fallar en silencio dejaria una pagina en blanco sin causa.
  throw new Error("index.html is missing the #root container");
}

// Las frases del idioma del arranque llegan antes de pintar, y las del otro justo
// despues: separadas, el catalogo cabe en el presupuesto de la espera (2026-10-09).
const raiz = createRoot(contenedor);
const inicial = initialLanguageChoice(browserLanguages()).locale;
void loadLocale(inicial).then(() => {
  raiz.render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
  // El otro idioma, cuando el navegador quede libre tras el primer pintado: antes
  // contaba dentro de la espera y la pasaba (2026-10-09).
  const otro = inicial === "es" ? "en" : "es";
  const cargarElOtro = () => void loadLocale(otro);
  if ("requestIdleCallback" in window) {
    window.requestIdleCallback(cargarElOtro, { timeout: 3000 });
  } else {
    setTimeout(cargarElOtro, 1500);
  }
});
