"""El conductor de texto: corre un caso de golden set **por el canal chat** (C-22).

Es lo que faltaba para que una conversacion de DS-2 se mida donde de verdad ocurre.
Hasta aqui las sondas de U11 simulaban el recorrido con el codigo real de bloques y
composicion pero **sin canal**: sin conversacion, sin limites, sin deteccion de
idioma y sin transcripcion. Eso sirve para medir la captura y no sirve para lo que
ahora hace falta -- transcripciones reales con las que calibrar al juez (DS-7) --,
porque una transcripcion que nadie mantuvo por un canal no es la que una persona
habria tenido.

**Que es real aqui y que no.** Real: la conversacion y sus limites, la apertura con
su registro, la deteccion de idioma por turno, la entrega al grafo y la
transcripcion que queda en el caso. Sustituido: nada de esta unidad. El grafo entra
por el puerto que la raiz de composicion enchufa, asi que una corrida con clave de
proveedor mide el sistema entero y una corrida de prueba enchufa un doble.

**Que campo contesta el asegurado simulado.** No se adivina del texto de la
pregunta: se lee del caso. Despues de cada turno se mira la completitud que dejo
con `blocks.next_ask` --el espejo de lo que el nodo `intake` va a preguntar, para un
siniestro y para una solicitud de cotizacion-- y se le pide al guion la respuesta de
esa clave: un campo, o la confirmacion de lo leido. Emparejar por el orden del guion
se rompe en cuanto la agente pregunta en otro orden, que es la conducta normal.

**El reloj lo lleva el conductor, no el proceso.** Dos mensajes seguidos mas
rapidos que el intervalo minimo son una rafaga, y el canal los rechaza: una persona
escribe despacio y un conductor no. La primera corrida de este conductor se detuvo
en el segundo turno por eso mismo. La salida no es apagar el limite --es conducta
del canal y tiene que aplicarse-- sino que el conductor **avance su propio reloj**
entre turnos, que es justo para lo que todas estas funciones reciben `now` por
argumento. De paso la corrida deja de depender de cuanto tarde la maquina, que es
lo que la practica pide de una corrida de evaluaciones.

**Pero la latencia se mide con el reloj de verdad.** El reloj del conductor solo mueve las
fechas; el tiempo que tarda la primera palabra es el monotono del proceso, el mismo que usa la
ruta (`received_monotonic` en `chat/api.py`), y lo mide la entrega (`chat/latency.py`) con su
definicion de siempre. El conductor solo toma la marca de cuando "recibe" el mensaje, antes de
admitirlo, y guarda lo que la entrega devuelve: de ahi sale la latencia que la linea base publica.

**El limite de turnos es una salida y no un adorno.** Una conversacion que no
avanza --porque el guion no tiene el campo que se pide, o porque la agente repite--
termina igual, y el caso lo declara con sus turnos fuera de guion en vez de colgar
la corrida.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from untangle import language
from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.case_record.models import Origin
from untangle.chat import delivery, opening
from untangle.chat import session as chat
from untangle.chat.limits import LimitKind
from untangle.chat.wire import EventQueue
from untangle.evals.models import Channel, ChatTurnLatency, GoldenCase
from untangle.evals.runner import api as runner
from untangle.evals.runner.failures import TargetUnavailableError
from untangle.evals.scripted_insured import ScriptedInsured
from untangle.orchestration.contracts import InboundTurn
from untangle.orchestration.nodes.intake import blocks
from untangle.orchestration.nodes.intake.blocks import Block
from untangle.tenancy import api as tenancy
from untangle.tenancy.models import TenantId, UnknownTenantError

#: El techo de turnos de una conversacion. Cinco bloques de campos mas la
#: confirmacion, con margen para las correcciones que un guion puede traer.
#:
#: **No es el unico techo, y casi nunca es el que manda**: el limite de mensajes
#: por conversacion de la aseguradora suele ser menor, y entonces el que corta es
#: ese. Se toma el menor de los dos a proposito, porque una conversacion que
#: termina por un limite es una conversacion que **no se completo**, y eso tiene
#: que verse como tal en vez de parecerse a una que llego al final.
MAX_TURNS = 24

#: El campo del primer mensaje cuando todavia no hay caso al que preguntarle. La
#: conversacion existe desde el primer mensaje y el caso solo cuando hay algo que
#: registrar, asi que aqui no hay completitud que leer: se usa el primer campo del
#: guion, que es lo que la persona venia a decir. Escribir un campo fijo seria
#: decidir por ella cual es su primera frase.
PRIMER_CAMPO_POR_OMISION = Block.IDENTITY_AND_POLICY.value

#: Lo que se espera por cada evento al vaciar la cola. Corto: los eventos ya
#: estan publicados cuando la entrega vuelve, y esto solo le da al bucle de
#: eventos la vuelta que necesita para entregarlos.
_ESPERA_DE_VACIADO = 0.05

#: El instante en que empieza toda conversacion conducida. Fijo: dos corridas del
#: mismo commit tienen que ver los mismos tiempos (BR1.7 del corredor).
#:
#: **Ese dia es del conductor y de nadie mas**: es anterior al primer despliegue, asi
#: que ningun visitante escribio en el. Por eso antes de cada conversacion se dejan en
#: cero sus contadores de mensajes (`chat.forget_past_day`): si no, cada corrida suma
#: sobre la anterior en el mismo dia y a las pocas corridas el canal rechaza todo por
#: cupo diario, que fue lo que paso el 2026-10-12 --catorce conversaciones en rojo sin
#: que nada estuviera roto--.
INICIO = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

#: Los limites que no son de la conversacion sino del dia: si uno de estos rechaza un
#: mensaje, lo agotado es el cupo de la base donde se evalua, no algo que el caso mida.
_CUPOS_DEL_DIA = frozenset({LimitKind.ORIGIN, LimitKind.SITE_DAY})


@dataclass
class _Reloj:
    """El reloj de una conversacion conducida, que avanza a saltos declarados.

    No lee el reloj del proceso a proposito. Con el de verdad, dos mensajes
    seguidos son una rafaga y el canal rechaza el segundo --con razon--, asi que
    ninguna conversacion pasaria del primer turno; y la corrida dependeria de lo
    rapida que sea la maquina.
    """

    ahora: datetime = INICIO

    def avanzar(self, segundos: float) -> datetime:
        self.ahora += timedelta(seconds=segundos)
        return self.ahora


@dataclass(frozen=True)
class _Pendiente:
    """Que se le va a preguntar al asegurado simulado en este turno."""

    field_key: str
    done: bool


async def _pendiente(tenant_id: TenantId, case_id: str | None, primero: str) -> _Pendiente:
    """El campo que toca, leido del caso y no del texto de la pregunta.

    **Lo que toca es lo que el nodo va a preguntar**, y eso lo dice `blocks.next_ask`: el
    mismo bloque y la misma clave que el nodo calcula. No es una deduccion propia del
    conductor, y el dia que lo fue dejo de coincidir: desde el 2026-10-08 la solicitud de
    cotizacion no lee de vuelta cada bloque sino toda ella al final, y un conductor que
    seguia contestando la confirmacion de cada bloque le decia "si, es correcto" veinte
    veces a una agente que preguntaba por el vehiculo (`complete: 0, total: 17`).
    """
    if case_id is None:
        return _Pendiente(field_key=primero, done=False)

    vista = await casos.get_case(tenant_id, case_id)
    if vista is None:
        return _Pendiente(field_key=primero, done=False)

    pide = blocks.next_ask(vista.record_type, vista.completeness, vista.state)
    if pide.kind is blocks.AskKind.DONE:
        return _Pendiente(field_key="", done=True)
    return _Pendiente(field_key=pide.key, done=False)


def _texto_del_evento(cable: dict[str, Any]) -> str | None:
    """Lo que la agente dijo en un evento del cable, si dijo algo.

    Los eventos que llevan **clave y no texto** --la espera, la derivacion, el
    error-- no aportan un turno de conversacion: su frase la resuelve el navegador,
    y aqui se cuentan por su tipo y no por unas palabras que esta unidad tendria
    que volver a resolver.
    """
    if cable.get("kind") in {"turn.partial", "turn.final"}:
        texto = cable.get("text")
        return texto if isinstance(texto, str) and texto != "" else None
    return None


def _si_es_el_cupo_del_dia_no_se_midio(limite: LimitKind | None, tenant_id: TenantId) -> None:
    """El cupo diario no es conducta que el caso mida: es la base de evaluacion agotada.

    Se dice con su nombre y el caso queda sin medir, en vez de salir en rojo por una
    conversacion a medias que nadie sabria leer.
    """
    if limite in _CUPOS_DEL_DIA:
        msg = (
            f"el canal rechazo el mensaje por el cupo diario ('{limite}') de '{tenant_id}' "
            "en la base donde se evalua: la conversacion no se pudo conducir"
        )
        raise TargetUnavailableError(msg)


@dataclass
class ChatDriver:
    """Corre un caso por el canal chat. Una instancia por corrida."""

    channel: Channel = Channel.CHAT

    async def run_case(self, case: GoldenCase) -> runner.CaseTranscript:
        if case.tenant is None:
            msg = (
                f"el caso '{case.case_key}' no declara aseguradora, y una conversacion "
                "de chat siempre ocurre dentro de una"
            )
            raise ValueError(msg)

        tenant_id = case.tenant
        try:
            config = tenancy.require(tenant_id)
        except UnknownTenantError as error:
            # Un inquilino de fixture --`injection-test` de RT-2-- que esta corrida no
            # aprovisiono: el caso no se pudo ejecutar, no fallo (NFR10.3).
            raise TargetUnavailableError(str(error)) from error
        clave = tenancy.new_visitor_key()
        registro = await tenancy.resolve_visitor_key(
            tenant_id=tenant_id, visitor_key=clave, origin=f"evals:{case.case_key}"
        )
        reloj = _Reloj()
        # El dia del conductor empieza en cero, como lo encontraria un visitante.
        await chat.forget_past_day(tenant_id, day=INICIO, now=datetime.now(UTC))
        # Un salto mayor que el intervalo minimo de esta aseguradora: el limite se
        # sigue aplicando, y lo que deja de pasar es que el conductor lo dispare.
        paso = config.chat.min_seconds_between_messages + 1
        conversacion = await chat.open_session(
            tenant_id=tenant_id,
            visitor_key_digest=registro.visitor_key_hash,
            origin_digest=registro.origin,
            language=case.language,
            now=reloj.ahora,
        )

        turnos: list[runner.Turn] = []
        latencias: list[ChatTurnLatency] = []

        # BR1.1: la apertura sale antes de cualquier texto del visitante, y queda
        # anotada. Es el primer turno de la agente, igual que en la pantalla.
        apertura = opening.compose(config, language=case.language)
        conversacion = await chat.mark_opening_delivered(conversacion, now=reloj.ahora)
        turnos.append(runner.Turn(speaker="agent", text=apertura.text))

        primero = case.script[0].field_key if case.script else PRIMER_CAMPO_POR_OMISION
        responder = ScriptedInsured(case)
        # La cola del corredor es suya y no la del registro del proceso: aqui no
        # hay navegador, asi que su referencia es la conversacion que se esta
        # recorriendo.
        cola = EventQueue(stream_ref=conversacion.chat_session_id)

        # El menor de los dos techos: el propio y el de la aseguradora.
        techo = min(MAX_TURNS, config.chat.messages_per_session)
        for _ in range(techo):
            pendiente = await _pendiente(tenant_id, conversacion.case_id, primero)
            if pendiente.done:
                break

            respuesta = responder.answer(pendiente.field_key)
            ahora = reloj.avanzar(paso)
            # La marca de cuando el servidor recibe el mensaje, **antes de admitirlo**, como
            # la toma la ruta (`chat/api.py`): la espera de admitir y contar tambien es de
            # quien escribe. Es el reloj monotono de verdad y no `reloj`, que es el simulado
            # que solo mueve las fechas: una latencia medida con el simulado daria siempre cero.
            recibido = time.monotonic()
            admision = await chat.admit(
                conversacion,
                config=config.chat,
                message_characters=len(respuesta.text),
                now=ahora,
            )
            if not admision.admitted:
                _si_es_el_cupo_del_dia_no_se_midio(admision.limit, tenant_id)
                # Un limite de la conversacion alcanzado no es un fallo del caso: es
                # una conducta del canal, y el caso la declara en su registro en vez
                # de dejar la conversacion a medias sin decir por que.
                break

            idioma = language.for_turn(respuesta.text, current=conversacion.language)
            await chat.count_message(conversacion, now=ahora)
            turnos.append(
                runner.Turn(speaker="insured", text=respuesta.text, field_key=pendiente.field_key)
            )

            entregado = await delivery.deliver(
                cola,
                InboundTurn(
                    tenant_id=tenant_id,
                    session_ref=conversacion.chat_session_id,
                    case_id=conversacion.case_id,
                    text=respuesta.text,
                    language=idioma.language,
                    channel="chat",
                    received_at=ahora,
                ),
                handle_turn=_manejador(),
                visitor_key_hash=registro.visitor_key_hash,
                # Una corrida de evaluaciones **no** es dato de visitante: sus
                # casos no los borra el reinicio nocturno (BR4.6 de U4), que es
                # justo lo contrario de lo que le toca al chat publico.
                origin=Origin.LOCAL_DEPLOYMENT,
                received_monotonic=recibido,
            )
            latencias.extend(_latencia_del_turno(entregado, idioma.language))
            # Se vacia la cola **entera** despues de cada entrega. Con el plazo en
            # cero no se vacia nada --`wait_for(..., timeout=0)` vence antes de
            # poder sacar lo que ya estaba dentro-- y a los diez eventos la cola se
            # llena y el canal declara la pestana abandonada. Lo dijo su propio
            # evento de traza en la primera corrida.
            for _ in range(entregado.events):
                cable = await cola.next_event(heartbeat_after=_ESPERA_DE_VACIADO)
                if cable is None:
                    break
                texto = _texto_del_evento(cable)
                if texto is not None:
                    turnos.append(runner.Turn(speaker="agent", text=texto))

            # La conversacion pudo abrir el caso en este turno.
            viva = await chat.find_live(
                tenant_id=tenant_id, visitor_key_digest=registro.visitor_key_hash
            )
            if viva is not None:
                conversacion = viva

        vista = await _vista(tenant_id, conversacion.case_id)
        return runner.CaseTranscript(
            case_key=case.case_key,
            turns=tuple(turnos),
            record=_registro(vista),
            off_script_turns=responder.off_script_turns,
            # El corredor lee lo que la agente dijo con la guardia de verdad, y esta le
            # pide el numero del caso para no tomar por ajeno el propio.
            case_number=None if vista is None else vista.case_number,
            chat_latencies=tuple(latencias),
        )


def _latencia_del_turno(
    entregado: delivery.Delivered, idioma: Locale
) -> tuple[ChatTurnLatency, ...]:
    """La latencia del turno es la que mide la entrega, con la definicion del chat en vivo.

    La frase de espera no cuenta y un error tampoco (`chat/latency.py`): un turno que no dio
    ninguna primera palabra no deja valor, porque no hay nada que medir, y la cifra publicada
    no se mejora con turnos que no contestaron.
    """
    if entregado.first_word_ms is None:
        return ()
    return (ChatTurnLatency(language=idioma, first_word_ms=entregado.first_word_ms),)


def _manejador() -> delivery.TurnHandler:
    """El grafo, por el mismo puerto que usa el canal.

    Se pide en cada turno y no se guarda: una corrida puede enchufar un doble y
    otra el de verdad, y guardarlo dejaria a la segunda corriendo contra el de la
    primera.
    """
    return delivery.current_turn_handler()


async def _vista(tenant_id: TenantId, case_id: str | None) -> casos.CaseView | None:
    """El caso tal como quedo, o nada si la conversacion no llego a abrir ninguno."""
    if case_id is None:
        return None
    return await casos.get_case(tenant_id, case_id)


def _registro(vista: casos.CaseView | None) -> dict[str, Any]:
    """Lo que el caso quedo diciendo, para comparar con lo esperado."""
    if vista is None:
        return {}
    return {
        "record_type": vista.record_type.value,
        "state": vista.state.value,
        "complete": vista.completeness.complete,
        "total": vista.completeness.total,
        # El idioma del caso: es lo que RT-10 mide. Un caso que cambia de idioma
        # a mitad para esquivar un control tiene que quedar registrado en el
        # idioma en que se atendio, no en el que se intento colar.
        "language": vista.language,
    }


def register() -> None:
    """Registra el conductor del canal chat (C-22). Lo llama la raiz de composicion."""
    runner.register_driver(ChatDriver())


__all__ = ["MAX_TURNS", "ChatDriver", "register"]
