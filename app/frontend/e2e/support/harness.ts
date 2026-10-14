// Las comprobaciones del arnes, una por regla (F9; BR7.2 a BR7.6, SEC-U6.2,
// SEC-U6.5, CG-U6-2).
//
// Cada una falla con un mensaje que nombra la pantalla, el idioma, el modo, la
// regla y el elemento: un arnes que solo dice "fallo" obliga a reproducir a mano
// lo que el ya sabia.

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

import type { VisitableRoute } from "../visitable-routes";

export type Lang = "es" | "en";
export type Mode = "light" | "dark";

export const LANGS: readonly Lang[] = ["es", "en"];
export const MODES: readonly Mode[] = ["light", "dark"];

/** El idioma del navegador que abre cada idioma de la pagina (BR2.1). */
export function browserLocale(lang: Lang): string {
  return lang === "es" ? "es-CO" : "en-US";
}

/**
 * Las claves que la interfaz puede guardar en el navegador (BR3.5, SEC-U6.5): el
 * modo, el idioma elegido y el idioma que comparte con la landing (el mismo
 * dominio, `cautelia-lang`).
 *
 * Y el borrador del cuadro de escribir del chat (`cautelia.chat-drafts`, 2026-10-12): lo
 * escrito y no enviado, que vuelve al regresar a la pagina. Es una sola clave con un
 * objeto por aseguradora, y solo aparece cuando alguien escribe: nunca lo guarda un
 * recorrido que se limita a mirar.
 */
export const ALLOWED_STORAGE_KEYS: ReadonlySet<string> = new Set([
  "untangle.theme",
  "untangle.locale",
  "cautelia-lang",
  "cautelia.chat-drafts",
]);

/** La consulta con que toda pantalla pregunta, al arrancar, si el servidor esta listo. */
const SALUD_DE_LISTO = "/api/health/ready";

/** Lo que el arnes observa de una pagina mientras la recorre. */
export interface Observed {
  readonly requests: string[];
  readonly consoleErrors: string[];
  /** Las veces que la salud de listo respondio 503 de verdad (ver `unexpectedConsoleErrors`). */
  readonly notReady: string[];
}

/** El cuerpo de un 503 de listo, con la forma de C-01 (lo que ve la espera). */
const LISTO_503 = JSON.stringify({
  type: "about:blank",
  title: "Service unavailable",
  status: 503,
  trace_id: "00000000000000000000000000000000",
  code: "provider_unavailable",
  retry_after_s: 5,
});

/**
 * Prepara la pagina antes de abrirla: registra cada peticion y cada error de la
 * consola, anota las violaciones de la politica de contenido y, para las dos
 * paginas de la espera, hace que la salud de listo responda 503.
 */
export async function prepare(page: Page, screen: VisitableRoute): Promise<Observed> {
  const observado: Observed = { requests: [], consoleErrors: [], notReady: [] };
  page.on("request", (peticion) => {
    observado.requests.push(peticion.url());
  });
  page.on("response", (respuesta) => {
    if (respuesta.status() === 503 && new URL(respuesta.url()).pathname === SALUD_DE_LISTO) {
      observado.notReady.push(respuesta.url());
    }
  });
  page.on("console", (mensaje) => {
    if (mensaje.type() === "error") {
      observado.consoleErrors.push(mensaje.text());
    }
  });
  page.on("pageerror", (error) => {
    observado.consoleErrors.push(`${error.name}: ${error.message}`);
  });
  // Toda violacion de la politica de contenido queda anotada en la pagina, aunque
  // el navegador no la diga en la consola (CG-U6-2).
  await page.addInitScript(() => {
    const anotadas: string[] = [];
    Object.defineProperty(window, "__cspViolations", { value: anotadas });
    document.addEventListener("securitypolicyviolation", (evento) => {
      anotadas.push(`${evento.violatedDirective} ${evento.blockedURI}`);
    });
  });
  if (screen.readiness !== undefined) {
    await page.route("**/api/health/ready", (ruta) =>
      ruta.fulfill({
        status: 503,
        contentType: "application/problem+json",
        headers: { "Retry-After": "5" },
        body: LISTO_503,
      }),
    );
  }
  if (screen.readiness === "unavailable") {
    await page.clock.install();
  }
  // Las respuestas declaradas de la pantalla, cuando trae alguna. El arnes corre
  // contra una base vacia, asi que sin esto las pantallas de la bandeja se dibujarian
  // todas como "no hay nada aqui" y lo que entraria en la linea base seria una pagina
  // de estado en vez de la pantalla. Lo que se mide es el dibujo; las reglas de
  // acceso se prueban contra la base de verdad, en las pruebas de integracion.
  for (const respuesta of screen.stub ?? []) {
    await page.route(respuesta.url, (ruta) =>
      ruta.fulfill(
        respuesta.sse === true
          ? {
              status: 200,
              contentType: "text/event-stream",
              // Solo la senal de apertura: la pantalla queda conectada y no llega
              // ningun aviso, que es el estado en el que hay que medirla.
              body: "retry: 3000\n: open\n\n",
            }
          : {
              status: 200,
              contentType: "application/json",
              body: JSON.stringify(respuesta.body),
            },
      ),
    );
  }
  return observado;
}

