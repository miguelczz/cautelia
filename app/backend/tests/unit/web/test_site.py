"""El directorio del sitio, sin HTTP (BR4.1, BR4.2, BR4.4, SEC-U6.3, SEC-U6.9).

**Sin datos inventados**: las aseguradoras salen de la configuracion real de las
tres carpetas (`unit-test-instructions.md`, Dobles de prueba), no de filas
escritas a mano. Una fila a mano pasaria aunque el directorio leyera mal la
configuracion.
"""

from __future__ import annotations

import json
import re

import pytest

from untangle.server import site, surfaces
from untangle.surface_spec import SurfaceId, SurfaceProbe, SurfaceSpec
from untangle.tenancy import api as tenancy

from . import espias

SIN_ENLACES = site.SiteLinks()


async def _responde() -> None:
    return None


def _superficie(surface_id: SurfaceId, *, public: bool) -> SurfaceSpec:
    return SurfaceSpec(
        surface_id=surface_id,
        owning_unit="prueba",
        public=public,
        per_tenant=True,
        probe=SurfaceProbe(check=_responde, timeout_ms=100),
    )


@pytest.fixture
def aseguradoras() -> tuple[tenancy.TenantConfig, ...]:
    """Las tres de verdad, leidas de `app/config/tenants/`."""
    cargadas = tenancy.load()
    assert cargadas.unavailable == (), "una carpeta de aseguradora no valida"
    return cargadas.available


def test_cada_aseguradora_sale_con_lo_que_su_carpeta_trae(
    aseguradoras: tuple[tenancy.TenantConfig, ...],
) -> None:
    directorio = site.build_directory(aseguradoras, surfaces.SurfaceRegistry(), SIN_ENLACES)

    assert [t.tenant_id for t in directorio.tenants] == [t.tenant_id for t in aseguradoras]
    for presentada, configurada in zip(directorio.tenants, aseguradoras, strict=True):
        assert presentada.display_name == configurada.display_name
        assert presentada.default_language == configurada.default_language
        # La poliza de ejemplo completa, con la forma de C-25 (BR4.5).
        assert re.fullmatch(r"POL-\d{2}", presentada.example_policy)
        assert presentada.example_policy == configurada.example_policy
        # La marca es la de su carpeta, sin tocar.
        assert configurada.brand is not None
        assert presentada.brand is not None
        assert presentada.brand.accent == configurada.brand.accent
        assert presentada.brand.monogram is configurada.brand.monogram
        # La clave de su caracter, la de su carpeta y sin tocar (paso 18).
        assert configurada.character_key is not None
        assert presentada.character_key == configurada.character_key


def test_una_aseguradora_sin_marca_ni_caracter_sale_sin_ellos(
    aseguradoras: tuple[tenancy.TenantConfig, ...],
) -> None:
    """BR4.2 y CG-U6-4: lo que la configuracion no trae no aparece."""
    sin_marca = aseguradoras[0].evolve(brand=None, character_key=None)

    [presentada] = site.build_directory(
        [sin_marca], surfaces.SurfaceRegistry(), SIN_ENLACES
    ).tenants
    serializada = presentada.model_dump(exclude_none=True)

    assert "brand" not in serializada
    assert "character_key" not in serializada


def test_sin_superficies_montadas_el_directorio_no_ofrece_ninguna(
    aseguradoras: tuple[tenancy.TenantConfig, ...],
) -> None:
    """BR4.1: con nada montado, ningun boton lleva a nada."""
    directorio = site.build_directory(aseguradoras, surfaces.SurfaceRegistry(), SIN_ENLACES)

    assert directorio.surfaces == ()


def test_solo_ofrece_las_superficies_publicas_y_montadas(
    aseguradoras: tuple[tenancy.TenantConfig, ...],
) -> None:
    registro = surfaces.SurfaceRegistry(
        [
            _superficie(SurfaceId.INBOX, public=False),
            _superficie(SurfaceId.CHAT, public=True),
        ]
    )

    directorio = site.build_directory(aseguradoras, registro, SIN_ENLACES)

    assert directorio.surfaces == (SurfaceId.CHAT,)


