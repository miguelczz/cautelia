"""El numero de caso legible: tres letras de la aseguradora y seis digitos.

Es lo que la persona anota al cerrar, lo que la agente le dicta digito a digito,
y con lo que vuelve a retomar su caso. Por eso **no cambia nunca** una vez
creado (BR4.3): cambiarlo deja a alguien sin forma de volver.

Los tres prefijos de la demostracion son `STO`, `SUN` y `KNO`, elegidos para no
confundirse entre si al dictarse (decision FD-U4-1 de Miguel). Las maquetas
usaban `SMU` y `SMA`, que se diferencian en una sola letra y nombran
aseguradoras distintas; dictados por telefono suenan casi igual, y el propio
diseno de la voz reconoce ese riesgo obligando a deletrear con una palabra las
letras que se confunden.

El prefijo sale de la configuracion de la aseguradora y **nunca de una tabla en
este archivo** (BR4.1): una correspondencia escrita aqui seria la ramificacion
por inquilino que el proyecto prohibe, y anadir una cuarta aseguradora dejaria
de ser anadir una carpeta.
"""

from __future__ import annotations

import secrets

from untangle.case_record.models import CaseNumber
from untangle.tenancy import config
from untangle.tenancy.models import TenantConfig

#: Cuantos digitos lleva el numero. Seis, como fija FR1.5.
DIGITS = 6

#: El mayor numero representable con esos digitos, mas uno.
_RANGO = 10**DIGITS


class PrefixCollisionError(RuntimeError):
    """Dos aseguradoras declaran el mismo prefijo de numero de caso.

    Es condicion de arranque y no una advertencia (BR4.2). Con dos prefijos
    iguales, dos casos de aseguradoras distintas pueden compartir numero, y
    entonces el numero deja de identificar un caso: la persona que lo dicta y
    quien lo busca estarian hablando de cosas distintas sin saberlo.
    """


def assert_prefixes_are_distinct(tenants: tuple[TenantConfig, ...] | None = None) -> None:
    """Comprueba en el arranque que ningun prefijo se repite (BR4.2).

    Vive aqui y no en el cargador de U2 a proposito. Ese cargador apaga **solo
    la carpeta rota**, y un prefijo repetido no rompe ninguna de las dos
    carpetas por separado: es una propiedad del conjunto. La comprueba quien
    depende de ella.
    """
    cargadas = tenants if tenants is not None else config.loaded().available

    por_prefijo: dict[str, list[str]] = {}
    for tenant in cargadas:
        por_prefijo.setdefault(tenant.case_number_prefix, []).append(tenant.tenant_id)

    repetidos = {p: sorted(ids) for p, ids in por_prefijo.items() if len(ids) > 1}
    if repetidos:
        detalle = "; ".join(f"'{p}' lo declaran {ids}" for p, ids in sorted(repetidos.items()))
        msg = (
            f"dos aseguradoras comparten prefijo de numero de caso: {detalle}. "
            "Con el mismo prefijo, dos casos distintos pueden compartir numero (BR4.2)"
        )
        raise PrefixCollisionError(msg)


def _serial() -> str:
    """Seis digitos, con ceros a la izquierda.

    Se eligen al azar y no de forma correlativa. Un numero correlativo publica
    cuantos casos lleva la demostracion y deja adivinar el siguiente; el numero
    no es credencial --el acceso lo decide el enlace firmado de U2 (SEC-U4.14)--
    pero no hay razon para regalar lo uno ni lo otro.
    """
    return f"{secrets.randbelow(_RANGO):0{DIGITS}d}"


def mint(tenant_id: str, *, taken: frozenset[str] = frozenset()) -> CaseNumber:
    """Un numero nuevo para esa aseguradora, distinto de los que ya existen.

    `taken` son los seriales ya usados por esa aseguradora, que el repositorio
    consulta. La unicidad es **dentro de la aseguradora** (BR4.3): dos
    aseguradoras pueden tener el mismo serial porque su prefijo las separa.
    """
    tenant = config.require(tenant_id)

    # El espacio es de un millon por aseguradora y la demostracion no se acerca,
    # asi que reintentar es barato. El limite existe para que un espacio agotado
    # falle diciendolo, en vez de girar para siempre.
    for _ in range(100):
        serial = _serial()
        if serial not in taken:
            return CaseNumber(prefix=tenant.case_number_prefix, serial=serial)

    msg = (
        f"no se encontro un numero libre para '{tenant_id}' en cien intentos: "
        f"quedan muy pocos de los {_RANGO} posibles"
    )
    raise RuntimeError(msg)


def parse(value: str) -> CaseNumber:
    """Lee un numero escrito, como el que teclea quien retoma su caso.

    Acepta la forma exacta y nada mas. Ser permisivo aqui --aceptar minusculas,
    espacios o un guion de mas-- haria que el mismo caso se escribiera de varias
    maneras, y la busqueda por numero dejaria de encontrarlo.
    """
    partes = value.split("-")
    if len(partes) != 2:
        msg = f"'{value}' no tiene la forma de un numero de caso: tres letras, guion, seis digitos"
        raise ValueError(msg)
    return CaseNumber(prefix=partes[0], serial=partes[1])
