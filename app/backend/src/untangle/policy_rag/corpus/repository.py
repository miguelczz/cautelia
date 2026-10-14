"""Las escrituras y lecturas del corpus, todas por el punto unico de sesion (BR1.7).

Ningun modulo de `policy_rag` abre su propia conexion (SEC-U8.5): toda consulta
pasa por `untangle.tenancy.api`, con la aseguradora ya fijada, igual que hace
`rules/repository.py` con `rule_evaluation`.

**El vector, sin paquete nuevo.** No hay adaptador de `pgvector` para
SQLAlchemy ni para el driver: el vector viaja como el texto que pgvector
espera -- `[0.1,0.2,...]` -- ligado como parametro y convertido con
`CAST(:embedding AS vector)`, exactamente como U9 convierte sus columnas JSON
con `CAST(:x AS jsonb)` porque el driver no adapta un `dict`/`list` de Python
por si solo (`rules/repository.py`).

**Los cuatro catalogos del corpus se escriben con `INSERT ... ON CONFLICT DO
UPDATE`, nunca con un borrado seguido de una insercion.** `clause_index`
cuelga de `clauses` con `ON DELETE CASCADE` (BR1.3, para que una clausula que
de verdad desaparece del corpus se lleve su entrada del indice); un borrado
masivo de `clauses` en cada ingesta arrastraria **todo** el indice con ella, y
entonces BR1.5 -- cero llamadas al proveedor al reingestar sin cambios --
seria imposible de cumplir: cada corrida volveria a encontrar la tabla vacia.
El `UPSERT` dice lo mismo en menos filas tocadas y deja vivo lo que no cambio.

Lo que **si** se compara explicitamente antes de escribir es `clause_index`
(BR1.5): ahi esta el costo real -- una llamada al proveedor por clausula -- y
ahi es donde reingestar sin cambios tiene que costar cero.

**Limite conocido, declarado y no escondido.** Esta version no borra una fila
de `policy_forms`, `clauses`, `clause_relations` o `issued_policies` cuyo
identificador desaparecio de `app/data/` entre dos corridas: ningun criterio
de esta unidad ejercita ese camino (el corpus de U7 crece o se corrige, no se
encoge), y anadirlo sin una prueba que lo pida seria codigo sin caso previo.
Si algun dia hace falta, la comprobacion es la misma que BR1.2 ya hace al
leer: comparar los identificadores del corpus contra los que ya hay en la
base y borrar la diferencia.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime

from untangle.policy_rag.corpus.models import (
    Clause,
    ClauseIndexEntry,
    ClauseRelation,
    IssuedPolicy,
    PolicyForm,
)
from untangle.providers.ports import Vector
from untangle.tenancy import api as tenancy
from untangle.tenancy.models import TenantId

#: La configuracion de `to_tsvector` por idioma de la clausula (TECH-U8.4). El
#: idioma de la conversacion no interviene aqui: el lematizador tiene que ser
#: el del texto que se indexa, o degrada justo la busqueda que deberia ayudar.
_TSVECTOR_CONFIG: dict[str, str] = {"es": "spanish", "en": "english"}

_UPSERT_FORMULARIO = """
    INSERT INTO policy_forms
        (tenant_id, form_id, form_version, form_kind, language, issuer_label,
         issuer_tenant, jurisdiction_ref)
    VALUES
        (:tenant_id, :form_id, :form_version, :form_kind, :language, :issuer_label,
         :issuer_tenant, :jurisdiction_ref)
    ON CONFLICT (tenant_id, form_id, form_version) DO UPDATE SET
        form_kind = EXCLUDED.form_kind,
        language = EXCLUDED.language,
        issuer_label = EXCLUDED.issuer_label,
        issuer_tenant = EXCLUDED.issuer_tenant,
        jurisdiction_ref = EXCLUDED.jurisdiction_ref
