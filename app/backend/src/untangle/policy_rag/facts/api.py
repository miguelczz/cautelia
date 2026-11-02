"""La superficie de `policy_rag.facts`: los datos rigidos de una poliza emitida (plan 09, punto 6).

Lo que consumen la respuesta del chat y de la llamada (por un puerto que enchufa la raiz de
composicion), el servidor MCP (`untangle.policy_mcp`) y, mas adelante, el subagente ajustador.
Todas las funciones leen **la poliza de esa aseguradora y de ninguna otra**: la lectura pasa por
`corpus.find_policy`, que abre la sesion por el punto unico (`tenancy.session_for`) con el
`tenant_id` fijado, y la politica de fila de la base filtra el resto.

**`None` es «esa poliza no existe para esta aseguradora».** Una poliza inexistente y la de otra
aseguradora devuelven lo mismo (BR2.6): el codigo nunca llega a saber cual de las dos era. Una
lista vacia es otra cosa --la poliza existe y no trae nada de eso--.

No llama a ningun proveedor y no lee el reloj: la fecha de vigencia la entrega quien llama.
"""

from __future__ import annotations

from datetime import date

from untangle.base import Locale, RigidTopic
from untangle.policy_rag.corpus import repository as corpus
from untangle.policy_rag.facts import records, rigid
from untangle.policy_rag.facts.models import (
    ClauseFact,
    DeductibleFact,
    DriverFact,
    EndorsementFact,
    LimitFact,
    PolicySummary,
    VehicleFact,
)
from untangle.policy_rag.facts.rigid import RigidAnswer
from untangle.tenancy.models import TenantId


async def policy_summary(
    tenant_id: TenantId, policy_number: str, *, on: date
) -> PolicySummary | None:
    """Titular, emisora, periodo y si rige en `on`."""
    poliza = await corpus.find_policy(tenant_id, policy_number=policy_number)
    return None if poliza is None else records.summarize(poliza, on=on)


async def limits(
    tenant_id: TenantId, policy_number: str, *, language: Locale
) -> tuple[LimitFact, ...] | None:
    """Los limites de la poliza, con los montos escritos para el idioma."""
    poliza = await corpus.find_policy(tenant_id, policy_number=policy_number)
    return None if poliza is None else records.limits_of(poliza, language=language)


async def deductibles(
    tenant_id: TenantId, policy_number: str, *, language: Locale
) -> tuple[DeductibleFact, ...] | None:
    """Los deducibles de la poliza, con los montos escritos para el idioma."""
    poliza = await corpus.find_policy(tenant_id, policy_number=policy_number)
    return None if poliza is None else records.deductibles_of(poliza, language=language)


async def vehicles(tenant_id: TenantId, policy_number: str) -> tuple[VehicleFact, ...] | None:
    """Los vehiculos asegurados por su descripcion."""
    poliza = await corpus.find_policy(tenant_id, policy_number=policy_number)
    return None if poliza is None else records.vehicles_of(poliza)


async def drivers(tenant_id: TenantId, policy_number: str) -> tuple[DriverFact, ...] | None:
    """Los conductores que la poliza declara. Vacia es «no declara conductores»."""
    poliza = await corpus.find_policy(tenant_id, policy_number=policy_number)
    return None if poliza is None else records.drivers_of(poliza)


async def endorsements(
    tenant_id: TenantId, policy_number: str, *, language: Locale
) -> tuple[EndorsementFact, ...] | None:
    """Los endosos de la poliza y que clausulas cambia cada uno."""
    poliza = await corpus.find_policy(tenant_id, policy_number=policy_number)
    if poliza is None:
        return None
    claves = await corpus.clause_keys_of_forms(tenant_id, form_ids=poliza.endorsement_ids)
    return records.endorsements_of(poliza, clause_keys=claves, language=language)


async def clause(tenant_id: TenantId, policy_number: str, clause_id: str) -> ClauseFact | None:
    """Una clausula por su identificador, **solo si pertenece a esa poliza**.

    Pertenece cuando es del formulario base de la poliza o de uno de sus endosos: la misma regla
    del verificador de citas. Una clausula de otro formulario, de otra aseguradora o que no existe
    devuelve lo mismo, `None`. Las clausulas senuelo del corpus no se devuelven nunca.
    """
    poliza = await corpus.find_policy(tenant_id, policy_number=policy_number)
    if poliza is None:
        return None
    encontradas = await corpus.clauses_by_ids(tenant_id, clause_ids=[clause_id])
    for c in encontradas:
        pertenece = c.form_id == poliza.form_id or c.form_id in poliza.endorsement_ids
        if pertenece and not c.is_distractor:
            return ClauseFact(
                clause_id=c.clause_id,
                clause_key=c.clause_key,
                form_id=c.form_id,
                form_version=c.form_version,
                part=c.part,
                language=c.language,
                text=c.text,
            )
    return None


async def rigid_answer(  # noqa: PLR0913 -- el tema y el contexto del turno, ninguno derivable de otro
    tenant_id: TenantId,
    policy_number: str,
    topic: RigidTopic,
    *,
    language: Locale,
    on: date,
    spoken: bool = False,
) -> RigidAnswer | None:
    """La respuesta de una pregunta rigida desde el registro, o `None`.

    `None` si la poliza no existe para esa aseguradora, si el tema no es rigido o si el registro
    no trae el dato: en los tres casos quien llama sigue por el camino de siempre.
    """
    if topic is RigidTopic.NONE:
        return None
    poliza = await corpus.find_policy(tenant_id, policy_number=policy_number)
    if poliza is None:
        return None
    claves = (
        await corpus.clause_keys_of_forms(tenant_id, form_ids=poliza.endorsement_ids)
        if topic is RigidTopic.ENDORSEMENTS
        else {}
    )
    return rigid.render(topic, poliza, language=language, on=on, spoken=spoken, clause_keys=claves)


__all__ = [
    "ClauseFact",
    "DeductibleFact",
    "DriverFact",
    "EndorsementFact",
    "LimitFact",
    "PolicySummary",
    "RigidAnswer",
    "VehicleFact",
    "clause",
    "deductibles",
    "drivers",
    "endorsements",
    "limits",
    "policy_summary",
    "rigid_answer",
    "vehicles",
]
