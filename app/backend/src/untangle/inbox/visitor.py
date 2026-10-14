"""El visitante que entra a su caso con un enlace firmado (C-07, BR5.1 a BR5.7).

Dos compuertas duras viven aqui.

**BR5.1: el enlace abre su caso y nunca la lista.** La sesion que deja el canje
autoriza **un caso**, no una aseguradora. Con ella, la cola responde igual que a
quien no tiene nada: mostrar la lista expondria casos de otros visitantes. No es
que la pantalla no la ofrezca --eso es cortesia--: es que la ruta no la entrega.

**BR5.2: una firma alterada y un caso que no existe se responden igual.** Un
mensaje distinto por causa le dice a quien prueba enlaces cual de sus intentos
acerto el identificador. Las cuatro causas que U2 distingue --invalido, caducado,
revocado, de otro caso-- comparten respuesta hacia fuera y la causa real viaja al
rastro, que es donde sirve.

## Como se encuentra la aseguradora de un token que no la nombra

El token no dice a que aseguradora pertenece, **y eso es a proposito**: si lo
dijera, quien tuviera uno sabria de quien es antes de canjearlo. Asi que el canje
le pregunta a cada aseguradora cargada, bajo su propia politica de fila, y la
primera que lo reconoce se lo queda.

Cuesta tantas consultas como aseguradoras haya --tres-- y no filtra nada: cuantas
hay es publico, sale en el inicio del sitio. Las alternativas eran peores: meter la
aseguradora en el token cambia un formato ya emitido y lo revela, y buscar sin
aseguradora fijada saltaria la politica de fila para la consulta que mas la
necesita.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from untangle import observability
from untangle.tenancy import api as tenancy
from untangle.tenancy import visitor_access
from untangle.tenancy.models import CaseLinkGrant, LinkRejectedError, LinkRejection

#: La cookie que deja el canje. Vive solo bajo `/api`, es `HttpOnly` --nada del
#: lado del navegador la necesita-- y nunca dura mas que el enlace que la creo.
CASE_COOKIE = "ut_case"

#: La ruta del canje, tal como C-07 la declara. La sonda de RT-4 contra el
#: despliegue vivo la interroga por este nombre exacto.
REDEEM_PATH = "/case-links/redeem"


@dataclass(frozen=True)
class CaseSession:
    """Lo que autoriza una cookie de caso: **un** caso, nunca una aseguradora."""

    tenant_id: str
    case_id: str
    access: str
    expires_at: datetime


class CaseSessionInvalidError(RuntimeError):
    """La cookie de caso no vale, o no abre lo que se pidio.

    Una sola excepcion para todas las causas: la ruta la responde igual que un
    caso que no existe, y por eso no hay nada que distinguir aqui.
    """


async def redeem(token: str, *, signing_key: str | None, now: datetime) -> CaseSession:
    """Canjea el token por una sesion de caso, buscando en cada aseguradora.

    Sube el contador de canjes: es lo que hace la pantalla **una vez al cargar**.

    Levanta con la **misma** excepcion cuando el token no vale, cuando vencio,
    cuando esta revocado y cuando no hay ninguna aseguradora que lo reconozca.
    Quien llama no tiene forma de distinguirlas aunque quisiera.
    """
    return await _buscar(token, signing_key=signing_key, now=now, contar=True)


async def session_from_cookie(token: str, *, signing_key: str | None, now: datetime) -> CaseSession:
    """La sesion de una peticion que ya trae la cookie, **sin** contar un canje.

    La cookie lleva el token porque esta unidad no acuna credenciales: emitirlas y
    validarlas es de U2 (C-07), y inventarse aqui una segunda cosa firmada seria
    un segundo mecanismo de acceso que nadie pidio. Lo que si hacia falta era
    distinguir canjear de comprobar, y eso lo aporta U2 con su enmienda.
    """
    return await _buscar(token, signing_key=signing_key, now=now, contar=False)


async def _buscar(
    token: str, *, signing_key: str | None, now: datetime, contar: bool
) -> CaseSession:
    ultima: LinkRejection = LinkRejection.INVALID
    mirar = visitor_access.redeem_case_link if contar else visitor_access.verify_case_link
    for tenant_id in tenancy.available_ids():
        try:
            concesion = await mirar(token, tenant_id=tenant_id, signing_key=signing_key, now=now)
        except LinkRejectedError as error:
            # La causa se guarda para el rastro y se sigue preguntando: que esta
            # aseguradora no lo reconozca no dice nada sobre las demas.
            ultima = error.cause
            continue
        return CaseSession(
            tenant_id=concesion.tenant_id,
            case_id=concesion.case_id,
            access=concesion.access,
            expires_at=concesion.expires_at,
        )

    observability.emit("inbox.case_link_rejected", cause=ultima.value)
    msg = "el enlace no vale"
    raise CaseSessionInvalidError(msg)


def cookie_max_age(sesion: CaseSession, *, now: datetime) -> int:
    """Lo que le queda al enlace, en segundos, y nunca mas que eso (BR5.3).

    La cookie no puede vivir mas que el enlace que la creo: si viviera mas, el
    vencimiento del enlace dejaria de significar nada y quien tuviera la cookie
    seguiria entrando.
    """
    restante = int((sesion.expires_at - now).total_seconds())
    return max(restante, 0)


def authorize(sesion: CaseSession, *, case_id: str) -> None:
    """Comprueba que esa sesion abre **ese** caso (BR5.1).

    Pedir otro caso responde como si no existiera. Lo comprueba U2, que es quien
    lo define; aqui se llama para que ninguna ruta pueda olvidarse.
    """
    try:
        visitor_access.authorize_case(
            CaseLinkGrant(
                tenant_id=sesion.tenant_id,
                case_id=sesion.case_id,
                access=sesion.access,
                expires_at=sesion.expires_at,
                redeemed_count=0,
            ),
            case_id,
        )
    except LinkRejectedError as error:
        msg = "la sesion de caso no abre ese caso"
        raise CaseSessionInvalidError(msg) from error


#: **No hay aqui una comprobacion de vencimiento**, y no por olvido.
#:
#: La habia, y al romperla no se cayo ninguna prueba: `verify_case_link` de U2 ya
#: compara la caducidad contra el reloj en **cada** llamada, asi que una sesion
#: reconstruida desde la cookie no puede existir si el enlace vencio. Era una
#: segunda copia de la misma regla, y dos guardias para lo mismo significan que el
#: dia que una cambie la otra seguira diciendo lo de antes.
#:
#: Lo que BR5.4 pide --que decidir con el enlace vencido no se aplique-- se cumple
#: por ese camino y se prueba por la puerta, que es donde importa.
