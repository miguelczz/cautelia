"""Los conductores que declara cada poliza emitida (el sexto insumo del motor de reglas).

`unlisted_driver` se deriva comparando a quien conducia con los conductores que la poliza del
caso declara, y para comparar la poliza tiene que declararlos. Lo que estas pruebas vigilan no es
la forma del archivo sino lo que la comparacion de nombres necesita de los datos:

- que el **titular vaya primero** y nadie se repita, porque "figura" se decide contra esa lista;
- que un conductor adicional sea un **familiar** --los apellidos de la casa y otro nombre de
  pila--, que es el caso dificil de la comparacion y el mas comun en una poliza real;
- que la poliza de ejemplo de cada aseguradora declare a alguien ademas del titular, para que la
  demostracion tenga un conductor declarado que no sea la persona que habla;
- que **declarar conductores no mueva nada de lo ya sembrado**: el resto del archivo es el que ya
  habia, y lo vigila `test_composition` al comparar con lo versionado.
"""

from __future__ import annotations

import json
from functools import cache
from typing import Any

import pytest

from untangle.base import Locale
from untangle.synthetic_data import generator
from untangle.synthetic_data.chooser import SeededChooser
from untangle.synthetic_data.cli import CORPUS_COMPOSERS
from untangle.synthetic_data.models import DriverRef, IssuedPolicyRecord
from untangle.synthetic_data.people import (
    FAMILY_NAMES,
    GIVEN_NAMES,
    People,
    PeopleError,
    Pools,
    UsedValues,
    compose_relative_name,
)
from untangle.tenancy import config as tenancy_config

from .apoyo import RAIZ_REAL


@cache
def _generacion() -> generator.RenderedGeneration:
    return generator.render(
        generator.GenerationRequest(
            repo_root=RAIZ_REAL, data_dir=RAIZ_REAL / "app" / "data", composers=CORPUS_COMPOSERS
        )
    )


def _polizas() -> dict[str, dict[str, Any]]:
    """Cada poliza emitida del corpus, por su ruta dentro de `app/data/`."""
    return {
        ruta: json.loads(contenido)
        for ruta, contenido in _generacion().files.items()
        if "/issued_policies/" in ruta
    }


def _nombres(poliza: dict[str, Any]) -> list[str]:
    return [d["full_name"] for d in poliza["drivers"]]


def _idioma_de_la_emisora(poliza: dict[str, Any]) -> Locale:
    tenants = tenancy_config.load(RAIZ_REAL / "app" / "config" / "tenants")
    emisora = next(t for t in tenants.available if t.tenant_id == poliza["issuer_tenant"])
    return emisora.default_language


def test_cada_poliza_declara_primero_a_su_titular_y_a_nadie_dos_veces() -> None:
    polizas = _polizas()
    assert polizas, "no hay polizas emitidas que revisar"

    for ruta, poliza in polizas.items():
        nombres = _nombres(poliza)
        assert nombres, f"{ruta}: no declara conductores"
        assert nombres[0] == poliza["named_insured"]["full_name"], ruta
        assert len(set(nombres)) == len(nombres), ruta


def test_la_poliza_de_ejemplo_de_cada_aseguradora_declara_a_alguien_ademas_del_titular() -> None:
    tenants = tenancy_config.load(RAIZ_REAL / "app" / "config" / "tenants")
    polizas = _polizas()

    for tenant in tenants.available:
        ruta = f"tenants/{tenant.tenant_id}/issued_policies/{tenant.example_policy}.json"
        assert len(polizas[ruta]["drivers"]) >= 2, f"{ruta}: solo declara al titular"


def test_un_conductor_adicional_es_un_familiar_con_otro_nombre_de_pila() -> None:
    """Los apellidos de la casa y un nombre de pila que nadie mas en la poliza lleva."""
    adicionales = 0
    for ruta, poliza in _polizas().items():
        titular, *familiares = _nombres(poliza)
        partes = titular.split()
        de_pila = [titular.split()[0].casefold()]
        for nombre in familiares:
            adicionales += 1
            palabras = nombre.split()
            if _idioma_de_la_emisora(poliza) == "es":
                assert palabras[1] == partes[1], f"{ruta}: {nombre} no lleva el apellido de la casa"
                assert len(palabras) == 3, f"{ruta}: {nombre}"
            else:
                assert palabras[-1] == partes[-1], (
                    f"{ruta}: {nombre} no lleva el apellido de la casa"
                )
            assert palabras[0].casefold() not in de_pila, (
                f"{ruta}: {nombre} repite un nombre de pila"
            )
            de_pila.append(palabras[0].casefold())
    assert adicionales, "ninguna poliza declara un conductor adicional"


