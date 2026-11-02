"""El siniestro por el chat: todo lo que falta, en un solo mensaje (plan 09, punto 2, 2026-11-02).

Decision de Miguel: en el chat la agente pide de una vez los datos que faltan, como una lista que
**sale del codigo** --los bloques a los que el caso les debe algo--, y acepta las respuestas en uno
o en varios mensajes; por voz sigue una pregunta a la vez. Lo que se prueba es lo que la persona
lee y que la lista siga al caso: no pide lo ya dicho, no se repite sin avance, no sale en la
llamada y no pisa lo que ya funcionaba (emergencia, cotizacion).
"""

from __future__ import annotations

import pytest

from untangle.base import Locale
from untangle.copy_catalog import api as copy_api
from untangle.orchestration.nodes.intake import composition
from untangle.orchestration.nodes.intake.blocks import Block
from untangle.orchestration.nodes.intake.extraction import ExtractedItem
from untangle.orchestration.nodes.intake.understanding import (
    UnderstandingResponse,
    UnderstoodItem,
    Want,
)

from .test_node import _completitud, _estado, _Extractor, _nodo

_MARCADOR = composition.CLAIM_LIST_MARKER


def _lineas(texto: str) -> list[str]:
    return [linea for linea in texto.splitlines() if linea.startswith(_MARCADOR)]


def _entendido(*items: UnderstoodItem) -> UnderstandingResponse:
    return UnderstandingResponse(
        wants=Want.CONTINUE if items else Want.REPORT_ACCIDENT, items=items
    )


@pytest.mark.parametrize("idioma", ["es", "en"])
async def test_el_primer_turno_pide_la_lista_entera_con_los_opcionales_al_final(
    idioma: Locale,
) -> None:
    salida = await _nodo(_Extractor()).run(
        _estado(turn_text="Quiero reportar un choque", language=idioma)
    )

    assert salida.intake_response_key == str(composition.QUESTION_CLAIM_ALL)
    lineas = _lineas(salida.intake_response_text)
    # Los cuatro bloques obligatorios (heridos, identidad, que paso, cuando y donde) y los dos
    # opcionales (el carro y las otras personas), en ese orden.
    assert len(lineas) == 6
    assert salida.intake_response_text.splitlines()[0] == copy_api.t(
        composition.QUESTION_CLAIM_ALL, locale=idioma
    )
    assert "?" not in salida.intake_response_text
    assert salida.intake_next_block is Block.SAFETY
    assert salida.intake_extracted == ()


async def test_la_lista_no_pide_lo_ya_dicho_ni_repite_los_opcionales() -> None:
    salida = await _nodo(_Extractor()).run(
        _estado(
            turn_text="Me chocaron por detrás en la carrera 43",
            previous_block=Block.SAFETY,
            understood=_entendido(
                UnderstoodItem(field_key="description", value="Me chocaron por detrás"),
                UnderstoodItem(field_key="location", value="Carrera 43"),
            ),
        )
    )

    assert salida.intake_response_key == str(composition.QUESTION_CLAIM_REST)
    lineas = _lineas(salida.intake_response_text)
    # Faltan heridos, identidad y la hora: ni lo dicho ni los opcionales.
    assert [linea.removeprefix(_MARCADOR) for linea in lineas] == [
        copy_api.t(composition.CLAIM_ITEM_SAFETY, locale="es"),
        copy_api.t(composition.CLAIM_ITEM_IDENTITY_AND_POLICY, locale="es"),
        copy_api.t(composition.CLAIM_ITEM_WHEN_ONLY, locale="es"),
    ]


async def test_con_un_solo_bloque_pendiente_es_una_pregunta_y_no_una_lista() -> None:
    salida = await _nodo(_Extractor()).run(
        _estado(
            turn_text="Anoche, en la autopista",
            previous_block=Block.WHEN_AND_WHERE,
            completeness=_completitud("injuries", "identity_and_policy", "description"),
            understood=_entendido(UnderstoodItem(field_key="incident_datetime", value="Anoche")),
        )
    )

    assert _lineas(salida.intake_response_text) == []
    assert salida.intake_response_key == str(composition.QUESTION_WHERE_ONLY)


async def test_sin_avance_tras_la_lista_se_pregunta_una_sola_cosa() -> None:
    """La misma salvaguarda de la cotizacion: repetir la lista sin fin es peor que preguntar."""
    salida = await _nodo(_Extractor()).run(
        _estado(
            turn_text="No sé",
            previous_block=Block.SAFETY,
            understood=_entendido(),
        )
    )

    assert _lineas(salida.intake_response_text) == []
    assert salida.intake_response_key == str(composition.QUESTION_SAFETY)


@pytest.mark.parametrize("idioma", ["es", "en"])
async def test_por_voz_sigue_siendo_una_pregunta_a_la_vez(idioma: Locale) -> None:
    salida = await _nodo(_Extractor()).run(
        _estado(turn_text="Quiero reportar un choque", language=idioma, spoken=True)
    )

    assert _lineas(salida.intake_response_text) == []
    assert salida.intake_response_key == str(composition.QUESTION_SAFETY)


async def test_la_emergencia_gana_a_la_lista() -> None:
    salida = await _nodo(_Extractor()).run(
        _estado(
            turn_text="Mi hija está herida",
            emergency_raised=True,
            emergency_instruction="Llama ya al 911.",
        )
    )

    assert _lineas(salida.intake_response_text) == []
    assert "911" in salida.intake_response_text


async def test_los_datos_del_primer_mensaje_se_anotan_y_la_lista_pide_el_resto() -> None:
    salida = await _nodo(_Extractor(ExtractedItem(field_key="injuries", value="no"))).run(
        _estado(
            turn_text="Nadie se lastimó, fue solo el golpe",
            understood=_entendido(UnderstoodItem(field_key="injuries", value="no")),
        )
    )

    assert [c.field_key for c in salida.intake_extracted] == ["injuries"]
    assert salida.intake_response_key == str(composition.QUESTION_CLAIM_REST)
    assert len(_lineas(salida.intake_response_text)) == 3
