"""El numero de poliza en lo que la persona dijo, tambien por voz (2026-10-09).

Desde el 2026-10-30 el numero es `POL-` y **dos** cifras (`POL-23`): antes eran seis. Quien lo
dice por voz dice «veintitres» o «dos tres», y el reconocedor lo entrega como «Paul 23», «pol 23»
o en palabras. Lo que hay que seguir midiendo es lo mismo: reconocerlo cuando es una poliza, no
tomar por poliza cualquier numero de dos cifras, y nunca inventar lo que no se oyo.
"""

from __future__ import annotations

import pytest

from untangle.orchestration.nodes.intake import policy


@pytest.mark.parametrize(
    ("dicho", "esperado"),
    [
        ("mi póliza es 23", "POL-23"),
        ("mi póliza es la 2 3", "POL-23"),
        ("my policy is 2 3", "POL-23"),
        ("23", "POL-23"),
        ("es la 23", "POL-23"),
        ("mi póliza es POL-11", "POL-11"),
        ("mi póliza es la pol-11", "POL-11"),
        # Dicho en palabras, en los dos idiomas.
        ("mi póliza es veintitrés", "POL-23"),
        ("mi póliza es treinta y uno", "POL-31"),
        ("mi póliza es la cincuenta", "POL-50"),
        ("mi póliza es once", "POL-11"),
        ("my policy is twenty-three", "POL-23"),
        ("my policy is thirty one", "POL-31"),
        ("veintitrés", "POL-23"),
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
        # El numero de seis cifras de antes ya no es una poliza.
        "mi póliza es POL-100042",
    ],
)
def test_otras_cifras_no_se_leen_como_poliza(dicho: str) -> None:
    assert policy.policy_number_in(dicho) is None


# --- El numero tal como lo entrega el reconocedor de una llamada (2026-10-13) --------------
#
# En una llamada real, «Soy Marco Parker, mi poliza es POL-200117» llego en tres trozos:
# «Claro, mi nombre completo es Marco Parker» / «y mi poliza es Paul» / «201 17.». El turno
# trae los finales unidos con un espacio. Con dos cifras la misma forma de fallo es «Paul 20 1.»
# por «veintiuno» (POL-21).


def test_la_llamada_real_se_oye_incompleta_y_no_se_inventa_nada() -> None:
    dicho = "Claro, mi nombre completo es Lina Diaz y mi póliza es Paul 20 1."

    oido = policy.heard_policy_number(dicho)

    assert oido is not None
    assert oido.digits == "201"
    assert not oido.complete
    assert oido.number is None
    # Tres cifras no son una poliza: el buscador exacto no recibe nada que adivinar.
    assert policy.policy_number_in(dicho) is None


@pytest.mark.parametrize(
    ("dicho", "esperado"),
    [
        # La palabra que nombra el codigo llega deformada, justo despues de «poliza».
        ("mi póliza es Paul 23", "POL-23"),
        ("mi póliza es Pol 23", "POL-23"),
        ("mi póliza es Poll 23", "POL-23"),
        ("mi póliza es Paula 23", "POL-23"),
        ("mi póliza es pool 23", "POL-23"),
        ("mi póliza es pole 23", "POL-23"),
        ("my policy is Paul 23", "POL-23"),
        ("mi póliza es Paul 20", "POL-20"),
        # O sola antes de las cifras, sin decir «poliza».
        ("es Paul 2 3", "POL-23"),
        ("Paula 23", "POL-23"),
        # Las cifras juntas, en grupos y en trozos distintos.
        ("mi póliza es Paul 2 3", "POL-23"),
        ("mi póliza es 2 3", "POL-23"),
        ("mi póliza es 2-3", "POL-23"),
        ("mi póliza es 2.3", "POL-23"),
        ("mi póliza es 2,3", "POL-23"),
        ("mi póliza: 23", "POL-23"),
        ("Póliza #23", "POL-23"),
        ("mi póliza es la POL 23", "POL-23"),
        ("mi póliza es pol23", "POL-23"),
        ("mi póliza es P O L 2 3", "POL-23"),
        # Entre dos finales seguidos: el punto de cada final queda en medio.
        ("y mi póliza es Paul. 2. 3.", "POL-23"),
        ("y mi póliza es Paul. 23.", "POL-23"),
        # En palabras, en los dos idiomas: cifra por cifra y como numero.
        ("mi póliza es dos tres", "POL-23"),
        ("my policy is two three", "POL-23"),
        ("dos tres", "POL-23"),
        ("two three", "POL-23"),
        ("mi póliza es Paul dos 3", "POL-23"),
        ("mi póliza es Pol dos tres.", "POL-23"),
        ("mi póliza es Paul veintitrés", "POL-23"),
        ("mi póliza es veinte tres", "POL-23"),
        ("mi póliza es la treinta y cuatro", "POL-34"),
        ("my policy is twenty-three", "POL-23"),
        ("my policy is twenty three", "POL-23"),
        # Con otros datos en la frase.
        ("Soy Lina Diaz, mi póliza es Paul 23 y me chocaron", "POL-23"),
        ("Claro, mi nombre completo es Lina Diaz y mi póliza es Paul 23.", "POL-23"),
    ],
)
def test_con_exactamente_dos_cifras_se_arma_pol_y_esas_cifras(dicho: str, esperado: str) -> None:
    assert policy.policy_number_in(dicho) == esperado, dicho
    oido = policy.heard_policy_number(dicho)
    assert oido is not None
    assert oido.complete
    assert oido.number == esperado


