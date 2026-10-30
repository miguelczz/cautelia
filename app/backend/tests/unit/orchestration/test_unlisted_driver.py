"""El conductor que no figura en la poliza, derivado del campo del caso (sexto insumo de triage).

Lo que estas pruebas vigilan no es que la funcion devuelva un booleano: es que **tres situaciones
sigan siendo tres**, y que la tercera sea la que gane ante la duda.

- `False` (figura) y `True` (no figura) solo salen de un nombre completo pegado a un verbo de
  conducir, o de la frase que el sistema escribe cuando la persona confirma que conducia el
  titular. Decir `False` cuando no figura es el error caro: la regla no dispara y nadie lo mira.
- Todo lo demas es `None`, el insumo ausente, que no dispara. Un hijo sin nombre, un nombre de
  pila a secas, un nombre incompleto, una negacion o una duda no alcanzan para afirmar nada.

Los casos de cada tabla estan escritos desde lo que una persona diria, no desde lo que la
funcion hace: si uno se cae, la pregunta es si la funcion se equivoco o si el caso estaba mal
pensado, y no se cambia el valor esperado para que pase.
"""

from __future__ import annotations

import pytest

from untangle.base import Locale
from untangle.case_record.models import FieldStatus
from untangle.orchestration.nodes.intake.policy import PolicyMatch, confirmed_vehicle_value
from untangle.orchestration.triage_inputs import unlisted_driver

#: Una poliza en espanol: el titular y un hijo, que comparte sus apellidos.
POLIZA_ES = ("Natalia Henao Rendón", "Mateo Henao Gómez")
#: Una poliza en ingles: la titular y su esposo.
POLIZA_EN = ("Rebecca Miller", "Daniel James Miller")


def _lee(texto: str | None, declarados: tuple[str, ...] = POLIZA_ES) -> bool | None:
    return unlisted_driver(texto, status=FieldStatus.STATED, declared_drivers=declarados)


# --- La frase del sistema: el titular conducia -----------------------------------------------


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_la_frase_que_el_sistema_escribe_al_confirmar_al_titular_figura(idioma: Locale) -> None:
    """Contra el catalogo de verdad, no contra una copia de la frase.

    La derivacion reconoce la frase por sus palabras. Si alguien cambia el catalogo
    (`intake.policy.confirmed_vehicle`) y no cambia el reconocedor, esta prueba se cae: sin ella
    la derivacion dejaria de ver al titular sin que nada lo avisara.
    """
    coincidencia = PolicyMatch(
        policy_number="POL-11", holder_name=POLIZA_ES[0], vehicle="Renault Logan 2024"
    )
    escrito = confirmed_vehicle_value(coincidencia, language=idioma)

    assert escrito is not None
    declarados = POLIZA_ES if idioma == "es" else POLIZA_EN
    assert _lee(escrito, declarados) is False


@pytest.mark.parametrize(
    "texto",
    [
        pytest.param(
            "Renault Logan 2024, conducía el titular. manejaba su hijo",
            id="lo-que-se-guardaba-antes-con-un-hijo-sin-nombre",
        ),
        pytest.param(
            "Renault Logan 2024, conducía el titular. Lo manejaba mi hijo Carlos Ruiz Mora",
            id="lo-que-se-guardaba-antes-con-un-hijo-con-nombre",
        ),
        pytest.param(
            "Lo manejaba mi hijo Carlos Ruiz Mora. Renault Logan 2024, conducía el titular",
            id="otro-conductor-antes-de-la-frase",
        ),
        pytest.param("conducía el titular, creo", id="con-una-duda"),
        pytest.param("No, no conducía el titular", id="negada"),
    ],
)
def test_la_frase_del_titular_con_otra_version_de_quien_conducia_no_afirma_nada(
    texto: str,
) -> None:
    """Hasta el 2026-10-13 el caso guardaba la frase del titular **y** lo que dijo la persona.
    Un texto que dice las dos cosas no se lee a favor de ninguna."""
    assert _lee(texto) is None


# --- Un conductor que la poliza declara -------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "declarados"),
    [
        pytest.param(
            "Renault Logan 2024. Lo manejaba Mateo Henao Gómez.", POLIZA_ES, id="adicional"
        ),
        pytest.param("Lo conducía Natalia Henao Rendón", POLIZA_ES, id="el-titular-con-su-nombre"),
        pytest.param("Mi Renault Logan lo conducía Henao Gomez Mateo", POLIZA_ES, id="otro-orden"),
        pytest.param("Manejaba MATEO HENAO GÓMEZ", POLIZA_ES, id="mayusculas-y-tilde"),
        pytest.param("Iba manejando mi hijo Mateo Henao Gómez", POLIZA_ES, id="con-parentesco"),
        pytest.param("Mateo Henao Gómez iba manejando", POLIZA_ES, id="antes-del-verbo"),
        pytest.param("Conducido por Mateo Henao Gómez", POLIZA_ES, id="en-pasiva"),
        pytest.param(
            "Manejaba María de los Ángeles Pérez",
            ("Carlos Ruiz Mora", "María de los Ángeles Pérez"),
            id="con-particulas",
        ),
        pytest.param(
            "Honda Civic 2021. My husband Daniel James Miller was driving.",
            POLIZA_EN,
            id="ingles-antes-del-verbo",
        ),
        pytest.param(
            "My Honda Civic was driven by MILLER DANIEL JAMES", POLIZA_EN, id="ingles-en-pasiva"
        ),
    ],
)
def test_quien_nombra_completo_a_un_conductor_declarado_figura(
    texto: str, declarados: tuple[str, ...]
) -> None:
    assert _lee(texto, declarados) is False


