"""Los tipos de U4: el caso, sus campos, sus partes, su transcripcion y su historial.

Cinco entidades se guardan y siete objetos de valor no. La proporcion es el
diseno: lo que va a la base es lo que tiene que poder consultarse, corregirse y
borrarse cada noche; lo demas existe para que un valor invalido no se pueda
escribir.

Este modulo es una **hoja**: no importa ninguna otra pieza de `case_record`. Es
lo que permite probar una regla de transicion o un calculo de completitud sin
levantar una base de datos, y lo que hace alcanzable el piso del 80 % del modulo
probando logica en vez de orquestando contenedores.

Tres detalles cargan casi todo el peso, y los tres estan aqui:

1. **Un campo lleva su evidencia, y son de dos clases** (BR2.4): el turno en que
   la persona lo dijo, o la entrada del historial si lo escribio un ajustador.
   Exactamente una, y ninguna si el campo no se ha dicho. Sin esto, "la persona
   dijo que no hubo lesionados" y "nadie pregunto" serian el mismo dato, que es
   el error que el experimento 2 encontro.
2. **El estado de un adjunto tiene tres valores, no dos** (BR6.3): `empty` dice
   que se miro y no habia; `not_evaluated` dice que no se miro. Colapsarlos
   dejaria cerrar casos que nadie reviso, y es la misma distincion que el
   proyecto ya mantiene entre "no hay clausula" y "no pude verificar".
3. **El historial guarda los rechazos** (BR5.4): una transicion que el modelo no
   permite no deja el caso intacto y en silencio, deja escrito que alguien lo
   intento.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import NewType, Self

from pydantic import Field, model_validator

from untangle.base import Frozen, Locale

# --- Identificadores ----------------------------------------------------------

#: El identificador opaco del caso. No se deriva del numero legible ni lo
#: reemplaza: el numero es lo que la persona anota y dicta, este es lo que usan
#: las ocho unidades que consumen esta.
type CaseId = str

type PartyId = str
type TurnId = str
type ChangeId = str

#: El identificador de la clave que cifro una fila (NFRD-U4-1, decision de
#: Miguel). Hoy hay una sola clave y no cambia nada. El dia que haya que rotar,
#: las filas viejas se siguen leyendo con la clave vieja y las nuevas nacen con
#: la nueva, sin una migracion que reescriba el almacen entero.
type KeyId = str

#: El valor cifrado, y el tipo que la persistencia exige en las columnas con
#: dato personal (capa 1 de `security-design.md`). Una columna que aceptara `str`
#: seria una columna sin cifrar, y por eso no acepta `str`. **Solo `crypto.py`
#: lo fabrica**, y `mise run case:constructor` falla ante cualquier otro sitio
#: que lo intente.
Sealed = NewType("Sealed", bytes)


# --- Errores ------------------------------------------------------------------


class InvalidTransitionError(RuntimeError):
    """La pareja (estado actual, estado pedido) no esta en la tabla versionada.

    Se levanta en vez de devolver el caso sin cambiar, y **el llamador no la
    captura para seguir adelante** (convencion 8b del equipo). El intento queda
    anexado al historial antes de levantarla (BR3.2, BR5.4).
    """


class CaseSchemaError(ValueError):
    """El esquema versionado no declara lo que se pidio.

    El mensaje nombra el campo y el tipo de registro. Falla en el acto en vez de
    escribir un campo que la completitud despues no sabria contar (BR1.3).
    """


class ClosingRejectedError(RuntimeError):
    """Falto un adjunto, o la resolucion no es del conjunto cerrado.

    El mensaje nombra cual. El intento queda anexado al historial como
    `close_rejected` con su detalle (BR6.3, BR5.4).
    """


# --- Enums cerrados -----------------------------------------------------------
# Ninguno de estos valores se imprime nunca hacia una persona: la etiqueta sale
# del catalogo de textos en su idioma (BR3.6, AC4.10.2). Aqui estan porque el
# modelo es cerrado y un valor fuera del conjunto tiene que ser imposible de
# escribir, no solo improbable.


class RecordType(StrEnum):
    """Los tres tipos de registro (BR1.1, ADR-005, D18)."""

    CLAIM = "claim"
    COVERAGE_INQUIRY = "coverage_inquiry"
    QUOTE_REQUEST = "quote_request"


class CaseState(StrEnum):
    """Los siete estados (BR3.1, FR1.4). `CLOSED` es terminal."""

    OPEN = "open"
    CAPTURING = "capturing"
    VERIFYING = "verifying"
    DECIDING = "deciding"
    DERIVED = "derived"
    AWAITING_INSURED = "awaiting_insured"
    CLOSED = "closed"


class Resolution(StrEnum):
    """Las cuatro resoluciones (BR3.4, AC4.10.2, D18).

    `SENT_TO_INSURER` es lo que hace siempre una agencia: coloca la poliza pero
    no cierra el siniestro, y esa diferencia vive en su configuracion.
    """

    REGISTERED = "registered"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT_TO_INSURER = "sent_to_insurer"


class DerivationReason(StrEnum):
    """Los tres motivos de derivacion (BR3.7).

    Es un conjunto **cerrado y versionado**, no texto libre, porque la regla de
    la vuelta atras lo **lee**: un modelo declarado cerrado cuya condicion
    dependiera de una cadena que nadie controla no seria cerrado. Anadir un
    cuarto motivo es un cambio a esta lista, igual que a la tabla de
    transiciones.
    """

    DEMO_LIMIT = "demo_limit"
    PERSON_REQUESTED = "person_requested"
    RULE = "rule"


class Priority(StrEnum):
    """La prioridad del caso. `HIGH` cuando se derivo por peticion de persona (BR3.8)."""

    NORMAL = "normal"
    HIGH = "high"


class Channel(StrEnum):
    """Voz o chat. El del caso es por donde nacio; el del turno, por donde entro ese turno."""

    VOICE = "voice"
    CHAT = "chat"


class Origin(StrEnum):
    """De donde salio el caso (BR4.5, AC4.10.4).

    Decide que borra el reinicio nocturno: los dos primeros son dato de
    visitante, los dos ultimos no (BR4.6).
    """

    PUBLIC_CHAT = "public_chat"
    PUBLIC_VOICE_CONSOLE = "public_voice_console"
    LOCAL_DEPLOYMENT = "local_deployment"
    GENERATOR = "generator"


#: Los origenes que son dato de visitante. Se declara como conjunto y no como
#: comparacion suelta para que anadir un origen publico obligue a decidir aqui
#: si se borra, en vez de olvidarlo en un `if` a mitad de un archivo.
VISITOR_ORIGINS: frozenset[Origin] = frozenset({Origin.PUBLIC_CHAT, Origin.PUBLIC_VOICE_CONSOLE})


class FieldStatus(StrEnum):
    """Los tres estados de un campo (BR2.1, ADR-005).

    `NOT_STATED` no es "vacio": es "nadie lo dijo", y esa diferencia con
    `STATED` valor "ninguno" es lo que impide que el modelo invente un dato de
    seguridad (BR2.3).
    """

    NOT_STATED = "not_stated"
    STATED = "stated"
    CONFIRMED = "confirmed"


class PartyRole(StrEnum):
    """Los cinco roles del grupo repetible (BR1.7, FR1.2).

    `REPORTER` se anadio con `u11_intake_0001_reporter_party` (FD-U11-5,
    correccion del 2026-09-27): quien reporta por otro no es un testigo -- un
    testigo puede no haber visto nada, y un reportante puede ser el propio
    lesionado hablando por quien no puede -- y antes de esa migracion no habia
    ningun rol que dijera lo que de verdad era (BR1.5, AC1.4.1).
    """

    INJURED = "injured"
    WITNESS = "witness"
    OTHER_DRIVER = "other_driver"
    OTHER_VEHICLE = "other_vehicle"
    REPORTER = "reporter"


class Speaker(StrEnum):
    """Quien habla en un turno de la transcripcion."""

    INSURED = "insured"
    AGENT = "agent"
    STAFF = "staff"


class ActorType(StrEnum):
    """Quien hace un cambio (BR5.2)."""

    INSURED = "insured"
    AGENT = "agent"
    STAFF = "staff"
    SYSTEM = "system"


class ChangeKind(StrEnum):
    """Las seis clases de entrada del historial (BR5.1, BR5.4).

    `TRANSITION_REJECTED` y `CLOSE_REJECTED` existen porque un rechazo que no
    deja rastro es indistinguible de un intento que nadie hizo. El quinto valor
    existe por la misma razon, leida al reves: una version que **no** se acepto
    anotada como `FIELD_SET` es indistinguible de un campo que si cambio, y
    quien lea el historial creeria que el caso guarda el segundo valor cuando
    guarda el primero (BR5.5 de U11, FD-U11-7).
    """

    FIELD_SET = "field_set"
    #: U11, BR5.5: una segunda version de un campo ya confirmado, anotada sin
    #: reemplazarlo. El valor del caso sigue siendo el primero confirmado.
    FIELD_VERSION_ALTERNATE = "field_version_alternate"
    #: La bandeja: un ajustador anoto, cambio o quito un dato que leen las reglas de triage
    #: (monto estimado, cobertura disputada, sospecha de fraude). Lleva el nombre del dato
    #: como `field_key` y, en `detail`, el valor de antes y el de ahora. **No es un
    #: `FIELD_SET`**: ese dice que un campo del esquema del caso se fijo, y estos datos no
    #: son del esquema --no cuentan para la completitud ni los cuenta la persona--.
    TRIAGE_NOTED = "triage_noted"
    TRANSITION_APPLIED = "transition_applied"
    TRANSITION_REJECTED = "transition_rejected"
    CLOSE_REJECTED = "close_rejected"


#: Las clases que nombran un dato. El resto no lleva ninguno.
KINDS_WITH_FIELD: tuple[ChangeKind, ...] = (
    ChangeKind.FIELD_SET,
    ChangeKind.FIELD_VERSION_ALTERNATE,
    ChangeKind.TRIAGE_NOTED,
)


class AttachmentKind(StrEnum):
    """El estado de uno de los cinco adjuntos del cierre (BR6.3).

    `EMPTY` se miro y no habia. `NOT_EVALUATED` no se miro. Nunca se colapsan:
    colapsarlos dejaria cerrar un caso que nadie reviso.
    """

    PRESENT = "present"
    EMPTY = "empty"
    NOT_EVALUATED = "not_evaluated"


# --- Objetos de valor: no se guardan como tabla propia ------------------------


class CaseNumber(Frozen):
    """El numero legible: las dos iniciales de la aseguradora, guion y un contador.

    Los tres prefijos de la demostracion son `SA` (Seguros Aburra), `AP` (Autos
    Poblado) y `AC` (Agencia Castilla), y el contador empieza en 1 por aseguradora
    y no lleva ceros a la izquierda: `SA-1`, `AP-29`. Decision de Miguel del
    2026-10-30, que reemplaza las tres letras y los seis digitos al azar.

    El prefijo sale de la configuracion de la aseguradora, nunca de una tabla en
    el codigo (BR4.1): escribirlo aqui seria la ramificacion por inquilino que el
    proyecto prohibe.
    """

    prefix: str = Field(pattern=r"^[A-Z]{2}$")
    serial: str = Field(pattern=r"^[1-9]\d{0,5}$")

    def __str__(self) -> str:
        return f"{self.prefix}-{self.serial}"


class AttachmentState(Frozen):
    """El estado de un adjunto, con su referencia cuando la hay."""

    kind: AttachmentKind
    reference: str | None = None

    @model_validator(mode="after")
    def _referencia_solo_si_presente(self) -> Self:
        if self.kind is AttachmentKind.PRESENT and not self.reference:
            msg = "un adjunto presente tiene que traer la referencia por la que se recupera"
            raise ValueError(msg)
        if self.kind is not AttachmentKind.PRESENT and self.reference:
            msg = f"un adjunto '{self.kind}' no lleva referencia: no hay nada que recuperar"
            raise ValueError(msg)
        return self


class ClosingEvidence(Frozen):
    """Los cinco adjuntos de FR1.7, cada uno con su estado.

    Se guarda **con el caso** y no se comprueba y se olvida (NFR-U4-9): un caso
    cerrado expone que se comprobo al cerrarlo.
    """

    transcript: AttachmentState
    cited_clauses: AttachmentState
    fired_rules: AttachmentState
    trace_id: AttachmentState
    control_results: AttachmentState

    @property
    def complete(self) -> bool:
        """Cierra si ninguno esta sin evaluar. Un conjunto vacio cuenta como presente."""
        return all(
            adjunto.kind is not AttachmentKind.NOT_EVALUATED
            for adjunto in (
                self.transcript,
                self.cited_clauses,
                self.fired_rules,
                self.trace_id,
                self.control_results,
            )
        )

    def missing(self) -> tuple[str, ...]:
        """Los adjuntos sin evaluar, por nombre, para el mensaje del rechazo."""
        return tuple(
            nombre
            for nombre, adjunto in (
                ("transcript", self.transcript),
                ("cited_clauses", self.cited_clauses),
                ("fired_rules", self.fired_rules),
                ("trace_id", self.trace_id),
                ("control_results", self.control_results),
            )
            if adjunto.kind is AttachmentKind.NOT_EVALUATED
        )


class Completeness(Frozen):
    """La completitud, por campo y total, segun el tipo de registro del caso.

    Se **deriva** de los campos y no se guarda como numero suelto (BR2.8): un
    numero guardado es un numero que alguien puede escribir a mano.
    """

    per_field: dict[str, bool]
    #: Los campos que alguien **ya dijo** y que todavia no cuentan, porque su
    #: definicion exige leerlos en voz alta y nadie los ha confirmado.
    #:
    #: **Sin esto, `per_field` no puede distinguir "nadie lo dijo" de "lo dijo y
    #: falta confirmarlo"**, y esa es exactamente la diferencia que separa
    #: preguntar de leer de vuelta. Un booleano que colapsa las dos dejaba a la
    #: captura volviendo a preguntar lo ya contestado, para siempre: el campo
    #: nunca contaba, el bloque nunca terminaba y la agente repetia la pregunta.
    #: Lo vio Miguel usando el chat el 2026-09-29.
    #:
    #: Es aditivo a proposito: `per_field` sigue significando "cuenta como
    #: completo" y ningun consumidor suyo cambia.
    awaiting_readback: frozenset[str] = frozenset()
    #: Los campos **opcionales** del tipo (P4, decision de Miguel del 2026-10-06):
    #: estan en el mapa, para que la captura sepa si se dijeron, pero no cuentan
    #: ni en `total` ni en `complete`. Un siniestro queda listo para el ajustador
    #: con sus cuatro datos centrales; el vehiculo y las otras partes se ofrecen
    #: al final y se anotan si la persona quiere.
    optional: frozenset[str] = frozenset()
    complete: int = Field(ge=0)
    total: int = Field(ge=0)

    @classmethod
    def derive(
        cls,
        per_field: dict[str, bool],
        *,
        awaiting_readback: frozenset[str] = frozenset(),
        optional: frozenset[str] = frozenset(),
    ) -> Completeness:
        """La completitud con sus dos cifras **calculadas del mapa**, que es la
        unica forma de construirla que no puede desencajar (BR2.8)."""
        obligatorios = {clave: listo for clave, listo in per_field.items() if clave not in optional}
        return cls(
            per_field=per_field,
            awaiting_readback=awaiting_readback,
            optional=optional,
            complete=sum(1 for listo in obligatorios.values() if listo),
            total=len(obligatorios),
        )

    @model_validator(mode="after")
    def _la_cuenta_cuadra(self) -> Self:
        obligatorios = {c: v for c, v in self.per_field.items() if c not in self.optional}
        if self.total != len(obligatorios):
            msg = (
                f"la completitud dice {self.total} campos y el mapa trae "
                f"{len(obligatorios)} obligatorios: la cifra tiene que salir del mapa"
            )
            raise ValueError(msg)
        if self.complete != sum(1 for listo in obligatorios.values() if listo):
            msg = "la cifra de campos completos no coincide con el mapa del que sale"
            raise ValueError(msg)
        # Un campo no puede estar completo y a la vez esperando su lectura: si
        # lo estuviera, el bloque se daria por terminado y la lectura no llegaria
        # a decirse nunca, que es el defecto de partida con otra forma.
        contados = {clave for clave in self.awaiting_readback if self.per_field.get(clave, False)}
        if contados:
            msg = (
                f"los campos {sorted(contados)} cuentan como completos y a la vez "
                "esperan su lectura de confirmacion: son estados excluyentes"
            )
            raise ValueError(msg)
        return self

    def __str__(self) -> str:
        return f"{self.complete}/{self.total}"


class Actor(Frozen):
    """Quien hace un cambio. Una correccion con credencial apunta a su persona (BR5.2)."""

    actor_type: ActorType
    actor_id: str | None = None

    @model_validator(mode="after")
    def _el_personal_se_identifica(self) -> Self:
        if self.actor_type is ActorType.STAFF and not self.actor_id:
            msg = "una correccion hecha con credencial tiene que apuntar a quien la hizo"
            raise ValueError(msg)
        return self


class FieldDefinition(Frozen):
    """Una fila del esquema versionado: un campo de un tipo de registro (BR1.3)."""

    key: str
    requires_readback: bool
    source_block: str
    #: Opcional: se ofrece al final y no cuenta para la completitud (P4,
    #: decision de Miguel del 2026-10-06). Por omision, obligatorio.
    optional: bool = False


class Transition(Frozen):
    """Una fila de la tabla versionada de transiciones (BR3.2)."""

    id: str
    from_state: CaseState
    to_state: CaseState
    when: str
    conditions: tuple[str, ...] = ()


# --- Lo que se guarda ---------------------------------------------------------


class CaseField(Frozen):
    """Un campo del caso: lo que se dijo, cuan seguro esta y **que lo respalda**.

    La evidencia es la mitad del punto. Son dos clases y exactamente una
    (BR2.4): el turno en que se dijo, o la entrada del historial si lo escribio
    una persona desde la bandeja (BR2.5, decision FD-U4-3 de Miguel).
    """

    case_id: CaseId
    field_key: str
    #: Sellado, no en claro. Lo que el asegurado dijo --su direccion, la
    #: descripcion del accidente, su telefono-- es dato personal igual que el
    #: nombre del testigo, y SEC-U4.8 los cifra a los dos antes de persistir. El
    #: tipo es lo que lo impone: una columna que aceptara `str` seria una columna
    #: sin cifrar. La completitud y las transiciones no necesitan abrirlo: leen
    #: `status`, no el valor.
    value: Sealed | None = None
    status: FieldStatus = FieldStatus.NOT_STATED
    evidence_turn_id: TurnId | None = None
    evidence_change_id: ChangeId | None = None
    confirmed_aloud_at: datetime | None = None
    updated_at: datetime

    @model_validator(mode="after")
    def _la_evidencia_es_exactamente_una(self) -> Self:
        evidencias = [self.evidence_turn_id, self.evidence_change_id]
        presentes = sum(1 for e in evidencias if e is not None)

        if self.status is FieldStatus.NOT_STATED:
            if presentes:
                msg = "un campo no dicho no lleva evidencia: no hay nada que respaldar"
                raise ValueError(msg)
            if self.value is not None:
                msg = "un campo no dicho no lleva valor (BR2.3)"
                raise ValueError(msg)
            return self

        if presentes != 1:
            msg = (
                f"un campo '{self.status}' lleva exactamente una evidencia, "
                f"y este lleva {presentes} (BR2.4)"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _la_marca_de_lectura_va_con_el_turno(self) -> Self:
        if self.confirmed_aloud_at and self.evidence_change_id:
            msg = (
                "un campo corregido desde la bandeja no lleva marca de lectura "
                "en voz alta: no hubo conversacion (BR2.5)"
            )
            raise ValueError(msg)
        return self


class CaseParty(Frozen):
    """Una persona o un vehiculo mas del accidente (BR1.7, FR1.2).

    Un atributo que no se sabe queda vacio y es un **dato pendiente**, nunca un
    valor supuesto (BR1.8, AC1.8.2).
    """

    party_id: PartyId
    case_id: CaseId
    role: PartyRole
    name: Sealed | None = None
    contact: Sealed | None = None
    injury_status: str | None = None
    vehicle_description: str | None = None
    plate: Sealed | None = None
    plate_status: FieldStatus = FieldStatus.NOT_STATED
    plate_evidence_turn_id: TurnId | None = None
    statement_version: str | None = None
    #: La relacion de quien reporta con el asegurado ("vecino", "hijo del
    #: asegurado"), anadida por `u11_intake_0001_reporter_party` (FD-U11-5,
    #: AC1.4.1). Texto libre, ya redactado por U3 antes de persistirse (M6) --
    #: no cifrado: se une a `injury_status` y `vehicle_description` en el lado
    #: de fuera de `case_party_clave_con_valor`, no al de `name`/`contact`/
    #: `plate`.
    relation: str | None = None

    @model_validator(mode="after")
    def _la_placa_lleva_su_evidencia(self) -> Self:
        if self.plate_status is FieldStatus.NOT_STATED:
            if self.plate is not None or self.plate_evidence_turn_id is not None:
                msg = "una placa no dicha no lleva valor ni evidencia"
                raise ValueError(msg)
        elif self.plate_evidence_turn_id is None:
            msg = f"una placa '{self.plate_status}' lleva el turno que la respalda (AC1.8.3)"
            raise ValueError(msg)
        return self


class TranscriptTurn(Frozen):
    """Un turno de la conversacion, guardado **ya redactado** (BR6.1, C-13).

    El campo es `str` y no el tipo redactado de U3, y la razon es de costo:
    importar ese tipo trae la maquinaria de redaccion entera --medio segundo
    frente a los cincuenta milisegundos que cuesta este modulo-- y este modulo
    es la hoja que permite probar una regla de transicion sin levantar nada.

    Quien exige el tipo es la puerta: `transcript.append` pide un valor
    redactado, y ese tipo solo lo fabrica `compliance/redaction/api.py` --lo
    comprueba `mise run redaction:constructor`--, asi que no hay forma de anexar
    un turno sin redactar pasando por donde se anexan los turnos. Construir este
    tipo a mano con texto crudo si es posible, y por eso la superficie publica
    del modulo no ofrece esa via (SEC-U4.6).
    """

    turn_id: TurnId
    case_id: CaseId
    speaker: Speaker
    channel: Channel
    language: Locale
    text_redacted: str
    started_at: datetime
    ended_at: datetime | None = None
    interrupted: bool = False


class CaseChange(Frozen):
    """Una entrada del historial, incluidos los intentos rechazados (BR5.1, BR5.4).

    Es de **solo anexar** (BR5.3): no existe operacion que edite ni borre una
    entrada, y el borrado del reinicio nocturno borra el caso entero, no una
    entrada suelta.
    """

    change_id: ChangeId
    case_id: CaseId
    change_kind: ChangeKind
    field_key: str | None = None
    #: Las dos van selladas por la misma razon que el campo: **son copias suyas**.
    #: Dejarlas en claro desharia el cifrado para todo lo que alguna vez se
    #: corrigio, que es justo el dato que mas veces se toco y el que un volcado
    #: mas facilmente delata. El historial seria la fuga por la puerta de atras.
    previous_value: Sealed | None = None
    new_value: Sealed | None = None
    actor: Actor
    channel: Channel | None = None
    detail: str | None = None
    changed_at: datetime

    @model_validator(mode="after")
    def _el_campo_va_con_su_clase(self) -> Self:
        if self.change_kind in KINDS_WITH_FIELD:
            if not self.field_key:
                msg = "un cambio de campo nombra el campo que cambio"
                raise ValueError(msg)
        elif self.field_key:
            msg = f"una entrada '{self.change_kind}' no lleva campo: no cambio ninguno"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _un_rechazo_dice_que_se_intento(self) -> Self:
        rechazos = (ChangeKind.TRANSITION_REJECTED, ChangeKind.CLOSE_REJECTED)
        if self.change_kind in rechazos and not self.detail:
            msg = (
                "un rechazo lleva su detalle: sin el, el historial dice que algo "
                "se rechazo pero no que se intento (BR5.4)"
            )
            raise ValueError(msg)
        return self


class Case(Frozen):
    """El caso: la raiz, y la fuente de verdad del negocio.

    El punto de control del grafo guarda la ejecucion reanudable, no el caso; si
    los dos se contradijeran, manda el caso (enmienda de ADR-005).
    """

    case_id: CaseId
    tenant_id: str
    case_number: CaseNumber
    record_type: RecordType
    state: CaseState = CaseState.OPEN
    resolution: Resolution | None = None
    channel: Channel
    origin: Origin
    language: Locale
    policy_ref: str | None = None
    derivation_reason: DerivationReason | None = None
    #: En que turno de la conversacion salio la frase de derivacion. `None` cuando
    #: la derivacion no ocurrio en un turno --el boton de la consola de voz, la
    #: bandeja-- y es lo que deja a la revision de cumplimiento acotarse hasta ahi
    #: en vez de adivinar (BR5.1 de U10).
    derived_turn_id: TurnId | None = None
    #: El caso del que viene este, cuando la persona cambio de tema en mitad de una
    #: conversacion (2026-10-13). Se escribe al crear el caso y no cambia: la conversacion
    #: se lee a traves de la cadena, sin copiar turnos. Un caso anterior que se borra deja
    #: este valor en `None` (la base lo impone), asi que nunca apunta a nada que no exista.
    continues_case_id: CaseId | None = None
    priority: Priority = Priority.NORMAL
    closing_evidence: ClosingEvidence | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None

    @model_validator(mode="after")
    def _cerrado_lleva_sus_tres_cosas(self) -> Self:
        cerrado = self.state is CaseState.CLOSED
        tiene = (
            self.resolution is not None,
            self.closed_at is not None,
            self.closing_evidence is not None,
        )
        if cerrado and not all(tiene):
            msg = (
                "un caso cerrado lleva resolucion, momento de cierre y evidencia "
                "de cierre, las tres (BR3.4, BR6.4)"
            )
            raise ValueError(msg)
        if not cerrado and any(tiene):
            msg = "un caso que no esta cerrado no lleva resolucion ni cierre (BR3.5)"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _derivado_lleva_su_motivo(self) -> Self:
        derivado = self.state is CaseState.DERIVED
        if derivado and self.derivation_reason is None:
            msg = "un caso derivado lleva su motivo del conjunto cerrado (BR3.7)"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _el_turno_de_la_derivacion_es_de_un_caso_derivado(self) -> Self:
        """Un caso que no se derivo no tiene turno de derivacion.

        No es simetrico con el motivo: el motivo es **obligatorio** al derivar y el
        turno no --hay derivaciones que no ocurren en un turno-- pero un turno de
        derivacion en un caso que nunca se derivo seria un dato que contradice el
        estado, y la revision lo creeria.

        **Un caso cerrado lo conserva** (2026-10-11): se cierra desde derivado, y el
        turno en que se derivo es su historia, igual que el motivo. Hasta entonces
        esta regla rechazaba el caso ya cerrado y **decidir cualquier caso derivado
        en una conversacion fallaba con un error interno**: el recorrido principal
        de la demo, "decidir este caso como ajustador".
        """
        if self.derived_turn_id is not None and self.state not in (
            CaseState.DERIVED,
            CaseState.CLOSED,
        ):
            msg = (
                "un caso que no esta derivado no lleva turno de derivacion: "
                f"'{self.case_id}' esta en '{self.state.value}'"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _quien_pidio_una_persona_va_con_prioridad_alta(self) -> Self:
        """BR3.8. La unica regla que ata un motivo a una prioridad.

        Se impone en el tipo y no se deja al criterio de quien deriva: alguien
        que pide hablar con una persona ya pidio ayuda una vez, y que su caso
        quede detras de otros en la bandeja es exactamente el fallo que se
        siente como que no lo escucharon.
        """
        pidio_persona = self.derivation_reason is DerivationReason.PERSON_REQUESTED
        if pidio_persona and self.priority is not Priority.HIGH:
            msg = (
                "un caso derivado porque la persona pidio hablar con alguien "
                "lleva prioridad alta (BR3.8)"
            )
            raise ValueError(msg)
        return self

    @property
    def is_visitor_data(self) -> bool:
        """Si el reinicio nocturno lo borra (BR4.6, NFR19.2)."""
        return self.origin in VISITOR_ORIGINS
