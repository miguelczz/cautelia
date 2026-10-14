// Prepara la prueba de humo: una credencial de bandeja, sin que su valor se vea.
//
// La emite el comando de U2 y se guarda como **estado de navegador** en `tmp/`, que
// esta ignorado por git. Ni se imprime, ni se escribe en el repositorio, ni aparece en
// la salida de Playwright: lo unico que se dice es que se emitio.
//
// **Por que un comando y no una constante.** Una credencial escrita en el repositorio es
// una credencial publicada, y de ahi no se vuelve borrandola (D23). Esta dura doce horas
// y se emite de nuevo en cada corrida.

import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = fileURLToPath(new URL("../../..", import.meta.url));

/** La cookie de personal, tal como la emite y la lee el aplicativo. */
const COOKIE = "untangle_staff";

export function prepararCredencial(tenantId: string, principalId: string, destino: string): void {
  // El token sale por la salida estandar y todo lo demas por la de error, que es
  // exactamente para esto: se puede canalizar sin arrastrar el aviso.
  // **La ultima linea que no es un evento**, no toda la salida: el registro del proceso
  // escribe sus eventos JSON por la misma salida estandar, asi que tomar el bloque entero
  // le pega `{"event": "tenancy.staff_credential_issued", ...}` delante al token y el
  // navegador rechaza la cookie con "Invalid cookie fields", que no dice nada de esto.
  const salida = execFileSync(
    "uv",
    [
      "run",
      "--env-file",
      ".env",
      "--project",
      "app/backend",
      "python",
      "-m",
      "untangle.tenancy.cli",
      "issue-credential",
      "--tenant",
      tenantId,
      "--principal",
      principalId,
    ],
    { cwd: RAIZ, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] },
  );
  const token = salida
    .split("\n")
    .map((linea) => linea.trim())
    .filter((linea) => linea !== "" && !linea.startsWith("{"))
    .at(-1);

  if (!token) {
    throw new Error(
      "el comando no devolvio credencial: revisa UNTANGLE_STAFF_CREDENTIAL_SIGNING_KEY en .env",
    );
  }

  const url = new URL(process.env.UNTANGLE_SMOKE_URL ?? "http://127.0.0.1:8004");
  const estado = {
    cookies: [
      {
        name: COOKIE,
        value: token,
        domain: url.hostname,
        path: "/",
        // Un instante concreto y no `-1`: el protocolo del navegador rechaza la cookie
        // de sesion cuando llega por estado guardado. Doce horas es lo que dura la
        // credencial, asi que caduca a la vez que ella.
        expires: Math.floor(Date.now() / 1000) + 12 * 60 * 60,
        httpOnly: false,
        secure: false,
        sameSite: "Lax" as const,
      },
    ],
    origins: [],
  };

  mkdirSync(dirname(destino), { recursive: true });
  writeFileSync(destino, JSON.stringify(estado), "utf8");
  console.log(`credencial de '${principalId}' en '${tenantId}' preparada (no se imprime)`);
}