# --- Alguien que la poliza no declara ----------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "declarados"),
    [
        pytest.param("Manejaba su hijo Carlos Ruiz Mora.", POLIZA_ES, id="hijo-con-nombre"),
        pytest.param("Iba manejando mi hermano Carlos Ruiz", POLIZA_ES, id="dos-palabras"),
        pytest.param("Carlos Ruiz Mora iba manejando mi carro", POLIZA_ES, id="antes-del-verbo"),
        pytest.param(
            "Lo manejaba mi hijo Andrés Henao Rendón",
            POLIZA_ES,
            id="comparte-los-apellidos-del-titular",
        ),
        pytest.param("Conducido por Carlos Ruiz Mora", POLIZA_ES, id="en-pasiva"),
        pytest.param("Lo conducía el señor Carlos Ruiz", POLIZA_ES, id="con-tratamiento"),
        pytest.param(
            "Mi Renault Logan lo manejaba mi esposa Ana Pérez",
            POLIZA_ES,
            id="el-carro-con-mayuscula-no-estorba",
        ),
        pytest.param("Iba conduciendo mi amigo Pedro Gil", POLIZA_ES, id="amigo"),
        pytest.param(
            "Honda Civic 2021. My brother Peter Gardner was driving.",
            POLIZA_EN,
            id="ingles-antes-del-verbo",
        ),
        pytest.param(
            "Honda Civic 2021, driven by my brother Peter Gardner.",
            POLIZA_EN,
            id="ingles-en-pasiva",
        ),
        pytest.param("Peter Gardner was driving my car", POLIZA_EN, id="ingles-sin-parentesco"),
        pytest.param(
            "My son Kevin Miller was driving", POLIZA_EN, id="ingles-comparte-el-apellido"
        ),
        pytest.param("Mr Peter Gardner was driving", POLIZA_EN, id="ingles-con-tratamiento"),
    ],
)
def test_quien_nombra_completo_a_alguien_que_no_esta_en_la_poliza_no_figura(
    texto: str, declarados: tuple[str, ...]
) -> None:
    assert _lee(texto, declarados) is True