"""

_UPSERT_CLAUSULA = """
    INSERT INTO clauses
        (tenant_id, clause_id, clause_key, form_id, form_version, part, language,
         text, is_distractor, issuer_label)
    VALUES
        (:tenant_id, :clause_id, :clause_key, :form_id, :form_version, :part, :language,
         :text, :is_distractor, :issuer_label)
    ON CONFLICT (tenant_id, clause_id) DO UPDATE SET
        clause_key = EXCLUDED.clause_key,
        form_id = EXCLUDED.form_id,
        form_version = EXCLUDED.form_version,
        part = EXCLUDED.part,
        language = EXCLUDED.language,
        text = EXCLUDED.text,
        is_distractor = EXCLUDED.is_distractor,
        issuer_label = EXCLUDED.issuer_label
"""

_UPSERT_RELACION = """
    INSERT INTO clause_relations (tenant_id, relation_id, from_clause, to_clause, relation)
    VALUES (:tenant_id, :relation_id, :from_clause, :to_clause, :relation)
    ON CONFLICT (tenant_id, relation_id) DO NOTHING
"""

_UPSERT_POLIZA = """
    INSERT INTO issued_policies
        (tenant_id, policy_number, issuer_tenant, form_id, form_version, endorsement_ids,
         named_insured, drivers, vehicles, limits_and_deductibles, period_start, period_end)
    VALUES
        (:tenant_id, :policy_number, :issuer_tenant, :form_id, :form_version,
         CAST(:endorsement_ids AS jsonb), CAST(:named_insured AS jsonb),
         CAST(:drivers AS jsonb), CAST(:vehicles AS jsonb),
         CAST(:limits_and_deductibles AS jsonb), :period_start, :period_end)
    ON CONFLICT (tenant_id, policy_number) DO UPDATE SET
        issuer_tenant = EXCLUDED.issuer_tenant,
        form_id = EXCLUDED.form_id,
        form_version = EXCLUDED.form_version,
        endorsement_ids = EXCLUDED.endorsement_ids,
        named_insured = EXCLUDED.named_insured,
        drivers = EXCLUDED.drivers,
        vehicles = EXCLUDED.vehicles,
        limits_and_deductibles = EXCLUDED.limits_and_deductibles,
        period_start = EXCLUDED.period_start,
        period_end = EXCLUDED.period_end
"""


async def upsert_reference_data(
    tenant_id: TenantId,
    *,
    forms: Sequence[PolicyForm],
    clauses: Sequence[Clause],
    relations: Sequence[ClauseRelation],
    policies: Sequence[IssuedPolicy],
) -> None:
    """Escribe el corpus de referencia de una aseguradora, en una sola transaccion.

    El orden de escritura respeta las llaves foraneas: formularios antes que
    clausulas y polizas, clausulas antes que relaciones. Cada fila se resuelve
    por `ON CONFLICT` sobre su llave natural (BR1.3): reingestar sin cambios no
    toca ninguna fila que ya coincida, y una clausula editada llega con su
    texto nuevo sin arrastrar a `clause_index`, que cuelga de `clauses` y no de
    esta transaccion.
    """
    async with tenancy.session_for(tenant_id) as sesion:
        for formulario in forms:
            await tenancy.execute_sql(
                sesion,
                _UPSERT_FORMULARIO,
                tenant_id=formulario.tenant_id,
                form_id=formulario.form_id,
                form_version=formulario.form_version,
                form_kind=formulario.form_kind.value,
                language=formulario.language,
                issuer_label=formulario.issuer_label,
                issuer_tenant=formulario.issuer_tenant,
                jurisdiction_ref=formulario.jurisdiction_ref,
            )

        for clausula in clauses:
            await tenancy.execute_sql(
                sesion,
                _UPSERT_CLAUSULA,
                tenant_id=clausula.tenant_id,
                clause_id=clausula.clause_id,
                clause_key=clausula.clause_key,
                form_id=clausula.form_id,
                form_version=clausula.form_version,
                part=clausula.part,
                language=clausula.language,
                text=clausula.text,
                is_distractor=clausula.is_distractor,
                issuer_label=clausula.issuer_label,
            )

        for relacion in relations:
            await tenancy.execute_sql(
                sesion,
                _UPSERT_RELACION,
                tenant_id=relacion.tenant_id,
                relation_id=relacion.relation_id,
                from_clause=relacion.from_clause,
                to_clause=relacion.to_clause,
                relation=relacion.relation.value,
            )

        for poliza in policies:
            await tenancy.execute_sql(
                sesion,
                _UPSERT_POLIZA,
                tenant_id=poliza.tenant_id,
                policy_number=poliza.policy_number,
                issuer_tenant=poliza.issuer_tenant,
                form_id=poliza.form_id,
                form_version=poliza.form_version,
                endorsement_ids=json.dumps(list(poliza.endorsement_ids)),
                named_insured=json.dumps(poliza.named_insured),
                drivers=json.dumps([d.model_dump() for d in poliza.drivers]),
                vehicles=json.dumps(list(poliza.vehicles)),
                limits_and_deductibles=json.dumps(poliza.limits_and_deductibles),
                period_start=poliza.period_start,
                period_end=poliza.period_end,
            )


_LEER_INDICE = """
    SELECT clause_id, content_hash
    FROM clause_index
    WHERE tenant_id = :tenant_id AND embedding_model = :embedding_model
