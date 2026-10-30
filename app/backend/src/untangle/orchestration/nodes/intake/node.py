"""El nodo `intake` con la forma de C-15: su especificacion y su turno (BR1.1 a BR5.6).

Este archivo es lo que las otras piezas de la unidad no eran: **el nodo**. Ellas
saben cada una su regla --que bloque toca, como se lee un bloque, si un turno
insulta, como se compone una frase-- y ninguna sabe en que orden se aplican. Eso
es lo que hay aqui, y es lo que `functional-spec.md` promete entregarle a U12
("U11 entrega el nodo con la forma de C-15").

**Es puro, como C-15 exige.** Devuelve su conjunto de escritura y nada mas: no
abre transacciones, no escribe en la base y no captura su propio fallo. La razon
no es estetica -- LangGraph vuelve a ejecutar el nodo completo al reanudar tras
`interrupt()`, asi que un nodo que escribiera duplicaria efectos. Quien aplica el
conjunto de escritura al caso es el ejecutor de U12, por la API de U4.

**El orden del turno, y por que es este.** Cada paso puede terminar el turno, y
el que termina primero manda:

1. **La emergencia.** Si U10 levanto la senal, el turno son las dos frases de
   AC1.6.1 y no se pide ningun dato ni se extrae nada. Va primero porque
   cualquier otro orden le pregunta la placa a alguien que esta sangrando.
2. **El abuso.** Los insultos se recuentan sobre la transcripcion completa
   (BR5.4) y los umbrales los fija la aseguradora (TECH-U11.5). Al segundo
   umbral la sesion termina y no se extrae: seguir capturando de quien acaba de
   recibir la frase de cierre seria no haberla dicho.
3. **Lo social.** Si la persona saludo, agradecio, se despidio o pregunto
   cuanto falta, se reconoce sin modelo (`social.py`) y se contesta **delante**
   de lo que tocaba; la despedida va sola y deja el caso como esta. Un turno que
   no trae mas que eso no llama al extractor: no hay nada que extraer y la
   llamada gasta el plan gratuito para volver vacia (decision de Miguel,
   2026-10-06). Tampoco resuelve una lectura pendiente: "gracias" no es un no.
4. **La extraccion.** Solo lo dicho en este turno, con su evidencia (BR2.1,
   BR2.2). Va antes de elegir el bloque porque un dato adelantado tiene que
   contar ya para la completitud (BR3.3) -- si no, se le vuelve a preguntar en
   el mismo turno en el que lo dijo.
5. **El bloque y la frase.** El bloque sale del caso y no de un contador
   (BR3.2); la frase sale del catalogo (BR5.1) y lleva su clave (C-14). Si el
   turno resolvio una lectura, la frase empieza diciendolo --"Gracias." o
   "Entendido, lo corrijo."-- en vez de soltar la pregunta a secas.

**Lo que este nodo no decide.** A que nodo se va despues: es la funcion de
transicion del grafo, y es de U12 (convencion 5c). Depende de los dos ritmos
--que el turno no espere al trabajo de fondo-- y esta unidad no los modela.
Tampoco decide su propio presupuesto de latencia: `timeout_ms` y `attempts` de
mas abajo son el dato declarado mientras U12 no fije el suyo desde la medicion
real, igual que hicieron los otros tres nodos.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from pydantic import Field

from untangle import observability
from untangle.base import Frozen, Locale
from untangle.case_record import fields
from untangle.case_record.models import CaseState, Completeness, RecordType
from untangle.compliance.controls.normalization import fold
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration.nodes.intake import (
    blocks,
    composition,
    confirmation,
    extraction,
    normalization,
    policy,
    safety_evidence,
    social,
    tone,
)
from untangle.orchestration.nodes.intake.blocks import Block
from untangle.orchestration.nodes.intake.extraction import (
    ExtractedField,
    ExtractedItem,
    ExtractionResponse,
)
from untangle.orchestration.nodes.intake.policy import (
    HeardPolicyNumber,
    PolicyByHolderPort,
    PolicyMatch,
    PolicyMatchPort,
)
from untangle.orchestration.nodes.intake.social import SocialIntent
from untangle.orchestration.nodes.intake.understanding import Answer, UnderstandingResponse, Want
from untangle.orchestration.state import NodeSpec
from untangle.providers.ports import ProviderError, SystemInstruction
from untangle.telemetry.traces.models import NodeName
from untangle.tenancy.models import TENANT_ID_PATTERN, IntakeConfig, TenantId


class SessionEnd(StrEnum):
    """El unico motivo por el que la captura cierra la sesion (BR5.4, AC1.13.3)."""

    ABUSE = "abuse"


class ReadbackResolution(Frozen):
    """Lo que la persona contesto a una lectura de confirmacion (BR3.1, FD-U11-8).

    Lleva **los campos** y no solo el bloque, y esa diferencia importa: cuando
    alguien dice "no, dije que no habia heridos" esta rechazando y corrigiendo en
    la misma frase. Lo que se devuelve a "nadie lo dijo" son los campos que este
    turno **no** volvio a decir; borrar el bloque entero se llevaria por delante
    la correccion que acaba de llegar.
    """

    block: Block
    accepted: bool
    #: Los campos a confirmar, o a devolver a "nadie lo dijo".
    fields: tuple[str, ...]


class IntakeNodeInput(Frozen):
    """Los campos del estado que el nodo lee (`NodeSpec.reads`)."""

    tenant_id: TenantId = Field(pattern=TENANT_ID_PATTERN)
    case_id: str = Field(min_length=1)
    record_type: RecordType
    case_state: CaseState
    completeness: Completeness
    language: Locale
    #: El turno de la persona. Viaja como campo del estado y **nunca** se
    #: concatena al prompt de sistema (BR2.3, RT-1, RT-2).
    turn_text: str
    turn_id: str = Field(min_length=1)
    #: Si la conversacion es una llamada (2026-10-09): la voz cierra con sus frases,
    #: sin "el enlace de arriba" ni el numero de caso, que dice al despedirse.
    spoken: bool = False
    #: Los turnos de la persona en la conversacion, para recontar los insultos
    #: sobre la transcripcion completa en vez de llevar un contador (BR5.4).
    person_turns: tuple[str, ...] = ()
    #: La senal y la frase las produce el control barato de U10 (FD-U11-3): esta
    #: unidad no detecta la emergencia, la respeta.
    emergency_raised: bool = False
    emergency_instruction: str | None = None
    #: Lo ya confirmado del caso, para el resumen de cierre (AC1.5.2).
    confirmed_values: dict[str, str] = Field(default_factory=dict)
    #: El bloque cuya lectura se emitio en el turno anterior, si la hubo. Sale
    #: del punto de control, que es donde el conjunto de escritura del turno
    #: pasado quedo guardado: **no hay contador propio que desincronizar**.
    awaiting_confirmation: Block | None = None
    #: Lo dicho y sin confirmar, en claro, para poder leerlo de vuelta
    #: nombrandolo (FD-U11-8). Solo los campos que esperan su lectura.
    stated_values: dict[str, str] = Field(default_factory=dict)
    #: Cuantos insultos disparan la calma y cuantos el cierre, por aseguradora.
    intake_config: IntakeConfig = Field(default_factory=IntakeConfig)
    #: La poliza que el corpus devolvio en el turno anterior y espera el si o el no
    #: de la persona (P3). Sale del punto de control, como la lectura pendiente.
    awaiting_policy_confirmation: PolicyMatch | None = None
    #: Si ya se le pidio una vez a la persona que repitiera su poliza cifra por cifra
    #: (2026-10-13). Sale del punto de control y **sobrevive a los turnos**: la repeticion se
    #: pide una sola vez por conversacion, y si tampoco sale, sigue sin poliza identificada.
    policy_repeat_asked: bool = False
    #: Si ya se volvio a preguntar "¿eres tu?" porque la respuesta no fue ni si ni no
    #: (2026-10-14). Como la anterior, sale del punto de control y sobrevive a los turnos: se
    #: pregunta otra vez una sola vez por conversacion.
    policy_confirm_reasked: bool = False
    #: El bloque que la agente pregunto en el turno anterior (2026-10-10). Sale del
    #: punto de control, como la lectura pendiente. Sirve para una sola cosa: saber
    #: si un "no" corto contesta a "¿hubo alguien herido?" o a otra pregunta.
    previous_block: Block | None = None
    #: El numero legible del caso, para decirlo al cerrar (P4). Vacio en los
    #: dobles que no lo tienen.
    case_number: str = ""
    #: Lo que la agente entendio de este mensaje con el modelo (fase 0, 2026-10-07).
    #: Con esto los datos y el si o el no salen de lo que la persona quiso decir, y
    #: no de reglas por palabras; sin esto, la captura sigue como antes.
    understood: UnderstandingResponse | None = None


class IntakeNodeOutput(Frozen):
    """El conjunto de escritura del nodo (`NodeSpec.writes`), y nada mas.

    **Los nombres llevan el prefijo del nodo a proposito.** `policy_verification`
    ya escribe `response_key` y `response_text`, y dos nodos no comparten ningun
    campo del estado (convencion 6). Los dos corren en ritmos distintos y nunca
    compondrian el mismo turno, pero un campo compartido es un campo compartido:
    si U12 decide unificarlos al disenar el estado, que sea una decision escrita
    y no un choque que nadie vio.
    """

    intake_next_block: Block
    intake_extracted: tuple[ExtractedField, ...]
    #: El bloque cuya lectura se acaba de emitir. Hasta el si, no cuenta como
    #: confirmado (BR3.1).
    intake_awaiting_confirmation: Block | None
    #: Lo que la persona contesto a la lectura del turno anterior, si la hubo.
    #: Quien lo aplica al caso es el ejecutor, como con lo extraido.
    intake_readback_resolved: ReadbackResolution | None
    #: La clave del catalogo y el texto ya resuelto (C-14, BR5.1).
    intake_response_key: str
    intake_response_text: str
    intake_session_ended: SessionEnd | None
    #: La poliza encontrada en este turno, a la espera de confirmacion (P3).
    intake_policy_match: PolicyMatch | None = None
    #: Este turno pidio que repitiera la poliza cifra por cifra (2026-10-13): el numero que se
    #: oyo no llevo a ninguna. Quien guarda el punto de control lo conserva, para no pedirlo dos
    #: veces (`turn._writes_del_turno`).
    intake_policy_repeat_asked: bool = False
    #: Este turno volvio a preguntar "¿eres tu?" (2026-10-14). Quien guarda el punto de control
    #: lo conserva, para no preguntarlo una tercera vez (`turn._writes_del_turno`).
    intake_policy_confirm_reasked: bool = False
    #: El numero de poliza que la persona acaba de confirmar como suyo (P3): quien
    #: aplica el conjunto de escritura la ata al caso.
    intake_policy_confirmed: str | None = None
    #: La captura del siniestro termino (P4): los datos obligatorios estan y la
    #: persona no quiso agregar mas. Quien aplica el conjunto de escritura lleva
    #: el caso al ajustador.
    intake_capture_closed: bool = False


#: **1 600 ms y dos intentos.** Lo fijo U12 en su etapa de requisitos de calidad
#: (PERF-U12.4), y no es una eleccion: la meta p95 del turno son 800 ms --del fin
#: del habla al primer audio, decision del PRD-- y un nodo del ritmo del turno con
#: un tiempo maximo mayor no puede participar de ese turno; cuando se cumpliera, el
#: turno ya habria fallado su meta. La regla es el doble de la meta p95: margen
#: suficiente para que una llamada simplemente lenta termine, poco para que una
#: colgada retenga a la persona ocho segundos, que es lo que decia el valor
#: anterior. El trabajo propio de este nodo, sin la llamada al proveedor, esta
#: medido en 5,3 ms p95.
#:
#: **Este nodo NO consume sus `attempts`**: deja subir el fallo para que el
#: ejecutor comun aplique la politica (convencion 8b). Es lo contrario de
#: `policy_verification`, que si los consume porque tras agotarlos todavia tiene
#: que escribir su valor distinguible; aqui no hay nada que escribir despues, y
#: el turno degradado es una frase del catalogo que el ejecutor ya sabe emitir.
INTAKE_SPEC = NodeSpec(
    name=NodeName.INTAKE,
    reads=frozenset(IntakeNodeInput.model_fields),
    writes=frozenset(IntakeNodeOutput.model_fields),
    rhythm="turn",
    timeout_ms=1_600,
    attempts=2,
    # Lo que la persona lee si el nodo falla o se pasa de tiempo: una frase que
    # dice lo que paso y pide repetir, no la de calma de BR5.4 (que habla de
    # insultos y dejaba a la persona sin saber que hacer; defecto del 2026-10-06).
    degraded_copy_key=str(composition.INTAKE_DEGRADED),
)

#: Como el nodo pide la extraccion y la instruccion de sistema versionada, por
#: closure desde la raiz de composicion (C-16, TECH-U11.1).
ExtractorPort = extraction.ExtractorPort
InstructionPort = Callable[[Locale], SystemInstruction]
#: El reloj, para las fechas relativas de la normalizacion (BR2.4). Un nodo no
#: lee el reloj por su cuenta: asi dos corridas del mismo caso normalizan igual.
ClockPort = Callable[[], date]


@dataclass(frozen=True)
class _CierreRapido:
    """Lo que el cierre del recorrido rapido (P4) necesita para componer su salida."""

    state: IntakeNodeInput
    extracted: tuple[ExtractedField, ...]
    resolution: ReadbackResolution | None
    lead_in: str | None
    completeness: Completeness
    opcionales: tuple[Block, ...]
    fase: composition.ClosingPhase

    @property
    def ya_cerro_la_captura(self) -> bool:
        """Si el caso ya salio de la captura: en revision, con un ajustador o cerrado."""
        return self.fase is not composition.ClosingPhase.CAPTURING

    def salida(
        self,
        clave: CopyKey,
        texto: str,
        *,
        cerrado: bool = False,
        esperando: Block | None = None,
    ) -> IntakeNodeOutput:
        return IntakeNodeOutput(
            intake_next_block=Block.DONE if self.ya_cerro_la_captura else Block.FINAL_CONFIRMATION,
            intake_extracted=self.extracted,
            intake_awaiting_confirmation=esperando,
            intake_readback_resolved=self.resolution,
            intake_response_key=str(clave),
            intake_response_text=composition.with_lead_in(self.lead_in, texto),
            intake_session_ended=None,
            intake_capture_closed=cerrado,
        )

    def frase(
        self, kind: composition.FastClosing, *, missing: tuple[Block, ...] = ()
    ) -> tuple[CopyKey, str]:
        return composition.compose_fast_closing(
            kind,
            case_number=self.state.case_number,
            language=self.state.language,
            missing=missing,
            spoken=self.state.spoken,
            phase=self.fase,
        )

    def pregunta_opcional(self) -> tuple[CopyKey, str]:
        primero = self.opcionales[0]
        return composition.question_of(
            primero,
            blocks.missing_fields_in_block(self.state.record_type, primero, self.completeness),
            language=self.state.language,
        )


#: Donde esta el caso, para elegir la frase de cierre. `open` no llega aqui --el primer turno
#: ya lo paso a captura--, y si llegara se trata como captura.
_FASE_DEL_CASO: dict[CaseState, composition.ClosingPhase] = {
    CaseState.VERIFYING: composition.ClosingPhase.REVIEWING,
    CaseState.DECIDING: composition.ClosingPhase.REVIEWING,
    CaseState.DERIVED: composition.ClosingPhase.WITH_ADJUSTER,
    CaseState.AWAITING_INSURED: composition.ClosingPhase.WITH_ADJUSTER,
    CaseState.CLOSED: composition.ClosingPhase.REGISTERED,
}


def _turno_terminado(
    *,
    key: str,
    text: str,
    block: Block,
    session_ended: SessionEnd | None = None,
) -> IntakeNodeOutput:
    """Un turno que no extrae nada: emergencia, calma o cierre por abuso."""
    return IntakeNodeOutput(
        intake_next_block=block,
        intake_extracted=(),
        intake_awaiting_confirmation=None,
        intake_readback_resolved=None,
        intake_response_key=key,
        intake_response_text=text,
        intake_session_ended=session_ended,
    )


def _preguntar_por_la_poliza(
    state: IntakeNodeInput, extracted: Sequence[ExtractedField], match: PolicyMatch
) -> IntakeNodeOutput:
    """La poliza existe: la agente dice de quien es y pregunta si es ella (P3)."""
    clave, texto = policy.compose_found(
        match, language=state.language, asks_driver=state.record_type is RecordType.CLAIM
    )
    return IntakeNodeOutput(
        intake_next_block=Block.IDENTITY_AND_POLICY,
        intake_extracted=tuple(extracted),
        intake_awaiting_confirmation=None,
        intake_readback_resolved=None,
        intake_response_key=str(clave),
        intake_response_text=texto,
        intake_session_ended=None,
        intake_policy_match=match,
    )


class IntakeNode:
    """El nodo `intake` (C-15). Se construye en la raiz de composicion con sus puertos."""

    spec: NodeSpec = INTAKE_SPEC

    def __init__(
        self,
        *,
        extract: ExtractorPort,
        instruction: InstructionPort,
        clock: ClockPort,
        lookup: PolicyMatchPort | None = None,
        holder_lookup: PolicyByHolderPort | None = None,
    ) -> None:
        self._extract = extract
        self._instruction = instruction
        self._clock = clock
        # Sin puerto de busqueda la captura funciona como antes de P3: guarda lo
        # dicho y no coteja. Lo enchufa la raiz de composicion.
        self._lookup = lookup
        # La busqueda por nombre del titular (2026-10-13), para cuando el numero se oyo mal.
        # Sin ella, un numero que no lleva a ninguna poliza solo pide repetirlo.
        self._holder_lookup = holder_lookup

    async def run(self, state: IntakeNodeInput) -> IntakeNodeOutput:
        """Un turno de captura. Puro: devuelve su conjunto de escritura (C-15)."""
        if state.emergency_raised:
            # BR4.1: rompe el orden en el mismo turno, antes de pedir nada. Con la
            # senal levantada y sin la frase de U10, `compose_turn` falla: medio
            # turno de emergencia es peor que ninguno.
            turno = composition.compose_turn(
                emergency_raised=True,
                emergency_instruction=state.emergency_instruction,
                # `compose_turn` ignora el bloque con la senal levantada; se pasa
                # el que toca por firma, no porque influya.
                block=Block.SAFETY,
                missing_field_keys=(),
                emotion=None,
                language=state.language,
            )
            return _turno_terminado(key=turno.key, text=turno.text, block=Block.SAFETY)

        # Un siniestro que las reglas ya cerraron no se sigue capturando (US1.17): sus campos
        # no cambian --la evidencia de cierre atestigua lo que habia al cerrarlo-- y llamar al
        # modelo para extraer algo que no se va a guardar es gastar para nada. Se dice donde
        # quedo y no se anota nada.
        if state.record_type is RecordType.CLAIM and state.case_state is CaseState.CLOSED:
            cerrado = _CierreRapido(
                state=state,
                extracted=(),
                resolution=None,
                lead_in=None,
                completeness=state.completeness,
                opcionales=(),
                fase=composition.ClosingPhase.REGISTERED,
            )
            return cerrado.salida(*cerrado.frase(composition.FastClosing.ALREADY))

        # El abuso y la respuesta a "¿es usted?" (P3) terminan el turno sin
        # extraer: el primero porque no se sigue capturando a quien recibio la
        # frase de cierre; el segundo porque un si escribe dos campos del corpus y
        # un no devuelve la identidad a "nadie lo dijo".
        temprano = self._abuso(state) or self._resolver_poliza(state)
        if temprano is not None:
            return temprano

        senal = social.detect(state.turn_text, language=state.language)
        solo_social = senal is not None and social.is_only_social(
            state.turn_text, language=state.language
        )

        # Sin nada que extraer no se llama al modelo: "hola" o "gracias" volverian
        # con una lista vacia tras varios segundos del plan gratuito.
        extraidos = () if solo_social else await self._capturar(state)
        if not extraidos and not solo_social:
            extraidos = self._respuesta_libre_de_cotizacion(state)
        completitud = _con_lo_extraido(state.record_type, state.completeness, extraidos)

        # La poliza que la persona acaba de dar, buscada en el corpus (P3): si
        # existe, la agente dice de quien es y pregunta si es ella, en vez de
        # seguir con el bloque siguiente.
        # Y el numero que se oyo y no lleva a ninguna poliza (2026-10-13): llego incompleto, o
        # en una llamada no existe. Si el titular se nombro entero y una sola poliza suya se
        # parece, se propone; si no, se pide una vez que lo repita cifra por cifra.
        de_la_poliza = await self._poliza_del_turno(state, extraidos)
        if de_la_poliza is not None:
            return de_la_poliza

        # La lectura del turno anterior se resuelve **antes** de elegir bloque:
        # un si deja el bloque terminado y lo que toca preguntar ya es otro.
        resolucion = self._resolver_lectura(state, extraidos, only_social=solo_social)
        if resolucion is not None:
            completitud = _con_la_confirmacion(completitud, resolucion)

        bloque = blocks.next_block(state.record_type, completitud, state.case_state)
        return self._componer_turno(state, extraidos, resolucion, completitud, bloque, senal)

    def _componer_turno(  # noqa: PLR0913, PLR0917 -- el estado, lo extraido, la lectura resuelta, la completitud, el bloque y la senal: lo que hay que juntar
        self,
        state: IntakeNodeInput,
        extraidos: tuple[ExtractedField, ...],
        resolucion: ReadbackResolution | None,
        completitud: Completeness,
        bloque: Block,
        senal: SocialIntent | None,
    ) -> IntakeNodeOutput:
        """Lo que la agente dice con el bloque ya elegido: despedida, cierre,
        lectura o pregunta, con lo social, la correccion y la transicion delante."""
        if senal is SocialIntent.GOODBYE:
            # La despedida va sola y deja el caso donde estaba: lo extraido se
            # escribe igual, la lectura pendiente sigue pendiente, y el turno
            # siguiente retoma por el mismo bloque.
            clave, texto = composition.compose_social(senal, language=state.language)
            return IntakeNodeOutput(
                intake_next_block=bloque,
                intake_extracted=extraidos,
                intake_awaiting_confirmation=(
                    state.awaiting_confirmation if resolucion is None else None
                ),
                intake_readback_resolved=resolucion,
                intake_response_key=str(clave),
                intake_response_text=texto,
                intake_session_ended=None,
            )

        antesala = self._antesala(
            senal,
            resolucion,
            language=state.language,
            record_type=state.record_type,
            completeness=completitud,
            corrections=tuple(
                c for c in extraidos if state.completeness.per_field.get(c.field_key, False)
            ),
        )

        # El siniestro con sus datos obligatorios cierra con el recorrido rapido
        # (P4): el caso queda con el ajustador y lo opcional se ofrece una vez. Un
        # caso ya derivado no tiene bloque (`DONE`) pero si puede tener la oferta
        # abierta, o una persona que sigue escribiendo: las dos cosas se contestan.
        if state.record_type is RecordType.CLAIM and (
            bloque in (Block.FINAL_CONFIRMATION, Block.DONE)
            or state.awaiting_confirmation is Block.FINAL_CONFIRMATION
        ):
            return self._cerrar_siniestro(state, extraidos, resolucion, completitud, antesala)

        # El bloque no tiene nada mas que preguntar y espera su lectura: se lee,
        # nombrando lo dicho (FD-U11-8). Es el unico camino que confirma un campo
        # desde la conversacion, y hasta el 2026-09-29 no existia: `build_readback`
        # llevaba desde U11 escrita y probada sin que nadie la llamara.
        if state.record_type is RecordType.QUOTE_REQUEST and bloque in blocks.order_for(
            RecordType.QUOTE_REQUEST
        ):
            # La solicitud se conversa (2026-10-08): se abre pidiendo todo de una vez,
            # lo que falta se pregunta agrupado y se confirma una sola vez al final.
            orden = blocks.order_for(RecordType.QUOTE_REQUEST)
            con_faltantes = next(
                (
                    b
                    for b in orden
                    if blocks.missing_fields_in_block(state.record_type, b, completitud)
                ),
                None,
            )
            if con_faltantes is None:
                por_leer = [
                    b
                    for b in orden
                    if blocks.readback_fields_in_block(state.record_type, b, completitud)
                ]
                if por_leer:
                    return self._leer_la_solicitud(
                        state, por_leer, extraidos, resolucion, lead_in=antesala
                    )
            else:
                bloque = con_faltantes
                if not any(completitud.per_field.values()) and not completitud.awaiting_readback:
                    clave, texto = composition.quote_opening_question(language=state.language)
                    return IntakeNodeOutput(
                        intake_next_block=bloque,
                        intake_extracted=extraidos,
                        intake_awaiting_confirmation=None,
                        intake_readback_resolved=resolucion,
                        intake_response_key=str(clave),
                        intake_response_text=composition.with_lead_in(antesala, texto),
                        intake_session_ended=None,
                    )

        if blocks.readback_due(state.record_type, bloque, completitud):
            return self._leer_de_vuelta(state, bloque, extraidos, resolucion, lead_in=antesala)

        faltan = (
            blocks.missing_fields_in_block(state.record_type, bloque, completitud)
            if bloque in blocks.order_for(state.record_type)
            else ()
        )
        if not extraidos and resolucion is None and len(faltan) > 1:
            # Un turno sin nada anotado ni lectura resuelta no es el primero de este
            # bloque: la pregunta agrupada ya se hizo y la persona no la contesto. Volver
            # a pedir los mismos tres datos repetia el mensaje sin fin (visto el
            # 2026-10-11 con "Three." contestando a modelo, VIN y perdida total); se pide
            # solo el primero, con la frase de un dato que el catalogo ya tiene. El
            # primer mensaje de un bloque --tras un turno que si anoto algo-- sigue
            # agrupado. Sin estado: lo extraido en este turno es lo unico que se mira.
            faltan = faltan[:1]
        turno = composition.compose_turn(
            emergency_raised=False,
            block=bloque,
            missing_field_keys=faltan,
            emotion=tone.detect_emotion(state.turn_text, language=state.language),
            language=state.language,
            record_type=state.record_type,
            confirmed_values=state.confirmed_values,
            question_known=completitud.per_field.get("question_asked", False),
        )
        return IntakeNodeOutput(
            intake_next_block=bloque,
            intake_extracted=extraidos,
            intake_awaiting_confirmation=bloque if bloque is Block.FINAL_CONFIRMATION else None,
            intake_readback_resolved=resolucion,
            intake_response_key=turno.key,
            intake_response_text=composition.with_lead_in(antesala, turno.text),
            intake_session_ended=None,
        )

    async def _poliza_del_turno(
        self, state: IntakeNodeInput, extracted: Sequence[ExtractedField]
    ) -> IntakeNodeOutput | None:
        """Lo que el turno hace con la poliza que la persona dio, o `None` si no dio ninguna."""
        encontrada = await self._buscar_poliza(state, extracted)
        if encontrada is None:
            return await self._poliza_sin_resolver(state, extracted)
        # En una consulta, quien ya dijo el nombre del titular no tiene que
        # confirmarlo: "¿Eres tu?" sobraba y retrasaba la respuesta (2026-10-09).
        # En un siniestro se pregunta igual, porque la pregunta tambien confirma
        # quien manejaba.
        # El nombre puede venir de un mensaje anterior, el que dio antes de elegir
        # que queria: viaja como el dato de identidad entendido (2026-10-09).
        dicho = " ".join(
            [state.turn_text] + [c.value for c in extracted if c.field_key == "identity_and_policy"]
        )
        if state.record_type is RecordType.COVERAGE_INQUIRY and policy.names_holder(
            dicho, encontrada.holder_name
        ):
            return self._confirmar_poliza(state, encontrada, asked=False, also=extracted)
        return _preguntar_por_la_poliza(state, extracted, encontrada)

    async def _buscar_poliza(
        self, state: IntakeNodeInput, extracted: Sequence[ExtractedField]
    ) -> PolicyMatch | None:
        """La poliza de la identidad recien extraida, si el corpus la tiene (P3)."""
        if self._lookup is None or state.record_type is RecordType.QUOTE_REQUEST:
            return None
        identidad = next(
            (campo for campo in extracted if campo.field_key == "identity_and_policy"), None
        )
        if identidad is None:
            # Tras pedirle que repitiera la poliza, el numero puede llegar sin que el
            # extractor lo lleve a la identidad: se busca en lo que dijo.
            if not state.policy_repeat_asked:
                return None
            return await policy.look_up(state.tenant_id, state.turn_text, lookup=self._lookup)
        return await policy.look_up(state.tenant_id, identidad.value, lookup=self._lookup)

    async def _poliza_sin_resolver(
        self, state: IntakeNodeInput, extracted: Sequence[ExtractedField]
    ) -> IntakeNodeOutput | None:
        """Un numero de poliza que se oyo y no lleva a ninguna (2026-10-13).

        El reconocedor de una llamada entrega «Paul 20 1» por «POL-21»: el numero llega
        incompleto, o con una cifra cambiada. `_buscar_poliza` solo encuentra una poliza con
        el numero exacto, y sin ella el caso seguia **sin poliza identificada** aunque la
        persona hubiera dicho su nombre entero. Aqui, para un numero que llego incompleto (en
        el chat y en la llamada) o que no existe (solo en la llamada, donde lo normal es que se
        haya oido mal; en el chat se escribe y se deja como esta):

        1. Si la persona nombro entero a su titular, **una sola** poliza suya y las cifras se
           parecen (`policy.digits_resemble`), **se propone** con la frase de siempre. Nunca se
           ata: el si de la persona es lo unico que la ata (`_resolver_poliza`).
        2. Si no, y todavia no se pidio, se pide **una vez** que la repita cifra por cifra.
        3. Si tampoco sale, `None`: la captura sigue como antes, sin poliza identificada.

        Devuelve `None` cuando no hay nada que resolver: no se oyo ningun numero de poliza.
        """
        if self._lookup is None or state.record_type is RecordType.QUOTE_REQUEST:
            return None
        de_identidad = " ".join(c.value for c in extracted if c.field_key == "identity_and_policy")
        oido = policy.heard_policy_number(de_identidad) or policy.heard_policy_number(
            state.turn_text
        )
        if oido is None or (oido.complete and not state.spoken):
            return None

        if oido.number is not None:
            exacta = await policy.look_up(state.tenant_id, oido.number, lookup=self._lookup)
            if exacta is not None:
                return _preguntar_por_la_poliza(state, extracted, exacta)

        propuesta = await self._poliza_del_titular(state, oido, de_identidad)
        if propuesta is not None:
            return _preguntar_por_la_poliza(state, extracted, propuesta)
        if state.policy_repeat_asked:
            return None
        return IntakeNodeOutput(
            intake_next_block=Block.IDENTITY_AND_POLICY,
            intake_extracted=tuple(extracted),
            intake_awaiting_confirmation=None,
            intake_readback_resolved=None,
            intake_response_key=str(policy.POLICY_NOT_FOUND_REPEAT),
            intake_response_text=policy.compose_not_found_repeat(language=state.language),
            intake_session_ended=None,
            intake_policy_repeat_asked=True,
        )

    async def _poliza_del_titular(
        self, state: IntakeNodeInput, oido: HeardPolicyNumber, de_identidad: str
    ) -> PolicyMatch | None:
        """La unica poliza del titular que la persona nombro entero, si sus cifras se parecen."""
        if self._holder_lookup is None:
            return None
        dicho = f"{state.turn_text} {de_identidad}".strip()
        del_titular = await self._holder_lookup(state.tenant_id, dicho)
        if len(del_titular) != 1 or not policy.digits_resemble(
            oido.digits, del_titular[0].policy_number
        ):
            return None
        return del_titular[0]

    def _resolver_poliza(self, state: IntakeNodeInput) -> IntakeNodeOutput | None:
        """Que contesto la persona a "¿es usted?" (P3).

        Un si escribe la identidad con el nombre del titular y, si la poliza
        trae vehiculo, el vehiculo con el titular al volante, los dos con la
        evidencia de este turno; y deja la poliza para atarla al caso. Un no
        devuelve la identidad a "nadie lo dijo" y se vuelve a pedir, esta vez con
        nombre. Lo que no es ni si ni no se pregunta **una vez mas** (2026-10-14: en una
        llamada, una frase mal oida tras "¿eres tu?" hizo que la agente volviera a pedir el
        nombre y la poliza que ya tenia); si tampoco entonces es un si, se trata como no: la
        agente no afirma quien es alguien que no lo confirmo.
        """
        pendiente = state.awaiting_policy_confirmation
        if pendiente is None:
            return None
        acepto = _acepta(state)
        if not acepto and not _niega(state) and not state.policy_confirm_reasked:
            clave, texto = policy.compose_confirm_again(
                pendiente,
                language=state.language,
                asks_driver=state.record_type is RecordType.CLAIM,
            )
            return IntakeNodeOutput(
                intake_next_block=Block.IDENTITY_AND_POLICY,
                intake_extracted=(),
                intake_awaiting_confirmation=None,
                intake_readback_resolved=None,
                intake_response_key=str(clave),
                intake_response_text=texto,
                intake_session_ended=None,
                intake_policy_match=pendiente,
                intake_policy_confirm_reasked=True,
            )
        if not acepto:
            completitud = _con_la_confirmacion(
                state.completeness,
                ReadbackResolution(
                    block=Block.IDENTITY_AND_POLICY, accepted=False, fields=("identity_and_policy",)
                ),
            )
            return IntakeNodeOutput(
                intake_next_block=blocks.next_block(
                    state.record_type, completitud, state.case_state
                ),
                intake_extracted=(),
                intake_awaiting_confirmation=None,
                intake_readback_resolved=ReadbackResolution(
                    block=Block.IDENTITY_AND_POLICY, accepted=False, fields=("identity_and_policy",)
                ),
                intake_response_key=str(policy.POLICY_DECLINED),
                intake_response_text=policy.compose_declined(language=state.language),
                intake_session_ended=None,
            )
        return self._confirmar_poliza(state, pendiente)

    def _confirmar_poliza(
        self,
        state: IntakeNodeInput,
        pendiente: PolicyMatch,
        *,
        asked: bool = True,
        also: Sequence[ExtractedField] = (),
    ) -> IntakeNodeOutput:
        """La poliza queda confirmada: identidad con el nombre del titular y, si la trae,
        el vehiculo con el titular al volante, los dos con la evidencia de este turno."""
        confirmados = [
            ExtractedField(
                field_key="identity_and_policy",
                value=policy.confirmed_identity_value(pendiente, language=state.language),
                normalized=None,
                evidence_turn_id=state.turn_id,
                evidence_verbatim_redacted=state.turn_text,
            )
        ]
        vehiculo = policy.confirmed_vehicle_value(pendiente, language=state.language)
        # «Soy yo, pero manejaba mi hijo» (C3): el conductor que la persona dijo
        # manda sobre el titular al volante que la poliza supone.
        dicho_al_volante = next(
            (
                item.value
                for item in (state.understood.items if state.understood is not None else ())
                if item.field_key == "vehicle_and_driver"
            ),
            None,
        )
        if dicho_al_volante is not None and pendiente.vehicle is not None:
            # El vehiculo de la poliza **sin** «conducia el titular»: la frase del catalogo
            # afirma justo lo contrario de lo que la persona acaba de decir, y quien lee el
            # campo --el ajustador, y la derivacion del conductor-- no puede fiarse de un
            # texto que dice las dos cosas a la vez.
            vehiculo = f"{pendiente.vehicle}. {dicho_al_volante}"
        if vehiculo is not None and "vehicle_and_driver" in {
            d.key for d in fields.definitions_for(state.record_type)
        }:
            confirmados.append(
                ExtractedField(
                    field_key="vehicle_and_driver",
                    value=vehiculo,
                    normalized=None,
                    evidence_turn_id=state.turn_id,
                    evidence_verbatim_redacted=state.turn_text,
                )
            )
        # Lo demas que dijo en el mismo mensaje --la pregunta de la consulta-- se
        # guarda tambien: sin ella no hay que responder (2026-10-09).
        tomados = {c.field_key for c in confirmados}
        confirmados.extend(c for c in also if c.field_key not in tomados)
        completitud = _con_lo_extraido(state.record_type, state.completeness, confirmados)
        bloque = blocks.next_block(state.record_type, completitud, state.case_state)
        antesala = (
            composition.compose_transition(accepted=True, language=state.language)
            if asked
            else None
        )
        if state.record_type is RecordType.CLAIM and bloque in (
            Block.FINAL_CONFIRMATION,
            Block.DONE,
        ):
            # La poliza era lo ultimo que faltaba: el siniestro se cierra aqui, por el
            # mismo recorrido rapido que cualquier otro. Componer "la siguiente
            # pregunta" de un siniestro sin preguntas levantaba, y la persona leia
            # "tuve un problema para responder" justo al terminar (2026-10-10).
            cierre = self._cerrar_siniestro(state, confirmados, None, completitud, antesala)
            return cierre.model_copy(update={"intake_policy_confirmed": pendiente.policy_number})
        faltan = (
            blocks.missing_fields_in_block(state.record_type, bloque, completitud)
            if bloque in blocks.order_for(state.record_type)
            else ()
        )
        turno = composition.compose_turn(
            emergency_raised=False,
            block=bloque,
            missing_field_keys=faltan,
            emotion=None,
            language=state.language,
            record_type=state.record_type,
            confirmed_values=state.confirmed_values,
            question_known=completitud.per_field.get("question_asked", False),
        )
        return IntakeNodeOutput(
            intake_next_block=bloque,
            intake_extracted=tuple(confirmados),
            intake_awaiting_confirmation=bloque if bloque is Block.FINAL_CONFIRMATION else None,
            intake_readback_resolved=None,
            intake_response_key=turno.key,
            # "Gracias por confirmar" solo si se le pregunto.
            intake_response_text=composition.with_lead_in(antesala, turno.text),
            intake_session_ended=None,
            intake_policy_confirmed=pendiente.policy_number,
        )

    def _cerrar_siniestro(
        self,
        state: IntakeNodeInput,
        extracted: Sequence[ExtractedField],
        resolution: ReadbackResolution | None,
        completeness: Completeness,
        lead_in: str | None,
    ) -> IntakeNodeOutput:
        """El cierre del recorrido rapido (P4, decision de Miguel del 2026-10-06; US1.17).

        Con los obligatorios dichos, la agente dice que ya tiene lo necesario y **el caso pasa
        a revision en ese mismo turno** (`intake_capture_closed`): las reglas deciden despues si
        lo cierra la agente o lo mira un ajustador, y lo dice cuando lo sabe. Hasta el
        2026-10-13 la frase prometia un ajustador y el caso se derivaba siempre. Si falta algo
        opcional, lo **ofrece una sola vez** y lee la respuesta en el turno siguiente
        (`_contestar_la_oferta`); mientras la oferta esta abierta el caso no se cierra ni se
        deriva. Quien sigue escribiendo despues del cierre recibe el recordatorio de donde esta
        su caso, y lo que diga con forma de dato se anota igual --salvo en un caso ya cerrado,
        que no cambia (BR6.4 de U4)--.
        """
        cierre = _CierreRapido(
            state=state,
            extracted=tuple(extracted),
            resolution=resolution,
            lead_in=lead_in,
            completeness=completeness,
            opcionales=blocks.optional_blocks_missing(state.record_type, completeness),
            fase=_FASE_DEL_CASO.get(state.case_state, composition.ClosingPhase.CAPTURING),
        )
        if state.awaiting_confirmation is Block.FINAL_CONFIRMATION:
            return self._contestar_la_oferta(cierre)
        if cierre.ya_cerro_la_captura:
            # Despues del cierre, sin oferta abierta: la persona sigue escribiendo.
            if extracted:
                return cierre.salida(*cierre.frase(composition.FastClosing.AFTER_EXTRA))
            return cierre.salida(*cierre.frase(composition.FastClosing.ALREADY))
        if not cierre.opcionales:
            return cierre.salida(*cierre.frase(composition.FastClosing.DONE), cerrado=True)
        return cierre.salida(
            *cierre.frase(composition.FastClosing.OFFER, missing=cierre.opcionales),
            cerrado=True,
            esperando=Block.FINAL_CONFIRMATION,
        )

    @staticmethod
    def _contestar_la_oferta(cierre: _CierreRapido) -> IntakeNodeOutput:
        """La respuesta a "¿quieres agregar X, o lo dejamos asi?".

        Lo que trae datos se anota y se sigue ofreciendo lo que quede; un si
        explicito pide el primer bloque opcional; cualquier otra cosa cierra la oferta. El
        caso ya esta en revision con la oferta, asi que ninguna rama vuelve a cerrar la
        captura --el turno que **cierra la oferta** es el que vuelve a lanzar la decision
        (`turn._despues_de_la_captura`)--. Con una excepcion: un caso que sigue en captura
        con la oferta abierta es uno al que nunca se le pudo pasar a revision, y cerrar la
        oferta es la ocasion de reintentarlo.
        """
        sigue_en_captura = cierre.fase is composition.ClosingPhase.CAPTURING
        if cierre.extracted:
            if cierre.opcionales:
                return cierre.salida(
                    *cierre.pregunta_opcional(), esperando=Block.FINAL_CONFIRMATION
                )
            return cierre.salida(
                *cierre.frase(composition.FastClosing.AFTER_EXTRA), cerrado=sigue_en_captura
            )
        if cierre.opcionales and _acepta_la_oferta(cierre.state):
            return cierre.salida(*cierre.pregunta_opcional(), esperando=Block.FINAL_CONFIRMATION)
        return cierre.salida(
            *cierre.frase(composition.FastClosing.DECLINED), cerrado=sigue_en_captura
        )

    @staticmethod
    def _antesala(  # noqa: PLR0913 -- la senal, la lectura, las correcciones y el caso: lo que decide que va delante
        senal: SocialIntent | None,
        resolucion: ReadbackResolution | None,
        *,
        language: Locale,
        record_type: RecordType,
        completeness: Completeness,
        corrections: Sequence[ExtractedField] = (),
    ) -> str | None:
        """Lo que va delante del turno que tocaba, o nada.

        Una lectura resuelta manda sobre el saludo y el agradecimiento: a "si,
        gracias" se le contesta "Gracias." y no "Con gusto. Gracias.". La
        pregunta por el avance se contesta siempre, porque es una pregunta.
        """
        partes: list[str] = []
        for corregido in corrections:
            # Un dato ya dicho que vuelve a decirse se reemplaza y se dice (P4):
            # "perdon, no eran dos sino tres" no vuelve a preguntar nada.
            partes.append(composition.compose_correction(corregido.value, language=language))
        if resolucion is not None:
            partes.append(
                composition.compose_transition(accepted=resolucion.accepted, language=language)
            )
        elif senal in (SocialIntent.GREETING, SocialIntent.THANKS):
            partes.append(composition.compose_social(senal, language=language)[1])
        if senal is SocialIntent.PROGRESS:
            avance = composition.Progress(
                done=completeness.complete,
                total=completeness.total,
                missing=blocks.missing_blocks(record_type, completeness),
            )
            partes.append(composition.compose_social(senal, language=language, progress=avance)[1])
        return " ".join(partes) if partes else None

    def _resolver_lectura(
        self,
        state: IntakeNodeInput,
        extracted: Sequence[ExtractedField],
        *,
        only_social: bool = False,
    ) -> ReadbackResolution | None:
        """Que contesto la persona a la lectura del turno anterior (BR3.1).

        Lo que no es un si es un no, y callar no confirma: es el mismo
        reconocedor que usa la voz para un codigo deletreado, y la misma regla.
        Un dato que se anota porque nadie dijo lo contrario es un dato inventado.

        **Con una excepcion desde el 2026-10-06:** un turno que solo saluda,
        agradece o pregunta cuanto falta no contesta la lectura, ni con si ni con
        no, y la lectura sigue pendiente: se vuelve a leer. "Gracias" como
        respuesta a "¿Es correcto?" borraba el bloque y lo volvia a preguntar.
        """
        pendiente = state.awaiting_confirmation
        if pendiente is None or pendiente not in blocks.order_for(state.record_type):
            return None
        acepto = _acepta(state)
        if only_social and not acepto and not _niega(state):
            return None
        # En la solicitud, la lectura es una sola para todos sus bloques (2026-10-08).
        a_leer = (
            blocks.order_for(RecordType.QUOTE_REQUEST)
            if state.record_type is RecordType.QUOTE_REQUEST
            else (pendiente,)
        )
        candidatos = tuple(
            campo
            for b in a_leer
            for campo in blocks.readback_fields_in_block(state.record_type, b, state.completeness)
        )
        # Tampoco contesta la lectura quien no dice si ni no y sigue con datos de
        # otra parte: en una cotizacion, "es un Mazda 3 2021" despues de "¿Es
        # correcto?" sobre el conductor borraba al conductor y la agente volvia a
        # pedir su nombre, turno tras turno (visto en produccion el 2026-10-08).
        del_bloque = {
            d.key
            for d in fields.definitions_for(state.record_type)
            if blocks.block_of(d.source_block) in a_leer
        }
        if (
            not acepto
            and not _niega(state)
            and extracted
            and not any(campo.field_key in del_bloque for campo in extracted)
        ):
            return None
        # Lo que este mismo turno volvio a decir no se toca: quien rechaza una
        # lectura suele corregirla en la misma frase.
        redichos = {campo.field_key for campo in extracted}
        afectados = tuple(clave for clave in candidatos if acepto or clave not in redichos)
        if not afectados:
            return None
        return ReadbackResolution(block=pendiente, accepted=acepto, fields=afectados)

    def _leer_de_vuelta(
        self,
        state: IntakeNodeInput,
        block: Block,
        extracted: Sequence[ExtractedField],
        resolution: ReadbackResolution | None,
        *,
        lead_in: str | None = None,
    ) -> IntakeNodeOutput:
        """La lectura de confirmacion de un bloque terminado (FD-U11-8).

        Se leen **los valores**, no un resumen: "anotado, sin heridos" cumple y
        "anotado, los datos del accidente" no. Los de este turno salen de lo
        extraido, que todavia no esta en el caso; los de turnos anteriores llegan
        en `stated_values`, ya descifrados por quien tiene el cifrador.
        """
        valores = {**state.stated_values, **{c.field_key: c.value for c in extracted}}
        return IntakeNodeOutput(
            intake_next_block=block,
            intake_extracted=tuple(extracted),
            intake_awaiting_confirmation=block,
            intake_readback_resolved=resolution,
            intake_response_key=str(confirmation.readback_key(block)),
            intake_response_text=composition.with_lead_in(
                lead_in, confirmation.build_readback(block, valores, language=state.language)
            ),
            intake_session_ended=None,
        )

    def _leer_la_solicitud(
        self,
        state: IntakeNodeInput,
        por_leer: Sequence[Block],
        extracted: Sequence[ExtractedField],
        resolution: ReadbackResolution | None,
        *,
        lead_in: str | None = None,
    ) -> IntakeNodeOutput:
        """Toda la solicitud leida de una vez, con una sola pregunta (2026-10-08).

        Queda a la espera del ultimo bloque de la solicitud: `_resolver_lectura`
        confirma con un si todos los campos dichos de la solicitud, no solo los de ese.
        """
        valores = {**state.stated_values, **{c.field_key: c.value for c in extracted}}
        ultimo = blocks.order_for(RecordType.QUOTE_REQUEST)[-1]
        return IntakeNodeOutput(
            intake_next_block=ultimo,
            intake_extracted=tuple(extracted),
            intake_awaiting_confirmation=ultimo,
            intake_readback_resolved=resolution,
            intake_response_key=str(confirmation.READBACK_QUOTE_ALL),
            intake_response_text=composition.with_lead_in(
                lead_in,
                confirmation.build_quote_summary(por_leer, valores, language=state.language),
            ),
            intake_session_ended=None,
        )

    def _abuso(self, state: IntakeNodeInput) -> IntakeNodeOutput | None:
        """BR5.4: la calma al llegar al primer umbral, el cierre al segundo.

        Los umbrales los fija la configuracion de la aseguradora y no el codigo
        (TECH-U11.5, FD-U11-6). Se recuenta sobre la transcripcion completa, asi
        que reanudar tras `interrupt()` no pierde la cuenta (FD-U11-1).
        """
        # Solo responde a un turno que insulta: con el recuento de toda la conversacion
        # y nada mas, despues del segundo insulto hasta un "gracias" recibia la frase
        # de calma, para siempre (C4, visto el 2026-10-07).
        if not tone.is_insult(state.turn_text, language=state.language):
            return None
        insultos = tone.count_insults(state.person_turns, language=state.language)
        if insultos >= state.intake_config.close_after_insults:
            return _turno_terminado(
                key=str(composition.TONE_CLOSING_ABUSE),
                text=composition.compose_closing_by_abuse(language=state.language),
                block=Block.DONE,
                session_ended=SessionEnd.ABUSE,
            )
        if insultos >= state.intake_config.calm_after_insults:
            return _turno_terminado(
                key=str(composition.TONE_CALM),
                text=composition.compose_calm(language=state.language),
                block=blocks.next_block(state.record_type, state.completeness, state.case_state),
            )
        return None

    async def _capturar(self, state: IntakeNodeInput) -> tuple[ExtractedField, ...]:
        """Lo que la persona dijo, como campos: por regla cuando basta, por modelo si no.

        **Una respuesta corta a una pregunta de un solo dato se guarda tal cual, sin
        llamar al modelo** (decision del 2026-10-07). Es lo que Miguel pidio --"lo
        que le digan, que lo guarde"-- y lo que el plan gratuito del modelo obliga:
        su latencia va de menos de un segundo a mas de cuarenta, y con ella «Sí,
        dos personas» a «¿Hubo alguien herido?» vencia el presupuesto del turno y
        la agente pedia que lo repitieran. Una respuesta larga, o una pregunta de
        dos datos (cuando y donde), si pasa por el modelo, que es quien sabe
        repartirla; y si el modelo no contesta a tiempo y habia un solo dato
        pendiente, el texto entero se guarda en ese dato en vez de perderse. La
        correccion (P4) funciona igual por los dos caminos.
        """
        if state.understood is not None:
            return self._de_lo_entendido(state, state.understood.as_extraction())
        if is_short_answer(state.turn_text):
            por_regla = self._campos_por_regla(state)
            if por_regla:
                return self._como_respuesta(state, por_regla)
            if state.record_type is RecordType.CLAIM and _es_asentimiento(
                state.turn_text, state.language
            ):
                # Un "si" a secas a una pregunta abierta (la de seguridad ya se lo
                # quedo la regla): no hay nada que extraer, y preguntarselo al
                # modelo era esperar hasta ocho segundos para que dijera lo mismo.
                return ()
        try:
            return await asyncio.wait_for(self._extraer(state), timeout=EXTRACTION_SOFT_TIMEOUT_S)
        except (TimeoutError, ProviderError):
            por_regla = self._campos_por_regla(state)
            if not por_regla:
                raise
            return self._como_respuesta(state, por_regla)

    def _respuesta_libre_de_cotizacion(self, state: IntakeNodeInput) -> tuple[ExtractedField, ...]:
        """En la cotizacion, una respuesta corta que nadie repartio va al dato preguntado.

        Solo a los de texto libre (VIN, marca, ciudad...): los que tienen tipo --anos,
        si/no, conteos-- se quedan sin escribir si no se entienden, y se vuelven a
        preguntar. Es lo que el siniestro ya hace ("lo que le digan, que lo guarde"): a
        "¿cual es el VIN?" contestar "no lo tengo a la mano" repetia la pregunta, y un
        "no" seco si se anotaba (visto el 2026-10-08). Una pregunta de la persona no es
        una respuesta.
        """
        if state.record_type is not RecordType.QUOTE_REQUEST or "?" in state.turn_text:
            return ()
        # Si el modelo propuso datos y no pasaron la validacion, el texto no era la
        # respuesta al dato preguntado: "uso el carro a veces" no es un nombre. Y solo
        # si lo entendido es que contesta: "Pedir una cotizacion" abre la solicitud y
        # quedaba anotado como nombre del conductor (visto el 2026-10-08).
        entendido = state.understood
        if entendido is not None and (entendido.items or entendido.wants is not Want.CONTINUE):
            return ()
        if not is_short_answer(state.turn_text) or state.awaiting_confirmation is not None:
            return ()
        preguntado = _bloque_preguntado(state)
        if preguntado is None:
            return ()
        # Entre los datos preguntados juntos, solo si hay uno de texto libre: con dos, el
        # texto no dice a cual va, y eso lo reparte la IA.
        libres = [
            c
            for c in preguntado[1][: composition.QUOTE_QUESTIONS_PER_TURN]
            if c not in extraction.QUOTE_TYPED_FIELDS
        ]
        if len(libres) != 1:
            return ()
        return self._como_respuesta(state, (libres[0],))

    def _campos_por_regla(self, state: IntakeNodeInput) -> tuple[str, ...]:
        """A que campos de la pregunta pendiente va el turno, sin modelo.

        Con un solo dato pendiente, a ese. Con dos (cuando y donde), a los que el
        texto delata: una fecha u hora relativa va a `incident_datetime` y una
        calle o un lugar a `location`; si delata los dos, el texto entero queda en
        los dos, que es lo que el ajustador lee de todos modos. Sin ninguna senal,
        vacio: eso si lo reparte el modelo. Solo para los tipos cuyos bloques
        preguntan de una vez; la solicitud de cotizacion pregunta campo a campo y
        tiene sus propios tipos.
        """
        if state.record_type is RecordType.QUOTE_REQUEST:
            return ()
        preguntado = _bloque_preguntado(state)
        if preguntado is None:
            return ()
        _, faltan = preguntado
        # Un numero de poliza es identidad diga lo que diga la pregunta pendiente:
        # quien abre con "soy Marcela Rios, mi poliza es POL-21" antes de
        # contestar si hubo heridos no esta hablando de heridos. Tambien el que llego
        # incompleto («poliza Paul 201 17»): es de la poliza aunque falten cifras. Y, tras
        # pedirle que repitiera la poliza, la repeticion es la identidad aunque esta ya tenga
        # el primer intento anotado.
        identidad_anotada = state.completeness.per_field.get("identity_and_policy", False)
        if policy.heard_policy_number(state.turn_text) is not None and (
            not identidad_anotada or state.policy_repeat_asked
        ):
            return ("identity_and_policy",)
        if len(faltan) == 1:
            return _campo_unico_por_regla(faltan[0], state.turn_text, state.language)
        return tuple(
            campo
            for campo in faltan
            if _delata(campo, state.turn_text, language=state.language, now=self._clock())
        )

    def _como_respuesta(
        self, state: IntakeNodeInput, field_keys: Sequence[str]
    ) -> tuple[ExtractedField, ...]:
        """El turno entero como valor de los campos que la agente acababa de preguntar,
        con la misma evidencia y normalizacion que si lo hubiera dicho el modelo."""
        texto = state.turn_text.strip()
        return extraction.extract_fields(
            ExtractionResponse(
                items=tuple(ExtractedItem(field_key=clave, value=texto) for clave in field_keys)
            ),
            turn_id=state.turn_id,
            turn_text=state.turn_text,
            language=state.language,
            now=self._clock(),
            allowed_keys=frozenset(d.key for d in fields.definitions_for(state.record_type)),
        )

    async def _extraer(self, state: IntakeNodeInput) -> tuple[ExtractedField, ...]:
        """BR2.1 a BR2.4: lo dicho en este turno, con evidencia y normalizado."""
        prompt = extraction.build_extraction_prompt(
            self._instruction(state.language),
            state.turn_text,
            asked=_pregunta_anterior(state),
        )
        resultado = await self._extract(prompt)
        # `parsed_as` y no `text`: la extraccion se pide con esquema, asi que el
        # adaptador ya la valido y volver a parsear el texto seria validarla dos
        # veces con dos reglas distintas (`providers/ports.py`).
        return self._de_lo_entendido(state, resultado.parsed_as(ExtractionResponse))

    def _de_lo_entendido(
        self, state: IntakeNodeInput, respuesta: ExtractionResponse
    ) -> tuple[ExtractedField, ...]:
        """Los datos que dio el modelo, validados y normalizados como cualquier otro."""
        # Lo mismo que decide la regla lo decide sobre el modelo: un "si, soy yo"
        # no es un nombre ni una descripcion, aunque el modelo lo haya puesto ahi
        # (en produccion salio "Corregido: Sí, soy yo" sobre la identidad).
        # Solo en el siniestro: en una solicitud de cotizacion "no, esta limpio" o
        # "si" son respuestas de verdad a sus campos de si o no.
        if state.record_type is RecordType.CLAIM:
            respuesta = ExtractionResponse(
                items=tuple(
                    item
                    for item in respuesta.items
                    if item.field_key == "injuries"
                    or not _es_asentimiento(item.value, state.language)
                )
            )
            if not _respalda_el_dato_de_heridos(state) and any(
                item.field_key == "injuries" for item in respuesta.items
            ):
                # El modelo anoto heridos sin que la persona hablara de eso: se
                # descarta y la pregunta se hace. Es el dato de seguridad del reporte.
                observability.emit(
                    "intake.injuries_without_evidence",
                    tenant_id=state.tenant_id,
                    case_id=state.case_id,
                )
                respuesta = ExtractionResponse(
                    items=tuple(i for i in respuesta.items if i.field_key != "injuries")
                )
        return extraction.extract_fields(
            respuesta,
            turn_id=state.turn_id,
            turn_text=state.turn_text,
            language=state.language,
            now=self._clock(),
            # Solo los campos que declara el tipo de este caso: el prompt es uno para
            # todos los tipos, y el modelo puede devolver la clave de otro.
            allowed_keys=frozenset(d.key for d in fields.definitions_for(state.record_type)),
        )


#: Cuanto se espera al modelo antes de guardar el texto en el dato pendiente. Mas
#: corto que el presupuesto del turno del chat (11,5 s) a proposito: lo que se
#: ahorra es la espera de la persona, y lo que se pierde --un dato adelantado en
#: una respuesta larga-- se vuelve a preguntar en su bloque.
EXTRACTION_SOFT_TIMEOUT_S = 4.0

#: Hasta cuantas palabras es "una respuesta corta": lo que contesta una pregunta
#: sin contar otra cosa. Por encima, el modelo reparte lo que haya.
SHORT_ANSWER_MAX_WORDS = 12


def _acepta(state: IntakeNodeInput) -> bool:
    """Si la persona dijo que si a la pregunta de si o no pendiente.

    Con lo entendido por el modelo manda su lectura del sentido («la hora no, fue mas
    tarde» es un no aunque no diga «no»); sin ella, el reconocedor por frases. Lo
    que no es un si sigue siendo un no: callar no confirma.
    """
    if state.understood is not None and state.understood.answer is not Answer.NONE:
        return state.understood.answer is Answer.YES
    return confirmation.is_affirmative(state.turn_text, language=state.language)


def _acepta_la_oferta(state: IntakeNodeInput) -> bool:
    """Si quiere agregar lo que se le ofrecio al cerrar: por lo entendido, o por frases."""
    if state.understood is not None and state.understood.answer is not Answer.NONE:
        return state.understood.answer is Answer.YES
    return confirmation.accepts_offer(state.turn_text, language=state.language)


def _niega(state: IntakeNodeInput) -> bool:
    if state.understood is not None and state.understood.answer is not Answer.NONE:
        return state.understood.answer is Answer.NO
    return confirmation.is_negative(state.turn_text, language=state.language)


def _respalda_el_dato_de_heridos(state: IntakeNodeInput) -> bool:
    """Si este mensaje puede dejar anotado el dato de heridos.

    O habla de heridos (`safety_evidence`), o corrige el dato que ya habia dado, o es
    una respuesta corta a la pregunta de seguridad que la agente acababa de hacer:
    «no», «nadie», «si, dos».

    **La llamada ya no abre preguntando por heridos** (2026-10-11): abre con "¿en que
    te puedo ayudar?", asi que un "no" en su primer turno no contesta esa pregunta.
    """
    if safety_evidence.mentions_injuries(state.turn_text):
        return True
    if state.completeness.per_field.get("injuries", False):
        # Ya lo habia dicho: esto es una correccion --"perdon, no eran dos sino
        # tres"--, no un dato que el modelo se saco de la manga.
        return True
    return state.previous_block is Block.SAFETY and is_short_answer(state.turn_text)


def _bloque_preguntado(state: IntakeNodeInput) -> tuple[Block, tuple[str, ...]] | None:
    """El bloque que la agente pregunto en el turno anterior y lo que le faltaba.

    Es la misma deduccion que hizo ese turno (`blocks.next_block` sobre la
    completitud guardada), asi que no hace falta persistirla: con el mismo caso
    sale la misma pregunta. `None` cuando no habia pregunta de bloque pendiente.
    """
    bloque = blocks.next_block(state.record_type, state.completeness, state.case_state)
    if state.record_type is RecordType.QUOTE_REQUEST:
        # La solicitud pregunta por el primer bloque con datos que faltan, aunque otro
        # anterior espere su lectura: se confirma todo al final (2026-10-08).
        bloque = next(
            (
                b
                for b in blocks.order_for(state.record_type)
                if blocks.missing_fields_in_block(state.record_type, b, state.completeness)
            ),
            bloque,
        )
    if bloque not in blocks.order_for(state.record_type):
        return None
    faltan = blocks.missing_fields_in_block(state.record_type, bloque, state.completeness)
    if not faltan:
        return None
    return bloque, faltan


def _pregunta_anterior(state: IntakeNodeInput) -> str | None:
    """La pregunta que la agente hizo en el turno anterior, para el extractor."""
    preguntado = _bloque_preguntado(state)
    if preguntado is None:
        return None
    bloque, faltan = preguntado
    return composition.question_of(bloque, faltan, language=state.language)[1]


#: Lo que delata un lugar en una respuesta corta, plegado: la via, la esquina, el
#: sitio. Solo decide entre los dos campos de "cuando y donde"; no es un detector
#: de lugares general.
_PLACE_MARKERS: tuple[str, ...] = (
    "calle",
    "carrera",
    "cra ",
    "cra.",
    "avenida",
    "av ",
    "av.",
    "autopista",
    "carretera",
    "via ",
    "km ",
    "kilometro",
    "barrio",
    "parqueadero",
    "frente a",
    "esquina",
    "glorieta",
    "puente",
    "peaje",
    "en la ",
    "en el ",
    "street",
    "avenue",
    "road",
    "highway",
    "intersection",
    "parking",
    "corner",
    "exit ",
    "at the ",
    "on the ",
    "near ",
    "downtown",
)

#: Lo que delata una hora o un momento que el normalizador de fechas no resuelve.
_TIME_MARKERS: tuple[str, ...] = (
    "a las ",
    "de la manana",
    "de la tarde",
    "de la noche",
    "mediodia",
    "medianoche",
    "madrugada",
    "esta manana",
    "esta tarde",
    "esta noche",
    "anoche",
    "hace ",
    "lunes",
    "martes",
    "miercoles",
    "jueves",
    "viernes",
    "sabado",
    "domingo",
    " at ",
    "this morning",
    "this afternoon",
    "tonight",
    "last night",
    " ago",
    "o'clock",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    " am",
    " pm",
)


def _delata(field_key: str, text: str, *, language: Locale, now: date) -> bool:
    """Si el texto delata el campo: una fecha u hora para `incident_datetime`, un
    lugar para `location`. Cualquier otro campo no se delata por regla."""
    plegado = f" {fold(text)} "
    if field_key == "incident_datetime":
        if normalization.normalize_relative_date(text, language=language, now=now) is not None:
            return True
        return any(marca in plegado for marca in _TIME_MARKERS)
    if field_key == "location":
        return any(marca in plegado for marca in _PLACE_MARKERS)
    return False


#: Lo que anuncia que la persona corrige algo ya dicho, plegado (sin tildes). Una
#: correccion no contesta la pregunta pendiente sino otra anterior, y eso solo lo
#: sabe repartir el modelo: «perdon, no eran dos sino tres» con «¿que paso?»
#: pendiente es de los heridos, no de lo que paso.
_CORRECTION_MARKERS: tuple[str, ...] = (
    "perdon",
    "me equivoque",
    "no era ",
    "no eran ",
    "no fue ",
    "corrijo",
    "en realidad",
    "mejor dicho",
    "quise decir",
    "rectifico",
    "sorry",
    "i meant",
    "actually",
    "correction",
    "i was wrong",
    "it wasn't",
    "it was not",
    "not two",
)


#: Hasta cuantas palabras es un "si" o un "no" a secas.
_ACK_MAX_WORDS = 3


def _es_asentimiento(text: str, language: Locale) -> bool:
    """Un si, un no o un "soy yo" sin mas: contesta una duda, no una pregunta abierta."""
    if len(text.split()) > _ACK_MAX_WORDS:
        return False
    return confirmation.is_affirmative(text, language=language) or confirmation.is_negative(
        text, language=language
    )


#: Lo que delata que una respuesta corta habla de heridos, plegado. Un si o un no
#: tambien cuentan, porque la pregunta es de si o no.
_INJURY_MARKERS: tuple[str, ...] = (
    "herid",
    "lastim",
    "lesion",
    "golpead",
    "ambulancia",
    "hospital",
    "sangr",
    "dolor",
    "nadie",
    "ninguno",
    "ninguna",
    "todos bien",
    "todo bien",
    "estamos bien",
    "estoy bien",
    "hurt",
    "injur",
    "ambulance",
    "bleed",
    "pain",
    "nobody",
    "no one",
    "everyone",
    "fine",
    "okay",
    " ok",
)


def _campo_unico_por_regla(campo: str, text: str, language: Locale) -> tuple[str, ...]:
    """Si el unico dato pendiente se guarda por regla con este texto, o nada.

    Un "si" o un "ok" a secas contesta la pregunta de seguridad, pero a "¿que
    paso?" no contesta nada: guardarlo como lo que paso seria inventar un dato
    (visto en produccion el 2026-10-07); va al modelo, que devuelve vacio, y la
    agente vuelve a preguntar. Y a "¿hubo alguien herido?" solo se guarda por
    regla lo que habla de eso: quien contesta contando el choque va al modelo,
    que sabe que es la descripcion y no los heridos.
    """
    if campo != "injuries" and _es_asentimiento(text, language):
        return ()
    if campo == "injuries" and not _habla_de_heridos(text, language):
        return ()
    return (campo,)


def _habla_de_heridos(text: str, language: Locale) -> bool:
    """Si una respuesta corta contesta la pregunta de seguridad: un si, un no o una
    palabra de heridos. Lo demas (el relato del choque, la poliza) es otro dato."""
    if confirmation.is_affirmative(text, language=language) or confirmation.is_negative(
        text, language=language
    ):
        return True
    plegado = f" {fold(text)} "
    return any(marca in plegado for marca in _INJURY_MARKERS)


def is_short_answer(text: str) -> bool:
    """Una respuesta corta, sin pregunta y sin aire de correccion: lo que contesta
    lo que se acaba de preguntar y nada mas. Esas las resuelven reglas, sin modelo."""
    plegado = fold(text)
    if "?" in text or len(text.split()) > SHORT_ANSWER_MAX_WORDS:
        return False
    return not any(marca in plegado for marca in _CORRECTION_MARKERS)


def _con_lo_extraido(
    record_type: RecordType, completeness: Completeness, extracted: Sequence[ExtractedField]
) -> Completeness:
    """La completitud de este turno, contando lo que se acaba de extraer (BR3.3).

    No persiste nada: es la vista que necesita `next_block` para no volver a
    preguntar un dato que la persona acaba de adelantar. El campo de verdad lo
    escribe el ejecutor cuando aplica el conjunto de escritura.

    **Un campo que exige lectura de confirmacion no queda completo por haberse
    dicho**, y esa linea era la mitad del defecto del 2026-09-29. Esta funcion lo
    marcaba completo en el turno en que se extraia, asi que el nodo pasaba al
    bloque siguiente; al turno siguiente leia el caso de la base, lo encontraba
    solo `stated` --que no cuenta-- y volvia al bloque anterior. Preguntar,
    avanzar y volver: exactamente lo que se veia en pantalla.
    """
    if not extracted:
        return completeness
    exige_lectura = {
        definicion.key
        for definicion in fields.definitions_for(record_type)
        if definicion.requires_readback
    }
    por_campo: dict[str, bool] = {**completeness.per_field}
    esperando = set(completeness.awaiting_readback)
    for campo in extracted:
        if campo.field_key in exige_lectura:
            esperando.add(campo.field_key)
            por_campo[campo.field_key] = False
        else:
            por_campo[campo.field_key] = True
    return Completeness.derive(
        por_campo, awaiting_readback=frozenset(esperando), optional=completeness.optional
    )


def _con_la_confirmacion(
    completeness: Completeness, resolution: ReadbackResolution
) -> Completeness:
    """La completitud despues de resolver una lectura, sin persistir nada.

    Misma idea que la de arriba: el nodo necesita saber que bloque toca **en
    este turno**, y el caso todavia no se ha escrito. Un si deja los campos
    completos; un no los devuelve a "nadie lo dijo", que es lo que de verdad
    acaba de decir la persona.
    """
    por_campo: dict[str, bool] = {**completeness.per_field}
    esperando = set(completeness.awaiting_readback)
    for clave in resolution.fields:
        esperando.discard(clave)
        por_campo[clave] = resolution.accepted
    return Completeness.derive(
        por_campo, awaiting_readback=frozenset(esperando), optional=completeness.optional
    )


__all__ = [
    "INTAKE_SPEC",
    "ClockPort",
    "ExtractorPort",
    "InstructionPort",
    "IntakeNode",
    "IntakeNodeInput",
    "IntakeNodeOutput",
    "ReadbackResolution",
    "SessionEnd",
]