# --- Todo lo demas: ausente ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "declarados"),
    [
        pytest.param("Renault Logan 2024. Manejaba su hijo.", POLIZA_ES, id="hijo-sin-nombre"),
        pytest.param("Lo manejaba Carlos.", POLIZA_ES, id="solo-un-nombre-de-pila"),
        pytest.param("Lo manejaba Mateo.", POLIZA_ES, id="el-nombre-de-pila-de-un-declarado"),
        pytest.param("Lo manejaba Mateo Henao.", POLIZA_ES, id="nombre-incompleto-de-un-declarado"),
        pytest.param(
            "Lo manejaba Nathalia Henao Rendón.",
            POLIZA_ES,
            id="una-letra-de-diferencia-con-Natalia",
        ),
        pytest.param(
            "Lo manejaba Mateo Henao Gomes", POLIZA_ES, id="apellido-con-una-letra-distinta"
        ),
        pytest.param("No manejaba Carlos Ruiz Mora, era mi hijo.", POLIZA_ES, id="negado"),
        pytest.param(
            "Nadie manejaba, estaba parado. Carlos Ruiz Mora conducía", POLIZA_ES, id="con-un-nadie"
        ),
        pytest.param("Creo que lo manejaba Carlos Ruiz Mora", POLIZA_ES, id="con-una-duda"),
        pytest.param("Quizás lo conducía Carlos Ruiz Mora", POLIZA_ES, id="con-un-quizas"),
        pytest.param("No sé quién manejaba.", POLIZA_ES, id="no-se"),
        pytest.param(
            "Carlos Ruiz Mora conducía. Pedro Gil Soto manejaba.",
            POLIZA_ES,
            id="dos-nombres-distintos",
        ),
        pytest.param("lo manejaba carlos ruiz mora", POLIZA_ES, id="en-minusculas"),
        pytest.param(
            "Manejaba Juan Carlos Andrés Felipe Gómez Pérez", POLIZA_ES, id="demasiadas-palabras"
        ),
        pytest.param(
            "Hola, soy Carlos Ruiz Mora. Manejaba yo",
            POLIZA_ES,
            id="el-que-habla-no-es-el-conductor",
        ),
        pytest.param(
            "Carlos Ruiz Mora y yo íbamos en el carro", POLIZA_ES, id="sin-verbo-de-conducir"
        ),
        pytest.param(
            "Mi Renault Logan lo manejaba mi hijo", POLIZA_ES, id="el-carro-con-mayuscula"
        ),
        pytest.param("Chevrolet Spark lo manejaba mi hijo", POLIZA_ES, id="el-carro-pegado-al-lo"),
        pytest.param(
            "Mi Chevrolet Spark iba conduciendo mi hijo", POLIZA_ES, id="el-carro-antes-del-verbo"
        ),
        pytest.param("Manejaba un Mazda 2", POLIZA_ES, id="el-carro-despues-del-verbo"),
        pytest.param("Manejaba el Renault Logan 2024", POLIZA_ES, id="el-carro-con-articulo"),
        pytest.param("Renault Logan 2024, placa WBR686", POLIZA_ES, id="solo-el-vehiculo"),
        pytest.param("Peter was driving.", POLIZA_EN, id="ingles-un-nombre-de-pila"),
        pytest.param("Daniel was driving.", POLIZA_EN, id="ingles-nombre-de-pila-de-un-declarado"),
        pytest.param("Daniel James was driving.", POLIZA_EN, id="ingles-nombre-incompleto"),
        pytest.param("Peter Gardner wasn't driving, my son was.", POLIZA_EN, id="ingles-negado"),
        pytest.param("I don't know who was driving.", POLIZA_EN, id="ingles-no-se"),
        pytest.param(
            "I think my brother Peter Gardner was driving", POLIZA_EN, id="ingles-con-una-duda"
        ),
        pytest.param("My son was driving", POLIZA_EN, id="ingles-hijo-sin-nombre"),
        pytest.param("Honda Civic 2021 Peter Gardner", POLIZA_EN, id="ingles-sin-verbo"),
        pytest.param("", POLIZA_ES, id="vacio"),
        pytest.param("   ", POLIZA_ES, id="en-blanco"),
    ],
)
def test_lo_que_no_se_puede_afirmar_queda_ausente(texto: str, declarados: tuple[str, ...]) -> None:
    """Nunca `False` ni `True` por una frase que no los dice: el insumo queda ausente.

    Las tablas de arriba son ejemplos; esta es la de las frases que un cambio generoso de la
    derivacion convertiria en una afirmacion sin que nadie lo notara.
    """
    assert _lee(texto, declarados) is None


# --- Sin con que comparar ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "texto",
    [
        "Renault Logan 2024, conducía el titular",
        "Lo manejaba Mateo Henao Gómez",
        "Lo manejaba mi hijo Carlos Ruiz Mora",
    ],
)
@pytest.mark.parametrize("declarados", [(), ("",), ("   ", "…")], ids=["vacia", "vacio", "blancos"])
def test_una_poliza_que_no_declara_conductores_no_permite_decir_nada(
    texto: str, declarados: tuple[str, ...]
) -> None:
    """Ni «figura» ni «no figura»: con la lista vacia todo parecia no figurar. Es lo que trae una
    base cuyas polizas se ingirieron antes de que se declararan conductores."""
    assert _lee(texto, declarados) is None


def test_un_campo_que_nadie_dijo_no_tiene_nada_que_leer() -> None:
    """El estado manda: aunque hubiera texto, un campo `NOT_STATED` no se lee."""
    resultado = unlisted_driver(
        "Lo manejaba mi hijo Carlos Ruiz Mora",
        status=FieldStatus.NOT_STATED,
        declared_drivers=POLIZA_ES,
    )

    assert resultado is None


def test_sin_valor_no_hay_nada_que_leer() -> None:
    assert unlisted_driver(None, status=FieldStatus.STATED, declared_drivers=POLIZA_ES) is None


def test_un_campo_confirmado_cuenta_igual_que_uno_dicho() -> None:
    nombrado = "Lo manejaba mi hijo Carlos Ruiz Mora"
    titular = "Lo conducía Natalia Henao Rendón"

    assert (
        unlisted_driver(nombrado, status=FieldStatus.CONFIRMED, declared_drivers=POLIZA_ES) is True
    )
    assert (
        unlisted_driver(titular, status=FieldStatus.CONFIRMED, declared_drivers=POLIZA_ES) is False
    )


def test_el_apostrofo_tipografico_se_lee_igual_que_el_recto() -> None:
    """Un teclado de telefono escribe "wasnt" con el apostrofo curvo: la negacion no se pierde."""
    curvo = "Peter Gardner wasn" + chr(0x2019) + "t driving, my son was."

    assert _lee(curvo, POLIZA_EN) is None
    assert _lee("Peter Gardner was driving, my son was not.", POLIZA_EN) is None
