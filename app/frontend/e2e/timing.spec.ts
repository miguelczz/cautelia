import { expect, test, type CDPSession, type Page } from "@playwright/test";

// Los escenarios de tiempo en un telefono de gama media con red lenta (Q2 de NFR
// Requirements): el perfil que Lighthouse llama "4G lenta" --1,6 Mbps de bajada,
// 750 kbps de subida y 150 ms de ida y vuelta-- y la CPU cuatro veces mas lenta.
//
// - NFR16.3: la espera, con la salud de listo respondiendo 503, pinta el esqueleto
//   de la pantalla pedida en **menos de 3 s**. Antes era el titulo de "la demo esta
//   despertando"; esa pagina ya no existe (decision de Miguel, 2026-10-06) y el umbral
//   no baja.
// - PERF-U6.1: lo que el navegador descarga antes de pintarla --HTML, JavaScript,
//   CSS y la fuente del cuerpo de texto-- pesa **200 KB o menos** comprimido.
// - PERF-U6.2: el inicio, con el proceso listo, muestra sus tres filas en **4 s o
//   menos**.
//
// Los tiempos salen del propio navegador, no de lo que tarda Playwright en darse
// cuenta: la API de Element Timing (el atributo `elementtiming` de cada fila) y, para
// el esqueleto --que son bloques de color sin texto ni imagen, y por eso no los
// reporta--, el cuadro en que el navegador dibujo la region de espera. Cada valor medido sale en la salida de la corrida y
// como anotacion del reporte, pase o no pase su umbral.

const NFR16_3_MAX_MS = 3_000;
const PERF_U6_1_MAX_BYTES = 200_000;
const PERF_U6_2_MAX_MS = 4_000;

const LISTO_503 = JSON.stringify({
  type: "about:blank",
  title: "Service unavailable",
  status: 503,
  trace_id: "00000000000000000000000000000000",
  code: "provider_unavailable",
  retry_after_s: 5,
});

interface Descarga {
  readonly url: string;
  readonly wallTimeMs: number;
  bytes: number;
}

async function telefonoLento(
  page: Page,
): Promise<{ cdp: CDPSession; descargas: Map<string, Descarga> }> {
  const cdp = await page.context().newCDPSession(page);
  const descargas = new Map<string, Descarga>();
  cdp.on("Network.requestWillBeSent", (evento) => {
    descargas.set(evento.requestId, {
      url: evento.request.url,
      wallTimeMs: evento.wallTime * 1000,
      bytes: 0,
    });
  });
  cdp.on("Network.loadingFinished", (evento) => {
    const descarga = descargas.get(evento.requestId);
    if (descarga !== undefined) {
      descarga.bytes = evento.encodedDataLength;
    }
  });
  await cdp.send("Network.enable");
  await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
  await cdp.send("Network.emulateNetworkConditions", {
    offline: false,
    latency: 150,
    downloadThroughput: (1.6 * 1024 * 1024) / 8,
    uploadThroughput: (750 * 1024) / 8,
  });
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  return { cdp, descargas };
}

/** Anota cada pintado de un elemento con `elementtiming`, desde antes de cargar. */
async function anotarPintados(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const pintados: { id: string; t: number }[] = [];
    Object.defineProperty(window, "__paints", { value: pintados });
    new PerformanceObserver((lista) => {
      for (const entrada of lista.getEntries() as (PerformanceEntry & {
        identifier: string;
        renderTime: number;
        loadTime: number;
      })[]) {
        pintados.push({ id: entrada.identifier, t: entrada.renderTime || entrada.loadTime });
      }
    }).observe({ type: "element", buffered: true });
  });
}

/**
 * Anota el cuadro en que se dibujo el esqueleto de la espera: cuando aparece la region
 * en el documento, dos cuadros despues --el primero lo compone y el segundo lo
 * muestra--, con el reloj del propio navegador.
 */
