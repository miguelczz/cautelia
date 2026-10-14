"""Las dos tablas que U19 anadio a la bandeja (BR4.1, BR4.2).

El alcance de cada rol --a que casos se limita su bandeja-- y el permiso que pide
decidir cada tipo de registro. Las dos son tablas cerradas, y lo que se comprueba
aqui es sobre todo que **no les falte ninguna fila**: una correspondencia a la que
le falta una entrada no falla al cargar, falla en la peticion de alguien.

Las rutas las ejercitan las pruebas de integracion de U19, que entran por HTTP.
"""

from __future__ import annotations

import pytest

from untangle.case_record.models import CaseState, RecordType
from untangle.inbox import actions
from untangle.inbox import api as bandeja
from untangle.inbox import queue as cola
from untangle.tenancy.models import Action, Role


def test_cada_rol_declara_su_alcance_de_bandeja() -> None:
    """Un rol ausente de la tabla seria un rol sin recorte, y eso no se ve."""
    faltan = set(Role) - set(cola.ALCANCE_DE_ROL)

    assert not faltan, f"sin alcance declarado: {sorted(rol.value for rol in faltan)}"


def test_un_rol_sin_alcance_declarado_no_se_atiende(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falla en vez de servir la cola entera, que es el fallo abierto."""
    monkeypatch.setattr(cola, "ALCANCE_DE_ROL", {})

    with pytest.raises(cola.UndeclaredRoleScopeError):
        cola.scope_of(Role.UNDERWRITER)


def test_la_bandeja_del_suscriptor_se_acota_a_solicitudes_derivadas() -> None:
    """BR4.2: ni siniestros, ni solicitudes que las reglas ya resolvieron."""
    acotados = cola.narrow(cola.QueueFilters(), role=Role.UNDERWRITER)

    assert acotados is not None
    assert acotados.record_type is RecordType.QUOTE_REQUEST
    assert acotados.state is CaseState.DERIVED


def test_pedir_otro_estado_siendo_suscriptor_no_devuelve_los_derivados() -> None:
    """Lo pedido y el alcance no se cruzan: la pagina sale vacia.

    La otra lectura --ignorar el filtro y devolver lo derivado-- responderia filas
    que nadie pidio, y quien las lea creera que eso es lo que hay en `closed`.
    """
    assert cola.narrow(cola.QueueFilters(state=CaseState.CLOSED), role=Role.UNDERWRITER) is None


def test_los_otros_roles_no_se_acotan_por_tipo() -> None:
    """El alcance de U19 es del suscriptor: la cola del ajustador no cambia."""
    acotados = cola.narrow(cola.QueueFilters(state=CaseState.CLOSED), role=Role.ADJUSTER)

    assert acotados is not None
    assert acotados.record_type is None
    assert acotados.state is CaseState.CLOSED


def test_cada_tipo_de_registro_declara_su_permiso_de_decision() -> None:
    """Los tres tipos de U4, sin excepcion."""
    for tipo in RecordType:
        bandeja.permiso_de_decision(record_type=tipo, action=actions.InboxAction.APPROVE)


def test_decidir_una_solicitud_pide_otro_permiso_que_decidir_un_siniestro() -> None:
    """BR4.1: es lo unico que separa al suscriptor del ajustador en la ruta."""
    assert (
        bandeja.permiso_de_decision(
            record_type=RecordType.QUOTE_REQUEST, action=actions.InboxAction.APPROVE
        )
        is Action.DECIDE_QUOTE
    )
    assert (
        bandeja.permiso_de_decision(
            record_type=RecordType.CLAIM, action=actions.InboxAction.APPROVE
        )
        is Action.DECIDE_CASE
    )


def test_marcar_como_enviado_no_mira_el_tipo() -> None:
    """Lo que traspasa la agencia es el caso, cualquiera que sea (BR4.6 de U14)."""
    for tipo in RecordType:
        assert (
            bandeja.permiso_de_decision(record_type=tipo, action=actions.InboxAction.MARK_SENT)
            is Action.MARK_SENT
        )


def test_un_tipo_sin_permiso_declarado_no_se_atiende(monkeypatch: pytest.MonkeyPatch) -> None:
    """Y no cae en uno por omision, que lo elegiria quien olvido la fila."""
    monkeypatch.setattr(bandeja, "_PERMISO_DE_DECISION", {})

    with pytest.raises(bandeja.UndeclaredDecisionPermissionError):
        bandeja.permiso_de_decision(
            record_type=RecordType.QUOTE_REQUEST, action=actions.InboxAction.APPROVE
        )
