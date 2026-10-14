// La raiz de la aplicacion (`AppRoot`): los proveedores y la puerta de la espera.
//
// El orden de los proveedores es el de `frontend-components.md`: la cache de
// datos solo en memoria (BR3.5), el idioma, el modo, el anunciador unico (BR7.5)
// y, dentro, la espera del proceso, que dibuja el enrutador solo con el proceso
// listo.

import { QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { createQueryClient } from "../shared/api-client/query-client";
import { LocaleProvider } from "../shared/i18n/locale-provider";
import { ThemeProvider } from "../shared/theme/theme-provider";
import { AnnouncerProvider } from "../shared/ui/announcer";
import { ReadinessGate } from "./readiness-gate";

export function App() {
  const [cache] = useState(createQueryClient);
  return (
    <QueryClientProvider client={cache}>
      <LocaleProvider>
        <ThemeProvider>
          <AnnouncerProvider>
            <ReadinessGate />
          </AnnouncerProvider>
        </ThemeProvider>
      </LocaleProvider>
    </QueryClientProvider>
  );
}
