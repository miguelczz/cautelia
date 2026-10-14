"""El directorio del sitio: lo que el inicio necesita para dibujarse (F2, FD-U6-9).

`GET /api/site`, sin credencial y sin aseguradora: el inicio no pertenece a
ninguna. Responde tres cosas, y cada una con una regla que la hace honesta:

- **Las aseguradoras**, leidas de su configuracion versionada. De cada una sale
  solo lo que su carpeta trae: sin marca no hay monograma, sin caracter no hay
  linea de caracter, y el titular y el vehiculo de la poliza de ejemplo no
  aparecen hasta que el corpus los tenga (BR4.2). El codigo no tiene ninguna
  condicion por aseguradora (convencion 9 del equipo).
- **Las superficies publicas y montadas**, del registro de la raiz de
  composicion. Una superficie que no esta montada no aparece, y la interfaz no
  dibuja su boton (BR4.1, FD-U6-1).
- **Los enlaces externos**, solo si estan configurados (BR4.4). Un enlace que
  falta no se dibuja; ninguno apunta al repositorio mientras sea privado.

Como la salud, esta ruta **no llama a ningun proveedor ni gasta** (SEC-U6.9): su
costo es leer configuracion ya cargada. Y no cuenta nada sensible: ni claves, ni
direcciones internas, ni credenciales de la bandeja (SEC-U6.3).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from fastapi import APIRouter

from untangle.base import Frozen, Locale
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.server.problems import problem_responses
from untangle.server.surfaces import SurfaceRegistry
from untangle.surface_spec import SurfaceId
from untangle.tenancy import api as tenancy


class TenantBrandView(Frozen):
    """La marca de una aseguradora, tal como la dibuja la interfaz (BR1.6)."""

    accent: str
    accent_on_dark: str
    monogram: tenancy.Monogram


#: El nombre de la agente cuando la carpeta de la aseguradora no declara el suyo.
AGENT_NAME = CopyKey("insurer.agent.name")


class TenantPresentation(Frozen):
    """Lo que el inicio muestra de una aseguradora (entidad `TenantPresentation`).

    `character_key` y `brand` son opcionales porque su configuracion puede no
    traerlos (CG-U6-4): lo que falta no se muestra ni se inventa (BR4.2).
    """

    tenant_id: str
    display_name: str
    kind: tenancy.TenantKind
    default_language: Locale
    #: Forma `POL-` y seis digitos (C-25). Se muestra entera (BR4.5).
    example_policy: str
    #: El **nombre visible** de quien emitio esa poliza, cuando no la emitio esta
    #: aseguradora (U23, BR1.2). Nulo en una emisora, que emite las suyas.
    #:
    #: Viaja resuelto a nombre y no a identificador porque es lo que se lee en la
    #: pantalla, y resolverlo en el navegador obligaria a cada pantalla a cruzar
    #: dos filas del directorio para dibujar una.
    example_policy_issuer: str | None = None
    character_key: str | None = None
    brand: TenantBrandView | None = None
    #: El nombre de la agente de esta aseguradora, ya resuelto: el de su carpeta o,
    #: si no declara ninguno, el del catalogo.
    agent_name: str


class SiteLinks(Frozen):
    """Los enlaces externos configurados. El que falta no viaja (BR4.4)."""

    readme_url: str | None = None
    video_url: str | None = None


class SiteDirectory(Frozen):
    """La respuesta de `GET /api/site`."""

    tenants: tuple[TenantPresentation, ...]
    #: Solo las publicas y montadas, en el orden de la lista cerrada (BR4.1).
    surfaces: tuple[SurfaceId, ...]
    links: SiteLinks


@dataclass(frozen=True)
class SiteDeps:
    """Lo que el directorio necesita, entregado por la raiz de composicion."""

    registry: SurfaceRegistry
    links: SiteLinks
    #: Las aseguradoras cargadas. Una carpeta rota no esta aqui: se apago sola.
    tenants: Callable[[], Sequence[tenancy.TenantConfig]]


def presentation(
    tenant: tenancy.TenantConfig, *, issuer_name: str | None = None
) -> TenantPresentation:
    """Una aseguradora, tal como la ve el inicio. Solo lo que su carpeta trae.

    `issuer_name` es la unica excepcion, y entra **por argumento** justamente para
    no ser una: el nombre de quien emitio la poliza de ejemplo es dato de otra
    carpeta, asi que esta funcion no lo busca --no tiene las demas a la vista-- y
    quien la llama con el conjunto entero se lo pasa resuelto.
    """
    marca = tenant.brand
    return TenantPresentation(
        tenant_id=tenant.tenant_id,
        display_name=tenant.display_name,
        kind=tenant.kind,
        default_language=tenant.default_language,
        example_policy=tenant.example_policy,
        example_policy_issuer=issuer_name,
        character_key=tenant.character_key,
        agent_name=tenant.agent_name or copy_api.t(AGENT_NAME, locale="es"),
        brand=(
            TenantBrandView(
                accent=marca.accent,
                accent_on_dark=marca.accent_on_dark,
                monogram=marca.monogram,
            )
            if marca is not None
            else None
        ),
    )


def build_directory(
    tenants: Sequence[tenancy.TenantConfig],
    registry: SurfaceRegistry,
    links: SiteLinks,
) -> SiteDirectory:
    """El directorio del sitio. Pura: se prueba sin proceso ni base.

    Es quien resuelve el nombre del emisor de cada poliza de ejemplo, porque es la
    unica pieza que tiene las tres aseguradoras a la vista. Un emisor declarado que
    no este cargado queda en nulo y **no se inventa** (BR4.2): la vista de
    comparacion falla cerrada y no ofrece preguntar.
    """
    nombres = {tenant.tenant_id: tenant.display_name for tenant in tenants}
    return SiteDirectory(
        tenants=tuple(
            presentation(
                tenant,
                issuer_name=(
                    nombres.get(tenant.example_policy_issuer)
                    if tenant.example_policy_issuer is not None
                    else None
                ),
            )
            for tenant in tenants
        ),
        surfaces=registry.public_mounted(),
        links=links,
    )


def router(deps: SiteDeps) -> APIRouter:
    """La ruta del directorio. Lo que falta no viaja: los nulos no se envian."""
    enrutador = APIRouter(prefix="/api", tags=["site"])

    @enrutador.get(
        "/site",
        response_model=SiteDirectory,
        response_model_exclude_none=True,
        operation_id="getSite",
        responses=problem_responses(),
    )
    async def site() -> SiteDirectory:
        return build_directory(deps.tenants(), deps.registry, deps.links)

    return enrutador
