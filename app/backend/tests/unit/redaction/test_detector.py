"""El detector: los cuatro tipos, las tres formas, el turno mixto y el solape.

**Los modelos no se simulan.** Lo que se prueba es que detecta el detector, y un
doble no detecta nada: una prueba con un detector falso pasaria con la redaccion
rota, que es exactamente el fallo que esta unidad existe para impedir.

El detector se construye **una vez para toda la sesion**. Cargar los dos modelos
en cada prueba multiplicaria la corrida por el numero de pruebas sin comprobar
nada nuevo; lo que si se comprueba aparte es que la carga falla cuando falta un
modelo.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from untangle import paths
from untangle.compliance.redaction import detector as deteccion
from untangle.compliance.redaction.recognizers.models import (
    DetectedEntity,
    EntityType,
)
from untangle.evals.redaction_fixtures import Seed, load_fixtures

IDIOMAS = ("es", "en")


@pytest.fixture(scope="session")
def detector() -> deteccion.Detector:
    """El detector real, con los dos modelos residentes."""
    return deteccion.load()


def _semillas(seccion: str) -> list[pytest.param]:  # type: ignore[valid-type]
    casos = []
    for idioma in IDIOMAS:
        fixtures = load_fixtures(idioma, paths.repo_root())  # type: ignore[arg-type]
        for seed in getattr(fixtures, seccion):
            casos.append(pytest.param(idioma, seed, id=f"{idioma}/{seed.id}"))
    return casos


@pytest.fixture(autouse=True)
def _sin_detector_compartido() -> Iterator[None]:
    """Ninguna prueba deja instalado un detector para la siguiente."""
    yield
    deteccion.reset()


# --- Los cuatro tipos, los dos idiomas, las tres formas (AC4.13.1, AC4.13.2) --


@pytest.mark.parametrize(("idioma", "semilla"), _semillas("seeds"))
def test_cada_semilla_se_detecta_con_su_tipo(
    idioma: str, semilla: Seed, detector: deteccion.Detector
) -> None:
    """Los cuatro tipos propios, en sus tres formas de escritura.

    Es la meta de NFR11.1: 100 % sobre **casos sembrados**, que no es una meta de
    deteccion en texto libre. Un reconocedor que falle en su propio caso sembrado
    esta roto, no imperfecto.
    """
    hallazgos = detector.detect(semilla.text, language=idioma)  # type: ignore[arg-type]

    tipos = {h.entity_type for h in hallazgos}
    assert semilla.entity_type in tipos, (
        f"{semilla.id}: se detectaron {sorted(t.value for t in tipos)}"
    )


@pytest.mark.parametrize(("idioma", "semilla"), _semillas("seeds"))
def test_ninguna_semilla_queda_fuera_de_un_hallazgo(
    idioma: str, semilla: Seed, detector: deteccion.Detector
) -> None:
    """El valor sembrado esta **entero** dentro de algun hallazgo.

    Detectar el tipo no basta: un hallazgo que cubriera medio telefono dejaria la
    otra mitad a la vista y la medicion por tipo seguiria diciendo que ese tipo
    se detecto.
    """
    hallazgos = detector.detect(semilla.text, language=idioma)  # type: ignore[arg-type]

    cubierto = any(
        semilla.value in semilla.text[h.start : h.end]
        for h in hallazgos
        if h.entity_type is semilla.entity_type
    )

    assert cubierto, f"{semilla.id}: ningun hallazgo de su tipo contiene el valor sembrado"


# --- El turno mixto: RT-15 (AC4.13.4, BR2.3, BR2.9) ---------------------------


@pytest.mark.parametrize(("idioma", "semilla"), _semillas("cross_language"))
def test_el_dato_dictado_en_el_otro_idioma_se_tapa_igual(
    idioma: str, semilla: Seed, detector: deteccion.Detector
) -> None:
    """Cambiar de idioma no es una via para sacar un dato en claro.

    Es la unica compuerta dura del grupo 2 y la que mas veces se rompe en un
    detector real, porque casi todos se configuran por idioma y se prueban con
    texto de un solo idioma.
    """
    hallazgos = detector.detect(semilla.text, language=idioma)  # type: ignore[arg-type]

    assert any(
        h.entity_type is semilla.entity_type and semilla.value in semilla.text[h.start : h.end]
        for h in hallazgos
    )


@pytest.mark.parametrize(("idioma", "semilla"), _semillas("cross_language"))
def test_el_hallazgo_se_atribuye_al_juego_que_lo_encontro(
    idioma: str, semilla: Seed, detector: deteccion.Detector
) -> None:
    """BR2.9, la mitad que la revision anadio.

    Si el hallazgo se atribuyera al idioma del turno, la medicion diria que ese
    idioma funciona cuando quien atrapo el dato fue el otro juego, y un
    reconocedor roto quedaria escondido detras del otro durante semanas.
    """
    hallazgos = detector.detect(semilla.text, language=idioma)  # type: ignore[arg-type]

    del_dato = [
        h
        for h in hallazgos
        if h.entity_type is semilla.entity_type and semilla.value in semilla.text[h.start : h.end]
    ]

    assert del_dato
    assert all(h.recognizer_id.startswith(f"{semilla.found_by_language}-") for h in del_dato), (
        f"{semilla.id}: atribuido a {[h.recognizer_id for h in del_dato]}, "
        f"y lo encontro el juego '{semilla.found_by_language}'"
    )


def test_los_dos_juegos_corren_aunque_el_turno_sea_de_uno_solo(
    detector: deteccion.Detector,
) -> None:
    """El mismo texto, leido como turno espanol y como turno ingles.

    Un detector que cargara solo el juego del turno daria resultados distintos
    segun como se lea el turno, y esa diferencia es el agujero de RT-15.
    """
    texto = "Mi cedula es siete nueve uno dos tres cuatro cinco seis, gracias."

    como_espanol = detector.detect(texto, language="es")
    como_ingles = detector.detect(texto, language="en")

    tipos_es = {h.entity_type for h in como_espanol}
    tipos_en = {h.entity_type for h in como_ingles}
    assert EntityType.NATIONAL_ID in tipos_es
    assert EntityType.NATIONAL_ID in tipos_en


# --- El solape (decision FD-U3-5, paso 20) ------------------------------------


def test_el_respaldo_nunca_gana_un_solape() -> None:
    """Una poliza dentro de una tirada que el respaldo tambien reclamo.

    Sin esta regla se etiquetaria como dato sin clasificar y la medicion por tipo
    perderia un acierto real, justo en el tipo que si sabemos identificar.
    """
    texto = "mi numero es 2003410000 y ya"
    poliza = DetectedEntity(
        entity_type=EntityType.POLICY_NUMBER,
        start=13,
        end=19,
        recognizer_id="es-policy-number",
        confidence=0.85,
    )
    respaldo = DetectedEntity(
        entity_type=EntityType.UNCLASSIFIED,
        start=13,
        end=23,
        recognizer_id="es-fallback-context",
        confidence=0.4,
    )

    resueltos = deteccion.resolve_overlaps(texto, [respaldo, poliza], turno="es")

    tipos = {h.entity_type for h in resueltos}
    assert EntityType.POLICY_NUMBER in tipos


def test_lo_que_solo_reclamaba_el_perdedor_sigue_tapado() -> None:
    """El perdedor de un solape se queda con lo que sobra.

    Descartarlo entero dejaria a la vista los caracteres que solo el reclamaba:
    en el caso de arriba, los cuatro digitos que la poliza no cubria.
    """
    texto = "mi numero es 2003410000 y ya"
    poliza = DetectedEntity(
        entity_type=EntityType.POLICY_NUMBER,
        start=13,
        end=19,
        recognizer_id="es-policy-number",
        confidence=0.85,
    )
    respaldo = DetectedEntity(
        entity_type=EntityType.UNCLASSIFIED,
        start=13,
        end=23,
        recognizer_id="es-fallback-context",
        confidence=0.4,
    )

    resueltos = deteccion.resolve_overlaps(texto, [respaldo, poliza], turno="es")

    tapado = "".join(texto[h.start : h.end] for h in resueltos)
    assert "2003410000" == tapado


def test_el_hallazgo_del_idioma_del_turno_gana_el_empate() -> None:
    """Dos juegos encuentran el mismo trozo: el credito es del turno.

    Sin este escalon, un nombre espanol en un turno espanol se atribuiria al
    juego ingles solo porque `en-` va antes que `es-` en el alfabeto, y el
    informe por idioma diria que el espanol no encuentra nada (P12).
    """
    texto = "Hable con Carlos Mendoza ayer."

    def _persona(quien: str) -> DetectedEntity:
        return DetectedEntity(
            entity_type=EntityType.PERSON,
            start=10,
            end=24,
            recognizer_id=quien,
            confidence=0.85,
        )

    resueltos = deteccion.resolve_overlaps(
        texto, [_persona("en-person"), _persona("es-person")], turno="es"
    )

    assert [h.recognizer_id for h in resueltos] == ["es-person"]


def test_dos_hallazgos_del_mismo_tamano_los_gana_el_mas_especifico() -> None:
    """A igual tamano, gana el tipo propio del dominio sobre el del modelo."""
    texto = "El carro placa ABC123 quedo mal."

    def _hallazgo_en_la_placa(tipo: EntityType, quien: str) -> DetectedEntity:
        return DetectedEntity(
            entity_type=tipo, start=15, end=21, recognizer_id=quien, confidence=0.85
        )

    resueltos = deteccion.resolve_overlaps(
        texto,
        [
            _hallazgo_en_la_placa(EntityType.LOCATION, "es-location"),
            _hallazgo_en_la_placa(EntityType.LICENSE_PLATE, "es-license-plate"),
        ],
        turno="es",
    )

    assert [h.entity_type for h in resueltos] == [EntityType.LICENSE_PLATE]


# --- La regla de respaldo (BR2.5, SEC-U3.6) -----------------------------------


def test_el_respaldo_tapa_un_formato_inventado_junto_a_su_frase_de_contexto(
    detector: deteccion.Detector,
) -> None:
    """Cubre el formato que nadie previo, que es por donde se escapan las cosas."""
    texto = "Mi numero de expediente interno es 4471903388221 en el sistema viejo."

    hallazgos = detector.detect(texto, language="es")

    assert any(h.entity_type is EntityType.UNCLASSIFIED for h in hallazgos)


def test_el_respaldo_no_tapa_digitos_sin_frase_de_contexto(
    detector: deteccion.Detector,
) -> None:
    """Sin contexto declarado, una tirada de digitos no es un dato personal.

    Tapar toda tirada larga convertiria cualquier importe o fecha en un hallazgo,
    y la cifra del respaldo dejaria de servir como senal de reconocedor roto.
    """
    texto = "El taller cobro 1450000 pesos por la reparacion completa."

    hallazgos = detector.detect(texto, language="es")

    assert not any(h.entity_type is EntityType.UNCLASSIFIED for h in hallazgos)


# --- Lo que un hallazgo nunca lleva -------------------------------------------


def test_un_hallazgo_no_lleva_el_valor_que_encontro(detector: deteccion.Detector) -> None:
    """`DetectedEntity` lleva donde estaba y quien lo encontro, no que era.

    Un hallazgo que cargara su valor convertiria cualquier volcado de diagnostico
    --un log, un mensaje de excepcion-- en la fuga que este componente evita.
    """
    texto = "Mi celular es 3005551234 por si acaso."

    hallazgos = detector.detect(texto, language="es")

    assert hallazgos
    for hallazgo in hallazgos:
        serializado = hallazgo.model_dump_json()
        assert "3005551234" not in serializado
        assert set(hallazgo.model_dump()) == {
            "entity_type",
            "start",
            "end",
            "recognizer_id",
            "confidence",
        }


# --- Fallar cerrado (BR1.7, SEC-U3.10) ----------------------------------------


def test_un_idioma_sin_juego_cargado_levanta(detector: deteccion.Detector) -> None:
    """Fallar cerrado: no existe camino en que un fallo produzca texto sin tapar."""
    with pytest.raises(deteccion.DetectionError):
        detector.detect("cualquier cosa", language="pt")  # type: ignore[arg-type]


def test_si_falta_un_modelo_la_carga_falla_nombrandolo_y_nombrando_el_comando(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INF-U3-3: un `ImportError` de spaCy no le dice a nadie que hacer."""
    monkeypatch.setitem(deteccion.MODELOS, "es", "es_core_news_que_no_existe")

    with pytest.raises(deteccion.ModelsMissingError) as error:
        deteccion.load()

    assert "es_core_news_que_no_existe" in str(error.value)
    assert deteccion.COMANDO_DE_MODELOS in str(error.value)


