// La parte de la aplicacion que se dibuja con el proceso listo: el enrutador y
// sus pantallas.
//
// Es un trozo aparte que se carga **despues** de la pagina de espera: lo que el
// navegador descarga antes de pintar "la demo esta despertando" es solo el marco,
// los proveedores y esa pagina (PERF-U6.1, NFR16.3). Mientras la demo despierta,
// este trozo se trae en segundo plano, y al estar lista se dibuja sin esperar.

import { RouterProvider } from "@tanstack/react-router";
import { useState } from "react";

import { createAppRouter } from "./router";

export default function RoutedApp() {
  const [router] = useState(() => createAppRouter());
  return <RouterProvider router={router} />;
}
