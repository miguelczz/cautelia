"""El nodo `intake` con la forma de C-15: el orden del turno y su conjunto de escritura.

Las piezas de la unidad tienen cada una su prueba; esto prueba lo que ninguna de
ellas sabe: **en que orden se aplican**. Cada paso del turno puede terminarlo, y
cuál termina primero es la conducta.
"""

from __future__ import annotations

import asyncio
from datetime import date

import pytest

from untangle.base import ProviderName, SpendSource, Use
from untangle.case_record.models import CaseState, Completeness, RecordType
from untangle.compliance.controls import api as controls
from untangle.compliance.controls.phrases import EmergencyPhraseMode
from untangle.copy_catalog import api as copy_api
from untangle.orchestration.nodes.compliance.node import COMPLIANCE_SPEC
from untangle.orchestration.nodes.decision.node import DECISION_SPEC
from untangle.orchestration.nodes.intake import composition, confirmation, policy
from untangle.orchestration.nodes.intake.blocks import Block
from untangle.orchestration.nodes.intake.extraction import ExtractedItem, ExtractionResponse
from untangle.orchestration.nodes.intake.node import (
    INTAKE_SPEC,
    IntakeNode,
    IntakeNodeInput,
    SessionEnd,
)
from untangle.orchestration.nodes.intake.policy import PolicyMatch
from untangle.orchestration.nodes.intake.social import SocialIntent
from untangle.orchestration.nodes.policy_verification.node import POLICY_VERIFICATION_SPEC
from untangle.providers.ports import (
    GenerationResult,
    InstructionText,
    PromptRef,
    SystemInstruction,
    UsageReport,
)
from untangle.tenancy.models import IntakeConfig

HOY = date(2026, 9, 27)

#: La indicación de emergencia la produce el control barato de U10 (FD-U11-3).
INDICACION = controls.emergency_instruction(EmergencyPhraseMode.PUBLIC, language="es")[1]

#: Los siete campos de un siniestro, todos sin completar.
CAMPOS = (
    "identity_and_policy",
    "incident_datetime",
    "location",
    "description",
    "vehicle_and_driver",
    "other_parties",
    "injuries",
)


def _completitud(*completos: str) -> Completeness:
    """La completitud del siniestro como la calcula el caso: los opcionales en el
    mapa y fuera de la cuenta (P4)."""
    from untangle.case_record import fields

    return Completeness.derive(
        {c: c in completos for c in CAMPOS},
        optional=frozenset(d.key for d in fields.definitions_for(RecordType.CLAIM) if d.optional),
    )


def _resultado(*items: ExtractedItem) -> GenerationResult:
    return GenerationResult(
        text=None,
        parsed=ExtractionResponse(items=items),
        usage=UsageReport(
            provider=ProviderName.GEMINI,
            model="gemini-2.5-flash",
            use=Use.CHAT,
            source=SpendSource.PROVIDER_REPORTED,
        ),
        prompt=PromptRef(prompt_id="intake", locale="es", sha256="a" * 64),
    )


class _Extractor:
    """Un extractor de mentira que cuenta cuántas veces lo llamaron."""

    def __init__(self, *items: ExtractedItem) -> None:
        self._items = items
        self.llamadas = 0

    async def __call__(self, _prompt: object) -> GenerationResult:
        self.llamadas += 1
        return _resultado(*self._items)


def _instruccion(_language: str) -> SystemInstruction:
    return SystemInstruction(
        ref=PromptRef(prompt_id="intake", locale="es", sha256="a" * 64),
        text=InstructionText("Eres la agente de captura. Nunca afirmes cobertura."),
    )


def _nodo(extractor: _Extractor, *, lookup: _Buscador | None = None) -> IntakeNode:
    return IntakeNode(extract=extractor, instruction=_instruccion, clock=lambda: HOY, lookup=lookup)


TITULAR = PolicyMatch(
    policy_number="POL-11", holder_name="Natalia Henao Rendón", vehicle="Renault Logan 2024"
)


class _Buscador:
    """Un corpus de mentira: una sola poliza, y cuenta cuantas veces le preguntaron."""

    def __init__(self, coincidencia: PolicyMatch | None = TITULAR) -> None:
        self._coincidencia = coincidencia
        self.preguntas: list[str] = []

    async def __call__(self, _tenant_id: str, policy_number: str) -> PolicyMatch | None:
        self.preguntas.append(policy_number)
        if self._coincidencia is not None and policy_number == self._coincidencia.policy_number:
            return self._coincidencia
        return None


def _estado(**cambios: object) -> IntakeNodeInput:
    base: dict[str, object] = {
        "tenant_id": "knotwell",
        "case_id": "CASO-1",
        "record_type": RecordType.CLAIM,
        "case_state": CaseState.CAPTURING,
        "completeness": _completitud(),
        "language": "es",
        "turn_text": "me chocaron por detrás en la autopista",
        "turn_id": "turno-1",
    }
    return IntakeNodeInput.model_validate({**base, **cambios})


# --- El orden del turno -------------------------------------------------------


async def test_la_emergencia_termina_el_turno_sin_extraer_nada() -> None:
    """AC1.6.1, AC1.6.2 [bloquea]: no se le pide ningún dato a quien está sangrando.

    Y no solo no se pregunta: **no se llama al modelo**. Un turno de emergencia
    que gasta una llamada de extracción es un turno que tardó en decir lo único
    que importaba.
    """
    extractor = _Extractor(ExtractedItem(field_key="location", value="la autopista"))

    salida = await _nodo(extractor).run(
        _estado(
            emergency_raised=True,
            emergency_instruction=INDICACION,
            turn_text="mi acompañante está sangrando mucho",
        )
    )

    assert extractor.llamadas == 0
    assert salida.intake_extracted == ()
    assert INDICACION in salida.intake_response_text
    assert salida.intake_session_ended is None


async def test_sin_la_frase_de_u10_el_turno_de_emergencia_no_se_compone() -> None:
    with pytest.raises(ValueError, match=r"AC1\.6\.1"):
        await _nodo(_Extractor()).run(_estado(emergency_raised=True))


async def test_al_segundo_umbral_de_insultos_la_sesion_termina_sin_extraer() -> None:
    """BR5.4: seguir capturando de quien acaba de recibir la frase de cierre
    sería no haberla dicho."""
    extractor = _Extractor(ExtractedItem(field_key="location", value="la autopista"))
    insultos = ("son unos inutiles", "son unos incompetentes", "son unos idiotas")

    salida = await _nodo(extractor).run(_estado(person_turns=insultos, turn_text=insultos[-1]))

    assert extractor.llamadas == 0
    assert salida.intake_session_ended is SessionEnd.ABUSE
    assert salida.intake_next_block is Block.DONE
    assert salida.intake_response_text == composition.compose_closing_by_abuse(language="es")


async def test_al_primer_umbral_se_calma_y_la_sesion_sigue() -> None:
    salida = await _nodo(_Extractor()).run(
        _estado(
            person_turns=("son unos inutiles", "son unos incompetentes"),
            turn_text="son unos incompetentes",
        )
    )

    assert salida.intake_session_ended is None
    assert salida.intake_response_text == composition.compose_calm(language="es")


