"""Las huellas de terceros y su compuerta (BR5.1 a BR5.3, SEC-U7.1, SEC-U7.2).

**Ningun specimen real.** El formulario que se usa aqui es un texto inventado para
la prueba, con secuencias conocidas, y el PDF se arma a mano con ese mismo texto:
una prueba que leyera un specimen real lo necesitaria en disco --y el repositorio
no lo tiene, a proposito-- o lo traeria dentro, que es justo lo que la unidad
prohibe.

Tres capas, en el orden de la rama determinista:

- la normalizacion compartida (`untangle.text_fingerprints`), que tiene que ser
  la misma para sacar las huellas y para compararlas;
- sacar las huellas: solo hashes, nada legible, y el comando que las escribe;
- la compuerta de `content:check`: umbral cero, y "no medido" que falla.
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from untangle.evals import content_checks
from untangle.synthetic_data import fingerprints
from untangle.synthetic_data.models import FingerprintSet
from untangle.text_fingerprints import (
    SHINGLE_SIZE,
    FingerprintSettings,
    SettingsError,
    load_settings,
    normalized_words,
    shingle_hashes,
)
from untangle.workspace import synthetic_fingerprints

from .apoyo import RAIZ_REAL

#: El formulario inventado. Nada de esto viene de ningun formulario real: son
#: frases escritas para esta prueba, con un encabezado de la referencia y
#: numeracion para que la normalizacion tenga algo que quitar.
SPECIMEN = (
    "PERSONAL AUTO POLICY\n"
    "PART D \u2013 COVERAGE FOR DAMAGE TO YOUR\n"
    "AUTO\n"
    "A. The lighthouse keeper paints every blue door on the northern pier at dawn.\n"
    "(1) Seven copper kettles whistle together whenever the orchard fog rolls in.\n"
    "2. Nobody remembers why the ferry schedule was printed on violet para-\n"
    "chment paper.\n"
)

#: Ocho palabras seguidas del specimen, sin numeracion ni encabezado.
COPIA = "the lighthouse keeper paints every blue door on"
#: Siete: una menos que la ventana.
CASI = "seven copper kettles whistle together whenever the"


def _ajustes() -> FingerprintSettings:
    return load_settings(RAIZ_REAL)


# --- La normalizacion compartida ---------------------------------------------


def test_quita_encabezados_aunque_el_pdf_los_parta_en_dos_lineas() -> None:
    """La edicion de 2018 parte "Part D -- Coverage for Damage to Your Auto" en dos
    lineas: por eso los encabezados se quitan como secuencias de palabras."""
    palabras = normalized_words(SPECIMEN, _ajustes().structure_headings)

    assert palabras[:4] == ("the", "lighthouse", "keeper", "paints")
    assert "coverage" not in palabras
    assert "personal" not in palabras


def test_quita_la_numeracion_y_une_la_palabra_partida_por_el_guion() -> None:
    palabras = normalized_words(
        "iv) (1) A. 2. Una PÓLIZA para-\nguas", _ajustes().structure_headings
    )

    assert palabras == ("una", "poliza", "paraguas")


def test_un_texto_de_menos_de_ocho_palabras_no_tiene_huellas() -> None:
    assert shingle_hashes(("uno", "dos", "tres")) == frozenset()
    assert len(shingle_hashes(tuple(COPIA.split()))) == 1


def test_una_ventana_sin_palabras_no_es_una_ventana() -> None:
    with pytest.raises(ValueError, match="no es una ventana"):
        shingle_hashes(("a",), size=0)


def test_cambiar_la_lista_de_encabezados_cambia_la_normalizacion() -> None:
    """La compuerta compara la normalizacion escrita con la actual: si la lista
    cambia sin volver a sacar las huellas, las dos dejan de ser la misma."""
    ajustes = _ajustes()
    otra = FingerprintSettings(
        shingles_file=ajustes.shingles_file,
        corpus=ajustes.corpus,
        structure_headings=ajustes.structure_headings[1:],
    )

    assert otra.normalization != ajustes.normalization


def test_sin_seccion_de_huellas_la_configuracion_falla_nombrando_el_archivo(
    tmp_path: Path,
) -> None:
    (tmp_path / "app" / "config").mkdir(parents=True)
    (tmp_path / "app" / "config" / "content-checks.yaml").write_text(
        "published: [app]\n", encoding="utf-8"
    )

    with pytest.raises(SettingsError, match=r"content-checks\.yaml"):
        load_settings(tmp_path)


# --- Sacar las huellas: solo hashes -------------------------------------------


def _pdf_minimo(lineas: list[str]) -> bytes:
    """Un PDF de una pagina con esas lineas, armado a mano para no traer uno real."""

    def escapar(linea: str) -> str:
        return linea.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    flujo = (
        "BT /F1 10 Tf 12 TL 40 760 Td "
        + " ".join(f"({escapar(linea)}) Tj T*" for linea in lineas)
        + " ET"
    )
    objetos = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(flujo.encode('latin-1'))} >>\nstream\n{flujo}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    salida = b"%PDF-1.4\n"
    desplazamientos = []
    for numero, objeto in enumerate(objetos, start=1):
        desplazamientos.append(len(salida))
        salida += f"{numero} 0 obj\n{objeto}\nendobj\n".encode("latin-1")
    inicio_xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    salida += "".join(f"{d:010d} 00000 n \n" for d in desplazamientos).encode()
    salida += f"trailer << /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF\n".encode()
    return salida


@pytest.fixture
def specimens(tmp_path: Path) -> Path:
    carpeta = tmp_path / "tmp" / "specimens"
    carpeta.mkdir(parents=True)
    (carpeta / "inventado.txt").write_text(SPECIMEN, encoding="utf-8")
    (carpeta / "inventado.pdf").write_bytes(
        _pdf_minimo([linea for linea in SPECIMEN.replace("\u2013", "-").splitlines() if linea])
    )
    return carpeta


def _specimen(carpeta: Path, nombre: str) -> fingerprints.SpecimenFile:
    return fingerprints.SpecimenFile(
        path=carpeta / nombre,
        form="XX 00 00",
        edition="01 26",
        publisher="Editorial inventada",
        retrieved_at=date(2026, 9, 21),
    )


def test_el_texto_plano_y_su_pdf_dan_huellas(specimens: Path) -> None:
    """CG-U7-5: el PDF que publica el regulador, o su texto plano."""
    for nombre in ("inventado.txt", "inventado.pdf"):
        conjunto, por_specimen = fingerprints.build_fingerprint_set(
            [_specimen(specimens, nombre)], _ajustes()
        )
        assert por_specimen[nombre] > 0
        assert next(iter(_ajustes().fingerprint(COPIA))) in conjunto.hashes


def test_el_archivo_de_huellas_no_trae_ninguna_secuencia_legible(
    specimens: Path, tmp_path: Path
) -> None:
    """SEC-U7.2: ni tres palabras seguidas del specimen en el archivo escrito."""
    conjunto, _ = fingerprints.build_fingerprint_set(
        [_specimen(specimens, "inventado.txt")], _ajustes()
    )
    destino = tmp_path / "huellas.json"
    fingerprints.write_fingerprint_set(conjunto, destino)

    escrito = destino.read_text(encoding="utf-8").lower()
    palabras = normalized_words(SPECIMEN, _ajustes().structure_headings)
    tripletas = {" ".join(palabras[i : i + 3]) for i in range(len(palabras) - 2)}
    assert [t for t in tripletas if t in escrito] == []
    assert fingerprints.load_fingerprint_set(destino) == conjunto


def test_dos_corridas_con_los_mismos_specimens_escriben_los_mismos_bytes(
    specimens: Path, tmp_path: Path
) -> None:
    for vuelta in ("a", "b"):
        conjunto, _ = fingerprints.build_fingerprint_set(
            [_specimen(specimens, "inventado.txt")], _ajustes()
        )
        fingerprints.write_fingerprint_set(conjunto, tmp_path / f"{vuelta}.json")

    assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()


@pytest.mark.parametrize(
    ("nombre", "contenido", "motivo"),
    [
        pytest.param("vacio.txt", "", "ninguna secuencia", id="sin-texto"),
        pytest.param("formulario.docx", "x", "no es un PDF", id="otro-formato"),
        pytest.param("roto.pdf", "esto no es un pdf", "no se pudo extraer", id="pdf-roto"),
    ],
)
def test_un_specimen_que_no_da_huellas_falla_sin_guardar_nada(
    specimens: Path, nombre: str, contenido: str, motivo: str
) -> None:
    """Guardar cero huellas de un specimen dejaria la compuerta pasando sin comparar."""
    (specimens / nombre).write_text(contenido, encoding="utf-8")

    with pytest.raises(fingerprints.FingerprintError, match=motivo):
        fingerprints.build_fingerprint_set([_specimen(specimens, nombre)], _ajustes())


def test_sin_specimens_no_hay_huellas() -> None:
    with pytest.raises(fingerprints.FingerprintError, match="ningun specimen"):
        fingerprints.build_fingerprint_set([], _ajustes())


# --- El comando ---------------------------------------------------------------


@pytest.fixture
def raiz(tmp_path: Path, specimens: Path) -> Path:
    """Un arbol con la configuracion real de los chequeos y el specimen inventado."""
    (tmp_path / "app" / "config").mkdir(parents=True)
    shutil.copy(RAIZ_REAL / "app" / "config" / "content-checks.yaml", tmp_path / "app" / "config")
    return tmp_path


def _argumentos(ruta: str) -> list[list[str]]:
    return [[ruta, "XX 00 00", "01 26", "Editorial inventada", "2026-09-21"]]


def test_el_comando_escribe_solo_hashes_e_imprime_solo_recuentos(
    raiz: Path, specimens: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        synthetic_fingerprints.run(raiz, specimens, _argumentos("tmp/specimens/inventado.pdf")) == 0
    )

    salida = capsys.readouterr()
    assert "lighthouse" not in (salida.out + salida.err).lower()
    escrito = FingerprintSet.model_validate_json(
        (raiz / "app" / "config" / "content" / "third-party-shingles.json").read_bytes()
    )
    assert escrito.sources[0].publisher == "Editorial inventada"
    assert escrito.normalization == load_settings(raiz).normalization


def test_sin_specimens_declarados_vuelve_a_sacarlas_de_los_del_archivo(
    raiz: Path, specimens: Path
) -> None:
    """Regenerar sin escribir de memoria el publicador y la fecha."""
    assert (
        synthetic_fingerprints.run(raiz, specimens, _argumentos("tmp/specimens/inventado.txt")) == 0
    )
    destino = raiz / "app" / "config" / "content" / "third-party-shingles.json"
    antes = destino.read_bytes()
    destino.unlink()
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(antes)

    assert synthetic_fingerprints.run(raiz, specimens, None) == 0
    assert destino.read_bytes() == antes


@pytest.mark.parametrize(
    ("argumentos", "motivo"),
    [
        pytest.param(
            [["app/specimen.txt", "F", "E", "P", "2026-09-21"]], "no esta en", id="fuera-de-tmp"
        ),
        pytest.param(
            [["tmp/specimens/inventado.txt", "F", "E", "P", "ayer"]], "no es una fecha", id="fecha"
        ),
        pytest.param(None, "no hay archivo de huellas", id="sin-archivo-previo"),
    ],
)
def test_el_comando_se_niega_y_no_escribe(
    raiz: Path,
    specimens: Path,
    argumentos: list[list[str]] | None,
    motivo: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Un specimen fuera de `tmp/specimens/` puede acabar en un commit (SEC-U7.2)."""
    assert synthetic_fingerprints.run(raiz, specimens, argumentos) == 1

    assert motivo in capsys.readouterr().err
    assert not (raiz / "app" / "config" / "content" / "third-party-shingles.json").exists()


