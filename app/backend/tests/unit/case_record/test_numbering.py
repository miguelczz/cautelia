"""El numero de caso: su forma, su unicidad y lo que no deja pasar (BR4.1 a BR4.3).

Lo que estas pruebas protegen es el numero que una persona anota al colgar y con
el que vuelve. Dos fallos distintos lo rompen: que cambie despues de darselo, y
que dos aseguradoras compartan prefijo y por tanto puedan compartir numero. El
segundo no lo nota nadie hasta que dos casos distintos responden al mismo
codigo.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from untangle.case_record import numbering
from untangle.case_record.models import CaseNumber
from untangle.tenancy import config
from untangle.tenancy.models import TenantConfig, TenantKind, VoiceConfig


def _tenant(tenant_id: str, prefijo: str) -> TenantConfig:
    return TenantConfig(
        tenant_id=tenant_id,
        display_name=tenant_id.title(),
        kind=TenantKind.CARRIER,
        default_language="es",
        jurisdiction="corvane",
        example_policy="POL-100042",
        case_number_prefix=prefijo,
        voice=VoiceConfig(primary_voice="catalina", language_default="es"),
    )


# --- La forma -----------------------------------------------------------------


def test_el_numero_se_escribe_con_tres_letras_guion_y_seis_digitos() -> None:
    """FR1.5 fija la forma, y la agente la dicta digito a digito al cerrar."""
    numero = CaseNumber(prefix="STO", serial="482913")

    assert str(numero) == "STO-482913"


@pytest.mark.parametrize(
    "prefijo",
    ["ST", "STON", "sto", "S1O", "ST "],
    ids=["corto", "largo", "minusculas", "con-digito", "con-espacio"],
)
def test_un_prefijo_que_no_son_tres_mayusculas_no_se_puede_construir(prefijo: str) -> None:
    """Un prefijo escrito de dos maneras acaba siendo dos prefijos distintos."""
    with pytest.raises(ValidationError):
        CaseNumber(prefix=prefijo, serial="482913")


@pytest.mark.parametrize(
    "serial",
    ["48291", "4829134", "48291a", "-82913"],
    ids=["corto", "largo", "con-letra", "con-signo"],
)
def test_un_serial_que_no_son_seis_digitos_no_se_puede_construir(serial: str) -> None:
    """Seis, ni cinco ni siete: es lo que la persona anota y lo que dicta."""
    with pytest.raises(ValidationError):
        CaseNumber(prefix="STO", serial=serial)


def test_el_serial_conserva_sus_ceros_a_la_izquierda() -> None:
    """Perderlos convertiria 000042 en 42 y la busqueda por numero fallaria."""
    numero = CaseNumber(prefix="SUN", serial="000042")

    assert str(numero) == "SUN-000042"


def test_un_numero_escrito_se_lee_solo_en_su_forma_exacta() -> None:
    """Ser permisivo haria que el mismo caso se escribiera de varias maneras."""
    assert numbering.parse("KNO-118844") == CaseNumber(prefix="KNO", serial="118844")

    for invalido in ["kno-118844", "KNO118844", "KNO-118844-2", "KNO 118844"]:
        with pytest.raises((ValueError, ValidationError)):
            numbering.parse(invalido)


# --- Los prefijos de la demostracion -------------------------------------------


def test_las_tres_aseguradoras_declaran_su_prefijo_y_ninguno_se_repite() -> None:
    """Es la comprobacion que corre al arrancar (BR4.2), sobre la configuracion real."""
    cargadas = config.load().available

    prefijos = {t.tenant_id: t.case_number_prefix for t in cargadas}
    assert prefijos == {"knotwell": "KNO", "stonecroft": "STO", "sunmeadow": "SUN"}
    numbering.assert_prefixes_are_distinct(cargadas)


def test_dos_aseguradoras_con_el_mismo_prefijo_no_dejan_arrancar() -> None:
    """Con el mismo prefijo, dos casos distintos pueden compartir numero, y
    entonces el numero deja de identificar un caso: quien lo dicta y quien lo
    busca estarian hablando de cosas distintas sin saberlo."""
    chocan = (_tenant("stonecroft", "SMU"), _tenant("sunmeadow", "SMU"))

    with pytest.raises(numbering.PrefixCollisionError) as error:
        numbering.assert_prefixes_are_distinct(chocan)

    assert "SMU" in str(error.value)
    assert "stonecroft" in str(error.value)
    assert "sunmeadow" in str(error.value)


def test_una_aseguradora_sin_prefijo_no_carga() -> None:
    """El prefijo es dato de la aseguradora y su ausencia se ve al validar la
    carpeta, no la primera vez que alguien cierra un caso.

    Se valida desde un mapa y no construyendo el modelo a mano porque ese es el
    camino real --archivo, mapa, modelo-- y porque el comprobador de tipos ya
    impide la llamada directa: la prueba que importa es la del archivo.
    """
    sin_prefijo = {
        "tenant_id": "stonecroft",
        "display_name": "Seguros Aburrá",
        "kind": "carrier",
        "default_language": "es",
        "jurisdiction": "corvane",
        "example_policy": "POL-100042",
        "voice": {"primary_voice": "catalina", "language_default": "es"},
    }

    with pytest.raises(ValidationError) as error:
        TenantConfig.model_validate(sin_prefijo)

    assert "case_number_prefix" in str(error.value)


# --- La unicidad ---------------------------------------------------------------


def test_el_numero_nuevo_no_repite_uno_ya_usado_por_esa_aseguradora() -> None:
    """La unicidad es dentro de la aseguradora: el prefijo separa a las demas."""
    config.install(config.load())
    try:
        usados = frozenset(f"{n:06d}" for n in range(999_000, 1_000_000))
        numero = numbering.mint("stonecroft", taken=usados)

        assert numero.serial not in usados
        assert numero.prefix == "STO"
    finally:
        config.reset()


def test_el_numero_lleva_el_prefijo_de_su_aseguradora_y_no_otro() -> None:
    """Es lo que hace que el numero diga de quien es el caso al leerlo."""
    config.install(config.load())
    try:
        assert numbering.mint("sunmeadow").prefix == "SUN"
        assert numbering.mint("knotwell").prefix == "KNO"
    finally:
        config.reset()
