"""Las frases solo-servidor no viajan al navegador, y el criterio se comprueba (SO-1)."""

from __future__ import annotations

from pathlib import Path

from untangle.copy_catalog.checks import check_server_only_keys
from untangle.copy_catalog.keys_module import render_keys_module, render_texts_module
from untangle.copy_catalog.models import CopyEntry, Surface
from untangle.copy_catalog.server_only import (
    BROWSER_KEY_EXCEPTIONS,
    SERVER_ONLY_PREFIXES,
    is_server_only,
)


def _entrada(clave: str, idioma: str = "es") -> CopyEntry:
    return CopyEntry(key=clave, locale=idioma, text="x", surface=Surface.SYSTEM)  # type: ignore[arg-type]


def test_el_prefijo_casa_la_clave_igual_y_las_que_cuelgan_pero_no_un_vecino() -> None:
    assert is_server_only("intake.question.plate")
    assert is_server_only("intake.unfinished")
    assert not is_server_only("intake.questions_extra.x")
    assert not is_server_only("intake.degraded")


def test_una_excepcion_gana_sobre_su_prefijo() -> None:
    assert is_server_only("adjuster.step.rules.text")
    assert not is_server_only("adjuster.step.rules.title")
    assert all(
        any(c.startswith(p + ".") for p in SERVER_ONLY_PREFIXES) for c in BROWSER_KEY_EXCEPTIONS
    )


def test_los_modulos_generados_dejan_fuera_las_claves_solo_servidor() -> None:
    entradas = {
        (clave, "es"): _entrada(clave)
        for clave in ("intake.question.plate", "adjuster.step.rules.title", "home.title")
    }

    claves = render_keys_module(entradas)
    frases = render_texts_module(entradas, "es")

    for generado in (claves, frases):
        assert "intake.question.plate" not in generado
        assert "adjuster.step.rules.title" in generado
        assert "home.title" in generado


def _arbol(raiz: Path, archivos: dict[str, str]) -> Path:
    for ruta, contenido in archivos.items():
        destino = raiz / "app" / "frontend" / "src" / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(contenido, encoding="utf-8")
    return raiz


def _catalogo() -> dict[tuple[str, str], dict[str, object]]:
    claves = [f"{prefijo}.x" for prefijo in SERVER_ONLY_PREFIXES] + [
        "intake.question.plate",
        *BROWSER_KEY_EXCEPTIONS,
    ]
    return {(c, "es"): {"key": c} for c in claves}


def test_una_clave_solo_servidor_escrita_en_la_interfaz_se_nombra(tmp_path: Path) -> None:
    codigo = "\n".join(f't("{c}");' for c in BROWSER_KEY_EXCEPTIONS)
    raiz = _arbol(
        tmp_path,
        {"pages/a.tsx": codigo + '\nt("intake.question.plate");\n'},
    )

    hallazgos = check_server_only_keys(_catalogo(), raiz)

    nombradas = {h.where for h in hallazgos if h.rule == "SO-1"}
    assert "intake.question.plate" in nombradas


def test_una_excepcion_que_la_interfaz_ya_no_escribe_esta_vencida(tmp_path: Path) -> None:
    raiz = _arbol(tmp_path, {"pages/a.tsx": "export {};\n"})

    hallazgos = check_server_only_keys(_catalogo(), raiz)

    vencidas = {h.where for h in hallazgos if "vencio" in h.detail}
    assert vencidas == set(BROWSER_KEY_EXCEPTIONS)


def test_las_pruebas_y_los_modulos_generados_no_cuentan_como_consumidor(tmp_path: Path) -> None:
    codigo = "\n".join(f't("{c}");' for c in BROWSER_KEY_EXCEPTIONS)
    raiz = _arbol(
        tmp_path,
        {
            "pages/a.tsx": codigo,
            "pages/a.test.tsx": 't("intake.question.plate");',
            "shared/copy/copy-texts.es.ts": '["intake.question.plate", "x"]',
        },
    )

    assert check_server_only_keys(_catalogo(), raiz) == []
