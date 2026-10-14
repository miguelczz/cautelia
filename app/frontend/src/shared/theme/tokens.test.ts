import { describe, expect, it } from "vitest";

import tokens from "./tokens.css?raw";

// BR1.5: todo color sale de los tokens, y el cobre de la marca nunca es texto en
// el modo claro. Es un chequeo de texto sobre el propio codigo --"comprobable por
// un grep", como exige team.md para toda convencion afirmada--.

const FUENTES = import.meta.glob<string>(["../../**/*.{ts,tsx,css}", "!../../**/*.test.{ts,tsx}"], {
  query: "?raw",
  import: "default",
  eager: true,
});

const COLOR_LITERAL = /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(|\boklch\(/;

function bloque(selector: string): string {
  const inicio = tokens.indexOf(`${selector} {`);
  expect(inicio).toBeGreaterThanOrEqual(0);
  return tokens.slice(inicio, tokens.indexOf("}", inicio));
}

describe("los tokens del sistema de diseno", () => {
  it("ningun archivo fuera de tokens.css escribe un color literal", () => {
    const culpables = Object.entries(FUENTES)
      .filter(([ruta]) => ruta !== "./tokens.css")
      .filter(([, contenido]) => COLOR_LITERAL.test(contenido))
      .map(([ruta]) => ruta);

    expect(culpables).toEqual([]);
    // El recorrido ve de verdad el arbol: sin archivos, la lista vacia de
    // arriba no probaria nada.
    expect(Object.keys(FUENTES).length).toBeGreaterThan(20);
  });

  it("el cobre solo existe en el modo oscuro; en claro la marca es la tinta", () => {
    expect(bloque(':root[data-theme="dark"]')).toContain("--ut-brand: #e0873a;");
    expect(bloque(':root[data-theme="light"]').toLowerCase()).not.toContain("#e0873a");
    expect(bloque(':root[data-theme="light"]')).toContain("--ut-brand: #9a4f12;");
  });

  it("los dos modos definen los mismos tokens", () => {
    const nombres = (texto: string) =>
      [...texto.matchAll(/--ut-[a-z-]+(?=:)/g)].map((m) => m[0]).sort();

    expect(nombres(bloque(':root[data-theme="light"]'))).toEqual(
      nombres(bloque(':root[data-theme="dark"]')),
    );
  });
});