"""


async def existing_content_hashes(tenant_id: TenantId, *, embedding_model: str) -> dict[str, str]:
    """El `content_hash` ya indexado de cada clausula, para ese modelo (BR1.5, BR1.6).

    Indexado **por modelo**: el identificador del modelo es parte de la clave
    (BR1.6), asi que cambiar de modelo no encuentra nada indexado y reingesta
    todo, sin mezclar vectores de dos modelos.
    """
    async with tenancy.session_for(tenant_id) as sesion:
        filas = await tenancy.fetch_all(
            sesion, _LEER_INDICE, tenant_id=tenant_id, embedding_model=embedding_model
        )
    return {str(fila["clause_id"]): str(fila["content_hash"]) for fila in filas}


def _vector_literal(vector: Vector) -> str:
    """El vector en el formato de texto que pgvector espera: `[0.1,0.2,...]`.

    Nunca coma flotante de Python impreso con `str()` a secas: `repr(float)`
    ya da la forma mas corta que reproduce el valor exacto, y es la misma que
    usa el resto del proyecto para numeros que no son dinero (`ports.py`,
    `Vector`).
    """
    return "[" + ",".join(repr(componente) for componente in vector) + "]"


_UPSERT_INDICE = """
    INSERT INTO clause_index
        (tenant_id, clause_id, embedding_model, content_hash, indexed_at,
         lexical_vector, embedding)
    VALUES
        (:tenant_id, :clause_id, :embedding_model, :content_hash, :indexed_at,
         to_tsvector(CAST(:tsvector_config AS regconfig), :text),
         CAST(:embedding AS vector))
    ON CONFLICT (tenant_id, clause_id, embedding_model) DO UPDATE SET
        content_hash = EXCLUDED.content_hash,
        indexed_at = EXCLUDED.indexed_at,
        lexical_vector = EXCLUDED.lexical_vector,
        embedding = EXCLUDED.embedding
