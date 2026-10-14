"""Los insumos de triage que se derivan de lo capturado (PENDIENTES 1.8, mitad 2).

Lo que estas pruebas vigilan no es que la funcion devuelva un booleano: es que
**tres situaciones sigan siendo tres**. "Nadie pregunto por los terceros", "se
pregunto y no habia" y "hay terceros y les falta algo" tienen tres consecuencias
distintas en la bandeja, y las dos primeras colapsadas en `False` cierran directo
un caso que nadie llego a capturar.
"""

from __future__ import annotations

import pytest

from untangle.case_record import crypto
from untangle.case_record.models import CaseParty, FieldStatus, PartyRole, Sealed
from untangle.orchestration.triage_inputs import injuries_present, other_parties_data_pending
from untangle.settings import Settings

CASO = "case-0001"
#: Toda placa `stated` lleva el turno que la respalda: lo exige el propio modelo
#: (AC1.8.3), y por eso aqui no hay ninguna sin el.
TURNO = "turn-0001"


#: El cifrador de verdad, con una clave de un solo uso. **No se construye `Sealed`
#: a mano**: PA-8 exige que el unico sitio que fabrica un valor sellado sea
#: `case_record/crypto.py`, porque `NewType` se borra en tiempo de ejecucion y unos
#: bytes fabricados aqui son indistinguibles de un dato personal sin cifrar. Lo
#: comprueba `mise run case:constructor`, que es compuerta.
_CIFRADOR = crypto.Cipher.from_settings(Settings(case_field_encryption_key=crypto.generate_key()))


def _sellado(marca: str) -> Sealed:
    return _CIFRADOR.seal(marca)


def _parte(role: PartyRole, **atributos: object) -> CaseParty:
    return CaseParty(party_id=f"p-{role.value}", case_id=CASO, role=role, **atributos)  # type: ignore[arg-type]


def _persona_completa(role: PartyRole = PartyRole.OTHER_DRIVER) -> CaseParty:
    return _parte(role, name=_sellado("nombre"), contact=_sellado("telefono"))


def _vehiculo_completo() -> CaseParty:
    return _parte(
        PartyRole.OTHER_VEHICLE,
        plate=_sellado("ABC123"),
        plate_status=FieldStatus.STATED,
        plate_evidence_turn_id=TURNO,
        vehicle_description="sedan gris",
    )


# --- Las tres situaciones -----------------------------------------------------


def test_sin_preguntar_no_afirma_nada() -> None:
    """El bloque sin tocar devuelve `None`, y `None` deja el campo ausente.

    Un campo ausente no dispara ninguna regla, asi que el caso cae en revision
    estandar: la salida segura. Es distinto de `False`, que afirmaria que se
    comprobo.
    """
    assert other_parties_data_pending((), block_status=FieldStatus.NOT_STATED) is None


def test_preguntado_y_sin_terceros_es_una_respuesta_comprobada() -> None:
    """`False`, no `None`: es lo que deja cerrar directo un choque de un solo auto.

    La primera regla de Sunmeadow exige `other_parties_data_pending: false` junto
    con `injuries_present: false`. Si esta respuesta fuera `None`, ese camino de
    cierre directo no se abriria nunca y la regla quedaria muerta. Pero solo lo es
    cuando lo dicho **niega** a los terceros (ver la tabla de abajo): que el bloque
    se haya dicho no prueba que no los hubiera.
    """
    assert other_parties_data_pending((), block_status=FieldStatus.STATED, value="ninguno") is False


def test_el_bloque_dicho_sin_texto_no_prueba_que_no_hubiera_terceros() -> None:
    """Antes de la regla de cierre directo real esto era `False`: «dicho» bastaba.

    Con cierre directo de verdad, «me choco un taxi y se fue» deja el bloque dicho y sin
    ninguna fila de partes, y devolver `False` cerraria solo un choque con un tercero
    desconocido. Sin texto que lo niegue, el insumo queda ausente.
    """
    assert other_parties_data_pending((), block_status=FieldStatus.STATED) is None
    assert other_parties_data_pending((), block_status=FieldStatus.CONFIRMED, value=None) is None


def test_un_tercero_al_que_le_falta_algo_deja_el_caso_pendiente() -> None:
    sin_telefono = _parte(PartyRole.OTHER_DRIVER, name=_sellado("nombre"))

    assert other_parties_data_pending((sin_telefono,), block_status=FieldStatus.STATED) is True


