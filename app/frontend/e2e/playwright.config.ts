import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { defineConfig, devices } from "@playwright/test";

// El arnes de accesibilidad y de tiempos (F9, BR7.1 a BR7.6). Corre con
// `mise run a11y`, que primero comprueba la completitud del registro de
// pantallas y compila la interfaz, y **contra el proceso real**: la misma raiz de
// composicion que sirve la demo, con los estaticos recien compilados y las
// cabeceras de verdad, sobre una base efimera (`scripts/servidor-del-arnes.py`).
// Un servidor de desarrollo de Vite no tendria ni la politica de contenido ni la
// cache de produccion, que es parte de lo que el arnes mide.
//
// Tres motores (Q1 de NFR Requirements de U6): Chromium corre todo; Firefox y
// WebKit corren solo las pruebas marcadas `@render`, la prueba de dibujo de
// cada pantalla registrada. Los escenarios de tiempo (`@timing`) corren al final,
// solos, cuando los demas ya terminaron: medirlos mientras otros navegadores
// ocupan la maquina mediria la maquina.
//
// **Los tres solo en la tuberia** (decision de Miguel, 2026-09-29). En un portatil,
// tres motores reales en paralelo --cada uno con su proceso y su base efimera-- son
// varios minutos de ventilador, y correr el arnes en local es opcional por la propia
// practica del equipo: la compuerta autoritativa es GitHub Actions. En local queda
// Chromium, que es el que corre **todas** las pruebas; lo que se pierde es la
// comprobacion de que cada pantalla se dibuja igual en Firefox y en WebKit, y esa
// sigue corriendo en cada entrega, que es donde bloquea.
//
// La senal es `CI`, la misma que ya usa `forbidOnly` unas lineas mas abajo, y no una
// variable propia: dos formas de decir "esto es la tuberia" es como una se queda
// vieja.
//
// Los navegadores se instalan aparte, con `mise run browsers:install`, y **no**
// en el camino del clon al reporte (NFR21.3).

const RAIZ = fileURLToPath(new URL("../../..", import.meta.url));

// Lo que deja cada corrida --capturas, trazas de los fallos, el resumen de
// tiempos-- va a `tmp/`, que esta ignorado y que el motor del flujo salta al
// calcular la huella del codigo.
const SALIDA = fileURLToPath(new URL("../../../tmp/a11y/results", import.meta.url));

// Si esto es la tuberia. La misma senal que `forbidOnly`, para que no haya dos
// formas de decirlo.
const EN_LA_TUBERIA = process.env.CI !== undefined;

// El puerto del proceso bajo prueba: **uno libre, elegido al arrancar**, y no uno
// fijo. Con el 8765 fijo, el arnes chocaba con cualquier proceso que ya lo
// tuviera --por ejemplo, el mismo servidor del arnes abierto a mano para mirar la
// demo--, y el paso 5 de `verify.sh` caia en rojo sin que nada del producto
// hubiera cambiado. Mirar la demo y verificar no pueden excluirse.
//
// Se le pide el puerto al sistema operativo abriendo un servidor en el puerto 0
// y leyendo cual le dio, en un proceso aparte porque la configuracion se carga de
// forma sincrona. Queda una ventana minima entre soltarlo y que el servidor del
// arnes lo tome; es la misma de cualquier eleccion de puerto libre, y fallaria a
// la vista, no en silencio.
//
// Playwright carga este archivo tambien en cada proceso trabajador. El primero
// que lo carga --el principal-- deja el puerto en `A11Y_HARNESS_PORT`, y los
// trabajadores, que heredan su entorno, lo leen de ahi en vez de elegir otro:
// si cada uno eligiera el suyo, apuntarian a servidores que no existen. Quien
// quiera un puerto concreto para depurar lo pone en esa variable.
function puertoLibre(): string {
  return execFileSync(
    process.execPath,
    [
      "-e",
      "const s=require('node:net').createServer();s.listen(0,'127.0.0.1',()=>{process.stdout.write(String(s.address().port));s.close();});",
    ],
    { encoding: "utf8" },
  ).trim();
}

process.env.A11Y_HARNESS_PORT ??= puertoLibre();
const PUERTO = Number(process.env.A11Y_HARNESS_PORT);
const ORIGEN = `http://127.0.0.1:${String(PUERTO)}`;