async def test_despues_de_la_calma_un_mensaje_sin_insultos_sigue_el_reporte() -> None:
    """C4, visto el 2026-10-07: el recuento es de toda la conversacion, y sin mirar el
    turno actual la agente repetia la frase de calma para siempre."""
    extractor = _Extractor(ExtractedItem(field_key="injuries", value="nadie"))
    insultos = ("son unos inutiles", "son unos incompetentes")

    salida = await _nodo(extractor).run(
        _estado(
            person_turns=(*insultos, "perdón, nadie salió herido"),
            turn_text="perdón, nadie salió herido",
        )
    )

    assert salida.intake_response_text != composition.compose_calm(language="es")
    assert extractor.llamadas == 1


async def test_el_umbral_lo_fija_la_aseguradora_y_no_el_codigo() -> None:
    """TECH-U11.5: con otra configuración, los mismos insultos hacen otra cosa."""
    dos = ("son unos inutiles", "son unos incompetentes")

    con_default = await _nodo(_Extractor()).run(_estado(person_turns=dos, turn_text=dos[-1]))
    con_umbral_alto = await _nodo(_Extractor()).run(
        _estado(
            person_turns=dos,
            turn_text=dos[-1],
            intake_config=IntakeConfig(calm_after_insults=5, close_after_insults=6),
        )
    )

    assert con_default.intake_response_text == composition.compose_calm(language="es")
    assert con_umbral_alto.intake_response_text != composition.compose_calm(language="es")


async def test_un_dato_dicho_en_este_turno_no_se_vuelve_a_preguntar_en_este_turno() -> None:
    """BR3.3: la extracción va antes de elegir el bloque.

    Al revés, se le preguntaría a la persona por el dato que acaba de dar, en el
    mismo turno en el que lo dio.

    **La aserción cambió dos veces y la intención no.** El 2026-09-29, porque
    `injuries` exigía lectura y decirlo lo dejaba esperando su lectura. El
    2026-10-06 (P4, decisión de Miguel) ningún campo del siniestro la exige: lo
    dicho cuenta en el acto, y el turno sigue con el bloque siguiente sin
    preguntar lo que acaba de oír.
    """
    extractor = _Extractor(ExtractedItem(field_key="injuries", value="nadie se lastimó"))

    salida = await _nodo(extractor).run(_estado(turn_text="nadie se lastimó, fue solo el golpe"))

    # Desde el 2026-10-07 una respuesta corta a una pregunta de un solo dato se
    # guarda por regla, sin modelo: el dato es el turno entero.
    assert extractor.llamadas == 0
    assert [(c.field_key, c.value) for c in salida.intake_extracted] == [
        ("injuries", "nadie se lastimó, fue solo el golpe")
    ]
    assert salida.intake_next_block is Block.IDENTITY_AND_POLICY
    assert salida.intake_response_key == str(composition.QUESTION_IDENTITY_AND_POLICY)
    assert salida.intake_awaiting_confirmation is None


# --- Guardar sin modelo lo que contesta una pregunta de un dato (2026-10-07) -------

#: Mas de doce palabras: lo que ya no es "una respuesta corta" y pasa por el modelo.
_LARGA = (
    "No, por suerte nadie se lastimó, aunque el otro conductor se bajó muy alterado "
    "y estuvimos discutiendo un rato largo en la vía"
)


#: Larga y sin fecha, hora ni lugar: nada que una regla pueda repartir.
_SIN_SENALES = (
    "No sabría decirle con exactitud, estaba muy nervioso y la verdad no me fijé bien "
    "en nada de eso mientras pasaba todo"
)


class _ExtractorLento(_Extractor):
    """Un modelo que no contesta a tiempo."""

    async def __call__(self, _prompt: object) -> GenerationResult:
        self.llamadas += 1
        await asyncio.sleep(5)
        return _resultado(*self._items)


async def test_una_respuesta_larga_si_pasa_por_el_modelo() -> None:
    extractor = _Extractor(ExtractedItem(field_key="injuries", value="nadie se lastimó"))

    salida = await _nodo(extractor).run(_estado(turn_text=_LARGA))

    assert extractor.llamadas == 1
    assert [c.field_key for c in salida.intake_extracted] == ["injuries"]


async def test_una_respuesta_corta_con_pregunta_no_se_guarda_a_ciegas() -> None:
    extractor = _Extractor()

    salida = await _nodo(extractor).run(_estado(turn_text="¿Y eso para qué lo necesita?"))

    assert extractor.llamadas == 1
    assert salida.intake_extracted == ()


async def test_si_el_modelo_no_contesta_a_tiempo_el_texto_queda_en_el_dato_pendiente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from untangle.orchestration.nodes.intake import node as node_module

    monkeypatch.setattr(node_module, "EXTRACTION_SOFT_TIMEOUT_S", 0.01)
    extractor = _ExtractorLento()

    salida = await _nodo(extractor).run(_estado(turn_text=_LARGA))

    assert extractor.llamadas == 1
    assert [(c.field_key, c.value) for c in salida.intake_extracted] == [("injuries", _LARGA)]
    assert salida.intake_next_block is Block.IDENTITY_AND_POLICY


