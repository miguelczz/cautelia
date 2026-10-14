"""Las etiquetas: idioma, numeracion y lo que nunca llevan (BR3.1 a BR3.4).

Lo que aqui se protege es lo que **queda escrito**: una persona lee la
transcripcion, el renglon de log o la traza exportada, y tiene que entenderla sin
descifrar nada y sin que le quede delante ni un digito del dato.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from untangle.base import Locale
from untangle.compliance.redaction import labels
from untangle.compliance.redaction.recognizers.models import DetectedEntity, EntityType
from untangle.copy_catalog import api as copy_api


@pytest.fixture(autouse=True)
def _catalogo_limpio() -> Iterator[None]:
    """Ninguna prueba deja un catalogo instalado para la siguiente."""
    copy_api.reset()
    yield
    copy_api.reset()


def _hallazgo(
    tipo: EntityType, inicio: int, fin: int, *, quien: str = "es-phone"
) -> DetectedEntity:
    return DetectedEntity(
        entity_type=tipo, start=inicio, end=fin, recognizer_id=quien, confidence=0.9
    )


# --- El idioma de la conversacion (BR3.2, decision FD-U3-7) -------------------


@pytest.mark.parametrize("tipo", list(EntityType))
def test_cada_tipo_tiene_etiqueta_en_los_dos_idiomas(tipo: EntityType) -> None:
    """BR3.4: si a un tipo le faltara su clave en un idioma, el dato saldria
    tapado con el nombre de la clave delante de una persona."""
    en_espanol = labels.label_for(tipo, locale="es", ordinal=1)
    en_ingles = labels.label_for(tipo, locale="en", ordinal=1)

    for etiqueta in (en_espanol, en_ingles):
        assert etiqueta.startswith("[")
        assert etiqueta.endswith("]")
        assert "redaction.label" not in etiqueta, "la clave salio en vez de su frase"


def test_la_etiqueta_se_escribe_en_el_idioma_de_la_conversacion() -> None:
    """Un `[PHONE]` dentro de prosa en espanol se lee peor que un `[TELEFONO]`,
    y un renglon de log se lee fuera del aplicativo, sin catalogo que resolver."""
    assert labels.label_for(EntityType.PHONE, locale="es", ordinal=1) != labels.label_for(
        EntityType.PHONE, locale="en", ordinal=1
    )


def test_la_etiqueta_lleva_su_numero() -> None:
    assert "2" in labels.label_for(EntityType.PHONE, locale="es", ordinal=2)


# --- La numeracion dentro de la llamada (BR3.3, decision FD-U3-10) ------------


def test_dos_datos_distintos_del_mismo_tipo_se_distinguen() -> None:
    """El telefono del asegurado y el del testigo, en el mismo turno.

    Sin numero, los dos saldrian como `[TELEFONO]` y quien lea la transcripcion
    no sabria si son el mismo numero repetido o dos numeros distintos.
    """
    texto = "Mi telefono es 3005551234 y el del testigo es 3005559999."
    hallazgos = [
        _hallazgo(EntityType.PHONE, 15, 25),
        _hallazgo(EntityType.PHONE, 46, 56),
    ]

    etiquetas = labels.labels_for(texto, hallazgos, locale="es")

    assert etiquetas[0] != etiquetas[1]


def test_el_mismo_valor_repetido_conserva_su_numero() -> None:
    """Repetir el mismo telefono en un turno no lo convierte en dos telefonos."""
    texto = "Mi telefono es 3005551234, repito, 3005551234."
    hallazgos = [
        _hallazgo(EntityType.PHONE, 15, 25),
        _hallazgo(EntityType.PHONE, 35, 45),
    ]

    etiquetas = labels.labels_for(texto, hallazgos, locale="es")

    assert etiquetas[0] == etiquetas[1]


def test_la_numeracion_es_por_tipo_y_no_una_sola_cuenta() -> None:
    """Un telefono y una placa en el mismo turno son `1` cada uno.

    Con una cuenta unica, la placa saldria como `[PLACA 2]` y pareceria que hubo
    una primera placa que no se ve.
    """
    texto = "Mi telefono es 3005551234 y la placa es ABC123."
    hallazgos = [
        _hallazgo(EntityType.PHONE, 15, 25),
        _hallazgo(EntityType.LICENSE_PLATE, 40, 46, quien="es-license-plate"),
    ]

    etiquetas = labels.labels_for(texto, hallazgos, locale="es")

    assert etiquetas == (
        labels.label_for(EntityType.PHONE, locale="es", ordinal=1),
        labels.label_for(EntityType.LICENSE_PLATE, locale="es", ordinal=1),
    )


def test_la_numeracion_empieza_de_nuevo_en_cada_llamada() -> None:
    """Deliberado (decision FD-U3-10): mantenerla entre turnos exigiria guardar
    la correspondencia entre el valor real y su numero, que es la boveda que
    BR1.6 prohibe. Donde de verdad sirve --distinguir el telefono del asegurado
    del del testigo-- es dentro del mismo turno."""
    primero = "Llame al 3005559999 ayer."
    segundo = "Hoy llame al 3005551234."

    uno = labels.labels_for(primero, [_hallazgo(EntityType.PHONE, 9, 19)], locale="es")
    dos = labels.labels_for(segundo, [_hallazgo(EntityType.PHONE, 13, 23)], locale="es")

    assert uno == dos == (labels.label_for(EntityType.PHONE, locale="es", ordinal=1),)


# --- Lo que la etiqueta nunca lleva (BR3.1) -----------------------------------


def test_la_etiqueta_no_depende_del_dato_que_tapa() -> None:
    """AC4.12.3: nunca con sus digitos, ni con su longitud.

    Se comprueba por donde de verdad se rompe: la etiqueta la deciden **el tipo
    y el numero**, y nada mas. Dos datos distintos, de longitudes distintas y sin
    un digito en comun, producen la misma etiqueta. Asi no puede colarse un
    prefijo, un sufijo ni la longitud, que son las tres formas de dejar algo
    reconstruible, y la tercera lo es incluso sin ensenar un digito.

    Lo unico que la etiqueta tiene en comun con el dato es el numero de orden,
    que no sale del valor sino de cuantos datos de ese tipo lleva el texto.
    """
    uno = labels.labels_for(
        "Llame al 3005551234.", [_hallazgo(EntityType.PHONE, 9, 19)], locale="es"
    )
    otro = labels.labels_for("Llame al 6088899.", [_hallazgo(EntityType.PHONE, 9, 16)], locale="es")

    assert uno == otro

    (etiqueta,) = uno
    assert "3005551234" not in etiqueta
    # Ninguna pareja de digitos seguidos del dato aparece en la etiqueta: el
    # numero de orden es un digito suelto y no dice nada del valor.
    dato = "3005551234"
    parejas = {dato[i : i + 2] for i in range(len(dato) - 1)}
    assert not any(pareja in etiqueta for pareja in parejas), etiqueta


def test_la_numeracion_no_guarda_ningun_valor() -> None:
    """BR1.6: lo que se lleva entre hallazgos son numeros, no valores.

    Se comprueba por la conducta que esa propiedad implica: el numero de un
    hallazgo depende solo de lo que hay **en este texto**, asi que redactar el
    mismo valor en dos textos distintos no lo recuerda.
    """
    numeros = labels.ordinals(
        "3005551234 y 3005551234 y 3005559999",
        [
            _hallazgo(EntityType.PHONE, 0, 10),
            _hallazgo(EntityType.PHONE, 13, 23),
            _hallazgo(EntityType.PHONE, 26, 36),
        ],
    )

    assert numeros == (1, 1, 2)


# --- Lo que se dice en voz alta en lugar de una etiqueta (2026-10-13) ----------


@pytest.mark.parametrize("idioma", ["es", "en"])
@pytest.mark.parametrize("tipo", list(EntityType))
def test_cada_tipo_tiene_su_palabra_neutra_en_los_dos_idiomas(
    tipo: EntityType, idioma: Locale
) -> None:
    """Sin palabra neutra, una etiqueta que llegara al altavoz saldria con la clave."""
    dicha = labels.spoken_label_for(tipo, locale=idioma)

    assert dicha.strip()
    assert "redaction.spoken" not in dicha, "la clave salio en vez de su frase"
    assert "[" not in dicha
    assert not any(c.isdigit() for c in dicha)


@pytest.mark.parametrize("idioma", ["es", "en"])
@pytest.mark.parametrize("tipo", list(EntityType))
def test_cada_etiqueta_se_cambia_por_la_palabra_neutra_de_su_tipo(
    tipo: EntityType, idioma: Locale
) -> None:
    """Con cualquier numero, y sin dejar ni el corchete ni el digito."""
    for numero in (1, 2, 17):
        etiqueta = labels.label_for(tipo, locale=idioma, ordinal=numero)
        texto = f"antes {etiqueta} despues"

        dicho = labels.replace_labels_with_spoken(texto, locale=idioma)

        palabra = labels.spoken_label_for(tipo, locale=idioma)
        assert dicho == f"antes {palabra} despues"


def test_una_etiqueta_del_otro_idioma_tambien_se_cambia() -> None:
    """El idioma de la llamada puede cambiar a mitad; lo ya escrito conserva su etiqueta."""
    en_espanol = labels.label_for(EntityType.PERSON, locale="es", ordinal=1)

    dicho = labels.replace_labels_with_spoken(f"Hola {en_espanol}.", locale="en")

    assert dicho == f"Hola {labels.spoken_label_for(EntityType.PERSON, locale='en')}."


def test_un_texto_sin_etiquetas_no_cambia() -> None:
    texto = "Tu placa [ABC] y la linea 3 [del reporte] siguen igual."

    assert labels.replace_labels_with_spoken(texto, locale="es") == texto


def test_varias_etiquetas_en_un_mismo_texto_se_cambian_todas() -> None:
    nombre = labels.label_for(EntityType.PERSON, locale="en", ordinal=1)
    lugar = labels.label_for(EntityType.LOCATION, locale="en", ordinal=1)
    otro = labels.label_for(EntityType.PERSON, locale="en", ordinal=2)

    dicho = labels.replace_labels_with_spoken(f"{nombre} fue a {lugar} con {otro}", locale="en")

    assert dicho == "that name fue a that place con that name"
    assert "[" not in dicho