async function anotarEsqueleto(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const observador = new MutationObserver(() => {
      if (document.querySelector('[data-testid="page-skeleton"]') === null) {
        return;
      }
      observador.disconnect();
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          Object.defineProperty(window, "__skeletonPaint", { value: performance.now() });
        });
      });
    });
    observador.observe(document, { childList: true, subtree: true });
  });
}

async function pintados(page: Page, id: string): Promise<number[]> {
  return page.evaluate(
    (buscado) =>
      (window as unknown as { __paints: { id: string; t: number }[] }).__paints
        .filter((pintado) => pintado.id === buscado)
        .map((pintado) => pintado.t),
    id,
  );
}

/** Publica lo medido: en la salida de la corrida y como anotacion del reporte. */
function publicar(escenario: string, valores: Record<string, number>): void {
  const linea = `timing ${escenario}: ${JSON.stringify(valores)}`;
  console.log(linea);
  test.info().annotations.push({ type: "timing", description: linea });
}

test.describe.configure({ mode: "serial" });

test.use({
  viewport: { width: 360, height: 640 },
  isMobile: true,
  hasTouch: true,
  deviceScaleFactor: 2,
  locale: "es-CO",
  colorScheme: "dark",
});

test("el esqueleto de la espera se pinta en menos de 3 s y pesa 200 KB o menos antes @timing", async ({
  page,
}) => {
  const { descargas } = await telefonoLento(page);
  await anotarEsqueleto(page);
  await page.route("**/api/health/ready", (ruta) =>
    ruta.fulfill({
      status: 503,
      contentType: "application/problem+json",
      headers: { "Retry-After": "5" },
      body: LISTO_503,
    }),
  );

  await page.goto("/");
  await expect(page.getByTestId("page-skeleton")).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() => (window as unknown as { __skeletonPaint?: number }).__skeletonPaint),
    )
    .toBeDefined();
  // La fuente del cuerpo de texto cuenta en el peso aunque llegue despues del
  // primer pintado con la fuente del sistema (PERF-U6.1).
  await page.evaluate(() => document.fonts.ready);

  const esqueletoMs = await page.evaluate(
    () => (window as unknown as { __skeletonPaint?: number }).__skeletonPaint,
  );
  const origen = await page.evaluate(() => performance.timeOrigin);
  if (esqueletoMs === undefined) {
    throw new Error("the waiting skeleton was never painted");
  }
  const antes = [...descargas.values()].filter(
    (descarga) =>
      descarga.wallTimeMs <= origen + esqueletoMs || /ibm-plex-sans-.*\.woff2/.test(descarga.url),
  );
  const bytes = antes.reduce((suma, descarga) => suma + descarga.bytes, 0);

  publicar("waiting", {
    skeleton_ms: Math.round(esqueletoMs),
    bytes_before: bytes,
    requests: antes.length,
  });
  expect(esqueletoMs, "NFR16.3: el esqueleto de espera tardo 3 s o mas").toBeLessThan(
    NFR16_3_MAX_MS,
  );
  expect(
    bytes,
    "PERF-U6.1: lo descargado antes de la pagina de espera pasa de 200 KB",
  ).toBeLessThanOrEqual(PERF_U6_1_MAX_BYTES);
});

test("el inicio muestra sus tres filas en 4 s o menos @timing", async ({ page }) => {
  await telefonoLento(page);
  await anotarPintados(page);

  await page.goto("/");
  await expect(page.getByTestId("insurer-row")).toHaveCount(3);
  await expect
    .poll(async () => (await pintados(page, "insurer-name")).length)
    .toBeGreaterThanOrEqual(3);

  const filas = await pintados(page, "insurer-name");
  const ultimaMs = Math.max(...filas);

  publicar("home", { rows_ms: Math.round(ultimaMs) });
  expect(
    ultimaMs,
    "PERF-U6.2: el inicio tardo mas de 4 s en mostrar sus filas",
  ).toBeLessThanOrEqual(PERF_U6_2_MAX_MS);
});
