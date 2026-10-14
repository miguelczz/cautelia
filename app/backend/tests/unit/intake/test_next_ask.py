"""`blocks.next_ask` dice lo mismo que el nodo `intake` de verdad (2026-10-12).

El conductor de las evaluaciones contesta lo que `next_ask` dice que toca. Si el nodo
cambia la forma de preguntar y `next_ask` no, el conductor vuelve a contestar una pregunta
que nadie hizo --paso el 2026-10-08, cuando la solicitud de cotizacion dejo de leer de vuelta
cada bloque y las cuatro conversaciones de DS-4 se quedaron diciendo "si, es correcto" hasta
el techo de mensajes--. Esta prueba ata las dos cosas: corre el **nodo real**, con un
extractor que no devuelve nada, sobre varios estados de completitud, y exige que lo que sale
coincida con lo que `next_ask` predice.

El nodo no usa `next_ask`: el espejo es de lectura, y esta prueba es lo que lo mantiene
honesto.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest

from untangle.base import ProviderName, SpendSource, Use
from untangle.case_record import fields
from untangle.case_record.models import (
    CaseField,
    CaseState,
    Completeness,
    FieldStatus,
    RecordType,
)
from untangle.copy_catalog import api as copy_api
from untangle.orchestration.nodes.intake import blocks, composition
from untangle.orchestration.nodes.intake.blocks import AskKind, Block
from untangle.orchestration.nodes.intake.extraction import ExtractionResponse
from untangle.orchestration.nodes.intake.node import IntakeNode, IntakeNodeInput, IntakeNodeOutput
from untangle.providers.ports import (
    GenerationResult,
    InstructionText,
    PromptRef,
    SystemInstruction,
    UsageReport,
)

HOY = date(2026, 10, 12)
AHORA = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
DICHO, CONFIRMADO = FieldStatus.STATED, FieldStatus.CONFIRMED

SOLICITUD = RecordType.QUOTE_REQUEST
SINIESTRO = RecordType.CLAIM
CLAVES_DE_LA_SOLICITUD = tuple(d.key for d in fields.definitions_for(SOLICITUD))
OBLIGATORIOS_DEL_SINIESTRO = tuple(
    d.key for d in fields.definitions_for(SINIESTRO) if not d.optional
)

#: Un mensaje neutro y largo: no es una respuesta corta, no saluda ni agradece, y el
#: extractor doble no devuelve nada. Lo unico que cuenta es el estado del caso.
MENSAJE_NEUTRO = (
    "Continuemos con lo que sigue en el trámite del vehículo que estamos haciendo ahora mismo"
)


@pytest.fixture(autouse=True)
def _catalogo_limpio() -> Iterator[None]:
    copy_api.reset()
    yield
    copy_api.reset()


class _ExtractorVacio:
    async def __call__(self, _prompt: object) -> GenerationResult:
        return GenerationResult(
            text=None,
            parsed=ExtractionResponse(items=()),
            usage=UsageReport(
                provider=ProviderName.GEMINI,
                model="gemini-2.5-flash",
                use=Use.CHAT,
                source=SpendSource.PROVIDER_REPORTED,
            ),
            prompt=PromptRef(prompt_id="intake", locale="es", sha256="a" * 64),
        )


def _instruccion(_language: str) -> SystemInstruction:
    return SystemInstruction(
        ref=PromptRef(prompt_id="intake", locale="es", sha256="a" * 64),
        text=InstructionText("Eres la agente de captura."),
    )


def _completitud(record_type: RecordType, estados: dict[str, FieldStatus]) -> Completeness:
    """La completitud como la calcula el caso a partir de lo que tiene guardado."""
    campos = tuple(
        CaseField(
            case_id="C-1",
            field_key=clave,
            value=None,
            status=estado,
            evidence_turn_id="t0",
            updated_at=AHORA,
        )
        for clave, estado in estados.items()
    )
    return fields.completeness_of(record_type, campos)


async def _el_nodo_responde(
    record_type: RecordType, completitud: Completeness, *, language: str = "es"
) -> IntakeNodeOutput:
    nodo = IntakeNode(extract=_ExtractorVacio(), instruction=_instruccion, clock=lambda: HOY)
    return await nodo.run(
        IntakeNodeInput(
            tenant_id="sunmeadow",
            case_id="C-1",
            record_type=record_type,
            case_state=CaseState.CAPTURING,
            completeness=completitud,
            language=language,  # type: ignore[arg-type]
            turn_text=MENSAJE_NEUTRO,
            turn_id="t1",
            awaiting_confirmation=None,
            # Los valores de la lectura: el nodo los nombra al leer la solicitud entera.
            stated_values=dict.fromkeys(CLAVES_DE_LA_SOLICITUD, "valor"),
        )
    )


def _todo_menos(*faltantes: str, estado: FieldStatus = DICHO) -> dict[str, FieldStatus]:
    return {clave: estado for clave in CLAVES_DE_LA_SOLICITUD if clave not in faltantes}


#: (nombre, estados de la solicitud, la clave del campo que toca preguntar).
SOLICITUD_CON_FALTANTES = [
    ("nada dicho", {}, "driver_name"),
    ("un bloque dicho", dict.fromkeys(CLAVES_DE_LA_SOLICITUD[:4], DICHO), "vehicle_year"),
    ("un bloque dicho y confirmado", dict.fromkeys(CLAVES_DE_LA_SOLICITUD[:4], CONFIRMADO), "vehicle_year"),
    ("al segundo bloque le falta el vin", _todo_menos("vin", "salvage_title", "vehicle_age_years"), "vin"),
    ("falta un dato de un bloque anterior", _todo_menos("license_years"), "license_years"),
    ("sin cobertura, faltan los meses", _todo_menos("lapse_months"), "lapse_months"),
]  # fmt: skip


@pytest.mark.parametrize(
    ("nombre", "estados", "campo"),
    SOLICITUD_CON_FALTANTES,
    ids=[c[0] for c in SOLICITUD_CON_FALTANTES],
)
async def test_si_a_la_solicitud_le_falta_algo_el_nodo_pregunta_por_el_primer_campo_sin_decir(
    nombre: str, estados: dict[str, FieldStatus], campo: str
) -> None:
    completitud = _completitud(SOLICITUD, estados)

    pide = blocks.next_ask(SOLICITUD, completitud, CaseState.CAPTURING)
    salida = await _el_nodo_responde(SOLICITUD, completitud)

    assert (pide.kind, pide.key) == (AskKind.FIELD, campo), nombre
    # El mismo bloque, y sin lectura en espera: el nodo pregunta, no lee.
    assert salida.intake_next_block is pide.block
    assert salida.intake_awaiting_confirmation is None
    # Y el primer dato que el nodo pregunta es ese: la clave de su respuesta es la del
    # campo (la apertura con todo de una vez, cuando no hay nada dicho, es la unica
    # excepcion declarada).
    esperada = (
        str(composition.QUESTION_QUOTE_ALL) if not estados else f"intake.question.quote_{campo}"
    )
    assert salida.intake_response_key == esperada, nombre


async def test_con_todo_dicho_y_sin_confirmar_toca_la_confirmacion_del_ultimo_bloque() -> None:
    """Lo que dejo desorientado al conductor: el nodo lee toda la solicitud una vez y la deja
    en espera del ultimo bloque, y esa es la clave con la que el guion contesta."""
    completitud = _completitud(SOLICITUD, _todo_menos())

    pide = blocks.next_ask(SOLICITUD, completitud, CaseState.CAPTURING)
    salida = await _el_nodo_responde(SOLICITUD, completitud)

    assert pide.kind is AskKind.CONFIRMATION
    assert salida.intake_response_key == "intake.readback.quote_all"
    assert salida.intake_awaiting_confirmation is Block.QUOTE_HISTORY
    assert pide.key == salida.intake_awaiting_confirmation.value == "quote_history"
    assert pide.block is salida.intake_next_block is Block.QUOTE_HISTORY


async def test_con_todo_confirmado_no_toca_nada() -> None:
    completitud = _completitud(SOLICITUD, _todo_menos(estado=CONFIRMADO))

    pide = blocks.next_ask(SOLICITUD, completitud, CaseState.CAPTURING)
    salida = await _el_nodo_responde(SOLICITUD, completitud)

    assert completitud.complete == completitud.total == 17
    assert pide.kind is AskKind.DONE
    assert pide.block is salida.intake_next_block is Block.FINAL_CONFIRMATION


def test_un_caso_que_ya_no_captura_no_pregunta_nada() -> None:
    """El grafo no corre `intake` sobre una solicitud derivada (el nodo ni tiene pregunta
    para `done`), asi que aqui se compara con `next_block`, que es lo que el nodo mira."""
    completitud = _completitud(SOLICITUD, _todo_menos())

    for estado in (CaseState.DERIVED, CaseState.CLOSED, CaseState.OPEN):
        pide = blocks.next_ask(SOLICITUD, completitud, estado)

        assert pide.kind is AskKind.DONE
        assert pide.block is blocks.next_block(SOLICITUD, completitud, estado) is Block.DONE


def test_sin_campos_declarados_no_hay_nada_que_preguntar() -> None:
    vacia = Completeness.derive({}, awaiting_readback=frozenset(), optional=frozenset())

    assert blocks.next_ask(SOLICITUD, vacia, CaseState.CAPTURING).kind is AskKind.DONE


def test_la_solicitud_ya_no_se_pregunta_como_los_demas_tipos() -> None:
    """La regresion en una frase: con la solicitud dicha y sin confirmar, `next_block` sigue
    devolviendo el bloque del conductor --nada cuenta todavia--, y `next_ask` no."""
    completitud = _completitud(SOLICITUD, _todo_menos())

    assert blocks.next_block(SOLICITUD, completitud, CaseState.CAPTURING) is Block.QUOTE_DRIVER
    pide = blocks.next_ask(SOLICITUD, completitud, CaseState.CAPTURING)
    assert (pide.kind, pide.key) == (AskKind.CONFIRMATION, "quote_history")


# --- Los siniestros: la misma pregunta que ya contestaba el conductor ---------------------


async def test_un_siniestro_sin_nada_dicho_pregunta_por_los_heridos() -> None:
    completitud = _completitud(SINIESTRO, {})

    pide = blocks.next_ask(SINIESTRO, completitud, CaseState.CAPTURING)
    salida = await _el_nodo_responde(SINIESTRO, completitud)

    assert (pide.kind, pide.key) == (AskKind.FIELD, "injuries")
    assert pide.block is salida.intake_next_block is Block.SAFETY
    assert salida.intake_awaiting_confirmation is None


async def test_un_siniestro_con_identidad_y_heridos_pregunta_que_paso() -> None:
    completitud = _completitud(
        SINIESTRO, {"identity_and_policy": CONFIRMADO, "injuries": CONFIRMADO}
    )

    pide = blocks.next_ask(SINIESTRO, completitud, CaseState.CAPTURING)
    salida = await _el_nodo_responde(SINIESTRO, completitud)

    assert (pide.kind, pide.key) == (AskKind.FIELD, "description")
    assert pide.block is salida.intake_next_block is Block.WHAT_HAPPENED


async def test_un_siniestro_con_sus_cinco_datos_obligatorios_no_pregunta_mas() -> None:
    completitud = _completitud(SINIESTRO, dict.fromkeys(OBLIGATORIOS_DEL_SINIESTRO, CONFIRMADO))

    pide = blocks.next_ask(SINIESTRO, completitud, CaseState.CAPTURING)
    salida = await _el_nodo_responde(SINIESTRO, completitud)

    assert pide.kind is AskKind.DONE
    assert pide.block is salida.intake_next_block is Block.FINAL_CONFIRMATION
