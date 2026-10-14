"""Las personas y los vehiculos ficticios del corpus (F3.2, paso 4; BR7.1).

Cada dato con forma de dato personal se **compone desde la semilla** y lleva una
forma que lo delata como ficticio, nunca se copia de un registro:

- **Nombres**: nombre y apellidos elegidos de los repertorios escritos a mano
  (`<prefijo>-POOL-GIVEN-NAMES` y `-FAMILY-NAMES`, CG-U7-2). En espanol, un nombre
  y dos apellidos; en ingles, un nombre y un apellido.
- **Telefonos**: del rango 555-01XX, que no se asigna a nadie (ADR-016): un movil
  de Colombia (`310 555 0142`) o un numero de Estados Unidos (`212-555-0142`).
- **Documentos**: una cedula de ocho digitos con puntos de millar (`43.218.907`), o
  un numero de la forma `9dd-gg-dddd` con el grupo entre 01 y 49: un 9 inicial no
  se asigna como numero de seguridad social, y los grupos 01 a 49 tampoco son de
  los numeros de contribuyente que si empiezan por 9.
- **Correos**: en `example.com` o `example.org`, dominios reservados.
- **Placas**: con la forma de cada idioma (`KTR482`, `KTR-4821`).
- **VIN**: diecisiete caracteres cuyo digito de control **falla** a proposito.

Todo sale de un elegidor sembrado que recibe quien compone la poliza o el caso;
este modulo no pide flujos por su cuenta. Los repertorios se buscan **por
idioma**: se escriben una vez en la carpeta de la emisora que redacta en ese
idioma, y los usan tambien los casos de la agencia y los del otro idioma.
"""

from __future__ import annotations

import unicodedata
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Final

from untangle.base import Locale
from untangle.synthetic_data.chooser import SeededChooser
from untangle.synthetic_data.models import (
    PersonalValueKind,
    PersonaRef,
    SourceKind,
    SourceText,
    VehicleRef,
    pool_items,
    vin_check_digit,
)

__all__ = [
    "FAMILY_NAMES",
    "GIVEN_NAMES",
    "VEHICLES",
    "People",
    "PeopleError",
    "Pools",
    "UsedValues",
    "compose_name",
    "compose_persona",
    "compose_plate",
    "compose_relative_name",
    "compose_unique_name",
    "compose_vehicle",
    "spoken_digits",
]

#: Los nombres de los repertorios: la parte de `source_id` que sigue a `-POOL-`.
GIVEN_NAMES: Final = "GIVEN-NAMES"
FAMILY_NAMES: Final = "FAMILY-NAMES"
VEHICLES: Final = "VEHICLES"

#: Las letras de una placa: sin I, O ni Q, que se confunden con 1, 0 y O al dictar.
_LETRAS_DE_PLACA: Final = "ABCDEFGHJKLMNPRSTUVWXYZ"
#: Los caracteres validos de un VIN (ISO 3779): sin I, O ni Q.
_CARACTERES_DE_VIN: Final = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
_DIGITOS_DE_CONTROL: Final = "0123456789X"

#: Prefijos moviles de Colombia (todos empiezan por 3) y codigos de area de Estados
#: Unidos. Solo dan verosimilitud: lo que hace ficticio al numero es el 555-01XX.
_PREFIJOS_MOVILES: Final = ("300", "301", "304", "310", "311", "312", "313", "315", "316", "320")
_CODIGOS_DE_AREA: Final = ("212", "303", "312", "415", "503", "602", "617", "702", "713", "919")

#: Los anos de modelo de los vehiculos.
_PRIMER_MODELO: Final = 2012
_ULTIMO_MODELO: Final = 2025

_PALABRAS: Final[dict[Locale, tuple[str, ...]]] = {
    "es": ("cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve"),
    "en": ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"),
}

#: Cuantas veces se vuelve a elegir si un valor ya se uso. Con los repertorios y
#: los rangos de este corpus basta con una o dos; el tope existe para que un
#: repertorio demasiado corto falle diciendolo en vez de girar para siempre.
_INTENTOS: Final = 50


class PeopleError(ValueError):
    """Falta un repertorio o se agotaron los valores distintos que puede dar."""


@dataclass
class UsedValues:
    """Los valores personales ya sembrados: dos personas no comparten telefono ni placa.

    Los nombres si pueden repetirse cuando alguien lo pide a proposito --DS-8
    siembra el mismo nombre en dos aseguradoras--, y por eso `claim` no se usa
    para un nombre impuesto.
    """

    taken: set[tuple[PersonalValueKind, str]] = field(default_factory=set)

    def claim(self, kind: PersonalValueKind, value: str) -> bool:
        """Reserva el valor. Dice si estaba libre."""
        clave = (kind, value)
        if clave in self.taken:
            return False
        self.taken.add(clave)
        return True


