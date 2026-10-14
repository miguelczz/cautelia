"""Una conversacion de chat por el camino real, con mensajes literales (datos sinteticos).

    uv run --env-file .env --project app/backend python scripts/chat-simulado.py \
        <aseguradora> <es|en> "mensaje 1" "mensaje 2" "@espera 14" "mensaje 3"

Es al chat lo que `mise run voice:simular` es a la llamada: arma la aplicacion entera, abre
una conversacion nueva y entrega cada mensaje por `chat.delivery`, con el modelo de verdad y
la base local. Imprime lo que el canal publica en cada turno y, al final, el caso y la
conversacion guardada. `@espera N` deja pasar N segundos para lo que trae el fondo (la
respuesta de cobertura).

**Gasta en el modelo de verdad**: alrededor de un centavo por conversacion de seis mensajes.
No corre en GitHub Actions ni forma parte de ninguna compuerta; es para ver una conversacion
entera antes de pedirle a nadie que la pruebe a mano.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime

from untangle import language
from untangle.case_record import api as casos
from untangle.case_record.models import Origin
from untangle.chat import delivery, opening
from untangle.chat import session as chat
from untangle.chat.wire import EventQueue
from untangle.orchestration.contracts import InboundTurn
from untangle.server import composition
from untangle.settings import Settings
from untangle.tenancy import api as tenancy


async def vaciar(cola: EventQueue, espera: float) -> None:
    while True:
        cable = await cola.next_event(heartbeat_after=espera)
        if cable is None:
            return
        resumen = {
            k: v
            for k, v in cable.items()
            if k in ("kind", "text", "case_id", "reason_code")
        }
        print(f"   <- {json.dumps(resumen, default=str, ensure_ascii=False)[:520]}")


async def main() -> None:
    tenant, idioma, mensajes = sys.argv[1], sys.argv[2], sys.argv[3:]
    aplicacion = composition.build_app(Settings())
    async with aplicacion.router.lifespan_context(aplicacion):
        config = tenancy.require(tenant)
        registro = await tenancy.resolve_visitor_key(
            tenant_id=tenant,
            visitor_key=tenancy.new_visitor_key(),
            origin="chat-simulado",
        )
        ahora = datetime.now(UTC)
        conversacion = await chat.open_session(
            tenant_id=tenant,
            visitor_key_digest=registro.visitor_key_hash,
            origin_digest=registro.origin,
            language=idioma,  # type: ignore[arg-type]
            now=ahora,
        )
        print("AGENTE(apertura):", opening.compose(config, language=idioma).text[:160])  # type: ignore[arg-type]
        conversacion = await chat.mark_opening_delivered(conversacion, now=ahora)
        cola = EventQueue(stream_ref=conversacion.chat_session_id)
        for texto in mensajes:
            if texto.startswith("@espera"):
                await vaciar(cola, float(texto.split()[1]))
                continue
            # El reloj de verdad: los turnos de la agente se guardan con el, y un reloj
            # adelantado para la persona desordenaria la historia que ve el modelo.
            await asyncio.sleep(config.chat.min_seconds_between_messages + 0.2)
            ahora = datetime.now(UTC)
            idioma_del_turno = language.for_turn(texto, current=conversacion.language)
            await chat.count_message(conversacion, now=ahora)
            print(f"\nPERSONA: {texto}")
            entregado = await delivery.deliver(
                cola,
                InboundTurn(
                    tenant_id=tenant,
                    session_ref=conversacion.chat_session_id,
                    case_id=conversacion.case_id,
                    text=texto,
                    language=idioma_del_turno.language,
                    channel="chat",
                    received_at=ahora,
                ),
                handle_turn=delivery.current_turn_handler(),
                visitor_key_hash=registro.visitor_key_hash,
                origin=Origin.LOCAL_DEPLOYMENT,
            )
            print(f"   (eventos del turno: {entregado.events})")
            await vaciar(cola, 0.3)
            viva = await chat.find_live(
                tenant_id=tenant, visitor_key_digest=registro.visitor_key_hash
            )
            if viva is not None:
                conversacion = viva
        await vaciar(cola, 0.5)
        if conversacion.case_id is not None:
            vista = await casos.get_case(tenant, conversacion.case_id)
            if vista is not None:
                print(
                    "\nCASO:",
                    vista.record_type.value,
                    vista.state.value,
                    f"{vista.completeness.complete}/{vista.completeness.total}",
                )
            for turno in await casos.conversation_transcript(
                tenant, conversacion.case_id
            ):
                print(f"   guardado {turno.speaker.value}: {turno.text_redacted[:150]}")


asyncio.run(main())
