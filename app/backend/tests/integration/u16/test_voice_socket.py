"""El socket de C-29: el apreton de manos, y una llamada entera con dobles.

**Se llama a la funcion del socket y no a un servidor.** Es la misma razon por la
que U13 prueba su flujo de eventos llamando al generador: un transporte de
pruebas ASGI no habla WebSocket, y levantar un servidor de verdad para comprobar
que cuatro tokens malos se cierran igual mediria el servidor y no la regla.

Lo que aqui se comprueba:

- que **las cuatro formas de token malo responden identicas** hacia afuera y solo
  se distinguen en la traza del servidor (BR1.5);
- que un socket que se abre y calla se suelta, sin dejar la llamada viva;
- que con el token bueno la llamada arranca: la apertura suena entera, la
  divulgacion queda registrada antes de atender nada (BR2.1) y colgar deja el
  motivo que la consola muestra (BR1.6);
- que el control viaja en texto y el audio en binario, que es lo unico que los
  distingue en el cable.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import orjson
import pytest
from fastapi import FastAPI
from starlette.websockets import WebSocketState

from untangle import observability
from untangle.base import Locale
from untangle.compliance.redaction.api import Redacted
from untangle.copy_catalog import api as copy_api
from untangle.orchestration import contracts as c14
from untangle.providers.ports import ExternalText, Transcript, WordHypothesis
from untangle.providers.voice_availability import VoiceAvailability
from untangle.server import composition, voice_routes
from untangle.settings import Settings
from untangle.telemetry.spend.models import VoiceMode
from untangle.telemetry.traces import api as trazas
from untangle.tenancy import api as tenancy
from untangle.tenancy import ephemeral, session
from untangle.voice import api as voz
from untangle.voice import loop as loop_voz

from ...unit.voice.dobles import con_rastro

pytestmark = pytest.mark.usefixtures("base_de_u16")

CLAVE = "marca-de-clave-del-token-de-voz-que-no-sale-000016"
#: La del enlace de caso, **otra a proposito**: desde que la voz firma con la
#: suya (PENDIENTES 1.16), una prueba que las igualara pasaria con las dos
#: claves cruzadas y no veria el dia que la raiz las vuelva a juntar.
CLAVE_DE_ENLACE = "marca-de-clave-de-enlaces-que-no-debe-salir-000016"


# --- Los dobles ---------------------------------------------------------------


def _final(texto: str) -> Transcript:
    palabras = tuple(
        WordHypothesis(text=ExternalText(p), start_s=i * 0.3, end_s=i * 0.3 + 0.2, confidence=0.95)
        for i, p in enumerate(texto.split())
    )
    return Transcript(text=ExternalText(texto), is_final=True, words=palabras)


@dataclass
class VozDoble:
    """La voz de U15, con el guion que la prueba le da. Cumple `VoicePlatform`.

    Entrega el audio **en trozos** por la misma razon que el doble de la unidad:
    medir una parada contra una sintesis instantanea no mide nada.
    """

    guion: Sequence[Transcript] = ()
    trozos: int = 2
    #: Si el guion sale **antes** de consumir el audio. Es el caso de alguien que
    #: ya esta hablando mientras la agente habla: sin esto no hay interrupcion
    #: que probar, porque el transcrito llegaria cuando ya se dijo todo.
    antes_del_audio: bool = False
    dicho: list[str] = field(default_factory=list)
    bytes_recibidos: int = 0

    def availability_for(self, tenant_id: str) -> VoiceAvailability:
        del tenant_id
        return VoiceAvailability.on()

    async def _oir(self, audio: AsyncIterator[bytes]) -> AsyncIterator[Transcript]:
        if self.antes_del_audio:
            for pieza in self.guion:
                yield pieza
        async for trozo in audio:
            self.bytes_recibidos += len(trozo)
        if not self.antes_del_audio:
            for pieza in self.guion:
                yield pieza

    def listen(
        self, tenant_id: str, audio: AsyncIterator[bytes], *, language: Locale
    ) -> AsyncIterator[Transcript]:
        del tenant_id, language
        return self._oir(audio)

    async def _decir(self, text: Redacted) -> AsyncIterator[bytes]:
        self.dicho.append(str(text))
        for _ in range(self.trozos):
            yield b"\x00\x01" * 240  # 20 ms de PCM16 a 24 kHz

    def speak(
        self, tenant_id: str, text: Redacted, *, mode: VoiceMode, language: Locale
    ) -> AsyncIterator[bytes]:
        del tenant_id, mode, language
        return self._decir(text)


@dataclass
class SocketFalso:
    """Un WebSocket con guion. Lleva la cuenta de lo que salio, y por que puerta."""

    entrantes: list[dict[str, object]] = field(default_factory=list)
    textos: list[dict[str, object]] = field(default_factory=list)
    audios: list[bytes] = field(default_factory=list)
    aceptado: bool = False
    cerrado_con: int | None = None
    client_state: WebSocketState = WebSocketState.CONNECTED

    async def accept(self) -> None:
        self.aceptado = True

    async def receive(self) -> dict[str, object]:
        if not self.entrantes:
            self.client_state = WebSocketState.DISCONNECTED
            return {"type": "websocket.disconnect"}
        return self.entrantes.pop(0)

    async def send_text(self, data: str) -> None:
        self.textos.append(orjson.loads(data))

    async def send_bytes(self, data: bytes) -> None:
        self.audios.append(data)

    async def close(self, code: int = 1000) -> None:
        self.cerrado_con = code
        self.client_state = WebSocketState.DISCONNECTED

    def cuadros(self, tipo: str) -> list[dict[str, object]]:
        return [c for c in self.textos if c.get("type") == tipo]


async def _sin_grafo(turn: c14.InboundTurn) -> AsyncIterator[c14.TurnEvent]:
    """Un grafo que contesta una frase. Lo que se prueba aqui es el transporte."""
    yield c14.FinalText(message_id="m1", text="Anotado.", language=turn.language)


# --- El andamiaje -------------------------------------------------------------


@pytest.fixture
async def app(sesiones: ephemeral.EphemeralDatabase, tmp_path: Path) -> AsyncIterator[FastAPI]:
    """La aplicacion construida: es lo que instala el catalogo y las aseguradoras."""
    construida = composition.build_app(
        Settings(env="local", database_url=sesiones.app_url, case_link_signing_key=CLAVE_DE_ENLACE),
        dist_dir=tmp_path,
    )
    try:
        yield construida
    finally:
        await session.dispose()
        session.configure(sesiones.app_url)
        trazas.reset_summaries()
        copy_api.reset()
        voice_routes.reset()


@pytest.fixture
def voz_doble(app: FastAPI) -> VozDoble:
    del app  # solo para que la aplicacion se construya antes
    doble = VozDoble()
    voice_routes.install(
        voice_routes.VoiceDeps(
            speech=doble,
            handle_turn=con_rastro(_sin_grafo),
            token_signing_key=CLAVE,
            case_link_signing_key=CLAVE_DE_ENLACE,
        )
    )
    return doble


def _aseguradora() -> str:
    return tenancy.available_ids()[0]


def _ahora() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Abierta:
    clave: str
    llamada: voz.CallSession


async def _abrir_llamada() -> Abierta:
    """Una llamada abierta por el camino de produccion, con su caso atado.

    **Se abre con el reloj de verdad y no con `AHORA`**, y eso no es un detalle:
    el ciclo mide la duracion maxima contra el instante en que la llamada
    empezo, asi que una llamada sembrada en una fecha fija nace con sus tres
    minutos ya vencidos y termina por `max_duration` antes de decir nada. Se
    descubrio asi, con dos pruebas esperando `dropped` y recibiendo eso.
    """
    aseguradora = _aseguradora()
    clave = tenancy.new_visitor_key()
    registro = await tenancy.resolve_visitor_key(
        tenant_id=aseguradora, visitor_key=clave, origin="prueba"
    )
    llamada = await voz.open_call(
        tenant_id=aseguradora,
        visitor_key_digest=registro.visitor_key_hash,
        language="en",
        voice_mode=VoiceMode.PRIMARY,
        now=_ahora(),
    )
    case_id = await voz.open_for_call(aseguradora, language="en", now=_ahora())
    return Abierta(clave=clave, llamada=await voz.attach_case(llamada, case_id=case_id))


def _auth(token: str) -> dict[str, object]:
    return {
        "type": "websocket.receive",
        "text": orjson.dumps({"type": "auth", "token": token}).decode(),
    }


def _hangup() -> dict[str, object]:
    return {"type": "websocket.receive", "text": orjson.dumps({"type": "hangup"}).decode()}


def _pcm() -> dict[str, object]:
    return {"type": "websocket.receive", "bytes": b"\x00\x01" * 240}


async def _correr(socket: SocketFalso, clave: str | None) -> None:
    await voice_routes._atender_socket(socket, _aseguradora(), clave)


# --- Los cuatro tokens malos, identicos hacia afuera (BR1.5) ------------------


@pytest.mark.parametrize(
    "hacer_token",
    [
        pytest.param(lambda abierta: None, id="ausente"),
        pytest.param(
            lambda abierta: voz.issue(
                abierta.llamada.call_id, signing_key=CLAVE, now=_ahora() - timedelta(hours=1)
            ),
            id="vencido",
        ),
        pytest.param(
            lambda abierta: voz.issue("call-de-otra-persona", signing_key=CLAVE, now=_ahora()),
            id="de-otra-llamada",
        ),
        pytest.param(
            lambda abierta: (
                voz.issue(abierta.llamada.call_id, signing_key=CLAVE, now=_ahora()) + "x"
            ),
            id="alterado",
        ),
        # El quinto, desde que la voz firma con la suya (PENDIENTES 1.16): un token
        # perfecto en todo --su llamada, su instante, su formato-- firmado con la
        # clave del **enlace de caso**. Es lo que pasaria el dia que la raiz
        # volviera a pasarle esa clave a la voz, y sin esta fila la separacion
        # quedaria declarada en los comentarios y en ninguna prueba.
        pytest.param(
            lambda abierta: voz.issue(
                abierta.llamada.call_id, signing_key=CLAVE_DE_ENLACE, now=_ahora()
            ),
            id="firmado-con-la-clave-del-enlace",
        ),
    ],
)
async def test_los_cinco_tokens_malos_cierran_igual(
    voz_doble: VozDoble, hacer_token: object
) -> None:
    """Distinguirlos hacia afuera le diria a quien prueba cual acerto a medias.

    Lo que se compara es el desenlace entero, no solo el codigo: mismo cierre,
    ninguna llamada marcada viva y ningun cuadro de estado.
    """
    abierta = await _abrir_llamada()
    token = hacer_token(abierta)  # type: ignore[operator]
    entrantes = [] if token is None else [_auth(str(token))]
    socket = SocketFalso(entrantes=entrantes)

    await _correr(socket, abierta.clave)

    assert socket.aceptado is True
    assert socket.cerrado_con == voice_routes.CLOSE_UNAUTHENTICATED
    assert socket.textos == []
    viva = await voz.find_live(
        tenant_id=_aseguradora(), visitor_key_digest=abierta.llamada.visitor_key_digest
    )
    assert viva is not None
    assert viva.state is voz.CallState.CONNECTING
    assert voz_doble.dicho == []


async def test_un_socket_sin_galleta_se_cierra_igual(voz_doble: VozDoble) -> None:
    """Sin galleta no se resuelve ninguna clave, y sin clave no hay llamada que abrir."""
    abierta = await _abrir_llamada()
    socket = SocketFalso(
        entrantes=[_auth(voz.issue(abierta.llamada.call_id, signing_key=CLAVE, now=_ahora()))]
    )

    await _correr(socket, None)

    assert socket.cerrado_con == voice_routes.CLOSE_UNAUTHENTICATED
    assert voz_doble.dicho == []


async def test_un_socket_que_calla_no_deja_la_llamada_viva(voz_doble: VozDoble) -> None:
    """Un socket que se abre y no dice nada se suelta: el flujo se agota y el
    apreton de manos no llega a pasar."""
    abierta = await _abrir_llamada()
    socket = SocketFalso(entrantes=[])

    await _correr(socket, abierta.clave)

    assert socket.cerrado_con == voice_routes.CLOSE_UNAUTHENTICATED
    assert voz_doble.dicho == []


# --- El token bueno: la llamada entera ----------------------------------------


async def test_con_el_token_bueno_la_llamada_arranca_y_dice_la_apertura(
    voz_doble: VozDoble,
) -> None:
    """BR2.1: lo primero que suena es la apertura, y hasta que no queda registrada
    no se atiende nada."""
    abierta = await _abrir_llamada()
    socket = SocketFalso(
        entrantes=[
            _auth(voz.issue(abierta.llamada.call_id, signing_key=CLAVE, now=_ahora())),
            _hangup(),
        ]
    )

    await _correr(socket, abierta.clave)

    assert socket.cerrado_con != voice_routes.CLOSE_UNAUTHENTICATED
    assert voz_doble.dicho, "la apertura no llego a sintetizarse"
    apertura = voz_doble.dicho[0]
    assert "transcrib" in apertura.lower()
    estados = [c["value"] for c in socket.cuadros("state")]
    assert estados[0] == "live"


async def test_colgar_deja_el_motivo_que_la_consola_muestra(voz_doble: VozDoble) -> None:
    """BR1.6: el ultimo cuadro dice por que termino, del conjunto cerrado."""
    abierta = await _abrir_llamada()
    socket = SocketFalso(
        entrantes=[
            _auth(voz.issue(abierta.llamada.call_id, signing_key=CLAVE, now=_ahora())),
            _hangup(),
        ]
    )

    await _correr(socket, abierta.clave)

    finales = socket.cuadros("ended")
    assert [c["reason"] for c in finales] == [voz.EndReason.HANGUP.value]
    viva = await voz.find_live(
        tenant_id=_aseguradora(), visitor_key_digest=abierta.llamada.visitor_key_digest
    )
    assert viva is None


async def test_un_corte_deja_el_caso_retomable_y_colgar_no(voz_doble: VozDoble) -> None:
    """BR6.1: un socket que se cierra sin colgar es una **pausa**, no un final.

    Las dos ramas en la misma prueba a proposito: lo que distingue un corte de un
    colgado es exactamente la ventana de retoma, y comprobar solo una de las dos
    pasaria igual si las dos la dejaran.
    """
    cortada = await _abrir_llamada()
    socket_cortado = SocketFalso(
        entrantes=[
            _auth(voz.issue(cortada.llamada.call_id, signing_key=CLAVE, now=_ahora())),
            _pcm(),
        ]
    )
    await _correr(socket_cortado, cortada.clave)

    colgada = await _abrir_llamada()
    socket_colgado = SocketFalso(
        entrantes=[
            _auth(voz.issue(colgada.llamada.call_id, signing_key=CLAVE, now=_ahora())),
            _hangup(),
        ]
    )
    await _correr(socket_colgado, colgada.clave)

    assert [c["reason"] for c in socket_cortado.cuadros("ended")] == [voz.EndReason.DROPPED.value]
    retomable = await voz.find_resumable(
        tenant_id=_aseguradora(),
        visitor_key_digest=cortada.llamada.visitor_key_digest,
        now=_ahora(),
    )
    assert retomable is not None
    assert retomable.call_id == cortada.llamada.call_id

    sin_retoma = await voz.find_resumable(
        tenant_id=_aseguradora(),
        visitor_key_digest=colgada.llamada.visitor_key_digest,
        now=_ahora(),
    )
    assert sin_retoma is None


async def test_dejar_el_caso_guardado_lo_deja_retomable_con_su_propio_motivo(
    voz_doble: VozDoble, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La despedida de "guardalo" le dice a la persona hasta cuando puede retomarlo, y eso
    solo es cierto si la fila deja abierta la ventana: `silence` y `max_duration` tambien
    dicen "queda guardado" y no la abren."""

    async def guardado(self: voz.CallRunner) -> voz.EndReason:
        return voz.EndReason.SAVED

    monkeypatch.setattr(voz.CallRunner, "run", guardado)
    abierta = await _abrir_llamada()
    socket = SocketFalso(
        entrantes=[
            _auth(voz.issue(abierta.llamada.call_id, signing_key=CLAVE, now=_ahora())),
            _pcm(),
        ]
    )

    await _correr(socket, abierta.clave)

    assert [c["reason"] for c in socket.cuadros("ended")] == [voz.EndReason.SAVED.value]
    retomable = await voz.find_resumable(
        tenant_id=_aseguradora(),
        visitor_key_digest=abierta.llamada.visitor_key_digest,
        now=_ahora(),
    )
    assert retomable is not None
    assert retomable.end_reason is voz.EndReason.SAVED
    ventana = tenancy.require(_aseguradora()).call.resume_window_seconds
    assert retomable.ended_at is not None
    assert retomable.resume_until == retomable.ended_at + timedelta(seconds=ventana)


