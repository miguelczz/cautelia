"""Los comandos de U2: emision de credenciales y las dos comprobaciones.

Lo que se prueba del comando de emision no es que firme --eso ya esta probado en
la pieza de identidad-- sino **donde escribe**: a la salida estandar y a ningun
archivo. Una credencial en un archivo del repositorio es una credencial
publicada, y de ahi no se vuelve borrandola (BR2.6, D23).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from untangle.tenancy import cli, ephemeral, rls_assertion, staff_identity, visitor_access
from untangle.tenancy.models import ConnectionRole, RlsReport, TableIsolation

CLAVE = "clave-de-prueba-de-la-bandeja-para-la-firma-hs256"

#: Un token con la forma real --secreto, punto, firma-- y **sin nada detras**, para la
#: prueba del comando del enlace: lo que se mide es donde acaba en la direccion.
#:
#: La supresion lleva su razon al lado, como exige la practica del equipo: el linter ve
#: un nombre que dice "token" con una cadena pegada y avisa, y hace bien. Aqui no hay
#: secreto: no existe la clave que lo firmaria, el comando real esta doblado en esta
#: misma prueba, y la emision de verdad se prueba en la pieza de acceso de U2.
TOKEN_DE_MENTIRA = "el-secreto-de-mentira.la-firma-de-mentira"  # noqa: S105


def test_emitir_una_credencial_la_escribe_en_la_salida_estandar(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("UNTANGLE_STAFF_CREDENTIAL_SIGNING_KEY", CLAVE)

    codigo = cli.main(["issue-credential", "--tenant", "stonecroft", "--principal", "diana"])

    salida = capsys.readouterr()
    token = salida.out.strip()
    assert codigo == 0
    # El token, solo, en la salida estandar: asi se puede canalizar sin arrastrar
    # explicaciones. Todo lo demas va por la salida de error.
    assert token.count(".") == 2
    assert "horas" in salida.err
    assert "comprometida" in salida.err

    credencial = staff_identity.verify_credential(
        token, expected_tenant="stonecroft", signing_key=CLAVE
    )
    assert credencial.principal_id == "diana"


def test_el_comando_de_emision_no_admite_escribir_a_un_archivo() -> None:
    """La ausencia de la opcion es el control. Con ella, alguien la usaria."""
    ayuda = cli._parser().format_help()

    assert "--out" not in ayuda
    assert "--file" not in ayuda
    assert "--output" not in ayuda


def test_ningun_archivo_del_repositorio_cambia_al_emitir(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Se comprueba lo que de verdad importa: que no deja nada escrito."""
    monkeypatch.setenv("UNTANGLE_STAFF_CREDENTIAL_SIGNING_KEY", CLAVE)
    monkeypatch.chdir(tmp_path)

    cli.main(["issue-credential", "--tenant", "knotwell", "--principal", "priya-raman"])
    capsys.readouterr()

    assert list(tmp_path.iterdir()) == []


def test_emitir_sin_clave_falla_nombrando_la_variable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("UNTANGLE_STAFF_CREDENTIAL_SIGNING_KEY", raising=False)

    codigo = cli.main(["issue-credential", "--tenant", "stonecroft", "--principal", "diana"])

    assert codigo == 1
    assert "UNTANGLE_STAFF_CREDENTIAL_SIGNING_KEY" in capsys.readouterr().err