/** Cuanto se espera el titulo mirando en cada cuadro, antes de dejarselo a la asercion. */
const ESPERA_DEL_TITULO_MS = 5_000;

/**
 * Espera a que el titulo este dibujado, mirando en cada cuadro.
 *
 * No comprueba nada: la asercion que sigue es la misma de siempre. Existe porque las
 * esperas de Playwright reintentan a los 0, 20, 50, 100 y 100 ms y despues **cada 500**:
 * el aplicativo pinta su titulo hacia los 370 ms, justo despues del quinto intento, y
 * cada apertura dormia hasta el siguiente --unos 450 ms sin hacer nada, medidos el
 * 2026-10-12 en las tres rutas probadas--. Con 150 aperturas por corrida, eso era parte
 * de lo que tenia al arnes contra su presupuesto. Si el titulo no llega, no falla aqui:
 * falla la asercion, con su mensaje.
 */
export async function waitForHeading(page: Page): Promise<void> {
  await page
    .waitForFunction(
      () => {
        const titulo = document.querySelector("h1");
        return titulo !== null && titulo.getClientRects().length > 0;
      },
      undefined,
      { timeout: ESPERA_DEL_TITULO_MS },
    )
    .catch(() => undefined);
}

/**
 * Abre la pantalla y espera a que este dibujada del todo.
 *
 * Las dos pantallas de la espera son distintas: con el proceso dormido no hay titulo
 * ni texto --solo el esqueleto de la pantalla pedida y su hilo de progreso, sin contar
 * por que (decision de Miguel, 2026-10-06)--, y a los 60 s aparece "no disponible",
 * que si tiene titulo.
 */
export async function openScreen(page: Page, screen: VisitableRoute): Promise<void> {
  await page.goto(screen.path);

  if (screen.readiness === "waking") {
    await expectWaitingSkeleton(page);
    return;
  }
  if (screen.readiness === "unavailable") {
    await expectWaitingSkeleton(page);
    // Sesenta segundos de espera, sin esperarlos de verdad (BR5.4).
    await page.clock.fastForward("01:01");
    await expect(page.getByTestId("status-page")).toHaveAttribute(
      "data-status-kind",
      "unavailable",
    );
  } else {
    // Con el reloj de la pagina tomado (la rama de arriba) no se mira por cuadros.
    await waitForHeading(page);
  }
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  if (screen.route === "/" || screen.route === "/home") {
    // La raiz redirige al inicio; las dos terminan en la misma pantalla.
    await expect(page.getByTestId("home")).toBeVisible();
  }
}

/** La espera del proceso: el esqueleto de la pantalla pedida, sin una palabra a la vista. */
export async function expectWaitingSkeleton(page: Page): Promise<void> {
  const esqueleto = page.getByTestId("page-skeleton");
  await expect(esqueleto).toBeVisible();
  await expect(esqueleto).toHaveAttribute("aria-busy", "true");
  await expect(page.getByTestId("progress-thread")).toBeAttached();
  await expect(page.getByRole("heading")).toHaveCount(0);
}

/** Lo que dice una pantalla dibujada: su titulo, o su esqueleto si es la espera. */
export async function expectScreenDrawn(page: Page, screen: VisitableRoute): Promise<void> {
  if (screen.readiness === "waking") {
    await expectWaitingSkeleton(page);
    return;
  }
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
}

function etiqueta(screen: VisitableRoute, lang: Lang, mode: Mode): string {
  return `${screen.routeId} (${lang}, ${mode})`;
}

/**
 * BR7.2: el analizador automatico; un hallazgo serio o critico en una pantalla de
 * visitante bloquea, y en una de personal se reporta sin bloquear (D25).
 */
export async function expectAxeClean(page: Page, screen: VisitableRoute, lang: Lang, mode: Mode) {
  const resultado = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"])
    // Solo se arman los hallazgos, que es lo unico que aqui se lee: corren las mismas
    // reglas y salen las mismas violaciones, sin el detalle de lo que paso o no aplica
    // (un 10 % menos por analisis, medido el 2026-10-12, y hay dos por prueba).
    .options({ resultTypes: ["violations"] })
    .analyze();
  const graves = resultado.violations.filter(
    (hallazgo) => hallazgo.impact === "serious" || hallazgo.impact === "critical",
  );
  const reporte = graves.map(
    (hallazgo) =>
      `${etiqueta(screen, lang, mode)} ${hallazgo.id} [${hallazgo.impact ?? "?"}]: ` +
      hallazgo.nodes.map((nodo) => nodo.target.join(" ")).join(" | "),
  );
  if (screen.audience === "staff") {
    for (const linea of reporte) {
      console.warn(`a11y (staff, no bloquea): ${linea}`);
    }
    return;
  }
  expect(reporte, reporte.join("\n")).toEqual([]);
}

