"""El ciclo de la llamada con la boca de la llamada abierta (2026-10-13).

`SessionVoice` es una voz que mantiene su conexion abierta durante toda la llamada. Lo que se
prueba aqui es lo que el ciclo tiene que hacer para que eso funcione sin romper nada:

- abrir la sesion **una vez**, antes de la apertura, y que todas las frases salgan por ella;
- cerrarla siempre, tambien cuando la llamada falla;
- **cerrar el flujo de una frase interrumpida antes de decir la siguiente**. Con la conexion
  abierta, la frase nueva espera a que la anterior suelte el canal, asi que la frase de
  cortesia de una interrupcion --que antes se decia con la interrumpida todavia abierta-- se
  habria quedado esperando para siempre. Es el defecto que esta prueba atrapa, y la boca de
  prueba lo reproduce: dice una frase a la vez, con una cerradura.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from dataclasses import dataclass, field, replace

import pytest

from untangle.base import Locale
from untangle.compliance.redaction.api import Redacted, from_catalog
from untangle.copy_catalog import api as copy_api
from untangle.telemetry.spend.models import VoiceMode
from untangle.tenancy import config as tenancy_config
from untangle.voice import api as voz
from untangle.voice.call import Utterance
from untangle.voice.loop import CallSpeech, SessionVoice

from ...unit.voice.dobles import final as final_con_tiempos
from .test_call_loop import SILENCIO, CanalFalso, VozDoble, _correr, _motor

pytestmark = pytest.mark.usefixtures("base_de_u16")


@pytest.fixture
def catalogo() -> None:
    copy_api.install(copy_api.load())
    tenancy_config.install(tenancy_config.load())


@dataclass
class BocaDeUnaFraseALaVez:
    """La boca de una llamada que dice una frase a la vez, como el canal de Cartesia.

    La segunda frase espera a que la primera suelte la cerradura, que solo ocurre cuando su
    flujo se cierra o se agota. Si el ciclo dejara un flujo abierto y pidiera otra frase, la
    prueba se quedaria esperando y caeria por tiempo.
    """

    trozos: int = 3
    dicho: list[str] = field(default_factory=list)
    idiomas: list[Locale] = field(default_factory=list)
    #: Cuantas frases se han empezado a leer y todavia no se cierran, como mucho a la vez.
    abiertas_a_la_vez: int = 0
    #: Cuantas hay abiertas ahora mismo.
    abiertas_ahora: int = 0
    explota_en_la_frase: int | None = None
    _cerradura: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _abiertas: int = field(default=0, init=False)

    async def _decir(self, text: Redacted) -> AsyncIterator[bytes]:
        async with self._cerradura:
            self._abiertas += 1
            self.abiertas_ahora = self._abiertas
            self.abiertas_a_la_vez = max(self.abiertas_a_la_vez, self._abiertas)
            try:
                self.dicho.append(str(text))
                if self.explota_en_la_frase == len(self.dicho):
                    msg = "la sintesis se cayo"
                    raise RuntimeError(msg)
                for _ in range(self.trozos):
                    yield b"\x00\x01" * 240
            finally:
                self._abiertas -= 1
                self.abiertas_ahora = self._abiertas

    def speak(
        self, tenant_id: str, text: Redacted, *, mode: VoiceMode, language: Locale
    ) -> AsyncIterator[bytes]:
        del tenant_id, mode
        self.idiomas.append(language)
        return self._decir(text)


@dataclass
class VozConSesion(VozDoble):
    """Un `VozDoble` que ofrece la sesion de la llamada: la boca esta detras de ella.

    `speak` suelto sigue existiendo (es parte de `CallVoice`) pero aqui **no debe usarse**:
    si el ciclo lo usara con una sesion disponible, `dicho_suelto` lo delataria.
    """

    boca: BocaDeUnaFraseALaVez = field(default_factory=BocaDeUnaFraseALaVez)
    aperturas: int = 0
    cierres: int = 0
    pedidas: list[tuple[str, VoiceMode, Locale]] = field(default_factory=list)
    dicho_suelto: list[str] = field(default_factory=list)

    @contextlib.asynccontextmanager
    async def speech_session(
        self, tenant_id: str, *, mode: VoiceMode, language: Locale
    ) -> AsyncIterator[CallSpeech]:
        self.aperturas += 1
        self.pedidas.append((tenant_id, mode, language))
        try:
            yield self.boca
        finally:
            self.cierres += 1

    def speak(
        self, tenant_id: str, text: Redacted, *, mode: VoiceMode, language: Locale
    ) -> AsyncIterator[bytes]:
        self.dicho_suelto.append(str(text))
        return super().speak(tenant_id, text, mode=mode, language=language)


def test_la_voz_de_prueba_ofrece_la_sesion_y_la_suelta_no() -> None:
    assert isinstance(VozConSesion(), SessionVoice)
    assert not isinstance(VozDoble(), SessionVoice)


async def test_la_sesion_se_abre_una_vez_con_la_llamada_y_todas_las_frases_salen_por_ella(
    catalogo: None,
) -> None:
    motor = await _motor()
    doble = VozConSesion()
    canal = CanalFalso(entrantes=[voz.Hangup()])

    motivo = await asyncio.wait_for(_correr(motor, canal, doble).run(), timeout=5)

    assert motivo is voz.EndReason.HANGUP
    assert doble.aperturas == 1
    assert doble.pedidas == [(motor.call.tenant_id, motor.call.voice_mode, motor.language)]
    assert doble.boca.dicho, "la apertura no salio por la sesion"
    assert "transcrib" in doble.boca.dicho[0].lower()
    assert doble.dicho_suelto == [], "una frase salio por la voz suelta con la sesion abierta"
    assert doble.cierres == 1


async def test_la_sesion_se_cierra_tambien_cuando_la_llamada_falla(catalogo: None) -> None:
    motor = await _motor()
    doble = VozConSesion(boca=BocaDeUnaFraseALaVez(explota_en_la_frase=1))
    canal = CanalFalso(entrantes=[SILENCIO], seguir=lambda: True)

    motivo = await asyncio.wait_for(_correr(motor, canal, doble).run(), timeout=5)

    assert motivo is voz.EndReason.ERROR
    assert doble.aperturas == 1
    assert doble.cierres == 1, "una llamada que falla dejo la conexion abierta"


async def test_la_sesion_se_cierra_si_cancelan_la_llamada(catalogo: None) -> None:
    motor = await _motor()
    doble = VozConSesion()
    canal = CanalFalso(entrantes=[SILENCIO], seguir=lambda: True)
    llamada = asyncio.create_task(_correr(motor, canal, doble).run())
    async with asyncio.timeout(5):
        while not doble.boca.dicho:  # noqa: ASYNC110 -- la condicion es algo que ya paso (la apertura sono), no un evento que el ciclo pueda avisar
            await asyncio.sleep(0)

    llamada.cancel()
    with pytest.raises(asyncio.CancelledError):
        await llamada

    assert doble.cierres == 1


async def test_una_interrupcion_cierra_la_frase_cortada_antes_de_decir_la_siguiente(
    catalogo: None,
) -> None:
    """La persona corta a la agente en plena apertura: el flujo de esa frase se cierra, y la
    apertura repetida --y la frase de cortesia, si la hay-- salen por la misma sesion, una a la
    vez. Con el defecto de antes (la frase de cortesia se decia con el flujo cortado todavia
    abierto) esta llamada no terminaba."""
    motor = await _motor()
    doble = VozConSesion(guion=[final_con_tiempos("wait I need to correct something")])
    doble.antes_del_audio = True
    canal = CanalFalso(entrantes=[SILENCIO], seguir=lambda: len(doble.boca.dicho) < 2)

    await asyncio.wait_for(_correr(motor, canal, doble).run(), timeout=5)

    assert canal.de_tipo(voz.StopAudio), "no se mando la orden de vaciar la cola"
    assert len(doble.boca.dicho) >= 2, "la apertura cortada no se repitio por la misma sesion"
    assert doble.boca.abiertas_a_la_vez == 1, "dos frases a la vez por una sola conexion"
    assert doble.aperturas == 1
    assert doble.dicho_suelto == []


async def test_la_frase_interrumpida_queda_cerrada_cuando_el_ciclo_sigue(catalogo: None) -> None:
    """Con la conexion de la llamada abierta, una frase que se deja de leer a medias tiene que
    cerrarse **ya**, en la tarea que la leia: si quedara abierta, la siguiente esperaria a que
    el recolector la recoja. Aqui se mira en el instante en que `_decir` devuelve."""
    motor = await _motor()
    doble = VozConSesion(boca=BocaDeUnaFraseALaVez(trozos=50))
    ciclo = _correr(motor, CanalFalso(), doble)
    ciclo._oido.put_nowait(final_con_tiempos("wait I need to correct something"))

    async with ciclo._con_la_boca_abierta():
        interrumpida = await asyncio.wait_for(ciclo._decir(motor.opening()), timeout=5)
        abiertas_al_volver = doble.boca.abiertas_ahora

    assert interrumpida
    assert abiertas_al_volver == 0, "la frase cortada siguio abierta tras la interrupcion"


async def test_la_frase_de_cortesia_de_una_interrupcion_sale_despues_de_cerrar_la_cortada(
    catalogo: None,
) -> None:
    """Antes se decia con la interrumpida todavia abierta: con una sola conexion la frase
    nueva espera a que la anterior suelte el canal, y la llamada se quedaba colgada."""
    motor = await _motor()
    cortesia = Utterance(text=from_catalog("Go ahead.", language="en"))
    motor.on_barge_in = lambda *_a, **_k: cortesia  # type: ignore[method-assign]
    doble = VozConSesion(boca=BocaDeUnaFraseALaVez(trozos=50))
    ciclo = _correr(motor, CanalFalso(), doble)
    ciclo._oido.put_nowait(final_con_tiempos("wait I need to correct something"))

    async with ciclo._con_la_boca_abierta():
        interrumpida = await asyncio.wait_for(ciclo._decir(motor.opening()), timeout=5)

    assert interrumpida
    assert doble.boca.dicho[-1] == "Go ahead."
    assert doble.boca.abiertas_a_la_vez == 1


async def test_el_cambio_de_idioma_se_dice_en_el_idioma_nuevo_por_la_misma_sesion(
    catalogo: None,
) -> None:
    """La voz se elige por idioma en cada frase, no al abrir la sesion."""
    motor = await _motor()
    doble = VozConSesion()
    ciclo = _correr(motor, CanalFalso(), doble)

    async with ciclo._con_la_boca_abierta():
        await ciclo._decir(motor.opening())
        motor.call = replace(motor.call, language="es")
        await ciclo._decir(motor.opening())

    assert doble.boca.idiomas == ["en", "es"]
    assert doble.aperturas == 1


async def test_con_una_voz_sin_sesion_las_frases_salen_por_la_voz_suelta(catalogo: None) -> None:
    motor = await _motor()
    doble = VozDoble()
    canal = CanalFalso(entrantes=[voz.Hangup()])
    ciclo = _correr(motor, canal, doble)

    motivo = await asyncio.wait_for(ciclo.run(), timeout=5)

    assert motivo is voz.EndReason.HANGUP
    assert doble.dicho, "la apertura no sono"
    assert ciclo._habla is None