def test_un_saludo_en_minuscula_no_es_un_nombre(detector: deteccion.Detector) -> None:
    """El reconocedor de voz transcribe en minuscula, y el modelo tomaba «hola»
    por persona: la consola mostraba «[NOMBRE 1] tuve un choque» (2026-10-07)."""
    for texto in ("hola tuve un choque en la calle diez", "hola hola", "¡hola!"):
        hallazgos = detector.detect(texto, language="es")
        assert [h for h in hallazgos if h.entity_type is EntityType.PERSON] == [], texto


def test_el_saludo_no_destapa_el_nombre_que_lo_sigue(detector: deteccion.Detector) -> None:
    """La lista descarta solo el tramo que es entero un saludo."""
    texto = "Hola, soy Valentina Restrepo Gil"
    hallazgos = detector.detect(texto, language="es")
    personas = [texto[h.start : h.end] for h in hallazgos if h.entity_type is EntityType.PERSON]
    assert any("Valentina" in p for p in personas), personas


# --- La primera palabra de una peticion no es un nombre (2026-10-12) ----------------
#
# «Queria saber si cubre los danos a terceros» se guardaba como «[NOMBRE 1] saber si
# cubre...»: el modelo toma por persona la forma verbal con que abre la frase, y la
# mayuscula inicial es lo unico en que se apoya. Se arregla la clase --una forma verbal
# que abre una peticion--, no la palabra, y sin soltar ningun nombre de verdad.


