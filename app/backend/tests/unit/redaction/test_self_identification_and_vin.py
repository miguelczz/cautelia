"""Dos fugas que encontro U7 al pasar sus valores sembrados por la redaccion (NFR11.10).

**Primera fuga: el nombre que sigue a una frase de autoidentificacion.** "My name
is Megan Hughes." salia entero: `en_core_web_md` etiqueta ese nombre como
organizacion, y U3 solo tapa lo que el modelo llama persona. Lo mismo con un
nombre espanol dentro de una frase inglesa ("My name is Lucia Ochoa Henao."), que
el modelo ingles no reconoce, y con "Soy Rosa Iturbe", que salio en claro en los
turnos de los casos sembrados de U7. La regla de autoidentificacion no depende
del modelo: despues de una frase como "my name is" o "me llamo", la secuencia de
dos a cuatro palabras con mayuscula que sigue es un nombre.

**Segunda fuga: el VIN no tenia reconocedor.** La regla de respaldo solo tapaba la
tirada final de digitos, y el resto del numero de serie quedaba a la vista.

Las pruebas de este archivo se escribieron **antes** del arreglo y se vieron
fallar (disciplina de la rama evaluada: primero el caso, despues la conducta).

**Las dos negativas.** Ninguna de las dos reglas puede tragarse el nombre de una
aseguradora. U3 no conoce aseguradoras --`redact()` recibe texto e idioma, y un
identificador de aseguradora en este modulo seria una rama por aseguradora que
BR4.2 de U2 prohibe--, asi que la negativa no se decide con una lista de
aseguradoras sino con la estructura: una secuencia que contiene una palabra de
organizacion declarada en el archivo de reconocedores ("Auto", "Mutual",
"Insurance", "Seguros"...) no es el nombre de una persona. La prueba que recorre
los nombres visibles de **todas** las carpetas de `app/config/tenants/` es la
que vuelve comprobable "no se traga el nombre de una aseguradora conocida": la
aseguradora que se anada con un nombre sin palabra de organizacion hace fallar
esa prueba y obliga a decidirlo a la vista.

Se usan los modelos de verdad, como en `test_detector.py`: un doble no detecta
nada.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import yaml

from untangle import paths
from untangle.base import Locale
from untangle.compliance.redaction import api
from untangle.compliance.redaction import detector as deteccion
from untangle.compliance.redaction.recognizers import loading
from untangle.compliance.redaction.recognizers.models import (
    DetectedEntity,
    EntityType,
    SelfIdentificationRule,
)

IDIOMAS: tuple[Locale, ...] = ("es", "en")


@pytest.fixture(scope="module", autouse=True)
def _detector_cargado() -> Iterator[None]:
    """El detector real, una vez para el modulo, y nunca compartido con otro."""
    deteccion.install(deteccion.load())
    yield
    deteccion.reset()


def _cubierto_por(texto: str, valor: str, hallazgos: tuple[DetectedEntity, ...], tipo: str) -> bool:
    """Si un solo hallazgo del tipo pedido cubre el valor entero."""
    inicio = texto.index(valor)
    fin = inicio + len(valor)
    return any(
        h.entity_type.value == tipo and h.start <= inicio and fin <= h.end for h in hallazgos
    )


# --- Primera fuga: el nombre despues de la frase de autoidentificacion --------

NOMBRES_TRAS_LA_FRASE = [
    pytest.param("My name is Megan Hughes.", "Megan Hughes", id="en-cue-en-name"),
    pytest.param("My name is Lucía Ochoa Henao.", "Lucía Ochoa Henao", id="en-cue-es-name"),
    pytest.param("Me llamo Megan Hughes.", "Megan Hughes", id="es-cue-en-name"),
    pytest.param(
        "Buenos días, quiero reportar un choque. Soy Rosa Iturbe, póliza POL-32.",
        "Rosa Iturbe",
        id="es-soy-caso-sembrado",
    ),
]


@pytest.mark.parametrize("turno", IDIOMAS)
@pytest.mark.parametrize(("texto", "nombre"), NOMBRES_TRAS_LA_FRASE)
def test_el_nombre_tras_la_frase_de_autoidentificacion_se_tapa_como_nombre(
    texto: str, nombre: str, turno: Locale
) -> None:
    """El nombre entero queda dentro de un hallazgo de persona, en los dos turnos.

    En los dos turnos y no solo en el del idioma de la frase: dictar el nombre en
    el otro idioma no puede ser la via para sacarlo en claro, que es la misma
    compuerta de RT-15 aplicada a los nombres.
    """
    hallazgos = deteccion.get_detector().detect(texto, language=turno)

    assert _cubierto_por(texto, nombre, hallazgos, "person"), (
        f"ningun hallazgo de persona cubre el nombre entero en el turno '{turno}'"
    )


@pytest.mark.parametrize("turno", IDIOMAS)
@pytest.mark.parametrize(("texto", "nombre"), NOMBRES_TRAS_LA_FRASE)
def test_ninguna_palabra_del_nombre_sobrevive_a_la_redaccion(
    texto: str, nombre: str, turno: Locale
) -> None:
    """Lo que protege a la persona: ni el nombre ni ninguno de sus apellidos."""
    redactado = api.redact(texto, language=turno)

    visibles = [palabra for palabra in nombre.split() if palabra in redactado]
    assert visibles == [], f"{len(visibles)} palabra(s) del nombre siguen a la vista"


# --- Segunda fuga: el VIN -----------------------------------------------------

#: VIN ficticios del generador de U7: su digito de control falla a proposito, asi
#: que no son el numero de serie de ningun vehiculo (BR7.1 de U7).
VIN_EN = "52C8TUBCXZK651434"
VIN_ES = "9SCC4G1E9Z6423858"

VIN_EN_TEXTOS = [
    pytest.param(f"The VIN of my car is {VIN_EN}.", VIN_EN, id="en-compact"),
    pytest.param(
        "The VIN is 52C-8TUBCX-ZK651434, from the registration.",
        "52C-8TUBCX-ZK651434",
        id="en-separated",
    ),
    pytest.param(
        "The VIN is five two C eight T U B C X Z K six five one four three four.",
        "five two C eight T U B C X Z K six five one four three four",
        id="en-spoken",
    ),
]
VIN_ES_TEXTOS = [
    pytest.param(f"El VIN de mi carro es {VIN_ES}.", VIN_ES, id="es-compact"),
    pytest.param(
        "El VIN es 9SC C4G1E9 Z6423858, de la tarjeta.", "9SC C4G1E9 Z6423858", id="es-separated"
    ),
    pytest.param(
        "El VIN es nueve S C C cuatro G uno E nueve Z seis cuatro dos tres ocho cinco ocho.",
        "nueve S C C cuatro G uno E nueve Z seis cuatro dos tres ocho cinco ocho",
        id="es-spoken",
    ),
]


@pytest.mark.parametrize("turno", IDIOMAS)
@pytest.mark.parametrize(("texto", "vin"), [*VIN_EN_TEXTOS, *VIN_ES_TEXTOS])
def test_el_vin_se_tapa_entero_como_vin(texto: str, vin: str, turno: Locale) -> None:
    """Diecisiete caracteres sin I, O ni Q, en sus tres formas y en los dos turnos.

    Entero: tapar solo la cola de digitos deja a la vista el fabricante, el
    modelo y el ano, que junto con la placa identifican el vehiculo.
    """
    hallazgos = deteccion.get_detector().detect(texto, language=turno)

    assert _cubierto_por(texto, vin, hallazgos, "vin"), (
        f"ningun hallazgo de VIN cubre el VIN entero en el turno '{turno}'"
    )


@pytest.mark.parametrize("turno", IDIOMAS)
@pytest.mark.parametrize(("texto", "vin"), [*VIN_EN_TEXTOS[:2], *VIN_ES_TEXTOS[:2]])
def test_ningun_trozo_del_vin_sobrevive_a_la_redaccion(texto: str, vin: str, turno: Locale) -> None:
    """Ni el numero entero ni ninguno de sus grupos."""
    redactado = api.redact(texto, language=turno)

    trozos = [trozo for trozo in vin.replace("-", " ").split() if trozo in redactado]
    assert trozos == [], f"{len(trozos)} trozo(s) del VIN siguen a la vista"


# --- Las negativas: el nombre de la aseguradora se queda ----------------------

NEGATIVAS = [
    pytest.param("This is Autos Poblado calling about your claim.", "Autos Poblado", id="en"),
    pytest.param("Le habla Seguros Aburrá sobre su reclamación.", "Seguros Aburrá", id="es"),
]


@pytest.mark.parametrize("turno", IDIOMAS)
@pytest.mark.parametrize(("texto", "aseguradora"), NEGATIVAS)
def test_la_frase_de_autoidentificacion_no_se_traga_el_nombre_de_la_aseguradora(
    texto: str, aseguradora: str, turno: Locale
) -> None:
    """ "This is" y "le habla" son frases de autoidentificacion, y lo que las sigue
    aqui es una aseguradora, no una persona. Taparla dejaria la transcripcion sin
    decir quien llamaba, sin proteger a nadie."""
    assert aseguradora in api.redact(texto, language=turno)


def _nombres_visibles_de_las_aseguradoras() -> list[str]:
    """Los nombres visibles de todas las carpetas de aseguradora que existen.

    Se leen de las carpetas y no de una lista escrita aqui: la aseguradora que se
    anada queda cubierta sin tocar esta prueba.
    """
    nombres = []
    for archivo in sorted((paths.repo_root() / "app" / "config" / "tenants").glob("*/tenant.yaml")):
        datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
        nombres.append(str(datos["display_name"]))
    return nombres


PLANTILLAS = {
    "en": "This is {} calling about your claim.",
    "es": "Le habla {} sobre su reclamación.",
}


def test_hay_aseguradoras_que_recorrer() -> None:
    """Sin esto, la prueba de abajo pasaria sin recorrer ninguna."""
    assert len(_nombres_visibles_de_las_aseguradoras()) >= 3


@pytest.mark.parametrize("turno", IDIOMAS)
@pytest.mark.parametrize("plantilla", sorted(PLANTILLAS))
def test_ninguna_aseguradora_conocida_se_tapa_como_nombre(plantilla: str, turno: Locale) -> None:
    """El nombre visible de cada aseguradora sobrevive a la frase de autoidentificacion.

    Con su control positivo en la misma plantilla: un nombre de persona **si** se
    tapa. Sin el control, esta prueba pasaria igual con la regla de
    autoidentificacion rota o ausente, que es la forma de pasar que la practica
    del equipo prohibe.
    """
    control = PLANTILLAS[plantilla].format("Derek Warren")
    assert "Warren" not in api.redact(control, language=turno)

    tragadas = [
        nombre
        for nombre in _nombres_visibles_de_las_aseguradoras()
        if nombre not in api.redact(PLANTILLAS[plantilla].format(nombre), language=turno)
    ]
    assert tragadas == [], f"se taparon como nombre: {tragadas}"


# --- La regla por dentro (capa de deteccion, escrita tras el arreglo) ---------


def _reglas() -> list[pytest.param]:  # type: ignore[valid-type]
    juegos = loading.load_all()
    return [
        pytest.param(juegos[idioma].self_identification, frase, id=f"{idioma}/{frase}")
        for idioma in IDIOMAS
        for frase in juegos[idioma].self_identification.cues
    ]


@pytest.mark.parametrize(("regla", "frase"), _reglas())
def test_cada_frase_declarada_anuncia_el_nombre_que_la_sigue(
    regla: SelfIdentificationRule, frase: str
) -> None:
    """Una prueba por frase y no "con una frase cualquiera": la que se olvide sera
    justo la que no estaba cubierta."""
    texto = f"Hola, {frase} Derek Warren, llamo por el choque."

    hallazgos = deteccion.self_identification_findings(texto, regla)

    assert [texto[h.start : h.end] for h in hallazgos] == ["Derek Warren"]
    assert all(h.recognizer_id == regla.id for h in hallazgos)


@pytest.mark.parametrize(
    ("texto", "tapado"),
    [
        pytest.param(
            "I\u2019m Megan Hughes, the insured.", "Megan Hughes", id="apostrofo-tipografico"
        ),
        pytest.param("MY NAME IS MEGAN HUGHES.", "MEGAN HUGHES", id="todo-en-mayusculas"),
        pytest.param("I am Lucía Ochoa-Henao.", "Lucía Ochoa-Henao", id="apellido-compuesto"),
        pytest.param(
            "I am Ana María López García.", "Ana María López García", id="cuatro-palabras"
        ),
    ],
)
def test_la_regla_tapa_el_nombre_en_sus_variantes(texto: str, tapado: str) -> None:
    regla = loading.load_recognizer_set("en").self_identification

    hallazgos = deteccion.self_identification_findings(texto, regla)

    assert [texto[h.start : h.end] for h in hallazgos] == [tapado]


@pytest.mark.parametrize(
    "texto",
    [
        pytest.param("I am Derek, the insured.", id="una-sola-palabra"),
        pytest.param("I am Very Sorry To Bother You Today.", id="mas-de-cuatro-palabras"),
        pytest.param("I am from the north side.", id="sin-mayuscula"),
        # Con una palabra de organizacion **del juego ingles**, que es el que se
        # carga aqui: esta prueba mira la regla en aislamiento, y en produccion el
        # detector le pasa las palabras de los dos idiomas. El renombrado de las
        # aseguradoras del 2026-10-03 puso aqui un nombre espanol y la prueba cayo
        # diciendo la verdad: "seguros" no esta en la lista inglesa.
        pytest.param("I am Ridgeway Mutual's claims desk.", id="organizacion"),
        pytest.param("Diam Derek Warren Foster.", id="la-frase-pegada-a-otra-palabra"),
    ],
)
def test_lo_que_la_regla_no_toma_por_nombre(texto: str) -> None:
    """Cada limite de la regla, con su razon en la docstring de la funcion.

    Una sola palabra es demasiado a menudo otra cosa; mas de cuatro es un titulo;
    sin mayuscula no hay secuencia; con una palabra de organizacion es una
    empresa; y una frase pegada a otra palabra no es la frase.
    """
    regla = loading.load_recognizer_set("en").self_identification

    assert deteccion.self_identification_findings(texto, regla) == ()


def test_la_palabra_de_organizacion_se_compara_sin_tildes_ni_mayusculas() -> None:
    """ "Compañía" y "COMPANIA" son la misma palabra declarada."""
    regla = loading.load_recognizer_set("es").self_identification

    for texto in ("Le habla Compañía Andina.", "Le habla COMPANIA ANDINA."):
        assert deteccion.self_identification_findings(texto, regla) == ()


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_el_numero_no_se_normaliza_y_por_eso_el_plural_esta_declarado(idioma: Locale) -> None:
    """La comparacion normaliza tildes y mayusculas, **no el numero** (2026-10-03).

    La lista traia `auto` y no `autos`, asi que "Autos Poblado" no cruzaba ninguna
    palabra de organizacion y la regla lo tapaba entero como nombre de persona. Que
    faltara era un olvido y no una decision: la misma lista ya trae `seguros` y
    `servicios` en plural.

    Esta prueba fija el plural en los dos juegos. Sin ella, quitarlo dejaria a una
    aseguradora presentandose como "[NOMBRE 1]" y nada se pondria rojo hasta que
    alguien escuchara la apertura.
    """
    regla = loading.load_recognizer_set(idioma).self_identification
    singular, plural = "Le habla Auto Poblado.", "Le habla Autos Poblado."

    assert deteccion.self_identification_findings(singular, regla) == ()
    assert deteccion.self_identification_findings(plural, regla) == ()


def test_cuando_el_modelo_y_la_regla_encuentran_lo_mismo_el_credito_es_del_modelo() -> None:
    """La fila del modelo en el informe tiene que seguir diciendo si el modelo
    funciona: si la regla se llevara el credito de lo que el modelo tambien vio,
    un modelo que dejara de reconocer nombres no se notaria."""
    texto = "Hi, I am Derek Warren."

    def _persona(quien: str, confianza: float) -> DetectedEntity:
        return DetectedEntity(
            entity_type=EntityType.PERSON,
            start=9,
            end=21,
            recognizer_id=quien,
            confidence=confianza,
        )

    resueltos = deteccion.resolve_overlaps(
        texto,
        [
            _persona("en-person-cue", deteccion.CONFIANZA_DE_AUTOIDENTIFICACION),
            _persona("en-person", 0.85),
        ],
        turno="en",
    )

    assert [h.recognizer_id for h in resueltos] == ["en-person"]


def test_el_informe_da_su_fila_a_la_regla_y_no_la_suma_al_respaldo() -> None:
    """La fila en cero existe aunque no encuentre nada, y lo que encuentra cuenta
    como nombre --no como dato sin clasificar-- en la fila de la regla."""
    informe = api.redaction_report("My name is Megan Hughes.", language="en")

    assert {"en-person-cue", "es-person-cue"} <= set(informe.counts_by_recognizer)
    assert informe.counts_by_recognizer["en-person-cue"] == 1
    assert informe.counts_by_recognizer["es-person-cue"] == 0
    assert informe.counts_by_type[EntityType.PERSON] == 1
    assert informe.fallback_count == 0


@pytest.mark.parametrize(
    "texto",
    [
        pytest.param("Mi cuenta es 12345678901234567.", id="diecisiete-digitos"),
        pytest.param("The code is ABCDEFGHJKLMNPRST.", id="diecisiete-letras"),
        pytest.param("The VIN is 52C8TUBCXZK65143.", id="dieciseis"),
        pytest.param("The VIN is 52C8TUBCXZK6514344.", id="dieciocho"),
        pytest.param("The VIN is 52C8TUBCXZO651434.", id="con-o"),
    ],
)
def test_lo_que_no_es_un_vin(texto: str) -> None:
    """Diecisiete caracteres, sin I, O ni Q, con letras y digitos. Lo demas no es
    un VIN, y etiquetarlo como tal mentiria sobre lo que se tapo."""
    hallazgos = deteccion.get_detector().detect(texto, language="en")

    assert not any(h.entity_type is EntityType.VIN for h in hallazgos)


def test_un_vin_en_minusculas_tambien_se_tapa() -> None:
    """Quien lo teclea en un chat no siempre pone mayusculas."""
    texto = f"my vin is {VIN_EN.lower()} thanks"

    hallazgos = deteccion.get_detector().detect(texto, language="en")

    assert _cubierto_por(texto, VIN_EN.lower(), hallazgos, "vin")
