"""Por donde va una pregunta rigida por la poliza (plan 09, punto 6, 2026-11-02).

Decision de Miguel: lo que la persona pregunta y es **un dato guardado en su poliza** --el
deducible, los limites, la vigencia, los vehiculos, los conductores, los endosos-- se contesta con
codigo desde el registro, sin recuperacion de clausulas, sin verificador de citas y sin un modelo
que lo redacte. Ahorra la llamada que lo redactaria y es exacto: el valor sale del registro, no de
lo que un modelo recuerde. Una pregunta de interpretacion --«¿me cubre un carro de alquiler?»--
sigue por la recuperacion con su cita verificada, como siempre.

**Que decide el modelo y que decide el codigo.** El modelo que ya entiende el mensaje propone un
tema de una lista cerrada (`UnderstandingResponse.rigid_topic`, valores de `base.RigidTopic`); no
elige el camino. Este modulo valida esa propuesta contra el estado del caso --el tipo de caso, que
la poliza este identificada, que el mensaje no traiga datos del reporte por anotar-- y solo entonces
pide la respuesta al puerto. Ninguna transicion del grafo sale de texto libre del modelo.

**Lo que no se hace aqui.** Sin la poliza identificada no se contesta: el turno sigue como siempre,
que es pedir la poliza. Si el puerto no la encuentra --otra aseguradora o inexistente, que la base
no distingue-- o el registro no trae el dato, tampoco: sigue la recuperacion. Y la respuesta que
sale de aqui **pasa por la guardia de salida** como todo texto hacia la persona (lo hace el turno).

Este modulo no importa `untangle.policy_rag`: un contrato de importacion prohibe que el modulo del
turno llegue a la recuperacion y a la verificacion de citas. Habla con el puerto `RigidFactsPort`,
que la raiz de composicion enchufa.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from untangle import observability
from untangle.base import Locale, RigidTopic
from untangle.case_record.models import RecordType
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration.nodes.intake.understanding import Answer, UnderstandingResponse, Want


@dataclass(frozen=True)
class RigidAnswerView:
    """La respuesta de una pregunta rigida, ya armada desde el registro de la poliza (plan 09, 6).

    Texto del catalogo con los valores de la poliza dentro. Todavia no pasa por la guardia de
    salida: eso lo hace el turno, como con cualquier otro texto.
    """

    topic: RigidTopic
    copy_key: CopyKey
    text: str


class RigidFactsPort(Protocol):
    """Quien contesta una pregunta por un dato de la poliza leyendo la poliza (plan 09, punto 6).

    Por puerto y no por importacion: el modulo del turno no puede llegar a `untangle.policy_rag`
    --un contrato de importacion lo prohibe, porque la recuperacion y la verificacion de citas
    van en el ritmo de fondo (BR2.3)--, y la raiz de composicion enchufa quien lo cumple. No hay
    recuperacion, ni verificador de citas, ni modelo detras de este puerto: lee el registro.
    """

    async def answer(  # noqa: PLR0913 -- el tema y el contexto del turno, ninguno derivable de otro
        self,
        tenant_id: str,
        policy_number: str,
        topic: RigidTopic,
        *,
        language: Locale,
        on: date,
        spoken: bool,
    ) -> RigidAnswerView | None:
        """La respuesta desde el registro, o `None` si esa poliza no existe para la aseguradora o
        el registro no trae el dato: el turno sigue entonces por el camino de siempre."""
        ...


#: Las intenciones con las que un tema rigido es la pregunta del mensaje. Con otra --un saludo,
#: pedir una persona, un tema fuera de la aseguradora, reportar un accidente-- el tema no manda.
_INTENCIONES_QUE_PREGUNTAN = frozenset(
    {Want.POLICY_QUESTION, Want.CONTINUE, Want.GENERAL_QUESTION, Want.OTHER}
)

#: Los tipos de caso donde se contesta: un reporte con la poliza ya identificada y una consulta. En
#: una solicitud de cotizacion no hay poliza emitida de la que leer.
_CASOS_CON_POLIZA = frozenset({RecordType.CLAIM, RecordType.COVERAGE_INQUIRY})


def topic_for(
    understood: UnderstandingResponse | None,
    *,
    record_type: RecordType,
    policy_identified: bool,
) -> RigidTopic | None:
    """El tema rigido que este turno contesta desde el registro, o `None` si sigue su camino.

    `None` en todo lo que no es una pregunta limpia por un dato de la poliza ya identificada:

    - sin lectura del modelo, o con el tema `none` (cualquier pregunta de interpretacion);
    - una intencion que no pregunta por la poliza;
    - un tipo de caso sin poliza emitida (la cotizacion);
    - la poliza todavia sin identificar: el turno la pide como siempre;
    - un mensaje que ademas trae datos del reporte por anotar: la captura va primero y no se
      pierde nada (el tema rigido se vuelve a preguntar);
    - un mensaje que contesta una pregunta de si o no pendiente.
    """
    if understood is None or understood.rigid_topic is RigidTopic.NONE:
        return None
    if understood.wants not in _INTENCIONES_QUE_PREGUNTAN:
        return None
    if record_type not in _CASOS_CON_POLIZA or not policy_identified:
        return None
    if record_type is RecordType.CLAIM and understood.items:
        return None
    if understood.answer is not Answer.NONE:
        return None
    return understood.rigid_topic


async def answer(  # noqa: PLR0913 -- el puerto, la poliza y el contexto del turno, ninguno derivable de otro
    port: RigidFactsPort | None,
    *,
    tenant_id: str,
    policy_number: str,
    topic: RigidTopic,
    language: Locale,
    on: date,
    spoken: bool,
) -> RigidAnswerView | None:
    """La respuesta del tema leida del registro, o `None` si el turno debe seguir su camino.

    `None` sin puerto (un despliegue que no lo enchufo), si la poliza no existe para la aseguradora
    o si el registro no trae el dato. Deja un evento por cada desenlace, sin el texto ni la poliza.
    """
    if port is None:
        observability.emit("orchestration.rigid_facts_not_wired", tenant_id=tenant_id)
        return None
    respuesta = await port.answer(
        tenant_id, policy_number, topic, language=language, on=on, spoken=spoken
    )
    observability.emit(
        "orchestration.rigid_facts",
        tenant_id=tenant_id,
        topic=topic.value,
        answered=respuesta is not None,
    )
    return respuesta


__all__ = ["RigidAnswerView", "RigidFactsPort", "answer", "topic_for"]
