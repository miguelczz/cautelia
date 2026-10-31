"""El nodo `intake` con lo que la agente entendio del mensaje (fase 0, 2026-10-07).

Lo que se prueba es lo que cambia cuando el turno trae `understood`: los datos y el
si o el no salen de lo entendido, no de reglas por palabras ni del extractor, y
pasan por la misma validacion y normalizacion que cualquier dato.
"""

from __future__ import annotations

from untangle.case_record.models import Completeness, RecordType
from untangle.orchestration.nodes.intake.blocks import Block
from untangle.orchestration.nodes.intake.extraction import ExtractedItem
from untangle.orchestration.nodes.intake.understanding import (
    Answer,
    UnderstandingResponse,
    UnderstoodItem,
    Want,
)

from .test_node import (
    CAMPOS,
    TITULAR,
    _Buscador,
    _completitud,
    _estado,
    _Extractor,
    _nodo,
)


def _entendido(*items: UnderstoodItem, answer: Answer = Answer.NONE) -> UnderstandingResponse:
    return UnderstandingResponse(wants=Want.CONTINUE, items=items, answer=answer)


async def test_los_datos_salen_de_lo_entendido_sin_llamar_al_extractor() -> None:
    """E4: «desde el 2022» llega ya como 4 y no como el 18 que el texto tambien trae."""
    extractor = _Extractor(ExtractedItem(field_key="license_years", value="18"))

    salida = await _nodo(extractor).run(
        _estado(
            record_type=RecordType.QUOTE_REQUEST,
            turn_text="Desde el 2022, recién cumplidos los 18 años, ¿cuántos años es eso?",
            understood=_entendido(UnderstoodItem(field_key="license_years", value="4")),
        )
    )

    assert extractor.llamadas == 0
    assert [(c.field_key, c.value) for c in salida.intake_extracted] == [("license_years", "4")]


async def test_lo_entendido_pasa_por_la_misma_validacion_que_lo_extraido() -> None:
    """Un campo de otro tipo de caso no se escribe, y un valor tipado que no se
    puede convertir tampoco: el modelo propone y el codigo valida."""
    salida = await _nodo(_Extractor()).run(
        _estado(
            record_type=RecordType.QUOTE_REQUEST,
            turn_text="uso el carro a veces",
            understood=_entendido(
                UnderstoodItem(field_key="use_type", value="a veces"),
                UnderstoodItem(field_key="injuries", value="no"),
            ),
        )
    )

    assert salida.intake_extracted == ()


async def test_una_correccion_que_empieza_por_si_rechaza_la_lectura() -> None:
    """«Así es, pero fue a las 9 de la noche»: el reconocedor por frases lo lee como
    un si y confirmaba una hora equivocada. Lo entendido dice que es un no."""
    estado = _estado(
        turn_text="Así es, pero fue a las 9 de la noche",
        awaiting_confirmation=Block.SAFETY,
        completeness=Completeness(
            per_field=dict.fromkeys(CAMPOS, False),
            awaiting_readback=frozenset({"injuries"}),
            complete=0,
            total=len(CAMPOS),
        ),
        understood=_entendido(answer=Answer.NO),
    )

    salida = await _nodo(_Extractor()).run(estado)

    assert salida.intake_readback_resolved is not None
    assert not salida.intake_readback_resolved.accepted


async def test_un_si_entendido_confirma_aunque_no_diga_si() -> None:
    estado = _estado(
        turn_text="Así fue, tal cual",
        awaiting_confirmation=Block.SAFETY,
        completeness=Completeness(
            per_field=dict.fromkeys(CAMPOS, False),
            awaiting_readback=frozenset({"injuries"}),
            complete=0,
            total=len(CAMPOS),
        ),
        understood=_entendido(answer=Answer.YES),
    )

    salida = await _nodo(_Extractor()).run(estado)

    assert salida.intake_readback_resolved is not None
    assert salida.intake_readback_resolved.accepted


