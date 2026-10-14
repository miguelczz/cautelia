"""La admision de una llamada publica: los dos carriles diarios y la retoma (BR1.2, BR1.3).

**La decision es pura**, con la forma de `chat/limits.py`: recibe los limites, lo que
los contadores ya dicen y el reloj como argumento; no abre
sesion, no llama a nadie y no mira el reloj del proceso. Devuelve **cual** carril
rechazo --un `VoiceOffCode` de la lista cerrada-- y nunca la frase: esa sale del
catalogo por `OFF_CODE_KEYS`, en el punto unico de salida.

**La asimetria de la retoma es el diseno.** Una llamada que vuelve dentro de la
ventana de un corte retoma el mismo caso: **no** pasa por el carril de la conexion
--quien prueba tiene que poder terminar lo que empezo-- pero **si** por el del
sitio, que protege el dinero. Por eso un visitante con su llamada del dia gastada
es admitido al retomar, y el mismo visitante es rechazado si el sitio esta agotado.

**El borde de la ventana es abierto**, igual que `session.find_resumable`
(`resume_until > ahora`): a los 900 s exactos la ventana ya se cerro. Si esta
decision y esa consulta discreparan en un segundo, la disponibilidad ofreceria una
retoma que la admision luego trataria como llamada nueva.

**Lo que no hace:** no cuenta, no incrementa y no sabe que es una conexion. Los
contadores son de quien llama; aqui solo se comparan contra el limite.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from untangle.voice.availability import VoiceOffCode


@dataclass(frozen=True)
class CallLanes:
    """Los tres numeros con los que se admite una llamada publica, ya reunidos.

    **Los dos carriles son del sitio, no de una aseguradora**, y por eso no viven
    en su carpeta: "quince llamadas del sitio" escrito en tres carpetas son
    cuarenta y cinco, o las que toque leer. Salen de `VoiceLimits`
    (`providers.yaml`), que los declara **sin valor por omision a proposito** --un
    limite que el archivo no escribe es un limite que nadie decidio-- y que es el
    archivo que se revisa cuando hay que explicar por que se rechazo una llamada.

    **La ventana de retoma si es de la aseguradora** (`CallConfig`): cuanto tiempo
    se puede volver a una conversacion es una decision de como conversa cada una,
    no un control de gasto.

    Reunirlos aqui es lo que deja la decision sin depender de ninguno de los dos
    tipos de configuracion, y lo que impide confundir tres enteros en la llamada.
    """

    #: Llamadas al dia **desde una conexion**, no por persona: un visitante cambia
    #: de navegador o de red, asi que este carril protege la experiencia y no es un
    #: control de gasto (BR1.4).
    calls_per_visitor_day: int
    #: El **cupo de hoy** del sitio, no el tope escrito: U5 lo deriva cada dia de lo
    #: que queda del presupuesto y los dias que faltan (BR5.6), acotado por el tope
    #: de `VoiceLimits`. Por eso no puede haber una segunda copia por aseguradora
    #: que un dia diga otra cosa.
    #:
    #: **Puede ser menor que el de una conexion, incluso cero**, y eso no es una
    #: configuracion rota: es que hoy no caben mas llamadas. Que el *tope escrito*
    #: no quede por debajo lo comprueba `VoiceLimits`, que es donde seria un error
    #: de archivo.
    calls_per_site_day: int
    #: Cuanto tiempo queda retomable un caso despues de un corte (BR6.1).
    resume_window_seconds: int


@dataclass(frozen=True)
class CutCall:
    """La ultima llamada de esta conexion que quedo retomable, y cuando termino."""

    case_id: str
    ended_at: datetime


@dataclass(frozen=True)
class CallCounters:
    """Lo que los contadores ya dicen cuando se intenta una llamada.

    Los dos son **lo ya contado**, sin incluir la llamada que se intenta: quien
    decide compara contra el limite y el que suma es otro. Mezclar las dos cosas
    es como se acaba rechazando la llamada que justamente cabia.
    """

    visitor_calls_today: int
    site_calls_today: int
    #: La llamada cortada que esta conexion podria retomar, si la hay.
    cut_call: CutCall | None = None


@dataclass(frozen=True)
class PublicCallDecision:
    """Si la llamada se abre, y si no, cual carril la paro.

    `resumes_case` es un **dato** y no un efecto: quien decide no abre nada, dice
    que caso retomaria. `off_code` solo esta presente cuando no se admite.
    """

    admitted: bool
    off_code: VoiceOffCode | None = None
    resumes_case: str | None = None


class Lane(StrEnum):
    """Los dos carriles diarios, nombrados para poder cobrarlos en orden."""

    VISITOR = "visitor"
    SITE = "site"


#: Que codigo responde cada carril cuando es el que para la llamada. Tabla cerrada
#: y escrita: el que ve la persona nombra **su** carril, y el del sitio dice que no
#: es cosa suya.
OFF_CODE_OF: dict[Lane, VoiceOffCode] = {
    Lane.VISITOR: VoiceOffCode.RATE_LIMITED_DAILY,
    Lane.SITE: VoiceOffCode.RATE_LIMITED_SITE,
}


def lanes_for(*, resumes: bool) -> tuple[Lane, ...]:
    """Los carriles que esta llamada gasta, **en el orden en que se cobran** (BR1.3).

    Una sola funcion dice las dos mitades de la politica, y por eso existe: el
    orden --primero el de la conexion, que la persona entiende como suyo-- y la
    asimetria de la retoma --que se salta el de la conexion y **no** el del sitio,
    porque el minuto de audio se gasta igual--.

    La usan los dos caminos y por eso no se escribe dos veces: la disponibilidad,
    que **lee** los contadores sin tocarlos, y la apertura, que los **consume** de
    forma atomica. Dos copias del orden es como se acaba rechazando por un carril
    en una pantalla y por el otro en la peticion.
    """
    return (Lane.SITE,) if resumes else (Lane.VISITOR, Lane.SITE)


def resumable_case(corte: CutCall | None, *, window_seconds: int, now: datetime) -> str | None:
    """Que caso retomaria esta conexion ahora, si alguno (BR6.1).

    Lo usan la decision y la apertura, y por eso es publico: la apertura necesita
    saber **antes de cobrar** si esto es una retoma, porque una retoma no gasta el
    carril de la conexion. Dos lecturas distintas de la ventana es como se acaba
    cobrando una retoma en un camino y no en el otro.
    """
    if corte is None:
        return None
    return (
        corte.case_id
        if _dentro_de_la_ventana(corte, window_seconds=window_seconds, now=now)
        else None
    )


def _dentro_de_la_ventana(corte: CutCall, *, window_seconds: int, now: datetime) -> bool:
    return now < corte.ended_at + timedelta(seconds=window_seconds)


def decide(*, lanes: CallLanes, counters: CallCounters, now: datetime) -> PublicCallDecision:
    """Si esta llamada publica se abre, y si no, por cual carril (BR1.1, BR1.3).

    El carril de la conexion va antes que el del sitio: es el que la persona puede
    entender como suyo. Una retoma se salta el primero y **no** el segundo.
    """
    if now.tzinfo is None:
        msg = (
            "el instante tiene que llevar zona horaria: sin ella, la ventana depende de la maquina"
        )
        raise ValueError(msg)

    retoma = resumable_case(counters.cut_call, window_seconds=lanes.resume_window_seconds, now=now)

    contado = {
        Lane.VISITOR: counters.visitor_calls_today,
        Lane.SITE: counters.site_calls_today,
    }
    limite = {
        Lane.VISITOR: lanes.calls_per_visitor_day,
        Lane.SITE: lanes.calls_per_site_day,
    }
    # El orden y la asimetria salen de `lanes_for`, que es el unico sitio donde
    # estan escritos: aqui solo se recorren.
    for carril in lanes_for(resumes=retoma is not None):
        if contado[carril] >= limite[carril]:
            return PublicCallDecision(admitted=False, off_code=OFF_CODE_OF[carril])

    return PublicCallDecision(admitted=True, resumes_case=retoma)


__all__ = [
    "OFF_CODE_OF",
    "CallCounters",
    "CallLanes",
    "CutCall",
    "Lane",
    "PublicCallDecision",
    "decide",
    "lanes_for",
    "resumable_case",
]
