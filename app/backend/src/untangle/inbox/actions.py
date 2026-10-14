"""Que acciones ofrece un caso, y quien lo decide (BR4.3, BR4.5, BR4.7).

**Lo decide la configuracion de la aseguradora, no el codigo.** Una agencia coloca
polizas que emite otra y nunca cierra un siniestro: su unica accion es marcar el
caso como enviado a la emisora. Una aseguradora que emite aprueba y rechaza.

**De donde sale esa diferencia.** Del campo `kind` de la carpeta de configuracion
versionada de cada aseguradora, que es donde ya esta declarada. Se consideró
añadir una lista de acciones propia a cada configuracion, y se descartó: serian
dos sitios diciendo lo mismo --`kind: agency` y `actions: [mark_sent]`-- y el dia
que discreparan no habria forma de saber cual manda. Lo que la regla prohibe es un
identificador de aseguradora **literal** en el codigo de decision, y aqui no hay
ninguno: hay un valor de un conjunto cerrado que sale de un archivo.

**Dos capas, y la de fuera responde primero.** La tabla de permisos versionada de
U2 dice que puede **un rol** --un agente de cuenta no aprueba, un ajustador no marca
como enviado-- y se comprueba en el punto unico por el que pasan todas las rutas,
asi que rechaza antes de llegar aqui, con `404` y sin distinguir la causa. Lo de
aqui dice que ofrece **una aseguradora**. Hoy las dos coinciden, porque cada tipo de
aseguradora tiene su rol; el dia que no coincidan --una aseguradora nueva con un rol
que no le corresponde-- es esta la que lo dice, y por eso no sobra. Su prueba la
ejercita directamente: por la puerta solo se veria la otra.

**El estado del caso tambien acota.** Un caso derivado con completitud parcial se
decide --3 de 7 campos no impide firmar una decision-- y uno que espera al
asegurado, no: la vista dice por que y que falta, y la peticion directa se rechaza
sin cambiar el caso. Uno que la agente aun evalua (`verifying`, `deciding`) lo puede
tomar el personal --se deriva y se decide en la misma accion--, y un visitante con
enlace no: eso le quitaria a su propio caso el cierre sin ajustador.

**La tercera decision del contrato no existe aqui** (BR4.7). C-05 declara
`request_more` y ninguna historia la describe, ningun criterio la ejercita y
ninguna de las cuatro resoluciones de U4 le corresponde: construirla seria
inventar su conducta. Un caso que necesita mas informacion ya tiene camino
probado, que es quedarse esperando al asegurado. Decision de Miguel del
2026-09-28; añadirla despues es aditivo.
"""

from __future__ import annotations

from enum import StrEnum

from untangle.case_record.models import CaseState, Resolution
from untangle.tenancy.models import TenantConfig, TenantKind


class InboxAction(StrEnum):
    """Las acciones que la bandeja ofrece. Conjunto cerrado y sin `request_more`."""

    APPROVE = "approve"
    REJECT = "reject"
    MARK_SENT = "mark_sent"


#: La resolucion de U4 que corresponde a cada accion. Tabla cerrada y escrita, no
#: compuesta en ejecucion: una correspondencia armada con una cadena no aparece en
#: ningun chequeo y el dia que falte una entrada falla en la peticion, no aqui.
RESOLUTION_OF: dict[InboxAction, Resolution] = {
    InboxAction.APPROVE: Resolution.APPROVED,
    InboxAction.REJECT: Resolution.REJECTED,
    InboxAction.MARK_SENT: Resolution.SENT_TO_INSURER,
}

#: Los estados en los que un caso **se puede** decidir. `derived` y nada mas: es el
#: unico en el que el grafo esta pausado esperando a una persona. `awaiting_insured`
#: queda fuera a proposito (BR4.3) y `closed` tambien (BR4.4).
DECIDABLE_STATES: frozenset[CaseState] = frozenset({CaseState.DERIVED})

