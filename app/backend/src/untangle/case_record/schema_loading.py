"""La carga de los dos archivos versionados: campos por tipo y transiciones.

Lo que este modulo defiende es que **un esquema a medias no arranque**. Es la
unidad cuyo fallo no se manifiesta: un campo que falta en la lista no rompe
ninguna pantalla, solo hace que la completitud publique una cifra sobre un
denominador equivocado, y eso no lo nota nadie.

Por eso valida al cargar y falla nombrando la diferencia, en vez de devolver lo
que pudo leer.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from untangle.case_record.models import (
    CaseSchemaError,
    CaseState,
    FieldDefinition,
    RecordType,
    Transition,
)

#: Los siete campos centrales que FR1.1 declara para un siniestro. Se comprueban
#: contra el archivo al cargar: un esquema que declare seis publica una
#: completitud sobre seis, y la cifra mentiria sin que nadie lo note (BR1.4).
CLAIM_FIELDS: tuple[str, ...] = (
    "identity_and_policy",
    "incident_datetime",
    "location",
    "description",
    "vehicle_and_driver",
    "other_parties",
    "injuries",
)

#: Los diecisiete campos de una solicitud de cotizacion (U19), por bloque y en el
#: orden en que se preguntan. Se comprueban contra el archivo al cargar, igual que
#: los del siniestro: una solicitud que declare dieciseis publica una completitud
#: sobre dieciseis, y la cifra mentiria sin que nadie lo note. Las claves son las de
#: `docs/reference/estructura-solicitud-cotizacion.md`.
QUOTE_FIELDS_BY_BLOCK: dict[str, tuple[str, ...]] = {
    "quote_driver": ("driver_name", "driver_birth_date", "license_years", "license_jurisdiction"),
    "quote_vehicle": (
        "vehicle_year",
        "vehicle_make",
        "vehicle_model",
        "vin",
        "salvage_title",
        "vehicle_age_years",
    ),
    "quote_usage": ("use_type", "annual_mileage_band", "garaging_jurisdiction"),
    "quote_history": (
        "at_fault_losses_3y",
        "claims_3y",
        "prior_coverage_active",
        "lapse_months",
    ),
}
QUOTE_FIELDS: tuple[str, ...] = tuple(
    clave for claves in QUOTE_FIELDS_BY_BLOCK.values() for clave in claves
)

#: Los campos del siniestro que solo llegan a confirmado tras la lectura en voz
#: alta. Eran tres (lugar, vehiculo y conductor, lesiones; BR2.2, ADR-005) y desde
#: el 2026-10-06 no hay ninguno: decision de Miguel (P4), lo dicho se guarda y se
#: corrige si hace falta. La comprobacion se queda para que un campo con lectura
#: no vuelva a entrar al siniestro sin que alguien lo decida aqui.
READBACK_FIELDS: frozenset[str] = frozenset()


def schema_dir() -> Path:
    """El directorio de los archivos versionados, junto al codigo que los lee."""
    return Path(__file__).parent / "schema"


def _cargar(nombre: str, directorio: Path | None = None) -> dict[str, Any]:
    archivo = (directorio or schema_dir()) / nombre
    if not archivo.is_file():
        msg = f"falta el archivo versionado '{nombre}' en {archivo.parent}"
        raise CaseSchemaError(msg)
    cargado: Any = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    if not isinstance(cargado, dict):
        msg = f"'{nombre}' no es un mapa: el archivo esta vacio o mal formado"
        raise CaseSchemaError(msg)
    return cargado


def load_fields(directorio: Path | None = None) -> dict[RecordType, tuple[FieldDefinition, ...]]:
    """Los campos declarados por tipo de registro (BR1.3).

    Falla si un tipo del enum no aparece, si aparece uno que el enum no conoce,
    o si el siniestro no declara exactamente sus siete campos.
    """
    datos = _cargar("fields.yaml", directorio)
    crudos = datos.get("record_types")
    if not isinstance(crudos, dict):
        msg = "'fields.yaml' no declara 'record_types'"
        raise CaseSchemaError(msg)

    declarados = set(crudos)
    esperados = {t.value for t in RecordType}
    if declarados != esperados:
        faltan = sorted(esperados - declarados)
        sobran = sorted(declarados - esperados)
        msg = f"'fields.yaml' no cubre los tipos de registro: faltan {faltan}, sobran {sobran}"
        raise CaseSchemaError(msg)

    resultado: dict[RecordType, tuple[FieldDefinition, ...]] = {}
    for nombre, cuerpo in crudos.items():
        campos = (cuerpo or {}).get("fields") or []
        try:
            resultado[RecordType(nombre)] = tuple(FieldDefinition(**c) for c in campos)
        except Exception as error:
            msg = f"'fields.yaml', tipo '{nombre}': {error}"
            raise CaseSchemaError(msg) from error

    claim = tuple(c.key for c in resultado[RecordType.CLAIM])
    if claim != CLAIM_FIELDS:
        msg = (
            f"'fields.yaml' declara para el siniestro {list(claim)} y FR1.1 exige "
            f"{list(CLAIM_FIELDS)}, en ese orden"
        )
        raise CaseSchemaError(msg)

    quote = tuple((c.key, c.source_block) for c in resultado[RecordType.QUOTE_REQUEST])
    esperados_quote = tuple(
        (clave, bloque) for bloque, claves in QUOTE_FIELDS_BY_BLOCK.items() for clave in claves
    )
    if quote != esperados_quote:
        msg = (
            f"'fields.yaml' declara para la solicitud de cotizacion {list(quote)} y los "
            f"cuatro bloques de U19 exigen {list(esperados_quote)}, en ese orden"
        )
        raise CaseSchemaError(msg)
    for definicion in resultado[RecordType.QUOTE_REQUEST]:
        if not definicion.requires_readback:
            msg = (
                f"'fields.yaml': el campo '{definicion.key}' de la solicitud no exige lectura; "
                "la confirmacion es por bloque y un bloque sin campos que la exijan no se "
                "podria confirmar (AC6.1.2)"
            )
            raise CaseSchemaError(msg)

    con_lectura = {c.key for c in resultado[RecordType.CLAIM] if c.requires_readback}
    if con_lectura != READBACK_FIELDS:
        msg = (
            f"'fields.yaml' exige lectura en voz alta para {sorted(con_lectura)} y "
            f"la decision de Miguel del 2026-10-06 (P4) la exige para {sorted(READBACK_FIELDS)}"
        )
        raise CaseSchemaError(msg)

    return resultado


def load_transitions(directorio: Path | None = None) -> tuple[Transition, ...]:
    """La tabla versionada de transiciones (BR3.2).

    Falla si una fila nombra un estado que no existe, si dos filas comparten
    identificador, o si alguna sale de `closed`, que es terminal.
    """
    datos = _cargar("transitions.yaml", directorio)
    crudas = datos.get("transitions")
    if not isinstance(crudas, list) or not crudas:
        msg = "'transitions.yaml' no declara ninguna transicion"
        raise CaseSchemaError(msg)

    filas: list[Transition] = []
    for cruda in crudas:
        try:
            filas.append(
                Transition(
                    id=cruda["id"],
                    from_state=CaseState(cruda["from"]),
                    to_state=CaseState(cruda["to"]),
                    when=cruda["when"],
                    conditions=tuple(cruda.get("conditions") or ()),
                )
            )
        except Exception as error:
            msg = f"'transitions.yaml', fila {cruda!r}: {error}"
            raise CaseSchemaError(msg) from error

    identificadores = [f.id for f in filas]
    if len(set(identificadores)) != len(identificadores):
        msg = "'transitions.yaml' repite un identificador de transicion"
        raise CaseSchemaError(msg)

    parejas = [(f.from_state, f.to_state) for f in filas]
    if len(set(parejas)) != len(parejas):
        msg = "'transitions.yaml' declara dos veces la misma pareja de estados"
        raise CaseSchemaError(msg)

    if any(f.from_state is CaseState.CLOSED for f in filas):
        msg = "'transitions.yaml' saca una transicion de 'closed', que es terminal"
        raise CaseSchemaError(msg)

    return tuple(filas)


@lru_cache(maxsize=1)
def fields_by_record_type() -> dict[RecordType, tuple[FieldDefinition, ...]]:
    """Los campos del proceso, cargados una vez."""
    return load_fields()


@lru_cache(maxsize=1)
def transitions() -> tuple[Transition, ...]:
    """La tabla del proceso, cargada una vez."""
    return load_transitions()
