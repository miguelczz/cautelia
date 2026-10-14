"""El ejemplo real de `GET /api/site` que usan las pruebas del inicio (U6)."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

from untangle import paths
from untangle.server import composition, openapi_export
from untangle.surface_spec import SurfaceId, SurfaceSpec
from untangle.tenancy import api as tenancy


def _superficies_de(spec: composition.ModuleSpec) -> tuple[SurfaceSpec, ...]:
    """Las superficies que declara un modulo, sin montar la aplicacion entera."""
    if "surfaces" not in spec.provides:
        return ()
    modulo = importlib.import_module(spec.module)
    return tuple(modulo.surfaces())


def test_el_ejemplo_es_el_directorio_de_la_configuracion_versionada_sin_enlaces() -> None:
    ejemplo = json.loads(openapi_export.render_site_example())

    configuradas = tenancy.load().available
    assert [a["tenant_id"] for a in ejemplo["tenants"]] == [a.tenant_id for a in configuradas]
    assert ejemplo["links"] == {}
    # Las superficies montadas, y no una lista escrita a mano: U13 monto la
    # primera el 2026-09-28 y las que vienen --bandeja, voz, comparacion-- no
    # tendrian que volver a editar esta prueba para que siga midiendo lo mismo.
    # En el orden de la lista cerrada `SurfaceId`, que es el del registro: un modulo
    # puede montar dos superficies (el chat monta tambien la comparacion desde la
    # fase 1) y el orden de los modulos deja de ser el del directorio.
    orden = list(SurfaceId)
    montadas = [
        superficie.surface_id
        for spec in composition.MODULOS
        for superficie in _superficies_de(spec)
        if superficie.public
    ]
    assert ejemplo["surfaces"] == [s.value for s in sorted(montadas, key=orden.index)]
    for presentada, configurada in zip(ejemplo["tenants"], configuradas, strict=True):
        assert presentada["example_policy"] == configurada.example_policy
        assert presentada["character_key"] == configurada.character_key


def test_el_ejemplo_versionado_esta_al_dia() -> None:
    """La misma pregunta que la comprobacion de deriva, sin tocar el disco."""
    escrito = paths.site_example_path().read_text(encoding="utf-8")

    assert escrito == openapi_export.render_site_example()


def test_escribir_dos_veces_no_cambia_nada(tmp_path: Path) -> None:
    esquema = tmp_path / "openapi.json"
    ejemplo = tmp_path / "examples" / "site-directory.json"

    primera = openapi_export.write(esquema, ejemplo)
    segunda = openapi_export.write(esquema, ejemplo)

    assert primera == [esquema, ejemplo]
    assert segunda == []