#: Los estados en los que la agente todavia trabaja el caso por su cuenta (verifica la
#: poliza, evalua las reglas) y que **solo el personal** puede tomar (2026-10-13).
#:
#: Existen porque el cierre pasa por ellos unos segundos y porque un proceso que se
#: reinicia deja casos atascados ahi: la cola los muestra (solo `open` y `capturing`
#: quedan fuera) y, sin esto, el ajustador los veia y no podia hacer nada con ellos.
#: Tomar un caso es derivarlo (T5 o T7 de la tabla) y decidirlo en la misma accion; lo
#: que se pierde es el cierre directo, y por eso un visitante con enlace de
#: demostracion no puede: le quitaria a su propio caso el cierre sin ajustador.
TAKEOVER_STATES: frozenset[CaseState] = frozenset({CaseState.VERIFYING, CaseState.DECIDING})


class ActionNotAllowedError(RuntimeError):
    """Esa aseguradora no ofrece esa accion, o el caso no admite ninguna.

    Las dos causas comparten respuesta hacia fuera. Una agencia intentando aprobar
    y un caso que espera al asegurado son errores distintos para quien lee el
    rastro, y la misma puerta cerrada para quien llama.
    """


def allowed_for(tenant: TenantConfig) -> frozenset[InboxAction]:
    """Las acciones que ofrece esa aseguradora, por su tipo.

    Una agencia deriva siempre a quien emitio la poliza, asi que no aprueba ni
    rechaza: marca el caso como enviado. El traspaso real no existe en esta
    version, y nada de lo que ve el asegurado promete que la emisora lo llame.
    """
    if tenant.kind is TenantKind.AGENCY:
        return frozenset({InboxAction.MARK_SENT})
    return frozenset({InboxAction.APPROVE, InboxAction.REJECT})


def _se_decide_en(state: CaseState, *, by_staff: bool) -> bool:
    """Si un caso en ese estado admite una decision de quien pregunta.

    Una sola pregunta para la pantalla y para la ruta: `derived` lo decide cualquiera
    que pueda abrir el caso, y `verifying` y `deciding` solo quien entro con credencial
    de personal.
    """
    return state in DECIDABLE_STATES or (by_staff and state in TAKEOVER_STATES)


def is_takeover(state: CaseState) -> bool:
    """Si decidir un caso en ese estado es **tomarlo**: la agente aun no lo habia derivado."""
    return state in TAKEOVER_STATES


def offered_for(
    tenant: TenantConfig, *, state: CaseState, by_staff: bool = False
) -> frozenset[InboxAction]:
    """Las acciones que la bandeja **ofrece ahora**: la aseguradora y el estado juntos.

    Es lo que la pantalla dibuja y lo que la vista de caso manda por el cable, y por
    eso vive aqui y no alli: la pantalla que decidiera por su cuenta que un caso
    cerrado no se decide seria una segunda definicion de BR4.4 escrita en otro
    lenguaje, y el dia que una cambie la otra seguiria diciendo lo de antes.

    **Ofrecer no es permitir.** Lo que de verdad impide la accion es
    `require_allowed` en la ruta; esto es la cortesia de no dibujar un boton que va
    a ser rechazado. Las dos leen las mismas dos fuentes --el tipo de la
    aseguradora y el estado del caso-- por las mismas dos funciones, asi que no hay
    dos reglas: hay una regla y dos preguntas distintas sobre ella.

    `by_staff` es cierto solo para quien entro con credencial de personal: un visitante
    con enlace no recibe nada mientras la agente evalua su caso.
    """
    if not _se_decide_en(state, by_staff=by_staff):
        return frozenset()
    return allowed_for(tenant)


def require_allowed(
    tenant: TenantConfig, *, action: InboxAction, state: CaseState, by_staff: bool = False
) -> Resolution:
    """Comprueba la accion contra la aseguradora **y** contra el estado del caso.

    Las dos mitades juntas y en una sola funcion: separarlas dejaria dos sitios
    donde una ruta nueva puede olvidarse de una. Devuelve la resolucion que
    corresponde, para que quien llama no vuelva a decidirla.
    """
    if action not in allowed_for(tenant):
        msg = (
            f"la aseguradora '{tenant.tenant_id}' no ofrece la accion "
            f"'{action.value}': su tipo es '{tenant.kind.value}'"
        )
        raise ActionNotAllowedError(msg)
    if not _se_decide_en(state, by_staff=by_staff):
        msg = (
            f"un caso en '{state.value}' no se decide: solo se decide uno derivado, "
            "que es el unico con el grafo pausado esperando a una persona, o uno que "
            "la agente aun evalua si lo toma el personal"
        )
        raise ActionNotAllowedError(msg)
    return RESOLUTION_OF[action]