def test_terceros_completos_no_dejan_nada_pendiente() -> None:
    """El control contrario: sin el, una version que devolviera siempre cierto pasaria."""
    completos = (_persona_completa(), _vehiculo_completo())

    assert other_parties_data_pending(completos, block_status=FieldStatus.CONFIRMED) is False


# --- Que dato cuenta, segun lo que la parte es --------------------------------


@pytest.mark.parametrize(
    ("parte", "esperado"),
    [
        pytest.param(_persona_completa(), False, id="persona-completa"),
        pytest.param(
            _parte(PartyRole.OTHER_DRIVER, contact=_sellado("telefono")),
            True,
            id="persona-sin-nombre",
        ),
        pytest.param(
            _parte(PartyRole.OTHER_DRIVER, name=_sellado("nombre")), True, id="persona-sin-contacto"
        ),
        pytest.param(_vehiculo_completo(), False, id="vehiculo-completo"),
        pytest.param(
            _parte(PartyRole.OTHER_VEHICLE, vehicle_description="sedan gris"),
            True,
            id="vehiculo-sin-placa",
        ),
        pytest.param(
            _parte(
                PartyRole.OTHER_VEHICLE,
                plate=_sellado("ABC123"),
                plate_status=FieldStatus.STATED,
                plate_evidence_turn_id=TURNO,
            ),
            True,
            id="vehiculo-sin-descripcion",
        ),
    ],
)
def test_cada_clase_de_tercero_tiene_sus_propios_datos(parte: CaseParty, esperado: bool) -> None:
    """Un vehiculo no tiene telefono y una persona no tiene placa.

    Sin listas por rol, "le falta algun atributo" seria cierto para **todos** --un
    vehiculo nunca tiene nombre-- y la regla disparia siempre, que es la misma
    forma de fallo que un campo que no puede coincidir.
    """
    assert other_parties_data_pending((parte,), block_status=FieldStatus.STATED) is esperado


def test_la_placa_se_mira_por_su_estado_y_no_por_su_valor() -> None:
    """`NOT_STATED` es "nadie la dijo", que es justo el dato pendiente.

    Una version que mirara `plate is None` daria lo mismo en este caso y se
    equivocaria en el de abajo, donde la placa se dijo y no se pudo sellar.
    """
    dicha_sin_valor = _parte(
        PartyRole.OTHER_VEHICLE,
        plate_status=FieldStatus.STATED,
        plate_evidence_turn_id=TURNO,
        vehicle_description="sedan",
    )

    assert other_parties_data_pending((dicha_sin_valor,), block_status=FieldStatus.STATED) is False


# --- Quien es un tercero y quien no -------------------------------------------


def test_quien_reporta_no_es_un_tercero_del_accidente() -> None:
    """El texto que ve el ajustador dice "los terceros involucrados".

    Quien llama **por** alguien no esta involucrado en el accidente, asi que un
    reportante sin telefono no manda el caso a revision. Sin esta prueba, incluir
    `REPORTER` en la lista pasaria inadvertido y derivaria todo caso reportado por
    un familiar.
    """
    reportante = _parte(PartyRole.REPORTER, relation="hijo del asegurado")

    assert (
        other_parties_data_pending((reportante,), block_status=FieldStatus.STATED, value="ninguno")
        is False
    )
    # Y sin una negacion que lo respalde, un reportante no prueba que no hubiera terceros.
    assert other_parties_data_pending((reportante,), block_status=FieldStatus.STATED) is None


def test_un_lesionado_sin_datos_si_es_un_tercero() -> None:
    """El control contrario del de arriba: la lista no puede quedarse en dos roles."""
    lesionado = _parte(PartyRole.INJURED, injury_status="golpe en el brazo")

    assert other_parties_data_pending((lesionado,), block_status=FieldStatus.STATED) is True


# --- Terceros: lo que niega y lo que no --------------------------------------------------
#
# `False` es lo unico que cierra un caso sin ajustador, asi que cada duda cae en `None`. Las
# tablas llevan lo que deja el modelo («ninguno») y las palabras de la persona, en los dos
# idiomas.

