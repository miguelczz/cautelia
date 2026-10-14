"""La poliza que la persona dio, buscada en el corpus y confirmada en una frase (P3, decision de Miguel, 2026-10-06).

**Por que existe.** La captura pedia "su nombre completo y el numero de su poliza",
guardaba lo que llegara y seguia. Si la persona daba solo el numero, la identidad
quedaba completa sin nombre; y el numero nunca se cotejaba con el corpus, asi que
el caso no sabia de que poliza hablaba y la pregunta de cobertura degradaba por
"sin poliza identificada". Miguel pidio que la agente **sepa quien es**: con una
poliza valida, busca al titular y los vehiculos y los confirma en una sola
frase: «Encontre la poliza POL-100042 a nombre de Natalia Henao Rendon, con un
Renault Logan 2024. ¿Es usted y conducia ese carro?». Un "si" confirma identidad
y vehiculo a la vez; un "no" devuelve la identidad a "nadie lo dijo" y se pide de
nuevo, con nombre.

**Nada de esto llama a un modelo.** El numero se reconoce con el patron de la
poliza sobre lo que el extractor devolvio; la busqueda entra **por un puerto que
ya devuelve la coincidencia** (`PolicyMatchPort`), que la raiz de composicion
cablea al corpus de U8; el texto sale del catalogo. Una poliza ajena y una
inexistente responden igual (BR1.2): la politica de fila filtra antes de que el
corpus conteste.

**Este modulo es una hoja y no importa el corpus**, y no es un detalle: el
contrato de capas prohibe que el ritmo del turno llegue a la verificacion de
polizas, ni siquiera de rebote, y `turn.py` importa este modulo por el modelo
`PolicyMatch` que viaja en el punto de control. Por eso el puerto devuelve el
dato ya reducido y la conversion desde la poliza emitida vive en quien si puede
importar el corpus (la raiz). El patron del numero de poliza vive aqui una sola
vez y `identity` lo toma de aqui.

**Lo que se escribe al confirmar no es un dato inventado.** La persona dijo el
numero; el corpus dice el titular y el vehiculo; la persona dijo que si. Los dos
campos quedan con la evidencia del turno del si, que es donde la persona los
hizo suyos.

**Cuando el numero llega mal (2026-10-13).** Por voz, «POL-200117» llego como «Paul 201 17».
`heard_policy_number` reconoce el numero como lo entrega el reconocedor y devuelve lo oido sin
completarlo; `digits_resemble` dice si se parece al de una poliza. Con ellos el nodo puede
**proponer** la poliza del titular que la persona nombro, pero nunca atarla: solo el si lo hace.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from functools import lru_cache

from pydantic import Field

from untangle.base import Frozen, Locale
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration.nodes.intake import spelling
from untangle.tenancy.models import TenantId

#: BR1.6: `POL-` y seis digitos, sin iniciales de aseguradora (la misma forma que
#: siembra el generador sintetico de U7, `synthetic_data.models.POLICY_NUMBER_PATTERN`;
#: se repite aqui en vez de importarla porque esa forma es un formato del dominio del
#: asegurado, no un detalle del generador de datos de prueba, y `orchestration` no
#: importa `synthetic_data`). `identity` la toma de aqui: una sola definicion.
POLICY_NUMBER_PATTERN = re.compile(r"^POL-\d{6}$")
#: La misma forma, suelta dentro de una frase ("mi poliza es la POL-100042").
_POLICY_NUMBER_IN_TEXT = re.compile(r"\bPOL-\d{6}\b")

POLICY_FOUND = CopyKey("intake.policy.found")
POLICY_FOUND_NO_VEHICLE = CopyKey("intake.policy.found_no_vehicle")
POLICY_DECLINED = CopyKey("intake.policy.declined")
POLICY_CONFIRM_AGAIN = CopyKey("intake.policy.confirm_again")
POLICY_CONFIRM_AGAIN_DRIVER = CopyKey("intake.policy.confirm_again_driver")
POLICY_CONFIRMED_IDENTITY = CopyKey("intake.policy.confirmed_identity")
POLICY_CONFIRMED_VEHICLE = CopyKey("intake.policy.confirmed_vehicle")
#: Lo que se dice cuando el numero oido no existe o llego incompleto y no hay a quien
#: proponer: no se encontro, y se pide repetirlo cifra por cifra (una sola vez).
POLICY_NOT_FOUND_REPEAT = CopyKey("intake.policy.not_found_repeat")


def _palabras(texto: str) -> set[str]:
    sin_tildes = unicodedata.normalize("NFKD", texto.casefold())
    return set(
        re.findall(r"[a-z0-9]+", "".join(c for c in sin_tildes if not unicodedata.combining(c)))
    )


def names_holder(text: str, holder_name: str) -> bool:
    """Si el texto nombra al titular: todas las palabras de su nombre, con dos al menos.

    "Soy Natalia Henao Rendon, mi poliza es POL-100042" nombra a "Natalia Henao
    Rendon"; "Soy Natalia, la de la POL-100042" no, y se pregunta (2026-10-09).
    """
    del_titular = _palabras(holder_name)
    return len(del_titular) >= 2 and del_titular <= _palabras(text)


class PolicyMatch(Frozen):
    """Lo que el corpus dice de la poliza que la persona dio. Viaja en el punto de
    control hasta que la persona confirme o niegue."""

    policy_number: str
    holder_name: str
    #: El primer vehiculo de la poliza, como lo describe el corpus ("Renault Logan
    #: 2024"), o `None` si la poliza no trae ninguno.
    vehicle: str | None


#: Como el nodo pregunta por una poliza: el numero entra, la coincidencia sale, o
#: `None` si no existe en esta aseguradora. Lo cablea la raiz de composicion al
#: corpus de U8; aqui no se importa.
PolicyMatchPort = Callable[[TenantId, str], Awaitable[PolicyMatch | None]]

#: Como el nodo busca por nombre (2026-10-13): lo que la persona dijo entra, y salen **todas** las
#: polizas de esa aseguradora cuyo titular el texto nombra entero (`names_holder`). Lo cablea la
#: raiz de composicion al corpus de U8 por el punto unico de sesion; aqui no se importa. Vacio si
#: nadie esta nombrado: no hay modo de preguntar por "las polizas de todos".
PolicyByHolderPort = Callable[[TenantId, str], Awaitable[Sequence[PolicyMatch]]]


# --- Como se reconoce un numero de poliza dicho en voz alta -------------------------------
#
# Lo que entrega el reconocedor de una llamada no se parece a lo que se teclea. Una poliza
# dictada como «POL-200117» llego (2026-10-13) como «Paul 201 17», y en el chat llega con
# guiones, puntos o espacios. Se reconoce **sin modelo y con las palabras como dato**: la
# palabra que nombra el codigo (deformada), las cifras en grupos o en palabras, y la
# distancia a lo que no es una poliza --un telefono, una cedula, una placa, una fecha--.

#: Cuantas cifras tiene un numero de poliza.
POLICY_DIGITS = 6

#: Menos cifras que estas, pegadas a la palabra «poliza», no son un numero oido sino un
#: numero cualquiera que sigue a la palabra: «tengo poliza. 2 carros fueron golpeados».
MIN_HEARD_DIGITS = 3

#: Menos cifras oidas que estas no bastan para decir que «se parecen» a una poliza: con tres
#: de seis, medio corpus se parece.
MIN_RESEMBLING_DIGITS = 4

#: Cuantas cifras pueden faltar, como mucho, para que lo oido se parezca a una poliza.
MAX_MISSING_DIGITS = 2

#: La palabra que nombra el numero de poliza, y como llega «POL» deformada por el
#: reconocedor, que la oye como un nombre o como una palabra corriente.
_PALABRAS_DE_POLIZA = frozenset({"poliza", "polizas", "policy", "policies"})
_PALABRAS_DEL_CODIGO = frozenset({"pol", "pole", "poll", "pool", "paul", "paula", "poul"})
_ANCLAS = _PALABRAS_DE_POLIZA | _PALABRAS_DEL_CODIGO

#: Lo que puede ir entre la palabra de la poliza y sus cifras sin que deje de ser «su»
#: numero: «la poliza es la 200117», «my policy number is 200117».
_RELLENOS = frozenset(
    {
        "es", "la", "el", "numero", "nro", "no", "n", "de", "del", "mi", "ese", "esa", "seria",
        "tiene", "tengo", "que", "is", "the", "number", "my", "it", "its", "s", "was", "are",
    }
)  # fmt: skip
_RELLENOS_MAXIMOS = 3

#: Las palabras que dicen que las cifras que siguen son de **otro** dato: un telefono, una
#: cedula, una placa. Esos reconocedores viven en `compliance/redaction/`; aqui no se
#: duplican sus formatos: solo se evita tomar por poliza lo que una de estas palabras anuncia.
_OTRO_DATO = frozenset(
    {
        "telefono", "tel", "celular", "cel", "movil", "whatsapp", "wasap", "llamar", "llamame",
        "llame", "llamarme", "llamenme", "cedula", "documento", "identificacion", "cc", "nit",
        "placa", "placas", "matricula", "phone", "mobile", "cell", "call", "id", "license", "plate",
    }
)  # fmt: skip
_PALABRAS_ATRAS_DE_OTRO_DATO = 3

#: Una fecha escrita con cifras, que no puede ser parte de un numero de poliza. Se tapa
#: antes de buscar: «13-10-26» son seis cifras separadas por guiones, igual que una poliza
#: dictada en grupos.
_FECHA = re.compile(
    r"\b(?:\d{1,2}[/\-.]\d{1,2}[/\-.](?:\d{4}|\d{2})|\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2})\b"
)

#: Las piezas del texto ya plegado: cifras (`n`), palabras (`w`), punto o coma (`p`) y
#: cualquier otra marca que corta (`b`). Espacios, guiones, `#` y comillas no cuentan.
_PIEZA = re.compile(r"(?P<n>\d+)|(?P<w>[a-z]+)|(?P<p>[.,])|(?P<b>[^a-z\d\s\-#'\".,])")


class HeardPolicyNumber(Frozen):
    """Lo que la persona dijo como numero de poliza, tal como lo entrego el reconocedor.

    **Solo las cifras, sin completar ni corregir.** Con exactamente seis es un numero de
    poliza (`number`); con otra cantidad es un numero incompleto o de mas, y quien lo recibe
    decide que hacer, pero no se inventa nada: adivinar la cifra que falta podria acertar
    por casualidad y asociar el caso a la poliza de otra persona (BR1.6).
    """

    digits: str = Field(pattern=r"^\d+$")

    @property
    def complete(self) -> bool:
        return len(self.digits) == POLICY_DIGITS

    @property
    def number(self) -> str | None:
        """`POL-` y las seis cifras, o `None` si no son seis."""
        return f"POL-{self.digits}" if self.complete else None


@dataclass(frozen=True)
class _Pieza:
    tipo: str
    texto: str
    inicio: int
    fin: int


@dataclass(frozen=True)
class _Corrida:
    """Cifras seguidas --en grupos, en palabras o mezcladas-- y si la poliza va pegada."""

    cifras: str
    primera: int
    anclada: bool


def _plegar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(c for c in sin_tildes if not unicodedata.combining(c))


@lru_cache(maxsize=1)
def _palabras_de_cifra() -> dict[str, str]:
    """Las cifras dichas en palabras, en los dos idiomas: «cero», «siete», «zero», «seven»."""
    tabla: dict[str, str] = {"una": "1"}
    for por_idioma in spelling.load().digit_words.values():
        tabla.update(por_idioma)
    return tabla


def _piezas(texto: str) -> list[_Pieza]:
    plegado = _FECHA.sub(" ; ", _plegar(texto))
    piezas = [
        _Pieza(tipo=m.lastgroup or "b", texto=m.group(0), inicio=m.start(), fin=m.end())
        for m in _PIEZA.finditer(plegado)
    ]
    return _fusionar_deletreo(piezas)


def _fusionar_deletreo(piezas: list[_Pieza]) -> list[_Pieza]:
    """«P O L» y «P. O. L.» son la palabra `pol`: asi se deletrea el prefijo."""
    salida: list[_Pieza] = []
    i = 0
    while i < len(piezas):
        letras: list[_Pieza] = []
        j = i
        while j < len(piezas) and len(letras) < 3 and _es_letra_suelta(piezas[j]):
            letras.append(piezas[j])
            j += 1
            if j < len(piezas) and piezas[j].tipo == "p":
                j += 1
        if [p.texto for p in letras] == ["p", "o", "l"]:
            salida.append(_Pieza("w", "pol", letras[0].inicio, letras[-1].fin))
            i = j
        else:
            salida.append(piezas[i])
            i += 1
    return salida


def _es_letra_suelta(pieza: _Pieza) -> bool:
    return pieza.tipo == "w" and len(pieza.texto) == 1


def _cifras_de(pieza: _Pieza) -> str | None:
    if pieza.tipo == "n":
        return pieza.texto
    if pieza.tipo == "w":
        return _palabras_de_cifra().get(pieza.texto)
    return None


def _anclada(piezas: list[_Pieza], primera: int) -> bool:
    """Si la palabra de la poliza (o la del codigo) va pegada a las cifras que empiezan en `primera`.

    Entre una y otras solo caben los rellenos de «la poliza es la...», y el punto o la coma
    con que cada final del reconocedor cierra su trozo, y los dos puntos de «poliza: 200117».
    """
    rellenos = 0
    for pieza in reversed(piezas[:primera]):
        if pieza.tipo == "p" or (pieza.tipo == "b" and pieza.texto == ":"):
            continue
        if pieza.tipo == "w" and pieza.texto in _ANCLAS:
            return True
        if pieza.tipo == "w" and pieza.texto in _RELLENOS and rellenos < _RELLENOS_MAXIMOS:
            rellenos += 1
            continue
        return False
    return False


def _corridas(piezas: list[_Pieza]) -> list[_Corrida]:
    """Las tiradas de cifras. Un punto o una coma entre dos grupos las une si van pegados
    al siguiente (`200.117`) o si todavia no hay seis cifras (el final de un trozo y el
    principio del siguiente); con seis ya reunidas, un punto cierra la tirada."""
    corridas: list[_Corrida] = []
    i = 0
    while i < len(piezas):
        cifras = _cifras_de(piezas[i])
        if cifras is None:
            i += 1
            continue
        ultima = i
        while (siguiente := _seguir(piezas, ultima, len(cifras))) is not None:
            ultima, mas_cifras = siguiente
            cifras += mas_cifras
        corridas.append(_Corrida(cifras, i, _anclada(piezas, i)))
        i = ultima + 1
    return corridas


def _seguir(piezas: list[_Pieza], ultima: int, reunidas: int) -> tuple[int, str] | None:
    """El grupo de cifras que continua la tirada que acaba en `ultima`, o `None`."""
    k = ultima + 1
    while k < len(piezas) and piezas[k].tipo == "p":
        k += 1
    if k >= len(piezas):
        return None
    cifras = _cifras_de(piezas[k])
    if cifras is None:
        return None
    marcas = k - ultima - 1
    if marcas:
        pegado = marcas == 1 and piezas[k - 1].fin == piezas[k].inicio
        if not pegado and (marcas > 1 or reunidas >= POLICY_DIGITS):
            return None
    return k, cifras


def _va_con_otro_dato(piezas: list[_Pieza], primera: int) -> bool:
    """Si una de las tres palabras antes de las cifras anuncia un telefono, una cedula, una placa."""
    vistas = 0
    for pieza in reversed(piezas[:primera]):
        if pieza.tipo == "p":
            continue
        if pieza.tipo != "w" or vistas >= _PALABRAS_ATRAS_DE_OTRO_DATO:
            return False
        if pieza.texto in _OTRO_DATO:
            return True
        vistas += 1
    return False


def heard_policy_number(text: str) -> HeardPolicyNumber | None:
    """El numero de poliza que hay en lo que la persona dijo, completo o no, o `None`.

    Reconoce, por orden:

    1. `POL-` y seis cifras (lo que se teclea).
    2. Cifras pegadas a la palabra «poliza» o a la que nombra el codigo --«Paul», «Pol»,
       «Poll», «Paula», «pool», «pole»--, en grupos («201 17», «2001 17»), sueltas
       («2 0 0 1 1 7»), con guiones, puntos o comas, o dichas en palabras en espanol o en
       ingles («dos cero cero uno uno siete»), mezcladas tambien, y con los rellenos de «la
       poliza es la...» en medio. **De tres cifras en adelante**, completas o no.
    3. Seis cifras sin palabra pegada, si el texto nombra la poliza en otro sitio o es solo el
       numero --la respuesta a «¿cual es?»--, salvo que una palabra anuncie otro dato
       (`telefono`, `cedula`, `placa`...) o que sean una fecha.

    **Con otra cantidad de cifras que seis no se inventa nada**: se devuelve lo oido, y
    `complete` es falso. Las cifras de un telefono, una cedula, una placa o una fecha en la
    misma frase no se toman por la poliza.
    """
    exacto = _POLICY_NUMBER_IN_TEXT.search(text.upper())
    if exacto is not None:
        return HeardPolicyNumber(digits=exacto.group(0).removeprefix("POL-"))

    piezas = _piezas(text)
    corridas = _corridas(piezas)
    ancladas = [c for c in corridas if c.anclada and len(c.cifras) >= MIN_HEARD_DIGITS]
    completa = next((c for c in ancladas if len(c.cifras) == POLICY_DIGITS), None)
    if completa is not None:
        return HeardPolicyNumber(digits=completa.cifras)
    if ancladas:
        return HeardPolicyNumber(digits=ancladas[0].cifras)

    # Seis cifras sin palabra pegada: el reconocimiento de 2026-10-09.
    nombra_la_poliza = any(p.tipo == "w" and p.texto in _ANCLAS for p in piezas)
    # O el numero solo, contestando la pregunta: cuando hace una pausa para pensarlo, el
    # numero llega en su propio turno ("dos cero cero uno uno siete").
    palabras = sum(1 for p in piezas if p.tipo == "w" and _cifras_de(p) is None)
    for corrida in corridas:
        if len(corrida.cifras) != POLICY_DIGITS or _va_con_otro_dato(piezas, corrida.primera):
            continue
        if nombra_la_poliza or palabras <= 1:
            return HeardPolicyNumber(digits=corrida.cifras)
    return None


def policy_number_in(text: str) -> str | None:
    """El numero de poliza que hay en lo que la persona dijo, o `None`.

    Por voz llega sin el prefijo (2026-10-09) y deformado (2026-10-13): ver
    `heard_policy_number`. Aqui solo cuenta el que tiene **exactamente seis cifras**; uno
    incompleto no es una poliza, y quien quiera tratarlo pide `heard_policy_number`.
    """
    oido = heard_policy_number(text)
    return oido.number if oido is not None else None


def digits_resemble(heard: str, policy_number: str) -> bool:
    """Si lo oido se parece al numero de una poliza: la regla **conservadora** de «se parecen».

    Dos formas y no mas, con al menos cuatro cifras oidas (`MIN_RESEMBLING_DIGITS`):

    - **Faltan como mucho dos cifras y las oidas van en orden**: son una subsecuencia de las
      seis de la poliza (`20117` frente a `200117`: el reconocedor se comio un cero). Es el
      fallo corriente de un numero dictado.
    - **Con las seis oidas, una sola es distinta** (`200118` frente a `200117`).

    No se parecen tres cifras de menos, dos distintas, cifras fuera de orden ni cifras de
    mas. Que se parezca **no ata nada**: solo deja proponer la poliza, y la persona dice si.
    """
    cifras = policy_number.removeprefix("POL-")
    if not heard.isdigit() or len(heard) < MIN_RESEMBLING_DIGITS or len(heard) > len(cifras):
        return False
    if len(heard) == len(cifras):
        return sum(1 for a, b in zip(heard, cifras, strict=True) if a != b) <= 1
    if len(cifras) - len(heard) > MAX_MISSING_DIGITS:
        return False
    restantes = iter(cifras)
    return all(cifra in restantes for cifra in heard)


async def look_up(tenant_id: TenantId, text: str, *, lookup: PolicyMatchPort) -> PolicyMatch | None:
    """La poliza nombrada en el texto, si existe en esta aseguradora."""
    numero = policy_number_in(text)
    if numero is None:
        return None
    coincidencia = await lookup(tenant_id, numero)
    if coincidencia is None or not coincidencia.holder_name:
        return None
    return coincidencia


def compose_found(
    match: PolicyMatch, *, language: Locale, asks_driver: bool = True
) -> tuple[CopyKey, str]:
    """La frase que confirma al titular, y su clave.

    Quien manejaba solo se pregunta en un reporte de choque: en una consulta o una
    cotizacion "¿conducia ese carro?" no tiene sentido (visto en produccion el
    2026-10-08), y basta con "¿es usted?".
    """
    if match.vehicle is None or not asks_driver:
        return POLICY_FOUND_NO_VEHICLE, copy_api.t(
            POLICY_FOUND_NO_VEHICLE,
            locale=language,
            policy=match.policy_number,
            name=match.holder_name,
        )
    return POLICY_FOUND, copy_api.t(
        POLICY_FOUND,
        locale=language,
        policy=match.policy_number,
        name=match.holder_name,
        vehicle=match.vehicle,
    )


def compose_confirm_again(
    match: PolicyMatch, *, language: Locale, asks_driver: bool = True
) -> tuple[CopyKey, str]:
    """La misma pregunta otra vez, cuando la respuesta no fue ni si ni no (2026-10-14).

    Pregunta lo mismo que `compose_found` --identidad y, en un reporte con vehiculo, quien
    manejaba--, para que un si confirme exactamente lo que confirmaba la primera vez.
    """
    if match.vehicle is None or not asks_driver:
        return POLICY_CONFIRM_AGAIN, copy_api.t(
            POLICY_CONFIRM_AGAIN, locale=language, name=match.holder_name
        )
    return POLICY_CONFIRM_AGAIN_DRIVER, copy_api.t(
        POLICY_CONFIRM_AGAIN_DRIVER, locale=language, name=match.holder_name
    )


def compose_declined(*, language: Locale) -> str:
    """Lo que se dice cuando la persona dice que no es ella: se vuelve a pedir."""
    return copy_api.t(POLICY_DECLINED, locale=language)


def compose_not_found_repeat(*, language: Locale) -> str:
    """Lo que se dice cuando el numero oido no lleva a ninguna poliza: no se encontro y se
    pide repetirlo cifra por cifra. Sin cifras en la frase: no hay numero que leerle."""
    return copy_api.t(POLICY_NOT_FOUND_REPEAT, locale=language)


def confirmed_identity_value(match: PolicyMatch, *, language: Locale) -> str:
    """Lo que queda guardado como identidad y poliza al confirmar."""
    return copy_api.t(
        POLICY_CONFIRMED_IDENTITY,
        locale=language,
        name=match.holder_name,
        policy=match.policy_number,
    )


def confirmed_vehicle_value(match: PolicyMatch, *, language: Locale) -> str | None:
    """Lo que queda guardado como vehiculo y conductor al confirmar, si hay vehiculo."""
    if match.vehicle is None:
        return None
    return copy_api.t(POLICY_CONFIRMED_VEHICLE, locale=language, vehicle=match.vehicle)


__all__ = [
    "POLICY_CONFIRM_AGAIN",
    "POLICY_CONFIRM_AGAIN_DRIVER",
    "POLICY_DECLINED",
    "POLICY_FOUND",
    "POLICY_FOUND_NO_VEHICLE",
    "POLICY_NOT_FOUND_REPEAT",
    "POLICY_NUMBER_PATTERN",
    "HeardPolicyNumber",
    "PolicyByHolderPort",
    "PolicyMatch",
    "PolicyMatchPort",
    "compose_confirm_again",
    "compose_declined",
    "compose_found",
    "compose_not_found_repeat",
    "confirmed_identity_value",
    "confirmed_vehicle_value",
    "digits_resemble",
    "heard_policy_number",
    "look_up",
    "policy_number_in",
]
