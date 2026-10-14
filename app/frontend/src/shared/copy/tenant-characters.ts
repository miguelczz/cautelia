// GENERADO. No editar a mano.
//
// El caracter de cada aseguradora, tal como lo declara su configuracion
// (`character_key` en `app/config/tenants/<aseguradora>/tenant.yaml`). Sale con
// `mise run contracts:gen` y el chequeo de deriva lo compara.
//
// Por que existe: la clave del caracter llega a la interfaz como **dato** del
// directorio del sitio, no escrita en el codigo. Pasarsela a `t` en una
// variable es justo lo que prohibe el chequeo de claves literales (BR3.4), y
// con razon: una clave que viaja como dato no se encuentra con un grep. Esta
// tabla cierra el conjunto: cada clave que declara una aseguradora aparece aqui
// **literal**, resuelta por `t("...")`, y una clave que no esta en la tabla no
// se dibuja (BR4.2). Anadir una aseguradora sigue siendo anadir su carpeta y
// regenerar; el codigo de la interfaz no cambia.

import type { CopyKey } from "./copy-keys";

/** Resolver una clave literal del catalogo: la forma de `t` que usa esta tabla. */
export type ResolveCopy = (key: CopyKey) => string;

/** El caracter de cada clave declarada por alguna aseguradora. */
export const TENANT_CHARACTERS: ReadonlyMap<string, (t: ResolveCopy) => string> = new Map<
  string,
  (t: ResolveCopy) => string
>([
  ["insurer.character.agency", (t) => t("insurer.character.agency")],
  ["insurer.character.conservative", (t) => t("insurer.character.conservative")],
  ["insurer.character.flexible", (t) => t("insurer.character.flexible")],
]);
