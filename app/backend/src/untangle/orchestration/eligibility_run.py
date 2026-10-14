"""La elegibilidad de una solicitud, evaluada en el ritmo de fondo (BR2.5 de U19).

**El hueco que cierra.** `compose_eligibility_reply` esta escrita y probada desde
U19 y su unico consumidor era el corredor de evaluaciones: en el camino real,
Sunmeadow ofrecia cotizar y no respondia nunca. Lo que faltaba no era la frase,
era quien evaluara y donde quedara el resultado.

**Por que aqui y no como un nodo del grafo.** La transicion esta cerrada sobre los
cuatro nombres del PRD --`intake`, `policy_verification`, `decision`,
`compliance`-- y la convencion 3 del equipo exige una sola grafia para esos cuatro:
un quinto nombre la rompe en el enum, en la traza, en el reporte y en el tablero.
Y el estado del grafo solo admite campos que declare un `NodeSpec` (BR1.5), asi que
la salida tampoco cabria ahi. Se evalua en el ritmo de fondo --que es lo que BR2.5
pide, y lo que `rhythm.launch_background` nombra-- y se guarda en su tabla.

**No es un nodo, y por eso no lleva politica de fallo de nodo.** Un nodo la lleva
porque habla con un proveedor y puede colgarse; esto es calculo puro en memoria
sobre campos que ya estan guardados: sin red, sin reloj y sin modelo. Lo unico que
puede fallar es que un campo falte o este mal escrito, y las dos cosas levantan con
su nombre en vez de devolver una salida inventada.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from untangle import observability
from untangle.case_record import api as casos
from untangle.case_record.crypto import Cipher
from untangle.compliance.controls.api import HandoffReason
from untangle.orchestration import case_context, contracts, quote_reply, transcript_writer
from untangle.orchestration.output import ExitGate
from untangle.rules import eligibility
from untangle.rules import eligibility_repository as repositorio
from untangle.tenancy.models import TenantId

__all__ = ["EligibilityAdapter", "evaluate_and_store"]


async def evaluate_and_store(
    tenant_id: TenantId, case_id: str, *, cipher: Cipher, now: datetime
) -> eligibility.EligibilityOutcome | None:
    """Evalua la solicitud del caso y deja su salida, o `None` si todavia no se puede.

    Devuelve `None` --sin levantar-- cuando la aseguradora no tiene conjunto de
    elegibilidad o cuando a la solicitud le falta algun campo que el conjunto lee.
    Las dos son situaciones normales y no fallos: la segunda es una captura que
    todavia no termino, y evaluar con datos que faltan es como una solicitud mal
    capturada acabaria "elegible" (BR1.3).

    **Abre solo los campos que las reglas leen**, no el caso entero: abrir todo por
    comodidad convertiria esto en una operacion sobre todos los datos personales de
    quien pidio una cotizacion.
    """
    conjunto = eligibility.loaded().get(tenant_id)
    if conjunto is None:
        observability.emit(
            "orchestration.eligibility_unavailable", tenant_id=tenant_id, case_id=case_id
        )
        return None

    valores = await casos.open_field_values(
        tenant_id, case_id, sorted(conjunto.required_inputs), cipher=cipher
    )
    insumos = eligibility.eligibility_inputs(valores)
    try:
        salida = eligibility.evaluate_eligibility(conjunto, insumos)
    except eligibility.MissingEligibilityInputsError:
        # La captura todavia no termino. No se guarda nada y no se dice que no:
        # el turno distingue "no evaluada" de "no elegible" porque la fila no esta.
        observability.emit(
            "orchestration.eligibility_incomplete", tenant_id=tenant_id, case_id=case_id
        )
        return None

    await repositorio.save_eligibility(tenant_id, case_id, salida, evaluated_at=now)
    observability.emit(
        "orchestration.eligibility_evaluated",
        tenant_id=tenant_id,
        case_id=case_id,
        outcome=salida.outcome.value,
        band=salida.band.value,
    )
    if salida.outcome is eligibility.EligibilityOutcomeKind.REFERRED and await _completa(
        tenant_id, case_id
    ):
        await _al_suscriptor(tenant_id, case_id, now=now)
    return salida


async def _completa(tenant_id: TenantId, case_id: str) -> bool:
    """Si la solicitud tiene ya todos sus datos.

    Las reglas leen solo cinco de los diecisiete, asi que la evaluacion sale antes de
    terminar la captura. Guardarla temprano no hace dano; **decirla o derivar** si: en
    produccion el chat respondia "su solicitud puede seguir adelante" a mitad de la
    captura y la persona seguia contestando preguntas (visto el 2026-10-08).
    """
    vista = await casos.get_case(tenant_id, case_id)
    if vista is None:
        return False
    completitud = vista.completeness
    return completitud.total > 0 and completitud.complete == completitud.total


async def _al_suscriptor(tenant_id: TenantId, case_id: str, *, now: datetime) -> None:
    """C8, visto el 2026-10-07: la solicitud que el motor manda a un suscriptor quedaba
    en captura, y la cola del suscriptor solo lista casos derivados. Se deriva por la
    misma funcion que las demas derivaciones, atada al ultimo turno de la conversacion,
    que es hasta donde la revision de cumplimiento se acota."""
    turnos = await casos.transcript_of(tenant_id, case_id)
    if not turnos:
        observability.emit(
            "orchestration.referral_without_turn", tenant_id=tenant_id, case_id=case_id
        )
        return
    await case_context.derive_case(
        tenant_id=tenant_id,
        case_id=case_id,
        reason=HandoffReason.RULE,
        turn_id=str(turnos[-1].turn_id),
        now=now,
    )


async def deliver_reply(
    tenant_id: TenantId,
    case_id: str,
    salida: eligibility.EligibilityOutcome,
    *,
    notifier: contracts.CaseNotifier,
) -> bool:
    """Le lleva la respuesta a quien la pidio, **sin esperar a un turno siguiente**.

    **Es la mitad que de verdad cierra el hueco.** Todo lo demas que el fondo
    calcula se lee en el turno siguiente, y basta porque la persona vuelve a
    escribir. Una solicitud de cotizacion no: quien acaba de dar su ultimo campo se
    queda esperando, y sin esto la respuesta existe, esta guardada, y no llega
    nunca.

    **El texto pasa por la guardia de salida**, como todo lo que llega al asegurado
    --incluidos los caminos de degradacion y de error, y aunque salga entero del
    catalogo (M6, mandato del proyecto)--. No es ceremonia: la compuerta dura de
    esta unidad prohibe que una respuesta lleve un importe, un simbolo de moneda o
    un porcentaje en cualquier idioma, y la guardia es quien los caza. El modulo que
    compone la frase lo dice: no construye su propio detector porque este existe.

    Devuelve si habia alguien escuchando. `False` no es un fallo: la pestana se
    cerro, o el caso llego por la voz. La respuesta sigue guardada y el turno
    siguiente la lee.
    """
    vista = await casos.get_case(tenant_id, case_id)
    if vista is None:  # pragma: no cover -- se acaba de evaluar sobre ese caso
        return False
    texto_base = quote_reply.compose_eligibility_reply(
        salida.outcome.value, salida.band.value, salida.explanation_key, language=vista.language
    )
    puerta = ExitGate(tenant_id=tenant_id, language=vista.language, case_id=case_id)
    texto, _ = await puerta.send(texto_base)
    # Tambien a la transcripcion: lo que sale en pantalla es lo que queda al volver.
    return await transcript_writer.say_without_turn(
        notifier,
        transcript_writer.TranscriptScope(
            tenant_id=tenant_id, case_id=case_id, channel=vista.channel, language=vista.language
        ),
        text=texto,
        now=datetime.now(UTC),
    )


@dataclass(frozen=True)
class EligibilityAdapter:
    """El puerto de la elegibilidad, con el cifrador y el reloj que la raiz enchufa.

    Es la pieza que traduce entre los dos lados: del lado del motor hay enums y una
    fila en la base; del lado del turno hay tres cadenas y ninguna dependencia del
    motor de reglas. Nada mas cruza esa frontera --en particular, **no cruzan los
    identificadores de las reglas que decidieron**, que son para la traza y la
    bandeja (BR2.3)--.
    """

    cipher: Cipher
    clock: Callable[[], datetime]
    #: Quien sabe llevarle la respuesta a una conversacion viva. Opcional: sin el,
    #: la salida queda guardada y el turno siguiente la lee --que es el
    #: comportamiento de la tanda 1-- y se dice con su evento en vez de suponerlo.
    notifier: contracts.CaseNotifier | None = None

    async def evaluate(self, tenant_id: str, case_id: str) -> contracts.EligibilityView | None:
        salida = await evaluate_and_store(tenant_id, case_id, cipher=self.cipher, now=self.clock())
        if salida is None:
            return None
        if not await _completa(tenant_id, case_id):
            # La respuesta llega cuando la persona termina de dar sus datos, no antes.
            observability.emit(
                "orchestration.eligibility_held_until_complete",
                tenant_id=tenant_id,
                case_id=case_id,
            )
        elif self.notifier is None:
            observability.emit(
                "orchestration.eligibility_notifier_missing",
                tenant_id=tenant_id,
                case_id=case_id,
            )
        else:
            await deliver_reply(tenant_id, case_id, salida, notifier=self.notifier)
        return _como_texto(salida)

    async def stored(self, tenant_id: str, case_id: str) -> contracts.EligibilityView | None:
        guardada = await repositorio.eligibility_of(tenant_id, case_id)
        return None if guardada is None else _como_texto(guardada)


def _como_texto(salida: eligibility.EligibilityOutcome) -> contracts.EligibilityView:
    return contracts.EligibilityView(
        outcome=salida.outcome.value,
        band=salida.band.value,
        explanation_key=salida.explanation_key,
    )
