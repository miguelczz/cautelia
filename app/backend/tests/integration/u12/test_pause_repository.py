"""`DatabaseHumanReviewRequestStore`: la capa de datos de la pausa (paso 6, BR4.1, BR4.4, BR6.1).

`test_runtime_tables.py` (paso 1) ya prueba que la base **rechaza** una segunda
insercion directa mientras una pausa sigue viva (`human_review_request_una_viva`).
Lo que este archivo cierra es lo que ese paso no podia mostrar todavia: que la
pieza que de verdad usa el ejecutor **no choca contra esa regla**, sino que la
aprovecha para actualizar el motivo en vez de fallar -- BR6.1 dice "apoyate en
la base, no en una comprobacion previa en Python", y aqui es literal: no hay
ningun `find_open` antes del `INSERT` de `insert_open`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from untangle.orchestration.pause import HumanReviewRequestRecord, PauseReason, PauseStatus
from untangle.orchestration.pause_repository import DatabaseHumanReviewRequestStore

from .conftest import nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u12")

_AHORA = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def _pendiente(
    *, tenant_id: str, case_id: str, reason: PauseReason, request_id: str = "hrr-prueba"
) -> HumanReviewRequestRecord:
    return HumanReviewRequestRecord(
        request_id=request_id,
        tenant_id=tenant_id,
        case_id=case_id,
        reason=reason,
        status=PauseStatus.OPEN,
        created_at=_AHORA,
    )


# --- 1. Abrir, sin comprobacion previa (BR4.1, BR6.1) --------------------------


async def test_abrir_una_pausa_nueva_la_deja_leible(dos_aseguradoras: tuple[str, str]) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    store = DatabaseHumanReviewRequestStore()

    creada = await store.insert_open(
        _pendiente(tenant_id=propia, case_id=caso.case_id, reason=PauseReason.COMPLIANCE_REFERRAL)
    )

    assert creada.status is PauseStatus.OPEN
    assert creada.reason is PauseReason.COMPLIANCE_REFERRAL

    leida = await store.find_open(tenant_id=propia, case_id=caso.case_id)
    assert leida is not None
    assert leida.request_id == creada.request_id


async def test_abrir_dos_veces_el_mismo_caso_actualiza_el_motivo_al_mas_reciente(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """El nodo que se reintenta puede llamar dos veces con motivos distintos.

    La revision del paso 2 encontro exactamente esta clase de defecto en el
    canal especial de LangGraph: elegir por lote en vez de por escritura
    dejaba que el motivo nuevo se perdiera al reintentarse el nodo. Aqui se
    prueba que `human_review_request` no repite ese defecto: la fila que queda
    es la del ultimo intento, no la del primero, y sigue siendo **la misma
    fila** -- mismo `request_id`, mismo `created_at`.
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    store = DatabaseHumanReviewRequestStore()

    primera = await store.insert_open(
        _pendiente(
            tenant_id=propia,
            case_id=caso.case_id,
            reason=PauseReason.PROVIDER_FAILURE,
            request_id="hrr-primer-intento",
        )
    )
    segunda = await store.insert_open(
        _pendiente(
            tenant_id=propia,
            case_id=caso.case_id,
            reason=PauseReason.COMPLIANCE_REFERRAL,
            request_id="hrr-segundo-intento",
        )
    )

    # Sigue siendo la misma pausa: el identificador y el momento de creacion no
    # cambian con la actualizacion del motivo.
    assert segunda.request_id == primera.request_id
    assert segunda.created_at == primera.created_at
    assert segunda.reason is PauseReason.COMPLIANCE_REFERRAL

    viva = await store.find_open(tenant_id=propia, case_id=caso.case_id)
    assert viva is not None
    assert viva.reason is PauseReason.COMPLIANCE_REFERRAL

    # --- Rotura deliberada, para comprobar que la prueba de arriba distingue -----
    # Si `insert_open` conservara el motivo del PRIMER intento (`DO NOTHING` en
    # vez de `DO UPDATE`), `viva.reason` seguiria siendo `PROVIDER_FAILURE` y
    # la asercion de arriba fallaria. Se deja como comentario y no como codigo
    # ejecutado -- revertir `DO UPDATE SET reason = excluded.reason` a
    # `DO NOTHING` en `pause_repository._INSERTAR_O_ACTUALIZAR_MOTIVO` y volver
    # a correr esta prueba es la forma de verlo caer.


# --- 2. Retirar, nunca resolver (BR4.4) ----------------------------------------


async def test_retirar_una_pausa_viva_la_marca_withdrawn_no_resolved(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    store = DatabaseHumanReviewRequestStore()
    await store.insert_open(
        _pendiente(tenant_id=propia, case_id=caso.case_id, reason=PauseReason.ABUSE)
    )

    retirada = await store.withdraw(
        tenant_id=propia, case_id=caso.case_id, now=_AHORA + timedelta(minutes=5)
    )

    assert retirada is not None
    assert retirada.status is PauseStatus.WITHDRAWN
    assert retirada.withdrawn_at == _AHORA + timedelta(minutes=5)
    assert retirada.resolved_at is None

    # Ya no esta viva: una segunda pausa del mismo caso ahora abre una fila
    # nueva, no reactiva la retirada.
    ya_no_viva = await store.find_open(tenant_id=propia, case_id=caso.case_id)
    assert ya_no_viva is None


async def test_retirar_un_caso_sin_pausa_viva_es_un_no_op(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    store = DatabaseHumanReviewRequestStore()

    resultado = await store.withdraw(tenant_id=propia, case_id=caso.case_id, now=_AHORA)

    assert resultado is None


async def test_retirar_y_abrir_de_nuevo_es_una_pausa_distinta(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Tras retirarla, la fila retirada no vuelve a abrirse: nace una nueva.

    Sin la fila retirada, `withdrawn` significaria "nunca hubo pausa", que es
    exactamente lo que `resolved` tambien podria significar si se colapsaran.
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    store = DatabaseHumanReviewRequestStore()
    primera = await store.insert_open(
        _pendiente(
            tenant_id=propia,
            case_id=caso.case_id,
            reason=PauseReason.INCOMPLETE_CAPTURE,
            request_id="hrr-primera-pausa",
        )
    )
    await store.withdraw(tenant_id=propia, case_id=caso.case_id, now=_AHORA + timedelta(minutes=1))

    segunda = await store.insert_open(
        _pendiente(
            tenant_id=propia,
            case_id=caso.case_id,
            reason=PauseReason.INCOMPLETE_CAPTURE,
            request_id="hrr-segunda-pausa",
        )
    )

    assert segunda.request_id != primera.request_id
    viva = await store.find_open(tenant_id=propia, case_id=caso.case_id)
    assert viva is not None
    assert viva.request_id == segunda.request_id
