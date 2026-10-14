import { describe, expect, it } from "vitest";

import siteExample from "../../../../contracts/examples/site-directory.json";
import { tenantAccentStyle } from "./tenant-accent";
import tokens from "./tokens.css?raw";

// BR1.6: el acento sale de la configuracion de cada aseguradora, sin ninguna
// condicion por aseguradora en el codigo.

describe("el acento de una aseguradora", () => {
  it("inyecta los dos valores de su marca tal como llegan de su configuracion", () => {
    for (const aseguradora of siteExample.tenants) {
      expect(tenantAccentStyle(aseguradora.brand)).toEqual({
        "--tenant-accent": aseguradora.brand.accent,
        "--tenant-accent-on-dark": aseguradora.brand.accent_on_dark,
      });
    }
  });

  it("sin marca no inyecta nada y queda el acento de Cautelia", () => {
    expect(tenantAccentStyle(null)).toBeUndefined();
    expect(tenantAccentStyle(undefined)).toBeUndefined();
  });
});

// La accion secundaria de una aseguradora ("Llamar") lleva su acento en el borde y
// en la letra, sobre el fondo de la pagina. Se mide con los valores de verdad --los
// de cada aseguradora y los del fondo de cada modo-- para que un acento nuevo que no
// se lea no llegue a la pantalla (BR7.6: 4,5:1 para texto).

type Rgb = readonly [number, number, number];

function rgb(hex: string): Rgb {
  const n = Number.parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function luminance([r, g, b]: Rgb): number {
  const lineal = (c: number) => {
    const v = c / 255;
    return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lineal(r) + 0.7152 * lineal(g) + 0.0722 * lineal(b);
}

function contrast(a: Rgb, b: Rgb): number {
  const [claro, oscuro] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (claro + 0.05) / (oscuro + 0.05);
}

function fondoDeLaPagina(modo: "light" | "dark"): string {
  const inicio = tokens.indexOf(`:root[data-theme="${modo}"] {`);
  const bloque = tokens.slice(inicio, tokens.indexOf("}", inicio));
  const valor = /--ut-page:\s*(#[0-9a-fA-F]{6})/.exec(bloque)?.[1];
  if (valor === undefined) {
    throw new Error(`tokens.css has no --ut-page for ${modo}`);
  }
  return valor;
}

/** Un 10 % del acento sobre el fondo: lo que se ve con el puntero encima. */
function conVelo(fondo: Rgb, acento: Rgb): Rgb {
  const mezcla = (f: number, a: number) => Math.round(f * 0.9 + a * 0.1);
  return [mezcla(fondo[0], acento[0]), mezcla(fondo[1], acento[1]), mezcla(fondo[2], acento[2])];
}

describe("el acento como texto y borde (boton secundario de una aseguradora)", () => {
  const casos = siteExample.tenants.flatMap((aseguradora) => [
    [aseguradora.display_name, "light", aseguradora.brand.accent] as const,
    [aseguradora.display_name, "dark", aseguradora.brand.accent_on_dark] as const,
  ]);

  it.each(casos)(
    "%s, modo %s: se lee sobre el fondo y tambien al pasar el puntero",
    (_, modo, acento) => {
      const fondo = rgb(fondoDeLaPagina(modo));
      const color = rgb(acento);
      // Con el puntero encima el fondo toma un 10 % del acento (`hover:bg-tenant/10`).
      const encima = conVelo(fondo, color);

      expect(contrast(color, fondo)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(color, encima)).toBeGreaterThanOrEqual(4.5);
    },
  );
});
