// El atributo `elementtiming` de la API de Element Timing, que React pasa tal
// cual al DOM. El arnes lo usa para medir cuando se pinto el titulo de la pagina
// de espera y las filas del inicio (NFR16.3, PERF-U6.2), con el tiempo del propio
// navegador y no con el de una espera de Playwright.
import "react";

declare module "react" {
  // La fusion de interfaces exige el mismo parametro de tipo que la declaracion
  // de React, aunque este agregado no lo use.
  // eslint-disable-next-line @typescript-eslint/no-unused-vars -- la fusion con la declaracion de React exige el parametro
  interface HTMLAttributes<T> {
    elementtiming?: string;
  }
}