def test_los_enlaces_solo_viajan_si_estan_configurados(
    aseguradoras: tuple[tenancy.TenantConfig, ...],
) -> None:
    """BR4.4: sin variable no hay enlace; con una, solo esa."""
    sin = site.build_directory(aseguradoras, surfaces.SurfaceRegistry(), SIN_ENLACES)
    con_video = site.build_directory(
        aseguradoras,
        surfaces.SurfaceRegistry(),
        site.SiteLinks(video_url="https://example.org/video"),
    )

    assert sin.links.model_dump(exclude_none=True) == {}
    assert con_video.links.model_dump(exclude_none=True) == {
        "video_url": "https://example.org/video"
    }


def test_el_directorio_no_cuenta_nada_de_la_bandeja_ni_de_la_voz(
    aseguradoras: tuple[tenancy.TenantConfig, ...],
) -> None:
    """SEC-U6.3: ni personas de la bandeja, ni voces, ni prefijos internos.

    La prueba busca los valores reales de la configuracion en la respuesta
    serializada: si alguien anadiera un campo que los arrastra, apareceria.
    """
    directorio = site.build_directory(aseguradoras, surfaces.SurfaceRegistry(), SIN_ENLACES)
    serializado = json.dumps(directorio.model_dump(mode="json"))

    for aseguradora in aseguradoras:
        for persona in aseguradora.staff:
            assert persona.principal_id not in serializado
            assert persona.display_name not in serializado
        assert aseguradora.voice.primary_voice not in serializado
        assert f'"{aseguradora.case_number_prefix}"' not in serializado


def test_construir_el_directorio_no_llama_a_ningun_proveedor_ni_gasta(
    monkeypatch: pytest.MonkeyPatch, aseguradoras: tuple[tenancy.TenantConfig, ...]
) -> None:
    """SEC-U6.9: con cada puerta de dinero espiada, nadie la cruza."""
    llamadas = espias.instalar(monkeypatch)
    registro = surfaces.SurfaceRegistry([_superficie(SurfaceId.CHAT, public=True)])

    site.build_directory(aseguradoras, registro, SIN_ENLACES)

    assert llamadas == []


# --- U23, BR1.2: quien emitio la poliza de ejemplo de una agencia -------------


def test_el_directorio_resuelve_el_nombre_de_quien_emitio(
    aseguradoras: tuple[tenancy.TenantConfig, ...],
) -> None:
    """La agencia nombra a su emisor **con el nombre visible**, no con su identificador.

    Lo resuelve el directorio porque es la unica pieza que tiene las tres a la vista:
    `presentation` ve una sola carpeta, y el navegador tendria que cruzar dos filas
    del directorio para dibujar una.

    Ninguna aseguradora se nombra a mano: la agencia se busca por su tipo y el
    nombre esperado se lee de la carpeta que el emisor declarado nombra.
    """
    agencia = next(t for t in aseguradoras if t.kind is tenancy.TenantKind.AGENCY)
    assert agencia.example_policy_issuer is not None
    esperado = next(
        t.display_name for t in aseguradoras if t.tenant_id == agencia.example_policy_issuer
    )

    directorio = site.build_directory(aseguradoras, surfaces.SurfaceRegistry(), SIN_ENLACES)

    por_id = {t.tenant_id: t for t in directorio.tenants}
    assert por_id[agencia.tenant_id].example_policy_issuer == esperado
    assert esperado != agencia.display_name, "una agencia no emite su propia poliza"
    emisoras = [t for t in aseguradoras if t.kind is tenancy.TenantKind.CARRIER]
    assert all(por_id[t.tenant_id].example_policy_issuer is None for t in emisoras)


def test_un_emisor_declarado_que_no_esta_cargado_queda_en_nulo(
    aseguradoras: tuple[tenancy.TenantConfig, ...],
) -> None:
    """Lo que falta no se muestra ni se inventa (BR4.2 de U6).

    Con el nulo, la vista de comparacion falla cerrada y no ofrece la pregunta. La
    alternativa --ensenar el identificador-- pondria un `tenant_id` en una pantalla
    donde los demas nombres se escriben con mayusculas y espacios.
    """
    agencia = next(t for t in aseguradoras if t.kind is tenancy.TenantKind.AGENCY)

    directorio = site.build_directory([agencia], surfaces.SurfaceRegistry(), SIN_ENLACES)

    assert directorio.tenants[0].example_policy_issuer is None