@dataclass(frozen=True)
class People:
    """Lo que hace falta para componer personas: los repertorios y los valores ya usados."""

    pools: Pools
    used: UsedValues


@dataclass(frozen=True)
class Pools:
    """Los repertorios escritos a mano, por idioma y por nombre."""

    items: dict[tuple[Locale, str], tuple[str, ...]]

    @classmethod
    def from_sources(cls, texts: Iterable[SourceText]) -> Pools:
        """Junta los repertorios de todas las fuentes, ordenados por identificador.

        Si dos emisoras escriben en el mismo idioma, sus repertorios se unen: un
        nombre plausible en espanol lo es en cualquier aseguradora.
        """
        juntos: dict[tuple[Locale, str], list[str]] = defaultdict(list)
        for texto in sorted(texts, key=lambda t: t.source_id):
            if texto.kind not in {SourceKind.PERSONA_POOL, SourceKind.VEHICLE_POOL}:
                continue
            nombre = texto.source_id.split("-POOL-", 1)[1]
            for elemento in pool_items(texto.text, where=texto.source_id):
                if elemento not in juntos[(texto.language, nombre)]:
                    juntos[(texto.language, nombre)].append(elemento)
        return cls(items={clave: tuple(valores) for clave, valores in juntos.items()})

    def get(self, language: Locale, name: str) -> tuple[str, ...]:
        """Un repertorio, o un `PeopleError` que nombra cual falta."""
        valores = self.items.get((language, name))
        if not valores:
            msg = (
                f"falta el repertorio {name} en '{language}': se escribe a mano como "
                f"<prefijo>-POOL-{name} en el pools.yaml de una emisora de ese idioma"
            )
            raise PeopleError(msg)
        return valores


def _ascii(texto: str) -> str:
    """Sin tildes ni signos, en minusculas: la parte local de un correo."""
    plano = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return "".join(c for c in plano.lower() if c.isalnum())


def _unico(
    chooser: SeededChooser, used: UsedValues, kind: PersonalValueKind, make: Callable[[], str]
) -> str:
    """Elige hasta dar con un valor libre, o falla diciendo cual se agoto."""
    for _ in range(_INTENTOS):
        valor = make()
        if used.claim(kind, valor):
            return valor
    msg = f"no quedan valores de tipo {kind.value} distintos en el flujo '{chooser.stream}'"
    raise PeopleError(msg)


def compose_name(chooser: SeededChooser, pools: Pools, language: Locale) -> str:
    """Un nombre plausible en el idioma: nombre y uno o dos apellidos."""
    nombre = chooser.choice(pools.get(language, GIVEN_NAMES))
    apellidos = pools.get(language, FAMILY_NAMES)
    if language == "es":
        primero, segundo = chooser.sample(apellidos, 2)
        return f"{nombre} {primero} {segundo}"
    return f"{nombre} {chooser.choice(apellidos)}"


def compose_unique_name(chooser: SeededChooser, people: People, language: Locale) -> str:
    """Un nombre que ninguna otra persona del corpus lleva: el de un tercero de un caso."""
    return _unico(
        chooser,
        people.used,
        PersonalValueKind.NAME,
        lambda: compose_name(chooser, people.pools, language),
    )


def compose_relative_name(
    chooser: SeededChooser,
    people: People,
    language: Locale,
    *,
    holder_name: str,
    taken_given_names: frozenset[str],
) -> str:
    """El nombre de un familiar del titular: un nombre de pila nuevo y los apellidos de la casa.

    En espanol el primer apellido del titular y un segundo de los repertorios; en ingles su
    apellido. Es el conductor adicional que mas se ve en una poliza real --un hijo, una pareja--
    y el que pone a prueba la comparacion de nombres: comparte apellido con el titular y solo
    el nombre de pila lo distingue. El nombre de pila no repite ninguno de `taken_given_names`
    (en minusculas) y el nombre completo no lo lleva ninguna otra persona del corpus.
    """
    partes = holder_name.split()
    # El primer apellido en espanol (despues del nombre), el unico apellido en ingles (el ultimo).
    casa = partes[1] if language == "es" and len(partes) > 1 else partes[-1]
    apellidos = people.pools.get(language, FAMILY_NAMES)
    nombres = people.pools.get(language, GIVEN_NAMES)

    def componer() -> str:
        for _ in range(_INTENTOS):
            nombre = chooser.choice(nombres)
            if nombre.casefold() not in taken_given_names:
                break
        else:
            msg = f"no quedan nombres de pila distintos en el flujo '{chooser.stream}'"
            raise PeopleError(msg)
        if language == "es":
            segundo = chooser.choice(tuple(a for a in apellidos if a != casa))
            return f"{nombre} {casa} {segundo}"
        return f"{nombre} {casa}"

    return _unico(chooser, people.used, PersonalValueKind.NAME, componer)


