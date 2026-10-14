"""La parte de la siembra que no necesita base: caminos, identificadores y arranque (BR6.3).

Lo que toca la base se prueba en `tests/integration/u7/`. Aqui, lo que tiene que
ser cierto antes: que el camino de cada caso sembrado use **solo** transiciones de
la tabla de U4 --si no, la API lo rechazaria a mitad de la siembra--, que el
identificador de un caso sea el mismo en cada siembra, y que el comando se niegue
nombrando lo que falta en vez de sembrar a medias.
"""

from __future__ import annotations

import itertools

import pytest

from untangle import paths
from untangle.case_record import crypto, schema_loading
from untangle.case_record.models import ActorType, AttachmentKind, CaseState
from untangle.server import synthetic_seed
from untangle.synthetic_data.cases import load_seeded_cases
from untangle.synthetic_data.models import SeededCaseRecord
from untangle.tenancy import api as tenancy
from untangle.tenancy.models import Action, TenantKind

CASOS = load_seeded_cases(paths.data_dir())
TABLA = {(fila.from_state, fila.to_state) for fila in schema_loading.transitions()}


@pytest.mark.parametrize("caso", CASOS, ids=lambda c: c.case_key)
def test_el_camino_de_cada_caso_usa_solo_transiciones_de_la_tabla_de_u4(
    caso: SeededCaseRecord,
) -> None:
    camino = synthetic_seed.path_to(caso)
    estados = (CaseState.OPEN, *camino)
    if caso.resolution is not None:
        estados = (*estados, CaseState.CLOSED)

    fuera = [(a, b) for a, b in itertools.pairwise(estados) if (a, b) not in TABLA]

    assert fuera == []
    assert estados[-1].value == caso.state.value


def test_hay_casos_en_los_siete_estados() -> None:
    """Sin esto, la prueba de arriba podria recorrer menos caminos de los que existen."""
    assert {c.state.value for c in CASOS} == {estado.value for estado in CaseState}


def test_derivar_por_una_regla_pasa_por_decidir_y_por_una_persona_no() -> None:
    """T7 sale de `deciding`; T3, de la captura (tabla de U4)."""
    por_regla = next(c for c in CASOS if c.state.value == "awaiting_insured")
    por_persona = next(
        c for c in CASOS if c.derivation_reason and c.derivation_reason.value == "person_requested"
    )

    assert CaseState.DECIDING in synthetic_seed.path_to(por_regla)
    assert CaseState.DECIDING not in synthetic_seed.path_to(por_persona)


def test_el_identificador_de_un_caso_es_el_mismo_en_cada_siembra() -> None:
    claves = [c.case_key for c in CASOS]
    identificadores = [synthetic_seed.seeded_case_id(clave) for clave in claves]

    assert identificadores == [synthetic_seed.seeded_case_id(clave) for clave in claves]
    assert len(set(identificadores)) == len(claves)
    assert all(i.startswith("seed-") for i in identificadores)


def test_la_evidencia_de_cierre_permite_cerrar_y_apunta_al_caso() -> None:
    """Ningun adjunto sin evaluar, y la transcripcion se recupera por su clave."""
    evidencia = synthetic_seed.closing_evidence_for("SEED/sunmeadow/en/closed")

    assert evidencia.complete
    assert evidencia.transcript.kind is AttachmentKind.PRESENT
    assert evidencia.transcript.reference == "SEED/sunmeadow/en/closed"


def test_la_evidencia_de_cierre_de_un_caso_que_paso_por_las_reglas_las_lleva_presentes() -> None:
    """Con evaluacion guardada, el cierre ya no dice que las reglas no se miraron."""
    clave = "SEED/sunmeadow/en/closed"
    con_reglas = synthetic_seed.closing_evidence_for(clave, with_rules=True)
    sin_reglas = synthetic_seed.closing_evidence_for(clave)

    assert con_reglas.complete
    assert con_reglas.fired_rules.kind is AttachmentKind.PRESENT
    assert con_reglas.fired_rules.reference == clave
    assert sin_reglas.complete
    assert sin_reglas.fired_rules.kind is AttachmentKind.EMPTY


def test_evaluan_las_reglas_solo_los_que_salieron_de_la_decision() -> None:
    """Cerrados por las reglas o por una persona tras una regla, y derivados por una regla.

    No evaluan: el que sigue en captura, en verificacion o en `deciding`, y el que una persona
    pidio derivar sin que las reglas lo miraran. Se escribe por estado y motivo, que es como lo
    describe el archivo del caso, y no repitiendo el calculo de `evaluates_rules`.
    """
    for caso in CASOS:
        estado = caso.state.value
        motivo = caso.derivation_reason.value if caso.derivation_reason else None
        salio_de_decidir = (estado == "closed" and motivo in (None, "rule")) or (
            estado in ("derived", "awaiting_insured") and motivo == "rule"
        )

        assert synthetic_seed.evaluates_rules(caso) is salio_de_decidir, caso.case_key