/** BR7.3: sin desplazamiento horizontal. */
export async function expectNoHorizontalScroll(page: Page, label: string): Promise<void> {
  const medidas = await page.evaluate(() => {
    const raiz = document.scrollingElement ?? document.documentElement;
    return { ancho: raiz.scrollWidth, ventana: raiz.clientWidth };
  });
  expect(medidas.ancho, `${label}: la pagina se desplaza en horizontal`).toBeLessThanOrEqual(
    medidas.ventana,
  );
}

/** BR7.3: todo control tactil visible mide al menos 44 x 44. */
export async function expectTouchTargets(page: Page, label: string): Promise<void> {
  const pequenos = await page.evaluate(() => {
    const controles = document.querySelectorAll<HTMLElement>(
      'a[href], button, input, select, textarea, [role="button"], [tabindex]:not([tabindex="-1"])',
    );
    return [...controles]
      .filter((control) => {
        const caja = control.getBoundingClientRect();
        // Lo que no se ve --el enlace para saltar sin foco-- no es un objetivo.
        return (
          caja.width > 1 && caja.height > 1 && control.closest("[aria-hidden='true']") === null
        );
      })
      .filter((control) => {
        const caja = control.getBoundingClientRect();
        return caja.width < 44 || caja.height < 44;
      })
      .map((control) => {
        const caja = control.getBoundingClientRect();
        return `${control.tagName.toLowerCase()} "${control.textContent.trim()}" ${String(Math.round(caja.width))}x${String(Math.round(caja.height))}`;
      });
  });
  expect(pequenos, `${label}: controles de menos de 44 x 44`).toEqual([]);
}

interface Enfocado {
  readonly id: string;
  readonly visible: boolean;
}

/**
 * BR7.4: el primer elemento que recibe el foco es "Saltar al contenido"; con Tab
 * se llega a todo, con el anillo visible, y el recorrido sale de la pagina (no
 * hay trampas).
 */
export async function expectKeyboardTraversal(page: Page, label: string): Promise<void> {
  const recorribles = await page.evaluate(() => {
    const todos = document.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    return [...todos]
      .filter(
        (elemento) => elemento.tabIndex >= 0 && elemento.closest("[aria-hidden='true']") === null,
      )
      .filter((elemento) => getComputedStyle(elemento).visibility !== "hidden")
      .filter((elemento) => elemento.getClientRects().length > 0)
      .map((elemento, indice) => {
        elemento.setAttribute("data-harness-tab", String(indice));
        return elemento.getAttribute("data-testid") ?? String(indice);
      });
  });
  expect(recorribles.length, `${label}: no hay nada que recorrer con el teclado`).toBeGreaterThan(
    0,
  );
  expect(recorribles[0], `${label}: el primer elemento enfocable no es "Saltar al contenido"`).toBe(
    "skip-link",
  );

  const vistos = new Map<string, boolean>();
  let salio = false;
  const todos = recorribles.map((_, indice) => String(indice));
  // Dos vueltas como tope: una pantalla que abre con el foco puesto en un campo --el
  // chat-- sale de la pagina antes de pasar por lo que queda arriba, y necesita la
  // segunda para verlo. Pero se deja de pulsar en cuanto ya se vio todo y el foco salio:
  // seguir no comprueba nada mas, y esas pulsaciones de sobra eran la mitad del tiempo
  // del arnes en el corredor de dos nucleos (2026-10-12). Una trampa o un elemento
  // inalcanzable no cumplen la condicion, agotan el tope y fallan como antes.
  for (let pulsacion = 0; pulsacion < recorribles.length * 2 + 4; pulsacion += 1) {
    if (salio && todos.every((id) => vistos.has(id))) {
      break;
    }
    await page.keyboard.press("Tab");
    const actual = await page.evaluate((): Enfocado | null => {
      const activo = document.activeElement as HTMLElement | null;
      if (activo === null || activo === document.body) {
        return null;
      }
      const estilo = getComputedStyle(activo);
      const anillo = estilo.outlineStyle !== "none" && Number.parseFloat(estilo.outlineWidth) >= 2;
      return { id: activo.getAttribute("data-harness-tab") ?? activo.tagName, visible: anillo };
    });
    if (actual === null) {
      salio = true;
      continue;
    }
    vistos.set(actual.id, actual.visible);
  }

  const faltan = todos.filter((id) => !vistos.has(id));
  expect(faltan, `${label}: elementos a los que no se llega con Tab (posible trampa)`).toEqual([]);
  const sinAnillo = [...vistos].filter(([, visible]) => !visible).map(([id]) => id);
  expect(sinAnillo, `${label}: elementos con foco sin anillo visible`).toEqual([]);
  expect(salio, `${label}: el recorrido con Tab nunca sale de la pagina`).toBe(true);
}

