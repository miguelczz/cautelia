"""Lo unico que se comprueba de lo que el modelo contesta (2026-10-12).

Dos comprobaciones que cuidan a la persona --sin enlaces ni correos, sin el nombre de la agente
si nadie lo pregunto-- mas lo que hace falta para que haya un texto que mandar. El estilo no se
vigila aqui: lo miden las evaluaciones. Sin modelo y sin red.
"""

from __future__ import annotations

import io
import json
import sys
from collections.abc import Iterator

import pytest

from untangle import observability
from untangle.orchestration import model_reply
from untangle.orchestration.model_reply import FallbackReason, usable_reply
from untangle.tenancy import api as tenancy

_BASE = "¿Cuándo ocurrió el accidente?"


@pytest.fixture
def eventos() -> Iterator[io.StringIO]:
    destino = io.StringIO()
    observability.set_stream(destino)
    yield destino
    observability.set_stream(sys.stdout)


@pytest.fixture(autouse=True)
def aseguradoras() -> None:
    tenancy.install(tenancy.load())


@pytest.mark.parametrize("vacia", [None, "", "   ", "\n\t"])
def test_una_respuesta_vacia_no_vale(vacia: str | None) -> None:
    assert usable_reply(vacia, base=_BASE, agent_name=None) is None


def test_una_respuesta_normal_sale_sin_los_espacios_de_los_bordes() -> None:
    assert (
        usable_reply("  Qué susto. ¿Cuándo fue?\n", base=_BASE, agent_name=None)
        == "Qué susto. ¿Cuándo fue?"
    )


def test_el_largo_maximo_es_de_600_caracteres_y_un_caracter_mas_no_vale() -> None:
    cabe = "a" * model_reply.MAX_REPLY_CHARS
    pasa = "a" * (model_reply.MAX_REPLY_CHARS + 1)

    assert usable_reply(cabe, base=_BASE, agent_name=None) == cabe
    assert usable_reply(pasa, base=_BASE, agent_name=None) is None


@pytest.mark.parametrize(
    "texto",
    [
        "Mira https://untangle.example/caso para verlo.",
        "Entra a www.aseguradora.com y ahí lo ves.",
        "Escríbenos a ayuda@aseguradora.com cuando quieras.",
        "Contáctanos por @aseguradora",
        "Mira HTTP://EJEMPLO.COM",
    ],
)
def test_un_enlace_o_un_correo_no_valen_ni_aunque_la_frase_base_los_traiga(texto: str) -> None:
    """Los de verdad los pone el codigo; uno escrito por el modelo es inventado."""
    assert usable_reply(texto, base=_BASE, agent_name=None) is None
    assert usable_reply(texto, base=texto, agent_name=None) is None


def test_la_arroba_suelta_no_es_un_correo() -> None:
    assert usable_reply("Dime a las 3 @ la salida", base=_BASE, agent_name=None) is not None


@pytest.mark.parametrize("nombre", ["Valeria", "valeria", "VALERIA"])
def test_decir_el_nombre_de_la_agente_sin_que_la_frase_base_lo_traiga_no_vale(nombre: str) -> None:
    assert usable_reply(f"Hola, soy {nombre}. {_BASE}", base=_BASE, agent_name="Valeria") is None


def test_si_la_frase_base_trae_el_nombre_la_respuesta_puede_decirlo() -> None:
    base = "Hola, soy Valeria, una asistente de inteligencia artificial."

    assert usable_reply("Soy Valeria, una IA.", base=base, agent_name="Valeria") is not None


def test_sin_nombre_de_agente_no_se_comprueba_y_otra_palabra_no_cuenta() -> None:
    # «Valerian» no es «Valeria»: se compara la palabra entera.
    assert usable_reply("Hola, soy Valeria. " + _BASE, base=_BASE, agent_name=None) is not None
    assert usable_reply("Gracias, Valerian. " + _BASE, base=_BASE, agent_name="Valeria") is not None


def test_el_nombre_de_la_agente_sale_de_la_aseguradora_o_del_catalogo() -> None:
    nombre = model_reply.agent_name_of("sunmeadow", "es")

    assert nombre
    assert model_reply.agent_name_of("sunmeadow", "en")


def test_los_motivos_son_la_lista_cerrada_de_la_traza() -> None:
    assert {motivo.value for motivo in FallbackReason} == {
        "milestone",
        "no_model",
        "opening_turn",
        "wrong_language",
        "items_rejected",
        "invalid_reply",
        "report_not_done",
        "guard",
        "redacted_voice",
    }


def test_el_evento_dice_que_texto_salio_y_por_que_sin_llevar_el_texto(
    eventos: io.StringIO,
) -> None:
    model_reply.record_outcome("sunmeadow", "chat", None)
    model_reply.record_outcome("sunmeadow", "voice", FallbackReason.REDACTED_VOICE)

    lineas = eventos.getvalue().splitlines()
    assert '"event": "chat.reply_model"' in lineas[0]
    assert '"channel": "chat"' in lineas[0]
    assert '"event": "chat.reply_fallback"' in lineas[1]
    assert '"reason": "redacted_voice"' in lineas[1]
    assert '"channel": "voice"' in lineas[1]
    assert not {"text", "reply"} & json.loads(lineas[1]).keys()
