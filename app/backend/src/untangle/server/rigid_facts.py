"""El puerto de los datos rigidos de la poliza, cableado a `policy_rag.facts` (plan 09, punto 6).

El modulo del turno no puede llegar a `untangle.policy_rag` (un contrato de importacion lo
prohibe: la recuperacion y la verificacion de citas van en el ritmo de fondo), asi que declara el
puerto `RigidFactsPort` y la raiz de composicion enchufa quien lo cumple. Este adaptador solo
traduce: lee el registro por `policy_rag.facts.api` --que abre la sesion por el punto unico, con el
`tenant_id` fijado-- y devuelve la respuesta en la forma del contrato del turno.

No hay recuperacion, ni verificador de citas, ni proveedor de modelo detras: lee la base.
"""

from __future__ import annotations

from datetime import date

from untangle.base import Locale, RigidTopic
from untangle.orchestration.rigid_route import RigidAnswerView
from untangle.policy_rag.facts import api as facts

__all__ = ["PolicyFactsAdapter"]


class PolicyFactsAdapter:
    """Cumple `RigidFactsPort` leyendo la poliza emitida de la aseguradora del turno."""

    async def answer(  # noqa: PLR0913 -- la firma del puerto `RigidFactsPort`
        self,
        tenant_id: str,
        policy_number: str,
        topic: RigidTopic,
        *,
        language: Locale,
        on: date,
        spoken: bool,
    ) -> RigidAnswerView | None:
        respuesta = await facts.rigid_answer(
            tenant_id, policy_number, topic, language=language, on=on, spoken=spoken
        )
        if respuesta is None:
            return None
        return RigidAnswerView(
            topic=respuesta.topic, copy_key=respuesta.copy_key, text=respuesta.text
        )
