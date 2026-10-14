import { expect, test } from "@playwright/test";

import {
  ALLOWED_STORAGE_KEYS,
  expectOnlyPreferencesStored,
  waitForHeading,
} from "./support/harness";
import { VISITABLE_ROUTES } from "./visitable-routes";

// Lo que se mira recorriendo varias pantallas en la misma pestana: el modo se
// aplica antes del primer cuadro (BR1.2), ninguna navegacion lo cambia (BR1.3), y
// al terminar el navegador solo guardo preferencias (BR3.5, SEC-U6.5).

const RUTAS = VISITABLE_ROUTES.filter((pantalla) => pantalla.readiness === undefined);

test.describe(() => {
  test.use({ locale: "es-CO", colorScheme: "dark" });

  test("con una eleccion guardada, el primer cuadro ya tiene ese modo", async ({ page }) => {
    // La eleccion guardada se pone antes de que corra ningun guion de la pagina,
    // y el modo se lee en el instante en que aparece el cuerpo del documento: ahi
    // todavia no corrio la aplicacion, solo el paso de modo de la cabecera.
    await page.addInitScript(() => {
      window.localStorage.setItem("untangle.theme", "light");
      const anotado: string[] = [];
      Object.defineProperty(window, "__themeAtBody", { value: anotado });
      const anotar = (): boolean => {
        if ((document.body as HTMLElement | null) === null) {
          return false;
        }
        anotado.push(document.documentElement.getAttribute("data-theme") ?? "sin modo");
        return true;
      };
      if (!anotar()) {
        new MutationObserver((_, observador) => {
          if (anotar()) {
            observador.disconnect();
          }
        }).observe(document, { childList: true, subtree: true });
      }
    });

    await page.goto("/");

    const alAparecerElCuerpo = await page.evaluate(
      () => (window as unknown as { __themeAtBody: string[] }).__themeAtBody,
    );
    expect(alAparecerElCuerpo).toEqual(["light"]);
  });

  test("recorrer todas las pantallas conserva el modo y guarda solo preferencias", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page.getByTestId("home")).not.toHaveAttribute("data-home-state", "loading");
    await page.getByRole("button", { name: "Claro" }).click();
    await page.getByRole("button", { name: "English" }).click();
    await expect(page.locator("html")).toHaveAttribute("lang", "en");

    for (const pantalla of RUTAS) {
      await page.goto(pantalla.path);
      await waitForHeading(page);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(
        page.locator("html"),
        `${pantalla.routeId}: el modo cambio al navegar`,
      ).toHaveAttribute("data-theme", "light");
    }

    await expectOnlyPreferencesStored(page, "recorrido completo");
    const guardadas = await page.evaluate(() => Object.keys(window.localStorage));
    expect(guardadas.every((clave) => ALLOWED_STORAGE_KEYS.has(clave))).toBe(true);
    expect(guardadas).toContain("untangle.theme");
  });
});
