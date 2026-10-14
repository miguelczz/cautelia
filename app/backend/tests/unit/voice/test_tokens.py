"""El token que ata un socket a una llamada (BR1.4, BR1.5)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from untangle.tenancy.visitor_access import LinkSigningKeyMissingError
from untangle.voice import tokens

CLAVE = "x" * 32
OTRA_CLAVE = "y" * 32
AHORA = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
LLAMADA = "call-0123456789abcdef"


def _emitir(call_id: str = LLAMADA, *, clave: str = CLAVE) -> str:
    return tokens.issue(call_id, signing_key=clave, now=AHORA)


def test_un_token_recien_emitido_abre_su_llamada() -> None:
    veredicto = tokens.verify(_emitir(), call_id=LLAMADA, signing_key=CLAVE, now=AHORA)
    assert veredicto.accepted
    assert veredicto.rejection is None


@pytest.mark.parametrize(
    ("token", "motivo"),
    [
        (None, tokens.TokenRejection.MISSING),
        ("", tokens.TokenRejection.MISSING),
    ],
)
def test_sin_token_no_se_abre(token: str | None, motivo: tokens.TokenRejection) -> None:
    veredicto = tokens.verify(token, call_id=LLAMADA, signing_key=CLAVE, now=AHORA)
    assert not veredicto.accepted
    assert veredicto.rejection is motivo


def test_un_token_vencido_no_abre() -> None:
    despues = AHORA + tokens.TOKEN_LIFETIME + timedelta(seconds=1)
    veredicto = tokens.verify(_emitir(), call_id=LLAMADA, signing_key=CLAVE, now=despues)
    assert not veredicto.accepted
    assert veredicto.rejection is tokens.TokenRejection.EXPIRED


def test_el_token_de_otra_llamada_no_abre_esta() -> None:
    veredicto = tokens.verify(
        _emitir("call-ffffffffffffffff"), call_id=LLAMADA, signing_key=CLAVE, now=AHORA
    )
    assert not veredicto.accepted
    assert veredicto.rejection is tokens.TokenRejection.OTHER_CALL


def test_un_token_alterado_no_abre() -> None:
    crudo = _emitir()
    alterado = crudo[:-1] + ("A" if crudo[-1] != "A" else "B")
    veredicto = tokens.verify(alterado, call_id=LLAMADA, signing_key=CLAVE, now=AHORA)
    assert not veredicto.accepted
    assert veredicto.rejection is tokens.TokenRejection.TAMPERED


def test_un_token_de_otra_clave_no_abre() -> None:
    veredicto = tokens.verify(
        _emitir(clave=OTRA_CLAVE), call_id=LLAMADA, signing_key=CLAVE, now=AHORA
    )
    assert not veredicto.accepted
    assert veredicto.rejection is tokens.TokenRejection.TAMPERED


def test_un_token_con_forma_rota_no_abre() -> None:
    veredicto = tokens.verify("sin-puntos", call_id=LLAMADA, signing_key=CLAVE, now=AHORA)
    assert not veredicto.accepted
    assert veredicto.rejection is tokens.TokenRejection.TAMPERED


def test_las_cuatro_formas_de_token_malo_responden_igual_hacia_afuera() -> None:
    """BR1.5: distinguirlas le diria a quien prueba cual acerto a medias.

    Lo unico que sale del servidor es `accepted`, y en las cuatro es `False`. El
    motivo se distingue **por dentro**, para la traza, y por eso los cuatro son
    distintos entre si: si el modulo devolviera un solo motivo, la traza no
    podria separar un token alterado de uno vencido, que son incidentes
    distintos.
    """
    despues = AHORA + tokens.TOKEN_LIFETIME + timedelta(seconds=1)
    crudo = _emitir()
    veredictos = [
        tokens.verify(None, call_id=LLAMADA, signing_key=CLAVE, now=AHORA),
        tokens.verify(crudo, call_id=LLAMADA, signing_key=CLAVE, now=despues),
        tokens.verify(
            _emitir("call-ffffffffffffffff"), call_id=LLAMADA, signing_key=CLAVE, now=AHORA
        ),
        tokens.verify(crudo[:-1] + "A", call_id=LLAMADA, signing_key=CLAVE, now=AHORA),
    ]
    assert [v.accepted for v in veredictos] == [False, False, False, False]
    assert len({v.rejection for v in veredictos}) == len(veredictos)


def test_sin_clave_falla_en_el_acto_y_no_acepta_en_silencio() -> None:
    with pytest.raises(LinkSigningKeyMissingError):
        tokens.issue(LLAMADA, signing_key=None, now=AHORA)


def test_una_clave_corta_no_se_acepta() -> None:
    with pytest.raises(LinkSigningKeyMissingError):
        tokens.issue(LLAMADA, signing_key="corta", now=AHORA)


def test_el_token_no_lleva_la_clave_ni_el_navegador() -> None:
    """Lo que viaja dice *que llamada*, no quien es el visitante (BR1.4)."""
    crudo = _emitir()
    assert CLAVE not in crudo
    assert crudo.startswith(f"{LLAMADA}.")