NADIE_MAS = [
    "ninguno",
    "Ninguno.",
    "Ninguna",
    "no",
    "No.",
    "No, nadie",
    "Nadie",
    "Nadie más",
    "nadie mas",
    "No hubo otros",
    "No hubo otros vehículos",
    "No hubo otros vehículos involucrados",
    "No hubo ningún otro vehículo",
    "Ningún otro vehículo",
    "No hubo terceros",
    "No hay terceros",
    "Sin terceros",
    "No, no hubo nadie más",
    "No hubo nadie",
    "Cero",
    "Solo yo",
    "solo mi carro",
    "Solo mi carro, nadie más",
    "No, solo mi carro",
    "Solo el mío",
    "Solamente yo",
    "No, gracias",
    "none",
    "None",
    "No one",
    "No one else",
    "Nobody else",
    "Nobody",
    "No other vehicles",
    "No other cars were involved",
    "There were no other vehicles",
    "There was nobody else",
    "No, nobody else",
    "No, just me",
    "Just me",
    "Only my car",
    "Just my car, nobody else",
    "None at all",
    "No third parties",
    "No, thanks",
]

HUBO_OTROS_O_NO_SE_SABE = [
    "",
    "   ",
    # Nombra a un tercero.
    "Me chocó un taxi y se fue",
    "Un taxi",
    "Sí, un taxi blanco",
    "Sí",
    "Una moto",
    "El otro conductor se fue",
    "No, el otro conductor",
    "No, el otro conductor se fue",
    "Otro carro",
    "Otros vehículos",
    "Mi esposa iba conmigo",
    "Iba con mi hijo",
    "Un peatón",
    "A taxi hit me and drove off",
    "Yes, a white taxi",
    "Yes",
    "The other driver left",
    "No, the other driver left",
    "Another car",
    "A motorcycle",
    # Un «no» que no niega a los terceros, o que se contradice.
    "No, otros vehículos",
    "No, pero un taxi se fue",
    "No hubo otros vehículos pero una moto se fue",
    "No hubo otros, pero el taxi no paró",
    "Sí, nadie más",
    "Yes, nobody else",
    "No, but a taxi left",
    # Duda o desconocimiento.
    "No sé",
    "No se",
    "No creo",
    "Creo que no",
    "Creo que nadie más",
    "No estoy seguro",
    "Tal vez",
    "No tengo los datos del otro",
    "I don't know",
    "I think not",
    "I don't think so",
    "Not sure",
    "Maybe",
    "Not that I know of",
    # Habla de otra cosa.
    "Iba solo",
    "Iba solo y chocó otro carro",
    "Solo yo choqué",
    "Solo yo choqué con otro carro",
    "No hubo heridos",
    "Sin heridos",
    "Sin daños materiales",
    "Solo daños materiales",
    "Todo bien",
    "Nadie salió herido",
    "Just the car was damaged",
    "I was alone",
    "Only I crashed",
]


@pytest.mark.parametrize("texto", NADIE_MAS)
def test_una_negacion_clara_de_terceros_es_falso(texto: str) -> None:
    assert other_parties_data_pending((), block_status=FieldStatus.STATED, value=texto) is False, (
        texto
    )


@pytest.mark.parametrize("texto", HUBO_OTROS_O_NO_SE_SABE)
def test_un_tercero_nombrado_o_una_duda_nunca_es_falso(texto: str) -> None:
    """El error caro, de frente: ninguna frase que nombre a un tercero o dude sale falsa.

    Queda `None` y no `True`: sin filas de partes no hay a quien mirarle los datos, y el
    caso va a revision estandar (la salida segura) en vez de cerrar solo.
    """
    assert other_parties_data_pending((), block_status=FieldStatus.STATED, value=texto) is None, (
        texto
    )


def test_ninguna_frase_con_un_tercero_sale_falsa_con_ningun_prefijo() -> None:
    """Lo mismo cruzado con lo que una persona podria escribir alrededor.

    Las tablas son listas de ejemplos; esta cruza las frases que nombran a un tercero con
    cada prefijo, para que una palabra nueva en las listas de negaciones no abra un hueco
    sin que nada se ponga rojo.
    """
    nombran = [
        t
        for t in HUBO_OTROS_O_NO_SE_SABE
        if t.strip()
        and t
        not in {
            "No sé",
            "No se",
            "No creo",
            "Creo que no",
            "No estoy seguro",
            "Tal vez",
            "I don't know",
            "I think not",
            "I don't think so",
            "Not sure",
            "Maybe",
            "Not that I know of",
        }
    ]
    for prefijo in ["", "No. ", "No, ", "Nadie, ", "Ninguno, ", "Solo yo, ", "None, "]:
        for dicho in nombran:
            texto = f"{prefijo}{dicho}"
            assert (
                other_parties_data_pending((), block_status=FieldStatus.STATED, value=texto)
                is not False
            ), texto


