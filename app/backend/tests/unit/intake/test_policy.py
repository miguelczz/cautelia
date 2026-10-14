"""El numero de poliza en lo que la persona dijo, tambien por voz (2026-10-09)."""

from __future__ import annotations

import pytest

from untangle.orchestration.nodes.intake import policy


@pytest.mark.parametrize(
    ("dicho", "esperado"),
    [
        ("mi póliza es 200117", "POL-200117"),
        ("mi póliza es la 200 117", "POL-200117"),
        ("my policy is 2 0 0 1 1 7", "POL-200117"),
        ("200 117", "POL-200117"),
        ("mi póliza es POL-100042", "POL-100042"),
    ],
)
def test_la_poliza_dicha_por_voz_se_reconoce_sin_el_prefijo(dicho: str, esperado: str) -> None:
    """2026-10-09: por voz llega en cifras y sin «POL»; antes no se reconocia."""
    assert policy.policy_number_in(dicho) == esperado


@pytest.mark.parametrize(
    "dicho",
    [
        "mi teléfono es 3001234567 y la póliza no la sé",
        "fue el 15 de octubre de 2025 a las 10",
        "llámame al 300 123",
        "póliza 2001175",
    ],
)
def test_otras_cifras_no_se_leen_como_poliza(dicho: str) -> None:
    assert policy.policy_number_in(dicho) is None


# --- El numero tal como lo entrega el reconocedor de una llamada (2026-10-13) --------------
#
# En una llamada real, «Soy Marco Parker, mi poliza es POL-200117» llego en tres trozos:
# «Claro, mi nombre completo es Marco Parker» / «y mi poliza es Paul» / «201 17.». El turno
# trae los finales unidos con un espacio, y la poliza salia como «Paul 201 17».


def test_la_llamada_real_del_2026_10_13_se_oye_incompleta_y_no_se_inventa_nada() -> None:
    dicho = "Claro, mi nombre completo es Marco Parker y mi póliza es Paul 201 17."

    oido = policy.heard_policy_number(dicho)

    assert oido is not None
    assert oido.digits == "20117"
    assert not oido.complete
    assert oido.number is None
    # Cinco cifras no son una poliza: el buscador exacto no recibe nada que adivinar.
    assert policy.policy_number_in(dicho) is None


@pytest.mark.parametrize(
    "dicho",
    [
        # La palabra que nombra el codigo llega deformada, justo despues de «poliza».
        "mi póliza es Paul 200117",
        "mi póliza es Pol 200117",
        "mi póliza es Poll 200117",
        "mi póliza es Paula 200117",
        "mi póliza es pool 200117",
        "mi póliza es pole 200117",
        "my policy is Paul 200117",
        # O sola antes de las cifras, sin decir «poliza».
        "es Paul 200 117",
        "Paula 200117",
        # Las cifras en grupos y en trozos distintos.
        "mi póliza es Paul 200 117",
        "mi póliza es Paul 2001 17",
        "mi póliza es Paul 20 01 17",
        "mi póliza es 2 0 0 1 1 7",
        "mi póliza es 200-117",
        "mi póliza es 200.117",
        "mi póliza es 200,117",
        "mi póliza: 200117",
        "Póliza #200 117",
        "mi póliza es la POL 200117",
        "mi póliza es pol200117",
        "mi póliza es P O L 2 0 0 1 1 7",
        # Entre dos o tres finales seguidos: el punto de cada final queda en medio.
        "y mi póliza es Paul. 200. 117.",
        "y mi póliza es Paul 200. 1. 17.",
        # En palabras, en los dos idiomas.
        "mi póliza es dos cero cero uno uno siete",
        "my policy is two zero zero one one seven",
        "dos cero cero uno uno siete",
        "two zero zero one one seven",
        "mi póliza es Paul dos cero cero 1 1 siete",
        "mi póliza es Pol dos cero cero uno uno siete.",
        # Con otros datos en la frase.
        "Soy Marco Parker, mi póliza es Paul 200 117 y me chocaron",
        "Claro, mi nombre completo es Marco Parker y mi póliza es Paul 200 117.",
    ],
)
def test_con_exactamente_seis_cifras_se_arma_pol_y_esas_cifras(dicho: str) -> None:
    assert policy.policy_number_in(dicho) == "POL-200117", dicho
    oido = policy.heard_policy_number(dicho)
    assert oido is not None
    assert oido.complete
    assert oido.number == "POL-200117"