async def test_soy_el_titular_pero_manejaba_mi_hijo_confirma_y_anota_al_conductor() -> None:
    """C3: antes se anotaba que conducia el titular."""
    salida = await _nodo(_Extractor(), lookup=_Buscador()).run(
        _estado(
            turn_text="Sí, soy yo, pero el que iba manejando era mi hijo",
            awaiting_policy_confirmation=TITULAR,
            completeness=_completitud("injuries"),
            understood=_entendido(
                UnderstoodItem(field_key="vehicle_and_driver", value="manejaba su hijo"),
                answer=Answer.YES,
            ),
        )
    )

    assert salida.intake_policy_confirmed == "POL-11"
    vehiculo = next(c for c in salida.intake_extracted if c.field_key == "vehicle_and_driver")
    assert "Renault Logan 2024" in vehiculo.value
    assert "manejaba su hijo" in vehiculo.value


async def test_si_lo_entendido_ya_nombra_el_vehiculo_no_se_repite() -> None:
    """Se guardaba «Nissan Rogue 2012. Nissan Rogue 2012. Driven by the policyholder»
    (caso AP-53, 2026-10-31): el vehiculo de la poliza delante de un texto que ya lo traia."""
    salida = await _nodo(_Extractor(), lookup=_Buscador()).run(
        _estado(
            turn_text="Sí, soy yo y manejaba el Renault",
            awaiting_policy_confirmation=TITULAR,
            completeness=_completitud("injuries"),
            understood=_entendido(
                UnderstoodItem(
                    field_key="vehicle_and_driver", value="Renault Logan 2024, manejaba el titular"
                ),
                answer=Answer.YES,
            ),
        )
    )

    vehiculo = next(c for c in salida.intake_extracted if c.field_key == "vehicle_and_driver")
    assert vehiculo.value == "Renault Logan 2024, manejaba el titular"


async def test_si_la_persona_dice_quien_manejaba_no_se_anota_que_conducia_el_titular() -> None:
    """La frase del catalogo afirma lo contrario de lo que la persona acaba de decir.

    Se guardaba «Renault Logan 2024, conducía el titular. manejaba su hijo»: un texto que dice
    las dos cosas, que el ajustador lee tal cual y del que la derivacion del conductor no puede
    sacar nada. Con un si a secas, en cambio, la frase del titular sigue siendo la que se anota.
    """
    con_conductor = await _nodo(_Extractor(), lookup=_Buscador()).run(
        _estado(
            turn_text="Sí, soy yo, pero el que iba manejando era mi hijo",
            awaiting_policy_confirmation=TITULAR,
            completeness=_completitud("injuries"),
            understood=_entendido(
                UnderstoodItem(field_key="vehicle_and_driver", value="manejaba su hijo"),
                answer=Answer.YES,
            ),
        )
    )
    a_secas = await _nodo(_Extractor(), lookup=_Buscador()).run(
        _estado(
            turn_text="Sí",
            awaiting_policy_confirmation=TITULAR,
            completeness=_completitud("injuries"),
            understood=_entendido(answer=Answer.YES),
        )
    )

    dicho = next(c for c in con_conductor.intake_extracted if c.field_key == "vehicle_and_driver")
    anotado = next(c for c in a_secas.intake_extracted if c.field_key == "vehicle_and_driver")
    assert "conducía el titular" not in dicho.value
    assert anotado.value == "Renault Logan 2024, conducía el titular"


async def test_un_no_entendido_al_titular_no_confirma_aunque_el_texto_empiece_por_si() -> None:
    """Lo entendido manda sobre las palabras: «Sí, bueno, no soy yo, es mi mama»."""
    salida = await _nodo(_Extractor(), lookup=_Buscador()).run(
        _estado(
            turn_text="Sí, bueno, no soy yo, es la póliza de mi mamá",
            awaiting_policy_confirmation=TITULAR,
            completeness=_completitud("injuries", "identity_and_policy"),
            understood=_entendido(answer=Answer.NO),
        )
    )

    assert salida.intake_policy_confirmed is None