def _telefono(chooser: SeededChooser, language: Locale) -> str:
    final = chooser.digits(2)
    if language == "es":
        return f"{chooser.choice(_PREFIJOS_MOVILES)} 555 01{final}"
    return f"{chooser.choice(_CODIGOS_DE_AREA)}-555-01{final}"


def _documento(chooser: SeededChooser, language: Locale) -> str:
    if language == "es":
        digitos = f"{chooser.between(1, 9)}{chooser.digits(7)}"
        return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:]}"
    return f"9{chooser.digits(2)}-{chooser.between(1, 49):02d}-{chooser.digits(4)}"


def compose_persona(
    chooser: SeededChooser,
    people: People,
    language: Locale,
    *,
    persona_id: str,
    full_name: str | None = None,
) -> PersonaRef:
    """Una persona ficticia. `full_name` impone el nombre (DS-8) y no lo reserva."""
    used = people.used
    if full_name is None:
        nombre = compose_unique_name(chooser, people, language)
    else:
        nombre = full_name
        used.claim(PersonalValueKind.NAME, nombre)
    partes = nombre.split()
    local = f"{_ascii(partes[0])}.{_ascii(partes[1])}"
    dominio = chooser.choice(("example.com", "example.org"))
    sufijos = ("", *(str(n) for n in range(2, _INTENTOS + 1)))
    correo = next(
        c
        for c in (f"{local}{s}@{dominio}" for s in sufijos)
        if used.claim(PersonalValueKind.EMAIL, c)
    )
    return PersonaRef(
        persona_id=persona_id,
        full_name=nombre,
        phone=_unico(chooser, used, PersonalValueKind.PHONE, lambda: _telefono(chooser, language)),
        national_id=_unico(
            chooser, used, PersonalValueKind.NATIONAL_ID, lambda: _documento(chooser, language)
        ),
        email=correo,
    )


def compose_plate(chooser: SeededChooser, language: Locale, *, used: UsedValues) -> str:
    """Una placa inventada con la forma del idioma, distinta de las ya sembradas."""

    def placa() -> str:
        letras = "".join(chooser.choice(_LETRAS_DE_PLACA) for _ in range(3))
        return (
            f"{letras}{chooser.digits(3)}" if language == "es" else f"{letras}-{chooser.digits(4)}"
        )

    return _unico(chooser, used, PersonalValueKind.PLATE, placa)


def _vin(chooser: SeededChooser) -> str:
    """Un VIN cuyo digito de control falla: once caracteres, el control y seis digitos."""
    cabeza = "".join(chooser.choice(_CARACTERES_DE_VIN) for _ in range(8))
    modelo = "".join(chooser.choice(_CARACTERES_DE_VIN) for _ in range(2))
    serie = chooser.digits(6)
    borrador = f"{cabeza}0{modelo}{serie}"
    correcto = vin_check_digit(borrador)
    erroneo = chooser.choice(tuple(d for d in _DIGITOS_DE_CONTROL if d != correcto))
    return f"{cabeza}{erroneo}{modelo}{serie}"


def compose_vehicle(chooser: SeededChooser, people: People, language: Locale) -> VehicleRef:
    """Un vehiculo ficticio: placa del idioma, modelo del repertorio y VIN que falla."""
    modelo = f"{chooser.choice(people.pools.get(language, VEHICLES))} "
    modelo += str(chooser.between(_PRIMER_MODELO, _ULTIMO_MODELO))
    return VehicleRef(
        plate=compose_plate(chooser, language, used=people.used),
        make_model_year=modelo,
        vin=_unico(chooser, people.used, PersonalValueKind.VIN, lambda: _vin(chooser)),
    )


def spoken_digits(value: str, language: Locale) -> str:
    """Los digitos de un valor dichos uno a uno en el idioma: `uno cero dos...`.

    Es como se dicta un documento por telefono, y es la forma que RT-15 usa para
    probar la redaccion con una cedula dictada en el otro idioma.
    """
    return " ".join(_PALABRAS[language][int(d)] for d in value if d.isdigit())