async def test_si_el_modelo_no_contesta_y_la_pregunta_era_de_dos_datos_el_turno_falla(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cuando y donde son dos campos: sin modelo no se sabe repartir el texto, y
    adivinar seria inventar un dato. El ejecutor convierte el fallo en la frase de
    degradacion, como hasta ahora."""
    from untangle.orchestration.nodes.intake import node as node_module

    monkeypatch.setattr(node_module, "EXTRACTION_SOFT_TIMEOUT_S", 0.01)
    estado = _estado(
        turn_text=_SIN_SENALES,
        completeness=_completitud("injuries", "identity_and_policy", "description"),
    )

    with pytest.raises(TimeoutError):
        await _nodo(_ExtractorLento()).run(estado)


#: Con cuando y donde pendientes: el caso con todo menos esos dos.
_CUANDO_Y_DONDE = _completitud("injuries", "identity_and_policy", "description")


@pytest.mark.parametrize(
    ("texto", "campos"),
    [
        ("Ayer", ["incident_datetime"]),
        ("Fue el martes a las cinco de la tarde", ["incident_datetime"]),
        ("En la avenida Boyacá con calle 80", ["location"]),
        ("Saliendo del parqueadero del centro comercial", ["location"]),
        ("Ayer a las cinco en la avenida Boyacá con calle 80", ["incident_datetime", "location"]),
    ],
)
async def test_cuando_y_donde_se_reparten_por_regla_cuando_el_texto_lo_delata(
    texto: str, campos: list[str]
) -> None:
    extractor = _Extractor()

    salida = await _nodo(extractor).run(_estado(turn_text=texto, completeness=_CUANDO_Y_DONDE))

    assert extractor.llamadas == 0
    assert [c.field_key for c in salida.intake_extracted] == campos
    assert all(c.value == texto for c in salida.intake_extracted)


async def test_un_si_a_secas_no_se_guarda_como_lo_que_paso() -> None:
    """A «¿Qué pasó?» un «sí, soy yo» no contesta nada: va al modelo, que no saca
    nada, y la agente vuelve a preguntar; guardarlo seria inventar la descripcion."""
    extractor = _Extractor()

    salida = await _nodo(extractor).run(
        _estado(
            turn_text="Sí, soy yo", completeness=_completitud("injuries", "identity_and_policy")
        )
    )

    # Ni por regla ni por modelo: no hay nada que extraer, y la agente repite la
    # pregunta en el acto (en produccion esperar al modelo costaba ocho segundos).
    assert extractor.llamadas == 0
    assert salida.intake_extracted == ()
    assert salida.intake_next_block is Block.WHAT_HAPPENED


async def test_un_si_a_secas_que_el_modelo_pone_en_otro_campo_se_descarta() -> None:
    """El modelo devolvio «Sí, soy yo» como identidad: no es un nombre, y como la
    identidad ya estaba, habria salido «Corregido: Sí, soy yo»."""
    extractor = _Extractor(ExtractedItem(field_key="identity_and_policy", value="Sí, soy yo"))

    salida = await _nodo(extractor).run(
        _estado(
            turn_text="Sí, soy yo", completeness=_completitud("injuries", "identity_and_policy")
        )
    )

    # Desde que un si a secas no va al modelo, ni siquiera se le pregunta; el
    # filtro sobre lo que trae el modelo sigue ahi para los turnos largos.
    assert extractor.llamadas == 0
    assert salida.intake_extracted == ()
    assert "Corregido" not in salida.intake_response_text


async def test_la_poliza_dicha_ante_la_pregunta_de_seguridad_es_identidad_y_no_heridos() -> None:
    """Quien abre con su poliza antes de contestar si hubo heridos esta dando su
    identidad; la regla la guarda ahi sin modelo, y la seguridad sigue pendiente."""
    extractor = _Extractor()

    salida = await _nodo(extractor).run(_estado(turn_text="Soy Marcela Rios, mi poliza es POL-01."))

    assert extractor.llamadas == 0
    assert [c.field_key for c in salida.intake_extracted] == ["identity_and_policy"]
    assert salida.intake_next_block is Block.SAFETY


async def test_el_relato_del_choque_ante_la_pregunta_de_seguridad_va_al_modelo() -> None:
    """«Me chocaron por detrás» no dice nada de heridos: lo reparte el modelo."""
    extractor = _Extractor(ExtractedItem(field_key="description", value="me chocaron por detrás"))

    salida = await _nodo(extractor).run(_estado(turn_text="Me chocaron por detrás en un semáforo"))

    assert extractor.llamadas == 1
    assert [c.field_key for c in salida.intake_extracted] == ["description"]
    assert salida.intake_next_block is Block.SAFETY


async def test_un_si_a_secas_si_contesta_la_pregunta_de_seguridad() -> None:
    extractor = _Extractor()

    salida = await _nodo(extractor).run(_estado(turn_text="No, nadie"))

    assert extractor.llamadas == 0
    assert [c.field_key for c in salida.intake_extracted] == ["injuries"]


async def test_cuando_y_donde_sin_ninguna_senal_van_al_modelo() -> None:
    extractor = _Extractor(ExtractedItem(field_key="location", value="por el centro"))

    salida = await _nodo(extractor).run(
        _estado(turn_text="Fue por el centro, no me fijé más", completeness=_CUANDO_Y_DONDE)
    )

    assert extractor.llamadas == 1
    assert [c.field_key for c in salida.intake_extracted] == ["location"]


async def test_el_turno_entrega_la_clave_del_catalogo_y_el_texto() -> None:
    """C-14: U11 entrega la clave y el texto compuesto; el canal los usa los dos."""
    salida = await _nodo(_Extractor()).run(_estado())

    assert salida.intake_response_key.startswith("intake.")
    assert salida.intake_response_text


async def test_el_resumen_de_cierre_llega_cuando_no_falta_ningun_campo() -> None:
    """AC1.5.2 tras P4: con los siete campos dichos no hay nada que ofrecer y el
    siniestro cierra en el acto, con su numero y sin pregunta."""
    salida = await _nodo(_Extractor()).run(
        _estado(case_number="SIN-000042", completeness=_completitud(*CAMPOS))
    )

    assert salida.intake_next_block is Block.FINAL_CONFIRMATION
    assert salida.intake_response_key == str(composition.CLOSING_FAST_DONE)
    assert "SIN-000042" in salida.intake_response_text
    assert "?" not in salida.intake_response_text
    assert salida.intake_awaiting_confirmation is None
    assert salida.intake_capture_closed is True


# --- El recorrido rapido: sin lecturas, con oferta y con correccion (P4, 2026-10-06) ---

#: Los cinco obligatorios del siniestro: lo que basta para que el caso pase al ajustador.
OBLIGATORIOS = ("identity_and_policy", "incident_datetime", "location", "description", "injuries")


async def test_con_los_obligatorios_la_agente_cierra_y_ofrece_lo_opcional_una_vez() -> None:
    salida = await _nodo(_Extractor()).run(
        _estado(case_number="SIN-000042", completeness=_completitud(*OBLIGATORIOS))
    )

    assert salida.intake_response_key == str(composition.CLOSING_FAST_OFFER)
    assert "SIN-000042" in salida.intake_response_text
    for opcional in (Block.VEHICLE_AND_DRIVER, Block.OTHER_PARTIES):
        assert composition.block_label(opcional, language="es") in salida.intake_response_text
    assert salida.intake_awaiting_confirmation is Block.FINAL_CONFIRMATION, (
        "la respuesta a la oferta se lee en el turno siguiente"
    )
    assert salida.intake_capture_closed is True, (
        "la captura cierra en este turno, con la oferta abierta: el caso pasa a revision ya y "
        "no al contestar"
    )


#: Como llega el turno que contesta la oferta: el caso ya derivado y la oferta abierta.
_TRAS_LA_OFERTA = {
    "case_number": "SIN-000042",
    "case_state": CaseState.DERIVED,
    "awaiting_confirmation": Block.FINAL_CONFIRMATION,
}


async def test_un_si_a_la_oferta_pregunta_el_primer_bloque_opcional() -> None:
    salida = await _nodo(_Extractor()).run(
        _estado(
            turn_text="Sí, agreguemos eso",
            completeness=_completitud(*OBLIGATORIOS),
            **_TRAS_LA_OFERTA,
        )
    )

    pregunta = composition.compose_question(
        Block.VEHICLE_AND_DRIVER, ("vehicle_and_driver",), language="es"
    )
    assert salida.intake_response_text == pregunta
    assert salida.intake_awaiting_confirmation is Block.FINAL_CONFIRMATION
    assert salida.intake_capture_closed is False


async def test_un_no_a_la_oferta_cierra_y_deja_el_caso_con_el_ajustador() -> None:
    salida = await _nodo(_Extractor()).run(
        _estado(
            turn_text="No, así está bien",
            completeness=_completitud(*OBLIGATORIOS),
            **_TRAS_LA_OFERTA,
        )
    )

    assert salida.intake_response_key == str(composition.CLOSING_FAST_DECLINED)
    assert "SIN-000042" in salida.intake_response_text
    assert salida.intake_awaiting_confirmation is None
    assert salida.intake_capture_closed is False, "ya se derivo con la oferta"


async def test_un_no_asi_esta_bien_a_la_oferta_declina_aunque_ante_una_lectura_confirmara() -> None:
    """La misma frase significa lo contrario segun la pregunta: ante «¿quiere agregar
    X o lo dejamos?», «no, así está bien» deja el caso como está."""
    assert confirmation.is_affirmative("No, así está bien", language="es")
    assert not confirmation.accepts_offer("No, así está bien", language="es")
    assert not confirmation.accepts_offer("No, that's fine", language="en")
    assert confirmation.accepts_offer("Sí, agreguemos eso", language="es")
    assert confirmation.accepts_offer("Yes, let's add that", language="en")
    assert not confirmation.accepts_offer("mmm", language="es")


async def test_un_dato_opcional_tras_la_oferta_se_anota_y_se_pide_el_que_queda() -> None:
    extractor = _Extractor(ExtractedItem(field_key="vehicle_and_driver", value="mi Mazda, yo"))
    salida = await _nodo(extractor).run(
        _estado(
            turn_text="Iba en mi Mazda, conducía yo",
            completeness=_completitud(*OBLIGATORIOS),
            **_TRAS_LA_OFERTA,
        )
    )

    assert [c.field_key for c in salida.intake_extracted] == ["vehicle_and_driver"]
    pregunta = composition.compose_question(Block.OTHER_PARTIES, ("other_parties",), language="es")
    assert salida.intake_response_text == pregunta
    assert salida.intake_capture_closed is False


async def test_el_ultimo_dato_opcional_cierra_sin_volver_a_ofrecer() -> None:
    extractor = _Extractor(ExtractedItem(field_key="other_parties", value="un taxi"))
    salida = await _nodo(extractor).run(
        _estado(
            turn_text="El otro era un taxi",
            completeness=_completitud(*OBLIGATORIOS, "vehicle_and_driver"),
            **_TRAS_LA_OFERTA,
        )
    )

    assert salida.intake_response_key == str(composition.CLOSING_FAST_AFTER_EXTRA)
    assert salida.intake_awaiting_confirmation is None
    assert salida.intake_capture_closed is False


async def test_quien_sigue_escribiendo_tras_el_cierre_oye_donde_esta_su_caso() -> None:
    salida = await _nodo(_Extractor()).run(
        _estado(
            turn_text="¿Y ahora qué hago?",
            case_number="SIN-000042",
            case_state=CaseState.DERIVED,
            completeness=_completitud(*OBLIGATORIOS),
        )
    )

    assert salida.intake_response_key == str(composition.CLOSING_FAST_ALREADY)
    assert "SIN-000042" in salida.intake_response_text
    assert salida.intake_next_block is Block.DONE
    assert salida.intake_capture_closed is False


async def test_un_dato_que_llega_tras_el_cierre_se_anota_igual() -> None:
    extractor = _Extractor(ExtractedItem(field_key="other_parties", value="un taxi"))
    salida = await _nodo(extractor).run(
        _estado(
            turn_text="Se me olvidó: el otro carro era un taxi",
            case_number="SIN-000042",
            case_state=CaseState.DERIVED,
            completeness=_completitud(*OBLIGATORIOS),
        )
    )

    assert [c.field_key for c in salida.intake_extracted] == ["other_parties"]
    assert salida.intake_response_key == str(composition.CLOSING_FAST_AFTER_EXTRA)


async def test_un_dato_ya_dicho_que_vuelve_a_decirse_se_reemplaza_y_se_dice() -> None:
    """«Perdón, no eran dos sino tres»: se guarda lo nuevo, se dice que se corrigió
    y la agente sigue con lo que faltaba, sin volver a preguntar lo corregido."""
    extractor = _Extractor(ExtractedItem(field_key="injuries", value="tres heridos"))
    salida = await _nodo(extractor).run(
        _estado(
            turn_text="Perdón, no eran dos heridos sino tres",
            completeness=_completitud("injuries", "identity_and_policy"),
        )
    )

    assert [c.field_key for c in salida.intake_extracted] == ["injuries"]
    corregido = composition.compose_correction("tres heridos", language="es")
    assert salida.intake_response_text.startswith(corregido)
    assert salida.intake_next_block is Block.WHAT_HAPPENED
    assert salida.intake_awaiting_confirmation is None, "nada se lee de vuelta (P4)"


async def test_un_dato_dicho_por_primera_vez_no_se_anuncia_como_correccion() -> None:
    extractor = _Extractor(ExtractedItem(field_key="injuries", value="nadie"))
    salida = await _nodo(extractor).run(_estado(turn_text="No hubo heridos"))

    corregido = composition.compose_correction("nadie", language="es")
    assert corregido not in salida.intake_response_text
    assert salida.intake_awaiting_confirmation is None


# --- La poliza buscada en el corpus y el titular confirmado (P3, 2026-10-06) ------


async def test_con_la_poliza_dada_la_agente_dice_de_quien_es_y_pregunta_si_es_ella() -> None:
    """La identidad extraida trae un numero de poliza que el corpus conoce: en vez de
    seguir con el bloque siguiente, la agente nombra al titular y al vehiculo y
    pregunta si es ella. La poliza queda a la espera en el conjunto de escritura."""
    buscador = _Buscador()
    extractor = _Extractor(ExtractedItem(field_key="identity_and_policy", value="POL-11"))

    salida = await _nodo(extractor, lookup=buscador).run(
        _estado(turn_text="mi póliza es la POL-11", completeness=_completitud("injuries"))
    )

    assert buscador.preguntas == ["POL-11"]
    assert salida.intake_policy_match == TITULAR
    assert "POL-11" in salida.intake_response_text
    assert "Natalia Henao Rendón" in salida.intake_response_text
    assert "Renault Logan 2024" in salida.intake_response_text
    assert salida.intake_response_text.count("?") == 1
    assert salida.intake_response_key == str(policy.POLICY_FOUND)
    # Lo extraido se guarda igual: el numero que la persona dijo.
    assert [c.field_key for c in salida.intake_extracted] == ["identity_and_policy"]


async def test_en_una_consulta_solo_pregunta_si_es_ella_y_no_quien_manejaba() -> None:
    """Visto en produccion el 2026-10-08: a quien pregunto por el granizo se le pedia
    confirmar si "conducia ese carro". Eso solo se pregunta en un reporte de choque."""
    extractor = _Extractor(ExtractedItem(field_key="identity_and_policy", value="POL-11"))

    salida = await _nodo(extractor, lookup=_Buscador()).run(
        _estado(
            turn_text="soy Natalia, mi póliza es la POL-11",
            record_type=RecordType.COVERAGE_INQUIRY,
        )
    )

    assert salida.intake_response_key == str(policy.POLICY_FOUND_NO_VEHICLE)
    assert "Natalia Henao Rendón" in salida.intake_response_text
    assert "Renault Logan 2024" not in salida.intake_response_text


async def test_en_una_consulta_con_el_nombre_del_titular_no_pregunta_si_es_ella() -> None:
    """2026-10-09: «Soy Natalia Henao Rendon, mi poliza es POL-11. ¿Que me cubren si
    me roban el carro?» recibia «¿Eres tu?» antes de la respuesta."""
    extractor = _Extractor(
        ExtractedItem(field_key="identity_and_policy", value="POL-11"),
        ExtractedItem(field_key="question_asked", value="¿Qué me cubren?"),
    )

    salida = await _nodo(extractor, lookup=_Buscador()).run(
        _estado(
            turn_text="Soy Natalia Henao Rendon, mi póliza es POL-11. ¿Qué me cubren?",
            record_type=RecordType.COVERAGE_INQUIRY,
        )
    )

    assert salida.intake_policy_confirmed == "POL-11"
    assert salida.intake_policy_match is None
    assert "¿Eres tú?" not in salida.intake_response_text
    # La pregunta del mismo mensaje se guarda: es la que se responde enseguida.
    assert "question_asked" in {c.field_key for c in salida.intake_extracted}


def _completitud_de_consulta(*completos: str) -> Completeness:
    return Completeness.derive(
        {c: c in completos for c in ("identity_and_policy", "question_asked")}
    )


async def test_una_consulta_sin_pregunta_no_promete_revisar_sino_que_la_pide() -> None:
    """2026-10-12: quien entra por «Preguntar por mi poliza» da su nombre y su poliza y no
    ha preguntado nada. La agente decia «te respondo en un momento» y no habia nada que
    revisar: la respuesta no llegaba nunca. Sin pregunta se pregunta que quiere saber."""
    extractor = _Extractor(ExtractedItem(field_key="identity_and_policy", value="POL-11"))

    salida = await _nodo(extractor, lookup=_Buscador()).run(
        _estado(
            turn_text="Soy Natalia Henao Rendón, mi póliza es POL-11",
            record_type=RecordType.COVERAGE_INQUIRY,
            completeness=_completitud_de_consulta(),
        )
    )

    assert salida.intake_policy_confirmed == "POL-11"
    assert salida.intake_response_key == str(composition.COVERAGE_ASK_QUESTION)
    assert salida.intake_response_text == copy_api.t(composition.COVERAGE_ASK_QUESTION, locale="es")
    assert "momento" not in salida.intake_response_text


@pytest.mark.parametrize(
    ("dicha_antes", "dicha_ahora"),
    [
        pytest.param(("question_asked",), None, id="la-pregunta-llego-antes-que-la-poliza"),
        pytest.param((), "¿Qué me cubren?", id="la-pregunta-llega-con-la-poliza"),
    ],
)
async def test_una_consulta_con_pregunta_si_promete_revisar(
    dicha_antes: tuple[str, ...], dicha_ahora: str | None
) -> None:
    """El control positivo de arriba: con la pregunta en el caso, la revision se lanza y
    la frase de espera es verdad."""
    items = [ExtractedItem(field_key="identity_and_policy", value="POL-11")]
    if dicha_ahora is not None:
        items.append(ExtractedItem(field_key="question_asked", value=dicha_ahora))

    texto = "Soy Natalia Henao Rendón, mi póliza es POL-11"
    if dicha_ahora is not None:
        texto = f"{texto}. {dicha_ahora}"

    salida = await _nodo(_Extractor(*items), lookup=_Buscador()).run(
        _estado(
            turn_text=texto,
            record_type=RecordType.COVERAGE_INQUIRY,
            completeness=_completitud_de_consulta(*dicha_antes),
        )
    )

    assert salida.intake_policy_confirmed == "POL-11"
    assert salida.intake_response_key == str(composition.COVERAGE_CHECKING)


async def test_el_nombre_dicho_en_un_mensaje_anterior_tambien_evita_el_eres_tu() -> None:
    """2026-10-09: «Soy Daniel Foster, mi poliza es POL-31», despues «Preguntar por
    mi poliza»: el nombre llega como dato entendido del mensaje anterior."""
    from untangle.orchestration.nodes.intake import understanding

    entendido = understanding.UnderstandingResponse(
        wants=understanding.Want.POLICY_QUESTION,
        items=(
            understanding.UnderstoodItem(
                field_key="identity_and_policy", value="Natalia Henao Rendón, POL-11"
            ),
        ),
    )

    salida = await _nodo(_Extractor(), lookup=_Buscador()).run(
        _estado(
            turn_text="Preguntar por mi póliza",
            record_type=RecordType.COVERAGE_INQUIRY,
            understood=entendido,
        )
    )

    assert salida.intake_policy_confirmed == "POL-11"


async def test_en_un_reporte_con_el_nombre_del_titular_igual_pregunta_quien_manejaba() -> None:
    extractor = _Extractor(ExtractedItem(field_key="identity_and_policy", value="POL-11"))

    salida = await _nodo(extractor, lookup=_Buscador()).run(
        _estado(
            turn_text="Soy Natalia Henao Rendón, mi póliza es POL-11",
            completeness=_completitud("injuries"),
        )
    )

    assert salida.intake_policy_match == TITULAR
    assert salida.intake_policy_confirmed is None


async def test_una_poliza_que_el_corpus_no_tiene_sigue_la_captura_de_siempre() -> None:
    buscador = _Buscador(coincidencia=None)
    extractor = _Extractor(ExtractedItem(field_key="identity_and_policy", value="POL-99"))

    salida = await _nodo(extractor, lookup=buscador).run(
        _estado(turn_text="POL-99", completeness=_completitud("injuries"))
    )

    assert buscador.preguntas == ["POL-99"]
    assert salida.intake_policy_match is None
    assert salida.intake_next_block is Block.WHAT_HAPPENED


async def test_sin_numero_de_poliza_no_se_pregunta_al_corpus() -> None:
    buscador = _Buscador()
    extractor = _Extractor(ExtractedItem(field_key="description", value="me chocaron"))

    await _nodo(extractor, lookup=buscador).run(_estado(completeness=_completitud("injuries")))

    assert buscador.preguntas == []


async def test_el_si_al_titular_escribe_identidad_y_vehiculo_y_ata_la_poliza() -> None:
    """Un "si" no trae nada que extraer y escribe dos campos con la evidencia de este
    turno: la identidad con el nombre del titular y el vehiculo con el titular al
    volante. Y deja la poliza para que quien aplica el conjunto de escritura la ate
    al caso. Despues sigue con lo que toca, dando las gracias."""
    extractor = _Extractor()

    salida = await _nodo(extractor, lookup=_Buscador()).run(
        _estado(
            turn_text="Sí, soy yo",
            awaiting_policy_confirmation=TITULAR,
            completeness=_completitud("injuries"),
        )
    )

    assert extractor.llamadas == 0
    assert salida.intake_policy_confirmed == "POL-11"
    escritos = {c.field_key: c for c in salida.intake_extracted}
    assert set(escritos) == {"identity_and_policy", "vehicle_and_driver"}
    assert "Natalia Henao Rendón" in escritos["identity_and_policy"].value
    assert "POL-11" in escritos["identity_and_policy"].value
    assert "Renault Logan 2024" in escritos["vehicle_and_driver"].value
    assert all(c.evidence_turn_id == "turno-1" for c in escritos.values())
    assert salida.intake_response_text.startswith(
        composition.compose_transition(accepted=True, language="es")
    )
    assert salida.intake_next_block is Block.WHAT_HAPPENED


async def test_el_no_al_titular_devuelve_la_identidad_a_nadie_lo_dijo_y_la_pide_con_nombre() -> (
    None
):
    extractor = _Extractor()
    completitud = Completeness(
        per_field={**dict.fromkeys(CAMPOS, False), "injuries": True, "identity_and_policy": True},
        complete=2,
        total=len(CAMPOS),
    )

    salida = await _nodo(extractor, lookup=_Buscador()).run(
        _estado(
            turn_text="No, yo no soy",
            awaiting_policy_confirmation=TITULAR,
            completeness=completitud,
        )
    )

    assert extractor.llamadas == 0
    assert salida.intake_policy_confirmed is None
    assert salida.intake_readback_resolved is not None
    assert not salida.intake_readback_resolved.accepted
    assert salida.intake_readback_resolved.fields == ("identity_and_policy",)
    assert salida.intake_response_text == policy.compose_declined(language="es")
    assert salida.intake_next_block is Block.IDENTITY_AND_POLICY


# --- Lo que la persona dice de paso (decision de Miguel, 2026-10-06) -----------


async def test_un_saludo_a_secas_no_llama_al_modelo_y_antepone_el_saludo() -> None:
    """ "Hola" no trae nada que extraer, asi que el extractor no se llama; la
    respuesta saluda y **sigue con lo pendiente**, que en un caso nuevo es la
    pregunta de seguridad (BR1.1)."""
    extractor = _Extractor()

    salida = await _nodo(extractor).run(_estado(turn_text="Hola"))

    assert extractor.llamadas == 0
    assert salida.intake_extracted == ()
    saludo = composition.compose_social(SocialIntent.GREETING, language="es")[1]
    pregunta = composition.compose_question(Block.SAFETY, ("injuries",), language="es")
    assert salida.intake_response_text == f"{saludo} {pregunta}"
    assert salida.intake_response_key == str(composition.QUESTION_SAFETY)


async def test_un_saludo_con_datos_guarda_el_dato_y_tambien_saluda() -> None:
    extractor = _Extractor(ExtractedItem(field_key="injuries", value="nadie se lastimó"))

    salida = await _nodo(extractor).run(
        _estado(turn_text="Hola, nadie se lastimó, fue solo el golpe")
    )

    # Corta y contesta la pregunta de seguridad: se guarda por regla, sin modelo.
    assert extractor.llamadas == 0
    assert [c.field_key for c in salida.intake_extracted] == ["injuries"]
    assert salida.intake_response_text.startswith(
        composition.compose_social(SocialIntent.GREETING, language="es")[1]
    )


async def test_gracias_ante_una_lectura_pendiente_no_la_niega_sino_que_la_repite() -> None:
    """Antes, cualquier cosa que no fuera un si contaba como un no: "gracias"
    borraba el bloque de seguridad y lo volvia a preguntar."""
    extractor = _Extractor()
    estado = _estado(
        turn_text="Gracias",
        awaiting_confirmation=Block.SAFETY,
        stated_values={"injuries": "dos heridos"},
        completeness=Completeness(
            per_field=dict.fromkeys(CAMPOS, False),
            awaiting_readback=frozenset({"injuries"}),
            complete=0,
            total=len(CAMPOS),
        ),
    )

    salida = await _nodo(extractor).run(estado)

    assert extractor.llamadas == 0
    assert salida.intake_readback_resolved is None
    assert salida.intake_awaiting_confirmation is Block.SAFETY
    assert "dos heridos" in salida.intake_response_text
    assert salida.intake_response_text.startswith(
        composition.compose_social(SocialIntent.THANKS, language="es")[1]
    )


async def test_si_gracias_confirma_y_la_transicion_manda_sobre_el_agradecimiento() -> None:
    estado = _estado(
        turn_text="Sí, gracias",
        awaiting_confirmation=Block.SAFETY,
        completeness=Completeness(
            per_field=dict.fromkeys(CAMPOS, False),
            awaiting_readback=frozenset({"injuries"}),
            complete=0,
            total=len(CAMPOS),
        ),
    )

    salida = await _nodo(_Extractor()).run(estado)

    assert salida.intake_readback_resolved is not None
    assert salida.intake_readback_resolved.accepted
    gracias = composition.compose_transition(accepted=True, language="es")
    con_gusto = composition.compose_social(SocialIntent.THANKS, language="es")[1]
    assert salida.intake_response_text.startswith(gracias)
    assert con_gusto not in salida.intake_response_text
    assert salida.intake_next_block is Block.IDENTITY_AND_POLICY


async def test_la_despedida_va_sola_y_deja_la_lectura_pendiente() -> None:
    estado = _estado(
        turn_text="Hasta luego",
        awaiting_confirmation=Block.SAFETY,
        completeness=Completeness(
            per_field=dict.fromkeys(CAMPOS, False),
            awaiting_readback=frozenset({"injuries"}),
            complete=0,
            total=len(CAMPOS),
        ),
    )

    salida = await _nodo(_Extractor()).run(estado)

    assert salida.intake_response_key == str(composition.SOCIAL_GOODBYE)
    assert (
        salida.intake_response_text
        == composition.compose_social(SocialIntent.GOODBYE, language="es")[1]
    )
    assert "?" not in salida.intake_response_text
    assert salida.intake_awaiting_confirmation is Block.SAFETY
    assert salida.intake_session_ended is None


async def test_cuanto_falta_dice_el_avance_leido_del_caso_y_sigue_preguntando() -> None:
    estado = _estado(
        turn_text="¿Cuánto falta?",
        completeness=_completitud("injuries", "identity_and_policy", "description"),
    )

    salida = await _nodo(_Extractor()).run(estado)

    assert "3 de 5" in salida.intake_response_text, "los opcionales no cuentan en el total (P4)"
    assert (
        composition.block_label(Block.WHEN_AND_WHERE, language="es") in salida.intake_response_text
    )
    assert composition.block_label(Block.SAFETY, language="es") not in salida.intake_response_text
    # Preguntar cuanto falta no anota nada: la pregunta que sigue pide un solo dato, el
    # primero que falta (2026-10-12), y no los dos de "cuando y donde".
    pregunta = composition.compose_question(
        Block.WHEN_AND_WHERE, ("incident_datetime",), language="es"
    )
    assert salida.intake_response_text.endswith(pregunta)


async def test_una_lectura_corregida_lo_dice_antes_de_volver_a_preguntar() -> None:
    estado = _estado(
        turn_text="No, yo no dije eso",
        awaiting_confirmation=Block.SAFETY,
        completeness=Completeness(
            per_field=dict.fromkeys(CAMPOS, False),
            awaiting_readback=frozenset({"injuries"}),
            complete=0,
            total=len(CAMPOS),
        ),
    )

    salida = await _nodo(_Extractor()).run(estado)

    assert salida.intake_readback_resolved is not None
    assert not salida.intake_readback_resolved.accepted
    corrijo = composition.compose_transition(accepted=False, language="es")
    pregunta = composition.compose_question(Block.SAFETY, ("injuries",), language="es")
    assert salida.intake_response_text == f"{corrijo} {pregunta}"


# --- Un turno sin nada anotado pide un solo dato (2026-10-12) -----------------------


async def test_cuando_y_donde_sin_nada_anotado_se_vuelve_a_preguntar_solo_por_el_primero() -> None:
    """Se pidieron los dos y la persona no dio ninguno: repetir los dos no la ayuda."""
    estado = _estado(
        turn_text="mmm, no sé",
        completeness=_completitud("injuries", "identity_and_policy", "description"),
    )

    salida = await _nodo(_Extractor()).run(estado)

    assert salida.intake_extracted == ()
    assert salida.intake_response_key == str(composition.QUESTION_WHEN_ONLY)
    assert salida.intake_response_text == composition.compose_question(
        Block.WHEN_AND_WHERE, ("incident_datetime",), language="es"
    )


async def test_cuando_y_donde_si_se_anoto_algo_el_primer_mensaje_del_bloque_sigue_agrupado() -> (
    None
):
    """El control que distingue: sin el, la prueba de arriba pasaria con un nodo que
    preguntara siempre de a uno."""
    estado = _estado(
        turn_text="Me contó cómo pasó: un carro se me atravesó",
        completeness=_completitud("injuries", "identity_and_policy"),
    )

    salida = await _nodo(
        _Extractor(ExtractedItem(field_key="description", value="un carro se le atravesó"))
    ).run(estado)

    assert [c.field_key for c in salida.intake_extracted] == ["description"]
    assert salida.intake_response_key == str(composition.QUESTION_WHEN_AND_WHERE)
    assert salida.intake_response_text.endswith(
        composition.compose_question(
            Block.WHEN_AND_WHERE, ("incident_datetime", "location"), language="es"
        )
    )


async def test_una_lectura_rechazada_vuelve_a_preguntar_el_bloque_entero_y_agrupado() -> None:
    """Rechazar una lectura no es un turno sin respuesta: es el primer mensaje del bloque
    que se vuelve a pedir, y sigue agrupado."""
    completitud = _completitud("injuries", "identity_and_policy", "description").model_copy(
        update={"awaiting_readback": frozenset({"incident_datetime", "location"})}
    )
    estado = _estado(
        turn_text="No, yo no dije eso",
        awaiting_confirmation=Block.WHEN_AND_WHERE,
        completeness=completitud,
    )

    salida = await _nodo(_Extractor()).run(estado)

    assert salida.intake_readback_resolved is not None
    assert not salida.intake_readback_resolved.accepted
    assert salida.intake_response_key == str(composition.QUESTION_WHEN_AND_WHERE)


# --- La especificación (C-15) -------------------------------------------------


def test_ningun_nodo_comparte_un_campo_de_escritura_con_otro() -> None:
    """Convención 6: dos nodos no escriben el mismo campo del estado.

    `NodeSpec` no puede comprobarlo solo --no ve a los otros tres-- así que se
    comprueba aquí, que es donde están los cuatro. Es la razón por la que la
    salida de este nodo lleva el prefijo `intake_`: `policy_verification` ya
    escribe `response_key` y `response_text`.
    """
    especificaciones = (
        INTAKE_SPEC,
        POLICY_VERIFICATION_SPEC,
        DECISION_SPEC,
        COMPLIANCE_SPEC,
    )
    vistos: dict[str, str] = {}
    for spec in especificaciones:
        for campo in spec.writes:
            anterior = vistos.get(campo)
            assert anterior is None, f"'{campo}' lo escriben '{anterior}' y '{spec.name.value}'"
            vistos[campo] = spec.name.value


def test_la_captura_corre_en_el_ritmo_del_turno() -> None:
    """Es el único de los cuatro que lo hace: los otros tres son de fondo."""
    assert INTAKE_SPEC.rhythm == "turn"
    for spec in (POLICY_VERIFICATION_SPEC, DECISION_SPEC, COMPLIANCE_SPEC):
        assert spec.rhythm == "background"


# --- El cierre dice lo que es verdad: se revisa, y todavia no se sabe como termina (US1.17) ----

#: El turno que contesta la oferta con el caso en revision (las reglas aun no deciden).
_EN_REVISION = [CaseState.VERIFYING, CaseState.DECIDING]


def _tras_la_oferta_en_revision(estado: CaseState) -> dict[str, object]:
    return {
        "case_number": "SIN-000042",
        "case_state": estado,
        "awaiting_confirmation": Block.FINAL_CONFIRMATION,
    }


async def test_el_cierre_sin_oferta_dice_que_revisa_y_no_promete_un_ajustador() -> None:
    """El caso pasa a revision en este turno: las reglas pueden cerrarlo o mandarlo a un
    ajustador, y la frase no adelanta ninguna de las dos."""
    salida = await _nodo(_Extractor()).run(
        _estado(case_number="SIN-000042", completeness=_completitud(*CAMPOS))
    )

    assert salida.intake_response_text == (
        "Listo: ya tengo lo necesario para tu caso SIN-000042. "
        "Reviso tu reporte y te confirmo en un momento."
    )
    assert salida.intake_capture_closed is True


async def test_la_oferta_dice_que_ya_tiene_lo_necesario_y_no_promete_un_ajustador() -> None:
    salida = await _nodo(_Extractor()).run(
        _estado(case_number="SIN-000042", completeness=_completitud(*OBLIGATORIOS))
    )

    assert salida.intake_response_text.startswith(
        "Listo: ya tengo lo necesario para tu caso SIN-000042. ¿Quieres agregar "
    )
    assert salida.intake_response_text.endswith(", o lo dejamos así?")
    assert "ajustador" not in salida.intake_response_text.lower()


@pytest.mark.parametrize("estado", _EN_REVISION)
async def test_un_no_a_la_oferta_con_el_caso_en_revision_confirma_en_un_momento(
    estado: CaseState,
) -> None:
    salida = await _nodo(_Extractor()).run(
        _estado(
            turn_text="No, así está bien",
            completeness=_completitud(*OBLIGATORIOS),
            **_tras_la_oferta_en_revision(estado),
        )
    )

    assert salida.intake_response_key == str(composition.CLOSING_REVIEW_DECLINED)
    assert (
        salida.intake_response_text == "De acuerdo. Reviso tu reporte y te confirmo en un momento."
    )
    assert salida.intake_awaiting_confirmation is None, "la oferta se cierra"
    assert salida.intake_capture_closed is False, "la captura ya cerro con la oferta"
    assert salida.intake_next_block is Block.DONE


@pytest.mark.parametrize("estado", _EN_REVISION)
async def test_el_ultimo_dato_opcional_con_el_caso_en_revision_confirma_en_un_momento(
    estado: CaseState,
) -> None:
    extractor = _Extractor(ExtractedItem(field_key="other_parties", value="un taxi"))
    salida = await _nodo(extractor).run(
        _estado(
            turn_text="El otro era un taxi",
            completeness=_completitud(*OBLIGATORIOS, "vehicle_and_driver"),
            **_tras_la_oferta_en_revision(estado),
        )
    )

    assert salida.intake_response_key == str(composition.CLOSING_REVIEW_AFTER_EXTRA)
    assert (
        salida.intake_response_text
        == "Anotado, gracias. Reviso tu reporte y te confirmo en un momento."
    )
    assert salida.intake_awaiting_confirmation is None
    assert salida.intake_capture_closed is False


async def test_con_la_oferta_abierta_un_dato_opcional_sigue_ofreciendo_lo_que_queda() -> None:
    """Mientras quede algo por ofrecer la oferta sigue abierta: el caso no se resuelve."""
    extractor = _Extractor(ExtractedItem(field_key="vehicle_and_driver", value="mi Mazda, yo"))
    salida = await _nodo(extractor).run(
        _estado(
            turn_text="Iba en mi Mazda",
            completeness=_completitud(*OBLIGATORIOS),
            **_tras_la_oferta_en_revision(CaseState.DECIDING),
        )
    )

    assert salida.intake_awaiting_confirmation is Block.FINAL_CONFIRMATION


async def test_quien_sigue_escribiendo_mientras_se_revisa_oye_que_esta_en_revision() -> None:
    salida = await _nodo(_Extractor()).run(
        _estado(
            turn_text="¿Y ahora qué hago?",
            case_number="SIN-000042",
            case_state=CaseState.DECIDING,
            completeness=_completitud(*OBLIGATORIOS),
        )
    )

    assert salida.intake_response_key == str(composition.CLOSING_REVIEW_ALREADY)
    assert "SIN-000042" in salida.intake_response_text
    assert "ajustador" not in salida.intake_response_text.lower()
    assert salida.intake_capture_closed is False


async def test_un_dato_que_llega_mientras_se_revisa_se_anota_y_se_sigue_revisando() -> None:
    extractor = _Extractor(ExtractedItem(field_key="other_parties", value="un taxi"))
    salida = await _nodo(extractor).run(
        _estado(
            turn_text="Se me olvidó: el otro carro era un taxi",
            case_number="SIN-000042",
            case_state=CaseState.VERIFYING,
            completeness=_completitud(*OBLIGATORIOS),
        )
    )

    assert [c.field_key for c in salida.intake_extracted] == ["other_parties"]
    assert salida.intake_response_key == str(composition.CLOSING_REVIEW_AFTER_EXTRA)


@pytest.mark.parametrize("estado", [CaseState.DERIVED, CaseState.AWAITING_INSURED])
async def test_con_un_ajustador_las_frases_de_siempre_siguen_siendo_las_de_siempre(
    estado: CaseState,
) -> None:
    salida = await _nodo(_Extractor()).run(
        _estado(
            turn_text="No, así está bien",
            completeness=_completitud(*OBLIGATORIOS),
            **{**_TRAS_LA_OFERTA, "case_state": estado},
        )
    )

    assert salida.intake_response_key == str(composition.CLOSING_FAST_DECLINED)
    assert "ajustador" in salida.intake_response_text


async def test_un_caso_que_las_reglas_cerraron_se_dice_registrado_y_no_se_le_anota_nada() -> None:
    """BR6.4 de U4: un caso cerrado no cambia. El modelo ni se llama para extraer algo que no
    se va a guardar."""
    extractor = _Extractor(ExtractedItem(field_key="other_parties", value="un taxi"))
    salida = await _nodo(extractor).run(
        _estado(
            turn_text="Se me olvidó: el otro carro era un taxi",
            case_number="SIN-000042",
            case_state=CaseState.CLOSED,
            completeness=_completitud(*OBLIGATORIOS),
        )
    )

    assert extractor.llamadas == 0
    assert salida.intake_extracted == ()
    assert salida.intake_response_key == str(composition.CLOSING_FAST_REGISTERED)
    assert salida.intake_response_text == (
        "Tu caso SIN-000042 ya quedó registrado; puedes verlo con el enlace de arriba."
    )
    assert salida.intake_next_block is Block.DONE
    assert salida.intake_capture_closed is False


async def test_un_caso_cerrado_responde_a_una_emergencia_antes_que_a_nada() -> None:
    """La seguridad va primero: cerrado o no, quien dice que alguien se desangra oye la
    indicacion de emergencia."""
    salida = await _nodo(_Extractor()).run(
        _estado(
            case_state=CaseState.CLOSED,
            emergency_raised=True,
            emergency_instruction=INDICACION,
            completeness=_completitud(*OBLIGATORIOS),
        )
    )

    assert INDICACION in salida.intake_response_text


async def test_una_oferta_abierta_en_un_caso_que_nunca_paso_a_revision_lo_reintenta_al_cerrarse() -> (
    None
):
    """Si el paso a revision falla una vez, el caso sigue en captura con la oferta abierta: al
    cerrar la oferta la captura vuelve a darse por cerrada, que es lo que lo reintenta."""
    salida = await _nodo(_Extractor()).run(
        _estado(
            turn_text="No, así está bien",
            completeness=_completitud(*OBLIGATORIOS),
            case_number="SIN-000042",
            case_state=CaseState.CAPTURING,
            awaiting_confirmation=Block.FINAL_CONFIRMATION,
        )
    )

    assert salida.intake_response_key == str(composition.CLOSING_REVIEW_DECLINED)
    assert salida.intake_capture_closed is True


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize(
    "estado",
    [
        CaseState.CAPTURING,
        CaseState.VERIFYING,
        CaseState.DECIDING,
        CaseState.DERIVED,
        CaseState.CLOSED,
    ],
)
async def test_la_voz_no_dice_el_numero_ni_el_enlace_ni_un_ajustador_en_ninguna_fase(
    estado: CaseState, language: str
) -> None:
    """La despedida de la llamada es la que dice como quedo el caso, cuando ya se sabe."""
    salida = await _nodo(_Extractor()).run(
        _estado(
            turn_text="No, así está bien",
            language=language,
            spoken=True,
            case_number="SIN-000042",
            case_state=estado,
            completeness=_completitud(*OBLIGATORIOS),
            awaiting_confirmation=(
                Block.FINAL_CONFIRMATION if estado is not CaseState.CLOSED else None
            ),
        )
    )

    texto = salida.intake_response_text.lower()
    assert "sin-000042" not in texto
    assert "enlace" not in texto
    assert "link" not in texto
    assert "ajustador" not in texto
    assert "adjuster" not in texto