"""


async def upsert_index_entries(
    tenant_id: TenantId,
    *,
    embedding_model: str,
    entries: Sequence[tuple[ClauseIndexEntry, Clause, Vector]],
    indexed_at: datetime,
) -> None:
    """Escribe o actualiza una entrada del indice por clausula (BR1.3, BR1.6).

    Cada entrada trae su propia clausula para calcular `lexical_vector` con el
    idioma correcto (TECH-U8.4): la columna no es generada -- PostgreSQL no
    admite una subconsulta contra otra tabla ahi dentro -- asi que el `config`
    de `to_tsvector` viaja como parametro, resuelto aqui y no en la base.

    **La dimension la comprueba este codigo, no la columna.** `clause_index`
    declara `vector` sin dimension fija a proposito (BR1.6: el identificador del
    modelo es parte de la clave para que dos modelos convivan, y uno de otra
    dimension no cabria en una columna fija). Lo que no puede pasar es que una
    misma escritura mezcle dimensiones dentro del mismo modelo: eso no es un
    modelo nuevo, es un vector roto, y la busqueda por distancia fallaria mas
    tarde y lejos de aqui.
    """
    dimensiones = {len(vector) for _, _, vector in entries}
    if len(dimensiones) > 1:
        msg = (
            f"el modelo '{embedding_model}' entrego vectores de dimensiones distintas "
            f"en la misma escritura: {sorted(dimensiones)}"
        )
        raise ValueError(msg)

    async with tenancy.session_for(tenant_id) as sesion:
        for entrada, clausula, vector in entries:
            configuracion = _TSVECTOR_CONFIG.get(clausula.language)
            if configuracion is None:  # pragma: no cover -- Locale ya cierra los dos valores
                msg = f"idioma sin configuracion de tsvector: '{clausula.language}'"
                raise ValueError(msg)
            await tenancy.execute_sql(
                sesion,
                _UPSERT_INDICE,
                tenant_id=tenant_id,
                clause_id=entrada.clause_id,
                embedding_model=embedding_model,
                content_hash=entrada.content_hash,
                indexed_at=indexed_at,
                tsvector_config=configuracion,
                text=clausula.text,
                embedding=_vector_literal(vector),
            )


# --- Recuperacion filtrada (paso 4, tanda 2: BR2.1 a BR2.6) --------------------

_LEER_POLIZA = """
    SELECT tenant_id, policy_number, issuer_tenant, form_id, form_version, endorsement_ids,
           named_insured, drivers, vehicles, limits_and_deductibles, period_start, period_end
    FROM issued_policies
    WHERE tenant_id = :tenant_id AND policy_number = :policy_number
"""


async def find_policy(tenant_id: TenantId, *, policy_number: str) -> IssuedPolicy | None:
    """La poliza de quien pregunta, o nada.

    Una poliza inexistente y una de otra aseguradora devuelven **lo mismo**
    (BR2.6): la politica de fila ya filtro la segunda antes de que esta
    consulta la viera, asi que no hay aqui ninguna rama que las distinga -- ni
    falta que hace, porque el codigo nunca llega a saber cual de las dos era.
    """
    async with tenancy.session_for(tenant_id) as sesion:
        fila = await tenancy.fetch_one(
            sesion, _LEER_POLIZA, tenant_id=tenant_id, policy_number=policy_number
        )
    return IssuedPolicy.model_validate(dict(fila)) if fila is not None else None


# --- La pestana de polizas (fase 2, 2026-10-08) ------------------------------

_LISTAR_POLIZAS = """
    SELECT tenant_id, policy_number, issuer_tenant, form_id, form_version, endorsement_ids,
           named_insured, drivers, vehicles, limits_and_deductibles, period_start, period_end
    FROM issued_policies
    WHERE tenant_id = :tenant_id
    ORDER BY policy_number
"""

_CLAVES_DE_FORMULARIOS = """
    SELECT form_id, clause_key
    FROM clauses
    WHERE tenant_id = :tenant_id AND form_id = ANY(:form_ids) AND NOT is_distractor
    ORDER BY form_id, clause_key
"""


async def list_policies(tenant_id: TenantId) -> tuple[IssuedPolicy, ...]:
    """Las polizas emitidas de la aseguradora, por numero: las de ejemplo de la demo."""
    async with tenancy.session_for(tenant_id) as sesion:
        filas = await tenancy.fetch_all(sesion, _LISTAR_POLIZAS, tenant_id=tenant_id)
    return tuple(IssuedPolicy.model_validate(dict(fila)) for fila in filas)


async def clause_keys_of_forms(
    tenant_id: TenantId, *, form_ids: Sequence[str]
) -> dict[str, tuple[str, ...]]:
    """Que clausulas trae cada formulario, por su clave: lo que modifica un endoso."""
    if not form_ids:
        return {}
    async with tenancy.session_for(tenant_id) as sesion:
        filas = await tenancy.fetch_all(
            sesion, _CLAVES_DE_FORMULARIOS, tenant_id=tenant_id, form_ids=list(form_ids)
        )
    claves: dict[str, list[str]] = {}
    for fila in filas:
        claves.setdefault(str(fila["form_id"]), []).append(str(fila["clause_key"]))
    return {formulario: tuple(lista) for formulario, lista in claves.items()}


# --- El panel de documentos (fase 2, 2026-10-08) -----------------------------

_LISTAR_FORMULARIOS = """
    SELECT f.form_id, f.form_version, f.form_kind, f.language, f.issuer_label,
           COUNT(c.clause_id) AS clause_count
    FROM policy_forms f
    LEFT JOIN clauses c
      ON c.tenant_id = f.tenant_id AND c.form_id = f.form_id
     AND c.form_version = f.form_version
    WHERE f.tenant_id = :tenant_id
    GROUP BY f.form_id, f.form_version, f.form_kind, f.language, f.issuer_label
    ORDER BY f.form_kind, f.form_id, f.form_version
