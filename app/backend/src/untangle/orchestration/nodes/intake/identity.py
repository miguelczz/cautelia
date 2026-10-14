"""Identidad y poliza: quien es la persona y contra que caso se abre (BR1.1 a BR1.6, C-12, C-18).

**Nada de esto llama a ningun proveedor.** Identificar es consultar el corpus
de polizas de U8 (por numero o por cedula del titular) y, cuando corresponde,
abrir el caso de U4: dos lecturas y una escritura, todas deterministas.

**BR1.2 no es una rama que este archivo tenga que escribir: es una que tiene
que NO escribir.** `policy_rag.corpus.find_policy` y
`find_policy_by_national_id` ya devuelven `None` para una poliza ajena y para
una inexistente exactamente igual -- la politica de fila filtro la primera
antes de que la consulta la viera, y el codigo nunca llega a saber cual de las
dos era. `identify_by_policy_number` e `identify_by_national_id` traducen ese
`None` a un solo desenlace, `NOT_FOUND`, sin volver a mirar de cual se
trataba: anadir aqui una comprobacion "esta poliza es de otra aseguradora"
seria precisamente la rama que BR1.2 prohibe, aunque diera el mismo resultado.

**BR1.4 tampoco es una rama de este archivo.** `case_record.api.get_case` y
`get_case_by_number` ya devuelven `None` para un caso ajeno y uno inexistente
por la misma razon (la politica de fila filtra antes de que el codigo mire), y
este modulo no envuelve esas dos funciones: quien necesite leer un caso propio
las llama directo, sin que esta unidad interponga una comprobacion que ya
existe mas abajo y que solo se podria estropear repitiendola.

**Sobre BR1.5 y la relacion del tercero (corregido el 2026-09-27, revision de
la tanda 1).** La primera version de este modulo registraba al tercero con
`role=WITNESS` y escondia su relacion dentro del `CaseField` `other_parties`,
porque la decision FD-U11-5 de entonces prohibia a esta unidad crear
"ninguna entidad ni migracion" y `CaseParty` no tenia donde poner ni el rol ni
la relacion. Esa lectura dejaba AC1.4.1 sin cumplirse del todo: un testigo
puede no haber visto nada, y un tercero que reporta puede ser el propio
lesionado hablando por quien no puede -- no son el mismo rol -- y su relacion
declarada no quedaba "por escrito" en ningun sitio pensado para eso.

FD-U11-5 quedo corregida: U11 no crea entidades **nuevas**, pero si puede
**ampliar las de U4 de forma aditiva** cuando un criterio aprobado lo exige.
`u11_intake_0001_reporter_party` anadio el quinto rol, `PartyRole.REPORTER`, y
la columna `CaseParty.relation` (texto libre, anulable). `register_reporter`
registra ahora con ese rol y esa columna, y la relacion pasa por el punto
unico de redaccion de U3 antes de sellarse -- es texto que dicta la persona, y
BR2.3 exige lo mismo para cualquier texto que entra desde afuera (M6, el mismo
principio que BR4.3 en U8).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pydantic import Field

from untangle.base import Frozen, Locale
from untangle.case_record import api as case_record
from untangle.case_record import parties
from untangle.case_record.api import NewCase
from untangle.case_record.crypto import Cipher
from untangle.case_record.models import (
    CaseParty,
    Channel,
    Origin,
    PartyRole,
    RecordType,
)
from untangle.compliance.redaction.api import redact
from untangle.orchestration.nodes.intake import policy
from untangle.orchestration.nodes.intake.reporter import (
    ThirdPartyReporter as ThirdPartyReporter,
)
from untangle.orchestration.nodes.intake.reporter import (
    disclosed_fields as disclosed_fields,
)
from untangle.policy_rag.corpus.models import IssuedPolicy
from untangle.tenancy.models import TenantId

#: BR1.6: `POL-` y seis digitos. La definicion vive en `policy.py` --la hoja que el
#: ritmo del turno puede importar-- y aqui se re-exporta para quien ya la tomaba
#: de este modulo (2026-10-06, P3).
POLICY_NUMBER_PATTERN = policy.POLICY_NUMBER_PATTERN


class IdentificationOutcome(StrEnum):
    """Los tres desenlaces de identificar contra una poliza."""

    #: La poliza existe en esta aseguradora: se puede seguir.
    IDENTIFIED = "identified"
    #: BR1.2 y BR1.3 colapsados a proposito: una poliza ajena y una
    #: inexistente llegan aqui exactamente igual, y el que compone el turno
    #: (fuera de este modulo) responde con la frase de BR1.3 en los dos casos.
    NOT_FOUND = "not_found"
    #: BR1.6: el numero no tiene la forma que debe. Nunca se busca: adivinar
    #: el digito que falta podria acertar por casualidad y asociar el caso a
    #: la poliza de otra persona.
    MALFORMED = "malformed"


@dataclass(frozen=True)
class IdentificationResult:
    """Lo que devuelve identificar. `policy` solo esta cuando el desenlace es `IDENTIFIED`."""

    outcome: IdentificationOutcome
    policy: IssuedPolicy | None = None


#: Como el nodo pide la poliza, por closure desde la raiz de composicion --
#: igual que `EmbedPort` en `policy_verification` o `ClockPort` en `decision`.
#: Cablea `corpus.find_policy` o `corpus.find_policy_by_national_id` segun cual
#: de las dos funciones de mas abajo se este llamando; las dos comparten forma
#: porque las dos hacen la misma promesa (BR1.2): una poliza ajena responde
#: igual que una inexistente.
PolicyLookupPort = Callable[[TenantId, str], Awaitable[IssuedPolicy | None]]


async def identify_by_policy_number(
    tenant_id: TenantId, policy_number: str, *, lookup: PolicyLookupPort
) -> IdentificationResult:
    """BR1.2, BR1.3, BR1.6: identifica por nombre y numero de poliza.

    El nombre no se comprueba aqui -- el corpus de U8 no indexa por nombre, y
    la garantia de seguridad de BR1.2 no depende de el, solo del numero--; lo
    usa quien compone el turno para dirigirse a la persona, mas adelante.
    """
    if POLICY_NUMBER_PATTERN.match(policy_number) is None:
        # BR1.6: se pide de nuevo. Nunca se completa el digito que falta ni se
        # busca el numero mas parecido.
        return IdentificationResult(outcome=IdentificationOutcome.MALFORMED)

    poliza = await lookup(tenant_id, policy_number)
    if poliza is None:
        return IdentificationResult(outcome=IdentificationOutcome.NOT_FOUND)
    return IdentificationResult(outcome=IdentificationOutcome.IDENTIFIED, policy=poliza)


async def identify_by_national_id(
    tenant_id: TenantId, national_id: str, *, lookup: PolicyLookupPort
) -> IdentificationResult:
    """BR1.2: identifica por la cedula del titular, contra la poliza emitida.

    Sin comprobacion de forma propia: la cedula no tiene un patron unico entre
    los dos idiomas (`synthetic_data.models`, comentario de `national_id`), y
    quien de verdad decide si existe es el corpus, no una expresion regular de
    aqui.
    """
    poliza = await lookup(tenant_id, national_id)
    if poliza is None:
        return IdentificationResult(outcome=IdentificationOutcome.NOT_FOUND)
    return IdentificationResult(outcome=IdentificationOutcome.IDENTIFIED, policy=poliza)


class ReportIntent(StrEnum):
    """Lo que la persona elige en el primer turno (BR1.1)."""

    CLAIM = "claim"
    COVERAGE_INQUIRY = "coverage_inquiry"
    #: U19: pedir una cotizacion. Solo donde la aseguradora la tiene activa (BR1.5).
    QUOTE_REQUEST = "quote_request"


_RECORD_TYPE_OF: dict[ReportIntent, RecordType] = {
    ReportIntent.CLAIM: RecordType.CLAIM,
    ReportIntent.COVERAGE_INQUIRY: RecordType.COVERAGE_INQUIRY,
    ReportIntent.QUOTE_REQUEST: RecordType.QUOTE_REQUEST,
}


class OpeningRequest(Frozen):
    """Lo que hace falta para abrir un caso en el primer turno (BR1.1)."""

    case_id: str = Field(min_length=1)
    intent: ReportIntent
    channel: Channel
    origin: Origin
    language: Locale
    #: El caso del que viene este, cuando la persona cambio de tema en el chat (2026-10-13).
    continues_case_id: str | None = None


async def open_case(
    tenant_id: TenantId, request: OpeningRequest, *, now: datetime
) -> case_record.CaseView:
    """BR1.1: abre el caso en el primer turno, antes de pedir nada.

    Cual de los dos tipos se abre lo decide `request.intent`, y con el, el
    propio esquema de U4 (`case_record/schema/fields.yaml`) decide cuantos
    campos tiene el caso: un siniestro trae la pregunta de seguridad entre sus
    siete campos (AC1.5.1); una consulta de cobertura se abre con sus dos, sin
    ella (AC1.3.6) -- esta funcion no anade ni quita ningun campo, solo elige
    el tipo, y la diferencia de completitud sale sola del esquema.
    """
    return await case_record.create_case(
        tenant_id,
        NewCase(
            case_id=request.case_id,
            record_type=_RECORD_TYPE_OF[request.intent],
            channel=request.channel,
            origin=request.origin,
            language=request.language,
            continues_case_id=request.continues_case_id,
        ),
        now=now,
    )


async def register_reporter(  # noqa: PLR0913 -- seis datos del registro, ninguno derivable de otro
    tenant_id: TenantId,
    *,
    case_id: str,
    party_id: str,
    reporter: ThirdPartyReporter,
    language: Locale,
    cipher: Cipher,
) -> CaseParty:
    """BR1.5, AC1.4.1: registra al tercero que reporta, con su relacion.

    Se registra con `role=REPORTER` (`u11_intake_0001_reporter_party`,
    FD-U11-5 corregida) y solo con lo que el tercero aporto de si mismo. La
    relacion pasa por el punto unico de redaccion de U3 antes de sellarse --
    es texto que dicta la persona, y un dato personal suyo (un nombre, un
    telefono) podria colarse dentro ("es mi vecina, se llama Ana Torres") --
    y viaja sin cifrar en `CaseParty.relation`, igual que `injury_status` y
    `vehicle_description` (`parties.py`).
    """
    relacion_redactada = str(redact(reporter.relation, language=language))
    parte = parties.register_party(
        case_id=case_id,
        party_id=party_id,
        role=PartyRole.REPORTER,
        details=parties.PartyDetails(
            name=reporter.name, contact=reporter.contact, relation=relacion_redactada
        ),
        cipher=cipher,
    )
    await case_record.register_party(tenant_id, parte, cipher=cipher)
    return parte


__all__ = [
    "POLICY_NUMBER_PATTERN",
    "IdentificationOutcome",
    "IdentificationResult",
    "OpeningRequest",
    "PolicyLookupPort",
    "ReportIntent",
    "ThirdPartyReporter",
    "disclosed_fields",
    "identify_by_national_id",
    "identify_by_policy_number",
    "open_case",
    "register_reporter",
]