@pytest.mark.parametrize(
    ("dicho", "cifras"),
    [
        ("mi póliza es Paul 201", "201"),
        ("mi póliza es Paul 20 1", "201"),
        ("mi póliza: 2 0 1", "201"),
        ("mi póliza es Pol 2 0 1", "201"),
        ("mi póliza es dos cero uno", "201"),
        ("my policy is two zero one", "201"),
        # Mas de dos tampoco se corta ni se completa: se oye tal cual.
        ("mi póliza es Paul 2001175", "2001175"),
        ("mi póliza es 200 117", "200117"),
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
        # Una sola cifra, o sin nada que diga que son de la poliza, no es un numero oido.
        "mi póliza es Paul 2",
        "tengo póliza. 2 carros fueron golpeados",
        "dos personas heridas",
        "somos tres y el carro es un Mazda 3",
        "mi póliza no la tengo a la mano",
        "no sé el número",
        "Claro, mi nombre completo es Lina Diaz",
        # Dos cifras que son de otra cosa: una hora, una edad, una cantidad. Con seis cifras bastaba
        # que el texto nombrara la poliza en otro sitio; con dos, no.
        "el choque fue a las 10",
        "tengo 23 años",
        "somos 23 en la fiesta",
        "mi póliza no la tengo, el choque fue a las 10",
        "había once personas",
        "eran las diez de la noche",
        "my policy is lost, it was at ten pm",
    ],
)
def test_lo_que_no_parece_un_numero_de_poliza_no_se_oye_como_tal(dicho: str) -> None:
    assert policy.heard_policy_number(dicho) is None, dicho


@pytest.mark.parametrize(
    ("dicho", "esperado"),
    [
        # Un telefono, una cedula, una placa o una fecha en la misma frase no son la poliza.
        ("mi teléfono es 300 123 4567 y mi póliza es Paul 23", "POL-23"),
        ("mi celular es 3001234567 y mi póliza es pol 23", "POL-23"),
        ("mi cédula es 79123456 y mi póliza es POL-23", "POL-23"),
        ("mi cédula es 79.123.456 y mi póliza es Paul 23", "POL-23"),
        ("mi placa es ABC 123 y mi póliza es pol 23", "POL-23"),
        ("mi placa es ABC123 y mi póliza es Paul 23", "POL-23"),
        ("el choque fue el 13/10/2026 y mi póliza es Paul 23", "POL-23"),
        ("el choque fue el 13 de octubre de 2026, mi póliza es Paul 23", "POL-23"),
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
        # Dos cifras solas pero que una palabra anuncia como otro dato.
        "mi cédula es 79",
        "mi placa es 23",
    ],
)
def test_ninguno_de_esos_datos_se_toma_por_la_poliza_aunque_se_hable_de_ella(dicho: str) -> None:
    assert policy.policy_number_in(dicho) is None, dicho
    oido = policy.heard_policy_number(dicho)
    assert oido is None or not oido.complete, dicho


def test_con_dos_numeros_en_la_frase_gana_el_que_va_pegado_a_la_poliza() -> None:
    dicho = "el 300 123 es mi celular y mi póliza es Paul 23"

    assert policy.policy_number_in(dicho) == "POL-23"


def test_dos_numeros_sueltos_sin_palabra_de_poliza_no_se_toman_por_ninguno() -> None:
    """Con dos cifras, «21 y 30» es ambiguo: no se elige uno."""
    assert policy.policy_number_in("21 y 30") is None


@pytest.mark.parametrize(
    ("oido", "numero", "se_parecen"),
    [
        # Las mismas cifras, una distinta.
        ("22", "POL-21", True),
        ("31", "POL-21", True),
        ("20", "POL-21", True),
        # Una cifra de mas y las de la poliza en orden: «veinte uno» llega como «20 1».
        ("201", "POL-21", True),
        ("021", "POL-21", True),
        ("211", "POL-21", True),
        # Lo que no: una sola cifra, dos distintas, cifras fuera de orden, mas de una de sobra.
        ("2", "POL-21", False),
        ("32", "POL-21", False),
        ("12", "POL-21", False),
        ("120", "POL-21", False),
        ("2001", "POL-21", False),
        ("200117", "POL-21", False),
        ("", "POL-21", False),
    ],
)
def test_se_parecen_si_es_una_cifra_distinta_o_hay_una_de_mas_en_orden(
    oido: str, numero: str, se_parecen: bool
) -> None:
    assert policy.digits_resemble(oido, numero) is se_parecen
