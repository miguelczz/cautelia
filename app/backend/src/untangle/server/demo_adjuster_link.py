"""Un caso listo para hacer de ajustador en la demo local, con su enlace.

    mise run demo:ajustador
    mise run demo:ajustador -- --tenant <id> --base-url http://localhost:8050

Para probar a mano la pantalla del visitante que hace de ajustador (decidir y anotar para
las reglas) sin tener que conversar primero hasta que un reporte llegue a un ajustador
(2026-10-14, pedido de Miguel). Busca un siniestro que **admita anotaciones**
--`annotation.can_annotate`, la misma pregunta que hace la bandeja--, prefiere uno derivado
(se puede decidir ademas de anotar) y, entre los derivados, uno de un visitante antes que
uno del generador; emite su enlace de una hora con `tenancy.issue_case_link` e imprime la
direccion entera.

**Si el caso es del generador**, lo que se anote o decida con el enlace lo deshace el
siguiente reinicio, que devuelve los casos sembrados a su estado (`demo:reset`).

**El token sale solo por la salida estandar**, igual que en `tenancy:case-link`: un
archivo con el token dentro seria el unico sitio donde vive y a la vez el sitio donde no
debe estar. No hay `tenant_id` escrito aqui: sin `--tenant` se recorren las aseguradoras
cargadas, primero las que deciden (`carrier`) y despues las agencias.

Vive en `untangle.server` porque necesita a la vez la lista de casos, la regla de la
bandeja y el enlace del visitante, y es la unica capa donde los tres se encuentran.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence

from untangle.case_record import api as casos
from untangle.case_record import repository as case_repo
from untangle.case_record.api import CaseSummary
from untangle.case_record.models import CaseState, Origin
from untangle.inbox import annotation
from untangle.settings import Settings
from untangle.tenancy import api as tenancy
from untangle.tenancy.models import TenantId, TenantKind

#: Donde escucha `mise run dev` (ver la tarea en `mise.toml`).
BASE_LOCAL = "http://localhost:8050"

#: Cuantos casos se miran por aseguradora. La demo local tiene unas decenas.
_CUANTOS = 200

#: Los origenes de un visitante: se prefieren porque son los casos de quien prueba.
_DE_VISITANTE = frozenset({Origin.PUBLIC_CHAT.value, Origin.PUBLIC_VOICE_CONSOLE.value})


def choose_case(
    items: Sequence[CaseSummary], *, origins: dict[str, str] | None = None
) -> CaseSummary | None:
    """El caso con el que se hace de ajustador, o ninguno.

    Solo los que admiten anotaciones. Primero los derivados (se deciden y se anotan) y
    despues los que esperan al asegurado (solo se anotan); dentro de cada grupo, los de un
    visitante antes que los del generador, y el mas reciente primero.
    """
    origenes = origins or {}

    def orden(caso: CaseSummary) -> tuple[int, int, float]:
        derivado = 0 if caso.state is CaseState.DERIVED else 1
        de_visitante = 0 if origenes.get(caso.case_id) in _DE_VISITANTE else 1
        return (derivado, de_visitante, -caso.created_at.timestamp())

    candidatos = [
        caso
        for caso in items
        if annotation.can_annotate(state=caso.state, record_type=caso.record_type)
    ]
    return min(candidatos, key=orden) if candidatos else None


async def _origenes(tenant_id: TenantId) -> dict[str, str]:
    """De donde salio cada caso, para preferir los del visitante."""
    del_generador = await casos.list_cases(
        tenant_id,
        filters=case_repo.ListingFilters(origin=Origin.GENERATOR.value),
        limit=_CUANTOS,
    )
    origenes = {caso.case_id: Origin.GENERATOR.value for caso in del_generador.items}
    for origen in _DE_VISITANTE:
        pagina = await casos.list_cases(
            tenant_id, filters=case_repo.ListingFilters(origin=origen), limit=_CUANTOS
        )
        origenes.update({caso.case_id: origen for caso in pagina.items})
    return origenes


async def _buscar(tenant_id: TenantId) -> CaseSummary | None:
    pagina = await casos.list_cases(tenant_id, filters=case_repo.ListingFilters(), limit=_CUANTOS)
    return choose_case(pagina.items, origins=await _origenes(tenant_id))


async def _emitir(tenants: Sequence[TenantId], base: str, signing_key: str | None) -> int:
    try:
        return await _emitir_el_primero(tenants, base, signing_key)
    finally:
        await tenancy.dispose()


async def _emitir_el_primero(
    tenants: Sequence[TenantId], base: str, signing_key: str | None
) -> int:
    for tenant_id in tenants:
        caso = await _buscar(tenant_id)
        if caso is None:
            continue
        emitido = await tenancy.issue_case_link(
            tenant_id=tenant_id, case_id=caso.case_id, signing_key=signing_key
        )
        print(f"{base}/c#{emitido.token}")
        print(
            f"\ncaso {caso.case_number} de '{tenant_id}', {caso.state.value}; el enlace vale "
            f"hasta las {emitido.expires_at.astimezone():%H:%M}. Abralo en el navegador "
            "donde corre la demo. No lo guarde en ningun archivo.",
            file=sys.stderr,
        )
        return 0
    print(
        "demo:ajustador: ninguna aseguradora tiene un siniestro con un ajustador o esperando "
        "al asegurado. Siembre los casos de ejemplo con `mise run synthetic:seed` o termine "
        "un reporte en el chat.",
        file=sys.stderr,
    )
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    analizador.add_argument("--tenant", default=None, help="la aseguradora; sin ella, todas")
    analizador.add_argument("--base-url", default=BASE_LOCAL, help="donde corre la demo")
    argumentos = analizador.parse_args(argv)

    opciones = Settings()
    if not opciones.database_url:
        print(
            "demo:ajustador: falta UNTANGLE_DATABASE_URL. Levante la base local con "
            "`mise run services:up`",
            file=sys.stderr,
        )
        return 1
    tenancy.install(tenancy.load())
    tenancy.configure(opciones.database_url)
    # Primero las aseguradoras y despues las agencias: una agencia deriva siempre a quien emitio
    # la poliza, asi que ahi se marca como enviado y no se aprueba ni se rechaza.
    disponibles = tuple(
        sorted(
            tenancy.available_ids(),
            key=lambda t: (tenancy.require(t).kind is not TenantKind.CARRIER, t),
        )
    )
    if argumentos.tenant is not None and argumentos.tenant not in disponibles:
        print(
            f"demo:ajustador: no hay una aseguradora '{argumentos.tenant}'. "
            f"Las cargadas: {', '.join(disponibles)}",
            file=sys.stderr,
        )
        return 2
    elegidas = disponibles if argumentos.tenant is None else (argumentos.tenant,)
    base = str(argumentos.base_url).rstrip("/")
    return asyncio.run(_emitir(elegidas, base, opciones.case_link_signing_key))


if __name__ == "__main__":
    sys.exit(main())