def test_regenerar_sin_uno_de_los_specimens_declarados_falla(
    raiz: Path, specimens: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Sin todos, las huellas nuevas cubririan menos que las viejas."""
    assert (
        synthetic_fingerprints.run(raiz, specimens, _argumentos("tmp/specimens/inventado.txt")) == 0
    )
    (specimens / "inventado.txt").unlink()

    assert synthetic_fingerprints.run(raiz, specimens, None) == 1
    assert "Editorial inventada" in capsys.readouterr().err


# --- La compuerta de content:check --------------------------------------------


def _clausulas(raiz: Path, textos: dict[str, str]) -> None:
    carpeta = raiz / "app" / "data" / "tenants" / "emisora" / "clauses"
    carpeta.mkdir(parents=True, exist_ok=True)
    clausulas = [{"clause_id": clave, "text": texto} for clave, texto in textos.items()]
    (carpeta / "FORM.json").write_text(json.dumps({"clauses": clausulas}), encoding="utf-8")


def _con_huellas(raiz: Path, specimens: Path) -> None:
    assert (
        synthetic_fingerprints.run(raiz, specimens, _argumentos("tmp/specimens/inventado.txt")) == 0
    )


def test_una_sola_secuencia_compartida_falla_y_nombra_la_clausula(
    raiz: Path, specimens: Path
) -> None:
    """Umbral cero (BR5.2), y el hallazgo dice cuantas, nunca cuales."""
    _con_huellas(raiz, specimens)
    _clausulas(
        raiz,
        {
            "FORM-A.1": f"Our own words first, then {COPIA.upper()} and more of ours.",
            "FORM-A.2": f"Almost: {CASI} but never the eighth word.",
            "FORM-A.3": "A clause written entirely in our own words, with nothing borrowed at all.",
        },
    )

    hallazgos = content_checks.check_third_party_text(raiz)

    assert [h.detail.split(":")[0] for h in hallazgos] == ["FORM-A.1"]
    assert hallazgos[0].rule == content_checks.REGLA_DE_HUELLAS
    assert "lighthouse" not in str(hallazgos[0]).lower()


def test_la_compuerta_entra_en_el_chequeo_de_texto_de_clausula(raiz: Path, specimens: Path) -> None:
    """Es la mitad por huellas del mismo criterio de P8, y sale en su caso de evaluacion."""
    _con_huellas(raiz, specimens)
    _clausulas(raiz, {"FORM-A.1": COPIA})

    reglas = content_checks.load_rules(raiz)

    assert [h.rule for h in content_checks.check_clause_text(raiz, reglas)] == [
        content_checks.REGLA_DE_HUELLAS
    ]


@pytest.mark.parametrize(
    ("estropear", "motivo"),
    [
        pytest.param(lambda d: None, "falta el archivo", id="sin-archivo"),
        pytest.param(lambda d: {**d, "hashes": [], "sources": []}, "no trae huellas", id="vacio"),
        pytest.param(
            lambda d: {**d, "normalization": "v0"}, "otra normalizacion", id="otra-normalizacion"
        ),
        pytest.param(lambda d: {**d, "shingle_size": 5}, "otro tamano", id="otro-tamano"),
        pytest.param(lambda d: {**d, "hashes": ["legible"]}, "no es un SHA-256", id="no-es-hash"),
    ],
)
def test_sin_huellas_utilizables_el_chequeo_es_no_medido_y_falla(
    raiz: Path, specimens: Path, estropear: object, motivo: str
) -> None:
    """BR5.3: una compuerta que no se pudo ejecutar nunca pasa en verde."""
    _con_huellas(raiz, specimens)
    _clausulas(raiz, {"FORM-A.1": "A clause written entirely in our own words, nothing borrowed."})
    archivo = raiz / "app" / "config" / "content" / "third-party-shingles.json"
    nuevo = estropear(json.loads(archivo.read_text(encoding="utf-8")))  # type: ignore[operator]
    if nuevo is None:
        archivo.unlink()
    else:
        archivo.write_text(json.dumps(nuevo), encoding="utf-8")

    hallazgos = content_checks.check_third_party_text(raiz)

    assert len(hallazgos) == 1
    assert hallazgos[0].detail.startswith("no medido")
    assert motivo in hallazgos[0].detail


def test_sin_corpus_no_hay_nada_que_comparar(raiz: Path) -> None:
    """BR5.3 aplica cuando el corpus existe; sin el, no hay texto publicado."""
    assert content_checks.check_third_party_text(raiz) == []


def test_en_el_repositorio_la_compuerta_compara_de_verdad() -> None:
    """Sin esto, un corpus movido de sitio dejaria la compuerta en verde sin
    comparar nada: se exige que encuentre clausulas y huellas."""
    ajustes = load_settings(RAIZ_REAL)
    clausulas = content_checks._clausulas_del_corpus(RAIZ_REAL, ajustes.corpus)
    huellas, motivo = content_checks._huellas_guardadas(RAIZ_REAL, ajustes)

    assert len(clausulas) > 100
    assert motivo == ""
    assert len(huellas) > 1000
    assert SHINGLE_SIZE == ajustes.shingle_size
