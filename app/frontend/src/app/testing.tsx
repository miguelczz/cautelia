// Solo para pruebas: la raiz de la aplicacion sin la espera del proceso, para
// dibujar una pieza con los mismos proveedores que tiene en la pagina (cache en
// memoria, idioma, modo y anunciador). Ninguna pantalla lo importa.

import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { render, type RenderResult } from "@testing-library/react";
import type { ReactNode } from "react";

import { createQueryClient } from "../shared/api-client/query-client";
import type { Locale } from "../shared/copy/copy-keys";
import { LocaleProvider } from "../shared/i18n/locale-provider";
import { ThemeProvider } from "../shared/theme/theme-provider";
import { AnnouncerProvider } from "../shared/ui/announcer";
import { createAppRouter } from "./router";

export function Providers({
  locale,
  children,
}: {
  readonly locale: Locale;
  readonly children: ReactNode;
}) {
  return (
    <QueryClientProvider client={createQueryClient()}>
      <LocaleProvider initial={{ locale, source: "device" }}>
        <ThemeProvider>
          <AnnouncerProvider>{children}</AnnouncerProvider>
        </ThemeProvider>
      </LocaleProvider>
    </QueryClientProvider>
  );
}

export function renderWithProviders(ui: ReactNode, locale: Locale = "es"): RenderResult {
  return render(<Providers locale={locale}>{ui}</Providers>);
}

/** El enrutador de la aplicacion en una ruta, con los proveedores. */
export function renderRoute(path: string, locale: Locale = "es") {
  const router = createAppRouter(createMemoryHistory({ initialEntries: [path] }));
  const resultado = renderWithProviders(<RouterProvider router={router} />, locale);
  return { router, ...resultado };
}
