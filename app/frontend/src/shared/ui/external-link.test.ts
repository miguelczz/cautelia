import { describe, expect, it } from "vitest";

import { isSafeExternalLink } from "./external-link";

// Lo ultimo antes de un `href` que abre otra pestana: solo `https`, sin espacios.

describe("isSafeExternalLink", () => {
  it("deja pasar una direccion https", () => {
    expect(isSafeExternalLink("https://us.cloud.langfuse.com/project/p/traces/t")).toBe(true);
  });

  it.each([
    null,
    undefined,
    "",
    "https://",
    "http://us.cloud.langfuse.com/project/p/traces/t",
    "//us.cloud.langfuse.com/project/p/traces/t",
    "javascript:alert(1)",
    "data:text/html,hola",
    "https://con espacio/x",
    "https://con\nsalto/x",
    "/project/p/traces/t",
  ])("no deja pasar %s", (direccion) => {
    expect(isSafeExternalLink(direccion)).toBe(false);
  });
});
