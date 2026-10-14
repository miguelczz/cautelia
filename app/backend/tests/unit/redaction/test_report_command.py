"""El informe por idioma, por tipo y por reconocedor (NFR11.2, NFR-U3-5).

Es uno de los dos comandos que U3 mete en el paso 6 del guion de verificacion, y
por eso se prueba: un comando de medicion que se rompiera en silencio dejaria la
compuerta pasando en verde sin haber medido nada, que es exactamente la forma de
fallar que esta unidad existe para impedir.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from untangle import paths
from untangle.compliance.redaction import detector as deteccion
from untangle.compliance.redaction.recognizers.models import FORMAT_TYPES, EntityType
from untangle.workspace import redaction_report


@pytest.fixture(scope="session", autouse=True)
def _detector_cargado() -> Iterator[None]:
    deteccion.install(deteccion.load())
    yield
    deteccion.reset()


@pytest.fixture(scope="session")
def medidos() -> tuple[redaction_report.PorIdioma, ...]:
    """Una sola medicion para toda la sesion: corre el detector 30 veces."""
    return redaction_report.measure_all(paths.repo_root())


def test_mide_los_dos_idiomas_por_separado(
    medidos: tuple[redaction_report.PorIdioma, ...],
) -> None:
    """P12: nunca un promedio combinado.

    Un promedio esconderia que un idioma funciona y el otro no, que es
    justamente lo que la paridad del producto existe para evitar.
    """
    assert [m.language for m in medidos] == ["es", "en"]
    assert all(m.total > 0 for m in medidos)


@pytest.mark.parametrize("tipo", sorted(FORMAT_TYPES))
def test_cada_tipo_propio_tiene_hallazgos_en_los_dos_idiomas(
    tipo: EntityType, medidos: tuple[redaction_report.PorIdioma, ...]
) -> None:
    """NFR11.1: un reconocedor que falla en su propio caso sembrado esta roto.

    Los cuatro tipos propios del dominio y el VIN, que tambien tiene sus semillas
    en RT-14.
    """
    for medido in medidos:
        assert medido.counts_by_type[tipo] > 0, f"{medido.language}/{tipo.value}"


def test_el_informe_atribuye_al_juego_del_otro_idioma_lo_que_ese_juego_encontro(
    medidos: tuple[redaction_report.PorIdioma, ...],
) -> None:
    """La fila que prueba que los dos juegos corren (BR2.9).

    En la columna del turno espanol tiene que haber hallazgos de reconocedores
    `en-`: son los tres turnos de RT-15, con el dato dictado en ingles. Si esa
    columna estuviera a cero, o el juego ingles no estaria corriendo, o la
    atribucion estaria mintiendo, y las dos cosas dejan la compuerta dura de
    AC4.13.4 sin medir.
    """
    por_idioma = {m.language: m for m in medidos}

    del_otro_en_espanol = {
        identificador: cuantos
        for identificador, cuantos in por_idioma["es"].counts_by_recognizer.items()
        if identificador.startswith("en-") and cuantos
    }
    del_otro_en_ingles = {
        identificador: cuantos
        for identificador, cuantos in por_idioma["en"].counts_by_recognizer.items()
        if identificador.startswith("es-") and cuantos
    }

    assert del_otro_en_espanol
    assert del_otro_en_ingles


def test_la_cifra_del_respaldo_no_pasa_de_su_techo(
    medidos: tuple[redaction_report.PorIdioma, ...],
) -> None:
    """NFR11.2: 1 de cada 10 o menos, por idioma.

    No detiene la entrega --tapar de mas es el lado seguro-- pero pasarse
    significa una de dos cosas, y las dos son trabajo concreto: un reconocedor se
    rompio, o hay un formato frecuente sin reconocedor propio.
    """
    for medido in medidos:
        assert not medido.over_budget, (
            f"{medido.language}: el respaldo tapa {medido.fallback_share:.0%} del total"
        )


def test_un_reconocedor_que_no_encuentra_nada_hace_fallar_el_comando(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """La conducta que hace util al comando: cero hallazgos **detiene**.

    Sin ella, el dia que un reconocedor dejara de cargar el informe imprimiria
    una tabla de ceros y devolveria cero, y la compuerta seguiria en verde con la
    redaccion rota.
    """

    def _sin_hallazgos(root: object = None) -> tuple[redaction_report.PorIdioma, ...]:
        return (
            redaction_report.PorIdioma(
                language="es",
                counts_by_type=dict.fromkeys(EntityType, 0),
                counts_by_recognizer={"es-phone": 0},
                fallback_count=0,
                total=0,
            ),
        )

    monkeypatch.setattr(redaction_report, "measure_all", _sin_hallazgos)

    assert redaction_report.main() == 1
    assert "esta roto" in capsys.readouterr().err


def test_el_comando_imprime_los_dos_idiomas_y_ninguna_cifra_combinada(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Lo que se lee tiene que decir de que idioma habla cada numero."""
    assert redaction_report.main() == 0

    salida = capsys.readouterr().out
    assert "es" in salida
    assert "en" in salida
    assert "respaldo" in salida
    for tipo in EntityType:
        assert tipo.value in salida
