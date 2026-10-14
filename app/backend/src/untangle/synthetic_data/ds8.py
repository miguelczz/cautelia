"""DS-8, las colisiones de aislamiento, regeneradas por el generador (F3.2, paso 7; BR7.3).

U2 escribio DS-8 a mano porque el generador todavia no existia, y dejo dicho que
**su contenido es el contrato**, no el metodo que lo produjo. Aqui el generador lo
produce con la misma semilla y los mismos identificadores: cambian solo
`generated` (ahora `true`) y su motivo. Las pruebas de aislamiento de U2 leen las
mismas filas y no cambian (CG-U7-6).

## Por que los identificadores estan escritos aqui

Cada valor de DS-8 --el numero de poliza que se repite, el nombre, el caso, las
huellas del navegador-- es un **identificador estable** que otras pruebas nombran
por su valor: regenerarlos desde la semilla los cambiaria y romperia a U2. Por eso
se conservan tal cual, igual que se conserva el identificador de un caso de golden
set.

Lo que **no** esta escrito aqui es a que aseguradora pertenece cada fila: DS-8
necesita dos emisoras y una agencia, y las toma de la configuracion versionada
por su tipo y en orden de identificador. Ningun identificador de aseguradora se
escribe en este archivo (regla de `project.md`).

## El identificador de caso colisiona en los enlaces, no en la tabla del caso

Esta fixture nacio declarando el **mismo identificador de caso** en dos aseguradoras.
Cabe donde U2 la ejercita --`case_access_link`, que nombra el caso como texto y no
tiene llave foranea hacia el-- y **no cabe** en `case_record`, cuya llave primaria es
`case_id` a secas: sembrar el segundo choca contra `case_record_pkey`.

Las dos cosas estaban aprobadas y se contradecian, y nadie lo habia visto porque hasta
U14 **ningun codigo habia sembrado nunca las filas `cases` de este archivo**. Decision
de Miguel del 2026-09-28: manda el esquema. El identificador de caso es unico en toda
la base, la fila de la segunda emisora lleva el suyo, y lo que esas dos filas siguen
colisionando --numero de poliza y nombre del asegurado-- es lo que hace que una prueba
de aislamiento sobre casos signifique algo.

El enlace no cambia: los dos siguen apuntando al mismo identificador, que es la
colision que U2 prueba y la que RT-4 describe.

## Las polizas de DS-8 tambien son polizas del corpus

La colision de numero de poliza solo prueba algo si el corpus la tiene: por eso las
polizas de DS-8 salen tambien como polizas emitidas, con su numero, su asegurado y
su vigencia (`fixed_policies`), y U8 ingiere la colision tal como DS-8 la declara.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

from untangle.tenancy.config import LoadedTenants
from untangle.tenancy.models import TenantConfig, TenantKind

__all__ = [
    "DS8_OUTPUT",
    "DS8Error",
    "DS8Roles",
    "FixedPolicy",
    "compose_ds8",
    "fixed_policies",
    "roles_from",
]

#: La ruta de DS-8 dentro de `app/data/`: la misma que escribio U2 (CG-U7-6).
DS8_OUTPUT: Final = "fixtures/ds8_isolation.json"

#: La semilla de DS-8, que es la de todo el conjunto (FD-U7-4).
_SEMILLA: Final = 20260916

_MOTIVO: Final = (
    "Regenerada por el generador sintetico de U7 (`mise run synthetic:generate`) con la "
    "misma semilla y los mismos identificadores estables que la version escrita a mano en "
    "U2: su contenido es el contrato, no el metodo que lo produjo (BR7.3, CG-U7-6)."
)

_PROPOSITO: Final = (
    "Colisiones a proposito entre aseguradoras: mismo numero de poliza, mismo nombre de "
    "asegurado, mismo identificador de caso y misma clave de navegador en dos aseguradoras "
    "distintas. Una prueba de aislamiento con datos distintos pasaria aunque el aislamiento "
    "no existiera; estas filas son lo unico que la hace significar algo (AC4.11.3, DS-8)."
)

_AVISO: Final = "Cien por ciento sintetica. Ninguna persona, poliza ni matricula real (P8, W6, R9)."

# --- Los identificadores estables de U2 ----------------------------------------

_POLIZA_COMPARTIDA: Final = "POL-480915"
_ASEGURADO_COMPARTIDO: Final = "Alex Moreno"
_CASO_COMPARTIDO: Final = "CASE-7F3A21"
#: El caso de la segunda emisora. **Tiene su propio identificador y no repite el
#: de arriba**, porque `case_record` no lo admite: su llave primaria es `case_id`
#: a secas, asi que dos aseguradoras no pueden tener casos con el mismo. Lo que
#: esta fila colisiona son el numero de poliza y el nombre del asegurado, que si
#: caben. Decision de Miguel del 2026-09-28; ver el docstring del modulo.
_CASO_DE_LA_SEGUNDA_EMISORA: Final = "CASE-7F3A22"
_NAVEGADOR_COMPARTIDO: Final = "6f4b2c1d9a8e7350c2b1a0f9e8d7c6b5a4938271605f4e3d2c1b0a9f8e7d6c5b"

_POLIZA_DE_LA_AGENCIA: Final = "POL-173620"
_ASEGURADO_DE_LA_AGENCIA: Final = "Rosa Iturbe"
_CASO_DE_LA_AGENCIA: Final = "CASE-91BD04"
_NAVEGADOR_DE_LA_AGENCIA: Final = "7a5c3d2e0b9f8461d3c2b1a0f9e8d7c6b5a4938271605f4e3d2c1b0a9f8e7d6c"

_ORIGEN: Final = "https://demo.untangle.local"


class DS8Error(ValueError):
    """La configuracion no tiene las aseguradoras que DS-8 necesita."""


@dataclass(frozen=True)
class DS8Roles:
    """Las tres aseguradoras de DS-8, por su papel: dos emisoras y una agencia."""

    carrier_a: TenantConfig
    carrier_b: TenantConfig
    agency: TenantConfig


def roles_from(tenants: LoadedTenants) -> DS8Roles:
    """Las dos primeras emisoras y la primera agencia, en orden de identificador."""
    emisoras = sorted(
        (t for t in tenants.available if t.kind is TenantKind.CARRIER), key=lambda t: t.tenant_id
    )
    agencias = sorted(
        (t for t in tenants.available if t.kind is TenantKind.AGENCY), key=lambda t: t.tenant_id
    )
    if len(emisoras) < 2 or not agencias:
        msg = (
            "DS-8 necesita dos emisoras y una agencia en app/config/tenants/, y hay "
            f"{len(emisoras)} emisora(s) y {len(agencias)} agencia(s)"
        )
        raise DS8Error(msg)
    return DS8Roles(carrier_a=emisoras[0], carrier_b=emisoras[1], agency=agencias[0])


@dataclass(frozen=True)
class FixedPolicy:
    """Una poliza que DS-8 declara y que el corpus emite tal cual."""

    tenant_id: str
    policy_number: str
    insured_name: str
    effective_from: date
    effective_to: date


def fixed_policies(roles: DS8Roles) -> tuple[FixedPolicy, ...]:
    """Las tres polizas de DS-8, en el orden de sus filas."""
    return (
        FixedPolicy(
            roles.carrier_a.tenant_id,
            _POLIZA_COMPARTIDA,
            _ASEGURADO_COMPARTIDO,
            date(2026, 1, 1),
            date(2027, 1, 1),
        ),
        FixedPolicy(
            roles.carrier_b.tenant_id,
            _POLIZA_COMPARTIDA,
            _ASEGURADO_COMPARTIDO,
            date(2026, 3, 15),
            date(2027, 3, 15),
        ),
        FixedPolicy(
            roles.agency.tenant_id,
            _POLIZA_DE_LA_AGENCIA,
            _ASEGURADO_DE_LA_AGENCIA,
            date(2026, 2, 1),
            date(2027, 2, 1),
        ),
    )


def _colisiones(a: str, b: str) -> list[dict[str, object]]:
    return [
        {
            "field": "policy_number",
            "value": _POLIZA_COMPARTIDA,
            "tenants": [a, b],
            "reason": (
                "Dos aseguradoras emiten una poliza con el mismo numero. Es posible "
                "precisamente porque el numero no lleva iniciales de la aseguradora: si las "
                "llevara, esta colision seria imposible por construccion y la prueba de "
                "aislamiento no demostraria nada. Consumida por la unidad dueña de las "
                "polizas (U8); U2 no crea esa tabla."
            ),
        },
        {
            "field": "insured_name",
            "value": _ASEGURADO_COMPARTIDO,
            "tenants": [a, b],
            "reason": (
                "El mismo nombre de asegurado en dos aseguradoras. Consumida por la unidad "
                "dueña del caso (U4)."
            ),
        },
        {
            "field": "case_id",
            "value": _CASO_COMPARTIDO,
            "tenants": [a, b],
            "scope": "case_access_link",
            "reason": (
                "El mismo identificador de caso en dos aseguradoras, **sobre los enlaces de "
                "caso y no sobre la tabla del caso**. U2 la ejercita ahi: un enlace de una "
                "emisora y otro de la otra apuntan al mismo identificador y ninguno ve al "
                "otro; esa tabla no tiene llave foranea hacia el caso, asi que la colision "
                "cabe. En `case_record` no cabe: su llave primaria es `case_id` a secas, y "
                "sembrar el segundo choca. Hasta U14 nadie habia intentado sembrar las filas "
                "`cases` de esta fixture, asi que la contradiccion entre este archivo y el "
                "esquema vivio sin que nada la dijera. Decision de Miguel del 2026-09-28: "
                "manda el esquema, el identificador de caso es unico en toda la base, y esta "
                "colision se declara con su alcance en vez de describir algo imposible."
            ),
        },
        {
            "field": "visitor_key_hash",
            "value": _NAVEGADOR_COMPARTIDO,
            "tenants": [a, b],
            "reason": (
                "El mismo navegador visita las dos demostraciones. Tiene una fila por "
                "aseguradora y ninguna ve la de la otra (BR3.5)."
            ),
        },
    ]


def _enlace(numero: int, tenant_id: str, case_id: str, digest: str) -> dict[str, object]:
    return {
        "link_id": f"LNK-DS8-{numero:04d}",
        "tenant_id": tenant_id,
        "case_id": case_id,
        "token_digest": digest,
        "access": "view_and_decide",
        "created_at": "2026-09-16T10:00:00Z",
        "expires_at": "2026-09-16T11:00:00Z",
        "revoked_at": None,
        "redeemed_count": 0,
    }


def _navegador(tenant_id: str, digest: str, creado: str, visto: str) -> dict[str, object]:
    return {
        "tenant_id": tenant_id,
        "visitor_key_hash": digest,
        "origin": _ORIGEN,
        "created_at": creado,
        "last_seen_at": visto,
    }


def compose_ds8(roles: DS8Roles) -> dict[str, object]:
    """DS-8 entera: las mismas filas y colisiones que escribio U2, ahora generada."""
    a, b, k = roles.carrier_a.tenant_id, roles.carrier_b.tenant_id, roles.agency.tenant_id
    polizas = fixed_policies(roles)
    return {
        "fixture_id": "DS-8/isolation",
        "purpose": _PROPOSITO,
        "seed": _SEMILLA,
        "generated": True,
        "generated_reason": _MOTIVO,
        "synthetic_data_notice": _AVISO,
        "collisions": _colisiones(a, b),
        "rows": {
            "policies": [
                {
                    "tenant_id": p.tenant_id,
                    "policy_number": p.policy_number,
                    "insured_name": p.insured_name,
                    "effective_from": p.effective_from.isoformat(),
                    "effective_to": p.effective_to.isoformat(),
                }
                for p in polizas
            ],
            "cases": [
                {
                    "tenant_id": a,
                    "case_id": _CASO_COMPARTIDO,
                    "policy_number": _POLIZA_COMPARTIDA,
                    "insured_name": _ASEGURADO_COMPARTIDO,
                },
                {
                    "tenant_id": b,
                    "case_id": _CASO_DE_LA_SEGUNDA_EMISORA,
                    "policy_number": _POLIZA_COMPARTIDA,
                    "insured_name": _ASEGURADO_COMPARTIDO,
                },
                {
                    "tenant_id": k,
                    "case_id": _CASO_DE_LA_AGENCIA,
                    "policy_number": _POLIZA_DE_LA_AGENCIA,
                    "insured_name": _ASEGURADO_DE_LA_AGENCIA,
                },
            ],
            "case_access_links": [
                _enlace(
                    1,
                    a,
                    _CASO_COMPARTIDO,
                    "a1b2c3d4e5f60718293a4b5c6d7e8f900112233445566778899aabbccddeeff0",
                ),
                _enlace(
                    2,
                    b,
                    _CASO_COMPARTIDO,
                    "b2c3d4e5f60718293a4b5c6d7e8f900112233445566778899aabbccddeeff0a1",
                ),
                _enlace(
                    3,
                    k,
                    _CASO_DE_LA_AGENCIA,
                    "c3d4e5f60718293a4b5c6d7e8f900112233445566778899aabbccddeeff0a1b2",
                ),
            ],
            "visitor_keys": [
                _navegador(
                    a, _NAVEGADOR_COMPARTIDO, "2026-09-16T09:00:00Z", "2026-09-16T09:30:00Z"
                ),
                _navegador(
                    b, _NAVEGADOR_COMPARTIDO, "2026-09-16T09:05:00Z", "2026-09-16T09:35:00Z"
                ),
                _navegador(
                    k, _NAVEGADOR_DE_LA_AGENCIA, "2026-09-16T09:10:00Z", "2026-09-16T09:40:00Z"
                ),
            ],
        },
    }
