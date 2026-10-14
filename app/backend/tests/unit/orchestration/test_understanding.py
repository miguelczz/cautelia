"""La comprension de un mensaje: el respaldo cuando el modelo falla y el caso que abre.

Sin red y sin modelo: el puerto es un doble. Lo que se prueba es lo que el modulo
promete al turno --que nunca levanta y que deja su evento-- y la tabla cerrada que
dice que caso abre cada intencion.
"""

from __future__ import annotations

import asyncio
import io
import sys
from collections.abc import Iterator
from dataclasses import replace
from datetime import date

import pytest

from untangle import observability
from untangle.base import ProviderErrorKind, ProviderName, Use
from untangle.case_record.models import RecordType
from untangle.orchestration.nodes.intake import understanding
from untangle.orchestration.nodes.intake.understanding import (
    Answer,
    UnderstandingRequest,
    UnderstandingResponse,
    Want,
)
from untangle.providers.ports import BudgetExhausted, ExhaustedResource, ProviderError

PETICION = UnderstandingRequest(
    tenant_id="sunmeadow",
    language="es",
    today=date(2026, 10, 7),
    record_type=None,
    quote_enabled=True,
    noted=(),
    missing=(),
    person_text="Dame una cotización",
)


@pytest.fixture
def eventos() -> Iterator[io.StringIO]:
    destino = io.StringIO()
    observability.set_stream(destino)
    yield destino
    observability.set_stream(sys.stdout)


async def test_devuelve_lo_que_entendio_y_deja_su_evento(eventos: io.StringIO) -> None:
    async def entender(_p: UnderstandingRequest) -> UnderstandingResponse:
        return UnderstandingResponse(wants=Want.QUOTE)

    respuesta = await understanding.understand(entender, PETICION)

    assert respuesta == UnderstandingResponse(wants=Want.QUOTE)
    assert '"event": "chat.understood"' in eventos.getvalue()


async def test_sin_modelo_no_entiende_y_no_llama_a_nadie() -> None:
    assert await understanding.understand(None, PETICION) is None


@pytest.mark.parametrize(
    "error",
    [
        ProviderError(
            ProviderErrorKind.UNAVAILABLE, provider=ProviderName.ANTHROPIC, use=Use.CHAT_REPLY
        ),
        BudgetExhausted(
            ExhaustedResource.PROVIDER_QUOTA, provider=ProviderName.ANTHROPIC, use=Use.CHAT_REPLY
        ),
    ],
)
async def test_si_el_modelo_falla_el_turno_sigue_por_reglas(
    error: Exception, eventos: io.StringIO
) -> None:
    async def entender(_p: UnderstandingRequest) -> UnderstandingResponse:
        raise error

    assert await understanding.understand(entender, PETICION) is None
    assert '"event": "chat.understanding_fallback"' in eventos.getvalue()


@pytest.mark.parametrize(
    ("canal", "plazo"),
    [("chat", "UNDERSTANDING_TIMEOUT_CHAT_S"), ("voice", "UNDERSTANDING_TIMEOUT_VOICE_S")],
)
async def test_si_el_modelo_tarda_de_mas_el_turno_sigue_por_reglas(
    monkeypatch: pytest.MonkeyPatch, canal: str, plazo: str, eventos: io.StringIO
) -> None:
    """Cada canal espera lo suyo: se achica el plazo de ese canal y el otro no cuenta."""
    monkeypatch.setattr(understanding, plazo, 0.01)

    async def entender(_p: UnderstandingRequest) -> UnderstandingResponse:
        await asyncio.sleep(1)
        return UnderstandingResponse(wants=Want.QUOTE)

    peticion = replace(PETICION, channel=canal)  # type: ignore[arg-type]
    assert await understanding.understand(entender, peticion) is None
    assert '"cause": "timeout"' in eventos.getvalue()


def test_la_llamada_espera_menos_que_el_chat_porque_alguien_escucha_al_telefono() -> None:
    """El chat tambien redacta la respuesta (2026-10-12) y espera 6,5 s; la voz sigue en 3,5 s."""
    assert understanding.understanding_timeout_s("chat") == 6.5
    assert understanding.understanding_timeout_s("voice") == 3.5
    assert understanding.understanding_timeout_s("voice") < understanding.understanding_timeout_s(
        "chat"
    )


