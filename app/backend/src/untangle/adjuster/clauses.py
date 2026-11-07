"""El paso `clauses`: recuperar de la poliza las clausulas que se parecen a lo que paso.

La recuperacion es la de siempre (`policy_rag.corpus`): filtra por la poliza, busca por palabras y
por significado, fusiona por rango reciproco y cierra por relaciones. Lo que la decision cite de
aqui lo verifica despues el verificador exacto (`validation`), y solo lo verificado sale.

La consulta es el relato tal como lo conto la persona. Con la poliza fuera de vigencia, o sin
poliza, no se busca: no hay nada que se pueda citar.
"""

from __future__ import annotations

from untangle.adjuster.ports import AdjusterPorts
from untangle.base import Locale
from untangle.policy_rag.corpus import api as corpus
from untangle.policy_rag.corpus.models import Clause, IssuedPolicy
from untangle.tenancy.models import TenantId

#: Hasta donde llega el relato en la consulta: mas largo no mejora la busqueda y encarece el embedding.
_MAX_QUERY_CHARS = 1500


async def find_policy(tenant_id: TenantId, policy_number: str) -> IssuedPolicy | None:
    """La poliza emitida de esa aseguradora, para el verificador de citas."""
    return await corpus.find_policy(tenant_id, policy_number=policy_number)


#: La segunda consulta, fija: la cobertura que mas decide un siniestro de auto. Sin ella, un relato
#: que no menciona la palabra de la cobertura (un choque trasero «contado» como lo vivio la
#: persona) puede traer deberes y definiciones y dejar fuera la clausula que lo cubre.
_COVERAGE_QUERY = {
    "es": "cobertura de daños propios al vehículo asegurado por choque o colisión, y su deducible",
    "en": "coverage for damage to the insured's own vehicle from a collision, and its deductible",
}

#: La tercera: las exclusiones que se miran antes de aprobar. Aprobar sin haberlas buscado es el
#: error caro (uso comercial o de plataformas, conductores no declarados, actos intencionales).
_EXCLUSIONS_QUERY = {
    "es": "exclusiones de la cobertura: uso comercial o de plataformas, conductores no declarados, "
    "actos intencionales y otros casos que la póliza no cubre",
    "en": "coverage exclusions: commercial or platform use, undeclared drivers, intentional acts "
    "and other cases the policy does not cover",
}


async def retrieve(
    tenant_id: TenantId,
    *,
    policy_number: str,
    narrative: str,
    language: Locale,
    ports: AdjusterPorts,
) -> tuple[Clause, ...]:
    """Las clausulas recuperadas para el relato, para la cobertura de daños propios y para las exclusiones.

    Primero las del relato, en el orden en que la fusion las dejo, y despues las de las otras dos
    consultas que no estaban ya. Una sola llamada de embeddings para las tres.
    """
    relato = narrative[:_MAX_QUERY_CHARS] or " "
    consultas = [relato, _COVERAGE_QUERY[language], _EXCLUSIONS_QUERY[language]]
    vectores = await ports.embed(consultas)
    por_id: dict[str, Clause] = {}
    for consulta, vector in zip(consultas, vectores, strict=True):
        resultado = await corpus.retrieve(
            tenant_id,
            policy_number=policy_number,
            query_text=consulta,
            query_vector=vector,
            embedding_model=ports.embedding_model,
            now=ports.now(),
        )
        for clausula in resultado.clauses:
            por_id.setdefault(clausula.clause_id, clausula)
    return tuple(por_id.values())
