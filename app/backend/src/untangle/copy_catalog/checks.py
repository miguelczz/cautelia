"""Los seis chequeos del catalogo de textos (Flujo 3, BR3.1 a BR3.6).

Corren dentro del guion de verificacion, en cada entrega. Cada uno termina con
codigo distinto de cero **nombrando la clave o el archivo** culpable: un chequeo
que solo dice "fallo" obliga a buscar a mano lo que la herramienta ya sabia.

Los seis trabajan sobre las entradas **sin validar**. Si trabajaran sobre el
modelo, una entrada rota reventaria la carga con una traza antes de que el
chequeo llegara a decir que clave es la culpable -- y el mensaje util es
precisamente la clave.

Cada hallazgo lleva un identificador estable (`BR3.1`, `FF-2`, ...) para que se
lea igual en la consola, en el reporte por caso y en el diff contra la linea
base.
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from untangle import paths
from untangle.copy_catalog.loading import LOCALES
from untangle.copy_catalog.loading import load_raw_entries as load_raw_entries
from untangle.copy_catalog.models import COPY_KEY_PATTERN, CopyEntry

RawEntries = dict[tuple[str, str], dict[str, Any]]

# Donde se busca el consumidor literal de una clave (BR3.2) y donde se busca una
# clave construida en ejecucion (BR3.4).
EXTENSIONES_DE_CODIGO = (".py", ".ts", ".tsx")

# Los modulos que emiten texto hacia una persona. El chequeo de "nada en linea"
# se aplica aqui y no sobre todo el arbol, porque un mensaje de excepcion o el
# nombre de un evento tecnico los lee quien programa, no quien usa el producto
# (convencion 4 del equipo: tres registros de idioma, declarados una vez).
#
# Hoy casi todos estan vacios: llegan con las unidades que construyen cada
# pantalla y cada nodo. El chequeo esta en su sitio desde el primer commit para
# que la primera frase en linea falle, no para que se descubra despues.
#
# La interfaz de U6 se organiza por pantalla y por pieza compartida (`app/`,
# `pages/` y `shared/`), no por `modules/` como se previo en U1: se agregan sus
# directorios para que el chequeo la cubra de verdad. Se dejan fuera los modulos
# generados (el cliente de la API y las frases del catalogo): son el catalogo
# mismo, no texto escrito en linea.
SUPERFICIES_DE_SALIDA = (
    "app/backend/src/untangle/orchestration/nodes",
    "app/backend/src/untangle/chat",
    "app/backend/src/untangle/voice",
    "app/backend/src/untangle/inbox",
    "app/backend/src/untangle/compliance/controls",
    "app/frontend/src/modules",
    "app/frontend/src/app",
    "app/frontend/src/pages",
    "app/frontend/src/shared/ui",
    "app/frontend/src/shared/i18n",
    "app/frontend/src/shared/theme",
    "app/frontend/src/shared/api-client",
)

# La marca con la que empiezan los modulos que genera `mise run contracts:gen`
# desde el catalogo. Un modulo generado lista **todas** las claves, asi que
# contarlo como consumidor volveria el chequeo de claves sin consumidor una
# tautologia: cualquier clave muerta lo pasaria (hallazgo de U6, 2026-09-21).
MARCA_DE_GENERADO = "// GENERADO. No editar a mano."

# Una cadena se considera visible cuando tiene al menos cuatro palabras y termina
# como termina una frase. Es una heuristica, y por eso existe la lista de
# excepciones versionada en lugar de una regla mas retorcida.
#
# La expresion recorre los literales **completos**, de izquierda a derecha: cada
# coincidencia empieza en una comilla que abre y termina en la misma comilla que
# cierra. La version anterior podia empezar en la comilla que **cierra** un
# literal corto y tomar como cadena el codigo hasta el siguiente --en
# `startsWith("es") === true ? "es"` veia la "frase" `) === true ? `--; aparecio
# al cubrir el TypeScript de la interfaz (U6), donde dos literales por linea son
# comunes. La longitud minima se exige despues, sobre el literal ya aislado.
CADENA_ENTRECOMILLADA = re.compile(r"""(['"])((?:\\.|(?!\1)[^\\\n])*)\1""")
LONGITUD_MINIMA_DE_CADENA = 12
FIN_DE_FRASE = re.compile(r"[.!?:]\s*$")

# El lookbehind descarta la definicion de la funcion; el filtro de ruta descarta
# el propio resolvedor, que es el unico lugar donde recibir la clave como
# parametro es lo correcto, porque es quien la resuelve.
LLAMADA_CON_NOMBRE = re.compile(r"""(?<!def )\bt\(\s*(?!['"]|CopyKey\(\s*['"])([A-Za-z_]\w*)""")

# Una constante del modulo ligada a una clave literal conserva la propiedad que
# esta regla protege: la clave se puede encontrar con un grep. Lo que la regla
# persigue es la clave armada en ejecucion a partir de un valor calculado.
# La plantilla de TypeScript es la otra forma de armar una clave en ejecucion:
# `t(`estado.${valor}`)` no empieza por un nombre y la expresion de arriba no la
# ve. Se busca aparte (U6).
LLAMADA_CON_PLANTILLA = re.compile(r"\bt\(\s*`[^`]*\$\{")

CONSTANTE_DE_CLAVE = re.compile(
    r"""^([A-Z][A-Z0-9_]*)\s*(?::[^=]+)?=\s*"""
    r"""(?:(?:[A-Za-z_]\w*\.)?CopyKey\(\s*)?['"][a-z][a-z0-9_.]*['"]""",
    re.MULTILINE,
)


@dataclass(frozen=True)
class Finding:
    """Un hallazgo: su regla, donde esta y que hay que arreglar."""

    rule: str
    where: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.rule}] {self.where}: {self.detail}"


