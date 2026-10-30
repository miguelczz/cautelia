"""El numero de caso legible: las dos iniciales de la aseguradora y un contador.

Es lo que la persona anota al cerrar, lo que la agente le dicta y con lo que vuelve
a retomar su caso: `SA-1`, `AP-29`, `AC-7`. Por eso **no cambia nunca** una vez
creado (BR4.3): cambiarlo deja a alguien sin forma de volver. La unica vez que se
rompio fue a proposito, por decision de Miguel del 2026-10-30, cuando la revision
`u20_demo_0003_short_numbers` renumero los casos existentes con esta forma.

Los tres prefijos de la demostracion son `SA` (Seguros Aburra), `AP` (Autos
Poblado) y `AC` (Agencia Castilla): las iniciales de la empresa, para que el
numero diga de quien es el caso. Antes eran `STO`, `SUN` y `KNO` seguidos de seis
digitos al azar, y Miguel los encontro dificiles de dictar y de recordar.

El prefijo sale de la configuracion de la aseguradora y **nunca de una tabla en
este archivo** (BR4.1): una correspondencia escrita aqui seria la ramificacion por
inquilino que el proyecto prohibe, y anadir una cuarta aseguradora dejaria de ser
anadir una carpeta.
"""

from __future__ import annotations

from untangle.case_record.models import CaseNumber
from untangle.tenancy import config
from untangle.tenancy.models import TenantConfig

#: Cuantos digitos admite el contador como maximo: el mayor serial es 999999. Lo impone
#: `CaseNumber` y la restriccion de `case_number_issued`; aqui solo se usa para fallar
#: diciendolo cuando una aseguradora lo agote.
MAX_SERIAL = 999_999


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


def mint(tenant_id: str, *, taken: frozenset[str] = frozenset()) -> CaseNumber:
    """El numero que sigue para esa aseguradora: el mayor ya emitido, mas uno.

    `taken` son los seriales ya emitidos por esa aseguradora, que el repositorio lee de
    `case_number_issued`. El libro **sobrevive al reinicio nocturno**, asi que el contador
    no vuelve a empezar y ningun numero se repite (BR2.5 de U20). La unicidad es **dentro de
    la aseguradora** (BR4.3): dos aseguradoras pueden tener el mismo serial porque su prefijo
    las separa.

    Es un contador y no un numero al azar porque el numero nunca fue una credencial: el
    acceso al caso lo da la clave del navegador o el enlace firmado (`chat.resume`), asi que
    adivinar `AP-30` no abre nada. Lo que el contador publica --cuantos casos lleva la
    demostracion-- ya lo publica el panel de cifras. Decision de Miguel del 2026-10-30, para
    que el numero sea facil de decir y de recordar.
    """
    tenant = config.require(tenant_id)
    siguiente = max((int(serial) for serial in taken), default=0) + 1
    if siguiente > MAX_SERIAL:
        msg = f"'{tenant_id}' agoto sus numeros de caso: el contador llego a {MAX_SERIAL}"
        raise RuntimeError(msg)
    return CaseNumber(prefix=tenant.case_number_prefix, serial=str(siguiente))


def parse(value: str) -> CaseNumber:
    """Lee un numero escrito, como el que teclea quien retoma su caso.

    Acepta la forma exacta y nada mas. Ser permisivo aqui --aceptar minusculas,
    espacios o un guion de mas-- haria que el mismo caso se escribiera de varias
    maneras, y la busqueda por numero dejaria de encontrarlo.
    """
    partes = value.split("-")
    if len(partes) != 2:
        msg = f"'{value}' no tiene la forma de un numero de caso: dos letras, guion, el contador"
        raise ValueError(msg)
    return CaseNumber(prefix=partes[0], serial=partes[1])
