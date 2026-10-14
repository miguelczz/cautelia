"""Lo que se dice de una decision al volver a llamar (BR6.5, AC1.27.5)."""

from __future__ import annotations

import pytest

from untangle.base import Locale
from untangle.case_record.models import Resolution
from untangle.voice import notice

pytestmark = pytest.mark.usefixtures("catalogo_cargado")

IDIOMAS: tuple[Locale, ...] = ("en", "es")


@pytest.mark.parametrize("language", IDIOMAS)
@pytest.mark.parametrize(
    ("resolution", "clave"),
    [
        (Resolution.APPROVED, notice.APPROVED),
        (Resolution.REJECTED, notice.REJECTED),
        (Resolution.SENT_TO_INSURER, notice.SENT_TO_INSURER),
    ],
)
def test_cada_desenlace_tiene_su_frase(
    resolution: Resolution, clave: object, language: Locale
) -> None:
    dicho = notice.resolved(resolution, case_number="SUN482913", comment="", language=language)
    assert dicho.copy_key == clave
    assert "SUN482913" in dicho.text


@pytest.mark.parametrize("language", IDIOMAS)
def test_el_comentario_se_dice_solo_si_lo_hay(language: Locale) -> None:
    """Con el comentario dentro de la frase, una decision sin nota diria 'su
    comentario fue.' y sonaria a frase cortada."""
    sin = notice.resolved(
        Resolution.APPROVED, case_number="SUN482913", comment="  ", language=language
    )
    con = notice.resolved(
        Resolution.APPROVED,
        case_number="SUN482913",
        comment="Covered under the collision section.",
        language=language,
    )
    assert "Covered under the collision section." in con.text
    assert con.text.startswith(sin.text)
    assert len(con.text) > len(sin.text)


@pytest.mark.parametrize("language", IDIOMAS)
def test_un_caso_sin_decidir_no_inventa_un_resultado(language: Locale) -> None:
    """`REGISTERED` es lo que el sistema pone al abrir el caso; decirla seria
    decir que alguien decidio algo que nadie decidio."""
    dicho = notice.resolved(
        Resolution.REGISTERED, case_number="SUN482913", comment="x", language=language
    )
    assert dicho.copy_key == notice.PENDING


@pytest.mark.parametrize("language", IDIOMAS)
def test_lo_pendiente_no_promete_un_plazo(language: Locale) -> None:
    """La guia de voz prohibe especular sobre tiempos y la demo no garantiza
    ninguno."""
    texto = notice.pending(language=language).text.lower()
    for prohibida in ("today", "hoy", "tomorrow", "mañana", "hours", "horas"):
        assert prohibida not in texto
