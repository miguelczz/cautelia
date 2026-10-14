import { expect, test } from "@playwright/test";

import {
  expectNoCspViolations,
  expectNoHorizontalScroll,
  expectScreenDrawn,
  openScreen,
  prepare,
  unexpectedConsoleErrors,
} from "./support/harness";
import { VISITABLE_ROUTES } from "./visitable-routes";

// La prueba de dibujo de cada pantalla registrada, en los tres motores (Q1 de
// NFR Requirements): carga sin errores de consola, sin desplazamiento horizontal
// y con el titulo visible --o, en la espera del proceso, el esqueleto--. Firefox y
// WebKit corren solo esta; Chromium, todo.

// **Cada pantalla se dibuja una vez por motor, no dos** (2026-10-11). En Chromium la
// prueba de accesibilidad ya abre cada pantalla y comprueba esto mismo --titulo,
// desplazamiento horizontal, politica de contenido y consola--, asi que aqui Chromium
// solo corre las direcciones que esa prueba no abre: las que redirigen. Y una
// redireccion la resuelve el aplicativo, no el motor: Firefox y WebKit no la repiten.
// No se quita ninguna comprobacion; se deja de hacer dos veces. El arnes habia pasado
// su presupuesto de tiempo al sumar las dos pantallas de Casos.
for (const pantalla of VISITABLE_ROUTES) {
  const soloRedirige = pantalla.redirectsTo !== undefined;
  test(`${pantalla.routeId} se dibuja @render`, async ({ page, browserName }) => {
    test.skip(
      (browserName === "chromium") !== soloRedirige,
      soloRedirige
        ? "una redireccion la resuelve el aplicativo: se comprueba una vez, en Chromium"
        : "en Chromium esta pantalla ya la abre y la comprueba la prueba de accesibilidad",
    );
    const observado = await prepare(page, pantalla);
    await openScreen(page, pantalla);

    await expectScreenDrawn(page, pantalla);
    await expectNoHorizontalScroll(page, pantalla.routeId);
    await expectNoCspViolations(page, observado, pantalla.routeId);
    expect(
      unexpectedConsoleErrors(observado, pantalla),
      `${pantalla.routeId}: errores en la consola`,
    ).toEqual([]);
  });
}