@pytest.mark.parametrize(
    ("dicho", "cifras"),
    [
        ("mi póliza es Paul 201 17", "20117"),
        ("mi póliza: 201 17", "20117"),
        ("mi póliza es 200 11", "20011"),
        ("mi póliza es Pol 2 0 1 1 7", "20117"),
        ("mi póliza es dos cero uno uno siete", "20117"),
        ("my policy is two zero one one seven", "20117"),
        ("es Paul 201", "201"),
        # Mas de seis tampoco se corta ni se completa: se oye tal cual.
        ("mi póliza es Paul 2001175", "2001175"),
        ("mi póliza es 200 117 5", "2001175"),
        ("mi póliza es POL-1000421", "1000421"),
        ("mi póliza es 3001234567", "3001234567"),
    ],
)
def test_con_un_numero_distinto_de_cifras_se_devuelve_lo_oido_sin_inventar(
    dicho: str, cifras: str
) -> None:
    oido = policy.heard_policy_number(dicho)

    assert oido is not None, dicho
    assert oido.digits == cifras
    assert not oido.complete
    assert oido.number is None
    assert policy.policy_number_in(dicho) is None


@pytest.mark.parametrize(
    "dicho",
    [
        # Sin nada que diga que son de la poliza, pocas cifras no son un numero oido.
        "mi póliza es Paul 20",
        "tengo póliza. 2 carros fueron golpeados",
        "dos personas heridas",
        "somos tres y el carro es un Mazda 3",
        "mi póliza no la tengo a la mano",
        "no sé el número",
        "Claro, mi nombre completo es Marco Parker",
    ],
)
def test_lo_que_no_parece_un_numero_de_poliza_no_se_oye_como_tal(dicho: str) -> None:
    assert policy.heard_policy_number(dicho) is None, dicho


@pytest.mark.parametrize(
    ("dicho", "esperado"),
    [
        # Un telefono, una cedula, una placa o una fecha en la misma frase no son la poliza.
        ("mi teléfono es 300 123 4567 y mi póliza es Paul 200 117", "POL-200117"),
        ("mi celular es 3001234567 y mi póliza es pol 200117", "POL-200117"),
        ("mi cédula es 79123456 y mi póliza es POL-200117", "POL-200117"),
        ("mi cédula es 79.123.456 y mi póliza es Paul 200 117", "POL-200117"),
        ("mi placa es ABC 123 y mi póliza es pol 200 117", "POL-200117"),
        ("mi placa es ABC123 y mi póliza es Paul 200117", "POL-200117"),
        ("el choque fue el 13/10/2026 y mi póliza es Paul 200117", "POL-200117"),
        ("el choque fue el 13 de octubre de 2026, mi póliza es Paul 200117", "POL-200117"),
    ],
)
def test_otros_datos_en_la_misma_frase_no_se_confunden_con_la_poliza(
    dicho: str, esperado: str
) -> None:
    assert policy.policy_number_in(dicho) == esperado, dicho


@pytest.mark.parametrize(
    "dicho",
    [
        "mi teléfono es 3001234567 y la póliza no la sé",
        "mi teléfono es 300 123 4567 y la póliza no la sé",
        "mi póliza no la tengo, llámame al 300 123",
        "mi póliza no la tengo, mi celular es 300 123",
        "mi cédula es 79123456 y la póliza no la sé",
        "mi placa es ABC123 y la póliza no la sé",
        "mi placa es ABC 123 456 y la póliza no la sé",
        "el choque fue el 13-10-26 y la póliza no la tengo",
        "el choque fue el 13.10.2026 y la póliza no la tengo",
        "fue el 15 de octubre de 2025 a las 10",
        "my phone is 300 123 and my policy is lost",
    ],
)
def test_ninguno_de_esos_datos_se_toma_por_la_poliza_aunque_se_hable_de_ella(dicho: str) -> None:
    assert policy.policy_number_in(dicho) is None, dicho
    oido = policy.heard_policy_number(dicho)
    assert oido is None or not oido.complete, dicho


def test_con_dos_numeros_en_la_frase_gana_el_que_va_pegado_a_la_poliza() -> None:
    dicho = "el 300 123 es mi celular y mi póliza es Paul 200 117"

    assert policy.policy_number_in(dicho) == "POL-200117"


@pytest.mark.parametrize(
    ("oido", "numero", "se_parecen"),
    [
        # Faltan una o dos cifras, en orden.
        ("20117", "POL-200117", True),
        ("2011", "POL-200117", True),
        ("00117", "POL-200117", True),
        ("20017", "POL-200117", True),
        # Una cifra distinta, con las seis oidas.
        ("200118", "POL-200117", True),
        ("300117", "POL-200117", True),
        # Lo que no: tres cifras menos, cifras fuera de orden, dos distintas, de mas.
        ("201", "POL-200117", False),
        ("71102", "POL-200117", False),
        ("17001", "POL-200117", False),
        ("200228", "POL-200117", False),
        ("2001175", "POL-200117", False),
        ("30117", "POL-200117", False),
        ("", "POL-200117", False),
    ],
)
def test_se_parecen_si_faltan_como_mucho_dos_cifras_en_orden_o_una_es_distinta(
    oido: str, numero: str, se_parecen: bool
) -> None:
    assert policy.digits_resemble(oido, numero) is se_parecen
