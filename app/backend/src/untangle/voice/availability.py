"""Por que no hay voz, y que frase acompaña a cada motivo (C-08, BR1.1).

Es el vocabulario cerrado que la consola dibuja **antes** de ofrecer el botón:
ofrecer uno que va a fallar es peor que no ofrecerlo.

**Vive en la unidad y no en el archivo de rutas**, aunque sea la forma de una
respuesta HTTP. Dos razones: el chequeo que comprueba que la consola sabe decir
todos los motivos tiene que poder leerlo sin importar la raíz de composición, que
está por encima; y el conjunto es de la llamada, no de su puerta. El día que
alguien añada un quinto motivo, lo que tiene que enterarse es esta tabla.

**Las claves no se componen.** Cada motivo nombra la suya, tomada de la tabla de
su dueño --las cuotas son de U5 y la voz apagada de U15--, y ninguna se arma con
una interpolación: una clave compuesta no aparece en el chequeo de claves sin
consumidor, y ahí es donde se pierden.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from untangle.copy_catalog.api import CopyKey
from untangle.providers.voice_availability import REASON_KEYS
from untangle.telemetry.spend.labels import QUOTA_REASON_KEYS
from untangle.telemetry.spend.models import QuotaReason
from untangle.voice.wire import TIME_RUNNING_OUT


class VoiceOffCode(StrEnum):
    """Por qué no hay voz ahora mismo. **Lista cerrada**, la de C-08.

    Los dos carriles diarios están aquí porque el contrato los declara y la
    consola tiene una frase para cada uno. Los aplica U17 (`admission.decide`) y los
    devuelven las dos puertas: la disponibilidad como `reason_code` y abrir la llamada
    como el `code` del problema, con el mismo valor.
    """

    RATE_LIMITED_DAILY = "rate_limited_daily"
    RATE_LIMITED_SITE = "rate_limited_site"
    BUDGET_EXHAUSTED = "budget_exhausted"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    #: Pasaron 24 horas sin un reinicio nocturno exitoso, asi que las superficies
    #: publicas dejan de aceptar **casos nuevos** (BR3.2 de U20). Una llamada que
    #: retoma un caso ya abierto si se admite: lo que se estrecha es lo nuevo, y
    #: quien esta a mitad de un reporte lo termina (BR3.3).
    DEMO_CLOSED = "demo_closed"


#: La frase de cada motivo. **Una distinta por motivo** (2026-10-11): la consola decia
#: "la voz esta apagada" ante cualquier rechazo, y quien visita no sabia si volver
#: manana, si el limite era suyo o de todos, o si el gasto se habia acabado.
#:
#: Los dos carriles diarios tienen frase propia de la voz --las de U5 hablan del chat:
#: "llegaste al limite de hoy"-- y el techo de gasto conserva la de AC5.14.3, que es la
#: de U5 y ya era de la voz. El cuarto motivo no tiene una sola frase porque su causa la
#: sabe la configuración de cada aseguradora, y la disponibilidad de U15 la trae con el
#: motivo.
OFF_CODE_KEYS: Mapping[VoiceOffCode, CopyKey] = {
    VoiceOffCode.RATE_LIMITED_DAILY: CopyKey("voice.availability.rate_limited_daily"),
    VoiceOffCode.RATE_LIMITED_SITE: CopyKey("voice.availability.rate_limited_site"),
    VoiceOffCode.BUDGET_EXHAUSTED: QUOTA_REASON_KEYS[QuotaReason.BUDGET_EXHAUSTED],
    # **El unico literal de esta tabla**, y la razon esta en el contrato de capas:
    # la frase es de U20, que esta por encima de la voz, asi que su constante no se
    # puede importar desde aqui. Escribirla una vez y aqui es lo que la deja
    # dentro de `all_copy_keys()`, que es lo que hace que la consola sepa decirla;
    # que siga coincidiendo con la de U20 lo comprueba una prueba de U20, no la
    # memoria de quien edite una de las dos.
    VoiceOffCode.DEMO_CLOSED: CopyKey("demo.reset.surfaces_closed"),
}


def all_copy_keys() -> tuple[CopyKey, ...]:
    """Todo lo que el servidor puede pedirle a la consola que diga.

    Las tres de arriba, las de voz apagada de U15 --que llegan como `reason_key`
    de la disponibilidad-- y el único aviso que viaja por el socket. Sale de las
    tablas de cada dueño y no de una lista escrita a mano: una lista propia se
    quedaría atrás justo el día en que este chequeo tendría que avisar.
    """
    claves = [*OFF_CODE_KEYS.values(), *REASON_KEYS.values(), TIME_RUNNING_OUT]
    return tuple(dict.fromkeys(claves))


__all__ = ["OFF_CODE_KEYS", "VoiceOffCode", "all_copy_keys"]
