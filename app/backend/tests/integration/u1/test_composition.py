"""Pruebas de integracion de la raiz de composicion (C-24).

Son de integracion porque montan la aplicacion entera y la llaman por HTTP con
el cliente de prueba: lo que se comprueba es que las piezas encajen, no que cada
funcion devuelva lo suyo.

Ninguna necesita red, base de datos ni credenciales.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from untangle.copy_catalog import api as copy_api
from untangle.server import composition
from untangle.settings import Settings


@pytest.fixture(autouse=True)
def catalogo_limpio() -> Iterator[None]:
    yield
    copy_api.reset()


def test_la_aplicacion_arranca_y_responde_su_salud(tmp_path: Path) -> None:
    """La salud de C-02, que reemplaza al `/health` de U1 (CG-U6-8, FD-U6-6).

    Sin base --este camino no la tiene--, el proceso esta **vivo** y **no
    listo**: vivo responde 200 y listo 503 con la forma de C-01. Los dos
    indicadores de U5 --la tabla de precios cargada y que usos tienen clave--
    ya no viven en una ruta propia: viajan en `checks.providers` de listo cuando
    el proceso lo esta, y ahi los comprueba la prueba de integracion de U6, que
    tiene base.
    """
    app = composition.build_app(Settings(env="local", traces_endpoint=None), dist_dir=tmp_path)

    with TestClient(app) as cliente:
        vivo = cliente.get("/api/health/live")
        listo = cliente.get("/api/health/ready")

    assert vivo.status_code == 200
    assert vivo.json() == {"status": "live"}
    # Valores tecnicos: la etiqueta que lee una persona la resuelve el catalogo,
    # nunca se imprime el valor del enum.
    assert listo.status_code == 503
    assert listo.headers["content-type"].startswith("application/problem+json")
    assert listo.json()["code"] == "provider_unavailable"


def test_el_health_de_u1_ya_no_existe(tmp_path: Path) -> None:
    """Una sola salud, con la forma del contrato: la ruta vieja no responde su JSON."""
    app = composition.build_app(Settings(env="local", traces_endpoint=None), dist_dir=tmp_path)

    with TestClient(app) as cliente:
        vieja = cliente.get("/health")

    assert "priced_units" not in vieja.text
    assert "provider_uses_with_key" not in vieja.text


def test_un_modulo_declarado_sin_su_funcion_falla_al_arrancar_nombrandolo() -> None:
    declarado = composition.ModuleSpec(
        module="untangle.inbox",
        provides=frozenset({"router"}),
    )

    with pytest.raises(composition.ModuleContractError) as excinfo:
        composition.build_app(Settings(), modules=(declarado,))

    mensaje = str(excinfo.value)
    assert "untangle.inbox" in mensaje
    assert "router()" in mensaje


def test_un_modulo_declarado_que_no_existe_falla_al_arrancar_nombrandolo() -> None:
    declarado = composition.ModuleSpec(
        module="untangle.no_existe",
        provides=frozenset({"router"}),
    )

    with pytest.raises(composition.ModuleContractError) as excinfo:
        composition.build_app(Settings(), modules=(declarado,))

    assert "untangle.no_existe" in str(excinfo.value)


def test_el_detector_de_datos_personales_se_carga_al_arrancar(tmp_path: Path) -> None:
    """La carga de los modelos tarda segundos y bloquea a quien la dispara. Si se
    hace al primer uso, en una llamada de voz cae en el primer transcrito y
    congela el turno: medido en produccion el 2026-10-07, siete segundos sin oir
    nada. Se carga antes de aceptar conexiones."""
    from untangle.compliance.redaction import detector as deteccion

    deteccion.reset()
    app = composition.build_app(Settings(env="local", traces_endpoint=None), dist_dir=tmp_path)
    assert deteccion._detector is None

    with TestClient(app):
        cargado = deteccion._detector

    assert cargado is not None
