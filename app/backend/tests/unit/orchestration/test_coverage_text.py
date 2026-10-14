"""La respuesta de cobertura en el chat: tres frases, la parte en el idioma de la
conversacion y nada de relleno (2026-10-08, visto en produccion con Autos Poblado)."""

from __future__ import annotations

from dataclasses import dataclass

from untangle.copy_catalog import api as copy_api
from untangle.orchestration import turn


@dataclass(frozen=True)
class _Cita:
    clause_id: str
    part: str
    amount_deferred: bool = False


@dataclass(frozen=True)
class _Salida:
    citations: tuple[_Cita, ...]
    outcome: str = "verified"
    cross_language_notice: str | None = "La cláusula está escrita en inglés."
    response_text: str | None = None


def test_la_condicion_especial_manda_y_la_parte_sale_en_espanol() -> None:
    copy_api.install(copy_api.load())
    salida = _Salida(
        citations=(
            _Cita("SUN-PAP-2026-END-2-D.EXCL.5", "Endorsements", amount_deferred=True),
            _Cita("SUN-PAP-2026-D.EXCL.5", "Part D — Coverage for Damage to Your Auto"),
        )
    )

    texto = turn._texto_de_cobertura(salida, language="es")

    assert "una condición especial" in texto
    assert "Endorsements" not in texto
    assert "inglés" not in texto, "el aviso del idioma lo da la tarjeta de la cláusula"
    assert texto.count("ajustador") == 1


def test_una_parte_de_la_poliza_se_nombra_por_su_letra() -> None:
    copy_api.install(copy_api.load())
    salida = _Salida(citations=(_Cita("STO-PAP-2026-D.INS.OTC", "Parte D — Daños a su vehículo"),))

    assert "la Parte D, daños al vehículo" in turn._texto_de_cobertura(salida, language="es")
    assert "Part D, damage to your auto" in turn._texto_de_cobertura(salida, language="en")


@dataclass(frozen=True)
class _CitaConExplicacion:
    clause_id: str
    part: str
    claim: str
    amount_deferred: bool = False


def test_con_la_explicacion_de_la_ia_la_respuesta_dice_que_trata_la_clausula() -> None:
    copy_api.install(copy_api.load())
    salida = _Salida(
        citations=(
            _CitaConExplicacion(  # type: ignore[arg-type]
                "SUN-PAP-2026-END-2-D.EXCL.5",
                "Endorsements",
                "La exclusión de llantas no aplica a daños por un hueco en la vía",
            ),
        )
    )

    texto = turn._texto_con_explicacion(salida, language="es")

    assert texto is not None
    assert "una condición especial: La exclusión de llantas no aplica" in texto
    assert texto.count("ajustador") == 1


def test_sin_explicacion_no_hay_version_explicada() -> None:
    copy_api.install(copy_api.load())
    salida = _Salida(citations=(_Cita("STO-PAP-2026-D.INS.OTC", "Parte D"),))

    assert turn._texto_con_explicacion(salida, language="es") is None