def test_el_nombre_de_un_adicional_no_es_el_de_ninguna_otra_persona_del_corpus() -> None:
    """La unica repeticion de nombres es la de DS-8, entre titulares y a proposito."""
    titulares = {p["named_insured"]["full_name"] for p in _polizas().values()}
    adicionales = [n for p in _polizas().values() for n in _nombres(p)[1:]]

    assert len(set(adicionales)) == len(adicionales)
    assert not set(adicionales) & titulares


def test_los_conductores_adicionales_estan_en_la_lista_de_valores_personales() -> None:
    valores = json.loads(_generacion().files["personal_values.json"])["values"]
    nombres = {(v["language"], v["value"]) for v in valores if v["kind"] == "name"}

    for poliza in _polizas().values():
        idioma = _idioma_de_la_emisora(poliza)
        for nombre in _nombres(poliza):
            assert (idioma, nombre) in nombres, nombre


# --- El modelo -------------------------------------------------------------------------------


def _registro(**cambios: Any) -> IssuedPolicyRecord:
    base = dict(next(iter(_polizas().values())))
    base.update(cambios)
    return IssuedPolicyRecord.model_validate(base)


def test_una_poliza_sin_conductores_declarados_sigue_siendo_valida() -> None:
    """Es lo que dejan las filas anteriores a este campo: la derivacion la lee como «no se sabe»."""
    assert _registro(drivers=[]).drivers == ()


def test_el_primer_conductor_declarado_tiene_que_ser_el_titular() -> None:
    titular = next(iter(_polizas().values()))["named_insured"]["full_name"]

    with pytest.raises(ValueError, match="el primer conductor declarado es el titular"):
        _registro(drivers=[{"full_name": "Otra Persona Cualquiera"}, {"full_name": titular}])


def test_un_conductor_declarado_dos_veces_se_rechaza() -> None:
    titular = next(iter(_polizas().values()))["named_insured"]["full_name"]

    with pytest.raises(ValueError, match="conductores repetidos"):
        _registro(drivers=[{"full_name": titular}, {"full_name": titular}])


def test_un_conductor_no_admite_campos_de_mas() -> None:
    """Solo el nombre: un telefono o una cedula de mas serian datos personales sin dueno."""
    with pytest.raises(ValueError, match="phone"):
        DriverRef.model_validate({"full_name": "Natalia Henao", "phone": "310 555 0100"})


# --- compose_relative_name -------------------------------------------------------------------


def _gente(nombres: tuple[str, ...], apellidos: tuple[str, ...]) -> People:
    pools = Pools(items={("es", GIVEN_NAMES): nombres, ("es", FAMILY_NAMES): apellidos})
    return People(pools=pools, used=UsedValues())


def test_sin_un_nombre_de_pila_libre_se_dice_cual_se_agoto() -> None:
    gente = _gente(("Ana",), ("Ruiz", "Gil", "Mora"))

    with pytest.raises(PeopleError, match="no quedan nombres de pila distintos"):
        compose_relative_name(
            SeededChooser(1, "prueba"),
            gente,
            "es",
            holder_name="Ana Ruiz Gil",
            taken_given_names=frozenset({"ana"}),
        )


def test_un_familiar_en_espanol_lleva_el_primer_apellido_del_titular_y_otro_segundo() -> None:
    gente = _gente(("Ana", "Luis"), ("Ruiz", "Gil", "Mora"))

    nombre = compose_relative_name(
        SeededChooser(1, "prueba"),
        gente,
        "es",
        holder_name="Ana Ruiz Gil",
        taken_given_names=frozenset({"ana"}),
    )

    primero, casa, segundo = nombre.split()
    assert (primero, casa) == ("Luis", "Ruiz")
    assert segundo in {"Gil", "Mora"}
