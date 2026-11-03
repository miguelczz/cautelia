"""La configuracion versionada del ajustador de IA: lo que declara el archivo y lo que rechaza."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from untangle.adjuster import config
from untangle.workspace import schema_check

VALIDA: dict[str, Any] = {
    "config_version": 1,
    "max_searches": 3,
    "allowed_domains": ["fasecolda.com", "tucarro.com.co"],
    "daily_case_cap": 20,
    "attempts": 3,
    "vehicle_value_range_cop": [8_000_000, 800_000_000],
}


def _escribir(tmp_path: Path, **cambios: Any) -> Path:
    archivo = tmp_path / "adjuster.yaml"
    archivo.write_text(yaml.safe_dump(VALIDA | cambios), encoding="utf-8")
    return archivo


def test_el_archivo_versionado_declara_lo_que_el_diseno_pide() -> None:
    """El archivo que se despliega, no una fixture: busquedas, dominios, tope, intentos y rango."""
    cargada = config.load()

    assert cargada.max_searches == 3
    assert cargada.daily_case_cap == 20
    assert cargada.attempts == 3
    assert cargada.vehicle_value_range_cop == (8_000_000, 800_000_000)
    assert set(cargada.allowed_domains) == {
        "fasecolda.com",
        "guiadevalores.fasecolda.com",
        "tucarro.com.co",
        "carroya.com",
        "mercadolibre.com.co",
    }


def test_el_chequeo_del_espacio_de_trabajo_acepta_la_carpeta_versionada() -> None:
    from untangle import paths

    assert schema_check.revisar_ajustador(paths.adjuster_dir()) == []


def test_el_chequeo_del_espacio_de_trabajo_nombra_el_archivo_que_falla(tmp_path: Path) -> None:
    _escribir(tmp_path, daily_case_cap=0)

    [problema] = schema_check.revisar_ajustador(tmp_path)

    assert "adjuster.yaml" in problema
    assert "daily_case_cap" in problema


def test_una_configuracion_valida_carga(tmp_path: Path) -> None:
    cargada = config.load(_escribir(tmp_path))

    assert cargada.allowed_domains == ("fasecolda.com", "tucarro.com.co")


@pytest.mark.parametrize(
    "dominio",
    [
        "https://fasecolda.com",
        "fasecolda.com/guia",
        "Fasecolda.com",
        "fasecolda.com:443",
        "localhost",
        "fase colda.com",
        "-fasecolda.com",
        "",
    ],
)
def test_un_dominio_que_no_es_pelado_se_rechaza(tmp_path: Path, dominio: str) -> None:
    with pytest.raises(config.AdjusterConfigError) as error:
        config.load(_escribir(tmp_path, allowed_domains=["fasecolda.com", dominio]))

    assert "allowed_domains" in str(error.value)


def test_sin_dominios_la_busqueda_seria_abierta_y_se_rechaza(tmp_path: Path) -> None:
    with pytest.raises(config.AdjusterConfigError) as error:
        config.load(_escribir(tmp_path, allowed_domains=[]))

    assert "allowed_domains" in str(error.value)


def test_un_dominio_repetido_se_rechaza(tmp_path: Path) -> None:
    with pytest.raises(config.AdjusterConfigError) as error:
        config.load(_escribir(tmp_path, allowed_domains=["fasecolda.com", "fasecolda.com"]))

    assert "repetidos" in str(error.value)


@pytest.mark.parametrize(
    ("clave", "valor"),
    [
        ("max_searches", 0),
        ("max_searches", 11),
        ("daily_case_cap", 0),
        ("attempts", 0),
        ("attempts", 11),
        ("config_version", 2),
        ("vehicle_value_range_cop", [0, 100]),
        ("vehicle_value_range_cop", [100, 100]),
        ("vehicle_value_range_cop", [200, 100]),
        ("vehicle_value_range_cop", [100]),
    ],
)
def test_un_valor_fuera_de_lo_admitido_se_rechaza_nombrando_la_clave(
    tmp_path: Path, clave: str, valor: Any
) -> None:
    with pytest.raises(config.AdjusterConfigError) as error:
        config.load(_escribir(tmp_path, **{clave: valor}))

    assert clave in str(error.value)
    assert "adjuster.yaml" in str(error.value)


def test_una_clave_de_mas_se_rechaza(tmp_path: Path) -> None:
    """Una clave que el codigo no lee es una decision que nadie va a hacer cumplir."""
    with pytest.raises(config.AdjusterConfigError) as error:
        config.load(_escribir(tmp_path, model="claude-haiku-5-5"))

    assert "model" in str(error.value)


def test_un_archivo_que_no_existe_o_no_es_un_mapa_dice_cual(tmp_path: Path) -> None:
    with pytest.raises(config.AdjusterConfigError, match="no se pudo leer"):
        config.load(tmp_path / "no-existe.yaml")

    lista = tmp_path / "lista.yaml"
    lista.write_text("- uno\n- dos\n", encoding="utf-8")
    with pytest.raises(config.AdjusterConfigError, match="mapa"):
        config.load(lista)

    roto = tmp_path / "roto.yaml"
    roto.write_text("a: [sin cerrar\n", encoding="utf-8")
    with pytest.raises(config.AdjusterConfigError, match="YAML"):
        config.load(roto)


@pytest.mark.parametrize(
    ("valor", "plausible"),
    [
        (7_999_999, False),
        (8_000_000, True),
        (62_000_000, True),
        (800_000_000, True),
        (800_000_001, False),
        (0, False),
        (-5, False),
    ],
)
def test_un_valor_de_vehiculo_es_creible_dentro_del_rango_con_los_extremos(
    valor: int, plausible: bool
) -> None:
    cargada = config.AdjusterConfig.model_validate(VALIDA)

    assert cargada.is_plausible_vehicle_value(valor) is plausible
