"""Una sola conexion de sintesis por llamada: la sesion de Cartesia (2026-10-13).

Conectar con Cartesia desde Colombia cuesta de 0,7 a 0,8 s y se pagaba delante de cada
frase. La sesion abre el canal una vez y dice las frases de la llamada por el. Lo que estas
pruebas fijan es lo que no puede romperse al compartir el canal:

- que de verdad haya **una** conexion, abierta antes de la primera frase y cerrada al salir;
- que el audio de una frase no se mezcle con el de otra, tampoco cuando la anterior se
  abandono a medias (la persona interrumpio) y Cartesia sigue mandando lo que le quedaba;
- que un fallo de verdad cierre el canal y la frase siguiente abra otro;
- que cada frase conserve lo que garantiza `synthesize`: techo, gasto y taxonomia de errores.

El proveedor es `servidor_falso.py`, que se comporta como lo documenta Cartesia. Ninguna
prueba sale a la red: la guardia de `conftest.py` la haria fallar.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from untangle.base import Locale, ProviderErrorKind, ProviderName, UnitKind
from untangle.providers.adapters.cartesia import CartesiaTextToSpeech
from untangle.providers.adapters.cartesia.tts import SpeechSessionClosedError
from untangle.providers.ports import (
    BudgetExhausted,
    ExhaustedResource,
    ProviderError,
    SpendGate,
    TextToSpeech,
    VoiceRef,
)
from untangle.providers.transport import TransportError

from .apoyo import TIEMPOS, Abierto, Eventos, Registro, redactado, techo
from .servidor_falso import (
    BYTES_POR_TROZO,
    ServidorFalso,
    audio_de_la_frase,
)

CATALINA = "162e0f37-8504-474c-bb33-c606c01890dc"


def _voz(idioma: Locale = "es") -> VoiceRef:
    return VoiceRef(
        provider=ProviderName.CARTESIA, model="sonic-3.6", voice_id=CATALINA, language=idioma
    )


def _tts(
    servidor: ServidorFalso, *, gate: SpendGate | None = None
) -> tuple[CartesiaTextToSpeech, Registro]:
    registro = Registro()
    adaptador = CartesiaTextToSpeech(
        servidor.clientes(),
        gate=gate if gate is not None else Abierto(),
        usage=registro,
        timeouts=TIEMPOS,
    )
    return adaptador, registro


async def _decir(sesion: TextToSpeech, texto: str, idioma: Locale = "es") -> bytes:
    trozos = sesion.synthesize(redactado(texto, idioma), voice=_voz(idioma))
    return b"".join([t async for t in trozos])


def _solo_de(audio: bytes, frase: int) -> bool:
    return audio == audio_de_la_frase(frase) * (len(audio) // BYTES_POR_TROZO)


# --- Una sola conexion -----------------------------------------------------------------


async def test_varias_frases_salen_por_una_sola_conexion() -> None:
    servidor = ServidorFalso()
    tts, registro = _tts(servidor)

    async with tts.open_session() as sesion:
        primera = await _decir(sesion, "Hola, esta es la primera frase.")
        segunda = await _decir(sesion, "Y esta es la segunda.")
        tercera = await _decir(sesion, "Esta es la tercera.")

    assert servidor.aperturas == 1, "cada frase abrio su propia conexion"
    assert len(servidor.recibidos) == 3
    assert len({m["context_id"] for m in servidor.recibidos}) == 3, "un context_id por frase"
    assert _solo_de(primera, 1) and _solo_de(segunda, 2) and _solo_de(tercera, 3)
    assert len(primera) == 3 * BYTES_POR_TROZO
    # Cada frase cuenta sus caracteres, igual que `synthesize`.
    assert [r.units[0].units for r in registro.reports] == [
        Decimal(len("Hola, esta es la primera frase.")),
        Decimal(len("Y esta es la segunda.")),
        Decimal(len("Esta es la tercera.")),
    ]
    assert all(r.units[0].unit_kind is UnitKind.CHARACTERS for r in registro.reports)


async def test_el_canal_se_abre_al_entrar_y_antes_de_la_primera_frase() -> None:
    """Es lo que ahorra la conexion a la propia apertura: se paga mientras la llamada arranca."""
    servidor = ServidorFalso()
    tts, _ = _tts(servidor)

    async with tts.open_session():
        assert servidor.aperturas == 1
        assert servidor.recibidos == [], "todavia no se dijo nada"


async def test_al_salir_se_cierra_el_canal_y_tambien_si_el_cuerpo_falla() -> None:
    servidor = ServidorFalso()
    tts, _ = _tts(servidor)

    async with tts.open_session() as sesion:
        await _decir(sesion, "Una frase.")
    assert servidor.canales[0].cierres == 1

    nuevo = ServidorFalso()
    tts2, _ = _tts(nuevo)
    with pytest.raises(RuntimeError, match="la llamada fallo"):
        async with tts2.open_session():
            raise RuntimeError("la llamada fallo")
    assert nuevo.canales[0].cierres == 1, "una llamada que falla deja la conexion abierta"


async def test_una_sesion_cerrada_no_acepta_frases() -> None:
    servidor = ServidorFalso()
    tts, _ = _tts(servidor)
    async with tts.open_session() as sesion:
        pass

    with pytest.raises(SpeechSessionClosedError):
        await _decir(sesion, "Demasiado tarde.")
    assert servidor.aperturas == 1


async def test_cada_frase_lleva_su_voz_y_su_idioma_por_el_mismo_canal() -> None:
    """El cambio de idioma a mitad de llamada no necesita otra conexion: la voz y el idioma
    viajan en cada mensaje."""
    servidor = ServidorFalso()
    tts, _ = _tts(servidor)

    async with tts.open_session() as sesion:
        await _decir(sesion, "Hola, buenas tardes.", "es")
        await _decir(sesion, "Sure, we can continue in English.", "en")

    assert servidor.aperturas == 1
    assert [m["language"] for m in servidor.recibidos] == ["es", "en"]
    assert {m["voice"]["id"] for m in servidor.recibidos} == {CATALINA}


async def test_dos_frases_pedidas_juntas_salen_una_detras_de_otra_sin_mezclar_el_audio() -> None:
    servidor = ServidorFalso(trozos_por_frase=5)
    tts, _ = _tts(servidor)

    async with tts.open_session() as sesion:
        primera, segunda = await asyncio.gather(
            _decir(sesion, "Esta es una frase."), _decir(sesion, "Y esta es otra frase.")
        )

    assert servidor.aperturas == 1
    assert {bytes(primera), bytes(segunda)} == {
        audio_de_la_frase(1) * 5,
        audio_de_la_frase(2) * 5,
    }


# --- La interrupcion: la frase abandonada no cierra el canal ------------------------------


async def test_una_frase_abandonada_a_medias_deja_el_canal_abierto_para_las_siguientes() -> None:
    """La persona interrumpe a la agente: lo que quedaba por sintetizar se abandona y la frase
    siguiente --la de cortesia, la respuesta-- sale por la misma conexion, sin pagar otra."""
    servidor = ServidorFalso(trozos_por_frase=5)
    tts, registro = _tts(servidor)

    async with tts.open_session() as sesion:
        primera = sesion.synthesize(
            redactado("Una frase larga que van a cortar.", "es"), voice=_voz()
        )
        oidos = [await anext(primera), await anext(primera)]
        await primera.aclose()
        assert servidor.canales[0].cerrado is False, "interrumpir no cierra la conexion"

        siguiente = await _decir(sesion, "Claro, dime.")

    assert len(oidos) == 2
    assert servidor.aperturas == 1
    # Cartesia sigue mandando los trozos y el `done` de la frase cortada: no se cuelan en la
    # siguiente, que suena entera y solo con su propio audio.
    assert _solo_de(siguiente, 2)
    assert len(siguiente) == 5 * BYTES_POR_TROZO
    # La frase cortada tambien se cuenta: el mensaje salio y Cartesia pudo generarla.
    assert registro.reports[0].units[0].units == Decimal(len("Una frase larga que van a cortar."))


async def test_cancelar_la_tarea_que_lee_la_frase_tampoco_cierra_el_canal() -> None:
    servidor = ServidorFalso(trozos_por_frase=4)
    tts, _ = _tts(servidor)

    async with tts.open_session() as sesion:

        async def leer_para_siempre() -> None:
            async for _ in sesion.synthesize(
                redactado("Una frase cualquiera.", "es"), voice=_voz()
            ):
                await asyncio.sleep(10)

        lectora = asyncio.create_task(leer_para_siempre())
        await asyncio.sleep(0.05)
        lectora.cancel()
        with pytest.raises(asyncio.CancelledError):
            await lectora

        siguiente = await asyncio.wait_for(_decir(sesion, "Otra frase."), timeout=5)

    assert servidor.aperturas == 1
    assert _solo_de(siguiente, 2)


# --- Fallos: el canal se cierra y la siguiente frase abre otro ------------------------------


async def test_un_error_del_proveedor_sale_en_la_taxonomia_y_la_frase_siguiente_abre_otro_canal() -> (
    None
):
    servidor = ServidorFalso(error_en={1: 500})
    tts, registro = _tts(servidor)

    async with tts.open_session() as sesion:
        with pytest.raises(ProviderError) as capturado:
            await _decir(sesion, "Esta frase falla.")
        assert capturado.value.kind is ProviderErrorKind.UNAVAILABLE
        assert servidor.canales[0].cerrado, "tras un fallo el estado del canal no se sabe"

        despues = await _decir(sesion, "Esta sale bien.")

    assert servidor.aperturas == 2
    assert _solo_de(despues, 2)
    # El mensaje que fallo tambien cuenta, del lado conservador.
    assert len(registro.reports) == 2


async def test_si_el_proveedor_cierra_el_canal_en_reposo_la_frase_lo_reabre_una_vez() -> None:
    servidor = ServidorFalso()
    tts, registro = _tts(servidor)

    async with tts.open_session() as sesion:
        await _decir(sesion, "La primera.")
        servidor.canales[0].cerrar_desde_el_servidor()
        segunda = await _decir(sesion, "La segunda.")

    assert servidor.aperturas == 2
    assert _solo_de(segunda, 2)
    # El envio que encontro el canal cerrado no salio, asi que no se cuenta dos veces.
    assert [r.units[0].units for r in registro.reports][1] == Decimal(len("La segunda."))


async def test_si_el_canal_se_cae_con_audio_ya_entregado_es_un_fallo_y_no_se_repite_sola() -> None:
    """Media frase repetida no se arregla reabriendo: sale el error de siempre, y quien tiene
    una voz de respaldo (`SpeechPlatform`) la repite entera con ella."""
    servidor = ServidorFalso(cae_tras={1: 1})
    tts, _ = _tts(servidor)

    async with tts.open_session() as sesion:
        with pytest.raises(ProviderError) as capturado:
            await _decir(sesion, "Se corta a la mitad.")

    assert capturado.value.kind is ProviderErrorKind.UNAVAILABLE
    assert servidor.aperturas == 1


# --- Techo, gasto y eventos ----------------------------------------------------------------


async def test_con_el_techo_cerrado_no_se_abre_ningun_canal_ni_se_dice_nada(
    eventos: Eventos,
) -> None:
    servidor = ServidorFalso()
    tts, registro = _tts(servidor, gate=techo(gastado="5.00"))

    async with tts.open_session() as sesion:
        with pytest.raises(BudgetExhausted) as parada:
            await _decir(sesion, "Nada de esto debe salir.")

    assert parada.value.resource is ExhaustedResource.PROJECT_CAP
    assert servidor.aperturas == 0
    assert servidor.recibidos == []
    assert registro.reports == []
    precalentamiento = [e for e in eventos.lineas if e["event"] == "providers.speech_warmup_failed"]
    assert [e["error_type"] for e in precalentamiento] == ["BudgetExhausted"]


async def test_si_el_canal_no_abre_al_entrar_la_primera_frase_lo_intenta_otra_vez() -> None:
    servidor = ServidorFalso(falla_al_abrir=TransportError("OSError", timed_out=False))
    tts, _ = _tts(servidor)

    async with tts.open_session() as sesion:
        servidor.falla_al_abrir = None
        audio = await _decir(sesion, "Ahora si hay red.")

    assert servidor.aperturas == 1
    assert _solo_de(audio, 1)


async def test_el_evento_de_la_primera_frase_dice_si_la_conexion_estaba_abierta_y_no_lleva_texto(
    eventos: Eventos,
) -> None:
    servidor = ServidorFalso()
    tts, _ = _tts(servidor)
    texto = "Una frase con datos que no deben salir en un evento."

    async with tts.open_session() as sesion:
        await _decir(sesion, texto)
        servidor.canales[0].cerrar_desde_el_servidor()
        await _decir(sesion, texto)

    primeros = [e for e in eventos.lineas if e["event"] == "voice.tts_first_chunk"]
    assert [e["connection"] for e in primeros] == ["reused", "opened"]
    assert all(isinstance(e["ms"], int) and e["ms"] >= 0 for e in primeros)
    assert set(primeros[0]) == {"event", "provider", "ms", "connection"}
    assert texto not in eventos.crudo
