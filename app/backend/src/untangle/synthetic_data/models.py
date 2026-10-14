"""La forma de todo lo que el generador lee y escribe (U7, `entities.md`, C-26).

Tres familias, y cada una vive donde vive por una razon:

- **Entrada revisada** (`SourceFile`, `SourceText`, `ReviewSample`): lo que esta
  versionado en `app/data/sources/`. Un texto sin marca de revision no pasa de
  aqui (BR2.2).
- **Salida versionada** (`FormRecord`, `ClauseFile`, `ClauseRelationFile`,
  `IssuedPolicyRecord`, `SeededCaseRecord` y el manifiesto): lo que ingiere U8 y
  carga la siembra. Sus JSON Schema se generan a `app/contracts/schemas/` (C-28).
- **Borrador** (`DraftResponse`, `DraftText`): lo que devuelve el modelo al
  redactar. Nunca se versiona y la composicion no lo lee (BR2.1).

## Lo que se valida aqui y lo que no

Aqui se valida todo lo que se puede decir **mirando un solo objeto**: la forma
de un identificador, que un distractor diga con que se confunde, que un telefono
este en el rango ficticio. Lo que exige mirar varios --que un endoso exista, que
un identificador no se repita entre dos archivos, que la `example_policy` de cada
aseguradora exista-- lo valida quien tiene el conjunto: el cargador de fuentes y
la composicion.

## Sin identificadores de aseguradora en el codigo

`entities.md` dice que un texto fuente es de Stonecroft o de Sunmeadow. Esa lista
**no se escribe aqui**: el modelo solo exige la forma de un identificador, y el
cargador comprueba contra la configuracion versionada de `app/config/tenants/`
que la aseguradora exista y sea una emisora (regla de `project.md`).

## Los estados del caso, copiados a proposito

`SeededState`, `SeededResolution` y `SeededSpeaker` repiten los valores de
`case_record.models`. No se importan porque este paquete esta **debajo** del
registro del caso en el contrato de capas, que es lo que deja a U8 leer estos
modelos. La copia no se queda sola: una prueba compara las dos listas y falla si
un dia dicen cosas distintas.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date
from enum import StrEnum
from typing import Annotated, Final, Literal, Self

from pydantic import AfterValidator, Field, field_validator, model_validator

from untangle.base import Frozen, Locale
from untangle.tenancy.models import TENANT_ID_PATTERN

__all__ = [
    "CASE_TURNS_FILE_KEY",
    "CLAUSE_KEY_PATTERN",
    "DATA_PREFIX",
    "DIFFERENCES_FILE",
    "FORM_ID_PATTERN",
    "MANIFEST_OUTPUT",
    "MANIFEST_VERSION",
    "PERSONAL_VALUES_OUTPUT",
    "POLICY_NUMBER_PATTERN",
    "POOLS_FILE_KEY",
    "REVIEW_SAMPLE_SIZE",
    "SEEDED_CRITERIA_FILE",
    "SOURCES_PREFIX",
    "ClauseFile",
    "ClauseRecord",
    "ClauseRelationFile",
    "ClauseRelationRecord",
    "DeclaredDifference",
    "DifferenceFile",
    "DifferenceSource",
    "DistractorReason",
    "DraftClause",
    "DraftClauseKind",
    "DraftResponse",
    "DraftText",
    "DriverRef",
    "FingerprintSet",
    "FingerprintSource",
    "FormKind",
    "FormRecord",
    "GenerationManifest",
    "IssuedPolicyRecord",
    "PersonaRef",
    "PersonalValue",
    "PersonalValueKind",
    "PersonalValueList",
    "PolicyPart",
    "RelationKind",
    "ReviewSample",
    "ReviewVerdict",
    "ReviewedBy",
    "SeededCaseRecord",
    "SeededCaseRef",
    "SeededCaseSpec",
    "SeededChannel",
    "SeededCriteriaFile",
    "SeededCriterion",
    "SeededDerivationReason",
    "SeededField",
    "SeededFieldStatus",
    "SeededRecordType",
    "SeededResolution",
    "SeededSpeaker",
    "SeededState",
    "SeededTurn",
    "SourceEntry",
    "SourceFile",
    "SourceKind",
    "SourceText",
    "VehicleRef",
    "form_id_of",
    "parse_turns",
    "pool_items",
    "vin_check_digit",
]

# --- Las formas de los identificadores ----------------------------------------

#: Un formulario: el prefijo de tres letras de la aseguradora (el de sus numeros
#: de caso, FD-U7-1), la familia (`PAP` la poliza, `JUR` el documento de
#: jurisdiccion) y el ano de su edicion; un endoso anade `-END-<n>`.
#: Por ejemplo `STO-PAP-2026`, `STO-PAP-2026-END-3` o `SUN-JUR-2026`.
FORM_ID_PATTERN: Final = r"^[A-Z]{3}-[A-Z]{3}-\d{4}(?:-END-[1-9]\d*)?$"

#: La numeracion estructural de la referencia: `A.EXCL.A.3`, `D.INS.COLLISION`,
#: `F.FRAUD`. Es estructura, no texto (P8).
CLAUSE_KEY_PATTERN: Final = r"^[A-Za-z0-9]+(?:\.[A-Za-z0-9_]+)*$"

#: Una clausula: el formulario, un guion y su numeracion (BR3.2).
CLAUSE_ID_PATTERN: Final = (
    r"^[A-Z]{3}-[A-Z]{3}-\d{4}(?:-END-[1-9]\d*)?-[A-Za-z0-9]+(?:\.[A-Za-z0-9_]+)*$"
)

#: `AAAA.n`: el ano de la edicion y su numero dentro del ano (BR3.2).
VERSION_PATTERN: Final = r"^\d{4}\.[1-9]\d*$"

#: `POL-` y seis digitos, sin iniciales de la aseguradora (decision del
#: 2026-09-20): dos aseguradoras pueden repetir numero a proposito (DS-8).
POLICY_NUMBER_PATTERN: Final = r"^POL-\d{6}$"

#: Un repertorio de datos ficticios: `<prefijo>-POOL-<nombre>`.
POOL_SOURCE_ID_PATTERN: Final = r"^[A-Z]{3}-POOL-[A-Z0-9]+(?:-[A-Z0-9]+)*$"

#: Los turnos de un caso sembrado: `<prefijo>-CASE-<nombre>` (FD-U7-7).
CASE_SOURCE_ID_PATTERN: Final = r"^[A-Z]{3}-CASE-[A-Z0-9]+(?:-[A-Z0-9]+)*$"

#: El nombre de un caso sembrado dentro de su aseguradora e idioma: la ultima
#: parte de su `case_key` (BR6.2).
CASE_NAME_PATTERN: Final = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"

#: El modelo que redacto, por identificador exacto, o `hand` si se escribio a
#: mano (CG-U7-2).
DRAFTED_WITH_PATTERN: Final = r"^[a-z0-9][a-z0-9.\-]*$"

#: `SEED/<aseguradora>/<idioma>/<nombre>`, estable entre generaciones (BR6.2).
CASE_KEY_PATTERN: Final = r"^SEED/[a-z][a-z0-9-]{1,30}/(?:es|en)/[a-z0-9]+(?:-[a-z0-9]+)*$"

#: Un criterio de aceptacion (`AC5.6.2`).
AC_ID_PATTERN: Final = r"^AC\d+\.\d+\.\d+$"

SHA256_PATTERN: Final = r"^[0-9a-f]{64}$"

#: Un identificador libre y estable (una persona ficticia, una diferencia).
IDENTIFIER_PATTERN: Final = r"^[a-z0-9][a-z0-9-]*$"

#: Una clave de campo o de limite: `incident.datetime`, `a.bodily_injury`.
FIELD_KEY_PATTERN: Final = r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*$"

#: Las dos familias de formulario. Son vocabulario del generador, no de ninguna
#: aseguradora: todas tienen su poliza y su documento de jurisdiccion.
POLICY_FAMILY: Final = "PAP"
JURISDICTION_FAMILY: Final = "JUR"

#: Donde vive la salida, como ruta logica desde la raiz del repositorio. El
#: manifiesto nombra las salidas asi aunque se generen en un directorio temporal:
#: por eso sus bytes no dependen de donde se escribieron (BR1.1).
DATA_PREFIX: Final = "app/data/"
SOURCES_PREFIX: Final = "app/data/sources/"
MANIFEST_OUTPUT: Final = "app/data/manifest.json"
MANIFEST_VERSION: Final = 1

#: El archivo de fuentes que guarda los repertorios de datos ficticios.
POOLS_FILE_KEY: Final = "pools"

#: El archivo de fuentes que guarda los turnos de los casos sembrados (FD-U7-7).
CASE_TURNS_FILE_KEY: Final = "case_turns"

#: Los dos archivos de fuentes que no son de una aseguradora: las diferencias
#: declaradas entre emisoras (BR3.7) y los criterios que parten de un caso
#: sembrado (BR6.2). Viven en la raiz de `app/data/sources/`.
DIFFERENCES_FILE: Final = "differences.yaml"
SEEDED_CRITERIA_FILE: Final = "seeded_criteria.yaml"

#: La lista de valores personales ficticios que siembra el generador (FD-U7-8).
PERSONAL_VALUES_OUTPUT: Final = "app/data/personal_values.json"

#: Cuantas clausulas revisa Miguel por emisora (BR5.4).
REVIEW_SAMPLE_SIZE: Final = 10

_FORM_ID = re.compile(FORM_ID_PATTERN)


def _texto_no_vacio(valor: str) -> str:
    if not valor.strip():
        msg = "el texto esta vacio o solo tiene espacios"
        raise ValueError(msg)
    return valor


# Alias simples y no `type ...`: un alias de PEP 695 se publica como una entrada
# propia de `$defs` en el JSON Schema, y el esquema que se pide al modelo en la
# redaccion tiene que ser lo mas plano posible.
TenantIdStr = Annotated[str, Field(pattern=TENANT_ID_PATTERN)]
FormIdStr = Annotated[str, Field(pattern=FORM_ID_PATTERN)]
ClauseIdStr = Annotated[str, Field(pattern=CLAUSE_ID_PATTERN)]
ClauseKeyStr = Annotated[str, Field(pattern=CLAUSE_KEY_PATTERN)]
VersionStr = Annotated[str, Field(pattern=VERSION_PATTERN)]
Sha256Str = Annotated[str, Field(pattern=SHA256_PATTERN)]
FieldKeyStr = Annotated[str, Field(pattern=FIELD_KEY_PATTERN)]
AcIdStr = Annotated[str, Field(pattern=AC_ID_PATTERN)]
NonNegativeInt = Annotated[int, Field(ge=0)]
#: Texto de una clausula o de un turno: no vacio y no solo espacios.
NonBlankText = Annotated[str, Field(min_length=1), AfterValidator(_texto_no_vacio)]


def form_id_of(clause_id: str, clause_key: str) -> str:
    """El formulario de una clausula: su identificador sin `-<numeracion>`.

    Se calcula desde la numeracion y no partiendo por guiones: `STO-PAP-2026-END-3`
    tiene cuatro guiones y un corte por el ultimo daria un formulario inexistente.
    """
    sufijo = f"-{clause_key}"
    if not clause_id.endswith(sufijo):
        msg = f"'{clause_id}' no termina en su numeracion '{clause_key}'"
        raise ValueError(msg)
    return clause_id[: -len(sufijo)]


def _familia(form_id: str) -> str:
    return form_id.split("-")[1]


def _ano(form_id: str) -> str:
    return form_id.split("-")[2]


def _es_endoso(form_id: str) -> bool:
    return "-END-" in form_id


def _sin_repetidos(valores: tuple[str, ...], que: str) -> None:
    repetidos = sorted(v for v, veces in Counter(valores).items() if veces > 1)
    if repetidos:
        msg = f"{que} repetidos: {', '.join(repetidos)}"
        raise ValueError(msg)


# --- Los vocabularios cerrados ------------------------------------------------


class PolicyPart(StrEnum):
    """Las partes que se redactan y se versionan, una por archivo (`DraftText.part`).

    Las ocho primeras son las secciones de la referencia de estructura
    (`docs/reference/estructura-poliza-iso-pap.md`); las dos ultimas son las
    piezas que la referencia no trae y el corpus si: los endosos y el documento
    de jurisdiccion de cada emisora.
    """

    AGREEMENT = "agreement"
    DEFINITIONS = "definitions"
    PART_A = "part_a"
    PART_B = "part_b"
    PART_C = "part_c"
    PART_D = "part_d"
    PART_E = "part_e"
    PART_F = "part_f"
    ENDORSEMENTS = "endorsements"
    JURISDICTION = "jurisdiction"


class SourceKind(StrEnum):
    """Que es un texto fuente (`entities.md`)."""

    CLAUSE = "clause"
    ENDORSEMENT = "endorsement"
    JURISDICTION = "jurisdiction"
    DISTRACTOR = "distractor"
    PERSONA_POOL = "persona_pool"
    VEHICLE_POOL = "vehicle_pool"
    #: Los turnos cortos de un caso sembrado, escritos a mano (CG-U7-2, FD-U7-7).
    CASE_TURNS = "case_turns"


#: Los repertorios de datos ficticios: sin numeracion ni formulario.
POOL_KINDS: Final = frozenset({SourceKind.PERSONA_POOL, SourceKind.VEHICLE_POOL})

#: Lo que no es texto de un formulario: repertorios y casos sembrados.
_SIN_FORMULARIO: Final = POOL_KINDS | {SourceKind.CASE_TURNS}

#: Que tipos de texto admite cada archivo de fuentes. Una parte de la poliza trae
#: sus clausulas y los distractores que se confunden con ellas.
_TIPOS_DE_UNA_PARTE: Final = frozenset({SourceKind.CLAUSE, SourceKind.DISTRACTOR})
_TIPOS_POR_ARCHIVO: Final[dict[str, frozenset[SourceKind]]] = {
    POOLS_FILE_KEY: POOL_KINDS,
    CASE_TURNS_FILE_KEY: frozenset({SourceKind.CASE_TURNS}),
    PolicyPart.ENDORSEMENTS.value: frozenset({SourceKind.ENDORSEMENT, SourceKind.DISTRACTOR}),
    PolicyPart.JURISDICTION.value: frozenset({SourceKind.JURISDICTION, SourceKind.DISTRACTOR}),
}


class ReviewedBy(StrEnum):
    """Quien reviso: el agente contra la estructura y P8, o Miguel en la muestra."""

    CONDUCTOR = "conductor"
    MIGUEL = "miguel"


class DistractorReason(StrEnum):
    """Por que un distractor se confunde con su clausula (BR3.4)."""

    SUPERSEDED_VERSION = "superseded_version"
    NEAR_DUPLICATE = "near_duplicate"


class FormKind(StrEnum):
    BASE = "base"
    ENDORSEMENT = "endorsement"
    JURISDICTION = "jurisdiction"


class RelationKind(StrEnum):
    """Las tres relaciones entre clausulas (ADR-010, FD-U7-2: en ingles)."""

    ENDORSEMENT_MODIFIES = "endorsement_modifies"
    DEFINES = "defines"
    REFERS_TO = "refers_to"


class SeededState(StrEnum):
    """Los siete estados del caso. Copia de `case_record.models.CaseState`."""

    OPEN = "open"
    CAPTURING = "capturing"
    VERIFYING = "verifying"
    DECIDING = "deciding"
    DERIVED = "derived"
    AWAITING_INSURED = "awaiting_insured"
    CLOSED = "closed"


class SeededResolution(StrEnum):
    """Las cuatro resoluciones. Copia de `case_record.models.Resolution`."""

    REGISTERED = "registered"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT_TO_INSURER = "sent_to_insurer"


class SeededSpeaker(StrEnum):
    """Quien habla en un turno. Copia de `case_record.models.Speaker`."""

    INSURED = "insured"
    AGENT = "agent"
    STAFF = "staff"


class SeededRecordType(StrEnum):
    """Los tres tipos de registro. Copia de `case_record.models.RecordType`."""

    CLAIM = "claim"
    COVERAGE_INQUIRY = "coverage_inquiry"
    QUOTE_REQUEST = "quote_request"


class SeededChannel(StrEnum):
    """Por donde entro el caso. Copia de `case_record.models.Channel`."""

    VOICE = "voice"
    CHAT = "chat"


class SeededDerivationReason(StrEnum):
    """Por que se derivo. Copia de `case_record.models.DerivationReason`."""

    DEMO_LIMIT = "demo_limit"
    PERSON_REQUESTED = "person_requested"
    RULE = "rule"


class SeededFieldStatus(StrEnum):
    """Los dos estados de un campo que se ha dicho. Copia parcial de
    `case_record.models.FieldStatus`: un campo que no se ha dicho no se siembra,
    simplemente no esta."""

    STATED = "stated"
    CONFIRMED = "confirmed"


#: Los estados en que el caso ya paso por una derivacion y la lleva escrita.
_ESTADOS_DERIVADOS: Final = frozenset({SeededState.DERIVED, SeededState.AWAITING_INSURED})

#: Las resoluciones que decide una persona desde la bandeja: el caso se derivo
#: antes de cerrarse, y la razon de esa derivacion es parte del caso.
_RESOLUCIONES_DE_PERSONA: Final = frozenset(
    {SeededResolution.APPROVED, SeededResolution.REJECTED, SeededResolution.SENT_TO_INSURER}
)


class ReviewVerdict(StrEnum):
    """El veredicto de Miguel sobre la muestra (AC5.4.5, AC5.5.6)."""

    OWN_TEXT_STRUCTURE_OK = "own_text_structure_ok"
    CHANGES_REQUESTED = "changes_requested"


# --- Los casos sembrados, como se escriben en su fuente -------------------------


class SeededField(Frozen):
    """Un campo de un caso sembrado: su valor y si se dijo o ya se confirmo.

    El estado importa: tres campos del siniestro solo cuentan confirmados (BR2.2
    de U4), y un criterio como "tres de siete campos confirmados" no se puede
    sembrar con solo el valor.
    """

    value: NonBlankText
    status: SeededFieldStatus


def _derivacion_coherente(
    donde: str,
    state: SeededState,
    resolution: SeededResolution | None,
    derivation_reason: SeededDerivationReason | None,
) -> None:
    """El cierre y la derivacion de un caso sembrado, coherentes entre si.

    Un caso cerrado lleva resolucion, y solo uno cerrado la lleva. Un caso que ya
    paso por una derivacion --derivado, esperando al asegurado, o cerrado por la
    decision de una persona-- lleva la razon de esa derivacion, y ningun otro la
    lleva: `registered` lo cierran las reglas sin derivar.
    """
    if (state is SeededState.CLOSED) != (resolution is not None):
        msg = f"'{donde}': un caso cerrado lleva resolucion, y solo uno cerrado la lleva"
        raise ValueError(msg)
    derivado = state in _ESTADOS_DERIVADOS or resolution in _RESOLUCIONES_DE_PERSONA
    if derivado != (derivation_reason is not None):
        msg = (
            f"'{donde}': lleva la razon de su derivacion si y solo si paso por una "
            "(derivado, esperando al asegurado, o cerrado por la decision de una persona)"
        )
        raise ValueError(msg)


class SeededCaseSpec(Frozen):
    """Lo que dice la fuente de un caso sembrado, ademas de sus turnos (FD-U7-7).

    Los valores de los campos y de los turnos pueden llevar marcadores
    --`{insured_name}`, `{policy_number}`, `{plate}`...-- que la composicion llena
    con la persona y el vehiculo de una poliza emitida de la aseguradora: asi cada
    dato personal de un caso sale del conjunto sembrado y esta en la lista de
    valores personales (BR7.2).
    """

    #: La ultima parte de su `case_key`: `SEED/<aseguradora>/<idioma>/<name>`.
    name: str = Field(pattern=CASE_NAME_PATTERN, max_length=60)
    record_type: SeededRecordType = SeededRecordType.CLAIM
    channel: SeededChannel = SeededChannel.CHAT
    state: SeededState
    resolution: SeededResolution | None = None
    derivation_reason: SeededDerivationReason | None = None
    #: Si la persona asegurada tiene que ser de un idioma concreto --un turno que
    #: dicta la cedula en el otro idioma--. Sin el, cualquiera de la aseguradora.
    persona_language: Locale | None = None
    #: Si el caso es de la poliza de ejemplo de la aseguradora.
    example_policy: bool = False
    fields: dict[FieldKeyStr, SeededField] = Field(default_factory=dict)
    used_by: tuple[AcIdStr, ...] = ()

    @model_validator(mode="after")
    def _coherente(self) -> Self:
        _derivacion_coherente(self.name, self.state, self.resolution, self.derivation_reason)
        _sin_repetidos(self.used_by, f"'{self.name}': used_by")
        return self


# --- Entrada revisada: los textos fuente --------------------------------------


class SourceEntry(Frozen):
    """Un texto fuente tal como se escribe dentro de su archivo de parte.

    La aseguradora y el idioma no se repiten en cada entrada: los dice la
    cabecera del archivo, y el cargador los anade al construir el `SourceText`.
    Todo lo demas es de la entrada, **incluida la marca de revision**: cada texto
    se revisa por separado, y uno sin `reviewed_at`, `reviewed_by` o
    `drafted_with` no entra al corpus (BR2.2).
    """

    source_id: str = Field(min_length=1)
    kind: SourceKind
    clause_key: ClauseKeyStr | None = None
    #: El encabezado estructural de la parte, en el idioma del texto.
    part: str | None = Field(default=None, min_length=1)
    version: VersionStr
    text: NonBlankText
    distractor_of: ClauseIdStr | None = None
    distractor_reason: DistractorReason | None = None
    #: En una definicion, las formas en que su termino aparece en el texto de las
    #: demas clausulas ("vehiculo cubierto", "vehiculos cubiertos"). De ahi salen
    #: las relaciones `defines` (ADR-010): sin ellas habria que adivinar el termino.
    defines_terms: tuple[NonBlankText, ...] = ()
    #: Las clausulas a las que remite esta, por su identificador: la de la
    #: jurisdiccion que fija un minimo, por ejemplo. De ahi salen `refers_to`.
    refers_to: tuple[ClauseIdStr, ...] = ()
    #: En los turnos de un caso sembrado, el resto del caso (FD-U7-7).
    case: SeededCaseSpec | None = None
    reviewed_at: date
    reviewed_by: ReviewedBy
    drafted_with: str = Field(pattern=DRAFTED_WITH_PATTERN)

    @model_validator(mode="after")
    def _forma_segun_su_tipo(self) -> Self:
        if self.kind in POOL_KINDS:
            self._es_repertorio()
        elif self.kind is SourceKind.CASE_TURNS:
            self._son_turnos()
        else:
            self._es_de_formulario()
        self._distractor_ligado()
        self._relaciones_segun_su_tipo()
        return self

    def _son_turnos(self) -> None:
        if not re.fullmatch(CASE_SOURCE_ID_PATTERN, self.source_id):
            msg = (
                f"'{self.source_id}': los turnos de un caso se llaman <prefijo>-CASE-<nombre>, "
                "por ejemplo STO-CASE-DERIVED"
            )
            raise ValueError(msg)
        if self.case is None:
            msg = f"'{self.source_id}': los turnos de un caso llevan su caso (case)"
            raise ValueError(msg)
        if self.clause_key is not None or self.part is not None:
            msg = f"'{self.source_id}': los turnos de un caso no llevan numeracion ni parte"
            raise ValueError(msg)
        parse_turns(self.text, where=self.source_id)

    def _relaciones_segun_su_tipo(self) -> None:
        if self.case is not None and self.kind is not SourceKind.CASE_TURNS:
            msg = f"'{self.source_id}': solo los turnos de un caso llevan case"
            raise ValueError(msg)
        if self.defines_terms and not (
            self.kind is SourceKind.CLAUSE
            and self.clause_key is not None
            and self.clause_key.startswith("DEF.")
        ):
            msg = f"'{self.source_id}': solo una definicion (DEF.*) lleva defines_terms"
            raise ValueError(msg)
        if self.refers_to and self.kind not in {SourceKind.CLAUSE, SourceKind.ENDORSEMENT}:
            msg = f"'{self.source_id}': solo una clausula o un endoso remiten a otra (refers_to)"
            raise ValueError(msg)
        _sin_repetidos(self.refers_to, f"'{self.source_id}': refers_to")

    def _es_repertorio(self) -> None:
        if not re.fullmatch(POOL_SOURCE_ID_PATTERN, self.source_id):
            msg = (
                f"'{self.source_id}': un repertorio se llama <prefijo>-POOL-<nombre>, "
                "por ejemplo STO-POOL-GIVEN-NAMES"
            )
            raise ValueError(msg)
        if self.clause_key is not None:
            msg = f"'{self.source_id}': un repertorio no lleva numeracion (clause_key)"
            raise ValueError(msg)
        pool_items(self.text, where=self.source_id)

    def _es_de_formulario(self) -> None:
        if self.clause_key is None:
            msg = f"'{self.source_id}': un texto de tipo {self.kind.value} lleva clause_key"
            raise ValueError(msg)
        if self.part is None:
            msg = f"'{self.source_id}': un texto de tipo {self.kind.value} lleva part"
            raise ValueError(msg)
        formulario = form_id_of(self.source_id, self.clause_key)
        if not _FORM_ID.fullmatch(formulario):
            msg = (
                f"'{self.source_id}': el identificador es <formulario>-<numeracion>, y "
                f"'{formulario}' no tiene la forma de un formulario (por ejemplo "
                "STO-PAP-2026 o STO-PAP-2026-END-3)"
            )
            raise ValueError(msg)
        if _ano(formulario) != self.version.split(".")[0]:
            msg = (
                f"'{self.source_id}': el formulario es de {_ano(formulario)} y la version "
                f"'{self.version}' de otro ano"
            )
            raise ValueError(msg)
        self._familia_segun_tipo(formulario)

    def _familia_segun_tipo(self, formulario: str) -> None:
        esperada = {
            SourceKind.CLAUSE: (POLICY_FAMILY, False),
            SourceKind.ENDORSEMENT: (POLICY_FAMILY, True),
            SourceKind.JURISDICTION: (JURISDICTION_FAMILY, False),
        }.get(self.kind)
        if esperada is None:
            return
        familia, endoso = esperada
        if _familia(formulario) != familia or _es_endoso(formulario) != endoso:
            forma = f"<prefijo>-{familia}-<ano>" + ("-END-<n>" if endoso else "")
            msg = f"'{self.source_id}': un texto de tipo {self.kind.value} va en un formulario {forma}"
            raise ValueError(msg)

    def _distractor_ligado(self) -> None:
        if self.kind is SourceKind.DISTRACTOR:
            if self.distractor_of is None or self.distractor_reason is None:
                msg = (
                    f"'{self.source_id}': un distractor dice con que clausula se confunde "
                    "(distractor_of) y por que (distractor_reason)"
                )
                raise ValueError(msg)
            if self.distractor_of == self.source_id:
                msg = f"'{self.source_id}': un distractor no se confunde consigo mismo"
                raise ValueError(msg)
        elif self.distractor_of is not None or self.distractor_reason is not None:
            msg = f"'{self.source_id}': solo un distractor lleva distractor_of y distractor_reason"
            raise ValueError(msg)

    @property
    def form_id(self) -> str | None:
        """El formulario del texto, o nada si es un repertorio."""
        if self.clause_key is None:
            return None
        return form_id_of(self.source_id, self.clause_key)


class SourceText(SourceEntry):
    """Un texto fuente revisado, con su aseguradora y su idioma (`entities.md`)."""

    tenant_id: TenantIdStr
    language: Locale


class SourceFile(Frozen):
    """Un archivo de `app/data/sources/<aseguradora>/<idioma>/<parte>.yaml`.

    La cabecera repite lo que dice la ruta y el cargador comprueba que coincidan:
    un archivo movido a la carpeta de otra aseguradora no puede cambiar de dueno
    en silencio.
    """

    format_version: Literal[1]
    tenant_id: TenantIdStr
    language: Locale
    part_key: PolicyPart | Literal["pools", "case_turns"]
    texts: tuple[SourceEntry, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _tipos_segun_el_archivo(self) -> Self:
        permitidos = _TIPOS_POR_ARCHIVO.get(str(self.part_key), _TIPOS_DE_UNA_PARTE)
        for entrada in self.texts:
            if entrada.kind not in permitidos:
                nombres = ", ".join(sorted(k.value for k in permitidos))
                msg = (
                    f"'{entrada.source_id}' es de tipo {entrada.kind.value} y el archivo "
                    f"'{self.part_key}' solo admite: {nombres}"
                )
                raise ValueError(msg)
        _sin_repetidos(tuple(e.source_id for e in self.texts), "source_id")
        return self


class ReviewSample(Frozen):
    """La muestra de diez clausulas que revisa Miguel (BR5.4).

    El veredicto llega despues de la muestra, y con el su fecha y su commit: un
    veredicto sin fecha ni commit no dice que se reviso, ni cuando.
    """

    tenant_id: TenantIdStr
    sample_seed: NonNegativeInt
    clause_ids: tuple[ClauseIdStr, ...] = Field(
        min_length=REVIEW_SAMPLE_SIZE, max_length=REVIEW_SAMPLE_SIZE
    )
    reviewed_on: date | None = None
    commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{7,40}$")
    verdict: ReviewVerdict | None = None

    @model_validator(mode="after")
    def _veredicto_con_fecha_y_commit(self) -> Self:
        _sin_repetidos(self.clause_ids, "clause_ids")
        if self.verdict is not None and (self.reviewed_on is None or self.commit is None):
            msg = "un veredicto lleva la fecha de la revision (reviewed_on) y su commit"
            raise ValueError(msg)
        return self


# --- Salida versionada: el corpus (C-26) --------------------------------------


class FormRecord(Frozen):
    """Un formulario base, un endoso o el documento de jurisdiccion (`forms/<form_id>.json`)."""

    form_id: FormIdStr
    form_kind: FormKind
    form_version: VersionStr
    issuer_tenant: TenantIdStr
    issuer_label: str = Field(min_length=1)
    language: Locale
    jurisdiction_ref: FormIdStr | None = None
    clause_ids: tuple[ClauseIdStr, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _coherente(self) -> Self:
        if _ano(self.form_id) != self.form_version.split(".")[0]:
            msg = (
                f"'{self.form_id}' es de {_ano(self.form_id)} y su version '{self.form_version}' no"
            )
            raise ValueError(msg)
        if self.form_kind is FormKind.BASE and self.jurisdiction_ref is None:
            msg = f"'{self.form_id}': un formulario base referencia su documento de jurisdiccion"
            raise ValueError(msg)
        if (self.form_kind is FormKind.ENDORSEMENT) != _es_endoso(self.form_id):
            msg = f"'{self.form_id}': solo un endoso lleva -END-<n>, y todo endoso lo lleva"
            raise ValueError(msg)
        prefijo = f"{self.form_id}-"
        ajenas = [c for c in self.clause_ids if not c.startswith(prefijo)]
        if ajenas:
            msg = f"'{self.form_id}' lista clausulas de otro formulario: {', '.join(ajenas)}"
            raise ValueError(msg)
        _sin_repetidos(self.clause_ids, "clause_ids")
        return self


class ClauseRecord(Frozen):
    """Una clausula, con la forma exacta de C-26."""

    clause_id: ClauseIdStr
    form_id: FormIdStr
    form_version: VersionStr
    clause_key: ClauseKeyStr
    part: str = Field(min_length=1)
    language: Locale
    text: NonBlankText
    is_distractor: bool = False
    issuer_label: str = Field(min_length=1)

    @model_validator(mode="after")
    def _identificador_de_formulario_y_numeracion(self) -> Self:
        if self.clause_id != f"{self.form_id}-{self.clause_key}":
            msg = (
                f"'{self.clause_id}' no es su formulario '{self.form_id}' mas su "
                f"numeracion '{self.clause_key}' (BR3.2)"
            )
            raise ValueError(msg)
        if _ano(self.form_id) != self.form_version.split(".")[0]:
            msg = f"'{self.clause_id}': el formulario y la version '{self.form_version}' son de anos distintos"
            raise ValueError(msg)
        return self


class ClauseFile(Frozen):
    """Las clausulas de un formulario (`clauses/<form_id>.json`)."""

    form_id: FormIdStr
    clauses: tuple[ClauseRecord, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _todas_de_su_formulario(self) -> Self:
        ajenas = [c.clause_id for c in self.clauses if c.form_id != self.form_id]
        if ajenas:
            msg = f"'{self.form_id}' trae clausulas de otro formulario: {', '.join(ajenas)}"
            raise ValueError(msg)
        _sin_repetidos(tuple(c.clause_id for c in self.clauses), "clause_id")
        return self


class ClauseRelationRecord(Frozen):
    """Una relacion entre dos clausulas (ADR-010)."""

    from_clause: ClauseIdStr
    to_clause: ClauseIdStr
    relation: RelationKind

    @model_validator(mode="after")
    def _dos_extremos(self) -> Self:
        if self.from_clause == self.to_clause:
            msg = f"'{self.from_clause}' no se relaciona consigo misma"
            raise ValueError(msg)
        return self


class ClauseRelationFile(Frozen):
    """Las relaciones del espacio de una aseguradora (`clause_relations.json`)."""

    tenant_id: TenantIdStr
    relations: tuple[ClauseRelationRecord, ...]

    @model_validator(mode="after")
    def _sin_repetidas(self) -> Self:
        _sin_repetidos(
            tuple(f"{r.from_clause} {r.relation.value} {r.to_clause}" for r in self.relations),
            "relaciones",
        )
        return self


# --- Datos personales ficticios (BR7.1) ----------------------------------------

#: Los valores de cada caracter del VIN para el digito de control (ISO 3779).
_VIN_VALORES: Final[dict[str, int]] = {
    **{str(d): d for d in range(10)},
    **dict(zip("ABCDEFGH", range(1, 9), strict=True)),
    **dict(zip("JKLMN", range(1, 6), strict=True)),
    "P": 7,
    "R": 9,
    **dict(zip("STUVWXYZ", range(2, 10), strict=True)),
}
_VIN_PESOS: Final = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)


def vin_check_digit(vin: str) -> str:
    """El digito de control que tendria un VIN real (posicion 9)."""
    total = sum(_VIN_VALORES[c] * p for c, p in zip(vin, _VIN_PESOS, strict=True))
    resto = total % 11
    return "X" if resto == 10 else str(resto)


class PersonaRef(Frozen):
    """Una persona ficticia. Alimenta los canarios del segundo detector (ADR-013).

    Cada dato tiene una forma que lo delata como ficticio, y la forma que
    reconoce la redaccion de U3 para que la prueba de fuga lo encuentre (FR12.3).
    """

    persona_id: str = Field(pattern=IDENTIFIER_PATTERN)
    full_name: str = Field(min_length=3)
    #: Del rango 555-01XX, que no se asigna a nadie (ADR-016): un telefono de
    #: Colombia (`310 555 0142`) o de Estados Unidos (`212-555-0142`).
    phone: str = Field(pattern=r"^\+?[\d(][\d ()\-]*$")
    #: Una cedula de ocho a diez digitos (con o sin puntos) o un numero de la
    #: forma `ddd-dd-dddd`: las dos formas que reconoce U3.
    national_id: str = Field(pattern=r"^(?:\d{8,10}|\d{1,3}(?:\.\d{3}){2,3}|\d{3}-\d{2}-\d{4})$")
    email: str = Field(pattern=r"^[a-z0-9]+(?:[._-][a-z0-9]+)*@example\.(?:com|org)$")

    @field_validator("phone")
    @classmethod
    def _telefono_del_rango_ficticio(cls, valor: str) -> str:
        digitos = re.sub(r"\D", "", valor)
        if not re.fullmatch(r"(?:1|57)?\d{3}55501\d{2}", digitos):
            msg = (
                f"el telefono '{valor}' no esta en el rango ficticio 555-01XX: solo ese "
                "rango garantiza que no es de nadie (ADR-016)"
            )
            raise ValueError(msg)
        return valor


class DriverRef(Frozen):
    """Un conductor que la poliza declara. Solo su nombre: es lo unico que se compara.

    El telefono, la cedula y el correo son del titular (`PersonaRef`); un conductor adicional
    no los necesita, y cada dato personal de mas es uno mas que sembrar, redactar y vigilar.
    """

    full_name: str = Field(min_length=3)


class VehicleRef(Frozen):
    """Un vehiculo ficticio."""

    #: Una placa inventada con la forma de cada idioma: `ABC123` o `ABC12D` en
    #: Colombia, `ABC-1234` o `1ABC234` en Estados Unidos.
    plate: str = Field(
        pattern=r"^(?:[A-Z]{3}[ \-]?(?:\d{3}|\d{2}[A-Z])|[A-Z]{3}[ \-]?\d{4}|\d[A-Z]{3}\d{3})$"
    )
    make_model_year: str = Field(pattern=r"^\S.*\s(?:19|20)\d{2}$")
    #: Diecisiete caracteres sin I, O ni Q, y un digito de control **que falla**:
    #: un VIN valido podria ser de un vehiculo real (BR7.1).
    vin: str = Field(pattern=r"^[A-HJ-NPR-Z0-9]{17}$")

    @field_validator("vin")
    @classmethod
    def _vin_que_nunca_es_real(cls, valor: str) -> str:
        if valor[8] == vin_check_digit(valor):
            msg = (
                f"el VIN '{valor}' pasa su digito de control y podria ser de un vehiculo "
                "real: los VIN del corpus lo fallan a proposito (BR7.1)"
            )
            raise ValueError(msg)
        return valor


class IssuedPolicyRecord(Frozen):
    """Una poliza emitida, con sus declaraciones y endosos vigentes (FR5.2).

    Que el formulario y cada endoso existan, y que la `example_policy` de cada
    aseguradora este entre las emitidas, lo comprueba la composicion, que tiene
    el conjunto: aqui se comprueba todo lo que se ve en la poliza sola.
    """

    policy_number: str = Field(pattern=POLICY_NUMBER_PATTERN)
    tenant_id: TenantIdStr
    #: En una agencia, quien emitio la poliza; en una emisora, ella misma.
    issuer_tenant: TenantIdStr
    form_id: FormIdStr
    #: Una poliza sin version no valida (FR5.2).
    form_version: VersionStr
    endorsement_ids: tuple[FormIdStr, ...]
    period_start: date
    period_end: date
    named_insured: PersonaRef
    #: Los conductores que la poliza declara, **el titular primero**. Vacio es una poliza que no
    #: declara conductores, y quien la lee no puede decir si uno figura o no: el generador los
    #: declara siempre, y el vacio es lo que dejan las filas anteriores a este campo.
    drivers: tuple[DriverRef, ...] = ()
    vehicles: tuple[VehicleRef, ...] = Field(min_length=1)
    limits_and_deductibles: dict[FieldKeyStr, NonNegativeInt] = Field(min_length=1)

    @model_validator(mode="after")
    def _coherente(self) -> Self:
        if _es_endoso(self.form_id) or _familia(self.form_id) != POLICY_FAMILY:
            msg = f"'{self.policy_number}': form_id '{self.form_id}' no es un formulario base"
            raise ValueError(msg)
        if _ano(self.form_id) != self.form_version.split(".")[0]:
            msg = (
                f"'{self.policy_number}': form_version '{self.form_version}' no es de su formulario"
            )
            raise ValueError(msg)
        ajenos = [e for e in self.endorsement_ids if not e.startswith(f"{self.form_id}-END-")]
        if ajenos:
            msg = (
                f"'{self.policy_number}': endorsement_ids trae endosos que no son de "
                f"'{self.form_id}': {', '.join(ajenos)}"
            )
            raise ValueError(msg)
        _sin_repetidos(self.endorsement_ids, f"'{self.policy_number}': endosos")
        if self.period_end <= self.period_start:
            msg = f"'{self.policy_number}': el periodo termina antes de empezar"
            raise ValueError(msg)
        if self.drivers:
            if self.drivers[0].full_name != self.named_insured.full_name:
                msg = f"'{self.policy_number}': el primer conductor declarado es el titular"
                raise ValueError(msg)
            _sin_repetidos(
                tuple(d.full_name for d in self.drivers), f"'{self.policy_number}': conductores"
            )
        return self


class SeededTurn(Frozen):
    """Un turno corto de un caso sembrado, escrito a mano (CG-U7-2)."""

    speaker: SeededSpeaker
    text: NonBlankText


#: Una linea de turnos: `<hablante>: <texto>`.
_LINEA_DE_TURNO = re.compile(r"^(?P<hablante>[a-z]+): (?P<texto>\S.*)$")


def parse_turns(text: str, *, where: str) -> tuple[SeededTurn, ...]:
    """Los turnos de un caso, uno por linea: `insured: ...`, `agent: ...`, `staff: ...`.

    Una linea vacia o sin hablante conocido se nombra con su numero: un turno mal
    escrito que se tragara en silencio cambiaria lo que el caso dice que paso.
    """
    turnos: list[SeededTurn] = []
    hablantes = ", ".join(s.value for s in SeededSpeaker)
    for numero, linea in enumerate(text.splitlines(), start=1):
        coincide = _LINEA_DE_TURNO.fullmatch(linea.strip())
        if coincide is None or coincide["hablante"] not in {s.value for s in SeededSpeaker}:
            msg = f"'{where}': la linea {numero} no es '<hablante>: <texto>' con hablante en {hablantes}"
            raise ValueError(msg)
        turnos.append(
            SeededTurn(speaker=SeededSpeaker(coincide["hablante"]), text=coincide["texto"])
        )
    return tuple(turnos)


def pool_items(text: str, *, where: str) -> tuple[str, ...]:
    """Los elementos de un repertorio, uno por linea, sin vacios ni repetidos."""
    elementos = tuple(linea.strip() for linea in text.splitlines())
    if not elementos or any(not e for e in elementos):
        msg = f"'{where}': un repertorio lleva un elemento por linea, sin lineas vacias"
        raise ValueError(msg)
    _sin_repetidos(elementos, f"'{where}': elementos")
    return elementos


class SeededCaseRecord(Frozen):
    """Un caso sembrado, listo para cargarse por la API de U4 (US5.6)."""

    case_key: str = Field(pattern=CASE_KEY_PATTERN)
    tenant_id: TenantIdStr
    language: Locale
    record_type: SeededRecordType
    channel: SeededChannel
    state: SeededState
    resolution: SeededResolution | None = None
    derivation_reason: SeededDerivationReason | None = None
    #: La poliza emitida de la aseguradora a la que pertenece el caso.
    policy_number: str = Field(pattern=POLICY_NUMBER_PATTERN)
    fields: dict[FieldKeyStr, SeededField]
    transcript: tuple[SeededTurn, ...]
    used_by: tuple[AcIdStr, ...]

    @model_validator(mode="after")
    def _coherente(self) -> Self:
        esperado = f"SEED/{self.tenant_id}/{self.language}/"
        if not self.case_key.startswith(esperado):
            msg = f"'{self.case_key}' no empieza por '{esperado}': la clave nombra su aseguradora e idioma"
            raise ValueError(msg)
        _derivacion_coherente(self.case_key, self.state, self.resolution, self.derivation_reason)
        _sin_repetidos(self.used_by, f"'{self.case_key}': used_by")
        return self


# --- La lista de valores personales ficticios (BR7.2, FD-U7-8) ---------------


class PersonalValueKind(StrEnum):
    """Que clase de dato personal es un valor sembrado (`entities.md`)."""

    NAME = "name"
    PHONE = "phone"
    NATIONAL_ID = "national_id"
    EMAIL = "email"
    PLATE = "plate"
    VIN = "vin"
    POLICY_NUMBER = "policy_number"


class PersonalValue(Frozen):
    """Un valor personal ficticio sembrado, con su tipo y el idioma de quien lo tiene."""

    kind: PersonalValueKind
    language: Locale
    value: NonBlankText


class PersonalValueList(Frozen):
    """`app/data/personal_values.json`: lo leen la prueba de redaccion y los canarios de U21."""

    values: tuple[PersonalValue, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _en_forma_canonica(self) -> Self:
        claves = [(v.kind.value, v.language, v.value) for v in self.values]
        if claves != sorted(set(claves)):
            msg = "los valores van ordenados por tipo, idioma y valor, y sin repetir"
            raise ValueError(msg)
        return self


# --- Las huellas de los formularios de terceros (BR5.1) -----------------------


class FingerprintSource(Frozen):
    """De donde salieron las huellas: el specimen, no su texto."""

    form: str = Field(min_length=1)
    edition: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    retrieved_at: date
    file_sha256: Sha256Str


class FingerprintSet(Frozen):
    """Las huellas: **solo hashes**, en orden y sin repetir (SEC-U7.2).

    No hay ningun campo donde quepa una secuencia legible: el modelo no admite
    campos de mas, y los hashes solo admiten 64 digitos hexadecimales.
    """

    shingle_size: int = Field(default=8, ge=1)
    normalization: str = Field(min_length=1)
    sources: tuple[FingerprintSource, ...]
    hashes: tuple[Sha256Str, ...]

    @model_validator(mode="after")
    def _en_forma_canonica(self) -> Self:
        if list(self.hashes) != sorted(set(self.hashes)):
            msg = "las huellas van ordenadas y sin repetir: asi dos corridas escriben los mismos bytes"
            raise ValueError(msg)
        return self


# --- El manifiesto (C-26, BR1.4) ----------------------------------------------


class DeclaredDifference(Frozen):
    """Una diferencia puesta a proposito entre emisoras (AC5.4.3, BR3.7)."""

    difference_id: str = Field(pattern=IDENTIFIER_PATTERN)
    description: str = Field(min_length=1)
    present_in: tuple[FormIdStr, ...] = Field(min_length=1)
    absent_in: tuple[FormIdStr, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _presente_o_ausente(self) -> Self:
        ambos = sorted(set(self.present_in) & set(self.absent_in))
        if ambos:
            msg = f"'{self.difference_id}' dice que esta y que falta en: {', '.join(ambos)}"
            raise ValueError(msg)
        return self


class _RootSourceFile(Frozen):
    """Un archivo de fuentes de la raiz de `app/data/sources/`, con su marca de revision.

    Se revisa entero, como un texto fuente: sin `reviewed_at`, `reviewed_by` y
    `drafted_with` no entra (BR2.2).
    """

    format_version: Literal[1]
    reviewed_at: date
    reviewed_by: ReviewedBy
    drafted_with: str = Field(pattern=DRAFTED_WITH_PATTERN)


class DifferenceSource(Frozen):
    """Una diferencia declarada, con lo que la hace comprobable contra el corpus.

    Se comprueba por la numeracion: cada formulario de `present_in` tiene una
    clausula con `clause_key`, y ninguno de `absent_in` la tiene (BR3.7).
    """

    difference_id: str = Field(pattern=IDENTIFIER_PATTERN)
    description: NonBlankText
    clause_key: ClauseKeyStr
    present_in: tuple[FormIdStr, ...] = Field(min_length=1)
    absent_in: tuple[FormIdStr, ...] = Field(min_length=1)

    def declared(self) -> DeclaredDifference:
        """Lo que el manifiesto registra de ella."""
        return DeclaredDifference(
            difference_id=self.difference_id,
            description=self.description,
            present_in=self.present_in,
            absent_in=self.absent_in,
        )


class DifferenceFile(_RootSourceFile):
    """`app/data/sources/differences.yaml`: las diferencias puestas a proposito (AC5.4.3)."""

    differences: tuple[DifferenceSource, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _sin_repetidas(self) -> Self:
        _sin_repetidos(tuple(d.difference_id for d in self.differences), "difference_id")
        for diferencia in self.differences:
            diferencia.declared()
        return self


class SeededCriterion(Frozen):
    """Un criterio de aceptacion que parte de un caso sembrado, y de que unidad es."""

    ac_id: AcIdStr
    unit: str = Field(pattern=r"^U\d+$")


class SeededCriteriaFile(_RootSourceFile):
    """`app/data/sources/seeded_criteria.yaml`: los criterios que exigen su caso (BR6.2).

    Crece con cada unidad: la que construye un criterio que parte de un caso
    sembrado lo anade aqui junto con el caso, y la siguiente generacion comprueba
    que tenga al menos uno.
    """

    criteria: tuple[SeededCriterion, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _sin_repetidos(self) -> Self:
        _sin_repetidos(tuple(c.ac_id for c in self.criteria), "ac_id")
        return self


class SeededCaseRef(Frozen):
    """Un caso sembrado, visto desde el manifiesto: donde esta y quien lo usa."""

    case_key: str = Field(pattern=CASE_KEY_PATTERN)
    path: str
    used_by: tuple[AcIdStr, ...]


def _ruta_logica(ruta: str) -> str:
    """Una ruta relativa a la raiz del repositorio, en forma POSIX y sin atajos."""
    partes = ruta.split("/")
    if (
        not ruta
        or ruta.startswith("/")
        or "\\" in ruta
        or any(p in {"", ".", ".."} for p in partes)
    ):
        msg = f"'{ruta}' no es una ruta relativa en forma POSIX y sin atajos"
        raise ValueError(msg)
    return ruta


class GenerationManifest(Frozen):
    """El manifiesto de una generacion (C-26).

    **No lleva fecha ni nada que dependa del reloj**: con la misma semilla y las
    mismas entradas, sus bytes son los mismos (BR1.1). Las rutas son logicas
    --desde la raiz del repositorio-- aunque la generacion se escriba en un
    directorio temporal, por la misma razon.
    """

    manifest_version: Literal[1]
    seed: NonNegativeInt
    generator_version: str = Field(min_length=1)
    inputs: dict[str, Sha256Str]
    outputs: dict[str, Sha256Str]
    declared_differences: tuple[DeclaredDifference, ...]
    seeded_cases: tuple[SeededCaseRef, ...]
    review_samples: tuple[ReviewSample, ...]

    @model_validator(mode="after")
    def _rutas_en_su_sitio(self) -> Self:
        for ruta in self.inputs:
            _ruta_logica(ruta)
        for ruta in self.outputs:
            _ruta_logica(ruta)
            if not ruta.startswith(DATA_PREFIX) or ruta.startswith(SOURCES_PREFIX):
                msg = f"la salida '{ruta}' no esta bajo {DATA_PREFIX} o esta entre las fuentes"
                raise ValueError(msg)
            if ruta == MANIFEST_OUTPUT:
                msg = "el manifiesto no se lista a si mismo entre las salidas"
                raise ValueError(msg)
        ambas = sorted(set(self.inputs) & set(self.outputs))
        if ambas:
            msg = f"entrada y salida a la vez: {', '.join(ambas)}"
            raise ValueError(msg)
        sin_salida = [c.path for c in self.seeded_cases if c.path not in self.outputs]
        if sin_salida:
            msg = f"casos sembrados que no estan entre las salidas: {', '.join(sin_salida)}"
            raise ValueError(msg)
        _sin_repetidos(tuple(c.case_key for c in self.seeded_cases), "case_key")
        _sin_repetidos(tuple(d.difference_id for d in self.declared_differences), "difference_id")
        return self


# --- El borrador: lo que devuelve el modelo (BR2.1) ----------------------------


class DraftClauseKind(StrEnum):
    """Lo que el modelo puede proponer. Los repertorios se escriben a mano (CG-U7-2)."""

    CLAUSE = "clause"
    ENDORSEMENT = "endorsement"
    JURISDICTION = "jurisdiction"
    DISTRACTOR = "distractor"


class DraftClause(Frozen):
    """Una clausula propuesta. Sin identificador ni version: los pone la revision."""

    kind: DraftClauseKind
    clause_key: ClauseKeyStr
    #: El encabezado estructural de la parte, en el idioma pedido.
    part: str = Field(min_length=1)
    text: NonBlankText
    #: En un endoso, su numero (el `n` de `-END-<n>`).
    endorsement_number: int | None = Field(default=None, ge=1)
    #: En un distractor, la numeracion de la clausula con la que se confunde.
    distractor_of_key: ClauseKeyStr | None = None
    distractor_reason: DistractorReason | None = None

    @model_validator(mode="after")
    def _coherente(self) -> Self:
        if (self.kind is DraftClauseKind.ENDORSEMENT) != (self.endorsement_number is not None):
            msg = f"'{self.clause_key}': un endoso lleva su numero, y solo un endoso lo lleva"
            raise ValueError(msg)
        es_distractor = self.kind is DraftClauseKind.DISTRACTOR
        ligado = self.distractor_of_key is not None and self.distractor_reason is not None
        suelto = self.distractor_of_key is None and self.distractor_reason is None
        if (es_distractor and not ligado) or (not es_distractor and not suelto):
            msg = (
                f"'{self.clause_key}': un distractor dice con que se confunde y por que, "
                "y solo un distractor lo dice"
            )
            raise ValueError(msg)
        return self


class DraftResponse(Frozen):
    """El esquema de la salida estructurada que se pide al modelo."""

    clauses: tuple[DraftClause, ...] = Field(min_length=1)


class DraftText(Frozen):
    """Un borrador guardado en `tmp/synthetic-drafts/` (`entities.md`).

    Nunca se versiona y ningun comando de la composicion lo lee: existe para que
    el texto del modelo no llegue al corpus sin revision (BR2.1).
    """

    tenant_id: TenantIdStr
    language: Locale
    part: PolicyPart
    #: El identificador exacto del modelo que redacto, nunca un alias.
    model: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    clauses: tuple[DraftClause, ...] = Field(min_length=1)