async def test_sin_lo_entendido_la_captura_sigue_como_antes() -> None:
    """Si el modelo falla o tarda, el turno no trae `understood` y manda la regla."""
    salida = await _nodo(_Extractor()).run(_estado(turn_text="No, nadie se lastimó"))

    assert [c.field_key for c in salida.intake_extracted] == ["injuries"]


async def test_el_mensaje_que_abre_la_cotizacion_no_se_anota_como_un_dato() -> None:
    """Visto el 2026-10-08: "Pedir una cotizacion" quedo como nombre del conductor."""
    salida = await _nodo(_Extractor()).run(
        _estado(
            record_type=RecordType.QUOTE_REQUEST,
            turn_text="Pedir una cotización",
            understood=UnderstandingResponse(wants=Want.QUOTE, items=()),
        )
    )

    assert salida.intake_extracted == ()


async def test_confirmar_la_poliza_como_ultimo_dato_cierra_el_reporte_en_vez_de_caerse() -> None:
    """Quien cuenta todo --incluido que nadie salio herido-- y da su poliza al final.

    Al contestar «si» a «¿Eres tu?» ya no falta nada. La rama de la confirmacion
    armaba "la siguiente pregunta" de un siniestro sin preguntas pendientes y
    levantaba: en el chat salio "Tuve un problema para responder eso" (2026-10-10).
    """
    salida = await _nodo(_Extractor(), lookup=_Buscador()).run(
        _estado(
            turn_text="si, yo iba manejando el Logan",
            awaiting_policy_confirmation=TITULAR,
            completeness=_completitud(
                "injuries", "description", "incident_datetime", "location", "other_parties"
            ),
            understood=_entendido(answer=Answer.YES),
        )
    )

    assert salida.intake_policy_confirmed == "POL-11"
    assert {c.field_key for c in salida.intake_extracted} >= {"identity_and_policy"}
    # El reporte se cierra en este mismo turno y la frase lo dice.
    assert salida.intake_capture_closed is True
    assert salida.intake_response_text


# --- El dato de heridos solo se anota si la persona hablo de eso (2026-10-10) ------

HERIDOS_NO = UnderstoodItem(field_key="injuries", value="no")


async def test_el_modelo_no_puede_anotar_que_no_hubo_heridos_si_nadie_lo_dijo() -> None:
    """El caso del chat: un choque contado sin una palabra sobre las personas."""
    salida = await _nodo(_Extractor()).run(
        _estado(
            turn_text=(
                "hola, ayer un taxi me choco por detras en la avenida 80 con la 33, "
                "estaba parado en el semaforo"
            ),
            understood=_entendido(
                HERIDOS_NO,
                UnderstoodItem(field_key="description", value="un taxi lo choco por detras"),
            ),
        )
    )

    claves = {c.field_key for c in salida.intake_extracted}
    assert "injuries" not in claves
    # Lo demas que si dijo se conserva: la regla descarta un dato, no el mensaje.
    assert "description" in claves
    # Y la pregunta de seguridad sigue pendiente.
    assert salida.intake_next_block is Block.SAFETY


async def test_si_la_persona_dice_que_nadie_salio_herido_el_dato_se_anota() -> None:
    salida = await _nodo(_Extractor()).run(
        _estado(
            turn_text="me chocaron por detras ayer, gracias a Dios nadie salio herido",
            understood=_entendido(HERIDOS_NO),
        )
    )

    assert "injuries" in {c.field_key for c in salida.intake_extracted}


async def test_un_no_corto_a_la_pregunta_de_heridos_se_anota() -> None:
    salida = await _nodo(_Extractor()).run(
        _estado(
            turn_text="no, tranquila",
            previous_block=Block.SAFETY,
            understood=_entendido(HERIDOS_NO),
        )
    )

    assert "injuries" in {c.field_key for c in salida.intake_extracted}


