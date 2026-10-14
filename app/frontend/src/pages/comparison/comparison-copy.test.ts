import { describe, expect, it } from "vitest";

// BR1.3: ninguna cadena visible escrita en el componente. El chequeo del catalogo
// (`copy:check`) ve los literales entre comillas pero **no el texto suelto dentro
// de JSX** (`<p>Una frase.</p>`), que es justo como se escribe una frase en linea
// por descuido. Esta prueba cierra ese hueco para esta pantalla.
const FUENTES = import.meta.glob<string>(["./*.tsx", "!./*.test.tsx"], {
  query: "?raw",
  import: "default",
  eager: true,
});

// Texto entre una etiqueta que cierra y otra que abre, con letras y sin llaves.
const TEXTO_SUELTO = />\s*([^<>{}\n]*\p{L}[^<>{}\n]*)\s*</gu;

describe("el texto de la vista sale del catalogo (BR1.3)", () => {
  it("revisa los archivos de la pantalla", () => {
    expect(Object.keys(FUENTES).sort()).toEqual([
      "./comparison-column.tsx",
      "./comparison-page.tsx",
      "./comparison-routes.tsx",
    ]);
  });

  it("ningun archivo de la pantalla escribe texto suelto dentro de JSX", () => {
    for (const [archivo, fuente] of Object.entries(FUENTES)) {
      // Se quitan los comentarios: hablan de la pantalla y no se ven en ella.
      const sinComentarios = fuente.replace(/\{\/\*[\s\S]*?\*\/\}/g, "").replace(/\/\/.*$/gm, "");
      const sueltos = [...sinComentarios.matchAll(TEXTO_SUELTO)].map((m) => m[1]?.trim());
      expect(sueltos, `${archivo}: texto visible escrito en linea`).toEqual([]);
    }
  });

  it("el detector ve el texto suelto que busca", () => {
    const roto = "<p>Una frase escrita en linea.</p>";
    expect([...roto.matchAll(TEXTO_SUELTO)]).toHaveLength(1);
  });
});
