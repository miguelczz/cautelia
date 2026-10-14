"""La superficie de C-20: lo que U12 y U14 consumen de U10 (BR1.5, BR1.6, BR3.3, TECH-U10.1).

Aqui se prueba lo que la superficie anade a la logica pura: que la guardia deja
rastro de cada intervencion **sin la frase**, que falla cerrado tambien cuando lo
que no se puede leer es la configuracion de las aseguradoras, que la frase de
emergencia es la publica salvo que el despliegue diga otra cosa, y que un
archivo de patrones roto impide construir la aplicacion.
"""

from __future__ import annotations

import io
import json
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml

from untangle import observability, paths
from untangle.compliance.controls import api, patterns, phrases
from untangle.compliance.controls.models import InterventionAction
from untangle.server import composition
from untangle.settings import Settings
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.models import TenantConfig


@pytest.fixture
def eventos() -> Iterator[io.StringIO]:
    """Los eventos que emite el punto unico, capturados para leerlos."""
    salida = io.StringIO()
    observability.set_stream(salida)
    try:
        yield salida
    finally:
        observability.set_stream(sys.stdout)


def _leidos(salida: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(linea) for linea in salida.getvalue().splitlines() if linea]


async def test_la_guardia_deja_un_evento_por_intervencion_sin_la_frase(
    aseguradoras: tuple[TenantConfig, ...], eventos: io.StringIO
) -> None:
    """BR1.6: la categoria, el patron y la accion; nunca la frase."""
    frase = "Sí, fue culpa suya y le van a pagar 900 dólares."

    resultado = await api.guard_output(
        frase, tenant_id=aseguradoras[0].tenant_id, language="es", case_id="caso-1"
    )

    intervenidos = [e for e in _leidos(eventos) if e["event"] == "compliance.guard_intervened"]
    assert len(intervenidos) == len(resultado.interventions) == 2
    assert {e["category"] for e in intervenidos} == {"fault", "amount"}
    assert all(e["case_id"] == "caso-1" for e in intervenidos)
    assert "culpa" not in eventos.getvalue()
    assert "900" not in eventos.getvalue()


async def test_sin_la_configuracion_de_las_aseguradoras_falla_cerrado(
    aseguradoras: tuple[TenantConfig, ...],
    eventos: io.StringIO,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BR1.5: si no se puede evaluar la revelacion, la frase no sale."""

    def configuracion_rota() -> tenancy_config.LoadedTenants:
        msg = "no se pudo leer la configuracion"
        raise OSError(msg)

    monkeypatch.setattr(tenancy_config, "loaded", configuracion_rota)
    frase = "Le cuento lo que tengo configurado."

    resultado = await api.guard_output(frase, tenant_id=aseguradoras[0].tenant_id, language="en")

    assert resultado.evaluated is False
    assert resultado.text_out == phrases.degraded_text(locale="en")
    assert [i.action for i in resultado.interventions] == [InterventionAction.NOT_EVALUABLE]
    fallos = [e for e in _leidos(eventos) if e["event"] == "compliance.guard_not_evaluable"]
    assert [e["error_type"] for e in fallos] == ["OSError"]


async def test_las_senales_del_turno_por_la_superficie(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    assert await api.detect_human_request("¿Puedo hablar con un ajustador?")
    assert not await api.detect_human_request("Hablé con un ajustador ayer.")
    assert await api.detect_identity_question("Are you a real person?")
    assert await api.detect_emergency("Mi acompañante está inconsciente.")
    assert not await api.detect_emergency("Fue un golpecito.")
    senales = await api.read_turn_signals("Quiero hablar con una persona.")
    assert (senales.human_request, senales.identity_question, senales.emergency) == (
        True,
        False,
        False,
    )


@pytest.mark.parametrize(
    ("valor", "clave", "fragmento"),
    [
        # Sin la variable, y con la variable vacia de una plantilla copiada tal cual.
        (None, phrases.EMERGENCY_PUBLIC, "no puede enviar ayuda"),
        ("", phrases.EMERGENCY_PUBLIC, "no puede enviar ayuda"),
        ("public", phrases.EMERGENCY_PUBLIC, "no puede enviar ayuda"),
        ("local", phrases.EMERGENCY_LOCAL, "911"),
    ],
)
def test_la_frase_de_emergencia_es_la_publica_salvo_que_el_despliegue_diga_local(
    monkeypatch: pytest.MonkeyPatch, valor: str | None, clave: str, fragmento: str
) -> None:
    """BR3.3, CG-U10-2: lo seguro cuando nadie dijo nada es decir que no se envia ayuda."""
    if valor is None:
        monkeypatch.delenv("UNTANGLE_EMERGENCY_PHRASE", raising=False)
    else:
        monkeypatch.setenv("UNTANGLE_EMERGENCY_PHRASE", valor)

    modo = api.EmergencyPhraseMode(Settings().emergency_phrase)
    obtenida, texto = api.emergency_instruction(modo, language="es")

    assert obtenida == clave
    assert fragmento in texto


def test_una_frase_de_emergencia_desconocida_impide_arrancar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un valor mal escrito no cae en silencio en ninguna de las dos: falla al leerlo."""
    monkeypatch.setenv("UNTANGLE_EMERGENCY_PHRASE", "publica")

    with pytest.raises(ValueError, match="emergency_phrase"):
        Settings()


def test_la_respuesta_de_identidad_sale_del_catalogo_en_su_idioma() -> None:
    clave_es, texto_es = api.identity_answer(language="es")
    clave_en, texto_en = api.identity_answer(language="en")

    assert clave_es == clave_en == phrases.IDENTITY_ANSWER
    assert texto_es.startswith("No, soy una asistente de inteligencia artificial")
    assert texto_en.startswith("No, I'm an AI assistant")


def test_un_archivo_de_patrones_roto_impide_construir_la_aplicacion(
    patrones_copiados: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TECH-U10.1: el proceso no arranca, nombrando el archivo y el patron."""
    archivo = patrones_copiados / "en" / "emergency.yaml"
    datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    datos["patterns"][0]["regex"] = "(sin cerrar"
    archivo.write_text(yaml.safe_dump(datos), encoding="utf-8")
    monkeypatch.setattr(paths, "compliance_dir", lambda: patrones_copiados)

    with pytest.raises(patterns.PatternLoadError) as error:
        composition.build_app(Settings(database_url=None))

    assert str(archivo) in str(error.value)
    assert "emergency.en.signal.001" in str(error.value)