"""

_CLAUSULAS_DEL_FORMULARIO = """
    SELECT tenant_id, clause_id, clause_key, form_id, form_version, part, language, text,
           is_distractor, issuer_label
    FROM clauses
    WHERE tenant_id = :tenant_id AND form_id = :form_id
    ORDER BY form_version, clause_id
"""

_MODIFICACIONES_HACIA = """
    SELECT r.to_clause, c.form_id
    FROM clause_relations r
    JOIN clauses c ON c.tenant_id = r.tenant_id AND c.clause_id = r.from_clause
    WHERE r.tenant_id = :tenant_id AND r.relation = 'endorsement_modifies'
      AND r.to_clause = ANY(:clause_ids)
"""


async def list_forms(tenant_id: TenantId) -> tuple[dict[str, object], ...]:
    """Los formularios de la aseguradora, con cuantas clausulas trae cada uno."""
    async with tenancy.session_for(tenant_id) as sesion:
        filas = await tenancy.fetch_all(sesion, _LISTAR_FORMULARIOS, tenant_id=tenant_id)
    return tuple(dict(fila) for fila in filas)


async def clauses_of_form(tenant_id: TenantId, *, form_id: str) -> tuple[Clause, ...]:
    """Las clausulas de un formulario, en su orden."""
    async with tenancy.session_for(tenant_id) as sesion:
        filas = await tenancy.fetch_all(
            sesion, _CLAUSULAS_DEL_FORMULARIO, tenant_id=tenant_id, form_id=form_id
        )
    return tuple(Clause.model_validate(dict(fila)) for fila in filas)


async def amending_forms(
    tenant_id: TenantId, *, clause_ids: Sequence[str]
) -> dict[str, tuple[str, ...]]:
    """Que endosos modifican cada clausula: el formulario del que sale la modificacion."""
    if not clause_ids:
        return {}
    async with tenancy.session_for(tenant_id) as sesion:
        filas = await tenancy.fetch_all(
            sesion, _MODIFICACIONES_HACIA, tenant_id=tenant_id, clause_ids=list(clause_ids)
        )
    endosos: dict[str, list[str]] = {}
    for fila in filas:
        endosos.setdefault(str(fila["to_clause"]), []).append(str(fila["form_id"]))
    return {clausula: tuple(sorted(lista)) for clausula, lista in endosos.items()}


# --- Identificacion por cedula del titular (U11, enmienda de C-18, BR1.2) -----
#
# La otra mitad de la identificacion que el contrato ya prometia ("por numero o
# por cedula del titular", `functional-spec.md` de U11, "Fronteras con lo ya
# construido"): `find_policy` solo buscaba por numero porque ninguna unidad
# anterior necesitaba la otra via. `named_insured` es JSON -- lo declara
# `IssuedPolicy.named_insured: dict[str, Any]` -- y el generador sintetico
# (`synthetic_data.people`) siempre lo llena con la clave `national_id`
# (`PersonaRef.national_id`), asi que la consulta filtra sobre esa clave sin
# necesitar una columna nueva ni una migracion (FD-U11-5).
#
# Cuando la cedula coincide con mas de una poliza -- dos vigencias de la misma
# persona en la misma aseguradora, por ejemplo --, se devuelve la de menor
# numero para que dos corridas del mismo commit vean la misma (BR7.3): elegir
# "la mas reciente" exigiria comparar vigencias que todavia no importan a
# quien llama, y la demostracion no siembra ese caso.
_LEER_POLIZA_POR_CEDULA = """
    SELECT tenant_id, policy_number, issuer_tenant, form_id, form_version, endorsement_ids,
           named_insured, drivers, vehicles, limits_and_deductibles, period_start, period_end
    FROM issued_policies
    WHERE tenant_id = :tenant_id AND named_insured ->> 'national_id' = :national_id
    ORDER BY policy_number
    LIMIT 1
