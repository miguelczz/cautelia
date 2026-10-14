import { defineConfig } from "@hey-api/openapi-ts";

// El cliente tipado de la API, generado desde el esquema que produce FastAPI
// (C-28, BR3.1). Se regenera con `mise run contracts:gen` y el chequeo de deriva
// lo compara byte a byte: si el esquema cambio y el cliente no, la compuerta
// falla nombrando el archivo. **Nunca se edita a mano.**
//
// La salida vive en `src/shared/api/` y es el unico sitio desde donde la
// interfaz habla con el servidor. El generador va en version exacta en el
// manifiesto: una version nueva puede cambiar la forma del codigo generado, y
// eso tiene que ser un cambio a la vista, no una deriva.
// El cliente HTTP que el generador **empaqueta** junto a lo generado (`client/`
// y `core/`) es codigo de terceros: sale igual para cualquier esquema, fijado por
// la version exacta del generador, y no esta escrito para
// `exactOptionalPropertyTypes`. Lleva `// @ts-nocheck`, que es para ese codigo lo
// que `skipLibCheck` es para una dependencia en `node_modules`. Lo generado
// desde **nuestro** esquema --tipos, SDK y consultas-- se comprueba entero: es
// lo que consume la interfaz. El generador calcula la cabecera por archivo para
// lo suyo y una sola vez, sin archivo, para lo empaquetado; asi se distinguen.
const MARCA_DE_EMPAQUETADO =
  "// @ts-nocheck -- cliente HTTP empaquetado por el generador; ver openapi-ts.config.ts";

export default defineConfig({
  input: "../contracts/openapi.json",
  output: {
    path: "src/shared/api",
    header: (ctx) =>
      ctx.file === undefined ? [...ctx.defaultValue, MARCA_DE_EMPAQUETADO] : [...ctx.defaultValue],
  },
  plugins: [
    // El cliente de `fetch` de la plataforma: sin dependencia de ejecucion nueva.
    "@hey-api/client-fetch",
    "@hey-api/typescript",
    "@hey-api/sdk",
    // Las consultas de TanStack Query (ADR-002), sin capa persistente: los
    // datos viven solo en la memoria de la pestana (BR3.5).
    "@tanstack/react-query",
  ],
});
