"""El vocabulario de C-14, sin nada del framework del grafo.

**Por que vive aparte de `turn.py`.** Los tipos de C-14 son lo que los canales
--U13 el chat, U16 y U18 la voz, U14 la bandeja-- necesitan para hablar con el
grafo. Estaban en `turn.py`, junto a la implementacion, y eso obligaba a cada canal
a importar el modulo que importa LangGraph: el contrato de importacion "LangGraph
solo dentro del runtime del grafo" se rompia por transitividad en cuanto un canal
consumia su propio contrato.

No es un detalle de estilo. ADR-003 decide que **solo esta unidad conoce el
framework del grafo**, y la razon es que cambiarlo no deba tocar ningun canal. Un
canal que lo arrastra por una cadena de imports tiene la dependencia igual aunque
no la nombre, y el dia del cambio se entera.

Asi que el vocabulario baja aqui, a un modulo hoja que no importa nada de
LangGraph, y `turn.py` lo importa como todos los demas. **Lo detecto el propio
contrato del proyecto** cuando U13 fue el primer canal en consumir C-14 de verdad.

Este modulo no tiene conducta: son los tipos del acuerdo y nada mas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Literal, Protocol

from untangle.base import Locale
from untangle.compliance.controls.api import HandoffReason
from untangle.copy_catalog.api import CopyKey
from untangle.tenancy.models import TenantId

if TYPE_CHECKING:
    from untangle.orchestration.nodes.intake.understanding import UnderstandingResponse


#: Hasta cuantas palabras un turno de voz se resuelve sin modelo: "si", "no, nadie". Es un dato
#: del contrato y no de `turn.py` porque lo leen los dos lados: el turno decide con el si va a
#: entender el mensaje, y la llamada lo mira antes de adelantar esa lectura (2026-10-13).
VOICE_RULES_MAX_WORDS = 2


@dataclass(frozen=True)
class InboundTurn:
    """Un turno de un canal hacia el grafo (C-14). La forma exacta del contrato."""

    tenant_id: TenantId
    session_ref: str
    case_id: str | None
    text: str
    language: Locale
    channel: Literal["voice", "chat"]
    received_at: datetime
    #: Lo que la agente ya entendio de este mismo mensaje, cuando el canal tuvo que
    #: entenderlo antes de entregarlo: el primer mensaje del chat se entiende para
    #: saber que caso abrir, y no se vuelve a entender en el turno (2026-10-07). Desde el
    #: 2026-10-12 el chat entiende **todo** mensaje antes de entregarlo, para saber si la
    #: persona cambio de tema y hay que abrir otro caso.
    understood: UnderstandingResponse | None = None
    #: El canal ya intento entender el mensaje. Con `understood` vacio quiere decir que el
    #: modelo fallo o tardo: el turno sigue por reglas y **no vuelve a llamarlo**, que
    #: duplicaria la espera de la persona justo cuando el proveedor anda mal.
    understood_by_channel: bool = False
    #: Esa lectura se hizo sin el caso en el que el turno va a correr --el primer mensaje, o el
    #: que cambia de tema y abre otro caso--: su `reply` se escribio sin saber que datos faltan
    #: ahi, asi que el turno que abre el caso dice la frase del catalogo.
    understood_without_case: bool = False


@dataclass(frozen=True)
class PartialText:
    """Un fragmento de una respuesta larga, ya pasado por la guardia de salida."""

    message_id: str
    seq: int
    text: str


@dataclass(frozen=True)
class FinalText:
    """La respuesta cerrada del turno (C-14).

    `from_catalog` lo anade U18, y es aditivo: dice si este texto se compuso con
    frases del catalogo por idioma o si lo escribio un modelo. **Lo necesita el
    canal, no el grafo.** Quien emite tiene que taparle los datos personales a lo
    que escribio un modelo y **no** puede pasarle el detector a una frase nuestra:
    en espanol el detector etiqueta como nombre de persona el verbo con que
    arranca la frase, asi que la respuesta de cobertura salia diciendo "[LUGAR 1]
    la clausula dentro de la Parte D" en vez de "Encontre la clausula...".

    Es un dato y no una adivinanza del canal: el canal no puede mirar un texto y
    saber de donde vino, y adivinarlo con "¿trae clave?" fallaria con las
    respuestas que se componen de varias frases, que son casi todas las del nodo
    de captura.

    Llega con `False` por omision a proposito: lo seguro es tapar, y una rama
    nueva que olvide ponerlo tapa de mas --se ve-- en vez de tapar de menos.
    """

    message_id: str
    text: str
    language: Locale
    case_id: str | None = None
    citations: tuple[object, ...] = ()
    from_catalog: bool = False
    #: El turno cerro diciendo "dejame revisar tu poliza" y el fondo va a traer la
    #: respuesta (2026-10-11). Lo usa la llamada para aguardarla callada en vez de
    #: preguntar "¿sigues ahi?", y desde el 2026-10-12 tambien el chat, para mostrar
    #: que se esta revisando hasta que llega. **Solo es cierto si la revision de verdad
    #: se lanzo en este turno**: el turno que pide la pregunta, o que no pudo lanzar el
    #: fondo, no promete nada.
    answer_pending: bool = False
    #: Los botones de respuesta rapida que el codigo eligio para esta pregunta, ya
    #: resueltos del catalogo (fase 0, 2026-10-07). Vacio cuando no hay.
    suggestions: tuple[str, ...] = ()
    #: Cuando el mensaje es una respuesta de cobertura, su resultado: `verified`,
    #: `no_clause_found`, `unverifiable` o `rejected` (fase 1, 2026-10-08). Lo lee la
    #: comparacion, que no puede confundir "no hay clausula" con "no pude verificar".
    coverage_outcome: str | None = None


@dataclass(frozen=True)
class Waiting:
    """La frase de espera del ritmo del turno (BR2.4).

    Lleva `text` ya resuelto -- a diferencia de `TurnWaiting` en el flujo SSE
    de C-04, que solo manda `copy_key` porque el chat lo resuelve del lado del
    navegador --, porque la voz necesita el texto sintetizable de inmediato, en
    proceso, sin ida y vuelta (C-14: "la voz... usa Waiting como frase de
    espera"). Un serializador de canal que solo necesite la clave la toma de
    aqui y descarta el texto.
    """

    copy_key: CopyKey
    text: str


@dataclass(frozen=True)
class Handoff:
    """La conversacion se derivo, con su motivo del conjunto cerrado (BR4.1)."""

    reason_code: HandoffReason
    copy_key: CopyKey
    text: str
    case_id: str | None = None
    case_link: str | None = None


@dataclass(frozen=True)
class TurnError:
    """El turno no se pudo completar. Nunca queda abierto en silencio (C-14)."""

    code: str
    copy_key: CopyKey
    text: str


#: La union cerrada que un canal recibe. Cerrada a proposito: el comprobador de
#: tipos prueba que quien la serializa cubre las cinco ramas, y por eso un sexto
#: evento no puede entrar sin que su serializador se entere.
TurnEvent = PartialText | FinalText | Waiting | Handoff | TurnError


@dataclass(frozen=True)
class EligibilityView:
    """La elegibilidad de una solicitud, **como texto** (U19, BR2.3).

    Tres cadenas y no los enums de `rules.eligibility`, por el mismo motivo que
    `compose_eligibility_reply` los recibe asi: el turno no puede importar el motor
    de reglas --un contrato de capas lo prohibe-- porque importarlo lo arrastraria
    al camino del turno, y la elegibilidad se decide en el ritmo de fondo (BR2.5).

    Lo que **no** trae: los identificadores de las reglas que decidieron. Van a la
    traza y a la bandeja, nunca a quien pregunto (BR2.3).
    """

    outcome: str
    band: str
    explanation_key: str


class EligibilityPort(Protocol):
    """Quien sabe evaluar y releer la elegibilidad, enchufado por la raiz.

    Dos operaciones y no una: `evaluate` corre en el ritmo de fondo y deja el
    resultado; `stored` es lo que el turno lee despues, igual que ya lee la
    respuesta de cobertura que el fondo dejo. Separarlas es lo que impide que el
    turno evalue por accidente el dia que alguien cambie una linea.
    """

    async def evaluate(self, tenant_id: str, case_id: str) -> EligibilityView | None:
        """Evalua la solicitud y guarda su salida, o `None` si todavia no se puede."""
        ...

    async def stored(self, tenant_id: str, case_id: str) -> EligibilityView | None:
        """La salida ya guardada, o `None` si el fondo todavia no la dejo.

        `None` es "espera", nunca "no elegible": colapsarlos le diria que no a quien
        todavia no se le ha mirado.
        """
        ...


class CaseTurnSupport(Protocol):
    """Lo que el chat le pide al nucleo para saber si un mensaje cambia de tema (2026-10-12).

    Va del canal hacia el nucleo por un puerto y no por una importacion: el modulo del turno
    importa LangGraph y ningun canal puede arrastrarlo, ni siquiera por transitividad
    (ADR-003). La raiz de composicion enchufa quien lo cumple.
    """

    async def understand(self, turn: InboundTurn) -> UnderstandingResponse | None:
        """El mensaje, entendido con el contexto de su caso, o `None` si no se pudo
        (sin modelo, fallo, plazo vencido) o si el turno lo resuelve una senal por reglas."""
        ...

    async def carry_over(self, *, tenant_id: str, from_case_id: str, to_case_id: str) -> None:
        """Lleva al caso nuevo la identidad y la poliza que la persona ya dio en el anterior,
        para que no las repita. El caso anterior queda como estaba."""
        ...


class CaseNotifier(Protocol):
    """Quien sabe llevarle a un caso un mensaje **sin que haya turno siguiente**.

    **Por que existe.** Todo lo demas que el ritmo de fondo calcula se lee en el
    turno siguiente, y eso basta porque la persona vuelve a escribir: pregunta por
    cobertura, sigue contando. Una solicitud de cotizacion no: quien termina de dar
    sus diecisiete campos **no vuelve a escribir**, se queda esperando. Sin esto,
    la respuesta existe, esta guardada, y no llega nunca.

    **Va del nucleo hacia el canal, que es la direccion que no existia.** El canal
    importa el nucleo y nunca al reves (convencion 5a), asi que el nucleo declara
    el puerto y la raiz enchufa quien lo cumple. El nucleo no sabe que hay colas,
    ni navegadores, ni pestanas abiertas: dice "hay algo que decir de este caso" y
    quien lo implemente sabra si hay alguien escuchando.
    """

    async def notify(  # noqa: PLR0913 -- la firma del puerto CaseNotifier
        self,
        tenant_id: str,
        case_id: str,
        *,
        text: str,
        citations: tuple[object, ...] = (),
        suggestions: tuple[str, ...] = (),
        coverage_outcome: str | None = None,
        language: Locale | None = None,
    ) -> bool:
        """Entrega el texto a quien escuche por ese caso. Devuelve si habia alguien.

        `language` es el idioma en que se compuso el texto: lo que el canal ponga
        junto a el --la tarjeta de la clausula, su rotulo-- va en ese idioma, que no
        siempre es el de la conversacion (una aseguradora que arranca en ingles y una
        persona que pregunta en espanol).

        El valor de retorno no es cortesia: sin el, el fondo no podria distinguir
        "entregado" de "nadie escuchaba", y las dos dejan rastros distintos en la
        traza. El texto llega **ya pasado por la guardia de salida**: quien
        implemente esto no decide nada sobre su contenido. Las citas son las vistas
        verificadas de una respuesta de cobertura y los botones, los que eligio el
        codigo (fase 1, 2026-10-08).
        """
        ...


__all__ = [
    "VOICE_RULES_MAX_WORDS",
    "CaseNotifier",
    "CaseTurnSupport",
    "EligibilityPort",
    "EligibilityView",
    "FinalText",
    "Handoff",
    "InboundTurn",
    "PartialText",
    "TurnError",
    "TurnEvent",
    "Waiting",
]
