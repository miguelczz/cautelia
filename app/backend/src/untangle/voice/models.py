"""Lo que queda escrito de una llamada (U16, `entities.md`).

Una sola entidad, `CallSession`, y dos conjuntos cerrados. El equivalente de
`ChatSession` en el otro canal, y comparte con ella la forma de identificar al
navegador: el resumen de la clave del visitante, nunca la poliza.

**Aqui no hay ningun campo de audio, y la ausencia es la regla** (BR7.1, NFR19).
No hay ruta de archivo, no hay identificador de grabacion y no hay columna de
muestras. Es deliberado: un campo que no existe no se llena "temporalmente para
depurar", y llenarlo exigiria una migracion que alguien tendria que escribir y
justificar. Lo que queda del paso de una persona por esta demostracion es su
transcripcion redactada, que vive en el caso y se borra cada noche.

**Tampoco hay transcripcion ni limites.** La transcripcion es del caso (U4) y de
la traza (U5): una segunda copia se desincroniza, y la que alguien olvida borrar
es siempre la segunda. Los carriles publicos --tres minutos, una llamada al dia--
son de U17; esta fila guarda lo que paso, no lo que estaba permitido.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from untangle.base import Locale
from untangle.telemetry.spend.models import VoiceMode as SpendVoiceMode
from untangle.tenancy.models import TenantId


class CallState(StrEnum):
    """Donde esta una llamada. Tres, no cinco.

    `listening` y `speaking` son estado de la **conversacion**, no de la llamada:
    viven en memoria mientras corre, viajan por el socket para que la consola los
    dibuje y no se persisten porque nadie los consulta despues. Una tabla con el
    estado por segundo seria un registro de audio por otro nombre.
    """

    #: La sesion existe; el socket todavia no mando su cuadro de autenticacion.
    CONNECTING = "connecting"
    #: El socket esta autenticado y la llamada corre.
    LIVE = "live"
    #: Termino, por uno de los seis motivos.
    ENDED = "ended"


class EndReason(StrEnum):
    """Por que termino una llamada (BR1.6).

    Cerrado a proposito: la consola tiene una frase por cada uno y la bandeja una
    lectura, asi que un septimo no puede entrar sin que las dos se enteren.
    Una llamada que termina sin motivo es una que la consola no sabe explicar.
    """

    #: La persona colgo.
    HANGUP = "hangup"
    #: El tercer silencio (BR5.2).
    SILENCE = "silence"
    #: Se agoto la duracion maxima.
    MAX_DURATION = "max_duration"
    #: El socket se cerro sin cuadro de colgar (BR6.1). No es un final: es una pausa.
    DROPPED = "dropped"
    #: Fallo algo del camino.
    ERROR = "error"
    #: El reporte quedo completo y la agente cerro (BR3.7, AC1.23.4).
    #:
    #: **Es el sexto y se anadio al cablear el cierre**, no al disenarlo. El
    #: conjunto tenia cinco y ninguno decia esto: `hangup` es "la persona colgo",
    #: que no es lo que pasa cuando la agente termina de leer el numero de caso y
    #: se despide, y `silence` dejaria el caso esperando al asegurado justo
    #: cuando ya no espera nada. Un conjunto cerrado que no puede expresar un
    #: desenlace real no esta protegiendo: esta escondiendo.
    COMPLETED = "completed"
    #: El caso paso a un ajustador y la agente se despidio (2026-10-11).
    #:
    #: El septimo. Antes una llamada derivada seguia abierta hasta morir por
    #: silencio, y su fila decia `silence`: un motivo que no es el que ocurrio.
    HANDED_OFF = "handed_off"
    #: La persona pidio dejar el reporte guardado para seguir despues (2026-10-11).
    #:
    #: El octavo. Es la unica despedida deliberada que **deja el caso retomable**:
    #: `silence` y `max_duration` tambien dicen "queda guardado", pero no abren la
    #: ventana de retoma, y prometer "puedes retomarlo hasta..." tras ellas seria
    #: falso. `dropped` si la abre, pero cuenta una caida y esto no lo es.
    SAVED = "saved"


#: Voz principal o de respaldo. Se fija al crear la sesion y **no cambia a mitad
#: de llamada** (US5.11).
#:
#: **Se importa, no se declara otra vez.** Esta unidad lo escribio como enum
#: propio en su primera tanda y resulto ser un segundo conjunto cerrado con el
#: mismo nombre y los mismos dos valores que el de la contabilidad, que es su
#: dueno de verdad: quien elige el modo es U17 con `reserve_primary_voice`
#: (C-17), y la plataforma de voz de U15 ya recibe **ese**. Dos conjuntos
#: gemelos no se rompen el dia que nacen: se rompen el dia que uno gana un
#: tercer valor, y entonces la conversion en la frontera lo traduce a un
#: `ValueError` en produccion o, peor, lo redondea al que mas se parezca.
VoiceMode = SpendVoiceMode


#: Los estados desde los que una llamada todavia puede terminar. Fuera de aqui,
#: terminar otra vez no es un error que absorber: es una llamada que se cerro dos
#: veces, y eso hay que verlo.
ESTADOS_VIVOS = frozenset({CallState.CONNECTING, CallState.LIVE})


@dataclass(frozen=True)
class CallSession:
    """Una llamada, tal como esta en la base."""

    call_id: str
    tenant_id: TenantId
    visitor_key_digest: str
    language: Locale
    voice_mode: VoiceMode
    state: CallState
    started_at: datetime
    case_id: str | None = None
    ended_at: datetime | None = None
    end_reason: EndReason | None = None
    #: Hasta cuando se puede retomar tras un corte (BR6.1). Nulo mientras vive.
    resume_until: datetime | None = None

    @property
    def live(self) -> bool:
        return self.state in ESTADOS_VIVOS


__all__ = [
    "ESTADOS_VIVOS",
    "CallSession",
    "CallState",
    "EndReason",
    "VoiceMode",
]