"""


async def find_policy_by_national_id(
    tenant_id: TenantId, *, national_id: str
) -> IssuedPolicy | None:
    """La poliza del titular por su cedula, o nada -- la otra via de identificacion (BR1.2).

    Misma garantia que `find_policy`: la politica de fila ya filtro cualquier
    poliza de otra aseguradora antes de que esta consulta la viera, asi que una
    cedula sin poliza en esta aseguradora y una cedula cuya poliza es de otra
    devuelven **lo mismo**, sin ninguna rama que las distinga.
    """
    async with tenancy.session_for(tenant_id) as sesion:
        fila = await tenancy.fetch_one(
            sesion, _LEER_POLIZA_POR_CEDULA, tenant_id=tenant_id, national_id=national_id
        )
    return IssuedPolicy.model_validate(dict(fila)) if fila is not None else None


_LEER_CLAUSULA_POR_ID = """
    SELECT tenant_id, clause_id, clause_key, form_id, form_version, part, language, text,
           is_distractor, issuer_label
    FROM clauses
    WHERE tenant_id = :tenant_id AND clause_id = ANY(:clause_ids)
"""


async def clauses_by_ids(tenant_id: TenantId, *, clause_ids: Sequence[str]) -> tuple[Clause, ...]:
    """Las clausulas pedidas por identificador, en cualquier orden.

    Quien llama reordena: `ANY(:clause_ids)` no promete conservar el orden de
    la lista, y el orden que importa aqui es el que dejo la fusion (BR2.3).
    """
    if not clause_ids:
        return ()
    async with tenancy.session_for(tenant_id) as sesion:
        filas = await tenancy.fetch_all(
            sesion, _LEER_CLAUSULA_POR_ID, tenant_id=tenant_id, clause_ids=list(clause_ids)
        )
    return tuple(Clause.model_validate(dict(fila)) for fila in filas)


_LEER_CANDIDATAS = """
    SELECT tenant_id, clause_id, clause_key, form_id, form_version, part, language, text,
           is_distractor, issuer_label
    FROM clauses
    WHERE tenant_id = :tenant_id
      AND (
        (form_id = :form_id AND form_version = :form_version)
        OR form_id = ANY(:endorsement_ids)
      )
"""


async def candidate_clauses(
    tenant_id: TenantId,
    *,
    form_id: str,
    form_version: str,
    endorsement_ids: Sequence[str],
) -> tuple[Clause, ...]:
    """El universo de clausulas que esta poliza puede citar, sin puntuar todavia (BR2.1).

    El formulario base de la version que la poliza referencia, mas sus
    endosos vigentes -- y nada de otra aseguradora, de otra poliza ni de una
    version que esta poliza no referencia. Este conjunto se calcula **antes**
    de la busqueda lexica y de la vectorial, que es justo lo que BR2.1 exige:
    filtrar antes de puntuar, no despues.
    """
    async with tenancy.session_for(tenant_id) as sesion:
        filas = await tenancy.fetch_all(
            sesion,
            _LEER_CANDIDATAS,
            tenant_id=tenant_id,
            form_id=form_id,
            form_version=form_version,
            endorsement_ids=list(endorsement_ids),
        )
    return tuple(Clause.model_validate(dict(fila)) for fila in filas)


_BUSCAR_LEXICO = """
    SELECT clause_id
    FROM clause_index
    WHERE tenant_id = :tenant_id
      AND embedding_model = :embedding_model
      AND clause_id = ANY(:candidate_ids)
      AND lexical_vector @@ plainto_tsquery(CAST(:tsvector_config AS regconfig), :query_text)
    ORDER BY ts_rank_cd(
                 lexical_vector, plainto_tsquery(CAST(:tsvector_config AS regconfig), :query_text)
             ) DESC,
             clause_id
    LIMIT :limit
