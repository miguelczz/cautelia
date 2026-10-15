"""La base va por delante del codigo: una vuelta atras, no una migracion rota (2026-10-15).

La prueba de la vuelta atras del 15 de octubre dejo el sitio dos minutos en error: la
version anterior, al arrancar, no encontraba en su historia la migracion que la nueva
habia subido. Lo que se prueba aqui es la pieza que distingue ese caso de cualquier otro
fallo de alembic, sobre la historia de migraciones real y sin base de datos.
"""

from __future__ import annotations

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.script.revision import RangeNotAncestorError, ResolutionError
from alembic.util import CommandError

from untangle.tenancy import ephemeral


def _configuracion() -> Config:
    return ephemeral.alembic_config("postgresql+psycopg://sin-uso")


def _fallo(causa: BaseException) -> CommandError:
    error = CommandError("alembic no pudo subir")
    error.__cause__ = causa
    return error


def test_una_revision_que_esta_historia_no_tiene_es_la_base_por_delante() -> None:
    error = _fallo(ResolutionError("no la encuentro", "f00dfeedbeef"))

    assert ephemeral.unknown_revision(error, _configuracion()) == "f00dfeedbeef"


def test_una_revision_conocida_no_es_la_base_por_delante() -> None:
    configuracion = _configuracion()
    conocida = ScriptDirectory.from_config(configuracion).get_current_head()
    assert conocida is not None

    error = _fallo(ResolutionError("otra cosa", conocida))

    assert ephemeral.unknown_revision(error, configuracion) is None


def test_otro_fallo_de_alembic_no_se_confunde_con_una_vuelta_atras() -> None:
    error = _fallo(RangeNotAncestorError("a", "b"))

    assert ephemeral.unknown_revision(error, _configuracion()) is None
    assert ephemeral.unknown_revision(CommandError("sin causa"), _configuracion()) is None


def test_el_error_nombra_la_revision_y_dice_que_es_de_una_version_mas_nueva() -> None:
    error = ephemeral.DatabaseAheadError("f00dfeedbeef")

    assert error.revision == "f00dfeedbeef"
    assert "f00dfeedbeef" in str(error)
    assert "mas nueva" in str(error)
