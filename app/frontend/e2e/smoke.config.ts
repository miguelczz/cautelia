// La prueba de humo contra **un aplicativo que ya esta corriendo** (`mise run smoke`).
//
// A diferencia del arnes de accesibilidad, esta no levanta nada: apunta a lo que haya en
// `UNTANGLE_SMOKE_URL` --por omision el `mise run dev` local-- y recorre la bandeja con
// datos sembrados de verdad. Es la prueba que responde "esto funciona de punta a punta
// en mi maquina", que es distinta de "el codigo cumple sus reglas": eso lo dicen las 102
// pruebas de integracion y las 82 de pantalla.
//
// **Es de solo lectura por omision.** Decidir un caso lo cierra, y un caso cerrado no
// vuelve a `derived`: hay que rehacer la base. Con `UNTANGLE_SMOKE_DECIDE=1` tambien
// decide uno y comprueba que sale de la cola.

import { defineConfig, devices } from "@playwright/test";
import { fileURLToPath } from "node:url";

import { prepararCredencial } from "./smoke-setup";

const SALIDA = fileURLToPath(new URL("../../../tmp/smoke/results", import.meta.url));
export const ESTADO = fileURLToPath(new URL("../../../tmp/smoke/credencial.json", import.meta.url));

// El mismo puerto en que sirve `mise run dev` por omision. Estaba en 8004 --el que la
// busqueda de puerto libre habia elegido aquel dia--, asi que cada vez que la demo
// arrancaba en otro habia que pasarle `UNTANGLE_SMOKE_URL`. Con los dos fijos en el
// mismo numero, `mise run smoke` funciona sin averiguar nada.
export const BASE_URL = process.env.UNTANGLE_SMOKE_URL ?? "http://127.0.0.1:8050";
export const ASEGURADORA = process.env.UNTANGLE_SMOKE_TENANT ?? "stonecroft";
export const PERSONA = process.env.UNTANGLE_SMOKE_PRINCIPAL ?? "diana";

prepararCredencial(ASEGURADORA, PERSONA, ESTADO);

export default defineConfig({
  testDir: ".",
  testMatch: "smoke.spec.ts",
  outputDir: SALIDA,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: BASE_URL,
    storageState: ESTADO,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
