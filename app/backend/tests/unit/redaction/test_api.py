"""La superficie: que devuelve `redact`, y que hace cuando no puede (C-13).

Lo que aqui se protege es **fallar cerrado**. Un detector roto que devolviera el
texto tal cual no romperia ninguna pantalla ni levantaria ningun error: seguiria
saliendo texto, solo que con el dato dentro. Por eso las pruebas de abajo rompen
la carga a proposito y **exigen silencio**.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from untangle.compliance.redaction import api, sinks
from untangle.compliance.redaction import detector as deteccion
from untangle.compliance.redaction.recognizers import loading
from untangle.compliance.redaction.recognizers.models import EntityType
from untangle.copy_catalog import api as copy_api


@pytest.fixture(scope="session", autouse=True)
def _detector_cargado() -> Iterator[None]:
    """Un detector para toda la sesion; las pruebas que lo rompen lo restauran."""
    deteccion.install(deteccion.load())
    yield
    deteccion.reset()


@pytest.fixture
def _restaurar_detector() -> Iterator[None]:
    """Devuelve el detector del proceso despues de una prueba que lo rompe."""
    anterior = deteccion.get_detector()
    yield
    deteccion.install(anterior)


# --- Lo que devuelve (C-13, AC4.12.1) -----------------------------------------


def test_redact_devuelve_el_texto_con_las_etiquetas_en_su_sitio() -> None:
    texto = "Mi telefono es 3005551234 y la placa es ABC123."

    redactado = api.redact(texto, language="es")

    assert "3005551234" not in redactado
    assert "ABC123" not in redactado
    assert redactado.startswith("Mi telefono es ")
    assert redactado.endswith(".")


def test_redact_respeta_el_texto_que_no_tapa() -> None:
    """Sustituir a mano sobre indices es donde se cuelan los errores de un
    caracter, y aqui un caracter de mas deja medio dato a la vista."""
    texto = "Buenas, ayer me chocaron el carro cuando salia del trabajo."

    assert api.redact(texto, language="es") == texto


def test_un_texto_vacio_no_rompe_nada() -> None:
    """La transcripcion en vivo llama con la frase todavia vacia en cada
    fragmento que no cierra ninguna: si esto levantara, la consola se caeria en
    el primer fragmento de cada frase."""
    assert api.redact("", language="es") == ""


def test_la_etiqueta_sale_en_el_idioma_de_la_conversacion() -> None:
    texto = "Mi telefono es 3005551234."

    assert api.redact(texto, language="es") != api.redact(texto, language="en")


# --- El informe (C-13, BR4.1, BR4.2) ------------------------------------------


def test_el_informe_declara_todos_los_tipos_aunque_esten_en_cero() -> None:
    """Un tipo **ausente** del informe y un tipo con cero hallazgos son cosas
    distintas: confundirlas esconde un reconocedor que dejo de cargar."""
    informe = api.redaction_report("Mi telefono es 3005551234.", language="es")

    assert set(informe.counts_by_type) == set(EntityType)
    assert informe.counts_by_type[EntityType.PHONE] == 1
    assert informe.counts_by_type[EntityType.EMAIL] == 0


def test_el_informe_declara_todos_los_reconocedores_de_los_dos_idiomas() -> None:
    """La fila que desaparece es la senal de que un reconocedor dejo de cargar."""
    informe = api.redaction_report("Mi telefono es 3005551234.", language="es")

    declarados = {
        reconocedor.id for juego in loading.load_all().values() for reconocedor in juego.recognizers
    }

    assert declarados <= set(informe.counts_by_recognizer)
    assert informe.counts_by_recognizer["es-phone"] == 1


def test_la_cifra_del_respaldo_va_aparte_y_no_se_suma_a_ningun_tipo() -> None:
    """BR4.2: un respaldo que dispara mucho es la senal de que un reconocedor se
    rompio, y sumarlo a su tipo borraria justo esa senal."""
    informe = api.redaction_report(
        "Mi numero de expediente interno es 4471903388221 en el sistema viejo.",
        language="es",
    )

    assert informe.fallback_count >= 1
    assert informe.counts_by_type[EntityType.UNCLASSIFIED] == informe.fallback_count
    assert informe.counts_by_type[EntityType.PHONE] == 0


def test_el_informe_y_el_texto_redactado_cuentan_lo_mismo() -> None:
    """Las cifras salen de **la misma lista de hallazgos**, agrupada dos veces
    (SEC-U3.9). Dos recuentos independientes podrian divergir, y el dia que
    divergieran nadie sabria cual creer."""
    texto = "Mi telefono es 3005551234, el del testigo 3005559999, placa ABC123."

    informe = api.redaction_report(texto, language="es")

    assert sum(informe.counts_by_type.values()) == sum(informe.counts_by_recognizer.values())
    assert informe.total == 3


def test_el_informe_no_se_publica_como_promedio_de_los_dos_idiomas() -> None:
    """P12: el informe lleva **su** idioma, y quien lo publica no tiene forma de
    combinarlos sin decir cual es cual."""
    assert api.redaction_report("hola", language="es").language == "es"
    assert api.redaction_report("hello", language="en").language == "en"


# --- Fallar cerrado (BR1.7, SEC-U3.10, Flujo 4) -------------------------------


def test_si_el_detector_falla_redact_levanta_en_vez_de_devolver_texto(
    monkeypatch: pytest.MonkeyPatch, _restaurar_detector: None
) -> None:
    """No existe ninguna ruta en la que un fallo produzca texto sin tapar.

    Se rompe la carga a proposito y se **exige silencio**: si `redact` devolviera
    el texto de entrada, el fallo del detector se convertiria en una fuga que no
    avisa.
    """

    def _romper(*_: object, **__: object) -> None:
        msg = "el detector esta roto a proposito"
        raise deteccion.DetectionError(msg)

    monkeypatch.setattr(deteccion.Detector, "detect", _romper)

    with pytest.raises(api.RedactionFailedError):
        api.redact("Mi telefono es 3005551234.", language="es")


def test_el_informe_tambien_levanta_cuando_el_detector_falla(
    monkeypatch: pytest.MonkeyPatch, _restaurar_detector: None
) -> None:
    """Un informe que se produjera con el detector roto publicaria ceros, y un
    cero sin hallazgos y un cero por no haber mirado son cosas distintas."""

    def _romper(*_: object, **__: object) -> None:
        msg = "el detector esta roto a proposito"
        raise deteccion.DetectionError(msg)

    monkeypatch.setattr(deteccion.Detector, "detect", _romper)

    with pytest.raises(api.RedactionFailedError):
        api.redaction_report("Mi telefono es 3005551234.", language="es")


def test_el_error_no_lleva_el_texto_que_iba_a_tapar(
    monkeypatch: pytest.MonkeyPatch, _restaurar_detector: None
) -> None:
    """Un error de la redaccion que imprimiera lo que iba a tapar convertiria el
    camino de fallo en el punto de fuga que la unidad evita."""

    def _romper(*_: object, **__: object) -> None:
        msg = "el detector esta roto a proposito"
        raise deteccion.DetectionError(msg)

    monkeypatch.setattr(deteccion.Detector, "detect", _romper)

    with pytest.raises(api.RedactionFailedError) as error:
        api.redact("Mi telefono es 3005551234.", language="es")

    assert "3005551234" not in str(error.value)


def test_el_punto_de_salida_tiene_su_clave_de_degradacion() -> None:
    """Fallar cerrado no es quedarse mudo: el punto de salida responde con la
    frase del catalogo, en el idioma de la conversacion (BR1.7, Flujo 4)."""
    copy_api.reset()
    try:
        for idioma in ("es", "en"):
            frase = copy_api.t(sinks.DEGRADED_COPY_KEY, locale=idioma)
            assert frase != sinks.DEGRADED_COPY_KEY
            assert frase.strip()
    finally:
        copy_api.reset()


# --- El registro de puntos de salida (BR1.3, AC4.12.2) ------------------------


def test_los_seis_puntos_de_salida_estan_declarados_una_sola_vez() -> None:
    assert len(sinks.SINKS) == 6
    assert len(sinks.declared_names()) == 6


def test_cada_superficie_tiene_al_menos_un_punto_de_salida_declarado() -> None:
    """Una superficie sin punto declarado es una por la que sale texto y nadie
    responde por el."""
    for superficie in sinks.Surface:
        assert sinks.by_surface(superficie), superficie.value


def test_cada_punto_de_salida_declara_su_unidad_duena() -> None:
    """U3 declara la lista; cada unidad duena implementa el suyo exigiendo
    `Redacted`. Sin el dueno escrito, el dia que uno falle nadie sabe a quien le
    toca."""
    for sink in sinks.SINKS:
        assert sink.owning_unit.startswith("U")
        assert sink.writes.strip()


# --- La frase del catalogo (U18) ----------------------------------------------
# Lo que aqui se protege son dos cosas a la vez, y la segunda es la que importa:
# que la frase que escribimos nosotros salga entera, y que lo que se mete dentro
# de ella siga tapandose. Sin la segunda, esto seria una puerta de salida sin
# redaccion con otro nombre.


def test_la_frase_del_catalogo_sale_entera() -> None:
    """El caso que lo motivo, con la frase exacta que se danaba.

    En espanol el detector etiquetaba "Puedo" como nombre de persona, asi que la
    agente se presentaba diciendo "[NOMBRE 1] ayudarle a reportar un siniestro".
    Siete frases asi en espanol y ninguna en ingles.
    """
    frase = "Puedo ayudarle a reportar un siniestro o a resolver dudas sobre su poliza."

    assert str(api.from_catalog(frase, language="es")) == frase


def test_lo_que_se_mete_en_la_frase_si_se_tapa() -> None:
    """La otra mitad, y sin ella esto no seria una redaccion sino un puente.

    El hueco es donde entra el texto de fuera --el nombre de quien llama, el
    comentario de una ajustadora-- y ahi el detector si tiene que correr.
    """
    resultado = str(
        api.from_catalog(
            "Para cerrar: {resumen}. ¿Es correcto?", language="es", resumen="Soy Marcela Rios"
        )
    )

    assert "Marcela Rios" not in resultado
    assert "Para cerrar:" in resultado
    assert "¿Es correcto?" in resultado


def test_un_hueco_sin_valor_sale_a_la_vista_y_eso_esta_escrito() -> None:
    """Lo que esto **no** atrapa, dicho en una prueba para que nadie lo suponga.

    Una frase con huecos a la que nadie le paso ninguno sale con el `{hueco}`
    visible, igual que la saca el catalogo hoy. Es un defecto que se oye, no una
    fuga. La alternativa --llamar a `format` siempre-- haria levantar la llamada
    ante una llave escrita dentro del comentario de una ajustadora, y una llave en
    un comentario no puede tumbar una llamada.
    """
    assert str(api.from_catalog("Su caso es {numero}.", language="es")) == "Su caso es {numero}."


def test_una_llave_en_un_texto_sin_huecos_no_rompe_nada() -> None:
    """El caso real que decidio lo de arriba: la oferta de retomar junta la frase
    del catalogo con el comentario de quien decidio, y ese comentario lo escribio
    una persona."""
    texto = "Su caso fue aprobado. Nota de quien decidio: revisar {monto} con el taller."

    assert str(api.from_catalog(texto, language="es")) == texto


def test_si_el_detector_falla_la_frase_con_huecos_no_sale(
    monkeypatch: pytest.MonkeyPatch, _restaurar_detector: None
) -> None:
    """Falla cerrado igual que `redact`: si tapar el valor no se puede, no sale
    texto. La frase **sin** huecos si sale, y eso es lo que esta funcion existe para
    conseguir: no habia nada que tapar."""

    def _romper(*_: object, **__: object) -> None:
        msg = "el detector esta roto a proposito"
        raise deteccion.DetectionError(msg)

    monkeypatch.setattr(deteccion.Detector, "detect", _romper)

    assert str(api.from_catalog("Su caso quedo registrado.", language="es")) == (
        "Su caso quedo registrado."
    )
    with pytest.raises(api.RedactionFailedError):
        api.from_catalog("Para cerrar: {resumen}.", language="es", resumen="Soy Marcela Rios")
