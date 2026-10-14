import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

// El alcance esta declarado al prefijo del aplicativo, no como lista de
// exclusiones (convencion 1 del equipo). La cobertura sale en el mismo formato
// comun que la de Python para que el comando agregado pueda sumarlas
// ponderando por lineas (NFR18.1).
//
// El entorno es `jsdom` desde U6: las pruebas de componentes necesitan un
// documento, y las que no lo usan --el modulo tipado de claves-- corren igual en
// el. Un entorno por archivo seria una segunda configuracion que mantener.
export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    setupFiles: ["./vitest.setup.ts"],
    // Las hojas de estilos se leen como texto en la prueba de los tokens
    // (BR1.5): sin esto, Vitest devuelve una hoja vacia y la prueba no veria
    // ningun color.
    css: { include: [/\.css/] },
    // **Un techo de trabajadores, para no encender la maquina entera de golpe.**
    // Sin esto Vitest abre un proceso por nucleo y los 31 archivos gastan 37 s de
    // CPU en 6,6 s de reloj --737 % de uso--, que en un portatil es el ventilador
    // arrancando para una suite que dura lo que un parpadeo. Medido aqui: con dos
    // trabajadores son 24 s de CPU al 247 % en 11,7 s. Cinco segundos mas de reloj
    // a cambio de un tercio del pico.
    //
    // En la tuberia no se toca: alli la maquina es de un solo uso y lo que importa
    // es que termine pronto.
    ...(process.env.CI === undefined ? { maxWorkers: 2, minWorkers: 1 } : {}),
    coverage: {
      provider: "v8",
      reporter: ["text", "cobertura"],
      reportsDirectory: "coverage",
      // El codigo nuevo de U6 --el cliente generado de la API incluido-- entra
      // al calculo sin exclusiones nuevas (NFR18.4): excluirlo agrandaria una
      // lista que existe para lo que no es codigo del aplicativo.
      include: ["src/**/*.ts", "src/**/*.tsx"],
      exclude: ["src/**/*.test.ts", "src/**/*.test.tsx"],
      // El piso del 80 % se comprueba sobre el agregado de los dos proyectos,
      // no por proyecto: la interfaz puede quedar por debajo mientras el
      // agregado se cumpla (team.md, Piso de cobertura).
    },
  },
});
