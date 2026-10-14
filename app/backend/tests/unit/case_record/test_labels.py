"""Ningun valor interno del caso se imprime hacia una persona (SEC-U4.15).

Lo que se prueba es la correspondencia **en los dos sentidos**: que cada valor
del enum tenga su clave, y que cada clave exista en los dos idiomas. Con uno
solo, un valor nuevo saldria vacio en pantalla o una clave muerta se quedaria
acumulando en el catalogo, que es el fallo que la landing ya muestra.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

import pytest

from untangle.base import Locale
from untangle.case_record import labels, schema_loading
from untangle.case_record.models import (
    CaseState,
    DerivationReason,
    RecordType,
    Resolution,
)
from untangle.copy_catalog import api as copy_api


@pytest.mark.parametrize(
    ("enum", "mapa"),
    [
        (CaseState, labels.STATE_KEYS),
        (Resolution, labels.RESOLUTION_KEYS),
        (RecordType, labels.RECORD_TYPE_KEYS),
        (DerivationReason, labels.DERIVATION_REASON_KEYS),
    ],
    ids=["estado", "resolucion", "tipo_de_registro", "motivo_de_derivacion"],
)
def test_todo_valor_del_enum_tiene_su_clave(
    enum: type[StrEnum], mapa: Mapping[StrEnum, str]
) -> None:
    """Un valor nuevo sin clave saldria vacio en pantalla y no fallaria en
    ningun sitio. Esta prueba es ese sitio."""
    assert set(enum) == set(mapa)


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_toda_clave_existe_en_los_dos_idiomas(idioma: Locale) -> None:
    """La paridad no es cortesia: una clave que falta en un idioma deja media
    pantalla sin traducir y no se nota hasta que alguien la abre.

    Se compara la frase **contra la clave**, y no contra la cadena vacia: el
    catalogo devuelve la clave misma cuando la entrada falta --nunca lanza y nunca
    devuelve vacio--, asi que la version anterior de esta prueba pasaba con una
    clave inexistente. Lo encontro U14 al anadir las etiquetas de los campos.
    """
    faltantes = [
        clave
        for clave in sorted(labels.all_keys())
        if copy_api.t(clave, locale=idioma).strip() in ("", clave)
    ]

    assert faltantes == []


def test_todo_campo_del_esquema_tiene_su_etiqueta() -> None:
    """Los dos sentidos, como con los enums (U14).

    El juego de campos lo declara `schema/fields.yaml`. Un campo nuevo sin
    etiqueta se veria en la bandeja como su clave interna --`vehicle_and_driver`--,
    que es lo mismo que SEC-U4.15 prohibe de los estados; una etiqueta sin campo
    seria una clave muerta en el catalogo.
    """
    del_esquema = {
        definicion.key
        for definiciones in schema_loading.fields_by_record_type().values()
        for definicion in definiciones
    }

    assert del_esquema == set(labels.FIELD_KEYS)


def test_ningun_valor_interno_se_usa_como_etiqueta() -> None:
    """Las claves son claves, no los valores del enum disfrazados.

    Si la clave fuera el propio valor --`awaiting_insured`-- una pantalla que se
    olvidara de resolverla imprimiria el valor interno y se veria "casi bien",
    que es la forma mas facil de que se quede asi.
    """
    for estado, clave in labels.STATE_KEYS.items():
        assert clave != estado.value
        assert clave.startswith("case.state.")


def test_el_marcador_de_campo_no_disponible_existe() -> None:
    """El caso se abre igual con el campo marcado, y el marcador es texto que
    lee una persona, asi que sale del catalogo como cualquier otro."""
    for idioma in ("es", "en"):
        assert copy_api.t(labels.FIELD_UNAVAILABLE, locale=idioma).strip()
