"""Por donde va una pregunta rigida por la poliza, y como sale su respuesta (plan 09, punto 6).

Pura: sin base y sin modelo. El puerto es un doble que cuenta las llamadas; la guardia de salida es
la de verdad, con los patrones versionados.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest

from untangle.base import Locale, RigidTopic
from untangle.case_record import fields
from untangle.case_record.models import CaseState, Completeness, RecordType
from untangle.compliance.controls import patterns
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration import contracts, rigid_route, turn
from untangle.orchestration.model_reply import FallbackReason
from untangle.orchestration.nodes.intake import suggestions as sugerencias
from untangle.orchestration.nodes.intake.understanding import (
    Answer,
    UnderstandingResponse,
    UnderstoodItem,
    Want,
    canonical_reading,
)
from untangle.orchestration.output import ExitGate
from untangle.orchestration.rigid_route import RigidAnswerView
from untangle.tenancy import config as tenancy_config

HOY = date(2026, 11, 2)


@pytest.fixture(autouse=True)
def _catalogo_y_aseguradoras() -> Iterator[None]:
    copy_api.install(copy_api.load())
    tenancy_config.install(tenancy_config.load())
    patterns.reset()
    yield
    copy_api.reset()
    tenancy_config.reset()
    patterns.reset()


def _lectura(**cambios: Any) -> UnderstandingResponse:
    datos: dict[str, Any] = {"wants": Want.POLICY_QUESTION, "rigid_topic": RigidTopic.DEDUCTIBLE}
    datos.update(cambios)
    return UnderstandingResponse.model_validate(datos)


def _tema(
    lectura: UnderstandingResponse | None, tipo: RecordType, *, poliza: bool = True
) -> RigidTopic | None:
    return rigid_route.topic_for(lectura, record_type=tipo, policy_identified=poliza)


# --- La eleccion del camino ---------------------------------------------------


@pytest.mark.parametrize("tipo", [RecordType.COVERAGE_INQUIRY, RecordType.CLAIM])
def test_un_tema_rigido_con_la_poliza_identificada_sale_del_registro(tipo: RecordType) -> None:
    assert _tema(_lectura(), tipo) is RigidTopic.DEDUCTIBLE


def test_el_tema_none_nunca_sale_del_registro() -> None:
    assert _tema(_lectura(rigid_topic=RigidTopic.NONE), RecordType.COVERAGE_INQUIRY) is None


def test_sin_lectura_del_modelo_el_turno_sigue_su_camino() -> None:
    assert _tema(None, RecordType.COVERAGE_INQUIRY) is None


def test_sin_la_poliza_identificada_no_se_contesta() -> None:
    assert _tema(_lectura(), RecordType.COVERAGE_INQUIRY, poliza=False) is None


def test_una_solicitud_de_cotizacion_no_tiene_poliza_de_la_que_leer() -> None:
    assert _tema(_lectura(), RecordType.QUOTE_REQUEST) is None


@pytest.mark.parametrize(
    "intencion",
    [Want.OFF_TOPIC, Want.TALK_TO_PERSON, Want.QUOTE, Want.GREETING, Want.REPORT_ACCIDENT],
)
def test_con_otra_intencion_el_tema_no_manda(intencion: Want) -> None:
    assert _tema(_lectura(wants=intencion), RecordType.COVERAGE_INQUIRY) is None


@pytest.mark.parametrize("intencion", [Want.CONTINUE, Want.GENERAL_QUESTION, Want.OTHER])
def test_las_intenciones_que_preguntan_si_dejan_pasar_el_tema(intencion: Want) -> None:
    assert _tema(_lectura(wants=intencion), RecordType.COVERAGE_INQUIRY) is RigidTopic.DEDUCTIBLE


def test_en_un_reporte_los_datos_por_anotar_van_primero() -> None:
    con_datos = _lectura(items=(UnderstoodItem(field_key="description", value="me chocaron"),))

    assert _tema(con_datos, RecordType.CLAIM) is None
    # En una consulta los datos no compiten con la respuesta.
    assert _tema(con_datos, RecordType.COVERAGE_INQUIRY) is RigidTopic.DEDUCTIBLE


def test_un_mensaje_que_contesta_si_o_no_no_es_la_pregunta() -> None:
    assert _tema(_lectura(answer=Answer.YES), RecordType.COVERAGE_INQUIRY) is None


def test_un_tema_rigido_convierte_la_duda_general_en_pregunta_por_la_poliza() -> None:
    """Sin esto el primer mensaje no abriria la consulta cuando el modelo lo llama duda general."""
    lectura = canonical_reading(_lectura(wants=Want.GENERAL_QUESTION), None)

    assert lectura.wants is Want.POLICY_QUESTION
    # Una duda general sin tema rigido no se toca.
    sin_tema = canonical_reading(
        UnderstandingResponse(wants=Want.GENERAL_QUESTION, rigid_topic=RigidTopic.NONE), None
    )
    assert sin_tema.wants is Want.GENERAL_QUESTION


# --- La llamada al puerto -----------------------------------------------------


class _Puerto:
    def __init__(self, respuesta: RigidAnswerView | None) -> None:
        self.respuesta = respuesta
        self.llamadas: list[tuple[str, str, RigidTopic, Locale, date, bool]] = []

    async def answer(  # noqa: PLR0913 -- la firma del puerto
        self,
        tenant_id: str,
        policy_number: str,
        topic: RigidTopic,
        *,
        language: Locale,
        on: date,
        spoken: bool,
    ) -> RigidAnswerView | None:
        self.llamadas.append((tenant_id, policy_number, topic, language, on, spoken))
        return self.respuesta


def _vista(
    texto: str,
    tema: RigidTopic = RigidTopic.VEHICLES,
    clave: str = "chat.rigid.vehicles.listed",
) -> RigidAnswerView:
    return RigidAnswerView(topic=tema, copy_key=CopyKey(clave), text=texto)


async def test_el_puerto_recibe_el_tenant_la_poliza_el_tema_y_el_canal() -> None:
    puerto = _Puerto(_vista("texto"))

    respuesta = await rigid_route.answer(
        puerto,
        tenant_id="stonecroft",
        policy_number="POL-11",
        topic=RigidTopic.VEHICLES,
        language="es",
        on=HOY,
        spoken=True,
    )

    assert respuesta is not None
    assert puerto.llamadas == [("stonecroft", "POL-11", RigidTopic.VEHICLES, "es", HOY, True)]


async def test_sin_puerto_enchufado_el_turno_sigue_su_camino() -> None:
    respuesta = await rigid_route.answer(
        None,
        tenant_id="stonecroft",
        policy_number="POL-11",
        topic=RigidTopic.VEHICLES,
        language="es",
        on=HOY,
        spoken=False,
    )

    assert respuesta is None


async def test_si_la_poliza_no_existe_para_la_aseguradora_el_turno_sigue_su_camino() -> None:
    respuesta = await rigid_route.answer(
        _Puerto(None),
        tenant_id="stonecroft",
        policy_number="POL-00",
        topic=RigidTopic.VEHICLES,
        language="en",
        on=HOY,
        spoken=False,
    )

    assert respuesta is None


# --- La respuesta que sale, con la guardia de verdad ---------------------------


def _mensaje(idioma: Locale, canal: str = "chat") -> contracts.InboundTurn:
    tenant = sorted(c.tenant_id for c in tenancy_config.loaded().available)[0]
    return contracts.InboundTurn(
        tenant_id=tenant,
        session_ref="s",
        case_id="c",
        text="¿Cuál es mi deducible?",
        language=idioma,
        channel=canal,  # type: ignore[arg-type]
        received_at=datetime(2026, 11, 2, 12, 0, tzinfo=UTC),
    )


def _contexto(tipo: RecordType, idioma: Locale) -> Any:
    claves = [d.key for d in fields.definitions_for(RecordType.CLAIM)]
    return SimpleNamespace(
        record_type=tipo,
        state=CaseState.CAPTURING,
        language=idioma,
        case_id="c",
        completeness=Completeness(
            per_field={c: c == "identity_and_policy" for c in claves},
            complete=1,
            total=len(claves),
        ),
    )


def _previo(texto: str) -> Any:
    return SimpleNamespace(node_writes={"intake_response_text": texto})


async def _responder(  # noqa: PLR0913 -- el texto, el caso y la plantilla de la que salio
    texto: str,
    tipo: RecordType,
    idioma: Locale,
    *,
    pendiente: str = "",
    tema: RigidTopic = RigidTopic.VEHICLES,
    clave: str = "chat.rigid.vehicles.listed",
) -> contracts.FinalText:
    mensaje = _mensaje(idioma)
    return await turn._responder_desde_el_registro(
        mensaje,
        cast(Any, _contexto(tipo, idioma)),
        cast(Any, _previo(pendiente)),
        _vista(texto, tema, clave),
        turn_id="t1",
        gate=ExitGate(tenant_id=mensaje.tenant_id, language=idioma),
    )


async def test_en_una_consulta_la_respuesta_sale_tal_cual_y_ofrece_preguntas_de_ejemplo() -> None:
    texto = "Los vehículos que figuran en tu póliza POL-11 son: Kia Picanto 2013."

    evento = await _responder(texto, RecordType.COVERAGE_INQUIRY, "es")

    assert evento.text == texto
    assert evento.from_catalog is True
    assert evento.case_id == "c"
    assert evento.message_id == "t1"
    assert evento.suggestions == sugerencias.after_coverage(language="es")


async def test_en_un_reporte_se_retoma_la_pregunta_pendiente_detras_de_la_respuesta() -> None:
    texto = "Los vehículos que figuran en tu póliza POL-11 son: Kia Picanto 2013."

    evento = await _responder(
        texto, RecordType.CLAIM, "es", pendiente="¿Cuándo y dónde ocurrió el accidente?"
    )

    assert evento.text == f"{texto} ¿Cuándo y dónde ocurrió el accidente?"
    assert evento.suggestions == ()


async def test_el_deducible_sale_con_su_cifra_porque_el_turno_entrega_la_clave_de_su_plantilla() -> (
    None
):
    """Decision de Miguel, 2026-11-02: el deducible y los limites son cifras del registro."""
    texto = "Según tu póliza POL-11, el deducible de pérdida parcial es $\xa0250.000 por hurto."

    evento = await _responder(
        texto,
        RecordType.CLAIM,
        "es",
        pendiente="¿Cuándo y dónde ocurrió el accidente?",
        tema=RigidTopic.DEDUCTIBLE,
        clave="chat.rigid.deductible",
    )

    assert evento.text == f"{texto} ¿Cuándo y dónde ocurrió el accidente?"


async def test_la_guardia_interviene_un_monto_sin_llevarse_la_pregunta_pendiente() -> None:
    """Un monto de una plantilla que no es del deducible ni de los limites sigue siendo una
    categoria de la guardia: la respuesta se sustituye, la pregunta que la persona tiene que
    contestar no se pierde (se gatea por su cuenta)."""
    texto = "Según tu póliza POL-11, el deducible del vehículo es $\xa0250.000 en un choque."

    evento = await _responder(
        texto, RecordType.CLAIM, "es", pendiente="¿Cuándo y dónde ocurrió el accidente?"
    )

    assert "250.000" not in evento.text
    assert evento.text.endswith("¿Cuándo y dónde ocurrió el accidente?")
    assert len(evento.text) > len("¿Cuándo y dónde ocurrió el accidente?")


def test_el_motivo_de_la_traza_existe_y_es_el_de_los_datos_rigidos() -> None:
    assert FallbackReason.RIGID_FACTS.value == "rigid_facts"


# --- La forma de lo que se le pide al modelo ----------------------------------


def test_el_campo_es_una_lista_cerrada_y_por_omision_no_es_un_tema_rigido() -> None:
    assert UnderstandingResponse(wants=Want.GREETING).rigid_topic is RigidTopic.NONE
    with pytest.raises(ValueError, match="rigid_topic"):
        UnderstandingResponse.model_validate({"wants": "policy_question", "rigid_topic": "premium"})


def test_el_esquema_que_ve_el_proveedor_lista_exactamente_los_temas() -> None:
    esquema = UnderstandingResponse.model_json_schema()
    definicion = esquema["$defs"]["RigidTopic"]

    assert set(definicion["enum"]) == {t.value for t in RigidTopic}


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_la_instruccion_de_la_conversacion_nombra_cada_tema(idioma: str) -> None:
    from untangle import paths

    instruccion = (paths.prompts_dir() / f"conversation.{idioma}.md").read_text(encoding="utf-8")

    assert "`rigid_topic`" in instruccion
    for tema in RigidTopic:
        assert f"`{tema.value}`" in instruccion, f"la instruccion {idioma} no nombra '{tema.value}'"
