"""Los chequeos del catalogo sobre la interfaz de U6 (BR2.3, BR3.2 a BR3.4).

U6 extiende los chequeos de U1 en cuatro puntos, y cada uno los vuelve **mas
estrictos**, no menos:

- Un modulo generado desde el catalogo ya no cuenta como consumidor: lista todas
  las claves, y contarlo volvia el chequeo de claves muertas una tautologia.
- La clave del caracter que declara una aseguradora en su `tenant.yaml` si
  cuenta, y una que no existe en el catalogo es un hallazgo.
- Una clave armada con una plantilla de TypeScript es tan armada como la que
  viaja en una variable.
- El chequeo de cadenas en linea lee literales completos y cubre los directorios
  de la interfaz.

Cada prueba rompe el arbol a proposito y exige que el hallazgo nombre al
culpable.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from untangle import paths
from untangle.copy_catalog import checks

RAIZ_REAL = paths.repo_root()

CATALOGO = {
    "es": "insurer:\n  character:\n    calm:\n      text: Tranquila\n      surface: system\n",
    "en": "insurer:\n  character:\n    calm:\n      text: Calm\n      surface: system\n",
}

MARCA = "// GENERADO. No editar a mano.\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Un arbol minimo: el catalogo, una aseguradora y una carpeta de interfaz."""
    copia = tmp_path / "app" / "config" / "copy"
    copia.mkdir(parents=True)
    for idioma, texto in CATALOGO.items():
        (copia / f"{idioma}.yaml").write_text(texto, encoding="utf-8")
    shutil.copy(RAIZ_REAL / "app" / "config" / "copy" / "forbidden-forms.yaml", copia)
    (copia / "inline-allowlist.yaml").write_text("allowed: []\n", encoding="utf-8")
    (tmp_path / "app" / "frontend" / "src" / "pages").mkdir(parents=True)
    return tmp_path


def _aseguradora(repo: Path, carpeta: str, clave: str) -> None:
    destino = repo / "app" / "config" / "tenants" / carpeta
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "tenant.yaml").write_text(
        f"tenant_id: {carpeta}\ncharacter_key: {clave}\n", encoding="utf-8"
    )


def _interfaz(repo: Path, nombre: str, contenido: str) -> None:
    (repo / "app" / "frontend" / "src" / "pages" / nombre).write_text(contenido, encoding="utf-8")


def test_un_modulo_generado_no_cuenta_como_consumidor(repo: Path) -> None:
    _interfaz(repo, "copy-texts.ts", f'{MARCA}export const X = ["insurer.character.calm"];\n')

    hallazgos = [h for h in checks.run_all(repo) if h.rule == "BR3.2"]

    assert [h.where for h in hallazgos] == ["insurer.character.calm"]


def test_la_clave_de_caracter_de_una_aseguradora_cuenta_como_consumidor(repo: Path) -> None:
    _aseguradora(repo, "demo", "insurer.character.calm")

    assert [h for h in checks.run_all(repo) if h.rule == "BR3.2"] == []


def test_una_aseguradora_que_declara_una_clave_inexistente_es_un_hallazgo(repo: Path) -> None:
    _aseguradora(repo, "demo", "insurer.character.calm")
    _aseguradora(repo, "otra", "insurer.character.no_existe")

    hallazgos = [h for h in checks.run_all(repo) if h.rule == "BR3.2"]

    assert [h.where for h in hallazgos] == ["app/config/tenants/otra/tenant.yaml"]
    assert "insurer.character.no_existe" in hallazgos[0].detail


def test_una_clave_armada_con_plantilla_falla_nombrando_el_archivo(repo: Path) -> None:
    _aseguradora(repo, "demo", "insurer.character.calm")
    _interfaz(repo, "status.tsx", "export const f = (k: string) => t(`status.${k}.title`);\n")

    hallazgos = [h for h in checks.run_all(repo) if h.rule == "BR3.4"]

    assert [h.where for h in hallazgos] == ["app/frontend/src/pages/status.tsx:1"]


def test_una_clave_literal_en_una_tabla_de_mensajes_no_es_un_hallazgo(repo: Path) -> None:
    _aseguradora(repo, "demo", "insurer.character.calm")
    _interfaz(repo, "tabla.ts", 'export const m = (t: T) => t("insurer.character.calm");\n')

    assert [h for h in checks.run_all(repo) if h.rule in {"BR3.2", "BR3.4"}] == []


def test_el_codigo_entre_dos_literales_no_se_confunde_con_una_frase(repo: Path) -> None:
    _aseguradora(repo, "demo", "insurer.character.calm")
    _interfaz(repo, "idioma.ts", 'export const l = x.startsWith("es") === true ? "es" : "en";\n')

    assert [h for h in checks.run_all(repo) if h.rule == "BR3.3"] == []


def test_una_frase_escrita_en_linea_en_la_interfaz_se_detecta(repo: Path) -> None:
    _aseguradora(repo, "demo", "insurer.character.calm")
    _interfaz(
        repo, "inicio.tsx", 'export const x = <p>{"La demo está despertando ahora mismo."}</p>;\n'
    )

    hallazgos = [h for h in checks.run_all(repo) if h.rule == "BR3.3"]

    assert [h.where for h in hallazgos] == ["app/frontend/src/pages/inicio.tsx:1"]


def _modulo_de_voz(repo: Path, nombre: str, contenido: str) -> None:
    destino = repo / "app" / "backend" / "src" / "untangle" / "voice"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / nombre).write_text(contenido, encoding="utf-8")


def test_la_prosa_de_un_docstring_no_es_una_cadena_visible(repo: Path) -> None:
    """Un docstring no se le muestra a nadie, y explicarse cuesta frases enteras.

    El chequeo saltaba la linea que abre el bloque y solo esa, asi que la prosa de
    las siguientes se leia como codigo: un modulo que explicaba su regla citando la
    frase que la motiva se denunciaba a si mismo, y la unica salida era escribir mas
    vago. Lo encontro U18, con `main` en rojo.
    """
    _aseguradora(repo, "demo", "insurer.character.calm")
    _modulo_de_voz(
        repo,
        "peticion.py",
        '"""Una regla, explicada.\n\n'
        "Se explica con la frase que la motiva, porque sin ella la regla no se\n"
        'entiende: "Con mucho gusto le ayudo a reportar su caso ahora mismo."\n"""\n'
        "UMBRAL = 4\n",
    )

    assert [h for h in checks.run_all(repo) if h.rule == "BR3.3"] == []


def test_una_frase_escrita_en_linea_en_el_backend_si_se_detecta(repo: Path) -> None:
    """La otra mitad, y la que hace que la de arriba signifique algo: fuera de un
    docstring, la misma frase sigue siendo un hallazgo."""
    _aseguradora(repo, "demo", "insurer.character.calm")
    _modulo_de_voz(
        repo,
        "peticion.py",
        '"""Una regla."""\nFRASE = "Con mucho gusto le ayudo a reportar su caso ahora mismo."\n',
    )

    hallazgos = [h for h in checks.run_all(repo) if h.rule == "BR3.3"]

    assert [h.where for h in hallazgos] == ["app/backend/src/untangle/voice/peticion.py:2"]


def test_el_arbol_real_pasa_los_chequeos() -> None:
    """La linea base: el catalogo, la interfaz y las aseguradoras de verdad."""
    assert checks.run_all() == []
