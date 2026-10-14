// La cache de datos del servidor: **solo en memoria** (BR3.5).
//
// Nada de lo que llega del servidor se escribe en el almacenamiento del
// navegador: no se instala ninguna capa persistente de TanStack Query, y la cache
// se vacia al cerrar la pestana. Los datos de un caso no pueden quedar en el
// equipo para quien lo use despues (SEC-U6.5).

import { QueryCache, QueryClient } from "@tanstack/react-query";

import { reportConnectivityLost } from "./connectivity";
import { isConnectivityFailure } from "./problems";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (error) => {
        // Una red caida devuelve la espera a "comprobando"; un error del
        // servidor lo muestra la pantalla que lo pidio (F5).
        if (isConnectivityFailure(error)) {
          reportConnectivityLost();
        }
      },
    }),
    defaultOptions: {
      queries: {
        // El reintento lo decide la persona con "Reintentar" (M1, F5): un
        // reintento automatico escondido tras un esqueleto alarga la espera sin
        // decir por que.
        retry: false,
        refetchOnWindowFocus: false,
        staleTime: 30_000,
      },
    },
  });
}