def _code_files(root: Path) -> tuple[Path, ...]:
    """Los archivos de codigo del aplicativo, ordenados explicitamente."""
    encontrados: list[Path] = []
    for prefijo in ("app/backend/src", "app/frontend/src"):
        base = root / prefijo
        if not base.is_dir():
            continue
        encontrados.extend(
            archivo
            for archivo in base.rglob("*")
            if archivo.suffix in EXTENSIONES_DE_CODIGO and archivo.is_file()
        )
    return tuple(sorted(encontrados, key=lambda p: p.as_posix()))


def _is_generated(contenido: str) -> bool:
    """Un modulo generado desde el catalogo: no es consumidor de ninguna clave."""
    return contenido.startswith(MARCA_DE_GENERADO)


def tenant_character_keys(root: Path) -> dict[str, str]:
    """La clave del caracter que declara cada aseguradora, por carpeta (U6).

    Se lee el YAML **sin validar**, como el resto de los chequeos: una carpeta
    rota no tiene que impedir que el chequeo diga que clave falta. Lo que no es
    un texto se ignora aqui; el esquema de la aseguradora es quien lo rechaza.
    """
    directorio = root / "app" / "config" / "tenants"
    if not directorio.is_dir():
        return {}
    claves: dict[str, str] = {}
    for archivo in sorted(directorio.glob("*/tenant.yaml")):
        try:
            cargado: Any = yaml.safe_load(archivo.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if isinstance(cargado, dict) and isinstance(cargado.get("character_key"), str):
            claves[archivo.parent.name] = cargado["character_key"]
    return claves


def tenant_rule_explanation_keys(root: Path) -> dict[str, list[str]]:
    """La `then.explanation_key` de cada regla de cada aseguradora (U9, BR2.5).

    Se lee el YAML **sin validar**, como el resto de los chequeos: un archivo de
    reglas roto no tiene que impedir que el chequeo diga que clave falta. Una
    clave puede repetirse entre reglas o entre aseguradoras (varias reglas
    comparten la misma explicacion), por eso el valor es una lista de archivos.
    """
    directorio = root / "app" / "config" / "tenants"
    if not directorio.is_dir():
        return {}
    claves: dict[str, list[str]] = {}
    for archivo in sorted(directorio.glob("*/rules/*.yaml")):
        try:
            cargado: Any = yaml.safe_load(archivo.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(cargado, dict):
            continue
        for regla in cargado.get("rules") or []:
            if not isinstance(regla, dict):
                continue
            then = regla.get("then")
            if isinstance(then, dict) and isinstance(then.get("explanation_key"), str):
                claves.setdefault(then["explanation_key"], []).append(
                    archivo.relative_to(root).as_posix()
                )
    return claves


def _keys(entries: RawEntries) -> list[str]:
    return sorted({clave for clave, _ in entries})


def check_parity(entries: RawEntries) -> list[Finding]:
    """BR3.1 - Toda clave existe en espanol y en ingles."""
    por_clave: dict[str, set[str]] = {}
    for clave, locale in entries:
        por_clave.setdefault(clave, set()).add(locale)

    hallazgos: list[Finding] = []
    for clave in sorted(por_clave):
        faltan = sorted(set(LOCALES) - por_clave[clave])
        if faltan:
            hallazgos.append(
                Finding(
                    "BR3.1",
                    clave,
                    f"falta en {', '.join(faltan)}; una clave sin pareja deja una "
                    "frase vacia o en el idioma equivocado frente a una persona",
                )
            )
    return hallazgos


def check_consumers(entries: RawEntries, root: Path) -> list[Finding]:
    """BR3.2 - Toda clave aparece literalmente al menos una vez en el codigo.

    Tres precisiones de U6 y U9. Los modulos generados desde el catalogo no
    cuentan como consumidores, porque listan todas las claves. La clave del
    caracter que declara una aseguradora en su `tenant.yaml` **si** cuenta: la
    consume esa configuracion, que es donde vive la diferencia entre
    aseguradoras (convencion 9). Y la `then.explanation_key` de una regla de
    `rules/triage.yaml` tambien cuenta, por la misma razon: la consume esa
    regla, no una linea de codigo (BR2.4). En los tres casos, declarar una clave
    que no existe en el catalogo es igual de un hallazgo: la fila o la
    explicacion se dibujarian vacias en silencio.
    """
    textos = [
        contenido
        for archivo in _code_files(root)
        if not _is_generated(contenido := archivo.read_text(encoding="utf-8"))
    ]
    de_aseguradoras = tenant_character_keys(root)
    de_reglas = tenant_rule_explanation_keys(root)
    declaradas = set(de_aseguradoras.values()) | set(de_reglas)
    claves = set(_keys(entries))

    hallazgos = [
        Finding(
            "BR3.2",
            clave,
            "no tiene consumidor literal en el codigo; un catalogo que acumula "
            "claves muertas es el fallo que ya muestra la landing",
        )
        for clave in sorted(claves)
        if clave not in declaradas and not any(clave in contenido for contenido in textos)
    ]
    hallazgos.extend(
        Finding(
            "BR3.2",
            f"app/config/tenants/{carpeta}/tenant.yaml",
            f"declara character_key '{clave}', que no existe en el catalogo; la "
            "fila de la aseguradora se dibujaria sin su caracter",
        )
        for carpeta, clave in sorted(de_aseguradoras.items())
        if clave not in claves
    )
    hallazgos.extend(
        Finding(
            "BR3.2",
            archivo,
            f"declara 'then.explanation_key' como '{clave}', que no existe en el "
            "catalogo; la explicacion de esa regla se veria vacia",
        )
        for clave, archivos in sorted(de_reglas.items())
        if clave not in claves
        for archivo in archivos
    )
    return hallazgos


def _allowlist(root: Path) -> dict[str, str]:
    """Excepciones versionadas del chequeo de cadenas en linea, con su razon."""
    archivo = root / "app" / "config" / "copy" / "inline-allowlist.yaml"
    if not archivo.is_file():
        return {}
    cargado: Any = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    if not isinstance(cargado, dict):
        return {}
    entradas = cargado.get("allowed") or []
    if not isinstance(entradas, list):
        return {}
    return {
        str(entrada["text"]): str(entrada["reason"])
        for entrada in entradas
        if isinstance(entrada, dict) and "text" in entrada and "reason" in entrada
    }


def _es_frase_visible(texto: str) -> bool:
    """Un literal que parece una frase para una persona: largo, con palabras y cierre."""
    return (
        len(texto) >= LONGITUD_MINIMA_DE_CADENA
        and len(texto.split()) >= 4
        and FIN_DE_FRASE.search(texto) is not None
    )


def _es_archivo_de_prueba(archivo: Path) -> bool:
    """Una prueba no dibuja nada para nadie.

    El alcance de este chequeo es **lo que se publica**, y una prueba no se
    publica: su texto no llega a ninguna pantalla y no hay idioma que mantener
    en paridad. Lo que si necesita una prueba es escribir la frase que espera
    ver, y obligarla a sacarla del catalogo la haria comprobar que el catalogo
    coincide consigo mismo. Se excluye por la forma del nombre y no por una
    lista de archivos, que es lo que crece.
    """
    nombre = archivo.name
    return nombre.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")) or nombre.startswith(
        "test_"
    )


def _lineas_de_docstring(contenido: str, archivo: Path) -> frozenset[int]:
    """Las lineas que caen dentro de un docstring de Python.

    **Un docstring no se le muestra a nadie.** El chequeo miraba linea a linea y
    saltaba la que abre el bloque, que es la primera y solo la primera: la prosa
    de las lineas siguientes se leia como codigo. Asi que explicar una regla con la
    frase que la motiva --"«¿me lo dice in English?» esta dicho en espanol"-- se
    denunciaba como una cadena visible escrita en linea, y la unica salida era
    escribir mas vago.

    Se resuelve con el arbol y no con mas heuristica de lineas: `ast` dice
    exactamente donde empieza y acaba cada docstring. Un archivo que no se puede
    parsear --o que no es Python-- devuelve nada y el chequeo se comporta como
    antes: peor es preferible a ciego.

    Lo que **no** se salta es una cadena larga asignada a una variable: eso no es un
    docstring y `ast` no lo devuelve como tal.
    """
    if archivo.suffix != ".py":
        return frozenset()
    try:
        arbol = ast.parse(contenido)
    except SyntaxError:
        return frozenset()
    lineas: set[int] = set()
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        cuerpo = nodo.body
        if not cuerpo or not isinstance(cuerpo[0], ast.Expr):
            continue
        valor = cuerpo[0].value
        if not isinstance(valor, ast.Constant) or not isinstance(valor.value, str):
            continue
        fin = valor.end_lineno if valor.end_lineno is not None else valor.lineno
        lineas.update(range(valor.lineno, fin + 1))
    return frozenset(lineas)


def _frases_en_linea(archivo: Path, root: Path, permitidas: dict[str, str]) -> list[Finding]:
    """Las frases escritas en linea de un archivo, salvo las excepciones versionadas."""
    if _es_archivo_de_prueba(archivo):
        return []
    contenido = archivo.read_text(encoding="utf-8")
    if _is_generated(contenido):
        return []
    en_docstring = _lineas_de_docstring(contenido, archivo)
    hallazgos: list[Finding] = []
    for numero, linea in enumerate(contenido.splitlines(), start=1):
        if numero in en_docstring:
            continue
        if linea.strip().startswith(("#", "//", '"""', "*")):
            continue
        for coincidencia in CADENA_ENTRECOMILLADA.finditer(linea):
            texto = coincidencia.group(2)
            if texto in permitidas or not _es_frase_visible(texto):
                continue
            hallazgos.append(
                Finding(
                    "BR3.3",
                    f"{archivo.relative_to(root).as_posix()}:{numero}",
                    f"cadena visible escrita en linea: {texto!r}; toda frase "
                    "que lee una persona sale del catalogo por idioma",
                )
            )
    return hallazgos


def check_no_inline_copy(root: Path) -> list[Finding]:
    """BR3.3 - Ningun texto visible para una persona se escribe en linea."""
    permitidas = _allowlist(root)
    hallazgos: list[Finding] = []

    for prefijo in SUPERFICIES_DE_SALIDA:
        base = root / prefijo
        if not base.is_dir():
            continue
        archivos = sorted(
            (a for a in base.rglob("*") if a.suffix in EXTENSIONES_DE_CODIGO and a.is_file()),
            key=lambda p: p.as_posix(),
        )
        for archivo in archivos:
            hallazgos.extend(_frases_en_linea(archivo, root, permitidas))
    return hallazgos


def check_literal_keys(entries: RawEntries, root: Path) -> list[Finding]:
    """BR3.4 - Las claves son jerarquicas con puntos y nunca se concatenan.

    Dos cosas distintas: que la clave tenga la forma declarada, y que en el
    codigo no se arme una clave a partir de un valor calculado.
    """
    hallazgos: list[Finding] = [
        Finding("BR3.4", clave, "no es jerarquica con puntos y en minusculas")
        for clave in _keys(entries)
        if not COPY_KEY_PATTERN.match(clave)
    ]

    for archivo in _code_files(root):
        if "copy_catalog" in archivo.parts:
            continue
        contenido = archivo.read_text(encoding="utf-8")
        constantes = {m.group(1) for m in CONSTANTE_DE_CLAVE.finditer(contenido)}
        for numero, linea in enumerate(contenido.splitlines(), start=1):
            coincidencia = LLAMADA_CON_NOMBRE.search(linea)
            armada = coincidencia is not None and coincidencia.group(1) not in constantes
            if armada or LLAMADA_CON_PLANTILLA.search(linea):
                hallazgos.append(
                    Finding(
                        "BR3.4",
                        f"{archivo.relative_to(root).as_posix()}:{numero}",
                        "la clave no es un literal; una clave construida en "
                        "ejecucion hace inexacto el chequeo de claves sin consumidor",
                    )
                )
    return hallazgos


def check_version_decisions(entries: RawEntries) -> list[Finding]:
    """BR3.5 - Una version mayor que uno declara la decision que la cambio."""
    hallazgos: list[Finding] = []
    for (clave, locale), entrada in sorted(entries.items()):
        version = entrada.get("version", 1)
        if isinstance(version, int) and version > 1 and not entrada.get("decision"):
            hallazgos.append(
                Finding(
                    "BR3.5",
                    f"{clave} ({locale})",
                    f"version {version} sin identificador de decision; una frase "
                    "cambiada sin su razon deja la guia de voz y el producto "
                    "contandose historias distintas",
                )
            )
    return hallazgos


def load_forbidden_forms(root: Path | None = None) -> tuple[tuple[str, str, re.Pattern[str]], ...]:
    """La lista versionada de formas prohibidas, compilada."""
    base = root if root is not None else paths.repo_root()
    archivo = base / "app" / "config" / "copy" / "forbidden-forms.yaml"
    if not archivo.is_file():
        msg = f"falta la lista versionada de formas prohibidas: se esperaba '{archivo}'"
        raise FileNotFoundError(msg)

    cargado: Any = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    formas: list[tuple[str, str, re.Pattern[str]]] = []
    for forma in cargado.get("forms", []):
        for patron in forma["patterns"]:
            formas.append((str(forma["id"]), str(forma["reason"]).strip(), re.compile(patron)))
    return tuple(formas)


def check_forbidden_forms(entries: RawEntries, root: Path | None = None) -> list[Finding]:
    """BR3.6 - Ninguna frase contiene una forma de la lista versionada."""
    formas = load_forbidden_forms(root)
    hallazgos: list[Finding] = []
    for (clave, locale), entrada in sorted(entries.items()):
        texto = str(entrada.get("text", ""))
        for identificador, razon, patron in formas:
            if patron.search(texto):
                hallazgos.append(
                    Finding(
                        "BR3.6",
                        f"{clave} ({locale})",
                        f"coincide con la forma prohibida {identificador}: {razon.splitlines()[0]}",
                    )
                )
    return hallazgos


def check_schema(entries: RawEntries) -> list[Finding]:
    """Cada entrada valida el esquema que el cargador exige.

    Hacia falta: los otros chequeos leen el YAML crudo, asi que un `surface`
    fuera del conjunto cerrado los pasaba todos y hacia fallar el aplicativo al
    arrancar. Un comprobador que aprueba un catalogo que no carga es peor que no
    tenerlo, porque el fallo aparece lejos de su causa --en la redaccion, que
    falla cerrado y deja de emitir texto-- y ahi no dice de donde viene.

    Detectado construyendo U4, anadiendo las etiquetas del caso con
    `surface: staff`, que no existe.
    """
    hallazgos: list[Finding] = []
    for (clave, idioma), crudo in sorted(entries.items()):
        try:
            CopyEntry.model_validate({**crudo, "key": clave, "locale": idioma})
        except ValidationError as error:
            primero = error.errors()[0]
            campo = ".".join(str(parte) for parte in primero["loc"]) or "la entrada"
            hallazgos.append(
                Finding(
                    "BR3.1",
                    f"{clave} ({idioma})",
                    f"no valida el esquema del catalogo en `{campo}`: "
                    f"{primero['msg']}. El aplicativo no arrancaria con este archivo",
                )
            )
    return hallazgos


def run_all(root: Path | None = None) -> list[Finding]:
    """Los siete chequeos, en el orden del Flujo 3."""
    base = root if root is not None else paths.repo_root()
    entradas = load_raw_entries(base / "app" / "config" / "copy")

    return [
        *check_schema(entradas),
        *check_parity(entradas),
        *check_consumers(entradas, base),
        *check_no_inline_copy(base),
        *check_literal_keys(entradas, base),
        *check_version_decisions(entradas),
        *check_forbidden_forms(entradas, base),
    ]


def main() -> int:
    hallazgos = run_all()
    for hallazgo in hallazgos:
        print(str(hallazgo), file=sys.stderr)
    if hallazgos:
        print(f"\n{len(hallazgos)} hallazgo(s) en el catalogo de textos", file=sys.stderr)
        return 1
    print("catalogo de textos: los siete chequeos pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())
