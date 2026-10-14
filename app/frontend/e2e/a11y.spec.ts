import { expect, test } from "@playwright/test";

import {
  browserLocale,
  expectAxeClean,
  expectKeyboardTraversal,
  expectNoCspViolations,
  expectNoHorizontalScroll,
  expectOnlyPreferencesStored,
  expectReducedMotion,
  expectSameOrigin,
  expectTouchTargets,
  LANGS,
  MODES,
  openScreen,
  prepare,
  screenLabel,
  unexpectedConsoleErrors,
} from "./support/harness";
import { VISITABLE_ROUTES } from "./visitable-routes";

// F9 en Chromium: cada pantalla registrada, en espanol y en ingles, en modo
// claro y en oscuro (BR7.2, FD-U6-7). El idioma sale del navegador (BR2.1). El
// modo ya no sale del dispositivo: desde la enmienda de BR1.1 del 2026-10-06 el
// aplicativo abre en oscuro y el claro es una eleccion que se guarda, asi que el
// arnes la deja guardada antes de abrir la pagina, como la habria dejado una
// persona que lo eligio en el selector. La preferencia del dispositivo se emula
// igual, para comprobar que no manda.

// Una direccion que solo redirige no se mide dos veces: su destino ya esta en la
// lista, con sus dos idiomas y sus dos modos. Que la redireccion llega lo comprueba
// la prueba de dibujo.
for (const pantalla of VISITABLE_ROUTES.filter((ruta) => ruta.redirectsTo === undefined)) {
  for (const idioma of LANGS) {
    for (const modo of MODES) {
      test.describe(() => {
        test.use({
          locale: browserLocale(idioma),
          colorScheme: modo,
          viewport: { width: 1280, height: 800 },
        });

        test(`${pantalla.routeId} en ${idioma}, modo ${modo}`, async ({ page, baseURL }) => {
          const etiqueta = screenLabel(pantalla, idioma, modo);
          const observado = await prepare(page, pantalla);
          await page.addInitScript((elegido) => {
            window.localStorage.setItem("untangle.theme", elegido);
          }, modo);
          await openScreen(page, pantalla);

          // El idioma que pidio el navegador y el modo que dejo guardado la
          // persona, declarados en el documento (BR2.1, BR2.4, BR1.1).
          await expect(page.locator("html")).toHaveAttribute("lang", idioma);
          await expect(page.locator("html")).toHaveAttribute("data-theme", modo);

          // En el ancho de computador tampoco: es lo que comprobaba aqui la prueba
          // de dibujo de Chromium, que ya no repite estas pantallas.
          await expectNoHorizontalScroll(page, etiqueta);
          await expectAxeClean(page, pantalla, idioma, modo);
          await expectKeyboardTraversal(page, etiqueta);

          // El telefono: 360 x 640 sin desplazamiento horizontal y con controles
          // de 44 x 44 (BR7.3).
          await page.setViewportSize({ width: 360, height: 640 });
          await expectNoHorizontalScroll(page, etiqueta);
          await expectTouchTargets(page, etiqueta);
          await expectAxeClean(page, pantalla, idioma, modo);

          await expectReducedMotion(page, pantalla, etiqueta);
          await expectNoCspViolations(page, observado, etiqueta);
          expectSameOrigin(observado, baseURL ?? "", etiqueta);
          expect(
            unexpectedConsoleErrors(observado, pantalla),
            `${etiqueta}: errores en la consola`,
          ).toEqual([]);
          await expectOnlyPreferencesStored(page, etiqueta);
        });
      });
    }
  }
}
