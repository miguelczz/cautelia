"""Lo que se guarda de cada turno, sin base: se sustituye la escritura (2026-10-10).

La regla del proyecto es tapar los datos personales **antes de guardar**. Lo que dice
la agente la incumplia cuando salia de una frase del catalogo con datos dentro: se
guardaba tal cual.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest

from untangle import paths
from untangle.case_record import api as casos
from untangle.case_record.models import Channel
from untangle.compliance.redaction import api as redaccion
from untangle.orchestration import transcript_writer
from untangle.orchestration.transcript_writer import TranscriptScope

pytestmark = pytest.mark.anyio

AMBITO = TranscriptScope(
    tenant_id="stonecroft", case_id="case-1", channel=Channel.CHAT, language="es"
)
AHORA = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
RESPUESTA = (
    "Encontré la póliza POL-100042 a nombre de Natalia Henao Rendón, "
    "con un Renault Logan 2024. ¿Eres tú y conducías ese carro?"
)


@pytest.fixture
def guardados(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    textos: list[str] = []

    async def anotar(tenant_id: str, borrador: Any, texto: Any) -> str:
        textos.append(str(texto))
        return str(borrador.turn_id)

    monkeypatch.setattr(casos, "append_turn", anotar)
    redaccion.allow_own_vocabulary(
        [
            "Encontré la póliza {policy} a nombre de {holder}, con un {vehicle}. ¿Eres tú y conducías ese carro?"
        ]
    )
    redaccion.allow_public_terms(["Renault Logan"])
    yield textos
    redaccion.allow_own_vocabulary([])
    redaccion.allow_public_terms([])


@pytest.mark.parametrize("del_catalogo", [True, False])
async def test_lo_que_dice_la_agente_se_guarda_sin_la_poliza_ni_el_nombre(
    guardados: list[str], del_catalogo: bool
) -> None:
    """Venga del catalogo o de una reescritura del modelo: una sola puerta."""
    await transcript_writer.record_agent_turn(
        AMBITO, text=RESPUESTA, now=AHORA, from_catalog=del_catalogo
    )

    (guardado,) = guardados
    assert "POL-100042" not in guardado
    assert "Natalia" not in guardado
    # Y la frase sigue siendo legible para quien revisa el caso.
    assert guardado.startswith("Encontré la póliza [PÓLIZA 1] a nombre de [NOMBRE 1]")


async def test_lo_que_dijo_la_persona_se_sigue_tapando_entero(guardados: list[str]) -> None:
    await transcript_writer.record_person_turn(
        AMBITO, text="Soy Natalia Henao Rendón, mi póliza es POL-100042", now=AHORA
    )

    (guardado,) = guardados
    assert "Natalia" not in guardado
    assert "POL-100042" not in guardado


# --- Todo texto que se publica se guarda (2026-10-12) -----------------------------
#
# La pantalla mostro dos textos de la agente en un turno y la base guardo uno: el de
# «que quieres saber» salio por el aviso de fondo, que publicaba sin guardar. La regla
# queda en un solo camino, `say_without_turn`, y en un chequeo de que no hay otro.


class _Oyente:
    """El doble del canal: anota el orden en que pasan las cosas."""

    def __init__(self, orden: list[str], *, falla: bool = False) -> None:
        self._orden = orden
        self._falla = falla

    async def notify(  # noqa: PLR0913 -- la firma del puerto CaseNotifier
        self,
        tenant_id: str,
        case_id: str,
        *,
        text: str,
        citations: tuple[object, ...] = (),
        suggestions: tuple[str, ...] = (),
        coverage_outcome: str | None = None,
        language: str | None = None,
    ) -> bool:
        del tenant_id, case_id, citations, suggestions, coverage_outcome, language
        self._orden.append(f"publicado:{text}")
        if self._falla:
            msg = "el canal se cayo"
            raise RuntimeError(msg)
        return True


async def test_lo_que_se_publica_sin_turno_se_guarda_antes_de_publicarse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orden: list[str] = []

    async def anotar(tenant_id: str, borrador: Any, texto: Any) -> str:
        orden.append(f"guardado:{texto}")
        return str(borrador.turn_id)

    monkeypatch.setattr(casos, "append_turn", anotar)

    entregado = await transcript_writer.say_without_turn(
        _Oyente(orden), AMBITO, text="¿Qué quieres saber de tu póliza?", now=AHORA
    )

    assert entregado is True
    assert orden == [
        "guardado:¿Qué quieres saber de tu póliza?",
        "publicado:¿Qué quieres saber de tu póliza?",
    ]


async def test_si_el_canal_falla_el_texto_ya_esta_guardado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guardar primero es lo que hace que quien nunca lo vio lo encuentre al volver."""
    orden: list[str] = []

    async def anotar(tenant_id: str, borrador: Any, texto: Any) -> str:
        orden.append(f"guardado:{texto}")
        return str(borrador.turn_id)

    monkeypatch.setattr(casos, "append_turn", anotar)

    with pytest.raises(RuntimeError):
        await transcript_writer.say_without_turn(
            _Oyente(orden, falla=True), AMBITO, text="Listo.", now=AHORA
        )

    assert orden[0] == "guardado:Listo."


#: Quien implementa el puerto reparte la llamada a otro canal y no es un llamador.
_LLAMADA_AL_PUERTO = re.compile(r"\b(?:notifier|CASE_NOTIFIER)\.notify\(")


def test_ninguna_llamada_al_aviso_de_fondo_se_salta_el_guardado() -> None:
    """La unica llamada al puerto `CaseNotifier` esta dentro de `say_without_turn`.

    Una llamada suelta publicaria un texto que la transcripcion no tiene, y la pantalla
    mostraria al volver menos de lo que mostro. El chequeo es un grep porque la regla
    cruza modulos: el que publica no sabe quien guarda."""
    raiz = paths.repo_root() / "app" / "backend" / "src" / "untangle"
    llamadores = sorted(
        str(archivo.relative_to(raiz))
        for archivo in raiz.rglob("*.py")
        if _LLAMADA_AL_PUERTO.search(archivo.read_text(encoding="utf-8"))
    )

    assert llamadores == ["orchestration/transcript_writer.py"]
