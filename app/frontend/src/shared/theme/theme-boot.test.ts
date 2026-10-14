import { afterEach, describe, expect, it, vi } from "vitest";

import bootScript from "../../../public/theme-boot.js?raw";
import { readStoredTheme, resolveTheme, THEME_STORAGE_KEY } from "./preference";
import { DARK_QUERY, stubMatchMedia } from "./testing";

// BR1.2 y CG-U6-1: el paso que corre antes de pintar es un archivo propio, y
// decide **lo mismo** que el proveedor de modo. Se ejecuta el archivo tal cual
// se sirve, en los mismos escenarios, y se compara con la regla en TypeScript.

/** Corre un guion clasico en la ventana del documento, como lo hace el navegador. */
function correr(codigo: string): void {
  const guion = document.createElement("script");
  guion.textContent = codigo;
  document.head.appendChild(guion);
  guion.remove();
}

/**
 * El guion corre en la ventana propia del documento de pruebas, que no es el
 * objeto global de la prueba: la preferencia del dispositivo se le instala ahi,
 * con otro guion, antes de correr el paso de modo.
 */
function dispositivoEnOscuro(oscuro: boolean): void {
  correr(
    `window.matchMedia = function (consulta) { return { matches: ${String(oscuro)} && consulta === ${JSON.stringify(DARK_QUERY)} }; };`,
  );
}

function ejecutarPasoDeModo(): { mode: string | null; source: string | null } {
  correr(bootScript);
  const raiz = document.documentElement;
  return { mode: raiz.getAttribute("data-theme"), source: raiz.getAttribute("data-theme-source") };
}

const ESCENARIOS: readonly { nombre: string; guardado: string | null; oscuro: boolean }[] = [
  { nombre: "primera visita con el dispositivo en claro", guardado: null, oscuro: false },
  { nombre: "primera visita con el dispositivo en oscuro", guardado: null, oscuro: true },
  {
    nombre: "eleccion guardada en claro con el dispositivo en oscuro",
    guardado: "light",
    oscuro: true,
  },
  {
    nombre: "eleccion guardada en oscuro con el dispositivo en claro",
    guardado: "dark",
    oscuro: false,
  },
  { nombre: "valor corrupto", guardado: "sepia", oscuro: true },
];

afterEach(() => {
  vi.restoreAllMocks();
});

describe("el paso de modo antes de pintar", () => {
  it.each(ESCENARIOS)("decide igual que el proveedor: $nombre", ({ guardado, oscuro }) => {
    vi.spyOn(console, "info").mockImplementation(() => undefined);
    stubMatchMedia({ [DARK_QUERY]: oscuro });
    dispositivoEnOscuro(oscuro);
    if (guardado !== null) {
      window.localStorage.setItem(THEME_STORAGE_KEY, guardado);
    }

    const delPaso = ejecutarPasoDeModo();
    const delProveedor = resolveTheme(readStoredTheme());

    expect(delPaso).toEqual({ mode: delProveedor.mode, source: delProveedor.source });
  });

  it("con el almacenamiento bloqueado abre en oscuro sin lanzar, aunque el dispositivo prefiera claro", () => {
    dispositivoEnOscuro(false);
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });

    // La constancia va a la consola de la ventana del documento; lo que se
    // comprueba aqui es que la pagina se pinta con el modo por defecto.
    expect(ejecutarPasoDeModo()).toEqual({ mode: "dark", source: "default" });
  });

  it("sin eleccion guardada no mira al dispositivo: en claro tambien abre en oscuro", () => {
    vi.spyOn(console, "info").mockImplementation(() => undefined);
    dispositivoEnOscuro(false);

    expect(ejecutarPasoDeModo()).toEqual({ mode: "dark", source: "default" });
  });

  it("usa la misma clave de almacenamiento que el proveedor", () => {
    expect(bootScript).toContain(`"${THEME_STORAGE_KEY}"`);
  });
});
