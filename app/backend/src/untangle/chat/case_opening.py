"""Cuando nace el caso de una conversacion, y con que tipo (BR1.1 de U11).

**Este archivo existe porque faltaba, y su falta dejaba el chat sin atender a
nadie.** U11 construyo `identity.open_case` --"abre el caso en el primer turno,
antes de pedir nada"-- y nadie la llamaba: la exportaba y su unico consumidor era
su propia prueba. U12 escribio en el docstring de `UnaddressedTurnError` que
"cablear cuando nace un caso es de U13/U16" y levanta si el turno llega sin caso.
U13 entregaba el turno con `case_id` en nulo confiando en que "el grafo lo dira
por su cuenta si lo necesitaba". Las tres unidades correctas por dentro, y la
costura entre ellas sin dueno: el primer mensaje de cualquier visitante moria en
una tarea que nadie esperaba.

**Por que el canal y no el grafo.** La frontera es la que U12 dejo escrita, y su
razon se sostiene: el tipo de registro, el canal y el **origen** son datos del
canal. El origen en particular decide que borra el reinicio nocturno (BR4.6 de
U4): una conversacion publica es dato de visitante y una corrida de evaluaciones
no lo es. El grafo no tiene forma de distinguirlas, y el que entrega el turno si.

**Por que el tipo lo decide una regla y no el modelo.** `ReportIntent` tiene dos
valores y el chat no tiene ningun boton que los ofrezca, asi que alguien tiene que
leerlo del primer mensaje. Lo lee el reconocedor determinista que U12 ya escribio
para el desvio de cobertura --el mismo, no una copia-- porque la regla del
proyecto es literal: la categoria y la derivacion las deciden las reglas, no el
modelo. Preguntar por cobertura abre una consulta (dos campos, sin pregunta de
seguridad); cualquier otra cosa abre un siniestro (siete campos, con ella), que es
exactamente el reparto de BR1.1.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from collections.abc import Iterable
from datetime import datetime

from untangle.base import Locale
from untangle.case_record.models import Channel, Origin, RecordType
from untangle.orchestration import coverage_detour, quote_reply, stated_purpose
from untangle.orchestration.nodes.intake import identity
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.models import TenantId


def new_case_id() -> str:
    """El identificador del caso: opaco y sin orden.

    No es el numero del caso --ese lo acuna U4 contra los ya tomados-- sino su
    llave. Aleatorio a proposito: un identificador correlativo deja ver cuantos
    casos lleva la demostracion a cualquiera que reciba uno.
    """
    return f"case-{uuid.uuid4().hex[:16]}"


def intent_of(text: str, *, language: Locale, quote_enabled: bool = False) -> identity.ReportIntent:
    """BR1.1: cual de los tipos abre este primer mensaje.

    **Pedir cotizar abre una solicitud solo donde la aseguradora la tiene activa** (U19,
    BR1.5): es un dato de su configuracion, no una rama por aseguradora. Donde esta apagada
    el caso se abre como siniestro y el turno responde con la frase de AC6.1.3 antes de
    capturar nada (`quote_reply.reply_before_capture`).

    El reconocedor es el de U12 (`coverage_detour`), no uno propio: si algun dia
    se amplia para reconocer una forma nueva de preguntar por cobertura, el desvio
    dentro de un siniestro y la apertura de una consulta se amplian juntos. Dos
    reconocedores para la misma pregunta es como uno de los dos se queda viejo.
    """
    if quote_enabled and quote_reply.is_quote_request(text, language=language):
        return identity.ReportIntent.QUOTE_REQUEST
    if coverage_detour.is_coverage_question(text, language=language):
        return identity.ReportIntent.COVERAGE_INQUIRY
    return identity.ReportIntent.CLAIM


#: El tipo de caso que decidio la comprension, como la intencion que abre el caso.
_INTENCION_DEL_TIPO: dict[RecordType, identity.ReportIntent] = {
    RecordType.CLAIM: identity.ReportIntent.CLAIM,
    RecordType.COVERAGE_INQUIRY: identity.ReportIntent.COVERAGE_INQUIRY,
    RecordType.QUOTE_REQUEST: identity.ReportIntent.QUOTE_REQUEST,
}


def intent_for(record_type: RecordType) -> identity.ReportIntent:
    """La intencion que abre un caso de ese tipo (fase 0, 2026-10-07)."""
    return _INTENCION_DEL_TIPO[record_type]


#: Lo que cabe en un saludo sin pedido: saludos, cortesias y el nombre de la
#: agente, en los dos idiomas y ya sin tildes. Una sola palabra que no este aqui
#: --"choque", "cubre", "cotizar"-- y el mensaje ya dice algo.
_PALABRAS_DE_SALUDO = frozenset(
    {
        "hola", "holi", "ola", "buenas", "buenos", "buen", "dia", "dias", "tardes",
        "noches", "que", "tal", "como", "esta", "estas", "saludos", "alo", "hey",
        "ey", "oye", "senora", "senor", "senorita", "muy",
        "hello", "hi", "hiya", "good", "morning", "afternoon", "evening", "there",
        "how", "are", "you", "doing", "greetings", "yo",
    }
)  # fmt: skip

#: Mas palabras que esto ya no es un saludo suelto, aunque todas lo parezcan.
_MAXIMO_DE_PALABRAS_DE_SALUDO = 6

#: Como se llaman las agentes, sin tildes: "hola Isabel" tambien es solo un saludo.
#: Las instala la raiz de composicion desde la carpeta de cada aseguradora.
_AGENTES: frozenset[str] = frozenset({"catalina"})


def _sin_tildes(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text.casefold()) if not unicodedata.combining(c)
    )


def install_agent_names(names: Iterable[str]) -> None:
    """Los nombres de las agentes de las aseguradoras cargadas."""
    global _AGENTES
    _AGENTES = frozenset(_sin_tildes(nombre) for nombre in names if nombre.strip())


def is_greeting_only(text: str) -> bool:
    """Si el primer mensaje solo saluda, sin decir que necesita (2026-10-07).

    Por reglas y sin modelo, como el resto de la clasificacion del primer turno:
    "hola", "buenas tardes", "hola, ¿como estas?" son saludos; "hola, tuve un
    choque" no lo es y abre el reporte como siempre.
    """
    palabras = re.findall(r"[a-z]+", _sin_tildes(text))
    return 0 < len(palabras) <= _MAXIMO_DE_PALABRAS_DE_SALUDO and all(
        palabra in _PALABRAS_DE_SALUDO or palabra in _AGENTES for palabra in palabras
    )


def has_not_said_what_for(text: str, *, language: Locale) -> bool:
    """Si el primer mensaje, leido por reglas, todavia no dice a que viene la persona (2026-10-13).

    Es el respaldo del chat cuando el modelo que entiende los mensajes falla o tarda, y junta
    los dos casos que no abren ningun caso: el saludo suelto (`is_greeting_only`) y el que solo
    **anuncia** que quiere consultar algo --«queria consultar algo», «tengo una pregunta»,
    «necesito ayuda»--. Sin esto el segundo caia en `intent_of`, que devuelve un siniestro por
    omision, y abria el reporte de un accidente que nadie habia contado.

    El vocabulario del anuncio no es de este canal: lo comparte con la llamada
    (`stated_purpose`), y el modelo ya lo lee como un saludo (valor `greeting`). Conservadora,
    como esa: una sola palabra de contenido --«poliza», «choque», «cotizar»-- y el mensaje ya
    dice algo.
    """
    return is_greeting_only(text) or stated_purpose.says_nothing_about_purpose(
        text, language=language
    )


def _quote_enabled(tenant_id: TenantId) -> bool:
    """Si esa aseguradora tiene la cotizacion activa, leido de su configuracion (BR1.5)."""
    aseguradora = tenancy_config.loaded().get(tenant_id)
    return aseguradora is not None and aseguradora.quote_enabled


async def open_for_first_turn(  # noqa: PLR0913 -- el mensaje y su contexto, por nombre
    tenant_id: TenantId,
    *,
    text: str,
    language: Locale,
    origin: Origin,
    now: datetime,
    intent: identity.ReportIntent | None = None,
    continues_case_id: str | None = None,
) -> str:
    """Abre el caso de esta conversacion y devuelve su identificador (BR1.1).

    `intent` es el tipo que ya decidio la comprension del primer mensaje (fase 0,
    2026-10-07); sin ella, lo deciden las reglas de `intent_of`, como antes.
    `continues_case_id` es el caso del que viene, cuando la persona cambio de tema en mitad
    de la conversacion (2026-10-13): queda escrito en el caso nuevo para leer la conversacion
    a traves de los dos.

    No escribe el turno ni lo entrega: solo abre. Quien llama ata el caso a la
    conversacion antes de seguir, porque un caso abierto que ninguna conversacion
    reclama es un caso que el turno siguiente vuelve a abrir.
    """
    vista = await identity.open_case(
        tenant_id,
        identity.OpeningRequest(
            case_id=new_case_id(),
            intent=intent
            or intent_of(text, language=language, quote_enabled=_quote_enabled(tenant_id)),
            channel=Channel.CHAT,
            origin=origin,
            language=language,
            continues_case_id=continues_case_id,
        ),
        now=now,
    )
    return vista.case_id


__all__ = [
    "has_not_said_what_for",
    "install_agent_names",
    "intent_for",
    "intent_of",
    "is_greeting_only",
    "new_case_id",
    "open_for_first_turn",
]