def test_los_que_evaluan_y_los_que_no_son_los_dos_conjuntos_no_vacios() -> None:
    """Sin esto, la prueba de arriba pasaria igual si ninguno evaluara o todos lo hicieran."""
    evaluan = [c for c in CASOS if synthetic_seed.evaluates_rules(c)]

    assert evaluan
    assert len(evaluan) < len(CASOS)
    assert {c.tenant_id for c in evaluan} == {c.tenant_id for c in CASOS}


def test_sin_base_el_comando_se_niega_nombrando_la_variable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("UNTANGLE_DATABASE_URL", raising=False)

    assert synthetic_seed.main([]) == 1
    assert "UNTANGLE_DATABASE_URL" in capsys.readouterr().err


def test_sin_clave_de_cifrado_el_comando_se_niega_nombrandola(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("UNTANGLE_DATABASE_URL", "postgresql+psycopg://nadie@127.0.0.1:1/nada")
    monkeypatch.delenv(crypto.KEY_ENV_VAR, raising=False)

    assert synthetic_seed.main([]) == 1
    assert crypto.KEY_ENV_VAR in capsys.readouterr().err


# --- Quien cierra el caso sembrado ------------------------------------------------

#: El permiso que en vivo pide cada resolucion que pone el personal, escrito aqui a mano a
#: proposito: es la lectura independiente de `inbox.actions` y de la tabla de permisos contra la
#: que se compara lo que elige la siembra.
PERMISO_DE_LA_RESOLUCION = {
    "approved": Action.DECIDE_CASE,
    "rejected": Action.DECIDE_CASE,
    "sent_to_insurer": Action.MARK_SENT,
}
CERRADOS = [c for c in CASOS if c.state.value == "closed"]


def test_hay_cerrados_de_las_dos_clases_y_de_las_tres_resoluciones_del_personal() -> None:
    """Sin esto, las pruebas de abajo pasarian igual si ningun ejemplo se cerrara de una forma."""
    resoluciones = {c.resolution.value for c in CERRADOS if c.resolution is not None}

    assert resoluciones == {"registered", *PERMISO_DE_LA_RESOLUCION}


@pytest.mark.parametrize("caso", CERRADOS, ids=lambda c: c.case_key)
def test_lo_que_en_vivo_cierra_el_personal_lo_cierra_una_persona_de_su_aseguradora(
    caso: SeededCaseRecord,
) -> None:
    """Aprobado, rechazado y enviado a la aseguradora: autor `staff`, de la configuracion, con el
    permiso de esa decision. El cierre directo (`registered`) sigue siendo del sistema."""
    assert caso.resolution is not None
    autor = synthetic_seed.closing_actor_for(caso)

    if caso.resolution.value == "registered":
        assert autor == synthetic_seed.SEED_ACTOR
        return
    assert autor.actor_type is ActorType.STAFF
    persona = tenancy.require(caso.tenant_id).principal(autor.actor_id or "")
    assert persona is not None, f"{caso.case_key}: {autor.actor_id} no esta en su configuracion"
    assert tenancy.is_permitted(persona.role, PERMISO_DE_LA_RESOLUCION[caso.resolution.value])


@pytest.mark.parametrize(
    "caso", [c for c in CASOS if c.state.value != "closed"], ids=lambda c: c.case_key
)
def test_un_caso_que_no_se_cierra_no_tiene_otro_autor_que_el_sistema(
    caso: SeededCaseRecord,
) -> None:
    assert synthetic_seed.closing_actor_for(caso) == synthetic_seed.SEED_ACTOR


def test_una_agencia_con_un_aprobado_en_su_archivo_no_se_siembra() -> None:
    """Una agencia no aprueba: ese cierre no existiria en vivo, y la siembra lo dice en vez de
    inventarle un autor."""
    agencia = next(t for t in tenancy.loaded().available if t.kind is TenantKind.AGENCY)
    aprobado = next(c for c in CERRADOS if c.resolution and c.resolution.value == "approved")
    incoherente = aprobado.model_copy(update={"tenant_id": agencia.tenant_id})

    with pytest.raises(synthetic_seed.SeedError, match=aprobado.case_key):
        synthetic_seed.closing_actor_for(incoherente)


def test_sin_nadie_con_el_permiso_en_la_configuracion_no_se_siembra_el_cierre(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una aseguradora sin personal que pueda decidir no puede tener un cerrado aprobado: la
    siembra se detiene nombrando el caso, no lo cierra con el sistema."""
    aprobado = next(c for c in CERRADOS if c.resolution and c.resolution.value == "approved")
    sin_personal = tenancy.require(aprobado.tenant_id).model_copy(update={"staff": ()})
    monkeypatch.setattr(tenancy, "require", lambda _id: sin_personal)

    with pytest.raises(synthetic_seed.SeedError, match=aprobado.case_key):
        synthetic_seed.closing_actor_for(aprobado)
