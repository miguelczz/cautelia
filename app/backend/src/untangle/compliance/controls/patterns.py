"""La carga de los patrones versionados de `app/config/compliance/` (CG-U10-1).

Los controles del turno son reglas deterministas sobre texto normalizado
(FD-U10-1), y sus reglas son **datos**: viven en archivos YAML versionados, uno
por idioma y por familia, y cambiarlos es un cambio a la vista que llega con el
caso que lo motivo (BR9.2). El codigo no tiene ninguna expresion de la guardia
ni de las senales escrita dentro.

## Un archivo invalido impide arrancar (TECH-U10.1)

Un patron que no compila, que lleva mayusculas o tildes --y por eso nunca
coincidiria con el texto normalizado--, con un identificador que no es el suyo o
en la familia equivocada **no carga**, y el fallo nombra el archivo y el patron.
La raiz de composicion carga la biblioteca al construir la aplicacion: un
patron roto es un proceso que no arranca, no una guardia que deja pasar frases
en silencio. La guardia, ademas, falla cerrado si algo se rompe despues (BR1.5).

## Los dos idiomas sobre cada texto (BR1.3)

La biblioteca junta los patrones **de los dos idiomas** de cada familia, y los
controles los aplican todos a cada frase sin mirar el idioma del turno. Es lo
que para el ataque bilingue (RT-15): una promesa a medias en el otro idioma la
atrapa el juego de ese otro idioma.

## Forma de un identificador

`<familia>.<idioma>.<categoria>.<nnn>` en la guardia --`guard.es.amount.002`-- y
`<familia>.<idioma>.<signal|negation>.<nnn>` en las demas. El identificador es lo
que se guarda en cada intervencion en lugar de la frase (BR1.6), asi que tiene
que decir por si solo de donde salio.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Self, get_args

import yaml
from pydantic import Field, ValidationError, model_validator

from untangle import paths
from untangle.base import Frozen, Locale
from untangle.compliance.controls.models import (
    CATALOG_KEY_MAX_LENGTH,
    CATALOG_KEY_PATTERN,
    PATTERN_ID_MAX_LENGTH,
    PATTERN_ID_PATTERN,
    GuardCategory,
)
from untangle.compliance.controls.normalization import fold

#: Los dos idiomas, derivados del tipo para que anadir uno no exija acordarse de
#: tocar esta lista.
LOCALES: tuple[Locale, ...] = get_args(Locale)

#: Una secuencia de escape de una expresion regular: `\S`, `\d`, `\.`. Se quita
#: antes de comprobar que el patron esta normalizado, porque `\S` lleva una
#: mayuscula que significa algo y no es texto.
_ESCAPE = re.compile(r"\\.")


class PatternFamily(StrEnum):
    """Las cuatro familias de patrones (`entities.md`, PatternSet)."""

    GUARD = "guard"
    HUMAN_REQUEST = "human_request"
    IDENTITY_QUESTION = "identity_question"
    EMERGENCY = "emergency"


class PatternLoadError(Exception):
    """Los patrones no se pudieron cargar. El mensaje nombra el archivo y el patron.

    Es un fallo de arranque a proposito (TECH-U10.1): una guardia viva con sus
    patrones rotos parece que funciona, y ese es el peor estado posible para un
    control que nadie mira mientras no falla.
    """


class Pattern(Frozen):
    """Una expresion sobre texto normalizado, con su identificador estable."""

    id: str = Field(pattern=PATTERN_ID_PATTERN, max_length=PATTERN_ID_MAX_LENGTH)
    #: Solo en la guardia: la categoria que detecta (BR1.2).
    category: GuardCategory | None = None
    regex: str = Field(min_length=1)

    @model_validator(mode="after")
    def _compila(self) -> Self:
        try:
            re.compile(self.regex)
        except re.error as error:
            msg = f"el patron '{self.id}' no es una expresion valida: {error}"
            raise ValueError(msg) from error
        return self

    @model_validator(mode="after")
    def _esta_escrito_normalizado(self) -> Self:
        # Fuera de sus secuencias de escape, el patron tiene que ser igual a su
        # forma normalizada: una mayuscula o una tilde en un patron que mira
        # texto sin mayusculas ni tildes no coincide nunca, y el fallo no avisa.
        literal = _ESCAPE.sub("", self.regex)
        if fold(literal) != literal:
            msg = (
                f"el patron '{self.id}' lleva mayusculas, tildes o apostrofos "
                "tipograficos fuera de sus secuencias de escape; el texto que mira "
                "esta normalizado y nunca coincidiria (BR1.3)"
            )
            raise ValueError(msg)
        return self


def _forma_del_identificador(
    family: PatternFamily, language: Locale, pattern: Pattern, *, negation: bool
) -> str | None:
    """El problema del identificador de un patron, o nada."""
    if family is PatternFamily.GUARD:
        medio = pattern.category.value if pattern.category is not None else "<categoria>"
    else:
        medio = "negation" if negation else "signal"
    esperado = re.compile(rf"^{family.value}\.{language}\.{medio}\.\d{{3}}$")
    if esperado.match(pattern.id):
        return None
    return (
        f"el patron '{pattern.id}' no tiene la forma "
        f"'{family.value}.{language}.{medio}.<nnn>' que le toca por su archivo"
    )


class PatternSet(Frozen):
    """Los patrones versionados de un idioma para una familia (`entities.md`)."""

    language: Locale
    family: PatternFamily
    version: str = Field(min_length=1, max_length=32)
    patterns: tuple[Pattern, ...] = Field(min_length=1)
    #: Solo en la emergencia: los que apagan una senal **que tocan** (BR3.2).
    negations: tuple[Pattern, ...] = ()
    #: Solo en la guardia: las claves del catalogo de las plantillas aprobadas de
    #: respuesta verificada, que la categoria de promesa de cobertura no
    #: reemplaza (BR1.8). Se exime una **clave**, no un texto: solo lo que el
    #: aplicativo compuso desde el catalogo puede traerla, y el modelo no.
    exempt_catalog_keys: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _cada_patron_en_su_sitio(self) -> Self:
        problemas: list[str] = []
        guardia = self.family is PatternFamily.GUARD
        for patron in self.patterns:
            if guardia != (patron.category is not None):
                problemas.append(
                    f"el patron '{patron.id}' "
                    + ("no declara su categoria" if guardia else "declara una categoria")
                    + f" y su familia es '{self.family.value}'"
                )
            problema = _forma_del_identificador(self.family, self.language, patron, negation=False)
            if problema is not None:
                problemas.append(problema)
        for patron in self.negations:
            problema = _forma_del_identificador(self.family, self.language, patron, negation=True)
            if problema is not None:
                problemas.append(problema)
        if problemas:
            raise ValueError("; ".join(problemas))
        return self

    @model_validator(mode="after")
    def _negaciones_y_exenciones_solo_donde_van(self) -> Self:
        if self.negations and self.family is not PatternFamily.EMERGENCY:
            msg = (
                f"la familia '{self.family.value}' declara negaciones; solo la "
                "emergencia las tiene (BR3.2)"
            )
            raise ValueError(msg)
        if self.exempt_catalog_keys and self.family is not PatternFamily.GUARD:
            msg = f"la familia '{self.family.value}' declara exenciones; solo la guardia las tiene"
            raise ValueError(msg)
        forma = re.compile(CATALOG_KEY_PATTERN)
        malas = [
            clave
            for clave in self.exempt_catalog_keys
            if not forma.match(clave) or len(clave) > CATALOG_KEY_MAX_LENGTH
        ]
        if malas:
            msg = f"las exenciones {malas} no tienen forma de clave del catalogo"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _identificadores_unicos(self) -> Self:
        ids = [patron.id for patron in (*self.patterns, *self.negations)]
        repetidos = sorted({i for i in ids if ids.count(i) > 1})
        if repetidos:
            msg = f"los identificadores {repetidos} se repiten"
            raise ValueError(msg)
        return self


@dataclass(frozen=True)
class CompiledPattern:
    """Un patron listo para aplicar: su identificador, su categoria y su expresion."""

    id: str
    category: GuardCategory | None
    regex: re.Pattern[str]


def _compilar(patrones: tuple[Pattern, ...]) -> tuple[CompiledPattern, ...]:
    return tuple(CompiledPattern(p.id, p.category, re.compile(p.regex)) for p in patrones)


@dataclass(frozen=True)
class PatternLibrary:
    """Los patrones de **los dos idiomas**, compilados y agrupados por familia.

    Cada tupla trae primero los de espanol y despues los de ingles: el orden no
    cambia que se detecta --se aplican todos--, solo que identificador se nombra
    cuando dos patrones de idiomas distintos coinciden en la misma frase, y asi
    ese nombre es el mismo en cada corrida.
    """

    sets: tuple[PatternSet, ...]
    guard: tuple[CompiledPattern, ...]
    human_request: tuple[CompiledPattern, ...]
    identity_question: tuple[CompiledPattern, ...]
    emergency: tuple[CompiledPattern, ...]
    emergency_negations: tuple[CompiledPattern, ...]
    exempt_catalog_keys: frozenset[str]

    def versions(self) -> dict[str, str]:
        """La version de cada archivo, por `<idioma>/<familia>`."""
        return {f"{s.language}/{s.family.value}": s.version for s in self.sets}


def pattern_file(language: Locale, family: PatternFamily, root: Path | None = None) -> Path:
    """Donde vive el archivo de un idioma y una familia."""
    directorio = root if root is not None else paths.compliance_dir()
    return directorio / language / f"{family.value}.yaml"


def _problemas(error: ValidationError) -> str:
    """Cada problema con su ruta y su mensaje: el mensaje nombra el patron culpable."""
    return "; ".join(
        f"{'.'.join(str(parte) for parte in problema['loc']) or '(raiz)'}: {problema['msg']}"
        for problema in error.errors()
    )


def load_pattern_set(
    language: Locale, family: PatternFamily, root: Path | None = None
) -> PatternSet:
    """El archivo de un idioma y una familia, validado y nombrando el archivo en cada fallo."""
    archivo = pattern_file(language, family, root)
    if not archivo.is_file():
        msg = (
            f"faltan los patrones '{family.value}' del idioma '{language}': se esperaba "
            f"'{archivo}'. Sin ellos ese idioma no se vigila, y el fallo no avisa"
        )
        raise PatternLoadError(msg)
    try:
        cargado: Any = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        msg = f"no se pudo leer '{archivo}': {error}"
        raise PatternLoadError(msg) from error
    try:
        juego = PatternSet.model_validate(cargado)
    except ValidationError as error:
        msg = f"los patrones '{archivo}' no validan su esquema: {_problemas(error)} (TECH-U10.1)"
        raise PatternLoadError(msg) from error
    if juego.language != language or juego.family is not family:
        msg = (
            f"'{archivo}' declara '{juego.language}/{juego.family.value}' y vive en "
            f"el sitio de '{language}/{family.value}'"
        )
        raise PatternLoadError(msg)
    return juego


def _exigir_las_siete_categorias(juegos: dict[tuple[Locale, PatternFamily], PatternSet]) -> None:
    """Cada idioma cubre las siete categorias de la guardia (BR1.2, P12).

    Un idioma sin patrones de una categoria deja esa categoria vigilada solo por
    el otro idioma, y la paridad por idioma es justamente lo que un recuento
    combinado esconderia.
    """
    for idioma in LOCALES:
        juego = juegos[(idioma, PatternFamily.GUARD)]
        cubiertas = {p.category for p in juego.patterns}
        faltan = sorted(c.value for c in GuardCategory if c not in cubiertas)
        if faltan:
            archivo = pattern_file(idioma, PatternFamily.GUARD)
            msg = f"'{archivo}' no tiene patrones de las categorias {faltan} (BR1.2)"
            raise PatternLoadError(msg)


def _exigir_las_mismas_exenciones(juegos: dict[tuple[Locale, PatternFamily], PatternSet]) -> None:
    """Las dos guardias eximen las mismas claves: una exencion es de la plantilla, no del idioma."""
    por_idioma = {
        idioma: frozenset(juegos[(idioma, PatternFamily.GUARD)].exempt_catalog_keys)
        for idioma in LOCALES
    }
    if len(set(por_idioma.values())) > 1:
        detalle = "; ".join(f"{i}: {sorted(c)}" for i, c in sorted(por_idioma.items()))
        msg = f"las guardias de los dos idiomas eximen claves distintas: {detalle} (BR1.8)"
        raise PatternLoadError(msg)


def load_library(root: Path | None = None) -> PatternLibrary:
    """Los ocho archivos --cuatro familias por idioma--, validados y compilados."""
    juegos = {
        (idioma, familia): load_pattern_set(idioma, familia, root)
        for familia in PatternFamily
        for idioma in LOCALES
    }
    _exigir_las_siete_categorias(juegos)
    _exigir_las_mismas_exenciones(juegos)

    def de(familia: PatternFamily) -> tuple[Pattern, ...]:
        return tuple(p for idioma in LOCALES for p in juegos[(idioma, familia)].patterns)

    return PatternLibrary(
        sets=tuple(juegos.values()),
        guard=_compilar(de(PatternFamily.GUARD)),
        human_request=_compilar(de(PatternFamily.HUMAN_REQUEST)),
        identity_question=_compilar(de(PatternFamily.IDENTITY_QUESTION)),
        emergency=_compilar(de(PatternFamily.EMERGENCY)),
        emergency_negations=_compilar(
            tuple(p for i in LOCALES for p in juegos[(i, PatternFamily.EMERGENCY)].negations)
        ),
        exempt_catalog_keys=frozenset(
            clave
            for idioma in LOCALES
            for clave in juegos[(idioma, PatternFamily.GUARD)].exempt_catalog_keys
        ),
    )


# --- La biblioteca del proceso ------------------------------------------------

_library: PatternLibrary | None = None


def install(library: PatternLibrary) -> None:
    """Fija la biblioteca del proceso. La llama la raiz de composicion al arrancar."""
    global _library
    _library = library


def get_library() -> PatternLibrary:
    """La biblioteca del proceso, cargandola la primera vez si hace falta.

    Si la carga falla, levanta: quien la pide en el turno es la guardia, y la
    guardia convierte ese fallo en su salida de degradacion (BR1.5).
    """
    global _library
    if _library is None:
        _library = load_library()
    return _library


def reset() -> None:
    """Olvida la biblioteca cargada. Lo usan las pruebas para no compartir estado."""
    global _library
    _library = None
