"""El conductor de voz: corre un caso de DS-5 **por el transporte de la llamada** (C-22).

Es el hermano del conductor de texto y se parece poco, porque lo que entra no es
un guion de frases sino una grabación: alguien contando un accidente, con su
acento, sus pausas y su ruido de fondo. Lo que este conductor hace es meter esas
muestras por el mismo canal por el que entran las de un navegador, y anotar lo que
salió.

**Qué es real aquí y qué no.** Real: el reconocedor, la síntesis, el ritmo del
turno, la detección de fin de habla, los silencios, la interrupción y la
transcripción que queda en el caso. Sustituido: **el socket**, y nada más. En
lugar de un WebSocket hay un canal que lee el archivo y guarda lo que el servidor
habría mandado; el `CallRunner` que corre es el mismo, byte por byte.

**DS-5 corre por hito, no por entrega** (`team.md`, "Lo que no corre en cada
corrida"). Las grabaciones son de personas reales, viven fuera del repositorio y
medirlas gasta saldo de voz. Por eso este conductor no entra en la compuerta: se
invoca a mano con `mise run voice:call-live`, y su corrida se anota con su fecha.

**La grabación entra a 20 ms por trozo y con su reloj.** Empujarla de golpe
mediría otra cosa: el detector de fin de habla cuenta silencio, y un archivo
entregado entero en un instante no tiene silencios que contar. El trozo es el
mismo que manda el navegador, y el reloj lo lleva el conductor --como en el
conductor de texto-- para que la corrida no dependa de lo ocupada que esté la
máquina.

**No queda audio en ninguna parte** (BR7.1). La grabación es del disco de quien la
corre y este módulo no la copia, no la guarda y no la manda a ningún sitio salvo
al reconocedor. Lo que queda de la corrida es la transcripción redactada, igual
que en una llamada de verdad.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from untangle.case_record import api as casos
from untangle.case_record.models import Origin
from untangle.evals.models import Channel, GoldenCase
from untangle.evals.runner import api as runner
from untangle.tenancy import api as tenancy
from untangle.tenancy.models import TenantId
from untangle.voice import api as voz
from untangle.voice.loop import CallChannel, CallRunner, CallVoice

#: Cuánto audio lleva cada trozo, en milisegundos. El mismo que manda el navegador.
FRAME_MS = 20

#: Bytes de un trozo: 20 ms de PCM de 16 bits a 24 kHz, mono.
FRAME_BYTES = 24000 * 2 * FRAME_MS // 1000

#: El techo de una llamada de evaluación, en segundos. Más corto que el de la
#: demostración a propósito: una grabación de DS-5 dura minuto y medio, y un
#: techo generoso solo serviría para que una corrida colgada tardara en verse.
MAX_CALL_SECONDS = 240


class VoiceRecordingNotFoundError(FileNotFoundError):
    """La grabación del caso no está donde el caso dice.

    Se falla nombrando el archivo en vez de correr el caso en silencio: un caso de
    DS-5 sin su grabación no es un caso que falla, es uno que **no se midió**, y
    los dos no se colapsan nunca.
    """


@dataclass
class RecordingChannel(CallChannel):
    """El transporte de una llamada leída de un archivo.

    Entrega el audio en trozos de 20 ms y guarda lo que el servidor manda. Es lo
    único que este conductor sustituye del camino real.
    """

    samples: bytes
    frames: list[bytes] = field(default_factory=list)
    sent: list[voz.ServerFrame] = field(default_factory=list)
    audio_out: int = field(default=0, init=False)

    async def _entrar(self) -> AsyncIterator[bytes | voz.Hangup]:
        for inicio in range(0, len(self.samples), FRAME_BYTES):
            # Cede el turno entre trozos, como lo cede un socket: sin esto, el
            # reconocedor no llega a correr hasta que el archivo entero está en la
            # cola, y lo que se mediría sería una transcripción en diferido.
            await asyncio.sleep(0)
            yield self.samples[inicio : inicio + FRAME_BYTES]
        # La grabación se acabó: la persona colgó. Sin este cuadro, el final sería
        # un corte, y un corte deja el caso esperando al asegurado --que es otro
        # desenlace y otra fila en el reporte--.
        yield voz.Hangup()

    def inbound(self) -> AsyncIterator[bytes | voz.Hangup]:
        return self._entrar()

    async def send(self, frame: voz.ServerFrame) -> None:
        self.sent.append(frame)

    async def send_audio(self, chunk: bytes) -> None:
        # **Se cuenta, no se guarda** (BR7.1). Lo que importa del audio que salió
        # es cuánto fue; conservarlo sería la grabación que esta unidad existe
        # para no tener.
        self.audio_out += len(chunk)


@dataclass
class VoiceDriver(runner.EvalDriver):
    """El conductor del canal de voz (C-22).

    La plataforma de voz entra **por argumento**: quien la construye es la raíz de
    composición, que está por encima del corredor de evaluaciones. Es la misma
    inversión que usa el conductor de texto con el manejador de turno.
    """

    speech: CallVoice
    handle_turn: voz.TurnHandler
    #: Dónde viven las grabaciones de DS-5. Fuera del repositorio: son de personas
    #: reales y el corpus del proyecto es sintético.
    recordings: Path
    channel: Channel = Channel.VOICE

    def _grabacion(self, case: GoldenCase) -> bytes:
        archivo = self.recordings / f"{case.case_key.replace('/', '-')}.pcm"
        if not archivo.is_file():
            msg = (
                f"el caso '{case.case_key}' no tiene su grabacion en "
                f"'{archivo}': no es un caso que falla, es uno que no se midio"
            )
            raise VoiceRecordingNotFoundError(msg)
        return archivo.read_bytes()

    async def run_case(self, case: GoldenCase) -> runner.CaseTranscript:
        if case.tenant is None:
            msg = (
                f"el caso '{case.case_key}' no declara aseguradora, y una llamada "
                "siempre ocurre dentro de una"
            )
            raise ValueError(msg)

        tenant_id: TenantId = case.tenant
        config = tenancy.require(tenant_id)
        muestras = self._grabacion(case)

        reloj = _Reloj()
        registro = await tenancy.resolve_visitor_key(
            tenant_id=tenant_id,
            visitor_key=tenancy.new_visitor_key(),
            origin=f"evals:{case.case_key}",
        )
        llamada = await voz.open_call(
            tenant_id=tenant_id,
            visitor_key_digest=registro.visitor_key_hash,
            language=case.language,
            voice_mode=voz.VoiceMode.PRIMARY,
            now=reloj.ahora(),
        )
        # Una corrida de evaluaciones **no** es dato de visitante: sus casos no los
        # borra el reinicio nocturno, que es justo lo contrario de lo que le toca a
        # una llamada del enlace público.
        case_id = await voz.open_for_call(
            tenant_id, language=case.language, origin=Origin.LOCAL_DEPLOYMENT, now=reloj.ahora()
        )
        llamada = await voz.attach_case(llamada, case_id=case_id)
        llamada = await voz.mark_live(llamada)

        canal = RecordingChannel(samples=muestras)
        motor = voz.CallEngine(call=llamada, config=config, handle_turn=self.handle_turn)
        motivo = await CallRunner(
            engine=motor,
            channel=canal,
            speech=self.speech,
            now=reloj.ahora,
            max_call=timedelta(seconds=MAX_CALL_SECONDS),
            warn_at=timedelta(seconds=config.call.warn_at_seconds),
        ).run()
        await voz.end_call(motor.call, reason=motivo, now=reloj.ahora())

        vista = await _vista(tenant_id, motor.call.case_id)
        return runner.CaseTranscript(
            case_key=case.case_key,
            turns=tuple(_turnos(canal.sent)),
            record=_registro(vista, motivo),
            # El corredor lee lo que la agente dijo con la guardia de verdad, y esta le
            # pide el numero del caso para no tomar por ajeno el propio.
            case_number=None if vista is None else vista.case_number,
        )


def _turnos(frames: list[voz.ServerFrame]) -> list[runner.Turn]:
    """La conversación, leída de lo que salió por el cable.

    Se arma de los cuadros y no de una lista que el ciclo fuera llenando aparte:
    lo que se compara con el veredicto esperado tiene que ser **lo que la persona
    habría oído**, no lo que el servidor creyó decir. Solo los finales; un parcial
    se sustituye y no es un turno.
    """
    return [
        runner.Turn(speaker="agent" if cuadro.speaker == "agent" else "insured", text=cuadro.text)
        for cuadro in frames
        if isinstance(cuadro, voz.Transcript) and cuadro.final
    ]


async def _vista(tenant_id: TenantId, case_id: str | None) -> casos.CaseView | None:
    """El caso tal como quedo, o nada si la llamada no llego a abrir ninguno."""
    if case_id is None:
        return None
    return await casos.get_case(tenant_id, case_id)


def _registro(vista: casos.CaseView | None, reason: voz.EndReason) -> dict[str, Any]:
    """Lo que el caso quedó diciendo, más cómo terminó la llamada."""
    if vista is None:
        return {"end_reason": reason.value}
    return {
        "record_type": vista.record_type.value,
        "state": vista.state.value,
        "complete": vista.completeness.complete,
        "total": vista.completeness.total,
        "language": vista.language,
        # Por qué terminó: es lo que distingue un reporte completo de uno que se
        # quedó esperando, y sin él las dos filas del reporte se leerían igual.
        "end_reason": reason.value,
    }


@dataclass
class _Reloj:
    """El reloj de la corrida, que avanza con el audio y no con la máquina.

    Cada trozo entregado son 20 ms, así que el tiempo de la llamada se puede
    derivar de cuánto audio entró. Con el reloj del sistema, una máquina ocupada
    haría vencer el detector de fin de habla a mitad de una frase, y el caso
    fallaría por algo que no tiene que ver con lo que mide.
    """

    inicio: datetime = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
    transcurrido: timedelta = timedelta()

    def ahora(self) -> datetime:
        self.transcurrido += timedelta(milliseconds=FRAME_MS)
        return self.inicio + self.transcurrido


def register(*, speech: CallVoice, handle_turn: voz.TurnHandler, recordings: Path) -> None:
    """Registra el conductor del canal de voz (C-22). Lo llama quien tiene la voz.

    No lo llama la raíz del proceso servido, a diferencia del de texto: DS-5 corre
    por hito y a mano, y dejar el conductor registrado en el proceso público
    sugeriría que la compuerta lo ejecuta.
    """
    runner.register_driver(
        VoiceDriver(speech=speech, handle_turn=handle_turn, recordings=recordings)
    )


__all__ = [
    "FRAME_BYTES",
    "FRAME_MS",
    "MAX_CALL_SECONDS",
    "RecordingChannel",
    "VoiceDriver",
    "VoiceRecordingNotFoundError",
    "register",
]
