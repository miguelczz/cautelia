"""El numero de caso: su forma, su unicidad y lo que no deja pasar (BR4.1 a BR4.3).

Lo que estas pruebas protegen es el numero que una persona anota al colgar y con
el que vuelve: dos letras de la aseguradora y un contador (`AP-29`). Tres fallos
distintos lo rompen: que cambie despues de darselo, que dos aseguradoras compartan
prefijo y por tanto puedan compartir numero, y que el contador repita uno ya dado
(tambien despues del reinicio nocturno). El segundo no lo nota nadie hasta que dos
casos distintos responden al mismo codigo.
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
        example_policy="POL-11",
        case_number_prefix=prefijo,
        voice=VoiceConfig(primary_voice="catalina", language_default="es"),
    )


# --- La forma -----------------------------------------------------------------


def test_el_numero_se_escribe_con_dos_letras_guion_y_el_contador() -> None:
    """FR1.5 fija la forma, y la agente la dicta al cerrar."""
    numero = CaseNumber(prefix="AP", serial="29")

    assert str(numero) == "AP-29"


@pytest.mark.parametrize(
    "prefijo",
    ["A", "APO", "ap", "A1", "A "],
    ids=["corto", "largo", "minusculas", "con-digito", "con-espacio"],
)
def test_un_prefijo_que_no_son_dos_mayusculas_no_se_puede_construir(prefijo: str) -> None:
    """Un prefijo escrito de dos maneras acaba siendo dos prefijos distintos."""
    with pytest.raises(ValidationError):
        CaseNumber(prefix=prefijo, serial="29")


@pytest.mark.parametrize(
    "serial",
    ["", "0", "029", "1234567", "2a", "-29"],
    ids=["vacio", "cero", "con-cero-a-la-izquierda", "siete-cifras", "con-letra", "con-signo"],
)
def test_un_serial_que_no_es_un_contador_sin_ceros_no_se_puede_construir(serial: str) -> None:
    """De una a seis cifras y sin ceros a la izquierda: `AP-029` y `AP-29` serian dos
    formas de escribir el mismo caso y la busqueda por numero no lo encontraria."""
    with pytest.raises(ValidationError):
        CaseNumber(prefix="AP", serial=serial)


@pytest.mark.parametrize("serial", ["1", "9", "10", "29", "999999"])
def test_el_contador_admite_de_una_a_seis_cifras(serial: str) -> None:
    assert str(CaseNumber(prefix="SA", serial=serial)) == f"SA-{serial}"


def test_un_numero_escrito_se_lee_solo_en_su_forma_exacta() -> None:
    """Ser permisivo haria que el mismo caso se escribiera de varias maneras."""
    assert numbering.parse("AC-118") == CaseNumber(prefix="AC", serial="118")

    for invalido in ["ac-118", "AC118", "AC-118-2", "AC 118", "AC-0118", "ACX-118"]:
        with pytest.raises((ValueError, ValidationError)):
            numbering.parse(invalido)


# --- Los prefijos de la demostracion -------------------------------------------


def test_las_tres_aseguradoras_declaran_su_prefijo_y_ninguno_se_repite() -> None:
    """Es la comprobacion que corre al arrancar (BR4.2), sobre la configuracion real."""
    cargadas = config.load().available

    prefijos = {t.tenant_id: t.case_number_prefix for t in cargadas}
    assert prefijos == {"knotwell": "AC", "stonecroft": "SA", "sunmeadow": "AP"}
    numbering.assert_prefixes_are_distinct(cargadas)


def test_dos_aseguradoras_con_el_mismo_prefijo_no_dejan_arrancar() -> None:
    """Con el mismo prefijo, dos casos distintos pueden compartir numero, y
    entonces el numero deja de identificar un caso: quien lo dicta y quien lo
    busca estarian hablando de cosas distintas sin saberlo."""
    chocan = (_tenant("stonecroft", "SM"), _tenant("sunmeadow", "SM"))

    with pytest.raises(numbering.PrefixCollisionError) as error:
        numbering.assert_prefixes_are_distinct(chocan)

    assert "SM" in str(error.value)
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
        "example_policy": "POL-11",
        "voice": {"primary_voice": "catalina", "language_default": "es"},
    }

    with pytest.raises(ValidationError) as error:
        TenantConfig.model_validate(sin_prefijo)

    assert "case_number_prefix" in str(error.value)


# --- La unicidad ---------------------------------------------------------------


def test_el_primer_numero_de_una_aseguradora_es_el_uno() -> None:
    config.install(config.load())
    try:
        assert str(numbering.mint("stonecroft")) == "SA-1"
    finally:
        config.reset()


def test_el_numero_nuevo_es_el_siguiente_al_mayor_ya_emitido_por_esa_aseguradora() -> None:
    """El contador no repite uno ya dado, y un hueco no se rellena: el mayor manda."""
    config.install(config.load())
    try:
        assert str(numbering.mint("sunmeadow", taken=frozenset({"1", "2", "29"}))) == "AP-30"
        assert str(numbering.mint("sunmeadow", taken=frozenset({"7"}))) == "AP-8"
    finally:
        config.reset()


def test_el_contador_se_compara_como_numero_y_no_como_texto() -> None:
    """`9` es menor que `10`: comparado como texto, el siguiente a `10` seria `10`."""
    config.install(config.load())
    try:
        assert str(numbering.mint("knotwell", taken=frozenset({"9", "10"}))) == "AC-11"
    finally:
        config.reset()


def test_la_aseguradora_que_agota_su_contador_falla_diciendolo() -> None:
    config.install(config.load())
    try:
        with pytest.raises(RuntimeError, match="agoto"):
            numbering.mint("stonecroft", taken=frozenset({"999999"}))
    finally:
        config.reset()


def test_el_numero_lleva_el_prefijo_de_su_aseguradora_y_no_otro() -> None:
    """Es lo que hace que el numero diga de quien es el caso al leerlo."""
    config.install(config.load())
    try:
        assert numbering.mint("sunmeadow").prefix == "AP"
        assert numbering.mint("knotwell").prefix == "AC"
    finally:
        config.reset()
