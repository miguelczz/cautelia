"""Retomar un caso por chat, y las dos compuertas duras que lo rodean (BR6.1 a BR6.4).

**Las dos compuertas duras de esta unidad viven aqui**, y las dos dicen lo mismo con
sujetos distintos: un numero de caso creado desde otro navegador (BR6.2) y uno de otra
aseguradora (BR6.3) **responden igual que uno que no existe**.

Lo importante es como se consigue, porque no es comprobando.

- **La aseguradora** la filtra la politica de fila antes de que la consulta la vea. El
  codigo de esta unidad nunca llega a saber cual de los dos casos era, asi que no
  puede distinguirlos ni queriendo.
- **El navegador** se compara con el resumen de su clave, y la comparacion devuelve
  `None` --no "prohibido"--, que es el mismo valor que devuelve un numero inventado.

Las tres polizas de ejemplo son publicas a proposito (F8.7), asi que identificarse con
una no prueba nada: lo que ata un caso a una persona es la clave de su navegador o el
enlace firmado de U2.

**La filtracion no seria el dato, seria la distincion.** Recibir algo distinto de lo
que recibe un desconocido ya dice que ese caso existe, aunque la frase sea inofensiva.
Por eso esta funcion tiene **un solo camino de rechazo** y no tres: si hubiera uno por
causa, alguien acabaria dandoles mensajes distintos "para depurar".
"""

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Protocol

from untangle import observability
from untangle.case_record import api as casos
from untangle.tenancy import api as tenancy
from untangle.tenancy import session as db
from untangle.tenancy.models import TenantId

#: Por que no se retomo. **Nunca sale hacia fuera**: viaja al evento de la traza,
#: que es donde se puede mirar sin que lo vea quien lo intento. Hacia fuera hay un
#: solo resultado, que es no haber encontrado nada.
type RejectionCause = str

NOT_FOUND = "not_found"
OTHER_BROWSER = "other_browser"
OTHER_TENANT = "other_tenant"


@dataclass(frozen=True)
class Resumed:
    """El caso retomado. Solo existe cuando de verdad es de quien pregunta."""

    case_id: str
    case_number: str


class CallCases(Protocol):
    """Lo que el chat necesita de la voz: los casos que este navegador abrio por llamada.

    Es un puerto y no un import porque `chat` y `voice` son hermanos en el contrato de capas: la
    raiz de composicion enchufa `voice.session.case_ids_of_visitor`. Sin enchufar, la voz no
    cuenta como dueno y un caso empezado por llamada no se retoma: falla cerrado.
    """

    def __call__(
        self, *, tenant_id: TenantId, visitor_key_digest: str
    ) -> Awaitable[frozenset[str]]: ...


_CASOS_DE_LLAMADA: CallCases | None = None


def install_call_cases(lookup: CallCases | None) -> None:
    """Enchufa (o desenchufa, con `None`) la lectura de los casos que abrio la voz."""
    global _CASOS_DE_LLAMADA
    _CASOS_DE_LLAMADA = lookup


async def by_case_number(
    *,
    tenant_id: TenantId,
    case_number: str,
    visitor_key_digest: str,
    from_calls: bool = False,
) -> Resumed | None:
    """El caso de ese numero, **si es de este navegador y de esta aseguradora**.

    `from_calls` dice que tambien cuenta el caso que este navegador abrio por llamada
    (US1.20): lo decide la configuracion de la aseguradora, y por omision no cuenta.

    `None` en cualquier otro caso, y es el mismo `None` para las tres causas: el
    numero no existe, es de otro navegador, o es de otra aseguradora. Quien
    pregunta no puede distinguirlas, que es exactamente BR6.2 y BR6.3.

    La aseguradora no se comprueba aqui y no es un olvido: la consulta ya va por
    el punto unico de sesion con la aseguradora fijada, asi que un caso de otra no
    aparece. Comprobarlo ademas daria la impresion de que esto es lo que protege,
    y el dia que alguien quitara la comprobacion redundante pensaria que rompio
    algo mas grande de lo que rompio.
    """
    vista = await casos.get_case_by_number(tenant_id, case_number)
    if vista is None:
        _registrar(tenant_id, NOT_FOUND)
        return None

    # Quien es dueno de un caso no lo sabe U4 --su vista no expone ningun
    # navegador, y hace bien: un caso no es de un navegador, es de una persona
    # que puede llegar por dos canales--. Lo sabe **esta** unidad, porque la
    # conversacion es lo que ata las dos cosas. Se pregunta por la fila, no por
    # un campo del caso.
    if not await _es_de_este_navegador(
        tenant_id=tenant_id,
        case_id=vista.case_id,
        visitor_key_digest=visitor_key_digest,
        from_calls=from_calls,
    ):
        _registrar(tenant_id, OTHER_BROWSER)
        return None

    return Resumed(case_id=vista.case_id, case_number=case_number)


