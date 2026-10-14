"""La capa de configuracion: que carga y que no (BR2.6, BR2.7, BR2.8).

Lo que estas pruebas protegen es que **un reconocedor a medias no cargue**. Es la
unidad cuyo fallo no se manifiesta: un reconocedor sin su tipo, o con su idioma
equivocado, deja de tapar lo suyo y no rompe ninguna pantalla ni levanta ningun
error. Sigue saliendo texto, solo que con el dato dentro.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from untangle.compliance.redaction.recognizers import loading
from untangle.compliance.redaction.recognizers.models import (
    FORMAT_TYPES,
    OWN_DOMAIN_TYPES,
    EntityType,
    FallbackRule,
    Mechanism,
    Recognizer,
    WritingForm,
)

#: Los cinco campos obligatorios de un reconocedor (BR2.6).
CAMPOS_OBLIGATORIOS = ("id", "entity_type", "language", "mechanism", "source")


def _juego_crudo(language: str) -> dict[str, Any]:
    """El archivo real del idioma, sin validar, para poder romperlo a proposito."""
    archivo = loading.recognizers_dir() / f"{language}.yaml"
    cargado: Any = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    assert isinstance(cargado, dict)
    return cargado


def _escribir(directorio: Path, language: str, datos: dict[str, Any]) -> None:
    (directorio / f"{language}.yaml").write_text(
        yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


# --- Lo que hay, que tiene que estar -----------------------------------------


@pytest.mark.parametrize("language", ["es", "en"])
def test_cada_idioma_declara_sus_tipos_por_formato(language: str) -> None:
    """Placa, cedula, telefono y poliza (BR2.1, AC4.13.1), y el VIN, en los dos idiomas.

    Si a un idioma le faltara uno, ese tipo saldria en claro en ese idioma y la
    medicion por tipo lo diria solo si alguien la mira: no hay pantalla que se
    rompa. El conjunto es exacto: un tipo por formato de mas o de menos falla.
    El VIN entro cuando U7 encontro que salia con solo la cola tapada (NFR11.10);
    los cuatro de NFR11.1 siguen dentro.
    """
    juego = loading.load_recognizer_set(language)  # type: ignore[arg-type]

    propios = {r.entity_type for r in juego.recognizers if r.patterns}

    assert OWN_DOMAIN_TYPES <= FORMAT_TYPES
    assert propios == FORMAT_TYPES


@pytest.mark.parametrize("language", ["es", "en"])
def test_cada_reconocedor_propio_declara_las_tres_formas_de_escritura(language: str) -> None:
    """Compacta, con separadores y dictada (BR2.2, AC4.13.2)."""
    juego = loading.load_recognizer_set(language)  # type: ignore[arg-type]

    for reconocedor in juego.recognizers:
        if not reconocedor.patterns:
            continue
        formas = {patron.form for patron in reconocedor.patterns}
        assert formas == set(WritingForm), (
            f"{reconocedor.id} declara {sorted(f.value for f in formas)}"
        )


@pytest.mark.parametrize("language", ["es", "en"])
def test_cada_reconocedor_declara_su_mecanismo_y_su_procedencia(language: str) -> None:
    """Sin el mecanismo declarado, U21 no puede comprobar que el suyo es distinto.

    AC4.14.1 exige que los dos detectores no compartan mecanismo, y U21 lo
    comprueba leyendo **este archivo** sin importar este modulo (BR4.6). Un
    mecanismo sin declarar convierte esa comprobacion en una afirmacion.
    """
    juego = loading.load_recognizer_set(language)  # type: ignore[arg-type]

    declarados: list[Recognizer | FallbackRule] = [*juego.recognizers, juego.fallback]
    for reconocedor in declarados:
        assert isinstance(reconocedor.mechanism, Mechanism)
        assert reconocedor.source.strip()


def test_la_regla_de_autoidentificacion_produce_nombres_por_contexto() -> None:
    """U21 lee el mecanismo de este archivo para no compartirlo (AC4.14.1).

    La regla encuentra el nombre por la frase que lo anuncia: eso es contexto, y
    lo que produce es un nombre. Declarar otra cosa seria mentirle a U21 o sumar
    sus hallazgos a otro tipo.
    """
    for idioma in ("es", "en"):
        regla = loading.load_recognizer_set(idioma).self_identification
        assert regla.entity_type is EntityType.PERSON
        assert regla.mechanism is Mechanism.CONTEXT
        assert regla.source.strip()
        assert regla.id == f"{idioma}-person-cue"


def test_el_respaldo_solo_produce_lo_no_clasificado() -> None:
    """BR4.2: su cifra va aparte y nunca se suma a la de un tipo del dominio."""
    for idioma in ("es", "en"):
        juego = loading.load_recognizer_set(idioma)
        assert juego.fallback.entity_type is EntityType.UNCLASSIFIED
        assert juego.fallback.mechanism is Mechanism.CONTEXT


# --- Lo que no puede cargar ---------------------------------------------------


@pytest.mark.parametrize("campo", CAMPOS_OBLIGATORIOS)
def test_un_reconocedor_sin_uno_de_sus_cinco_campos_no_carga(campo: str, tmp_path: Path) -> None:
    """BR2.6: si falta cualquiera de los cinco, el arranque falla nombrandolo.

    Se prueba campo por campo y no "con un campo cualquiera": el que se olvide
    sera justo el que no estaba cubierto.
    """
    datos = _juego_crudo("es")
    del datos["recognizers"][0][campo]
    _escribir(tmp_path, "es", datos)

    with pytest.raises(loading.RecognizerLoadError) as error:
        loading.load_recognizer_set("es", tmp_path)

    assert "es.yaml" in str(error.value)


def test_un_reconocedor_que_sirve_a_otro_idioma_no_carga(tmp_path: Path) -> None:
    """BR2.7: un reconocedor sirve a **un** idioma.

    Uno que dijera servir a los dos haria que su medicion por idioma fuera un
    promedio, y un idioma roto quedaria escondido tras el otro.
    """
    datos = _juego_crudo("es")
    datos["recognizers"][0]["language"] = "en"
    _escribir(tmp_path, "es", datos)

    with pytest.raises(loading.RecognizerLoadError) as error:
        loading.load_recognizer_set("es", tmp_path)

    assert "es-license-plate" in str(error.value) or "language" in str(error.value)


def test_un_identificador_que_no_empieza_por_su_idioma_no_carga(tmp_path: Path) -> None:
    """Las sondas de RT-15 componen `<idioma>-<tipo>` para exigir que el informe
    atribuya el hallazgo al juego que lo encontro (BR2.9). Un identificador con
    otra forma dejaria esa sonda midiendo otra cosa sin que nadie se entere."""
    datos = _juego_crudo("es")
    datos["recognizers"][0]["id"] = "es2-license-plate"
    _escribir(tmp_path, "es", datos)

    with pytest.raises(loading.RecognizerLoadError):
        loading.load_recognizer_set("es", tmp_path)


def test_dos_reconocedores_con_el_mismo_identificador_no_cargan(tmp_path: Path) -> None:
    """Dos con el mismo identificador harian que el informe sumara los hallazgos
    de los dos bajo una sola fila, y un reconocedor roto se esconderia tras el
    otro justo en la columna que existe para verlo."""
    datos = _juego_crudo("es")
    datos["recognizers"][1]["id"] = datos["recognizers"][0]["id"]
    _escribir(tmp_path, "es", datos)

    with pytest.raises(loading.RecognizerLoadError) as error:
        loading.load_recognizer_set("es", tmp_path)

    assert "es.yaml" in str(error.value)


def test_un_idioma_sin_regla_de_autoidentificacion_no_carga(tmp_path: Path) -> None:
    """Es obligatoria, como el respaldo: sin ella, el nombre que el modelo no
    etiqueta como persona sale entero en ese idioma, y nada avisa."""
    datos = _juego_crudo("es")
    del datos["self_identification"]
    _escribir(tmp_path, "es", datos)

    with pytest.raises(loading.RecognizerLoadError) as error:
        loading.load_recognizer_set("es", tmp_path)

    assert "es.yaml" in str(error.value)


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        pytest.param("entity_type", "location", id="otro-tipo"),
        pytest.param("mechanism", "pattern", id="otro-mecanismo"),
        pytest.param("min_tokens", 5, id="minimo-sobre-el-maximo"),
        pytest.param("cues", [], id="sin-frases"),
        pytest.param("organization_words", [], id="sin-palabras-de-organizacion"),
        pytest.param("language", "en", id="otro-idioma"),
    ],
)
def test_una_regla_de_autoidentificacion_mal_declarada_no_carga(
    campo: str, valor: object, tmp_path: Path
) -> None:
    """Cada forma de declararla mal falla al cargar, nombrando el archivo.

    Sin frases no encuentra nada; sin palabras de organizacion se traga el nombre
    de las aseguradoras; con otro tipo o mecanismo miente al informe y a U21; con
    otro idioma, su medicion por idioma seria un promedio.
    """
    datos = _juego_crudo("es")
    datos["self_identification"][campo] = valor
    _escribir(tmp_path, "es", datos)

    with pytest.raises(loading.RecognizerLoadError) as error:
        loading.load_recognizer_set("es", tmp_path)

    assert "es.yaml" in str(error.value)


def test_un_patron_que_no_compila_no_carga(tmp_path: Path) -> None:
    """Una expresion rota no puede descubrirse en la primera llamada real: para
    entonces ya salio texto sin tapar."""
    datos = _juego_crudo("es")
    datos["recognizers"][0]["patterns"][0]["regex"] = r"([A-Z]{3}"
    _escribir(tmp_path, "es", datos)

    with pytest.raises(loading.RecognizerLoadError):
        loading.load_recognizer_set("es", tmp_path)


def test_un_archivo_que_falta_falla_nombrandolo(tmp_path: Path) -> None:
    """Fallar cerrado: sin su juego, ese idioma no se redacta, y el fallo no
    avisa solo (BR1.7, NFRD-U3-2)."""
    with pytest.raises(loading.RecognizerLoadError) as error:
        loading.load_recognizer_set("es", tmp_path)

    assert "es.yaml" in str(error.value)


# --- Lo que si se puede hacer solo con configuracion --------------------------


def test_anadir_un_formato_nuevo_es_solo_configuracion(tmp_path: Path) -> None:
    """BR2.8: un formato nuevo no toca el codigo de deteccion.

    Es la unica defensa del juego contra el olvido: si anadir un formato
    exigiera cambiar logica, el juego dejaria de poder revisarse de un vistazo.
    """
    datos = copy.deepcopy(_juego_crudo("es"))
    datos["recognizers"].append(
        {
            "id": "es-phone-corporativo",
            "entity_type": "phone",
            "language": "es",
            "mechanism": "pattern",
            "source": "Formato inventado para esta prueba: extension de cuatro digitos",
            "context": ["extension"],
            "patterns": [
                {"form": "compact", "regex": r"\bEXT\d{4}\b", "score": 0.5},
                {"form": "separated", "regex": r"\bEXT[ \-]\d{4}\b", "score": 0.5},
                {"form": "spoken", "regex": r"\bextension (?:uno|dos|tres){4}\b", "score": 0.5},
            ],
        }
    )
    _escribir(tmp_path, "es", datos)

    juego = loading.load_recognizer_set("es", tmp_path)

    assert "es-phone-corporativo" in {r.id for r in juego.recognizers}


def test_los_dos_juegos_se_cargan_juntos() -> None:
    """BR2.9: los dos, siempre.

    Cargar solo el del turno es la forma natural de escribirlo y es exactamente
    el agujero de RT-15: una cedula dictada en espanol dentro de un turno en
    ingles saldria en claro, y la compuerta dura fallaria por construccion.
    """
    juegos = loading.load_all()

    assert set(juegos) == {"es", "en"}
    assert all(juego.recognizers for juego in juegos.values())
