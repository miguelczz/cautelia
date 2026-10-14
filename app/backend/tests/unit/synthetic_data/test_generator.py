"""El nucleo del generador: mismos bytes, salidas independientes y nada escrito a medias.

Reglas: BR1.1 (bytes identicos), BR1.2 (azar por salida), BR1.4 (manifiesto),
BR1.5 y SEC-U7.5 (sin modelo ni claves), BR2.2 (sin marca de revision no se
escribe nada) y TECH-U7.1 y TECH-U7.2 (lo versionado es lo que se genera).

La composicion del corpus llega en el paso 8; aqui el nucleo recibe dos
compositores **de prueba**, minimos, que hacen lo que hace cualquier
compositor: leer las fuentes revisadas y elegir con el azar sembrado.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import pytest

from untangle import settings
from untangle.providers import factory
from untangle.synthetic_data import cli, generator, manifest
from untangle.synthetic_data.canonical import sha256_hex
from untangle.synthetic_data.generator import (
    Composition,
    CompositionContext,
    CorpusOutput,
    GenerationError,
    GenerationRequest,
)
from untangle.synthetic_data.models import GenerationManifest

from .apoyo import (
    COMPOSITORES,
    entrada,
    escribir_fuente,
    fuentes_minimas,
    poliza_con_azar,
    repo,
)


def _generar(
    raiz: Path, datos: Path, compositores: tuple[generator.Composer, ...] = COMPOSITORES
) -> None:
    generator.generate(GenerationRequest(repo_root=raiz, data_dir=datos, composers=compositores))


def _foto(directorio: Path) -> dict[str, bytes]:
    """Lo que el generador escribio: todo menos las fuentes, que son entrada."""
    return {
        p.relative_to(directorio).as_posix(): p.read_bytes()
        for p in sorted(directorio.rglob("*"))
        if p.is_file() and p.relative_to(directorio).parts[0] != "sources"
    }


# --- BR1.1: mismos bytes ------------------------------------------------------


def test_dos_generaciones_en_directorios_distintos_escriben_los_mismos_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raiz = repo(tmp_path / "repo")
    fuentes_minimas(raiz)

    _generar(raiz, tmp_path / "uno")
    # Otra zona horaria y otro momento: nada de eso puede llegar a los bytes.
    monkeypatch.setenv("TZ", "Pacific/Kiritimati")
    time.tzset()
    _generar(raiz, tmp_path / "dos")
    monkeypatch.delenv("TZ")
    time.tzset()

    uno, dos = _foto(tmp_path / "uno"), _foto(tmp_path / "dos")
    assert uno == dos
    assert sorted(uno) == [
        "manifest.json",
        "tenants/stonecroft/clauses/STO-PAP-2026.json",
        "tenants/stonecroft/issued_policies/POL-100042.json",
    ]


def test_la_forma_canonica_ordena_claves_no_escapa_y_termina_en_salto_de_linea(
    tmp_path: Path,
) -> None:
    raiz = repo(tmp_path / "repo")
    fuentes_minimas(raiz)
    _generar(raiz, tmp_path / "datos")

    texto = (tmp_path / "datos" / "tenants/stonecroft/clauses/STO-PAP-2026.json").read_bytes()

    assert texto.endswith(b"}\n")
    assert b"\r" not in texto
    assert "raya — para ver".encode() in texto
    claves = [
        linea.strip().split(b'"')[1] for linea in texto.splitlines() if linea.startswith(b'  "')
    ]
    assert claves == sorted(claves)


# --- BR1.2: anadir una salida no cambia las demas -----------------------------


def test_anadir_una_salida_no_cambia_los_bytes_de_las_demas(tmp_path: Path) -> None:
    raiz = repo(tmp_path / "repo")
    fuentes_minimas(raiz)
    _generar(raiz, tmp_path / "antes")
    # La nueva poliza consume su propio flujo de azar, y va primero a proposito:
    # si el azar fuera uno solo para toda la generacion, moveria el de la otra.
    _generar(raiz, tmp_path / "despues", (poliza_con_azar("POL-100043"), *COMPOSITORES))

    antes, despues = _foto(tmp_path / "antes"), _foto(tmp_path / "despues")
    nueva = "tenants/stonecroft/issued_policies/POL-100043.json"
    assert set(despues) - set(antes) == {nueva}
    for ruta in antes:
        if ruta != "manifest.json":
            assert despues[ruta] == antes[ruta], ruta


# --- BR1.4: el manifiesto y su comprobacion (TECH-U7.2) -----------------------


def test_el_manifiesto_registra_semilla_version_y_hashes_de_entradas_y_salidas(
    tmp_path: Path,
) -> None:
    raiz = repo(tmp_path)
    fuentes_minimas(raiz)
    _generar(raiz, raiz / "app" / "data")

    registrado = GenerationManifest.model_validate_json(
        (raiz / "app/data/manifest.json").read_bytes()
    )

    assert registrado.seed == 20260916
    assert registrado.generator_version == manifest.GENERATOR_VERSION
    assert set(registrado.inputs) == {
        "app/data/sources/stonecroft/es/part_a.yaml",
        "app/config/tenants/knotwell/tenant.yaml",
        "app/config/tenants/stonecroft/tenant.yaml",
        "app/config/tenants/sunmeadow/tenant.yaml",
    }
    salida = "app/data/tenants/stonecroft/clauses/STO-PAP-2026.json"
    contenido = (raiz / salida).read_bytes()
    assert registrado.outputs[salida] == sha256_hex(contenido)
    assert b"generated_at" not in (raiz / "app/data/manifest.json").read_bytes()
    assert manifest.verify_tree(raiz) == []


def test_schema_check_nombra_una_salida_editada_a_mano_y_una_fuente_sin_regenerar(
    tmp_path: Path,
) -> None:
    raiz = repo(tmp_path)
    fuentes_minimas(raiz)
    _generar(raiz, raiz / "app" / "data")
    salida = raiz / "app/data/tenants/stonecroft/clauses/STO-PAP-2026.json"
    salida.write_bytes(salida.read_bytes().replace(b"Relleno", b"Corregido"))
    escribir_fuente(
        raiz,
        [entrada(part="Parte B", source_id="STO-PAP-2026-B.INS", clause_key="B.INS")],
        parte="part_b",
    )

    problemas = "\n".join(manifest.verify_tree(raiz))

    assert (
        "'app/data/tenants/stonecroft/clauses/STO-PAP-2026.json': su hash no es el del manifiesto"
    ) in problemas
    assert (
        "'app/data/sources/stonecroft/es/part_b.yaml': fuente que el manifiesto no cuenta"
        in problemas
    )


# --- BR2.2 y validar antes de escribir: si algo falla, no se escribe nada ------


def test_una_fuente_sin_marca_de_revision_detiene_todo_y_no_toca_lo_generado(
    tmp_path: Path,
) -> None:
    raiz = repo(tmp_path)
    fuentes_minimas(raiz)
    datos = raiz / "app" / "data"
    _generar(raiz, datos)
    antes = _foto(datos)
    escribir_fuente(
        raiz,
        [entrada(source_id="STO-PAP-2026-C.INS", clause_key="C.INS", reviewed_by=None)],
        parte="part_c",
    )

    with pytest.raises(GenerationError) as error:
        _generar(raiz, datos)

    assert (
        "'app/data/sources/stonecroft/es/part_c.yaml': texts[0].reviewed_by (STO-PAP-2026-C.INS): "
        "falta 'reviewed_by'"
    ) in "\n".join(error.value.problems)
    assert _foto(datos) == antes


def test_un_problema_de_la_composicion_o_una_salida_invalida_no_escriben_nada(
    tmp_path: Path,
) -> None:
    raiz = repo(tmp_path)
    fuentes_minimas(raiz)

    def con_problema(_: CompositionContext) -> Composition:
        return Composition(problems=("'STO-PAP-2026-END-9': el endoso no existe",))

    def con_salida_invalida(_: CompositionContext) -> Composition:
        return Composition(
            outputs=(CorpusOutput("tenants/stonecroft/forms/X.json", {"form_id": "X"}),)
        )

    for compositor in (con_problema, con_salida_invalida):
        datos = tmp_path / compositor.__name__
        with pytest.raises(GenerationError):
            _generar(raiz, datos, (*COMPOSITORES, compositor))
        assert not datos.exists()


def test_una_salida_no_puede_escribir_en_las_fuentes_ni_repetirse(tmp_path: Path) -> None:
    raiz = repo(tmp_path)
    fuentes_minimas(raiz)

    def invasor(_: CompositionContext) -> Composition:
        ruta = "sources/stonecroft/es/part_a.yaml"
        return Composition(outputs=(CorpusOutput(ruta, {"x": 1}),))

    with pytest.raises(GenerationError) as error:
        _generar(raiz, tmp_path / "datos", (*COMPOSITORES, invasor, COMPOSITORES[0]))

    problemas = "\n".join(error.value.problems)
    assert "el generador nunca escribe en sources/" in problemas
    assert "dos piezas escriben la misma salida" in problemas


# --- Lo que el generador borra y lo que no ------------------------------------


def test_lo_que_ya_no_se_genera_se_borra_y_lo_ajeno_detiene_la_generacion(
    tmp_path: Path,
) -> None:
    raiz = repo(tmp_path)
    fuentes_minimas(raiz)
    datos = raiz / "app" / "data"
    _generar(raiz, datos, (*COMPOSITORES, poliza_con_azar("POL-100043")))

    informe = generator.generate(
        GenerationRequest(repo_root=raiz, data_dir=datos, composers=COMPOSITORES)
    )
    assert informe.deleted == ("tenants/stonecroft/issued_policies/POL-100043.json",)
    assert manifest.verify_tree(raiz) == []

    ajeno = datos / "fixtures" / "escrita_a_mano.json"
    ajeno.parent.mkdir()
    ajeno.write_text("{}\n", encoding="utf-8")
    (datos / ".DS_Store").write_bytes(b"\x00")
    with pytest.raises(GenerationError, match="el generador no lo escribio"):
        _generar(raiz, datos)
    assert ajeno.is_file()


# --- BR1.5 y SEC-U7.5: sin modelo y sin claves --------------------------------


def test_generar_con_el_entorno_vacio_y_la_fabrica_espiada_no_hace_ninguna_llamada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for variable in [v for v in os.environ if v.startswith("UNTANGLE_")]:
        monkeypatch.delenv(variable)
    llamadas: list[str] = []

    def espia(nombre: str) -> object:
        def registrar(*_: object, **__: object) -> None:
            llamadas.append(nombre)
            raise AssertionError(f"el generador llamo a {nombre}")

        return registrar

    monkeypatch.setattr(factory.ProviderClients, "__init__", espia("ProviderClients"))
    monkeypatch.setattr(factory.ProviderClients, "send", espia("ProviderClients.send"))
    monkeypatch.setattr(factory.SpeechClients, "__init__", espia("SpeechClients"))
    monkeypatch.setattr(settings.Settings, "__init__", espia("Settings"))
    raiz = repo(tmp_path)
    fuentes_minimas(raiz)

    assert cli.run_generate(raiz, raiz / "app" / "data", COMPOSITORES) == 0

    assert llamadas == []
    assert (raiz / "app/data/manifest.json").is_file()


# --- La comparacion de `synthetic:check` (TECH-U7.1) --------------------------


def test_check_pasa_con_lo_generado_y_nombra_cada_archivo_que_difiere(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raiz = repo(tmp_path)
    fuentes_minimas(raiz)
    datos = raiz / "app" / "data"
    _generar(raiz, datos)
    assert cli.run_check(raiz, datos, COMPOSITORES) == 0

    (datos / "tenants/stonecroft/issued_policies/POL-100042.json").write_text(
        "{}\n", encoding="utf-8"
    )
    shutil.rmtree(datos / "tenants/stonecroft/clauses")

    assert cli.run_check(raiz, datos, COMPOSITORES) == 1
    salida = capsys.readouterr()
    assert "'app/data/tenants/stonecroft/issued_policies/POL-100042.json': difiere" in salida.err
    assert (
        "'app/data/tenants/stonecroft/clauses/STO-PAP-2026.json': el generador lo produce y no "
        "esta versionado"
    ) in salida.err
    assert "synthetic:check: duracion" in salida.out


def test_sin_compositores_generate_y_check_se_niegan_sin_escribir(tmp_path: Path) -> None:
    raiz = repo(tmp_path)
    fuentes_minimas(raiz)

    assert cli.run_generate(raiz, raiz / "app" / "data", ()) == 2
    assert cli.run_check(raiz, raiz / "app" / "data", ()) == 2
    assert not (raiz / "app/data/manifest.json").exists()


# --- Lo que `schema:check` dice en los casos de borde (TECH-U7.2) --------------


def test_sin_corpus_no_hay_nada_que_comprobar_y_se_dice_no_medido(tmp_path: Path) -> None:
    raiz = repo(tmp_path)
    datos = raiz / "app" / "data"

    assert manifest.verify_tree(raiz) == []
    aviso = manifest.corpus_notice(datos)
    assert aviso is not None
    assert "no medido" in aviso

    (datos / "tenants").mkdir()
    assert manifest.corpus_notice(datos) is None
    assert manifest.verify_tree(raiz) == [
        "falta 'app/data/manifest.json': hay corpus y nada dice de que entradas salio (BR1.4). "
        "Regenerelo con `mise run synthetic:generate`"
    ]


def test_un_manifiesto_ilegible_o_desalineado_se_nombra(tmp_path: Path) -> None:
    raiz = repo(tmp_path)
    fuentes_minimas(raiz)
    datos = raiz / "app" / "data"
    _generar(raiz, datos)

    (datos / "tenants/stonecroft/issued_policies/POL-100042.json").unlink()
    configuracion = raiz / "app/config/tenants/stonecroft/tenant.yaml"
    configuracion.write_text(configuracion.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    problemas = "\n".join(manifest.verify_tree(raiz))
    assert (
        "'app/data/tenants/stonecroft/issued_policies/POL-100042.json': el manifiesto la lista "
        "como salida y no existe"
    ) in problemas
    assert (
        "'app/config/tenants/stonecroft/tenant.yaml': la entrada cambio despues de generar"
        in problemas
    )

    (datos / "manifest.json").write_text('{"manifest_version": 7}\n', encoding="utf-8")
    assert "'app/data/manifest.json': manifest_version" in "\n".join(manifest.verify_tree(raiz))


# --- Los comandos del archivo de tareas ---------------------------------------


@pytest.mark.parametrize("comando", ["fingerprints", "seed"])
def test_las_huellas_y_la_siembra_no_viven_en_el_comando_del_generador(
    comando: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """El generador no conoce `tmp/` ni la base: el comando de las huellas vive en
    `untangle.workspace` y el de la siembra en la raiz de composicion (FD-U7-9)."""
    with pytest.raises(SystemExit) as salida:
        cli.main([comando])

    assert salida.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


@pytest.mark.parametrize("comando", ["generate", "check"])
def test_sin_compositores_registrados_el_comando_se_niega_y_no_escribe(
    comando: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Sobre un repositorio temporal: correr las pruebas nunca escribe en app/data/ (BR1.3)."""
    raiz = repo(tmp_path)
    fuentes_minimas(raiz)
    monkeypatch.setenv("UNTANGLE_REPO_ROOT", str(raiz))
    monkeypatch.setattr(cli, "CORPUS_COMPOSERS", ())

    assert cli.main([comando]) == 2
    assert "no hay ningun compositor del corpus registrado" in capsys.readouterr().err
    assert not (raiz / "app/data/manifest.json").exists()


def test_una_generacion_que_falla_lo_informa_y_sale_con_uno(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raiz = repo(tmp_path)
    escribir_fuente(raiz, [entrada(reviewed_at=None)])

    assert cli.run_generate(raiz, raiz / "app" / "data", COMPOSITORES) == 1
    assert cli.run_check(raiz, raiz / "app" / "data", COMPOSITORES) == 1
    salida = capsys.readouterr().err
    assert "falta 'reviewed_at'" in salida
    assert "no se escribio nada" in salida
