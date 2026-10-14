"""Lo que el ajustador anota para las reglas de triage: monto, cobertura y fraude.

De los seis campos que leen las reglas de triage (`rules/fields.py`), dos se derivan de lo
que la persona conto y **tres los anota un ajustador desde la bandeja** (decision del
2026-10-03): el monto estimado, la cobertura disputada y la sospecha de fraude. Nunca
salen de la conversacion ni de un modelo --el monto lo estima el ajustador, y un juicio
del modelo como insumo de una regla es lo mismo con un paso en medio--. El sexto,
`unlisted_driver`, no es de esta pieza.

**Tambien los anota, sobre su propio caso, el visitante que hace de ajustador en la
demostracion** (2026-10-13), con su identificador de visitante en `noted_by`. Es la marca que
separa lo suyo de lo del personal: lo que escribio el personal no se le muestra ni lo pisa.

**Cada dato puede estar sin anotar, y sin anotar no es "no".** Una regla que lee un campo
ausente no dispara (BR2.1 de U9); una que lee `false` afirma que alguien lo comprobo. Por
eso los tres admiten `None`, y `rule_inputs` **omite** los que no estan anotados en vez de
escribirlos en falso: un `False` por no saber seria una regla que no dispara *diciendo*
que miro.

**Los nombres son los del vocabulario del motor** (`claim_amount`, `coverage_disputed`,
`fraud_suspected`): la columna, la clave del historial y el insumo de la regla se llaman
igual, y la correspondencia es un grep. Una prueba comprueba que son campos de triage
declarados y que cada aseguradora tiene al menos una regla que los lee --el hueco que
tuvieron hasta hoy: un campo que nadie produce no falla, simplemente no dispara--.

**Una fila por caso, no un historial.** Lo que vale es lo ultimo; quien cambio que y
cuando vive en el historial del caso, que ya es de solo anexar. Ninguna conexion propia:
toda consulta pasa por el punto unico de sesion, con la aseguradora fijada.

**El monto es la cifra interna** del motor --la que comparan las reglas--, y el proyecto la
muestra en pesos multiplicandola por mil. Esta pieza no convierte nada.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from untangle.rules.fields import RuleValue
from untangle.tenancy import api as tenancy
from untangle.tenancy.models import TenantId

CLAIM_AMOUNT: Final = "claim_amount"
COVERAGE_DISPUTED: Final = "coverage_disputed"
FRAUD_SUSPECTED: Final = "fraud_suspected"

#: Los tres datos que anota un ajustador, en el orden en que la pantalla los muestra.
NOTED_FIELDS: Final = (CLAIM_AMOUNT, COVERAGE_DISPUTED, FRAUD_SUSPECTED)

#: El tope de la cifra interna del monto: diez mil millones de pesos. Es un limite de
#: cordura para que un cero de mas no llegue al motor, no una regla de negocio; las
#: reglas de hoy miran 1.000 y 10.000. El piso (no negativo) lo impone ademas la base.
MAX_CLAIM_AMOUNT: Final = 10_000_000

#: Como se escribe "sin anotar" en el historial: un token del registro tecnico, no una frase.
UNSET: Final = "unset"


@dataclass(frozen=True)
class TriageValues:
    """Los tres datos tal como se anotan: cada uno `None` si esta sin anotar."""

    claim_amount: int | None = None
    coverage_disputed: bool | None = None
    fraud_suspected: bool | None = None

    def __post_init__(self) -> None:
        monto = self.claim_amount
        # `bool` es un `int` en Python: `True` como monto serian 1, y nadie lo quiso decir.
        if monto is not None and (isinstance(monto, bool) or not 0 <= monto <= MAX_CLAIM_AMOUNT):
            msg = f"el monto estimado es un entero entre 0 y {MAX_CLAIM_AMOUNT}, no {monto!r}"
            raise ValueError(msg)

    def is_empty(self) -> bool:
        """Si no hay nada anotado: los tres sin anotar, como cuando nadie ha escrito nada."""
        return all(valor is None for valor in self.as_mapping().values())

    def as_mapping(self) -> dict[str, int | bool | None]:
        return {
            CLAIM_AMOUNT: self.claim_amount,
            COVERAGE_DISPUTED: self.coverage_disputed,
            FRAUD_SUSPECTED: self.fraud_suspected,
        }

    def rule_inputs(self) -> dict[str, RuleValue]:
        """Los insumos de las reglas: solo lo anotado, y **nunca** un falso por no saber."""
        return {clave: valor for clave, valor in self.as_mapping().items() if valor is not None}


@dataclass(frozen=True)
class TriageNote:
    """Lo anotado de un caso, con quien lo anoto y cuando.

    `noted_by` es el identificador de la persona de la aseguradora, o el del visitante de la
    demostracion cuando lo anoto el desde su enlace.
    """

    values: TriageValues
    noted_by: str
    updated_at: datetime


@dataclass(frozen=True)
class TriageChange:
    """Un dato que cambio: su nombre y el valor de antes y de ahora, ya como texto tecnico."""

    field_key: str
    before: str
    after: str


def describe(valor: int | bool | None) -> str:
    """Un valor en el registro tecnico del historial: `unset`, `true`, `false` o el entero."""
    if valor is None:
        return UNSET
    if isinstance(valor, bool):
        return "true" if valor else "false"
    return str(valor)


def changes_between(previous: TriageValues, new: TriageValues) -> tuple[TriageChange, ...]:
    """Los datos cuyo valor cambio, en el orden de `NOTED_FIELDS`.

    Guardar lo mismo otra vez no cambia nada y no deja entrada: un historial con una linea
    por cada pulsacion de "guardar" no dice que paso, dice cuantas veces se pulso.
    """
    antes, ahora = previous.as_mapping(), new.as_mapping()
    return tuple(
        TriageChange(clave, describe(antes[clave]), describe(ahora[clave]))
        for clave in NOTED_FIELDS
        if antes[clave] != ahora[clave]
    )


_LEER = """
    SELECT claim_amount, coverage_disputed, fraud_suspected, noted_by, updated_at
    FROM case_triage_note
    WHERE tenant_id = :tenant_id AND case_id = :case_id
