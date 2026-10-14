"""Las sondas contra el **despliegue vivo** (NFR10.3, BR1.9, AC4.11.5).

Hoy hay dos, y las dos son el escenario adversarial RT-4 --acceso a un caso o
una poliza ajena-- por sus dos mitades: el enlace firmado del visitante, que
trajo U2, y la credencial de personal pidiendo la cola de otra aseguradora, que
trae U14.

**Por que contra el despliegue y no contra el arnes local.** Las fallas de
aislamiento son tan a menudo errores de configuracion del despliegue como errores
de codigo, y el arnes local no ve los primeros. Por eso este conjunto corre por
hito --semanas 6, 9 y 12-- con `mise run evals:run -- --subset rt4-live`, y no en
cada cambio.

**Por que habla por HTTP y no llama al modulo.** Un contrato de importacion
prohibe que el corredor de evaluaciones alcance la sesion de base de datos o la
raiz de composicion: es lo que mantiene el camino del clon al reporte sin base de
datos, y con ello la cifra publicada de NFR21. Una sonda contra un despliegue
habla por la red o no habla.

**Sin despliegue al que apuntar, el caso queda no medido**, con su causa y con la
corrida marcada como no comparable. Nunca en verde: una compuerta que no se pudo
ejecutar se declara asi, jamas se omite.

Se usa `urllib` de la biblioteca estandar y no un cliente nuevo: son dos
peticiones por caso, y una dependencia de tiempo de ejecucion tiene que ganarse
su sitio.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from untangle.base import Locale
from untangle.evals.models import Dataset
from untangle.evals.runner.api import CheckOutcome, EvalTarget, register_check, register_targets
from untangle.evals.runner.failures import TargetUnavailableError
from untangle.settings import Settings
from untangle.tenancy import config as tenant_config
from untangle.tenancy import staff_identity
from untangle.tenancy.models import TenantConfig

#: La ruta que canjea un enlace de caso (C-07), **como la sirve el despliegue**: bajo
#: `/api`. La dueña de la ruta es U14; esta sonda solo la interroga desde fuera.
#:
#: Hasta el 2026-10-11 decia `/case-links/redeem`, sin el prefijo. Contra el
#: despliegue de verdad eso no llega al canje: lo contesta lo que sirva las paginas,
#: igual para cualquier token, y la sonda habria pasado sin medir nada. No se habia
#: notado porque nunca se corrio contra el sitio publicado y el servidor de las
#: pruebas contestaba en cualquier ruta.
REDEEM_PATH = "/api/case-links/redeem"

#: Con que nombre se presenta la sonda. El dominio publico esta detras de un proxy
#: que rechaza con `403` al cliente por omision de la biblioteca estandar, antes de
#: que la peticion llegue al aplicativo (visto el 2026-10-11): sin esto la sonda
#: media al proxy y no al despliegue.
USER_AGENT = "cautelia-evals/1.0"

#: Cuanto se espera a una respuesta. Una sonda que se queda colgada convierte una
#: compuerta en un cronometro.
TIMEOUT_SEGUNDOS = 10.0

#: Dos tokens que **no corresponden a ningun caso vivo**. El primero ni siquiera
#: tiene forma de token; el segundo la tiene y una firma que no vale. Los dos
#: tienen que recibir exactamente la misma respuesta: si difirieran, el rechazo
#: seria un oraculo que dice que enlaces existieron alguna vez (BR3.3).
TOKENS_AJENOS = (
    "no-es-un-token",
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA.0000000000000000000000000000"
    "0000000000000000000000000000000000000000",
)


@dataclass(frozen=True)
class Respuesta:
    """Lo que devolvio el despliegue: su codigo y su cuerpo, tal cual."""

    status: int
    body: bytes


def _sondear(base_url: str, path: str, payload: dict[str, str], language: Locale) -> Respuesta:
    """Una peticion al despliegue. Devuelve la respuesta incluso si es de error."""
    destino = urllib.parse.urljoin(base_url, path)
    partes = urllib.parse.urlparse(destino)
    if partes.scheme not in ("http", "https"):
        msg = (
            f"UNTANGLE_LIVE_TARGET_URL apunta a '{partes.scheme}', que no es http "
            "ni https; la sonda no abre otra cosa"
        )
        raise TargetUnavailableError(msg)

    peticion = urllib.request.Request(  # noqa: S310 -- el esquema se acaba de comprobar arriba
        destino,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept-Language": language,
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT_SEGUNDOS) as respuesta:  # noqa: S310
            return Respuesta(status=int(respuesta.status), body=respuesta.read())
    except urllib.error.HTTPError as error:
        # Un 404 es exactamente lo que esta sonda espera: se lee y se compara.
        return Respuesta(status=int(error.code), body=error.read())
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        msg = f"no se pudo alcanzar el despliegue en '{destino}': {error}"
        raise TargetUnavailableError(msg) from error


def _rechazo_del_api(respuesta: Respuesta) -> dict[str, object] | None:
    """El cuerpo del rechazo sin su identificador de traza, o `None` si no es del API.

    El identificador de traza cambia en cada peticion y no dice nada del token: con
    el, dos rechazos identicos nunca serian iguales byte a byte. Lo demas --codigo,
    titulo, causa-- si tiene que coincidir.
    """
    try:
        cuerpo = json.loads(respuesta.body)
    except ValueError:
        return None
    if not isinstance(cuerpo, dict):
        return None
    return {clave: valor for clave, valor in cuerpo.items() if clave != "trace_id"}


def rt4_foreign_case_denied(*, language: Locale, root: Path) -> CheckOutcome:
    """RT-4: abrir un caso ajeno no devuelve nada, y no dice por que.

    Dos intentos con tokens que no corresponden a ningun caso vivo. Pasa cuando
    los dos reciben `404` y **la misma respuesta byte a byte**; falla si alguno
    concede acceso o si las dos respuestas se distinguen.
    """
    del root  # La sonda no lee el arbol: habla con el despliegue.

    objetivo = Settings().live_target_url
    if not objetivo:
        msg = (
            "no hay despliegue vivo al que apuntar: defina UNTANGLE_LIVE_TARGET_URL. "
            "Este caso corre por hito contra el despliegue publico (NFR10.3, BR1.9) "
            "y no se da por verde sin haberlo ejecutado."
        )
        raise TargetUnavailableError(msg)

    respuestas = [
        _sondear(objetivo, REDEEM_PATH, {"token": token}, language) for token in TOKENS_AJENOS
    ]

    concedidos = [r for r in respuestas if 200 <= r.status < 300]
    if concedidos:
        return CheckOutcome(
            passed=False,
            detail=(
                f"el despliegue concedio acceso con un token ajeno "
                f"(codigo {concedidos[0].status}) en {language}"
            ),
        )

    if any(r.status != 404 for r in respuestas):
        codigos = ", ".join(str(r.status) for r in respuestas)
        return CheckOutcome(
            passed=False,
            detail=(
                f"un token ajeno tiene que responder 404, como un caso que no "
                f"existe; se obtuvo {codigos} en {language}"
            ),
        )

    rechazos = [_rechazo_del_api(r) for r in respuestas]
    if any(rechazo is None for rechazo in rechazos):
        # Un 404 que no trae el cuerpo del API lo contesto otra cosa --una pagina, un
        # proxy--: la sonda no llego al canje y no midio nada.
        msg = (
            f"'{objetivo}' respondio 404 pero no con el rechazo del API: revise que "
            "UNTANGLE_LIVE_TARGET_URL sea la raiz del despliegue"
        )
        raise TargetUnavailableError(msg)

    if rechazos[0] != rechazos[1]:
        return CheckOutcome(
            passed=False,
            detail=(
                f"dos rechazos distintos en {language}: la diferencia convierte el "
                "rechazo en un oraculo que dice que enlaces existieron alguna vez"
            ),
        )

    return CheckOutcome(passed=True)


# --- La otra mitad de RT-4: la credencial de personal (U14, BR1.4) ------------

#: La ruta de la cola de una aseguradora (C-05). La dueña es U14; esta sonda la
#: interroga desde fuera, igual que a la de canje.
QUEUE_PATH_TEMPLATE = "/api/inbox/{tenant_id}/cases"

#: La cookie que lleva la credencial de la bandeja. U2 la emite y U14 la lee; aqui
#: solo se escribe en la cabecera.
STAFF_COOKIE = "untangle_staff"

#: Los codigos con que un despliegue dice "esa credencial no vale aqui".
CREDENCIAL_NO_ACEPTADA = frozenset({401, 403, 404})

#: Una credencial ilegible. No tiene que parecerse a nada: su unico trabajo es
#: producir el rechazo con el que se compara el de la credencial de otra
#: aseguradora. Si los dos no salen identicos, el rechazo es un oraculo.
CREDENCIAL_ILEGIBLE = "no-es-una-credencial"


def _sondear_cola(base_url: str, tenant_id: str, credencial: str, language: Locale) -> Respuesta:
    """Pide la cola de una aseguradora con una credencial. Devuelve lo que responda."""
    destino = urllib.parse.urljoin(base_url, QUEUE_PATH_TEMPLATE.format(tenant_id=tenant_id))
    partes = urllib.parse.urlparse(destino)
    if partes.scheme not in ("http", "https"):
        msg = (
            f"UNTANGLE_LIVE_TARGET_URL apunta a '{partes.scheme}', que no es http "
            "ni https; la sonda no abre otra cosa"
        )
        raise TargetUnavailableError(msg)

    peticion = urllib.request.Request(  # noqa: S310 -- el esquema se acaba de comprobar arriba
        destino,
        headers={
            "Accept": "application/json",
            "Accept-Language": language,
            "User-Agent": USER_AGENT,
            # La credencial viaja en la cookie y **nunca** en la direccion: una
            # credencial en la ruta queda en cada registro que la vea pasar.
            "Cookie": f"{STAFF_COOKIE}={credencial}",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT_SEGUNDOS) as respuesta:  # noqa: S310
            return Respuesta(status=int(respuesta.status), body=respuesta.read())
    except urllib.error.HTTPError as error:
        return Respuesta(status=int(error.code), body=error.read())
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        msg = f"no se pudo alcanzar el despliegue en '{destino}': {error}"
        raise TargetUnavailableError(msg) from error


def _dos_aseguradoras() -> tuple[TenantConfig, TenantConfig]:
    """Dos aseguradoras de la configuracion versionada, en orden de identificador.

    Ningun identificador de aseguradora se escribe aqui: salen de la carpeta de
    configuracion, como manda la regla del proyecto. Con menos de dos no hay
    aislamiento que comprobar y la sonda lo dice en vez de pasar.
    """
    disponibles = sorted(tenant_config.loaded().available, key=lambda t: t.tenant_id)
    if len(disponibles) < 2:
        msg = (
            f"la configuracion declara {len(disponibles)} aseguradora(s) y esta sonda "
            "necesita dos: sin una segunda no hay cola ajena que pedir"
        )
        raise TargetUnavailableError(msg)
    return disponibles[0], disponibles[1]


def rt4_inbox_queue_isolated(*, language: Locale, root: Path) -> CheckOutcome:
    """RT-4: una credencial nunca ve la cola de otra aseguradora (BR1.4 de U14).

    Tres pasos, con el **control positivo delante**: la credencial legitima recibe
    su cola con casos dentro; la misma credencial pidiendo la cola de otra
    aseguradora es rechazada; y ese rechazo es identico byte a byte al de una
    credencial ilegible.

    El primer paso no es cortesia. Sin el, los otros dos pasan igual contra una
    bandeja que no entregue nada nunca, que es exactamente el defecto que U13
    encontro en su propia prueba del resumen de traza.
    """
    del root  # La sonda no lee el arbol: habla con el despliegue.

    ajustes = Settings()
    objetivo = ajustes.live_target_url
    if not objetivo:
        msg = (
            "no hay despliegue vivo al que apuntar: defina UNTANGLE_LIVE_TARGET_URL. "
            "Este caso corre por hito contra el despliegue publico (NFR10.3, BR1.9) "
            "y no se da por verde sin haberlo ejecutado."
        )
        raise TargetUnavailableError(msg)

    propia, ajena = _dos_aseguradoras()
    if not propia.staff:
        msg = f"la aseguradora '{propia.tenant_id}' no declara personal al que emitirle credencial"
        raise TargetUnavailableError(msg)

    credencial = staff_identity.issue_credential(
        tenant_id=propia.tenant_id,
        principal_id=propia.staff[0].principal_id,
        signing_key=ajustes.staff_credential_signing_key,
    )

    # Paso 1 -- el control positivo. Va delante a proposito.
    propia_respuesta = _sondear_cola(objetivo, propia.tenant_id, credencial, language)
    if propia_respuesta.status in CREDENCIAL_NO_ACEPTADA:
        # La credencial se firma con la clave que tenga quien corre la sonda. Si el
        # despliegue no la acepta, lo mas probable es que no sea **su** clave, y con
        # eso no se puede distinguir "esta roto" de "no pude entrar a medir": no se
        # midio. Antes salia como fallo de una compuerta dura (2026-10-11).
        msg = (
            f"el despliegue no acepto la credencial de '{propia.tenant_id}' "
            f"({propia_respuesta.status}): la sonda necesita la clave de firma de ese "
            "despliegue (UNTANGLE_STAFF_CREDENTIAL_SIGNING_KEY) para emitirla"
        )
        raise TargetUnavailableError(msg)
    if propia_respuesta.status != 200:
        return CheckOutcome(
            passed=False,
            detail=(
                f"el control positivo fallo en {language}: la credencial legitima de "
                f"'{propia.tenant_id}' recibio {propia_respuesta.status} y no su cola. "
                "Sin cola entregada, no probar el aislamiento no significa nada."
            ),
        )
    try:
        entregado = json.loads(propia_respuesta.body)
        casos = entregado["items"]
    except (ValueError, KeyError, TypeError) as error:
        return CheckOutcome(
            passed=False,
            detail=f"el control positivo devolvio algo que no es una cola en {language}: {error}",
        )
    if not casos:
        return CheckOutcome(
            passed=False,
            detail=(
                f"el control positivo entrego una cola vacia en {language}: una bandeja "
                "que no entrega nada pasaria las dos comprobaciones siguientes sin "
                "tener ningun aislamiento"
            ),
        )

    # Paso 2 -- la misma credencial, la cola de otra aseguradora.
    ajena_respuesta = _sondear_cola(objetivo, ajena.tenant_id, credencial, language)
    if 200 <= ajena_respuesta.status < 300:
        return CheckOutcome(
            passed=False,
            detail=(
                f"fuga entre aseguradoras en {language}: la credencial de "
                f"'{propia.tenant_id}' obtuvo {ajena_respuesta.status} pidiendo la cola "
                f"de '{ajena.tenant_id}'"
            ),
        )

    # Paso 3 -- el rechazo tiene que ser el mismo que el de una credencial ilegible.
    ilegible = _sondear_cola(objetivo, ajena.tenant_id, CREDENCIAL_ILEGIBLE, language)
    # El cuerpo se compara sin su identificador de traza, que cambia en cada peticion
    # y no dice nada de la credencial.
    distintos = (_rechazo_del_api(ajena_respuesta) or ajena_respuesta.body) != (
        _rechazo_del_api(ilegible) or ilegible.body
    )
    if ajena_respuesta.status != ilegible.status or distintos:
        return CheckOutcome(
            passed=False,
            detail=(
                f"dos rechazos distintos en {language} ({ajena_respuesta.status} frente a "
                f"{ilegible.status}): la diferencia le dice a quien prueba credenciales "
                "cual de sus intentos acerto una aseguradora que existe"
            ),
        )

    return CheckOutcome(passed=True)


#: Las sondas contra el despliegue vivo, por el criterio que resuelven. Las trae
#: U2 (el enlace) y U14 (la cola), y viven juntas porque comparten transporte.
SONDAS = {
    "rt4_foreign_case_denied": rt4_foreign_case_denied,
    "rt4_inbox_queue_isolated": rt4_inbox_queue_isolated,
}


UNIT = "despliegue-vivo"

#: Compuerta dura (PRD 11.2 `[bloquea]`, fuga entre aseguradoras), registrada como
#: bloqueante el 2026-10-11: hasta entonces un fallo de RT-4 contaba como un caso
#: rojo mas, que una explicacion escrita podia levantar.
TARGETS: tuple[EvalTarget, ...] = (
    EvalTarget(
        "rt4_foreign_case_denied",
        Dataset.DS_6,
        "RT-4: el enlace de un caso no abre el de otra aseguradora, y los rechazos no "
        "se distinguen (NFR12.2 [bloquea])",
        blocking=True,
    ),
    EvalTarget(
        "rt4_inbox_queue_isolated",
        Dataset.DS_6,
        "RT-4: la credencial de una aseguradora no lee la cola de otra (NFR12.2 [bloquea])",
        blocking=True,
    ),
)


def register_live_probes() -> None:
    """Registra las sondas contra el despliegue vivo en el corredor."""
    for criterio, sonda in SONDAS.items():
        register_check(criterio, sonda)
    register_targets(UNIT, TARGETS)