async def test_un_no_corto_a_otra_pregunta_no_dice_nada_de_heridos() -> None:
    salida = await _nodo(_Extractor()).run(
        _estado(
            turn_text="no, tranquila",
            previous_block=Block.WHAT_HAPPENED,
            understood=_entendido(HERIDOS_NO),
        )
    )

    assert "injuries" not in {c.field_key for c in salida.intake_extracted}


async def test_en_una_llamada_el_primer_no_ya_no_contesta_por_heridos() -> None:
    """La apertura hablada pregunta "¿en que te puedo ayudar?" desde el 2026-10-11:
    un "no" en el primer turno no habla de heridos, y anotarlo seria inventar el dato."""
    salida = await _nodo(_Extractor()).run(
        _estado(turn_text="no, tranquila", spoken=True, understood=_entendido(HERIDOS_NO))
    )

    assert "injuries" not in {c.field_key for c in salida.intake_extracted}


async def test_corregir_el_dato_de_heridos_ya_dicho_no_pide_respaldo() -> None:
    """«Perdon, no eran dos sino tres»: no nombra heridos, pero corrige lo que ya dijo."""
    salida = await _nodo(_Extractor()).run(
        _estado(
            turn_text="perdón, no eran dos sino tres",
            previous_block=Block.WHAT_HAPPENED,
            completeness=_completitud("injuries"),
            understood=_entendido(UnderstoodItem(field_key="injuries", value="tres heridos")),
        )
    )

    assert "injuries" in {c.field_key for c in salida.intake_extracted}


# --- Una respuesta dudosa a "¿eres tu?" (2026-10-14) -------------------------------------


async def test_una_respuesta_que_no_es_ni_si_ni_no_vuelve_a_preguntar_una_vez() -> None:
    """En una llamada, una frase mal oida tras "¿eres tu?" hizo pedir otra vez nombre y poliza."""
    salida = await _nodo(_Extractor(), lookup=_Buscador()).run(
        _estado(
            turn_text="¿No sería mejor que fuera solamente con el?",
            awaiting_policy_confirmation=TITULAR,
            completeness=_completitud("injuries", "identity_and_policy"),
            understood=_entendido(answer=Answer.NONE),
        )
    )

    assert salida.intake_policy_confirmed is None
    assert salida.intake_policy_match == TITULAR, "la poliza sigue esperando el si"
    assert salida.intake_policy_confirm_reasked
    assert salida.intake_response_key == "intake.policy.confirm_again_driver"
    assert TITULAR.holder_name in salida.intake_response_text
    assert salida.intake_readback_resolved is None


async def test_si_tampoco_la_segunda_vez_es_un_si_se_trata_como_no() -> None:
    salida = await _nodo(_Extractor(), lookup=_Buscador()).run(
        _estado(
            turn_text="eh, no sé, ¿cómo así?",
            awaiting_policy_confirmation=TITULAR,
            policy_confirm_reasked=True,
            completeness=_completitud("injuries", "identity_and_policy"),
            understood=_entendido(answer=Answer.NONE),
        )
    )

    assert salida.intake_policy_confirmed is None
    assert salida.intake_policy_match is None
    assert salida.intake_response_key == "intake.policy.declined"


async def test_en_una_consulta_se_vuelve_a_preguntar_sin_hablar_del_carro() -> None:
    salida = await _nodo(_Extractor(), lookup=_Buscador()).run(
        _estado(
            record_type=RecordType.COVERAGE_INQUIRY,
            turn_text="¿perdón?",
            awaiting_policy_confirmation=TITULAR,
            completeness=_completitud("identity_and_policy"),
            understood=_entendido(answer=Answer.NONE),
        )
    )

    assert salida.intake_response_key == "intake.policy.confirm_again"
    assert "carro" not in salida.intake_response_text
