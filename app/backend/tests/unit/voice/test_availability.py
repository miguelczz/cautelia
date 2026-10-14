"""Por que no hay voz, y que frase acompana a cada motivo (C-08, V15 de la auditoria)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from untangle import paths
from untangle.base import Locale
from untangle.copy_catalog import api as copy_api
from untangle.voice.availability import OFF_CODE_KEYS, VoiceOffCode, all_copy_keys

pytestmark = pytest.mark.usefixtures("catalogo_cargado")

IDIOMAS: tuple[Locale, ...] = ("es", "en")

#: La pantalla que resuelve estas claves cuando el motivo llega en el 503 de abrir la
#: llamada y no como `reason_key`.
_TABLA_DE_LA_CONSOLA = Path("app") / "frontend" / "src" / "pages" / "voice" / "voice-copy.ts"


def test_cada_motivo_tiene_su_clave() -> None:
    """Un motivo nuevo sin clave tiene que fallar aqui y no salir vacio en pantalla.
    `provider_unavailable` es el unico sin clave propia: su causa la trae la
    disponibilidad de U15 con el motivo."""
    sin_clave = set(VoiceOffCode) - set(OFF_CODE_KEYS)

    assert sin_clave == {VoiceOffCode.PROVIDER_UNAVAILABLE}


@pytest.mark.parametrize("language", IDIOMAS)
def test_cada_motivo_dice_una_cosa_distinta(language: Locale) -> None:
    """V15: la consola decia "la voz esta apagada" ante cualquier rechazo. Con dos
    motivos que compartieran frase, el conjunto cerrado dejaria de servir para lo unico
    que existe, que es decir **cual** fue."""
    frases = {codigo: copy_api.t(clave, locale=language) for codigo, clave in OFF_CODE_KEYS.items()}

    assert len(set(frases.values())) == len(frases), frases


@pytest.mark.parametrize("language", IDIOMAS)
def test_ninguna_frase_de_un_limite_dice_que_la_voz_esta_apagada(language: Locale) -> None:
    """Ni inventa una cifra: dice de quien es el limite y cuando vuelve a haber cupo."""
    apagada = copy_api.t(copy_api.CopyKey("voice.console.unavailable"), locale=language)

    for codigo in (VoiceOffCode.RATE_LIMITED_DAILY, VoiceOffCode.RATE_LIMITED_SITE):
        frase = copy_api.t(OFF_CODE_KEYS[codigo], locale=language)
        assert apagada.lower() not in frase.lower()
        assert not re.search(r"\d", frase), frase


def test_el_limite_de_la_conexion_y_el_del_sitio_se_distinguen() -> None:
    """La primera frase es de quien llama ("desde esta conexion"); la segunda, de todos."""
    diario = copy_api.t(OFF_CODE_KEYS[VoiceOffCode.RATE_LIMITED_DAILY], locale="es")
    sitio = copy_api.t(OFF_CODE_KEYS[VoiceOffCode.RATE_LIMITED_SITE], locale="es")

    assert "esta conexión" in diario and "mañana" in diario
    assert "demostración" in sitio and "mañana" in sitio
    assert "esta conexión" not in sitio


def test_las_claves_que_el_servidor_manda_estan_todas_en_la_lista_de_la_consola() -> None:
    claves = {str(c) for c in all_copy_keys()}

    assert {str(c) for c in OFF_CODE_KEYS.values()} <= claves


def test_la_consola_resuelve_cada_motivo_de_abrir_la_llamada_con_la_clave_del_servidor() -> None:
    """Abrir la llamada responde el motivo como `code` y la consola lo lleva a una clave
    con su propia tabla. Que las dos tablas no se separen es lo que se comprueba aqui:
    leer el `reason_key` de un lado y el `code` del otro no puede decir dos cosas."""
    tabla = (paths.repo_root() / _TABLA_DE_LA_CONSOLA).read_text(encoding="utf-8")

    for codigo, clave in OFF_CODE_KEYS.items():
        assert re.search(rf'\b{codigo.value}:\s*"{re.escape(str(clave))}"', tabla), (
            f"{codigo.value} no apunta a '{clave}' en {_TABLA_DE_LA_CONSOLA.as_posix()}"
        )
    assert re.search(rf"\b{VoiceOffCode.PROVIDER_UNAVAILABLE.value}:\s*null", tabla)