/** BR7.6 y BR5.7: con movimiento reducido no hay desplazamientos ni escalas. */
export async function expectReducedMotion(page: Page, screen: VisitableRoute, label: string) {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const moviles = await page.evaluate(
    () =>
      new Promise<string[]>((resolver) => {
        requestAnimationFrame(() => {
          const enCurso = document
            .getAnimations()
            .filter((animacion) => animacion.playState === "running")
            .filter((animacion) => {
              const efecto = animacion.effect as KeyframeEffect | null;
              const cuadros = efecto?.getKeyframes() ?? [];
              return cuadros.some(
                (cuadro) => "transform" in cuadro || "translate" in cuadro || "scale" in cuadro,
              );
            })
            .map((animacion) => (animacion as CSSAnimation).animationName);
          resolver(enCurso);
        });
      }),
  );
  expect(
    moviles,
    `${label}: animaciones de desplazamiento o escala con movimiento reducido`,
  ).toEqual([]);
  if (screen.readiness === "waking") {
    // Sin movimiento no hay hilo, y queda el esqueleto quieto: no late ni se desplaza.
    await expect(page.getByTestId("page-skeleton")).toBeVisible();
    await expect(page.getByTestId("progress-thread").locator(".ut-thread")).toBeHidden();
  }
  await page.emulateMedia({ reducedMotion: "no-preference" });
}

/** CG-U6-2: ninguna violacion de la politica de contenido. */
export async function expectNoCspViolations(page: Page, observed: Observed, label: string) {
  const anotadas = await page.evaluate(
    () => (window as unknown as { __cspViolations?: string[] }).__cspViolations ?? [],
  );
  const enConsola = observed.consoleErrors.filter((texto) =>
    /content security policy/i.test(texto),
  );
  expect([...anotadas, ...enConsola], `${label}: violaciones de la politica de contenido`).toEqual(
    [],
  );
}

/** SEC-U6.2: ninguna peticion a otro origen. */
export function expectSameOrigin(observed: Observed, origin: string, label: string): void {
  const ajenas = observed.requests.filter(
    (url) => !url.startsWith("data:") && !url.startsWith("blob:") && new URL(url).origin !== origin,
  );
  expect(ajenas, `${label}: peticiones a terceros`).toEqual([]);
}

/**
 * Los errores de consola de la pagina. En las pantallas de la espera, el
 * navegador anota como error cada 503 de la salud de listo: es lo que la pagina
 * espera recibir, y no cuenta.
 *
 * **En las demas pantallas tampoco cuenta el 503 de la salud de listo, y solo ese.** Toda
 * pantalla pregunta al arrancar si el servidor esta listo, y "todavia no" es una respuesta
 * que sabe atender: espera y vuelve a preguntar. En un corredor lento el servidor de verdad
 * la dio una vez (2026-10-13, `voice-console` en WebKit): la pantalla espero, se dibujo bien y
 * la prueba fallo por el aviso del navegador. El mensaje de la consola no trae la direccion,
 * asi que se descuentan tantos avisos de 503 como respuestas 503 **de esa ruta** se vieron
 * pasar; un 503 de cualquier otra ruta sigue contando.
 */
export function unexpectedConsoleErrors(observed: Observed, screen: VisitableRoute): string[] {
  let porDescontar = observed.notReady.length;
  return observed.consoleErrors.filter((texto) => {
    if (/content security policy/i.test(texto)) {
      return false;
    }
    if (!texto.includes("status of 503")) {
      return true;
    }
    if (screen.readiness !== undefined) {
      return false;
    }
    if (porDescontar > 0) {
      porDescontar -= 1;
      return false;
    }
    return true;
  });
}

/** SEC-U6.5: el navegador guarda solo preferencias. */
export async function expectOnlyPreferencesStored(page: Page, label: string): Promise<void> {
  const claves = await page.evaluate(() => ({
    local: Object.keys(window.localStorage),
    session: Object.keys(window.sessionStorage),
  }));
  const ajenas = claves.local.filter((clave) => !ALLOWED_STORAGE_KEYS.has(clave));
  expect(ajenas, `${label}: claves guardadas que no son preferencias`).toEqual([]);
  expect(claves.session, `${label}: claves guardadas en la sesion`).toEqual([]);
}

export function screenLabel(screen: VisitableRoute, lang: Lang, mode: Mode): string {
  return etiqueta(screen, lang, mode);
}
