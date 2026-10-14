import js from "@eslint/js";
import tseslint from "typescript-eslint";
import security from "eslint-plugin-security";
import jsxA11y from "eslint-plugin-jsx-a11y";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import boundaries from "eslint-plugin-boundaries";

// Configuracion plana de ESLint 10 (ADR-002). El alcance se declara como el
// subarbol de este proyecto: la landing, `docs/`, `.claude/` y `aidlc/` quedan
// fuera por construccion, no por una lista de excepciones que crece.
export default tseslint.config(
  {
    ignores: ["coverage/**", "dist/**", "node_modules/**"],
  },
  js.configs.recommended,
  // `strictTypeChecked` exige informacion de tipos: es lo que hace que una
  // clave inexistente del catalogo sea un error y no un texto vacio.
  tseslint.configs.strictTypeChecked,
  tseslint.configs.stylisticTypeChecked,
  {
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },
  // Reglas de seguridad activadas: un hallazgo es compuerta dura, no advertencia
  // de estilo (team.md, Code Style).
  security.configs.recommended,
  // Reglas de accesibilidad de JSX, en su juego estricto.
  {
    files: ["src/**/*.tsx"],
    ...jsxA11y.flatConfigs.strict,
  },
  // Reglas de React (U6). `recommended` trae `no-danger-with-children`; la que
  // prohibe insertar HTML desde datos, `no-danger`, se activa aparte y como
  // error, porque es la puerta por la que un texto de un tercero se vuelve
  // codigo en la pagina (SEC-U6.8). `jsx-runtime` quita las reglas que el
  // transformador automatico de JSX ya no necesita.
  //
  // La version de React va escrita y no con `detect`: la deteccion llama a
  // `context.getFilename()`, que ESLint 10 retiro, y el linter entero se cae en
  // el primer archivo. Escrita, el complemento no pasa por ahi. Se comprobo
  // plantando un `dangerouslySetInnerHTML` y viendo fallar `no-danger`. Sube
  // con React, en el mismo cambio que sube el lockfile.
  {
    files: ["src/**/*.tsx"],
    ...react.configs.flat.recommended,
    settings: { react: { version: "19.3" } },
  },
  {
    files: ["src/**/*.tsx"],
    ...react.configs.flat["jsx-runtime"],
  },
  {
    files: ["src/**/*.tsx"],
    rules: {
      "react/no-danger": "error",
      // `elementtiming` es un atributo del DOM (API de Element Timing) que React
      // pasa tal cual; la regla no lo conoce. El arnes lo usa para medir el
      // pintado del titulo de espera y del inicio con el reloj del navegador.
      "react/no-unknown-property": ["error", { ignore: ["elementtiming"] }],
    },
  },
  {
    files: ["src/**/*.ts", "src/**/*.tsx"],
    ...reactHooks.configs.flat["recommended-latest"],
  },
  // --- Solo el cliente generado habla con el servidor (BR3.1, C-28) ----------
  // Ninguna llamada se escribe a mano: `fetch`, `XMLHttpRequest` y
  // `EventSource` solo existen dentro de `src/shared/api/`, que es lo que genera
  // `mise run contracts:gen` desde el esquema. Una llamada escrita a mano se
  // saltaria el tipado del esquema y la comprobacion de deriva, y el dia que la
  // ruta cambie nadie lo notaria.
  {
    files: ["src/**/*.ts", "src/**/*.tsx"],
    ignores: ["src/shared/api/**"],
    rules: {
      "no-restricted-globals": [
        "error",
        { name: "fetch", message: "Use el cliente generado de src/shared/api (BR3.1)." },
        { name: "XMLHttpRequest", message: "Use el cliente generado de src/shared/api (BR3.1)." },
        { name: "EventSource", message: "Use el cliente generado de src/shared/api (BR3.1)." },
      ],
      "no-restricted-properties": [
        "error",
        { object: "window", property: "fetch", message: "Use el cliente generado (BR3.1)." },
        { object: "globalThis", property: "fetch", message: "Use el cliente generado (BR3.1)." },
      ],
    },
  },
  // --- El cliente generado no se corrige a mano (C-28) ----------------------
  //
  // `src/shared/api/` lo escribe `mise run contracts:gen` desde el esquema y la
  // compuerta comprueba que no tenga deriva: editarlo a mano pone la compuerta
  // en rojo en la siguiente corrida. Desde que U14 anadio la cola con cursor, el
  // generador produce ayudantes de paginacion infinita que llevan `@ts-ignore`
  // donde nosotros escribiriamos `@ts-expect-error`.
  //
  // La regla se apaga **solo en esta carpeta y solo para esa comprobacion**. Lo
  // que la regla protege --que nadie silencie un error de tipos que ya no
  // existe-- es una disciplina de quien escribe, y aqui no escribe nadie. Todo
  // lo demas, incluido el chequeo de tipos completo, se sigue aplicando.
  {
    files: ["src/shared/api/**/*.ts"],
    rules: {
      "@typescript-eslint/ban-ts-comment": "off",
    },
  },
  // `EventSource` **si** vive en `src/shared/api-client/`, y solo ahi (U13).
  //
  // El flujo del chat es SSE y no tiene cliente generado que usar: el generador
  // produce clientes de peticion y respuesta, y lo que hace falta aqui es una
  // conexion que el navegador reconecta sola con `Last-Event-ID`, que es lo que
  // ADR-021 pide. La regla de arriba existe para que ninguna pantalla hable con
  // el servidor por su cuenta, y esa carpeta es justamente la puerta: `fetch` y
  // `XMLHttpRequest` siguen prohibidos tambien aqui.
  {
    files: ["src/shared/api-client/**/*.ts"],
    rules: {
      "no-restricted-globals": [
        "error",
        { name: "fetch", message: "Use el cliente generado de src/shared/api (BR3.1)." },
        { name: "XMLHttpRequest", message: "Use el cliente generado de src/shared/api (BR3.1)." },
      ],
    },
  },
  // --- La frontera del cliente generado (BR3.1, C-28, ADR-002) ----------------
  // La otra mitad de la regla de arriba, con `eslint-plugin-boundaries`: el
  // cliente generado (`src/shared/api/`) solo lo importa `src/shared/api-client/`,
  // que es donde viven la tabla de errores y las consultas. Ninguna pantalla habla
  // con el servidor por su cuenta, ni siquiera a traves del cliente generado, y
  // ninguna trae otra libreria HTTP: toda llamada pasa por la tabla que convierte
  // un error en texto del catalogo (BR3.2 a BR3.4).
  //
  // Los imports son relativos a proposito: el resolvedor de Node que trae el
  // complemento los sigue sin configuracion extra, y un alias `@/` lo dejaria sin
  // resolver y la regla sin efecto.
  {
    files: ["src/**/*.ts", "src/**/*.tsx"],
    plugins: { boundaries },
    settings: {
      "import/resolver": { node: { extensions: [".ts", ".tsx", ".js"] } },
      "boundaries/elements": [
        { type: "api", pattern: "src/shared/api/**", partialMatch: false },
        { type: "api-client", pattern: "src/shared/api-client/**", partialMatch: false },
        { type: "interface", pattern: "src/**", partialMatch: false },
      ],
    },
    rules: {
      "boundaries/dependencies": [
        "error",
        {
          default: "allow",
          // Sin esto la regla solo mira las dependencias locales, y la politica
          // de librerias HTTP de abajo no veria ninguna.
          checkAllOrigins: true,
          policies: [
            {
              from: { element: { types: { anyOf: ["interface"] } } },
              disallow: { to: { element: { type: "api" } } },
            },
            {
              from: { element: { types: { anyOf: ["interface", "api-client"] } } },
              disallow: {
                to: {
                  module: {
                    origin: "external",
                    source: ["axios", "ky", "ofetch", "superagent", "@hey-api/*"],
                  },
                },
              },
            },
          ],
        },
      ],
    },
  },
  // --- El cliente de la API generado (C-28) -----------------------------------
  // Lo escribe `@hey-api/openapi-ts` y el chequeo de deriva lo compara byte a
  // byte: **nunca se edita a mano**, asi que su estilo es el del generador y no
  // el nuestro. Se apagan las reglas de typescript-eslint --las que miran tipos y
  // las de estilo que ese codigo no sigue--, y **las de seguridad siguen
  // activas**: un hallazgo de seguridad es compuerta dura tambien aqui.
  {
    files: ["src/shared/api/**"],
    ...tseslint.configs.disableTypeChecked,
  },
  {
    files: ["src/shared/api/**"],
    rules: {
      "@typescript-eslint/array-type": "off",
      "@typescript-eslint/consistent-indexed-object-style": "off",
      "@typescript-eslint/consistent-type-definitions": "off",
      "@typescript-eslint/no-dynamic-delete": "off",
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-inferrable-types": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
      // Una respuesta sin cuerpo se genera como `204: void`, y esa es la forma
      // correcta para el generador. La regla habla de tipos escritos a mano;
      // aqui lo unico que conseguiria es que ninguna ruta pudiera responder 204,
      // que es lo que C-08 pide para cerrar una llamada. Entro con U16, la
      // primera que tiene una.
      "@typescript-eslint/no-invalid-void-type": "off",
    },
  },
  // La unica regla de seguridad que se apaga, y solo en el cliente HTTP que el
  // generador empaqueta (`client/`, `core/`): `detect-object-injection` marca
  // todo acceso con corchetes y una clave variable. Sus 21 hallazgos se
  // revisaron uno por uno el 2026-09-21 (U6, paso 12): las claves salen de una
  // union cerrada (`parseAs`), de las opciones tipadas de nuestras propias
  // llamadas, o son indices numericos de los interceptores; ninguna viene de un
  // texto del visitante. El codigo esta fijado por la version exacta del
  // generador, asi que un cambio en el se ve en el diff del cliente regenerado y
  // se vuelve a revisar ahi. Lo generado desde **nuestro** esquema --tipos, SDK y
  // consultas-- conserva la regla.
  {
    files: ["src/shared/api/client/**", "src/shared/api/core/**"],
    rules: {
      "security/detect-object-injection": "off",
      // La marca `@ts-nocheck` de ese mismo cliente (ver `openapi-ts.config.ts`),
      // admitida solo con su descripcion escrita al lado.
      "@typescript-eslint/ban-ts-comment": ["error", { "ts-nocheck": "allow-with-description" }],
    },
  },
  // Los dos nodos de audio de la llamada (U16). Corren en el hilo de audio, que
  // es otro mundo: ahi no hay `window` ni `document`, y si estan `registerProcessor`
  // y la clase base que el navegador inyecta. Declararlos aparte es lo que impide
  // que un `document.querySelector` se cuele en un archivo donde no existe.
  {
    files: ["public/voice-*-worklet.js"],
    languageOptions: {
      globals: {
        registerProcessor: "readonly",
        AudioWorkletProcessor: "readonly",
        sampleRate: "readonly",
        currentTime: "readonly",
      },
    },
  },
  {
    files: ["**/*.test.ts", "**/*.test.tsx"],
    rules: {
      // Una prueba de tipos comprueba a proposito que una expresion NO compila.
      "@typescript-eslint/no-unsafe-assignment": "off",
    },
  },
  {
    files: [
      "eslint.config.ts",
      "vitest.config.ts",
      "vitest.setup.ts",
      "vite.config.ts",
      "openapi-ts.config.ts",
    ],
    ...tseslint.configs.disableTypeChecked,
  },
  // El paso de modo antes de pintar (CG-U6-1): JavaScript clasico, sin modulos ni
  // compilacion, porque el navegador lo ejecuta tal cual antes que la
  // aplicacion. No esta en el proyecto de TypeScript, asi que va sin reglas de
  // tipos; las de seguridad siguen activas.
  {
    files: ["public/**/*.js"],
    ...tseslint.configs.disableTypeChecked,
    languageOptions: {
      parserOptions: { project: false, projectService: false, program: null },
      sourceType: "script",
      globals: { window: "readonly", document: "readonly", console: "readonly" },
    },
  },
);