@pytest.mark.parametrize("texto", NADIE_MAS)
def test_la_negacion_sin_estado_dicho_no_dice_nada(texto: str) -> None:
    """El estado manda: un bloque que nadie dijo no tiene nada que leer."""
    assert other_parties_data_pending((), block_status=FieldStatus.NOT_STATED, value=texto) is None


def test_una_fila_de_tercero_manda_sobre_lo_que_diga_el_texto() -> None:
    """«Ninguno» con un otro conductor registrado y sin telefono sigue siendo pendiente.

    La fila es evidencia de que hubo un tercero; el texto no la borra.
    """
    sin_telefono = _parte(PartyRole.OTHER_DRIVER, name=_sellado("nombre"))

    assert (
        other_parties_data_pending(
            (sin_telefono,), block_status=FieldStatus.STATED, value="ninguno"
        )
        is True
    )


# --- Heridos ------------------------------------------------------------------------------
#
# Lo que se vigila aqui es la asimetria: `False` es lo unico que cierra un caso sin ajustador,
# asi que cada duda tiene que caer en `True` o en `None`. Las tablas llevan las frases en los
# dos idiomas, tal como las deja el modelo («no») o las palabras de la persona.

NADIE_SE_LASTIMO = [
    "no",
    "No.",
    "NO, NADIE SE LASTIMÓ",
    "No, nadie",
    "Nadie",
    "Ninguno",
    "Nadie salió herido",
    "Nadie resultó lesionado",
    "Nadie se lastimó",
    "Nadie se hizo daño",
    "No hubo heridos",
    "No hay heridos",
    "Sin heridos",
    "Sin lesiones",
    "Ningún herido",
    "Cero heridos",
    "0 heridos",
    "Ni un rasguño",
    "No hubo ni heridos ni muertos",
    "No hubo daños personales",
    "No, gracias a Dios",
    "Gracias a Dios nadie se lastimó",
    "Afortunadamente nadie salió herido",
    "Por suerte no hubo heridos",
    "No, solo daños materiales",
    "No hubo heridos, solo daños materiales",
    "nope",
    "Nobody",
    "No one",
    "No one got hurt",
    "Nobody was hurt",
    "Nobody was injured, thank God",
    "No injuries",
    "There were no injuries",
    "Luckily nobody got hurt",
    "No, just the car",
    "No, only property damage",
    "No injuries, just property damage",
    "Zero injuries",
]

HUBO_HERIDOS = [
    "Sí",
    "si",
    "Sí, mi esposa",
    "Sí, dos personas",
    "Sí, mi hijo se golpeó la cabeza",
    "Hubo un herido",
    "Hay dos heridos",
    "Mi esposa está lesionada",
    "Un lesionado",
    "Estoy herido",
    "Se golpeó la cabeza",
    "Me duele el cuello",
    "Sangró mucho",
    "Se lo llevó la ambulancia",
    "Solo hubo heridos leves",
    "Creo que mi hijo se lastimó",
    # El «no» no borra lo que sigue.
    "No, pero mi hijo se golpeó la cabeza",
    "No hubo heridos, pero el otro conductor dice que le duele el cuello",
    "Nadie salió herido pero mi esposa tiene dolor",
    "Yes",
    "yes, two people",
    "Yes, my wife hit her head",
    "My son got hurt",
    "Someone was injured",
    "One person hurt",
    "I'm hurt",
    "The other driver went to the hospital",
    "No, but my son hit his head",
    "No injuries, but my neck hurts",
    "Nobody died but my wife is in pain",
]