"""

# `FOR UPDATE` para que dos ajustadores que anotan el mismo caso a la vez no lean la misma
# fila "de antes": el segundo espera al primero y su entrada de historial parte de lo que
# el primero dejo. Sin fila no hay nada que bloquear, y la llave primaria decide la carrera.
_LEER_PARA_CAMBIAR = _LEER + " FOR UPDATE"

_ESCRIBIR = """
    INSERT INTO case_triage_note (tenant_id, case_id, claim_amount, coverage_disputed,
                                  fraud_suspected, noted_by, updated_at)
    VALUES (:tenant_id, :case_id, :claim_amount, :coverage_disputed, :fraud_suspected,
            :noted_by, :updated_at)
    ON CONFLICT (tenant_id, case_id) DO UPDATE
    SET claim_amount = EXCLUDED.claim_amount,
        coverage_disputed = EXCLUDED.coverage_disputed,
        fraud_suspected = EXCLUDED.fraud_suspected,
        noted_by = EXCLUDED.noted_by,
        updated_at = EXCLUDED.updated_at
"""


def _nota(fila: Mapping[str, Any]) -> TriageNote:
    return TriageNote(
        values=TriageValues(
            claim_amount=fila["claim_amount"],
            coverage_disputed=fila["coverage_disputed"],
            fraud_suspected=fila["fraud_suspected"],
        ),
        noted_by=str(fila["noted_by"]),
        updated_at=fila["updated_at"],
    )


async def read(tenant_id: TenantId, case_id: str) -> TriageNote | None:
    """Lo anotado del caso, o nada si nadie ha anotado nada."""
    async with tenancy.session_for(tenant_id) as sesion:
        fila = await tenancy.fetch_one(sesion, _LEER, tenant_id=tenant_id, case_id=case_id)
    return None if fila is None else _nota(fila)


async def read_for_update(
    sesion: tenancy.TenantSession, tenant_id: TenantId, case_id: str
) -> TriageNote | None:
    """Lo anotado, dentro de la transaccion de quien va a cambiarlo."""
    fila = await tenancy.fetch_one(sesion, _LEER_PARA_CAMBIAR, tenant_id=tenant_id, case_id=case_id)
    return None if fila is None else _nota(fila)


async def write(  # noqa: PLR0913 -- la sesion, el caso, los valores, quien y el reloj
    sesion: tenancy.TenantSession,
    tenant_id: TenantId,
    case_id: str,
    values: TriageValues,
    *,
    noted_by: str,
    now: datetime,
) -> None:
    """Deja lo anotado como lo ultimo del caso, dentro de la transaccion de quien llama."""
    await tenancy.execute_sql(
        sesion,
        _ESCRIBIR,
        tenant_id=tenant_id,
        case_id=case_id,
        noted_by=noted_by,
        updated_at=now,
        **values.as_mapping(),
    )


async def rule_inputs_of(tenant_id: TenantId, case_id: str) -> dict[str, RuleValue]:
    """Lo anotado del caso como insumos de las reglas; vacio si nadie anoto nada."""
    nota = await read(tenant_id, case_id)
    return {} if nota is None else nota.values.rule_inputs()
