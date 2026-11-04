"""El paso `clauses`: recuperar de la poliza las clausulas que se parecen a lo que paso.

La recuperacion es la de siempre (`policy_rag.corpus`): filtra por la poliza, busca por palabras y
por significado, fusiona por rango reciproco y cierra por relaciones. Lo que la decision cite de
aqui lo verifica despues el verificador exacto (`validation`), y solo lo verificado sale.

La consulta es el relato tal como lo conto la persona. Con la poliza fuera de vigencia, o sin
poliza, no se busca: no hay nada que se pueda citar.
"""

from __future__ import annotations

from untangle.adjuster.ports import AdjusterPorts
from untangle.policy_rag.corpus import api as corpus
from untangle.policy_rag.corpus.models import Clause, IssuedPolicy
from untangle.tenancy.models import TenantId

#: Hasta donde llega el relato en la consulta: mas largo no mejora la busqueda y encarece el embedding.
_MAX_QUERY_CHARS = 1500


async def find_policy(tenant_id: TenantId, policy_number: str) -> IssuedPolicy | None:
    """La poliza emitida de esa aseguradora, para el verificador de citas."""
    return await corpus.find_policy(tenant_id, policy_number=policy_number)


async def retrieve(
    tenant_id: TenantId, *, policy_number: str, narrative: str, ports: AdjusterPorts
) -> tuple[Clause, ...]:
    """Las clausulas recuperadas para ese relato, en el orden en que la fusion las dejo."""
    consulta = narrative[:_MAX_QUERY_CHARS] or " "
    (vector,) = await ports.embed([consulta])
    resultado = await corpus.retrieve(
        tenant_id,
        policy_number=policy_number,
        query_text=consulta,
        query_vector=vector,
        embedding_model=ports.embedding_model,
        now=ports.now(),
    )
    return tuple(resultado.clauses)