// Los dos motores que solo corren en la tuberia. Cada uno ejecuta las pruebas de
// dibujo (`@render`) y nada mas: lo que comprueban es que cada pantalla registrada
// se ve igual fuera de Chromium.
const OTROS_MOTORES = EN_LA_TUBERIA
  ? [
      {
        name: "firefox",
        use: { ...devices["Desktop Firefox"] },
        grep: /@render/,
      },
      {
        name: "webkit",
        use: { ...devices["Desktop Safari"] },
        grep: /@render/,
      },
    ]
  : [];

export default defineConfig({
  testDir: ".",
  // **Cada archivo por su nombre, no por un comodin.** `**/*.spec.ts` recogia
  // tambien `smoke.spec.ts`, que existe para correr contra un aplicativo **ya
  // levantado** con datos sembrados: aqui, contra el proceso del arnes y su base
  // vacia, fallaba entera. Y puso `main` en rojo el dia que se creo, porque el
  // guion de verificacion se habia corrido antes de ese commit. Un comodin invita a
  // eso; una lista obliga a decidir donde corre cada archivo nuevo.
  testMatch: ["a11y.spec.ts", "journey.spec.ts", "render.spec.ts", "timing.spec.ts"],
  outputDir: SALIDA,
  fullyParallel: true,
  // **Todos los nucleos en la tuberia, la mitad en local.** Sin esto Playwright usa
  // la mitad de los nucleos, y en la tuberia eso es la mitad de la maquina parada
  // mientras el paso 5 corre. Medido en local sobre Chromium, con las mismas 92
  // pruebas: 66 s con dos trabajadores y 43 s con cuatro. El arnes escala con los
  // trabajadores porque el cuello no es el servidor --uno solo, con su base efimera--
  // sino cuantos navegadores caben a la vez.
  //
  // Es la primera de las dos respuestas que SCALE-U6.2 nombra para cuando el arnes se
  // pasa de su presupuesto: "se paraleliza por pantalla o se sube con decision
  // escrita, nunca se recortan idiomas ni modos". Se paraleliza primero, porque no
  // relaja nada.
  //
  // En local se deja el default: correr el arnes en el portatil es opcional por la
  // propia practica del equipo, y pegarle todos los nucleos es justo el ventilador que
  // la decision del 2026-09-29 queria evitar.
  // Se pone la clave solo en la tuberia, y no como `undefined`: la configuracion de
  // tipos del proyecto distingue "ausente" de "presente y nula".
  ...(EN_LA_TUBERIA ? { workers: "100%" } : {}),
  forbidOnly: process.env.CI !== undefined,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: ORIGEN,
    trace: "retain-on-failure",
  },
  webServer: {
    command: `uv run --project app/backend python scripts/servidor-del-arnes.py --port ${String(PUERTO)}`,
    cwd: RAIZ,
    // Vivo, no listo: la pagina de espera se prueba justamente con el proceso
    // arriba y la salud de listo respondiendo 503.
    url: `${ORIGEN}/api/health/live`,
    reuseExistingServer: false,
    // La base efimera tarda en levantar y migrar.
    timeout: 120_000,
    // Con SIGTERM el proceso apaga su base al salir.
    gracefulShutdown: { signal: "SIGTERM", timeout: 15_000 },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      grepInvert: /@timing/,
    },
    ...OTROS_MOTORES,
    {
      name: "timing",
      use: { ...devices["Desktop Chrome"] },
      grep: /@timing/,
      // **Sus pruebas no corren en paralelo entre si**, aunque el resto del arnes si.
      // Miden cuanto tarda una pagina en pintarse: dos de ellas a la vez medirian la
      // maquina ocupada, que es lo mismo que `dependencies` evita respecto de los
      // otros motores. Con los trabajadores al maximo esto deja de ser teorico.
      fullyParallel: false,
      // Los tiempos se miden cuando **todo lo demas** termino, sea lo que sea que
      // haya corrido: la lista se deriva de los motores activos en vez de escribirse
      // a mano, porque una dependencia a un motor que no existe deja a Playwright sin
      // arrancar, y una que falta deja los tiempos midiendo la maquina ocupada.
      dependencies: ["chromium", ...OTROS_MOTORES.map((motor) => motor.name)],
    },
  ],
});
