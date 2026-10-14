"""La poliza que se oyo mal, o que no esta: buscarla por el nombre y confirmarla (2026-10-13).

En una llamada real, «Soy Marco Parker, mi poliza es POL-200117» llego como «Marco Parker y mi
poliza es Paul 201 17». El caso quedo con «poliza Paul 201 17» y **sin poliza identificada**,
mientras que en el chat la agente dice «Encontre la poliza ... ¿Eres tu?». Estas pruebas fijan lo
que el nodo hace ahora con un numero que no existe o que llego incompleto:

- con el nombre completo del titular, **una sola** poliza suya y cifras que se parecen, **propone**
  esa poliza con la frase de siempre y espera el si;
- si no, dice que no la encontro y pide que la repita cifra por cifra, **una sola vez**;
- **nunca ata una poliza que la persona no confirmo**.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from untangle.orchestration.nodes.intake import policy
from untangle.orchestration.nodes.intake.blocks import Block
from untangle.orchestration.nodes.intake.extraction import ExtractedItem
from untangle.orchestration.nodes.intake.node import IntakeNode, IntakeNodeOutput
from untangle.orchestration.nodes.intake.policy import PolicyMatch

from .test_node import (
    HOY,
    _Buscador,
    _completitud,
    _estado,
    _Extractor,
    _instruccion,
)

MARCO = PolicyMatch(
    policy_number="POL-200117", holder_name="Marco Parker", vehicle="Ford Escape 2020"
)
ANA = PolicyMatch(
    policy_number="POL-422088", holder_name="Ana Torres", vehicle="Subaru Outback 2014"
)
# Una segunda poliza del mismo titular: con ella, «el titular con ese nombre» ya no es uno.
MARCO_OTRA = PolicyMatch(policy_number="POL-200999", holder_name="Marco Parker", vehicle=None)

LLAMADA_REAL = "Claro, mi nombre completo es Marco Parker y mi póliza es Paul 201 17."


class _Titulares:
    """El corpus de una aseguradora, visto por nombre: lo que cablea la raiz con `list_policies`."""

    def __init__(self, *polizas: PolicyMatch) -> None:
        self._polizas = polizas
        self.preguntas: list[tuple[str, str]] = []

    async def __call__(self, tenant_id: str, text: str) -> Sequence[PolicyMatch]:
        self.preguntas.append((tenant_id, text))
        return tuple(p for p in self._polizas if policy.names_holder(text, p.holder_name))


def _nodo(
    titulares: _Titulares | None,
    *,
    extractor: _Extractor | None = None,
    corpus: Sequence[PolicyMatch] = (MARCO, ANA),
) -> IntakeNode:
    por_numero = {p.policy_number: p for p in corpus}

    async def exacta(_tenant: str, numero: str) -> PolicyMatch | None:
        return por_numero.get(numero)

    return IntakeNode(
        extract=extractor or _Extractor(),
        instruction=_instruccion,
        clock=lambda: HOY,
        lookup=exacta,
        holder_lookup=titulares,
    )


def _identidad(valor: str) -> _Extractor:
    return _Extractor(ExtractedItem(field_key="identity_and_policy", value=valor))


def _propone(salida: IntakeNodeOutput, esperada: PolicyMatch, *, language: str = "es") -> None:
    """La agente propone la poliza con la frase del chat, y no ata nada."""
    assert salida.intake_policy_match == esperada
    assert salida.intake_policy_confirmed is None
    clave, texto = policy.compose_found(esperada, language="es" if language == "es" else "en")
    assert salida.intake_response_key == str(clave)
    assert salida.intake_response_text == texto
    assert salida.intake_policy_repeat_asked is False
    assert salida.intake_next_block is Block.IDENTITY_AND_POLICY


def _pide_repetir(salida: IntakeNodeOutput) -> None:
    assert salida.intake_response_key == str(policy.POLICY_NOT_FOUND_REPEAT)
    assert salida.intake_policy_repeat_asked is True
    assert salida.intake_policy_match is None
    assert salida.intake_policy_confirmed is None
    assert salida.intake_next_block is Block.IDENTITY_AND_POLICY
    assert salida.intake_awaiting_confirmation is None


# --- Propone: nombre completo + una sola poliza suya + cifras que se parecen -----------------


@pytest.mark.parametrize("por_voz", [True, False], ids=["llamada", "chat"])
async def test_la_llamada_real_propone_la_poliza_del_titular_y_espera_el_si(por_voz: bool) -> None:
    titulares = _Titulares(MARCO, ANA)
    nodo = _nodo(titulares, extractor=_identidad("Marco Parker, póliza Paul 201 17"))

    salida = await nodo.run(
        _estado(
            turn_text=LLAMADA_REAL,
            spoken=por_voz,
            completeness=_completitud("injuries"),
            tenant_id="sunmeadow",
        )
    )

    _propone(salida, MARCO)
    # Y la frase es la del chat, con los mismos datos y ninguno nuevo.
    assert "POL-200117" in salida.intake_response_text
    assert "Marco Parker" in salida.intake_response_text
    assert "Ford Escape 2020" in salida.intake_response_text
    assert salida.intake_response_text.count("?") == 1
    # La busqueda es de la aseguradora de la llamada y nada mas.
    assert [tenant for tenant, _ in titulares.preguntas] == ["sunmeadow"]


async def test_en_ingles_propone_con_la_frase_en_ingles() -> None:
    nodo = _nodo(_Titulares(MARCO, ANA), extractor=_identidad("Marco Parker, policy Paul 201 17"))

    salida = await nodo.run(
        _estado(
            language="en",
            turn_text="Sure, my full name is Marco Parker and my policy is Paul 201 17.",
            spoken=True,
            completeness=_completitud("injuries"),
        )
    )

    _propone(salida, MARCO, language="en")
    assert salida.intake_response_text.startswith("I found policy POL-200117")


async def test_lo_oido_tambien_vale_si_el_extractor_no_lo_guardo_en_la_identidad() -> None:
    """El numero puede estar solo en lo que dijo la persona: se busca ahi tambien."""
    nodo = _nodo(_Titulares(MARCO, ANA), extractor=_identidad("Marco Parker"))

    salida = await nodo.run(
        _estado(turn_text=LLAMADA_REAL, spoken=True, completeness=_completitud("injuries"))
    )

    _propone(salida, MARCO)


async def test_un_numero_completo_que_no_existe_pero_se_parece_tambien_se_propone_en_la_llamada() -> (
    None
):
    """«200 118» por «200 117»: el reconocedor cambio una cifra."""
    nodo = _nodo(_Titulares(MARCO, ANA), extractor=_identidad("Marco Parker, póliza Paul 200 118"))

    salida = await nodo.run(
        _estado(
            turn_text="Soy Marco Parker y mi póliza es Paul 200 118",
            spoken=True,
            completeness=_completitud("injuries"),
        )
    )

    _propone(salida, MARCO)


# --- Nunca ata lo que la persona no confirmo ---------------------------------------------------


async def test_proponer_no_ata_y_el_si_de_la_persona_es_lo_unico_que_la_ata() -> None:
    nodo = _nodo(_Titulares(MARCO, ANA), extractor=_identidad("Marco Parker, póliza Paul 201 17"))
    propuesta = await nodo.run(
        _estado(turn_text=LLAMADA_REAL, spoken=True, completeness=_completitud("injuries"))
    )
    assert propuesta.intake_policy_confirmed is None
    pendiente = propuesta.intake_policy_match
    assert pendiente is not None

    asiente = await _nodo(None).run(
        _estado(
            turn_text="Sí, soy yo",
            spoken=True,
            awaiting_policy_confirmation=pendiente,
            completeness=_completitud("injuries"),
        )
    )

    assert asiente.intake_policy_confirmed == "POL-200117"
    escritos = {c.field_key: c.value for c in asiente.intake_extracted}
    assert "Marco Parker" in escritos["identity_and_policy"]
    assert "POL-200117" in escritos["identity_and_policy"]


async def test_si_la_persona_dice_que_no_es_ella_no_se_ata_nada() -> None:
    nodo = _nodo(None)

    salida = await nodo.run(
        _estado(
            turn_text="No, yo no soy",
            spoken=True,
            awaiting_policy_confirmation=MARCO,
            completeness=_completitud("injuries"),
        )
    )

    assert salida.intake_policy_confirmed is None
    assert salida.intake_policy_match is None


# --- No la encuentra: pide repetir cifra por cifra, una sola vez -----------------------------


async def test_sin_ninguna_poliza_con_ese_nombre_pide_repetirla_cifra_por_cifra() -> None:
    nodo = _nodo(
        _Titulares(MARCO, ANA), extractor=_identidad("Camila Restrepo Vélez, póliza Paul 201 17")
    )

    salida = await nodo.run(
        _estado(
            turn_text="Me llamo Camila Restrepo Vélez y mi póliza es Paul 201 17.",
            spoken=True,
            completeness=_completitud("injuries"),
        )
    )

    _pide_repetir(salida)
    assert "cifra por cifra" in salida.intake_response_text
    assert "póliza" in salida.intake_response_text
    # Lo dicho se conserva, como hoy: la repeticion no borra el nombre.
    assert [c.field_key for c in salida.intake_extracted] == ["identity_and_policy"]


async def test_con_mas_de_una_poliza_del_titular_no_adivina_cual_y_pide_repetir() -> None:
    nodo = _nodo(
        _Titulares(MARCO, MARCO_OTRA, ANA),
        extractor=_identidad("Marco Parker, póliza Paul 201 17"),
        corpus=(MARCO, MARCO_OTRA, ANA),
    )

    salida = await nodo.run(
        _estado(turn_text=LLAMADA_REAL, spoken=True, completeness=_completitud("injuries"))
    )

    _pide_repetir(salida)


@pytest.mark.parametrize(
    "dicho",
    [
        "Marco Parker, póliza Paul 301 17",  # no son una subsecuencia: 30117
        "Marco Parker, póliza Paul 201",  # faltan tres cifras
        "Marco Parker, póliza Paul 200 228",  # dos cifras distintas
    ],
)
async def test_cifras_que_no_se_parecen_no_proponen_la_poliza_del_titular(dicho: str) -> None:
    nodo = _nodo(_Titulares(MARCO, ANA), extractor=_identidad(dicho))

    salida = await nodo.run(
        _estado(turn_text=f"Soy {dicho}", spoken=True, completeness=_completitud("injuries"))
    )

    _pide_repetir(salida)


async def test_sin_el_nombre_completo_no_se_busca_por_nombre_y_se_pide_repetir() -> None:
    titulares = _Titulares(MARCO, ANA)
    nodo = _nodo(titulares, extractor=_identidad("póliza Paul 201 17"))

    salida = await nodo.run(
        _estado(
            turn_text="Mi póliza es Paul 201 17.",
            spoken=True,
            completeness=_completitud("injuries"),
        )
    )

    _pide_repetir(salida)
    # Un solo nombre de pila no nombra a nadie: ninguna poliza vuelve de la busqueda.
    assert all(
        policy.names_holder(texto, MARCO.holder_name) is False for _, texto in titulares.preguntas
    )


async def test_la_repeticion_se_pide_una_sola_vez() -> None:
    """Si tampoco sale, la conversacion sigue sin poliza identificada, como hoy."""
    nodo = _nodo(
        _Titulares(MARCO, ANA), extractor=_identidad("Camila Restrepo Vélez, póliza Paul 201 17")
    )

    salida = await nodo.run(
        _estado(
            turn_text="Camila Restrepo Vélez, mi póliza es Paul 201 17.",
            spoken=True,
            policy_repeat_asked=True,
            completeness=_completitud("injuries"),
        )
    )

    assert salida.intake_response_key != str(policy.POLICY_NOT_FOUND_REPEAT)
    assert salida.intake_policy_match is None
    assert salida.intake_policy_confirmed is None
    # Sigue la captura de siempre, con lo que toca despues de la identidad.
    assert salida.intake_next_block is Block.WHAT_HAPPENED
    assert [c.field_key for c in salida.intake_extracted] == ["identity_and_policy"]


async def test_la_repeticion_que_si_sale_se_propone_aunque_ya_se_haya_pedido() -> None:
    """Segundo intento: la persona repite y el numero ya existe."""
    nodo = _nodo(_Titulares(MARCO, ANA), extractor=_identidad("dos cero cero uno uno siete"))

    salida = await nodo.run(
        _estado(
            turn_text="dos cero cero uno uno siete",
            spoken=True,
            policy_repeat_asked=True,
            previous_block=Block.IDENTITY_AND_POLICY,
            completeness=_completitud("injuries", "identity_and_policy"),
        )
    )

    _propone(salida, MARCO)


async def test_la_repeticion_dicha_sola_llega_a_la_identidad_sin_pasar_por_el_modelo() -> None:
    """Con la identidad ya anotada, un numero suelto no se tomaba por la respuesta a otra
    pregunta: tras pedir que lo repita, es la identidad."""
    extractor = _Extractor()
    nodo = _nodo(_Titulares(MARCO, ANA), extractor=extractor)

    salida = await nodo.run(
        _estado(
            turn_text="dos cero cero uno uno siete",
            spoken=True,
            policy_repeat_asked=True,
            previous_block=Block.IDENTITY_AND_POLICY,
            completeness=_completitud("injuries", "identity_and_policy"),
        )
    )

    assert extractor.llamadas == 0
    _propone(salida, MARCO)


# --- Lo que no cambia ---------------------------------------------------------------------------


async def test_un_numero_completo_que_no_existe_en_el_chat_sigue_la_captura_de_siempre() -> None:
    """Escrito con todas las cifras, en el chat no se pide repetir: es la conducta de antes."""
    buscador = _Buscador(coincidencia=None)
    extractor = _identidad("POL-999999")
    nodo = IntakeNode(
        extract=extractor,
        instruction=_instruccion,
        clock=lambda: HOY,
        lookup=buscador,
        holder_lookup=_Titulares(MARCO),
    )

    salida = await nodo.run(_estado(turn_text="POL-999999", completeness=_completitud("injuries")))

    assert salida.intake_policy_match is None
    assert salida.intake_policy_repeat_asked is False
    assert salida.intake_next_block is Block.WHAT_HAPPENED


async def test_sin_numero_de_poliza_no_se_pide_nada_ni_se_busca_por_nombre() -> None:
    titulares = _Titulares(MARCO, ANA)
    nodo = _nodo(titulares, extractor=_identidad("Marco Parker"))

    salida = await nodo.run(
        _estado(
            turn_text="Hola, soy Marco Parker.",
            spoken=True,
            completeness=_completitud("injuries"),
        )
    )

    assert salida.intake_policy_match is None
    assert salida.intake_policy_repeat_asked is False
    assert titulares.preguntas == []


async def test_un_numero_exacto_se_confirma_como_siempre_sin_buscar_por_nombre() -> None:
    titulares = _Titulares(MARCO, ANA)
    nodo = _nodo(titulares, extractor=_identidad("POL-422088"))

    salida = await nodo.run(
        _estado(turn_text="mi póliza es POL-422088", completeness=_completitud("injuries"))
    )

    assert salida.intake_policy_match == ANA
    assert titulares.preguntas == []


async def test_sin_la_busqueda_por_nombre_cableada_se_pide_repetir_igual() -> None:
    nodo = _nodo(None, extractor=_identidad("Marco Parker, póliza Paul 201 17"))

    salida = await nodo.run(
        _estado(turn_text=LLAMADA_REAL, spoken=True, completeness=_completitud("injuries"))
    )

    _pide_repetir(salida)