async def test_la_llamada_de_verdad_enciende_la_muletilla(
    voz_doble: VozDoble, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Por omision el ciclo no dice muletilla --las evaluaciones y las pruebas no la quieren--,
    asi que el unico sitio que la enciende es el que atiende el socket: si deja de pasar la
    constante, la llamada de verdad pierde la muletilla sin que nada falle."""
    vistas: list[object] = []

    async def espia(self: voz.CallRunner) -> voz.EndReason:
        vistas.append(self.filler_after)
        return voz.EndReason.HANGUP

    monkeypatch.setattr(voz.CallRunner, "run", espia)
    abierta = await _abrir_llamada()
    socket = SocketFalso(
        entrantes=[
            _auth(voz.issue(abierta.llamada.call_id, signing_key=CLAVE, now=_ahora())),
            _pcm(),
        ]
    )

    await _correr(socket, abierta.clave)

    assert vistas == [loop_voz.FILLER_AFTER]
    assert loop_voz.FILLER_AFTER == timedelta(milliseconds=350)


async def test_el_control_va_en_texto_y_el_audio_en_binario(voz_doble: VozDoble) -> None:
    """Es lo unico que los distingue en el cable.

    Si los cuadros de control salieran en binario, la consola reproduciria el
    JSON de un `stop_audio` como si fueran muestras. Se comprobo mandandolos por
    la misma puerta y viendo que ninguna prueba se caia: esta es la que lo mira.
    """
    abierta = await _abrir_llamada()
    socket = SocketFalso(
        entrantes=[
            _auth(voz.issue(abierta.llamada.call_id, signing_key=CLAVE, now=_ahora())),
            _hangup(),
        ]
    )

    await _correr(socket, abierta.clave)

    assert socket.textos, "no salio ningun cuadro de control"
    assert socket.audios, "no salio ningun trozo de audio"
    assert all(len(trozo) == 480 for trozo in socket.audios)


async def test_un_cuadro_que_el_protocolo_no_conoce_termina_la_llamada(
    voz_doble: VozDoble,
) -> None:
    """Aceptarlo saltandoselo dejaria al navegador creyendo que dijo algo que
    nadie oye."""
    abierta = await _abrir_llamada()
    socket = SocketFalso(
        entrantes=[
            _auth(voz.issue(abierta.llamada.call_id, signing_key=CLAVE, now=_ahora())),
            {"type": "websocket.receive", "text": orjson.dumps({"type": "sing"}).decode()},
        ]
    )

    await _correr(socket, abierta.clave)

    assert [c["reason"] for c in socket.cuadros("ended")] == [voz.EndReason.DROPPED.value]


async def test_el_caso_de_la_llamada_no_se_inventa(voz_doble: VozDoble) -> None:
    """La llamada sigue atada al caso con el que se abrio: la divulgacion se
    registro contra el y cambiarlo dejaria ese registro huerfano."""
    abierta = await _abrir_llamada()
    socket = SocketFalso(
        entrantes=[
            _auth(voz.issue(abierta.llamada.call_id, signing_key=CLAVE, now=_ahora())),
            _hangup(),
        ]
    )

    await _correr(socket, abierta.clave)

    async with session.session_for(_aseguradora()) as sesion:
        fila = await session.fetch_one(
            sesion,
            "SELECT case_id FROM call_session WHERE call_id = :call_id",
            call_id=abierta.llamada.call_id,
        )
    assert fila is not None
    assert fila["case_id"] == abierta.llamada.case_id


# --- Lo que llego del microfono y el cierre al colgar (2026-10-07) -------------


async def test_al_terminar_queda_cuanto_audio_llego_y_con_que_pico(
    voz_doble: VozDoble, monkeypatch: pytest.MonkeyPatch
) -> None:
    """«No me oye» tiene dos causas que se ven igual desde fuera: el navegador no
    mando nada o mando silencio. La traza las separa con dos numeros."""
    emitidos: list[tuple[str, dict[str, object]]] = []
    original = observability.emit

    def espiar(event: str, **campos: object) -> None:
        emitidos.append((event, campos))
        original(event, **campos)

    monkeypatch.setattr(observability, "emit", espiar)
    abierta = await _abrir_llamada()
    voz_alta = (16384).to_bytes(2, "little", signed=True) * 480
    socket = SocketFalso(
        entrantes=[
            _auth(voz.issue(abierta.llamada.call_id, signing_key=CLAVE, now=_ahora())),
            {"type": "websocket.receive", "bytes": b"\x00\x00" * 480},
            {"type": "websocket.receive", "bytes": voz_alta},
            _hangup(),
        ]
    )

    await _correr(socket, abierta.clave)

    audio = [campos for evento, campos in emitidos if evento == "voice.audio_received"]
    assert len(audio) == 1
    assert audio[0]["chunks"] == 2
    assert audio[0]["peak"] == 0.5


async def test_un_socket_ya_cerrado_no_levanta_al_colgar(voz_doble: VozDoble) -> None:
    """En produccion cada llamada colgada dejaba «Cannot call send once a close
    message has been sent» sin atrapar: el cierre se intentaba dos veces."""
    abierta = await _abrir_llamada()

    class SocketQueYaCerro(SocketFalso):
        async def close(self, code: int = 1000) -> None:
            del code
            msg = 'Cannot call "send" once a close message has been sent.'
            raise RuntimeError(msg)

    socket = SocketQueYaCerro(
        entrantes=[
            _auth(voz.issue(abierta.llamada.call_id, signing_key=CLAVE, now=_ahora())),
            _hangup(),
        ]
    )

    await _correr(socket, abierta.clave)

    assert [c["reason"] for c in socket.cuadros("ended")] == [voz.EndReason.HANGUP.value]