NO_SE_SABE = [
    "",
    "   ",
    "No sé",
    "No se",
    "No creo",
    "Creo que no",
    "Creo que nadie",
    "Nadie, creo",
    "No estoy seguro",
    "Parece que no",
    "Tal vez",
    # Una negacion que deja abierta la lesion pequena no dice que nadie se lastimo.
    "Nada grave",
    "No hubo heridos graves",
    "Nadie salió herido de gravedad",
    # Estar bien no es negar la lesion, y «no me lastime» habla solo de quien escribe.
    "Estamos bien",
    "Todos estamos bien",
    "Todo bien",
    "No me lastimé",
    "Mi hijo",
    "Una persona",
    "Solo fue el susto",
    "Solo daños materiales",
    # El «no» niega el carro, no a las personas.
    "No hubo daños materiales",
    "Sin daños materiales",
    "Ningún daño material",
    "Ninguno de los carros",
    "None of the cars",
    "No, el otro conductor se fue",
    "No hubo heridos, estoy segura",
    # Se contradice.
    "Sí, nadie se lastimó",
    "I don't know",
    "I think not",
    "I don't think so",
    "Not sure",
    "Maybe",
    "Nothing serious",
    "No serious injuries",
    "Nobody was seriously hurt",
    "Everyone is fine",
    "We are all fine",
    "I wasn't hurt",
    "Not hurt",
    "My son",
    "Just the car",
    "No, the other driver left",
    "Yes, nobody got hurt",
]


@pytest.mark.parametrize("texto", NADIE_SE_LASTIMO)
def test_una_negacion_clara_es_falso(texto: str) -> None:
    assert injuries_present(texto, status=FieldStatus.STATED) is False


@pytest.mark.parametrize("texto", HUBO_HERIDOS)
def test_una_mencion_de_dano_a_una_persona_es_verdadero(texto: str) -> None:
    assert injuries_present(texto, status=FieldStatus.STATED) is True


@pytest.mark.parametrize("texto", NO_SE_SABE)
def test_lo_dudoso_o_ajeno_a_las_personas_queda_ausente(texto: str) -> None:
    """Ni `True` ni `False`: sin el insumo el caso va a revision estandar."""
    assert injuries_present(texto, status=FieldStatus.STATED) is None


def test_ninguna_frase_con_dano_a_una_persona_sale_falsa() -> None:
    """El error caro, buscado por todos lados: ninguna frase de las que mencionan dano es falsa.

    Las tablas de arriba son listas de ejemplos; esta cruza la de heridos con cada prefijo y
    cada cierre que una persona podria escribir alrededor, para que un prefijo nuevo en la
    lista de negaciones no abra un hueco sin que nada se ponga rojo.
    """
    prefijos = ["", "No. ", "No, ", "Nadie, ", "Gracias a Dios, ", "Sin heridos, "]
    for prefijo in prefijos:
        for dano in HUBO_HERIDOS:
            texto = f"{prefijo}{dano}"
            assert injuries_present(texto, status=FieldStatus.STATED) is not False, texto


@pytest.mark.parametrize("texto", NADIE_SE_LASTIMO)
def test_el_mismo_texto_sin_estado_dicho_no_dice_nada(texto: str) -> None:
    """El estado manda: un campo que nadie dijo no tiene nada que leer."""
    assert injuries_present(texto, status=FieldStatus.NOT_STATED) is None


def test_un_campo_confirmado_cuenta_igual_que_uno_dicho() -> None:
    assert injuries_present("no", status=FieldStatus.CONFIRMED) is False
    assert injuries_present("sí, dos", status=FieldStatus.CONFIRMED) is True


def test_sin_valor_no_hay_nada_que_leer() -> None:
    assert injuries_present(None, status=FieldStatus.STATED) is None


def test_un_lesionado_registrado_manda_sobre_lo_que_diga_el_campo() -> None:
    """Un tercero registrado como lesionado es evidencia de heridos aunque el campo diga que no."""
    lesionado = (_parte(PartyRole.INJURED, injury_status="golpe en el brazo"),)

    assert injuries_present("no", status=FieldStatus.STATED, parties=lesionado) is True
    assert injuries_present(None, status=FieldStatus.NOT_STATED, parties=lesionado) is True


def test_un_tercero_que_no_esta_lesionado_no_cambia_la_lectura() -> None:
    """El control contrario: la regla es por rol, no por haber terceros."""
    otro = (_persona_completa(PartyRole.OTHER_DRIVER),)

    assert injuries_present("no", status=FieldStatus.STATED, parties=otro) is False
    assert injuries_present("no sé", status=FieldStatus.STATED, parties=otro) is None
