"""Chequeos de contenido sobre lo que se publica.

Dos chequeos independientes del lenguaje, porque protegen principios y no estilo:

1. **Frases prohibidas**: afirmar que algo "cumple con" NAIC, TCPA, EU AI Act,
   SOC 2 o HIPAA. El proyecto dice "inspirado en" (P6, R9). Una afirmacion de
   cumplimiento que nadie audito es una promesa que la demostracion no sostiene.
2. **ISO y ACORD**: el chequeo distingue **estructura** -- nombres de seccion y
   numeracion, permitidos y documentados en
   `docs/reference/estructura-poliza-iso-pap.md` -- de **texto de clausula**, que
   es lo prohibido (P8, W6). Tiene dos mitades: los marcadores, que buscan
   arranques de prosa de formulario en todo lo que se publica, y las **huellas**
   (U7, BR5.2), que buscan el calco entero en cada clausula del corpus: ninguna
   puede compartir una sola secuencia de ocho palabras con los formularios de
   terceros. Sin archivo de huellas, esa mitad no se omite: se declara "no
   medido" y falla (BR5.3).

Viven en `evals` y no en `workspace` porque son casos de evaluacion: la practica
del equipo pide que aparezcan "en el reporte por caso y en el diff contra la
linea base como cualquier otra prueba". Ponerlos en el paquete de herramientas
habria hecho que `evals` lo importara, y dos modulos hermanos habrian formado un
ciclo que el contrato `acyclic_siblings` rechaza.

**El alcance importa tanto como el patron.** Se aplican sobre lo que se publica:
codigo del aplicativo, `README.md`, copy del producto y `site/`. La
especificacion y los artefactos del flujo contienen esas frases precisamente
porque las prohiben, y quedan fuera por una lista de exclusiones versionada donde
cada entrada lleva su razon. Sin ese alcance los dos chequeos arrancarian en rojo
el primer dia: hoy el de frases prohibidas coincide con cinco archivos legitimos
--incluido el PRD que define la prohibicion-- y el de ISO/ACORD con diecisiete.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from untangle import paths
from untangle.base import Locale
from untangle.evals.models import Dataset
from untangle.evals.runner.api import CheckOutcome, EvalTarget, register_check, register_targets
from untangle.text_fingerprints import FingerprintSettings, SettingsError
from untangle.text_fingerprints import load_settings as load_fingerprint_settings

EXTENSIONES = (".py", ".ts", ".tsx", ".md", ".yaml", ".yml", ".json", ".html", ".css", ".txt")


@dataclass(frozen=True)
class ContentFinding:
    """Un hallazgo de contenido: su regla, donde esta y que hay que arreglar."""

    rule: str
    where: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.rule}] {self.where}: {self.detail}"


@dataclass(frozen=True)
class SpanishRegister:
    """El alcance y los patrones del registro en espanol (U18, BR5.4).

    Su alcance es **el catalogo y no los archivos publicados**: lo que se mira son
    las frases que la agente dice, que en el catalogo son las de `surface: voice`.
    Desde el 2026-10-09 la agente y las pantallas hablan de tu; este chequeo
    prohibe el trato de usted en esas frases.
    """

    catalog: str
    surfaces: frozenset[str]
    usted: tuple[tuple[str, str, re.Pattern[str]], ...]
    #: Identificador, palabra y cuantas veces se tolera en una frase.
    fillers: tuple[tuple[str, str, int], ...]


@dataclass(frozen=True)
class ContentRules:
    """Las listas versionadas que gobiernan los chequeos de contenido."""

    published: tuple[str, ...]
    exclusions: tuple[tuple[str, str], ...]
    forbidden_claims: tuple[tuple[str, str, re.Pattern[str]], ...]
    clause_markers: tuple[tuple[str, str, re.Pattern[str]], ...]
    spanish_register: SpanishRegister | None

    def is_excluded(self, relativo: str) -> bool:
        return any(relativo.startswith(ruta) for ruta, _ in self.exclusions)


def rules_path(root: Path) -> Path:
    return root / "app" / "config" / "content-checks.yaml"


def load_rules(root: Path | None = None) -> ContentRules:
    """Lee las listas versionadas. Falla nombrando el archivo si no esta."""
    base = root if root is not None else paths.repo_root()
    archivo = rules_path(base)
    if not archivo.is_file():
        msg = f"falta la lista versionada de chequeos de contenido: se esperaba '{archivo}'"
        raise FileNotFoundError(msg)

    cargado: Any = yaml.safe_load(archivo.read_text(encoding="utf-8")) or {}

    def compilar(clave: str) -> tuple[tuple[str, str, re.Pattern[str]], ...]:
        return tuple(
            (str(entrada["id"]), str(entrada["reason"]).strip(), re.compile(str(patron)))
            for entrada in cargado.get(clave, [])
            for patron in entrada["patterns"]
        )

    return ContentRules(
        published=tuple(str(p) for p in cargado.get("published", [])),
        exclusions=tuple(
            (str(e["path"]), str(e["reason"]).strip()) for e in cargado.get("exclusions", [])
        ),
        forbidden_claims=compilar("forbidden_claims"),
        clause_markers=compilar("clause_text_markers"),
        spanish_register=_registro(cargado),
    )


def _registro(cargado: Any) -> SpanishRegister | None:
    """La seccion del registro en espanol, o nada si la lista no la trae."""
    seccion = cargado.get("spanish_register")
    if not seccion:
        return None
    return SpanishRegister(
        catalog=str(seccion["catalog"]),
        surfaces=frozenset(str(s) for s in seccion.get("surfaces", [])),
        usted=tuple(
            (str(e["id"]), str(e["reason"]).strip(), re.compile(str(patron)))
            for e in seccion.get("usted", [])
            for patron in e["patterns"]
        ),
        fillers=tuple(
            (str(e["id"]), str(e["word"]), int(e["max_per_phrase"]))
            for e in seccion.get("fillers", [])
        ),
    )


def published_files(root: Path, rules: ContentRules) -> tuple[Path, ...]:
    """Los archivos que se publican, ya descontadas las exclusiones."""
    encontrados: list[Path] = []
    for prefijo in rules.published:
        objetivo = root / prefijo
        if objetivo.is_file():
            if not rules.is_excluded(objetivo.relative_to(root).as_posix()):
                encontrados.append(objetivo)
            continue
        if not objetivo.is_dir():
            continue

        # Se podan los directorios excluidos **al bajar**, no al filtrar despues:
        # `node_modules` tiene decenas de miles de archivos, y recorrerlos para
        # descartarlos convierte un chequeo de segundos en uno de minutos.
        for directorio, subdirectorios, archivos in objetivo.walk():
            relativo_dir = directorio.relative_to(root).as_posix()
            subdirectorios[:] = [
                nombre
                for nombre in subdirectorios
                if not rules.is_excluded(f"{relativo_dir}/{nombre}")
            ]
            for nombre in archivos:
                archivo = directorio / nombre
                if archivo.suffix not in EXTENSIONES:
                    continue
                if not rules.is_excluded(archivo.relative_to(root).as_posix()):
                    encontrados.append(archivo)

    return tuple(sorted(set(encontrados), key=lambda p: p.as_posix()))


def _scan(
    root: Path,
    rules: ContentRules,
    patrones: tuple[tuple[str, str, re.Pattern[str]], ...],
    regla: str,
) -> list[ContentFinding]:
    hallazgos: list[ContentFinding] = []
    for archivo in published_files(root, rules):
        try:
            contenido = archivo.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for numero, linea in enumerate(contenido.splitlines(), start=1):
            for identificador, razon, patron in patrones:
                if patron.search(linea):
                    hallazgos.append(
                        ContentFinding(
                            regla,
                            f"{archivo.relative_to(root).as_posix()}:{numero}",
                            f"{identificador}: {razon.splitlines()[0]}",
                        )
                    )
    return hallazgos


def check_forbidden_claims(root: Path, rules: ContentRules) -> list[ContentFinding]:
    """Ninguna afirmacion de cumplimiento normativo en lo que se publica."""
    return _scan(root, rules, rules.forbidden_claims, "CONTENT-CLAIMS")


def check_clause_text(root: Path, rules: ContentRules) -> list[ContentFinding]:
    """Ningun texto de clausula de ISO o ACORD en lo que se publica.

    Lo que se busca **no** son nombres de seccion ni numeros de formulario: eso
    es estructura, esta permitido y esta documentado. Lo que se busca son los
    arranques de prosa de formulario, que es la senal de que alguien copio texto
    en vez de escribir el suyo, y el calco por huellas en cada clausula del
    corpus (`check_third_party_text`).
    """
    return [
        *_scan(root, rules, rules.clause_markers, "CONTENT-CLAUSE"),
        *check_third_party_text(root),
    ]


#: El identificador estable de la mitad de las huellas, para el reporte por caso.
REGLA_DE_HUELLAS = "CONTENT-THIRD-PARTY"

_HASH = re.compile(r"^[0-9a-f]{64}$")


def _clausulas_del_corpus(root: Path, corpus: str) -> list[tuple[str, str, str]]:
    """Cada clausula del corpus: donde esta, su identificador y su texto.

    Lee los archivos como datos: el corredor de evaluaciones no importa el
    generador (BR8.1), y lo que se compara es lo que esta escrito, no lo que el
    generador produciria.
    """
    clausulas: list[tuple[str, str, str]] = []
    for archivo in sorted((root / corpus).glob("*/clauses/*.json"), key=lambda p: p.as_posix()):
        relativo = archivo.relative_to(root).as_posix()
        datos: Any = json.loads(archivo.read_text(encoding="utf-8"))
        for clausula in datos.get("clauses", []):
            clausulas.append((relativo, str(clausula["clause_id"]), str(clausula["text"])))
    return clausulas


def _huellas_guardadas(root: Path, ajustes: FingerprintSettings) -> tuple[frozenset[str], str]:
    """Las huellas del archivo, o el motivo por el que no se pueden usar.

    Comprueba lo que hace falta para comparar: que existan, que no esten vacias y
    que se hayan sacado con **esta** normalizacion. La forma completa del archivo
    la valida `schema:check` contra su modelo.
    """
    archivo = root / ajustes.shingles_file
    try:
        datos: Any = json.loads(archivo.read_text(encoding="utf-8")) if archivo.is_file() else None
    except (OSError, ValueError) as error:
        return frozenset(), f"no se pudo leer '{ajustes.shingles_file}': {type(error).__name__}"
    motivo = _por_que_no_sirven(datos, ajustes)
    return (frozenset(), motivo) if motivo else (frozenset(datos["hashes"]), "")


def _por_que_no_sirven(datos: Any, ajustes: FingerprintSettings) -> str:
    """El primer motivo por el que las huellas leidas no sirven para comparar, o nada."""
    nombre = ajustes.shingles_file
    if datos is None:
        return f"falta el archivo de huellas '{nombre}' (BR5.3)"
    if not isinstance(datos, dict):
        return f"'{nombre}' no es un objeto"
    hashes = datos.get("hashes")
    motivos = (
        (
            datos.get("normalization") != ajustes.normalization,
            f"'{nombre}' se saco con otra normalizacion; vuelva a sacarlas con "
            "`mise run synthetic:fingerprints`",
        ),
        (
            datos.get("shingle_size") != ajustes.shingle_size,
            f"'{nombre}' usa otro tamano de secuencia",
        ),
        (
            not isinstance(hashes, list) or not hashes or not datos.get("sources"),
            f"'{nombre}' no trae huellas ni specimens (BR5.3)",
        ),
        (
            isinstance(hashes, list)
            and not all(isinstance(h, str) and _HASH.fullmatch(h) for h in hashes),
            f"'{nombre}' trae algo que no es un SHA-256",
        ),
    )
    return next((motivo for falla, motivo in motivos if falla), "")


def check_third_party_text(root: Path) -> list[ContentFinding]:
    """Ninguna clausula del corpus comparte una secuencia de ocho palabras con terceros (BR5.2).

    Umbral cero: una sola secuencia compartida falla y nombra la clausula. Nunca
    imprime la secuencia: el hallazgo dice cuantas, no cuales, porque la
    secuencia seria texto del formulario de terceros dentro de un log.

    Sin corpus no hay nada que comparar. Con corpus y sin huellas utilizables, el
    chequeo es "no medido" y **falla** (BR5.3): una compuerta que no se pudo
    ejecutar nunca pasa en verde.
    """
    try:
        ajustes = load_fingerprint_settings(root)
    except SettingsError as error:
        return [
            ContentFinding(
                REGLA_DE_HUELLAS, "app/config/content-checks.yaml", f"no medido: {error}"
            )
        ]

    try:
        clausulas = _clausulas_del_corpus(root, ajustes.corpus)
    except (OSError, ValueError, KeyError, AttributeError) as error:
        return [
            ContentFinding(
                REGLA_DE_HUELLAS, ajustes.corpus, f"no medido: el corpus no se pudo leer ({error})"
            )
        ]
    if not clausulas:
        return []

    huellas, motivo = _huellas_guardadas(root, ajustes)
    if motivo:
        return [ContentFinding(REGLA_DE_HUELLAS, ajustes.shingles_file, f"no medido: {motivo}")]

    hallazgos: list[ContentFinding] = []
    for donde, clausula, texto in clausulas:
        compartidas = len(ajustes.fingerprint(texto) & huellas)
        if compartidas:
            hallazgos.append(
                ContentFinding(
                    REGLA_DE_HUELLAS,
                    donde,
                    f"{clausula}: comparte {compartidas} secuencia(s) de {ajustes.shingle_size} "
                    "palabras con un formulario de terceros; reescribala en su texto fuente, "
                    "con su revision, y regenere (BR5.2)",
                )
            )
    return hallazgos


def _frases_del_catalogo(nodo: Any, ruta: tuple[str, ...] = ()) -> list[tuple[str, str, str]]:
    """Cada entrada del catalogo como (clave, superficie, texto).

    Se recorre el arbol ya interpretado y **no las lineas del archivo**: por linea,
    un patron de usted casaria con el nombre de una clave --`chat.page.tu_mensaje`--
    y con los comentarios, que estan escritos en espanol precisamente para explicar
    la regla.
    """
    encontradas: list[tuple[str, str, str]] = []
    if isinstance(nodo, dict):
        texto = nodo.get("text")
        if isinstance(texto, str):
            encontradas.append((".".join(ruta), str(nodo.get("surface", "")), texto))
        for clave, valor in nodo.items():
            encontradas += _frases_del_catalogo(valor, (*ruta, str(clave)))
    elif isinstance(nodo, list):
        for i, valor in enumerate(nodo):
            encontradas += _frases_del_catalogo(valor, (*ruta, str(i)))
    return encontradas


def check_spanish_register(root: Path, rules: ContentRules) -> list[ContentFinding]:
    """La agente habla de tu en espanol, y sin abusar de las muletillas (BR5.4).

    Un catalogo que falta o una seccion sin patrones **no pasan en silencio**: se
    declaran como hallazgo, por lo mismo que las huellas de terceros. Un chequeo que
    no encuentra nada que mirar y dice "sin hallazgos" es indistinguible de uno que
    miro y no encontro nada.
    """
    registro = rules.spanish_register
    if registro is None:
        return [
            ContentFinding(
                "CONTENT-REGISTER",
                rules_path(root).relative_to(root).as_posix(),
                "falta la seccion `spanish_register`: el registro en espanol queda sin medir",
            )
        ]
    archivo = root / registro.catalog
    if not archivo.is_file():
        return [
            ContentFinding(
                "CONTENT-REGISTER",
                registro.catalog,
                "no existe el catalogo en espanol: el registro queda sin medir",
            )
        ]
    if not registro.usted:
        return [
            ContentFinding(
                "CONTENT-REGISTER",
                rules_path(root).relative_to(root).as_posix(),
                "la seccion `spanish_register` no trae ningun patron de usted",
            )
        ]

    catalogo: Any = yaml.safe_load(archivo.read_text(encoding="utf-8")) or {}
    frases = [
        (clave, texto)
        for clave, superficie, texto in _frases_del_catalogo(catalogo)
        if superficie in registro.surfaces
    ]
    if not frases:
        return [
            ContentFinding(
                "CONTENT-REGISTER",
                registro.catalog,
                f"ninguna frase con superficie {sorted(registro.surfaces)}: nada que mirar",
            )
        ]

    hallazgos: list[ContentFinding] = []
    for clave, texto in frases:
        for identificador, razon, patron in registro.usted:
            encontrado = patron.search(texto)
            if encontrado is not None:
                hallazgos.append(
                    ContentFinding(
                        "CONTENT-REGISTER",
                        f"{registro.catalog}:{clave}",
                        f"{identificador}: {razon.splitlines()[0]} («{encontrado.group(0)}»)",
                    )
                )
        for identificador, palabra, tope in registro.fillers:
            veces = len(re.findall(rf"(?i)\b{re.escape(palabra)}\b", texto))
            if veces > tope:
                hallazgos.append(
                    ContentFinding(
                        "CONTENT-REGISTER",
                        f"{registro.catalog}:{clave}",
                        f"{identificador}: «{palabra}» {veces} veces y el tope es {tope}",
                    )
                )
    return hallazgos


def run_all(root: Path | None = None) -> list[ContentFinding]:
    base = root if root is not None else paths.repo_root()
    reglas = load_rules(base)
    return [
        *check_forbidden_claims(base, reglas),
        *check_clause_text(base, reglas),
        *check_spanish_register(base, reglas),
    ]


# --- Como casos de evaluacion -------------------------------------------------


def _outcome(hallazgos: list[ContentFinding]) -> CheckOutcome:
    if hallazgos:
        return CheckOutcome(passed=False, detail="; ".join(str(h) for h in hallazgos))
    return CheckOutcome(passed=True)


# Los dos chequeos recorren archivos, no frases, y sus patrones cubren los dos
# idiomas en la misma pasada. Aun asi hay un caso por idioma, y el veredicto sale
# repetido en las dos columnas: es lo correcto y no una duplicacion perezosa.
# Reportar el hallazgo en una sola columna daria a entender que el otro idioma
# esta limpio, que es exactamente la lectura que la paridad existe para impedir.


def content_forbidden_claims(*, language: Locale, root: Path) -> CheckOutcome:
    """Criterio de evaluacion: sin afirmaciones de cumplimiento (P6, R9)."""
    del language
    return _outcome(check_forbidden_claims(root, load_rules(root)))


def content_clause_text(*, language: Locale, root: Path) -> CheckOutcome:
    """Criterio de evaluacion: sin texto de clausula ajena (P8, W6)."""
    del language
    return _outcome(check_clause_text(root, load_rules(root)))


def content_spanish_register(*, language: Locale, root: Path) -> CheckOutcome:
    """Criterio de evaluacion: la agente habla de tu en espanol (BR5.4).

    **Este si es de un solo idioma**, al contrario que los dos de arriba, y por eso
    el ingles se reporta como no aplicable en vez de repetir el veredicto: el
    registro del tu/usted no existe en ingles, y copiar el veredicto daria a entender
    que se midio algo alli.
    """
    if language != "es":
        return CheckOutcome(passed=True, detail="no aplica: el registro de tu es del espanol")
    return _outcome(check_spanish_register(root, load_rules(root)))


CHEQUEOS = {
    "content_forbidden_claims": content_forbidden_claims,
    "content_clause_text": content_clause_text,
    "content_spanish_register": content_spanish_register,
}


UNIT = "contenido-publicado"

#: Dos prohibiciones del proyecto (P6 y P8), registradas como bloqueantes el
#: 2026-10-11: afirmar "cumple con" una norma, y publicar texto de clausula de ISO
#: o ACORD. Un solo hallazgo detiene la entrega. El registro de tu del espanol es de
#: estilo y no bloquea.
TARGETS: tuple[EvalTarget, ...] = (
    EvalTarget(
        "content_forbidden_claims",
        Dataset.DS_8,
        "Nada de lo publicado afirma cumplir una norma (P6, R9)",
        blocking=True,
    ),
    EvalTarget(
        "content_clause_text",
        Dataset.DS_8,
        "Nada de lo publicado trae texto de clausula de ISO o ACORD (P8, W6)",
        blocking=True,
    ),
)


def register_content_checks() -> None:
    for criterio, chequeo in CHEQUEOS.items():
        register_check(criterio, chequeo)
    register_targets(UNIT, TARGETS)


def main() -> int:
    hallazgos = run_all()
    for hallazgo in hallazgos:
        print(str(hallazgo), file=sys.stderr)
    if hallazgos:
        print(f"\n{len(hallazgos)} hallazgo(s) de contenido", file=sys.stderr)
        return 1
    print("chequeos de contenido: sin hallazgos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
