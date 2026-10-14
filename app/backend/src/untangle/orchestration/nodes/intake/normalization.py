"""Normalizacion por reglas versionadas, en codigo, despues del modelo (BR2.4, TECH-U11.2).

**Por que en codigo y no en el modelo** (FD-U11-2): si normalizara el modelo,
dos corridas del mismo commit podrian escribir valores distintos para el mismo
turno, y la exactitud por campo de AC1.7.5 dejaria de ser reproducible. Estas
funciones son puras: mismo texto, mismo idioma, mismo resultado, siempre.

Cada normalizador devuelve `None` cuando el texto no tiene la forma de su
campo. `None` no es un error: es la senal de que el valor entra tal cual lo
dijo la persona, sin normalizacion (`FieldEvidence.normalization` vacio en
`entities.md`) -- normalizar mal seria peor que no normalizar, porque
escribiria un valor que la persona nunca dijo.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from untangle.base import Locale
from untangle.compliance.controls.normalization import normalize as fold_and_collapse
from untangle.orchestration.nodes.intake.spelling import load as load_spelling_alphabet

# --- BR2.4, TECH-U11.2: los separadores dictados que la transcripcion pega --
# --- a los codigos ("be de seis" -> "BD6") ----------------------------------


def decode_spelled_code(text: str, *, language: Locale, root: Path | None = None) -> str:
    """Reconstruye un codigo a partir de sus letras y digitos dictados.

    Usa la misma tabla que `spelling.spell_for_readback` (BR2.5): un nombre de
    letra hablado, o ese nombre seguido del conector y la palabra de
    desambiguacion de esa letra (los dos se consumen sin aportar nada nuevo),
    o un nombre de digito. Un token que no encaja en ninguna de las tres
    formas se descarta: es la parte de la frase que no es el codigo ("mi
    placa es...", "la poliza es...").
    """
    tabla = load_spelling_alphabet(root)
    nombres_letra = tabla.letter_names.get(language, {})
    nombres_digito = tabla.digit_words.get(language, {})
    desambiguaciones = tabla.disambiguations.get(language, {})
    #: El conector puede ser de varias palabras ("as in"): se compara como una
    #: secuencia de tokens, no como uno solo.
    conector_tokens = tuple(fold_and_collapse(tabla.connector.get(language, "")).split(" "))
    if conector_tokens == ("",):
        conector_tokens = ()
    n_conector = len(conector_tokens)

    # `findall` en vez de `split(" ")`: descarta comas y otra puntuacion que
    # se pega a la palabra de desambiguacion ("burro,") y que un `split`
    # dejaria adentro, rompiendo la comparacion contra la tabla.
    tokens = re.findall(r"[a-z0-9]+", fold_and_collapse(text))
    resultado: list[str] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]

        letra = nombres_letra.get(token)
        if letra is not None:
            resultado.append(letra)
            fin_conector = i + 1 + n_conector
            if (
                n_conector
                and fin_conector < len(tokens)
                and tuple(tokens[i + 1 : fin_conector]) == conector_tokens
                and desambiguaciones.get(tokens[fin_conector]) == letra
            ):
                i = fin_conector + 1
                continue
            i += 1
            continue

        digito = nombres_digito.get(token)
        if digito is not None:
            resultado.append(digito)
            i += 1
            continue

        if token.isdigit():
            resultado.extend(token)
            i += 1
            continue

        if len(token) == 1 and token.isalpha():
            resultado.append(token.upper())
            i += 1
            continue

        i += 1  # token que no es parte del codigo: se descarta.

    return "".join(resultado)


# --- Poliza, placa y cedula: dictado letra por letra, o ya escrito ----------
#
# Dos candidatos, en este orden: el texto **tal cual**, sin nada que no sea
# letra o digito (un numero ya escrito, "POL-480915"), y el texto **decodificado**
# de sus separadores dictados (BR2.4, "be de seis" -> "BD6"). El primero que
# tenga la forma cerrada del campo gana; los dos pasan por la misma
# comprobacion de forma, para que un numero ya escrito y uno deletreado se
# validen exactamente igual.

_POLICY_NUMBER = re.compile(r"^POL(\d{6})$")
_PLATE = re.compile(r"^[A-Z]{3}(?:\d{3}|\d{2}[A-Z]|\d{4})$|^\d[A-Z]{3}\d{3}$")


def _alnum(text: str) -> str:
    """Solo lo alfanumerico, sin espacios ni separadores ('-', '.', etc.)."""
    return "".join(caracter for caracter in text if caracter.isalnum())


def _candidatos(text: str, *, language: Locale, root: Path | None) -> tuple[str, str]:
    return (_alnum(text).upper(), decode_spelled_code(text, language=language, root=root).upper())


def normalize_policy_number(text: str, *, language: Locale, root: Path | None = None) -> str | None:
    """`POL-` y seis digitos, o `None` si lo dictado no completa un numero."""
    for candidato in _candidatos(text, language=language, root=root):
        coincidencia = _POLICY_NUMBER.match(candidato)
        if coincidencia is not None:
            return f"POL-{coincidencia.group(1)}"
    return None


def normalize_plate(text: str, *, language: Locale, root: Path | None = None) -> str | None:
    """Una placa colombiana o estadounidense, sin separadores, en mayusculas."""
    for candidato in _candidatos(text, language=language, root=root):
        if _PLATE.match(candidato) is not None:
            return candidato
    return None


def normalize_national_id(text: str, *, language: Locale, root: Path | None = None) -> str | None:
    """Solo los digitos de la cedula, sin puntos ni espacios."""
    for candidato in _candidatos(text, language=language, root=root):
        if candidato.isdigit() and 6 <= len(candidato) <= 10:
            return candidato
    return None


def normalize_phone(text: str, *, language: Locale, root: Path | None = None) -> str | None:
    """Solo los digitos del telefono, sin separadores."""
    for candidato in _candidatos(text, language=language, root=root):
        if candidato.isdigit() and 7 <= len(candidato) <= 15:
            return candidato
    return None


# --- Fechas relativas (BR2.4) ------------------------------------------------

#: Desplazamiento en dias respecto al turno, por frase y por idioma. Cerrada y
#: versionada aqui: anadir una frase es anadir una entrada, nunca una rama.
_RELATIVE_DAYS: dict[Locale, dict[str, int]] = {
    "es": {
        "hoy": 0,
        "ayer": -1,
        "anteayer": -2,
        "antier": -2,
    },
    "en": {
        "today": 0,
        "yesterday": -1,
        "the day before yesterday": -2,
    },
}

_DAYS_AGO = {
    "es": re.compile(r"hace (\d+) d[ií]as?"),
    "en": re.compile(r"(\d+) days? ago"),
}


def normalize_relative_date(text: str, *, language: Locale, now: date) -> date | None:
    """Una fecha relativa dicha en el turno, resuelta contra el reloj del turno.

    `now` es la fecha del turno, no la del reloj del proceso: dos corridas del
    mismo commit sobre el mismo caso tienen que resolver "ayer" a la misma
    fecha (BR2.4), y eso solo es cierto si el reloj entra por argumento.
    """
    normalizado = fold_and_collapse(text)
    # Las frases mas largas primero, y con limite de palabra: "ayer" es una
    # subcadena literal de "anteayer", y sin el limite de palabra "anteayer"
    # resolveria como si la persona hubiera dicho "ayer".
    frases_por_longitud = sorted(
        _RELATIVE_DAYS.get(language, {}).items(), key=lambda par: -len(par[0])
    )
    for frase, desplazamiento in frases_por_longitud:
        if re.search(rf"\b{re.escape(frase)}\b", normalizado):
            return now + timedelta(days=desplazamiento)

    patron = _DAYS_AGO.get(language)
    if patron is not None:
        coincidencia = patron.search(normalizado)
        if coincidencia is not None:
            return now - timedelta(days=int(coincidencia.group(1)))

    return None


# --- U19: los campos tipados de la solicitud de cotizacion -------------------
#
# Lo que las reglas de elegibilidad leen tiene que ser un numero, un si/no o un valor
# de un conjunto cerrado, y **lo que el modelo copia es lo que la persona dijo**
# ("hace como ocho anios", "no, esta limpio"). Esta es la mitad que lo convierte, en
# codigo y con tablas versionadas aqui, por la misma razon que el resto de la
# normalizacion (FD-U11-2): si lo convirtiera el modelo, dos corridas del mismo
# commit podrian escribir valores distintos para el mismo turno.
#
# **Un valor que no se puede convertir no se escribe.** Es lo contrario de la placa,
# que se conserva tal como se dijo: una placa dudosa sigue siendo una placa, pero un
# "uso: a veces" no es ninguno de los tres usos, y guardarlo dejaria la regla que lo
# lee sin poder disparar. El campo queda sin decir y se vuelve a preguntar.
#
# Son tablas cerradas y bilingues, acotadas a lo que los casos de DS-4 necesitan: se
# amplian el dia que un caso nuevo las pida mas anchas, nunca adivinando.

#: Las palabras que valen un numero, por idioma. Sin "y" compuesta mas alla de las
#: decenas: nadie dicta los anios de licencia como "ciento veinte".
_NUMBER_WORDS: dict[Locale, dict[str, int]] = {
    "es": {
        "cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4,
        "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
        "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
        "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
        "veinte": 20, "veintiuno": 21, "veintidos": 22, "veintitres": 23,
        "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26, "veintisiete": 27,
        "veintiocho": 28, "veintinueve": 29, "treinta": 30, "cuarenta": 40,
        "cincuenta": 50, "sesenta": 60,
    },
    "en": {
        "zero": 0, "one": 1, "once": 1, "twice": 2, "two": 2, "three": 3, "four": 4,
        "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
        "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
        "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    },
}  # fmt: skip

#: Lo que vale cero cuando es **toda** la respuesta o su primera palabra.
_ZERO_WORDS: dict[Locale, frozenset[str]] = {
    "es": frozenset({"ninguno", "ninguna", "ningun", "nunca", "nada", "no"}),
    "en": frozenset({"none", "never", "nothing", "no"}),
}

#: "menos de un ano": el nuevo conductor, que la regla de licencia nueva deriva.
_LESS_THAN_A_YEAR: dict[Locale, re.Pattern[str]] = {
    "es": re.compile(r"\b(menos de (un|1) ano|recien (saque|obtuve|me dieron))\b"),
    "en": re.compile(r"\b(less than (a|one|1) year|just (got|got my|received))\b"),
}

_TENS = frozenset({20, 30, 40, 50, 60})
_DIGITS = re.compile(r"\d{1,3}")
_YEAR_4 = re.compile(r"(?<!\d)(\d{4})(?!\d)")
_YEARS_UNIT: dict[Locale, re.Pattern[str]] = {
    "es": re.compile(r"\banos?\b"),
    "en": re.compile(r"\byears?\b"),
}


def _tokens(text: str) -> list[str]:
    """Las palabras del texto, plegadas (sin tildes ni mayusculas ni puntuacion)."""
    return re.findall(r"[a-z0-9]+", fold_and_collapse(text))


def parse_count(text: str, *, language: Locale) -> int | None:
    """Un conteo dicho con cifras o con palabras, o `None` si no hay ninguno.

    Cifras primero: "tengo 8 anios" es 8 aunque la frase traiga otra palabra que
    valga un numero. Despues palabras: "cinco", "treinta y cinco", "twenty-five".
    Un "no" o un "ninguno" son cero cuando abren la respuesta, porque la pregunta
    es "cuantos" y "no, ninguno" es la respuesta natural a "cuantos siniestros".
    """
    palabras = _tokens(text)
    if not palabras:
        return None
    for palabra in palabras:
        if _DIGITS.fullmatch(palabra):
            return int(palabra)

    tabla = _NUMBER_WORDS.get(language, {})
    for posicion, palabra in enumerate(palabras):
        valor = tabla.get(palabra)
        if valor is None:
            continue
        if valor in _TENS:
            # "treinta y cinco" / "twenty five": la decena suma la unidad que sigue.
            siguientes = palabras[posicion + 1 : posicion + 3]
            for candidata in siguientes:
                unidad = tabla.get(candidata)
                if unidad is not None and 0 < unidad < 10:
                    return valor + unidad
        return valor

    if palabras[0] in _ZERO_WORDS.get(language, frozenset()):
        return 0
    return None


def normalize_count(text: str, *, language: Locale) -> str | None:
    """Un conteo entero (siniestros, anios), como texto canonico."""
    valor = parse_count(text, language=language)
    return None if valor is None else str(valor)


def normalize_license_years(text: str, *, language: Locale) -> str | None:
    """Los anios con licencia. "Menos de un anio" es cero: lo que la regla de licencia nueva lee."""
    plegado = fold_and_collapse(text)
    if _LESS_THAN_A_YEAR[language].search(plegado):
        return "0"
    return normalize_count(text, language=language)


def normalize_lapse_months(text: str, *, language: Locale) -> str | None:
    """Los meses sin cobertura. Si lo dicho va en anios, se pasa a meses: "un anio" son doce."""
    valor = parse_count(text, language=language)
    if valor is None:
        return None
    plegado = fold_and_collapse(text)
    if _YEARS_UNIT[language].search(plegado):
        valor *= 12
    return str(valor)


def normalize_vehicle_year(text: str, *, now: date) -> str | None:
    """El anio del modelo: cuatro cifras entre 1900 y el anio que viene, o `None`.

    El techo es `now.year + 1` porque los modelos del anio siguiente salen antes de que
    el anio cambie. Un anio de dos cifras no se adivina: "el 98" puede ser 1998 o 2098,
    y se vuelve a preguntar.
    """
    for candidato in _YEAR_4.findall(text):
        anio = int(candidato)
        if 1900 <= anio <= now.year + 1:
            return str(anio)
    return None


def derive_vehicle_age(vehicle_year: str, *, now: date) -> str | None:
    """**El unico sitio donde se calcula la antiguedad del vehiculo** (BR1.4, FD-U19-4).

    Desde el anio del modelo y el reloj que la captura ya inyecta: nunca el reloj del
    proceso, porque dos corridas del mismo caso tienen que dar la misma antiguedad. Una
    regla que comparara contra un anio literal envejece sola; una que compara contra esta
    antiguedad no. Un modelo del anio siguiente da cero, no una antiguedad negativa.
    """
    if not vehicle_year.isdigit():
        return None
    return str(max(0, now.year - int(vehicle_year)))


def derive_lapse_months(prior_coverage_active: str) -> str | None:
    """Los meses sin cobertura de quien **tiene** cobertura vigente hoy: cero.

    `lapse_months` es "meses sin cobertura, cuando no tiene" (estructura de la solicitud).
    Quien la tiene hoy no esta en ese caso, asi que preguntarselo seria pedirle un dato
    que el campo no define para el, y el bloque no terminaria. Quien no la tiene no se
    deriva: se le pregunta.
    """
    return "0" if prior_coverage_active == "true" else None


#: «No tengo idea» empieza por «no» y no es una negativa: es no saber. El reconocedor de las
#: lecturas lo leeria como un no, y aqui un no es un dato que una regla lee (sin titulo de
#: salvamento, sin seguro). Quien no sabe no ha dicho nada, y se le vuelve a preguntar.
_UNSURE: dict[Locale, re.Pattern[str]] = {
    "es": re.compile(r"\b(no (tengo )?idea|ni idea|no (lo )?se|no estoy segur\w*|quien sabe)\b"),
    "en": re.compile(
        r"\b(no idea|not sure|unsure|i do ?n.?t know|do ?n.?t know|no clue|not certain)\b"
    ),
}


def normalize_yes_no(text: str, *, language: Locale) -> str | None:
    """`"true"` o `"false"` para un si/no, o `None` cuando no es ninguno de los dos.

    Reusa el reconocedor de las lecturas de confirmacion --`is_negative` manda primero:
    "no, esta limpio" no puede leerse como un si por traer "claro" o "correcto"--. Una
    respuesta que no es ni si ni no ("esta limpio") no se adivina.
    """
    if _UNSURE[language].search(fold_and_collapse(text)):
        return None
    # Import local: `confirmation` importa `blocks`, y este modulo lo importa la
    # extraccion, que `confirmation` no necesita.
    from untangle.orchestration.nodes.intake import confirmation

    if confirmation.is_negative(text, language=language):
        return "false"
    if confirmation.is_affirmative(text, language=language):
        return "true"
    return None


def _terms(*terms: str) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(terms) + r")\b")


#: El uso del vehiculo, del mas restrictivo al menos: si alguien dice "personal, y a
#: veces entregas", es comercial. Los terminos son raices plegadas.
_USE_TYPE_TERMS: dict[Locale, tuple[tuple[str, re.Pattern[str]], ...]] = {
    "es": (
        ("commercial", _terms(r"comercial\w*", "negocio", "reparto", r"domicilios?", r"entregas?",
                              "taxi", "uber", "didi", "cabify", "plataforma", "flete", "carga",
                              "empresa", "flota")),
        ("commuting", _terms("al trabajo", "trabajar", r"desplaz\w*", "ida y vuelta",
                             r"commut\w*", "a la oficina")),
        ("personal", _terms(r"personal\w*", "familiar", "paseo", "paseos", "particular",
                            "diligencias", "mandados")),
    ),
    "en": (
        ("commercial", _terms(r"commercial\w*", "business", r"deliver\w*", "rideshare",
                              "ride share", "uber", "lyft", "taxi", "courier", "fleet",
                              "cargo", "freight", "for hire")),
        ("commuting", _terms(r"commut\w*", "to work", "to the office", "work commute")),
        ("personal", _terms(r"personal\w*", "family", "pleasure", "errands", "leisure",
                            "recreation")),
    ),
}  # fmt: skip


def normalize_use_type(text: str, *, language: Locale) -> str | None:
    """`personal`, `commuting` o `commercial`, o `None` cuando no es ninguno."""
    plegado = fold_and_collapse(text)
    for valor, patron in _USE_TYPE_TERMS[language]:
        if patron.search(plegado):
            return valor
    return None


#: El recorrido anual, por tramos relativos: nadie sabe su kilometraje exacto, y fijar
#: un numero obligaria a decidir entre millas y kilometros. "Poco" antes que "mucho" para
#: que "no mucho" no se lea como alto.
_MILEAGE_TERMS: dict[Locale, tuple[tuple[str, re.Pattern[str]], ...]] = {
    "es": (
        ("low", _terms("poco", "bajo", "baja", "casi no", "ocasional", "menos de lo normal",
                       "no mucho")),
        ("medium", _terms(r"moderad\w*", "medio", "media", "normal", "promedio", "regular")),
        ("high", _terms("mucho", "alto", "alta", "bastante", "todos los dias", r"intens\w*")),
    ),
    "en": (
        ("low", _terms("low", "little", "rarely", "seldom", "not much", "not a lot")),
        ("medium", _terms(r"moderate\w*", "medium", "average", "normal")),
        ("high", _terms("high", "a lot", "lots", "heavy", "much")),
    ),
}  # fmt: skip


def normalize_mileage_band(text: str, *, language: Locale) -> str | None:
    """`low`, `medium` o `high`, o `None` cuando no es ninguno."""
    plegado = fold_and_collapse(text)
    for valor, patron in _MILEAGE_TERMS[language]:
        if patron.search(plegado):
            return valor
    return None


_VIN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


def normalize_vin(text: str, *, language: Locale, root: Path | None = None) -> str | None:
    """Un VIN de diecisiete caracteres, en mayusculas (sin I, O ni Q), o `None`."""
    for candidato in _candidatos(text, language=language, root=root):
        if _VIN.match(candidato) is not None:
            return candidato
    return None


__all__ = [
    "decode_spelled_code",
    "derive_lapse_months",
    "derive_vehicle_age",
    "normalize_count",
    "normalize_lapse_months",
    "normalize_license_years",
    "normalize_mileage_band",
    "normalize_national_id",
    "normalize_phone",
    "normalize_plate",
    "normalize_policy_number",
    "normalize_relative_date",
    "normalize_use_type",
    "normalize_vehicle_year",
    "normalize_vin",
    "normalize_yes_no",
    "parse_count",
]
