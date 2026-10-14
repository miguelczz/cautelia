"""Genera los modulos del catalogo que consume la interfaz (C-28).

Tres modulos de TypeScript, los tres versionados y cubiertos por el chequeo de
deriva: si el catalogo o una aseguradora cambian y el modulo no se regenera en
el mismo commit, la compuerta falla.

- **Las claves** (`copy-keys.ts`, U1): una clave que no existe deja de ser un
  texto vacio en pantalla y pasa a ser un **error de tipos antes de compilar**.
  Es la mitad de la comprobacion de paridad que un chequeo de texto no puede
  hacer.
- **Las frases** (`copy-texts.<idioma>.ts`, U6): el texto de cada clave en cada idioma,
  para que la interfaz resuelva sin preguntar al servidor.
- **El caracter de las aseguradoras** (`tenant-characters.ts`, U6): la tabla
  cerrada de las claves que las aseguradoras declaran en su configuracion.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from untangle.copy_catalog.models import CopyEntry

ENCABEZADO = """\
// GENERADO. No editar a mano.
//
// Sale del catalogo de textos (`app/config/copy/`) con el comando
// `mise run contracts:gen`. El guion de verificacion lo regenera y compara: si
// el catalogo cambio y este archivo no, la compuerta falla con su nombre.
//
// Una clave que no existe es un error de tipos aqui, no un texto vacio en
// pantalla.
"""


def render_keys_module(entries: Mapping[tuple[str, str], CopyEntry]) -> str:
    """El contenido del modulo de TypeScript, determinista."""
    claves = sorted({clave for clave, _ in entries})
    superficies = sorted({entrada.surface.value for entrada in entries.values()})

    if claves:
        union = "\n".join(f'  | "{clave}"' for clave in claves)
        lista = "\n".join(f'  "{clave}",' for clave in claves) + "\n"
    else:
        union = "  never"
        lista = ""

    union_superficies = " | ".join(f'"{s}"' for s in superficies) if superficies else "never"

    return f"""{ENCABEZADO}
/** Toda clave del catalogo, en los dos idiomas. */
export type CopyKey =
{union};

/** Los idiomas admitidos por el producto. */
export type Locale = "es" | "en";

/** Donde se muestra una frase. */
export type Surface = {union_superficies};

/** Las claves, para recorrerlas en tiempo de ejecucion. */
export const COPY_KEYS = [
{lista}] as const satisfies readonly CopyKey[];

export const LOCALES = ["es", "en"] as const satisfies readonly Locale[];
"""


ENCABEZADO_FRASES = """\
// GENERADO. No editar a mano.
//
// Las frases del catalogo de textos (`app/config/copy/`), por idioma, para que
// la interfaz las resuelva sin pedirlas al servidor. Sale con
// `mise run contracts:gen` y el chequeo de deriva lo compara: si el catalogo
// cambio y este archivo no, la compuerta falla con su nombre.
//
// Son mapas y no objetos: la interfaz busca por una clave tipada, y un mapa no
// convierte una clave cualquiera en una propiedad del objeto.
"""


#: Cuantas frases lleva cada tramo del modulo generado. **No es un detalle de estilo.**
#: Un solo literal con mas de mil frases hace que TypeScript tenga que reducir una union de
#: mas de mil tuplas distintas --la clave de cada una es un literal--, y se rinde con el
#: error 2590 («la union es demasiado compleja»): el catalogo estaba en 994 claves y la
#: 1.001 rompia `tsc` en los dos modulos de idioma, sin que nada tocara el codigo que los
#: lee. Con cada tramo declarado con su tipo, el literal que TypeScript reduce es el del
#: tramo y no el del catalogo entero, y el catalogo puede crecer sin volver a toparse.
FRASES_POR_TRAMO = 250

ENCABEZADO_TRAMOS = """\
// Las frases van en tramos, cada uno con su tipo declarado: ver `FRASES_POR_TRAMO` en
// `keys_module.py`. Un solo literal de mas de mil tuplas rompe el compilador (TS2590).
"""


def render_texts_module(entries: Mapping[tuple[str, str], CopyEntry], locale: str) -> str:
    """Las frases de **un** idioma como modulo de TypeScript, determinista.

    Un modulo por idioma (2026-10-09): el catalogo es lo mas pesado de lo que se
    descarga antes de la pagina de espera (PERF-U6.1), y con los dos idiomas juntos
    la pasaba. La interfaz carga el del arranque antes de pintar y el otro despues
    (`shared/i18n/catalog.ts`). Una clave que le falta a este idioma simplemente no
    va: el chequeo de paridad (BR3.1) es quien lo dice, nombrando la clave.
    """
    frases = sorted(
        (entrada.key, entrada.text) for (_, idioma), entrada in entries.items() if idioma == locale
    )
    tramos = [
        frases[desde : desde + FRASES_POR_TRAMO]
        for desde in range(0, len(frases), FRASES_POR_TRAMO)
    ] or [[]]
    declaraciones = "".join(
        f"const TRAMO_{indice}: readonly (readonly [CopyKey, string])[] = [\n"
        + "".join(
            f"  [{json.dumps(clave)}, {json.dumps(texto, ensure_ascii=False)}],\n"
            for clave, texto in tramo
        )
        + "];\n\n"
        for indice, tramo in enumerate(tramos)
    )
    union = ", ".join(f"...TRAMO_{indice}" for indice in range(len(tramos)))
    return f"""{ENCABEZADO_FRASES}
import type {{ CopyKey }} from "./copy-keys";

{ENCABEZADO_TRAMOS}
{declaraciones}/** La frase de cada clave en `{locale}`. */
const FRASES: ReadonlyMap<CopyKey, string> = new Map<CopyKey, string>([{union}]);

export default FRASES;
"""


ENCABEZADO_CARACTERES = """\
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
"""


def render_characters_module(character_keys: Sequence[str]) -> str:
    """La tabla cerrada de caracteres de aseguradora, determinista."""
    claves = sorted(set(character_keys))
    filas = "".join(
        f"  [{json.dumps(clave)}, (t) => t({json.dumps(clave)})],\n" for clave in claves
    )
    return f"""{ENCABEZADO_CARACTERES}
import type {{ CopyKey }} from "./copy-keys";

/** Resolver una clave literal del catalogo: la forma de `t` que usa esta tabla. */
export type ResolveCopy = (key: CopyKey) => string;

/** El caracter de cada clave declarada por alguna aseguradora. */
export const TENANT_CHARACTERS: ReadonlyMap<string, (t: ResolveCopy) => string> = new Map<
  string,
  (t: ResolveCopy) => string
>([
{filas}]);
"""