def _personas(detector: deteccion.Detector, texto: str, idioma: str) -> list[str]:
    hallazgos = detector.detect(texto, language=idioma)  # type: ignore[arg-type]
    return [texto[h.start : h.end] for h in hallazgos if h.entity_type is EntityType.PERSON]


@pytest.mark.parametrize(
    ("idioma", "texto"),
    [
        pytest.param("es", "Queria saber si cubre los daños a terceros", id="es-queria-sin-tilde"),
        pytest.param("es", "Quería saber si cubre los daños a terceros", id="es-queria-con-tilde"),
        pytest.param("es", "Necesito saber si me cubre un robo", id="es-necesito"),
        pytest.param("es", "Queria preguntar por mi poliza", id="es-queria-preguntar"),
        pytest.param("es", "Pregunto si cubre el granizo", id="es-pregunto-si"),
        pytest.param("es", "Hola. Queria saber si cubre el granizo", id="es-segunda-frase"),
        pytest.param("en", "Wanted to know if hail is covered", id="en-wanted-to"),
        pytest.param("en", "Need to report a crash", id="en-need-to"),
    ],
)
def test_la_forma_verbal_con_que_abre_una_peticion_no_es_un_nombre(
    detector: deteccion.Detector, idioma: str, texto: str
) -> None:
    assert _personas(detector, texto, idioma) == []


