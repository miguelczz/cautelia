import { describe, expect, expectTypeOf, it } from "vitest";

import { COPY_KEYS, LOCALES, type CopyKey, type Locale } from "./copy-keys";

// Lo que estas dos pruebas protegen es la mitad de la paridad que un chequeo de
// texto no puede hacer: que una clave inexistente sea un error **antes** de
// compilar, en vez de un texto vacio en pantalla.

describe("modulo tipado de claves del catalogo", () => {
  it("acepta una clave que existe y rechaza una que no, en tiempo de tipos", () => {
    const existente: CopyKey = "evals.scripted_insured.unknown_field";
    expect(COPY_KEYS).toContain(existente);

    // @ts-expect-error una clave que no esta en el catalogo no compila
    const inexistente: CopyKey = "evals.scripted_insured.no_existe";
    // La asercion en tiempo de ejecucion confirma que la comprobacion de arriba
    // es sobre el catalogo real y no sobre un tipo `string` disfrazado.
    expect(COPY_KEYS).not.toContain(inexistente);

    expectTypeOf<CopyKey>().not.toEqualTypeOf<string>();
  });

  it("declara los dos idiomas y solo esos", () => {
    expect([...LOCALES]).toEqual(["es", "en"]);
    expectTypeOf<Locale>().toEqualTypeOf<"es" | "en">();

    // @ts-expect-error el producto es bilingue por diseno: no hay un tercer idioma
    const otro: Locale = "pt";
    expect(LOCALES).not.toContain(otro);
  });
});