"""


async def lexical_rank(  # noqa: PLR0913 -- seis datos de una busqueda, ninguno derivable de otro
    tenant_id: TenantId,
    *,
    embedding_model: str,
    candidate_ids: Sequence[str],
    query_text: str,
    query_language: str,
    limit: int,
) -> tuple[str, ...]:
    """Los identificadores del conjunto candidato que casan por texto, en orden (BR2.3).

    La configuracion del analizador es la del **idioma de la cláusula**
    (`query_language`, que aqui es el idioma del corpus candidato, no el de la
    conversacion) por la misma razon que la ingesta la fija asi (TECH-U8.4): el
    lematizador tiene que ser el del texto que se busca, o degrada justo la
    busqueda que deberia ayudar.
    """
    if not candidate_ids:
        return ()
    configuracion = _TSVECTOR_CONFIG.get(query_language)
    if configuracion is None:
        msg = f"idioma sin configuracion de tsvector: '{query_language}'"
        raise ValueError(msg)
    async with tenancy.session_for(tenant_id) as sesion:
        filas = await tenancy.fetch_all(
            sesion,
            _BUSCAR_LEXICO,
            tenant_id=tenant_id,
            embedding_model=embedding_model,
            candidate_ids=list(candidate_ids),
            tsvector_config=configuracion,
            query_text=query_text,
            limit=limit,
        )
    return tuple(str(fila["clause_id"]) for fila in filas)


_BUSCAR_VECTORIAL = """
    SELECT clause_id
    FROM clause_index
    WHERE tenant_id = :tenant_id
      AND embedding_model = :embedding_model
      AND clause_id = ANY(:candidate_ids)
    ORDER BY embedding <=> CAST(:query_vector AS vector)
    LIMIT :limit
"""


async def vector_rank(
    tenant_id: TenantId,
    *,
    embedding_model: str,
    candidate_ids: Sequence[str],
    query_vector: Vector,
    limit: int,
) -> tuple[str, ...]:
    """Los identificadores del conjunto candidato mas cercanos por embedding, en orden (BR2.3).

    Exacta: sin indice HNSW ni IVFFlat, ordenando por distancia sobre las
    filas ya filtradas por `candidate_ids` (FD-U8-6, TECH-U8.2). Con 104
    clausulas por corpus el barrido es barato, y un indice aproximado no
    compraria nada medible.
    """
    if not candidate_ids:
        return ()
    async with tenancy.session_for(tenant_id) as sesion:
        filas = await tenancy.fetch_all(
            sesion,
            _BUSCAR_VECTORIAL,
            tenant_id=tenant_id,
            embedding_model=embedding_model,
            candidate_ids=list(candidate_ids),
            query_vector=_vector_literal(query_vector),
            limit=limit,
        )
    return tuple(str(fila["clause_id"]) for fila in filas)


_LEER_RELACIONES_HACIA = """
    SELECT tenant_id, from_clause, to_clause, relation
    FROM clause_relations
    WHERE tenant_id = :tenant_id AND to_clause = ANY(:clause_ids)
"""


async def relations_into(
    tenant_id: TenantId, *, clause_ids: Sequence[str]
) -> tuple[ClauseRelation, ...]:
    """Las relaciones que apuntan a alguna de las clausulas dadas (BR2.4, BR3.5).

    `to_clause` es el lado que importa para el cierre: un endoso vigente
    "modifica hacia" la clausula base, y una definicion "define hacia" la
    clausula que la usa (ver los datos reales de `clause_relations.json`, que
    es lo que fijo esta direccion y no el boceto de `domain-design`).
    """
    if not clause_ids:
        return ()
    async with tenancy.session_for(tenant_id) as sesion:
        filas = await tenancy.fetch_all(
            sesion, _LEER_RELACIONES_HACIA, tenant_id=tenant_id, clause_ids=list(clause_ids)
        )
    return tuple(ClauseRelation.model_validate(dict(fila)) for fila in filas)