@pytest.mark.parametrize(
    ("idioma", "texto", "nombre"),
    [
        # Un nombre solo, el mas probable de tapar de menos: la respuesta a «¿como te llamas?».
        pytest.param("es", "Marcela", "Marcela", id="es-nombre-solo"),
        # Un nombre que ademas es un verbo («leo»), solo o seguido de otra cosa.
        pytest.param("es", "Leo", "Leo", id="es-leo-solo"),
        pytest.param("es", "Leo dice que me cubre", "Leo", id="es-leo-con-verbo-conjugado"),
        pytest.param("es", "Leo mi poliza y no entiendo", "Leo", id="es-leo-mi-poliza"),
        # El nombre al principio de la frase, seguido de un verbo conjugado.
        pytest.param("es", "Sofia quiere reportar un choque", "Sofia", id="es-nombre-y-verbo"),
        pytest.param("es", "Daniel llamo ayer por mi choque", "Daniel", id="es-daniel"),
        pytest.param(
            "es", "Marcela Rios necesita saber si cubre", "Marcela Rios", id="es-completo"
        ),
        pytest.param(
            "es", "Queria hablar con Carlos Ramirez", "Carlos Ramirez", id="es-otro-nombre"
        ),
        pytest.param("en", "Mark reported a crash", "Mark", id="en-mark"),
        pytest.param("en", "Daniel Foster here", "Daniel Foster", id="en-completo"),
    ],
)
def test_soltar_la_forma_verbal_no_suelta_ningun_nombre(
    detector: deteccion.Detector, idioma: str, texto: str, nombre: str
) -> None:
    """El control de lo de arriba: los nombres de verdad, solos o al inicio de la frase,
    siguen tapados. «Queria» deja de serlo pero «Carlos Ramirez», en la misma frase, no."""
    assert nombre in _personas(detector, texto, idioma), texto
