"""La superficie publica de `policy_rag.corpus`: ingerir el corpus de U7 y recuperarlo (C-18).

Lo que `policy_rag.citations` (el verificador) y la raiz de composicion
(`untangle.server.corpus_ingest`) consumen de aqui, y nada mas. `retrieve`
llega en el paso 4 de esta unidad (tanda 2): filtra por poliza, busca lexico y
vectorial, fusiona por rango reciproco y cierra por relaciones (BR2.1 a BR2.6).
"""

from __future__ import annotations

from untangle.policy_rag.corpus.ingest import (
    EmbeddingClient,
    IngestionReport,
    IngestionSources,
    ingest_all,
    ingest_tenant,
)
from untangle.policy_rag.corpus.loading import CorpusValidationError, ManifestMismatchError
from untangle.policy_rag.corpus.models import Clause, ClauseRelation, IssuedPolicy, PolicyForm
from untangle.policy_rag.corpus.prompting import clause_as_prompt_content, clauses_as_prompt_content
from untangle.policy_rag.corpus.repository import (
    amending_forms,
    clause_keys_of_forms,
    clauses_of_form,
    find_policy,
    find_policy_by_national_id,
    list_forms,
    list_policies,
    relations_into,
)
from untangle.policy_rag.corpus.retrieval import (
    DEFAULT_LIMIT,
    ClauseSource,
    RetrievalProbe,
    RetrievalResult,
    retrieve,
)

__all__ = [
    "DEFAULT_LIMIT",
    "Clause",
    "ClauseRelation",
    "ClauseSource",
    "CorpusValidationError",
    "EmbeddingClient",
    "IngestionReport",
    "IngestionSources",
    "IssuedPolicy",
    "ManifestMismatchError",
    "PolicyForm",
    "RetrievalProbe",
    "RetrievalResult",
    "amending_forms",
    "clause_as_prompt_content",
    "clause_keys_of_forms",
    "clauses_as_prompt_content",
    "clauses_of_form",
    "find_policy",
    "find_policy_by_national_id",
    "ingest_all",
    "ingest_tenant",
    "list_forms",
    "list_policies",
    "relations_into",
    "retrieve",
]
