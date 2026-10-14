import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { brotliCompressSync, constants, gzipSync } from "node:zlib";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

const SALIDA = fileURLToPath(new URL("./dist", import.meta.url));

// Lo que se comprime: el texto. Las fuentes `woff2` ya viajan comprimidas.
const COMPRIMIBLE = /\.(?:html|js|css|json|svg|txt)$/;

function archivos(directorio: string): string[] {
  return readdirSync(directorio).flatMap((nombre) => {
    const ruta = join(directorio, nombre);
    return statSync(ruta).isDirectory() ? archivos(ruta) : [ruta];
  });
}

/**
 * Deja junto a cada archivo de texto compilado su version gzip y brotli, para que
 * el proceso sirva la que el navegador acepta (PERF-U6.1: lo que se descarga antes
 * de la pagina de espera se mide comprimido). Se comprime una vez al compilar, no
 * en cada peticion, y con la biblioteca de Node: sin dependencia nueva.
 */
function precomprimir(): Plugin {
  return {
    name: "untangle-precompress",
    apply: "build",
    closeBundle() {
      for (const ruta of archivos(SALIDA).filter((archivo) => COMPRIMIBLE.test(archivo))) {
        const contenido = readFileSync(ruta);
        writeFileSync(`${ruta}.gz`, gzipSync(contenido, { level: 9 }));
        writeFileSync(
          `${ruta}.br`,
          brotliCompressSync(contenido, {
            params: { [constants.BROTLI_PARAM_QUALITY]: constants.BROTLI_MAX_QUALITY },
          }),
        );
      }
    },
  };
}

// La compilacion a estaticos (ADR-002). Sale a `dist/`, que es donde el proceso
// los busca y los sirve desde el mismo origen que la API (CG-U6-5). Los archivos
// de `assets/` llevan huella de contenido en el nombre: por eso el proceso puede
// marcarlos inmutables y la pagina de entrada no (BR6.3).
export default defineConfig({
  plugins: [react(), tailwindcss(), precomprimir()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  build: {
    outDir: "dist",
    assetsDir: "assets",
    emptyOutDir: true,
  },
});
