"""Las clases de entrada del historial, y por que la quinta existe.

`ChangeKind` justifica sus valores con una sola idea: una entrada que no
distingue lo que paso de lo que no paso no sirve de historial. La quinta clase
--`FIELD_VERSION_ALTERNATE`, que U11 escribe cuando alguien da una segunda
version de un campo ya confirmado-- nace de la revision de la tanda 2 de U11,
donde esa version se anotaba como `FIELD_SET`: la linea de tiempo del caso
mostraba el segundo valor como el vigente, justo lo contrario de lo que decide
FD-U11-7.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from untangle.case_record import crypto, history
from untangle.case_record.models import (
    Actor,
    ActorType,
    CaseChange,
    CaseField,
    ChangeKind,
    FieldStatus,
)

AHORA = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
ASEGURADO = Actor(actor_type=ActorType.INSURED)


@pytest.fixture
def cifrador(monkeypatch: pytest.MonkeyPatch) -> crypto.Cipher:
    monkeypatch.setenv(crypto.KEY_ENV_VAR, crypto.generate_key())
    return crypto.Cipher.from_settings()


def _campo(cifrador: crypto.Cipher, texto: str) -> CaseField:
    return CaseField(
        case_id="CASO-1",
        field_key="incident_datetime",
        value=cifrador.seal(texto),
        status=FieldStatus.STATED,
        evidence_turn_id="turno-4",
        updated_at=AHORA,
    )


def test_la_version_alterna_no_se_confunde_con_un_campo_que_cambio(
    cifrador: crypto.Cipher,
) -> None:
    """BR5.5 de U11: el valor del caso sigue siendo el primero confirmado."""
    campo = _campo(cifrador, "13 de marzo")

    alterna = history.field_version_alternate(campo, actor=ASEGURADO, channel=None)
    fijado = history.field_set(campo, previous=None, actor=ASEGURADO, channel=None)

    assert alterna.change_kind is ChangeKind.FIELD_VERSION_ALTERNATE
    assert fijado.change_kind is ChangeKind.FIELD_SET


def test_la_version_alterna_no_dice_que_hubo_un_valor_anterior(
    cifrador: crypto.Cipher,
) -> None:
    """No hubo cambio: el campo autoritativo no se toco."""
    alterna = history.field_version_alternate(
        _campo(cifrador, "13 de marzo"), actor=ASEGURADO, channel=None
    )

    assert alterna.previous_value is None
    assert alterna.new_value is not None


def test_la_version_alterna_nombra_su_campo(cifrador: crypto.Cipher) -> None:
    """Una version alterna sin campo no diria de que dato es."""
    alterna = history.field_version_alternate(
        _campo(cifrador, "13 de marzo"), actor=ASEGURADO, channel=None
    )
    assert alterna.field_key == "incident_datetime"

    with pytest.raises(ValueError, match="nombra el campo"):
        CaseChange(
            change_id="cambio-1",
            case_id="CASO-1",
            change_kind=ChangeKind.FIELD_VERSION_ALTERNATE,
            field_key=None,
            new_value=cifrador.seal("13 de marzo"),
            actor=ASEGURADO,
            changed_at=AHORA,
        )