async def by_signed_link(
    *, tenant_id: TenantId, token: str, case_id: str, signing_key: str | None
) -> Resumed | None:
    """El caso de un enlace firmado de U2, si el enlace es suyo y esta vivo.

    Las cuatro causas de rechazo de U2 --invalido, caducado, revocado, de otro
    caso-- ya comparten respuesta ahi (BR3.3 de U2), y aqui se colapsan con las de
    arriba: hacia fuera, todo es no haber encontrado nada.

    La clave de firma entra por argumento y no se lee de los ajustes: quien la
    tiene a mano es la ruta, y leerla aqui ataria esta unidad a la configuracion
    del proceso.
    """
    try:
        # `expected_case` es de U2 y hace la comprobacion ahi: un enlace valido de
        # **otro** caso es una de sus cuatro causas de rechazo, no una
        # comprobacion que esta unidad deba repetir.
        concesion = await tenancy.redeem_case_link(
            token, tenant_id=tenant_id, signing_key=signing_key, expected_case=case_id
        )
    except tenancy.LinkRejectedError:
        _registrar(tenant_id, NOT_FOUND)
        return None

    vista = await casos.get_case(tenant_id, concesion.case_id)
    if vista is None:
        _registrar(tenant_id, NOT_FOUND)
        return None
    return Resumed(case_id=vista.case_id, case_number=str(vista.case_number))


_DEL_NAVEGADOR = """
    SELECT 1 AS suyo FROM chat_session
    WHERE tenant_id = :tenant_id AND case_id = :case_id
      AND visitor_key_digest = :visitor_key_digest
    LIMIT 1
"""


async def _es_de_este_navegador(
    *, tenant_id: TenantId, case_id: str, visitor_key_digest: str, from_calls: bool
) -> bool:
    """Si alguna conversacion de este navegador abrio ese caso, o --si se pide-- una llamada.

    Se mira la conversacion **aunque este cerrada**: alguien que vuelve al dia
    siguiente sigue siendo quien lo abrio. Lo que acota la retencion no es esta
    consulta, es el reinicio nocturno, que se lleva la fila entera.

    La llamada se mira por el mismo resumen de la clave del navegador, nunca por la poliza:
    la de ejemplo es publica y la comparten todos los visitantes de una aseguradora.
    """
    async with db.session_for(tenant_id) as sesion:
        fila = await db.fetch_one(
            sesion,
            _DEL_NAVEGADOR,
            tenant_id=tenant_id,
            case_id=case_id,
            visitor_key_digest=visitor_key_digest,
        )
    if fila is not None:
        return True
    if not from_calls or _CASOS_DE_LLAMADA is None:
        return False
    de_llamada = await _CASOS_DE_LLAMADA(tenant_id=tenant_id, visitor_key_digest=visitor_key_digest)
    return case_id in de_llamada


def _registrar(tenant_id: TenantId, cause: RejectionCause) -> None:
    """La causa, al evento de la traza y a ningun otro sitio.

    Se escribe aparte para que se lea de un vistazo que las tres causas van al
    mismo sitio y ninguna a la respuesta. Un `if` por causa en el retorno es
    exactamente lo que estas dos compuertas prohiben.
    """
    observability.emit("chat.resume_rejected", tenant_id=tenant_id, cause=cause)


__all__ = [
    "NOT_FOUND",
    "OTHER_BROWSER",
    "OTHER_TENANT",
    "CallCases",
    "Resumed",
    "by_case_number",
    "by_signed_link",
    "install_call_cases",
]