def test_emitir_para_una_persona_que_no_existe_falla_nombrandola(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("UNTANGLE_STAFF_CREDENTIAL_SIGNING_KEY", CLAVE)

    codigo = cli.main(["issue-credential", "--tenant", "stonecroft", "--principal", "nadie"])

    assert codigo == 1
    assert "nadie" in capsys.readouterr().err


def test_rls_check_contra_la_base_declarada_termina_en_verde(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Con `UNTANGLE_DATABASE_URL` puesta, pregunta a **esa** base."""
    monkeypatch.setenv("UNTANGLE_DATABASE_URL", sesiones.app_url)

    codigo = cli.main(["rls-check"])

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "case_access_link" in salida
    assert "visitor_key" in salida
    # La exclusion se imprime con su razon aunque todo este en verde: una
    # exclusion que solo se ve cuando algo falla es una exclusion que nadie
    # revisa.
    assert "alembic_version" in salida
    assert "no guarda datos del aplicativo" in salida
    assert "puede saltarse las politicas: no" in salida


def test_rls_check_devuelve_distinto_de_cero_cuando_falta_una_politica(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """La compuerta se pone roja y el mensaje nombra la tabla y que le falta."""
    monkeypatch.setenv("UNTANGLE_DATABASE_URL", sesiones.app_url)

    async def sin_politica(root: Path | None = None) -> RlsReport:
        return rls_assertion.evaluate(
            [
                TableIsolation(
                    table="tabla_nueva",
                    row_security=False,
                    force_row_security=False,
                    tenant_policies=0,
                )
            ],
            ConnectionRole(name="untangle_app", bypass_rls=False, superuser=False),
            [],
        )

    monkeypatch.setattr(rls_assertion, "assert_rls_complete", sin_politica)

    codigo = cli.main(["rls-check"])

    assert codigo == 1
    error = capsys.readouterr().err
    assert "tabla_nueva" in error
    assert "politica de aseguradora" in error


def test_migrate_check_sube_baja_y_vuelve_a_subir(capsys: pytest.CaptureFixture[str]) -> None:
    """SEC-U2.12, BR1.11: una base virgen, propia de este comando."""
    codigo = cli.main(["migrate-check"])

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "cabeza unica: " in salida
    assert "bajada      ok" in salida
    assert "resubida    ok" in salida


# --- El enlace de un caso: donde escribe, y donde va el token -----------------


def test_emitir_un_enlace_lo_escribe_con_el_token_en_el_fragmento(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C-07 y BR5.6: el token va en el fragmento, nunca en la ruta.

    La direccion se imprime **entera** y no solo el token, y es a proposito: armarla a
    mano es exactamente el paso donde alguien lo pone en la ruta, y desde ahi el token
    queda en la barra, en la cabecera de procedencia y en cada registro que lo vea
    pasar, durante la hora que vale.
    """
    monkeypatch.setenv("UNTANGLE_CASE_LINK_SIGNING_KEY", CLAVE)
    emitidos: list[dict[str, object]] = []

    async def emitir(**kwargs: object) -> object:
        emitidos.append(kwargs)
        # El token de mentira lleva la forma real --secreto, punto, firma-- porque lo
        # que se mide es donde acaba en la direccion. No abre nada: detras no hay
        # clave, y la emision de verdad esta probada en la pieza de acceso de U2.
        return SimpleNamespace(token=TOKEN_DE_MENTIRA)

    # Se parchea el modulo importado y no `cli.visitor_access`: es el mismo objeto, y
    # el comprobador de tipos exige que un atributo se lea de donde se exporta.
    monkeypatch.setattr(visitor_access, "issue_case_link", emitir)

    codigo = cli.main(["issue-case-link", "--tenant", "stonecroft", "--case", "CASE-1"])

    salida = capsys.readouterr()
    assert codigo == 0
    assert salida.out.strip() == f"/c#{TOKEN_DE_MENTIRA}"
    # El token **despues** del `#` y en ningun otro sitio de la direccion.
    ruta, _, fragmento = salida.out.strip().partition("#")
    assert TOKEN_DE_MENTIRA not in ruta
    assert fragmento == TOKEN_DE_MENTIRA
    assert emitidos == [{"tenant_id": "stonecroft", "case_id": "CASE-1", "signing_key": CLAVE}]


def test_el_comando_del_enlace_no_admite_escribir_a_un_archivo() -> None:
    """Igual que el de la credencial: el token se emite una sola vez, y de la fila
    queda solo su resumen, asi que un archivo con el token dentro seria el unico sitio
    donde vive y a la vez el sitio donde no debe estar."""
    with pytest.raises(SystemExit):
        cli.main(["issue-case-link", "--tenant", "stonecroft", "--case", "C", "--out", "f"])


def test_emitir_un_enlace_sin_clave_falla_nombrando_la_variable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("UNTANGLE_CASE_LINK_SIGNING_KEY", raising=False)

    codigo = cli.main(["issue-case-link", "--tenant", "stonecroft", "--case", "CASE-1"])

    assert codigo == 1
    assert "UNTANGLE_CASE_LINK_SIGNING_KEY" in capsys.readouterr().err
