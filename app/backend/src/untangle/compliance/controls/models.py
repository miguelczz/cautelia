"""Los tipos de lo que U10 guarda: divulgacion, intervencion y revision (BR8.1, BR8.2).

Tres entidades, las tres colgadas de un caso y las tres **dato de visitante**:
llevan la aseguradora con su politica, la marca de dato de visitante y se borran
con su caso (`entities.md`). Ninguna guarda texto libre de la persona ni del
modelo: solo enums, claves de catalogo, identificadores y marcas de tiempo. Lo
que dijo cada uno ya vive, redactado, en la transcripcion de U4; guardarlo otra
vez aqui seria abrir un segundo sitio de donde se puede escapar (SEC-U10.3).

Los enums son cerrados y llevan **la misma grafia** que las restricciones de la
migracion `u10_compliance_0001_tables`: un valor que no esta aqui no
se puede escribir en el codigo ni entrar en la base.

Las invariantes que la base tambien impone se comprueban aqui primero, con un
mensaje que dice cual se rompio. La base es la red de abajo: el dia que una ruta
nueva escriba en la tabla sin pasar por estos tipos, la para ella.

**Este modulo no importa `untangle.case_record`**, y no es un descuido: el
contrato `sin-ciclos` de `.importlinter` mira los paquetes hermanos de
`untangle`, y `case_record` ya importa `compliance.redaction`. Una arista de
`compliance.controls` hacia `case_record` cierra el ciclo `compliance` <->
`case_record` a ese nivel, aunque el contrato de capas la permita. Por eso los
identificadores del caso y del turno se tipan aqui como texto y el canal lleva
su propio enum, con la misma grafia que el de U4 y que la restriccion de la
tabla.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, Field, field_validator, model_validator

from untangle.base import Frozen, Locale
from untangle.tenancy.models import TENANT_ID_PATTERN, TenantId

#: Tope de los identificadores opacos. Un tope escrito es lo que deja a la
#: columna fuera de "texto libre" (NFR11.8); 64 cabe un UUID con prefijo.
ID_MAX_LENGTH = 64

#: Forma de una clave del catalogo de textos: segmentos en minusculas separados
#: por puntos, como `redaction.label.phone`. Se guarda la clave y nunca su texto.
CATALOG_KEY_PATTERN = r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$"
CATALOG_KEY_MAX_LENGTH = 96

#: Forma del identificador estable de un patron, por ejemplo
#: `guard.es.coverage_promise.003` (`entities.md`). Se exige la forma --segmentos
#: separados por puntos, sin espacios-- y no los segmentos exactos: cuales son lo
#: fija el cargador de patrones, y la base no tiene por que repetirlo.
PATTERN_ID_PATTERN = r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+){2,4}$"
PATTERN_ID_MAX_LENGTH = 64


class DisclosureChannel(StrEnum):
    """Por donde salio la apertura con la divulgacion (BR4.1).

    Los mismos dos valores que `case_record.models.Channel`, repetidos aqui por
    el contrato `sin-ciclos` (ver la cabecera del modulo).
    """

    CHAT = "chat"
    VOICE = "voice"


class GuardCategory(StrEnum):
    """Las siete categorias cerradas de la guardia (BR1.2).

    Una categoria nueva es un cambio de BR1.2, de este enum y de la restriccion
    de la tabla, en el mismo commit.
    """

    COVERAGE_PROMISE = "coverage_promise"
    AMOUNT = "amount"
    FAULT = "fault"
    LEGAL_ADVICE = "legal_advice"
    HUMANITY_CLAIM = "humanity_claim"
    TRANSFER_OR_DEADLINE = "transfer_or_deadline"
    CONFIG_DISCLOSURE = "config_disclosure"


class InterventionAction(StrEnum):
    """Que hizo la guardia con la frase (BR1.4, BR1.5)."""

    #: Primera de su categoria en el turno: salio la frase permitida del catalogo.
    SUBSTITUTED = "substituted"
    #: Otra de la misma categoria en el mismo turno: no salio nada en su lugar.
    DROPPED = "dropped"
    #: La guardia no pudo evaluar: la frase no salio y salio la de degradacion.
    NOT_EVALUABLE = "not_evaluable"


class FindingCode(StrEnum):
    """Un control de la revision completa que no paso (BR5.1). Lista cerrada."""

    DISCLOSURE_MISSING = "disclosure_missing"
    HUMAN_ROUTE_MISSED = "human_route_missed"
    PII_FOUND = "pii_found"
    ATTACHMENT_MISSING = "attachment_missing"


#: Que codigo corresponde a cada uno de los cuatro controles. Un control en
#: falso lleva **exactamente** su codigo entre los hallazgos, y uno en verdadero
#: no lo lleva: la marca y la lista no pueden decir cosas distintas.
FINDING_OF_CONTROL: dict[str, FindingCode] = {
    "disclosure_ok": FindingCode.DISCLOSURE_MISSING,
    "human_route_ok": FindingCode.HUMAN_ROUTE_MISSED,
    "pii_ok": FindingCode.PII_FOUND,
    "explainability_ok": FindingCode.ATTACHMENT_MISSING,
}


class DisclosureRecord(Frozen):
    """Que la apertura con la divulgacion salio, por que canal, en que idioma y cuando.

    Una por caso y canal: un caso de voz retomado por chat lleva dos (BR4.1,
    BR4.2). Guarda la **clave** de la apertura que salio, no su texto.
    """

    disclosure_id: str = Field(min_length=1, max_length=ID_MAX_LENGTH)
    tenant_id: TenantId = Field(pattern=TENANT_ID_PATTERN)
    case_id: str = Field(min_length=1, max_length=ID_MAX_LENGTH)
    channel: DisclosureChannel
    language: Locale
    catalog_key: str = Field(pattern=CATALOG_KEY_PATTERN, max_length=CATALOG_KEY_MAX_LENGTH)
    disclosed_at: AwareDatetime


def _problema_de_categoria(
    action: InterventionAction, category: GuardCategory | None, pattern_id: str | None
) -> str | None:
    """Que falla entre la accion, la categoria y el patron, o nada (BR1.5, BR1.6)."""
    sin_evaluar = action is InterventionAction.NOT_EVALUABLE
    if sin_evaluar != (category is None):
        return (
            "una intervencion lleva categoria si y solo si la guardia pudo "
            f"evaluar la frase (accion '{action.value}', categoria "
            f"{category.value if category else 'vacia'}) (BR1.5)"
        )
    if (category is None) != (pattern_id is None):
        return "la categoria y el patron que la detecto van juntos, o no va ninguno (BR1.6)"
    return None


def _problema_de_clave(action: InterventionAction, catalog_key: str | None) -> str | None:
    """Que falla entre la accion y la clave que salio, o nada (BR1.4, BR1.5)."""
    descartada = action is InterventionAction.DROPPED
    if descartada != (catalog_key is None):
        return (
            "una frase sustituida o no evaluable deja salir una clave del "
            "catalogo, y solo la descartada no deja ninguna "
            f"(accion '{action.value}') (BR1.4, BR1.5)"
        )
    return None


class InterventionDraft(Frozen):
    """Una intervencion **sin persistir**, tal como la devuelve la guardia (`GuardResult`).

    La guardia corre sobre cada frase antes de que exista el turno que la
    contendra, y a veces antes de que exista el caso: en el chat publico la
    primera respuesta sale sin caso abierto. Por eso lo que devuelve lleva la
    categoria, el patron, la accion y la clave que salio, y **ningun
    identificador**. Quien persiste --el punto unico de salida de U12, cuando el
    turno ya esta anexado-- la completa con `complete()`.

    Las invariantes son las mismas que las de la fila, con las mismas palabras:
    una intervencion que no se puede guardar no se puede ni construir.
    """

    category: GuardCategory | None
    pattern_id: str | None = Field(pattern=PATTERN_ID_PATTERN, max_length=PATTERN_ID_MAX_LENGTH)
    action: InterventionAction
    catalog_key: str | None = Field(pattern=CATALOG_KEY_PATTERN, max_length=CATALOG_KEY_MAX_LENGTH)

    @model_validator(mode="after")
    def _invariantes(self) -> Self:
        problema = _problema_de_categoria(self.action, self.category, self.pattern_id)
        problema = problema or _problema_de_clave(self.action, self.catalog_key)
        if problema is not None:
            raise ValueError(problema)
        return self

    def complete(
        self,
        *,
        intervention_id: str,
        tenant_id: TenantId,
        case_id: str,
        turn_id: str,
        occurred_at: datetime,
    ) -> GuardIntervention:
        """La fila que se guarda, con los identificadores que la guardia no conocia."""
        return GuardIntervention(
            intervention_id=intervention_id,
            tenant_id=tenant_id,
            case_id=case_id,
            turn_id=turn_id,
            category=self.category,
            pattern_id=self.pattern_id,
            action=self.action,
            catalog_key=self.catalog_key,
            occurred_at=occurred_at,
        )


class GuardIntervention(Frozen):
    """Una frase que la guardia no dejo salir, y que salio en su lugar (BR1.6).

    Guarda la categoria y el patron que la detectaron, **nunca la frase
    original**: podria contener lo que el visitante dijo, y lo que si salio ya
    esta en la transcripcion (SEC-U10.3).

    Cuando la guardia no pudo evaluar no hay categoria ni patron que nombrar, y
    por eso los dos van vacios exactamente en ese caso; `entities.md` los marca
    obligatorios, y esta es la unica excepcion, la que exige BR1.5.
    """

    intervention_id: str = Field(min_length=1, max_length=ID_MAX_LENGTH)
    tenant_id: TenantId = Field(pattern=TENANT_ID_PATTERN)
    case_id: str = Field(min_length=1, max_length=ID_MAX_LENGTH)
    turn_id: str = Field(min_length=1, max_length=ID_MAX_LENGTH)
    category: GuardCategory | None
    pattern_id: str | None = Field(pattern=PATTERN_ID_PATTERN, max_length=PATTERN_ID_MAX_LENGTH)
    action: InterventionAction
    #: La frase permitida que salio; vacia solo cuando la frase se descarto.
    catalog_key: str | None = Field(pattern=CATALOG_KEY_PATTERN, max_length=CATALOG_KEY_MAX_LENGTH)
    occurred_at: AwareDatetime

    @model_validator(mode="after")
    def _categoria_y_patron_solo_si_se_evaluo(self) -> Self:
        problema = _problema_de_categoria(self.action, self.category, self.pattern_id)
        if problema is not None:
            raise ValueError(problema)
        return self

    @model_validator(mode="after")
    def _clave_salvo_si_se_descarto(self) -> Self:
        problema = _problema_de_clave(self.action, self.catalog_key)
        if problema is not None:
            raise ValueError(problema)
        return self


class ComplianceReview(Frozen):
    """La revision completa de los cuatro controles, al cierre o en la derivacion (FR7.7).

    Una por caso y turno revisado: repetir la revision del mismo punto no crea
    otra (BR6.3). `reviewed_through_turn` es el ultimo turno revisado, el de la
    derivacion si la hubo (BR5.2).
    """

    review_id: str = Field(min_length=1, max_length=ID_MAX_LENGTH)
    tenant_id: TenantId = Field(pattern=TENANT_ID_PATTERN)
    case_id: str = Field(min_length=1, max_length=ID_MAX_LENGTH)
    disclosure_ok: bool
    human_route_ok: bool
    pii_ok: bool
    explainability_ok: bool
    #: Codigos cerrados, nunca texto libre; vacia si todo paso. Se guarda en un
    #: orden canonico para que dos revisiones iguales se escriban iguales.
    findings: tuple[FindingCode, ...] = ()
    reviewed_through_turn: str = Field(min_length=1, max_length=ID_MAX_LENGTH)
    reviewed_at: AwareDatetime

    @field_validator("findings")
    @classmethod
    def _sin_repetidos_y_en_orden(
        cls, findings: tuple[FindingCode, ...]
    ) -> tuple[FindingCode, ...]:
        if len(set(findings)) != len(findings):
            msg = f"la revision repite un hallazgo: {[f.value for f in findings]}"
            raise ValueError(msg)
        orden = list(FindingCode)
        return tuple(sorted(findings, key=orden.index))

    @model_validator(mode="after")
    def _cada_control_concuerda_con_su_hallazgo(self) -> Self:
        for control, codigo in FINDING_OF_CONTROL.items():
            paso: bool = getattr(self, control)
            presente = codigo in self.findings
            if paso == presente:
                msg = (
                    f"'{control}'={paso} contradice la lista de hallazgos "
                    f"('{codigo.value}' presente={presente}); un control que no paso "
                    "lleva exactamente su codigo (BR5.1)"
                )
                raise ValueError(msg)
        return self

    @property
    def passed(self) -> bool:
        """Los cuatro controles pasaron. Es la condicion de BR6.1 para cerrar."""
        return not self.findings