async def test_el_plazo_del_chat_deja_pasar_una_respuesta_mas_lenta_que_la_de_la_voz(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(understanding, "UNDERSTANDING_TIMEOUT_CHAT_S", 0.5)
    monkeypatch.setattr(understanding, "UNDERSTANDING_TIMEOUT_VOICE_S", 0.01)

    async def entender(_p: UnderstandingRequest) -> UnderstandingResponse:
        await asyncio.sleep(0.1)
        return UnderstandingResponse(wants=Want.QUOTE)

    assert await understanding.understand(entender, PETICION) is not None
    assert await understanding.understand(entender, replace(PETICION, channel="voice")) is None


@pytest.mark.parametrize(
    ("respuesta", "cotiza", "esperado"),
    [
        (UnderstandingResponse(wants=Want.QUOTE), True, RecordType.QUOTE_REQUEST),
        # Donde no se cotiza no se abre nada: se contesta y se ofrece lo que hay.
        (UnderstandingResponse(wants=Want.QUOTE), False, None),
        (UnderstandingResponse(wants=Want.POLICY_QUESTION), True, RecordType.COVERAGE_INQUIRY),
        (UnderstandingResponse(wants=Want.REPORT_ACCIDENT), True, RecordType.CLAIM),
        (UnderstandingResponse(wants=Want.TALK_TO_PERSON), True, RecordType.CLAIM),
        # C1: una duda general, un saludo o algo que no es ninguna opcion no es un
        # accidente.
        (UnderstandingResponse(wants=Want.GENERAL_QUESTION), True, None),
        (UnderstandingResponse(wants=Want.GREETING), True, None),
        (UnderstandingResponse(wants=Want.OTHER), True, None),
    ],
)
def test_que_caso_abre_cada_intencion(
    respuesta: UnderstandingResponse, cotiza: bool, esperado: RecordType | None
) -> None:
    assert understanding.opening_record_type(respuesta, quote_enabled=cotiza) is esperado


@pytest.mark.parametrize(
    ("actual", "respuesta", "cotiza", "esperado"),
    [
        # El ejemplo de Miguel: consultaba su poliza y ahora quiere reportar un accidente.
        (RecordType.COVERAGE_INQUIRY, Want.REPORT_ACCIDENT, True, RecordType.CLAIM),
        (RecordType.COVERAGE_INQUIRY, Want.QUOTE, True, RecordType.QUOTE_REQUEST),
        (RecordType.CLAIM, Want.QUOTE, True, RecordType.QUOTE_REQUEST),
        (RecordType.QUOTE_REQUEST, Want.REPORT_ACCIDENT, True, RecordType.CLAIM),
        (RecordType.QUOTE_REQUEST, Want.POLICY_QUESTION, True, RecordType.COVERAGE_INQUIRY),
        # Cotizar exige que la aseguradora cotice: donde no, no se abre nada.
        (RecordType.COVERAGE_INQUIRY, Want.QUOTE, False, None),
        # Preguntar por cobertura dentro de un reporte en curso no abre nada: es el mismo reporte.
        (RecordType.CLAIM, Want.POLICY_QUESTION, True, None),
        # Pedir lo mismo que el caso, o seguir con el, no es cambiar de tema.
        (RecordType.CLAIM, Want.REPORT_ACCIDENT, True, None),
        (RecordType.CLAIM, Want.CONTINUE, True, None),
        (RecordType.COVERAGE_INQUIRY, Want.POLICY_QUESTION, True, None),
        # Lo que no abre caso no lo cambia.
        (RecordType.CLAIM, Want.GENERAL_QUESTION, True, None),
        (RecordType.CLAIM, Want.GREETING, True, None),
        (RecordType.CLAIM, Want.TALK_TO_PERSON, True, None),
        (RecordType.CLAIM, Want.OTHER, True, None),
    ],
)
def test_cuando_cambiar_de_tema_abre_un_caso_nuevo(
    actual: RecordType, respuesta: Want, cotiza: bool, esperado: RecordType | None
) -> None:
    entendido = UnderstandingResponse(wants=respuesta)

    assert (
        understanding.switch_record_type(entendido, current=actual, quote_enabled=cotiza)
        is esperado
    )


@pytest.mark.parametrize("contesta", [Answer.YES, Answer.NO])
def test_quien_contesta_una_pregunta_de_si_o_no_no_esta_cambiando_de_tema(
    contesta: Answer,
) -> None:
    """«No, mejor reporto un choque» a «¿Es correcto?» contesta la lectura pendiente."""
    entendido = UnderstandingResponse(wants=Want.REPORT_ACCIDENT, answer=contesta)

    assert (
        understanding.switch_record_type(
            entendido, current=RecordType.QUOTE_REQUEST, quote_enabled=True
        )
        is None
    )


def test_preguntar_en_una_consulta_si_algo_esta_cubierto_no_abre_un_reporte() -> None:
    """«Ayer choque a un motociclista, ¿la poliza lo cubre?» dentro de una consulta: el modelo
    lo leyo como reportar un accidente y la conversacion paso sola a un reporte (2026-10-13)."""
    pregunta = UnderstandingResponse(wants=Want.REPORT_ACCIDENT, asks_about_coverage=True)

    assert (
        understanding.switch_record_type(
            pregunta, current=RecordType.COVERAGE_INQUIRY, quote_enabled=True
        )
        is None
    )
    # Cuando pide el reporte sin preguntar por cobertura, si se abre.
    pide = UnderstandingResponse(wants=Want.REPORT_ACCIDENT)
    assert (
        understanding.switch_record_type(
            pide, current=RecordType.COVERAGE_INQUIRY, quote_enabled=True
        )
        is RecordType.CLAIM
    )
    # Y la guarda es de la consulta: desde una cotizacion, contar un choque abre el reporte.
    assert (
        understanding.switch_record_type(
            pregunta, current=RecordType.QUOTE_REQUEST, quote_enabled=True
        )
        is RecordType.CLAIM
    )


def test_la_lista_cerrada_de_campos_es_la_de_los_tipos_de_caso() -> None:
    """Si `fields.yaml` gana un campo y esta lista no, el modelo no podria nombrarlo."""
    from typing import get_args

    from untangle.case_record import fields
    from untangle.orchestration.nodes.intake.extraction import DERIVED_FIELDS

    declarados = {
        d.key for tipo in RecordType for d in fields.definitions_for(tipo)
    } - DERIVED_FIELDS

    assert set(get_args(understanding.FieldKey)) == declarados


def test_un_campo_con_prefijo_no_cabe_en_el_esquema() -> None:
    """El primer mensaje perdia sus datos con `claim.incident_datetime` (2026-10-08)."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        UnderstandingResponse.model_validate(
            {"wants": "report_accident", "items": [{"field_key": "claim.location", "value": "x"}]}
        )


@pytest.mark.parametrize(
    ("tipo", "dicho"),
    [
        (RecordType.CLAIM, Want.REPORT_ACCIDENT),
        (RecordType.QUOTE_REQUEST, Want.QUOTE),
        (RecordType.COVERAGE_INQUIRY, Want.POLICY_QUESTION),
    ],
)
async def test_dentro_de_su_conversacion_pedir_lo_mismo_es_seguir(
    tipo: RecordType, dicho: Want
) -> None:
    async def entender(_p: UnderstandingRequest) -> UnderstandingResponse:
        return UnderstandingResponse(wants=dicho)

    peticion = UnderstandingRequest(**{**PETICION.__dict__, "record_type": tipo})
    respuesta = await understanding.understand(entender, peticion)

    assert respuesta is not None
    assert respuesta.wants is Want.CONTINUE


async def test_cambiar_de_tema_dentro_de_una_conversacion_se_conserva() -> None:
    async def entender(_p: UnderstandingRequest) -> UnderstandingResponse:
        return UnderstandingResponse(wants=Want.TALK_TO_PERSON)

    peticion = UnderstandingRequest(**{**PETICION.__dict__, "record_type": RecordType.CLAIM})
    respuesta = await understanding.understand(entender, peticion)

    assert respuesta is not None
    assert respuesta.wants is Want.TALK_TO_PERSON


async def test_una_duda_que_pregunta_por_cobertura_es_una_pregunta_por_la_poliza() -> None:
    async def entender(_p: UnderstandingRequest) -> UnderstandingResponse:
        return UnderstandingResponse(wants=Want.GENERAL_QUESTION, asks_about_coverage=True)

    respuesta = await understanding.understand(entender, PETICION)

    assert respuesta is not None
    assert respuesta.wants is Want.POLICY_QUESTION
    assert understanding.opening_record_type(respuesta, quote_enabled=True) is (
        RecordType.COVERAGE_INQUIRY
    )
