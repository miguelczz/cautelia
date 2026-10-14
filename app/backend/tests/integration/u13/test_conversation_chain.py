"""La conversacion a traves de la cadena de casos (2026-10-13).

Quien cambia de tema en el chat -- consultaba su poliza y dice «quiero reportar eso como un
accidente»-- sigue en un caso nuevo, y la conversacion solo apuntaba a uno: la agente no sabia
que era «eso» y, al recargar, la pantalla perdia de vista lo hablado antes. La decision fue
guardar de que caso viene cada caso y leer **a traves de la cadena**, sin copiar turnos.

Lo que se prueba aqui es la base y la lectura: el orden, el tope de saltos, que la cadena no
cruce de aseguradora, y que borrar el caso anterior -- lo que hace el reinicio nocturno-- ni se
lo impida ni deje filas colgando. El cambio de tema de punta a punta, con el enlace escrito por
el canal, vive en `test_topic_change.py`.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from untangle.case_record import api as casos
from untangle.case_record import purge
from untangle.case_record.models import Channel, Origin, RecordType, TranscriptTurn
from untangle.chat import history
from untangle.chat import session as chat_session
from untangle.orchestration import transcript_writer
from untangle.policy_rag.citations import api as citas
from untangle.policy_rag.citations.models import CoverageOutcome
from untangle.policy_rag.citations.verifier import CitationVerdict, VerificationResult
from untangle.tenancy import config as tenancy_config
from untangle.tenancy import session

from .conftest import AHORA, nuevo_caso
from .test_delivery import _conversacion_nueva
from .test_history_citations import _sembrar_clausula

pytestmark = pytest.mark.usefixtures("base_de_u13", "cifrador")


async def _decir(
    tenant_id: str,
    case_id: str,
    minuto: int,
    *,
    persona: str | None = None,
    agente: str | None = None,
) -> list[str]:
    """Lo que se dijo en un caso, `minuto` minutos despues de AHORA. Devuelve los turnos."""
    ambito = transcript_writer.TranscriptScope(
        tenant_id=tenant_id, case_id=case_id, channel=Channel.CHAT, language="es"
    )
    ahora = AHORA + timedelta(minutes=minuto)
    turnos = []
    if persona is not None:
        turnos.append(await transcript_writer.record_person_turn(ambito, text=persona, now=ahora))
    if agente is not None:
        turnos.append(
            await transcript_writer.record_agent_turn(
                ambito, text=agente, now=ahora + timedelta(seconds=30), from_catalog=True
            )
        )
    return turnos


async def _viene_de(tenant_id: str, case_id: str) -> str | None:
    async with session.session_for(tenant_id) as sesion:
        fila = await session.fetch_one(
            sesion, "SELECT continues_case_id FROM case_record WHERE case_id = :id", id=case_id
        )
    assert fila is not None
    viene = fila["continues_case_id"]
    return None if viene is None else str(viene)


def _textos(turnos: tuple[TranscriptTurn, ...]) -> list[str]:
    return [t.text_redacted for t in turnos]


# --- Leer a traves de la cadena -------------------------------------------------------


async def test_sin_enlace_la_conversacion_es_la_transcripcion_del_caso(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _decir(propia, caso.case_id, 1, persona="hola", agente="Cuéntame qué necesitas.")

    conversacion = await casos.conversation_transcript(propia, caso.case_id)

    assert conversacion == await casos.transcript_of(propia, caso.case_id)
    assert _textos(conversacion) == ["hola", "Cuéntame qué necesitas."]


async def test_va_del_caso_mas_antiguo_al_propio_y_cada_turno_conserva_su_caso(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    consulta = await nuevo_caso(propia, record_type=RecordType.COVERAGE_INQUIRY)
    reporte = await nuevo_caso(propia, continues_case_id=consulta.case_id)
    cotizacion = await nuevo_caso(propia, continues_case_id=reporte.case_id)
    await _decir(
        propia, consulta.case_id, 1, persona="¿me cubre la grúa?", agente="Sí, la Parte D."
    )
    await _decir(propia, reporte.case_id, 3, persona="quiero reportar eso", agente="¿Qué pasó?")
    await _decir(propia, cotizacion.case_id, 5, persona="y una cotización")

    desde_el_ultimo = await casos.conversation_transcript(propia, cotizacion.case_id)
    desde_el_del_medio = await casos.conversation_transcript(propia, reporte.case_id)

    assert _textos(desde_el_ultimo) == [
        "¿me cubre la grúa?",
        "Sí, la Parte D.",
        "quiero reportar eso",
        "¿Qué pasó?",
        "y una cotización",
    ]
    assert [t.case_id for t in desde_el_ultimo] == [
        consulta.case_id,
        consulta.case_id,
        reporte.case_id,
        reporte.case_id,
        cotizacion.case_id,
    ]
    # Solo hacia atras: el caso del medio no ve el que vino despues.
    assert _textos(desde_el_del_medio) == _textos(desde_el_ultimo)[:4]


async def test_con_relojes_iguales_el_orden_sigue_siendo_el_de_la_cadena(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Las pruebas (y un reloj grueso) ponen a todos los turnos en el mismo instante: el
    orden de la cadena es el que lo deja determinista."""
    _, propia = dos_aseguradoras
    primero = await nuevo_caso(propia)
    segundo = await nuevo_caso(propia, continues_case_id=primero.case_id)
    for caso, texto in ((segundo, "del segundo"), (primero, "del primero")):
        await _decir(propia, caso.case_id, 0, persona=texto)

    conversacion = await casos.conversation_transcript(propia, segundo.case_id)

    assert _textos(conversacion) == ["del primero", "del segundo"]


async def test_el_tope_de_saltos_corta_la_cadena(dos_aseguradoras: tuple[str, str]) -> None:
    _, propia = dos_aseguradoras
    anterior: str | None = None
    ids = []
    for orden in range(4):
        caso = await nuevo_caso(propia, continues_case_id=anterior)
        await _decir(propia, caso.case_id, orden, persona=f"caso {orden}")
        ids.append(caso.case_id)
        anterior = caso.case_id

    todo = await casos.conversation_transcript(propia, ids[-1])
    cortado = await casos.conversation_transcript(propia, ids[-1], max_hops=1)

    assert _textos(todo) == ["caso 0", "caso 1", "caso 2", "caso 3"]
    assert _textos(cortado) == ["caso 2", "caso 3"], "un salto atras y no mas"


# --- Que la cadena no salga de donde debe ----------------------------------------------


async def test_la_cadena_no_cruza_de_aseguradora(dos_aseguradoras: tuple[str, str]) -> None:
    """La llave lleva la aseguradora: una fila de una no puede continuar un caso de otra.

    PostgreSQL comprueba las llaves por encima de las politicas de fila, asi que con una llave
    de una sola columna esto pasaria; con el par `(aseguradora, caso)` el caso ajeno no existe
    para la llave y la base lo rechaza nombrandola."""
    otra, propia = dos_aseguradoras
    ajeno = await nuevo_caso(otra)
    await _decir(otra, ajeno.case_id, 1, persona="esto es de la otra aseguradora")

    with pytest.raises(IntegrityError, match="case_record_continua_a"):
        await nuevo_caso(propia, continues_case_id=ajeno.case_id)

    # Y leer desde un caso ajeno tampoco entrega nada: la politica de fila filtra antes.
    assert await casos.conversation_transcript(propia, ajeno.case_id) == ()


async def test_un_caso_no_se_continua_a_si_mismo(dos_aseguradoras: tuple[str, str]) -> None:
    _, propia = dos_aseguradoras

    with pytest.raises(IntegrityError, match="case_record_no_se_continua_a_si_mismo"):
        await casos.create_case(
            propia,
            casos.NewCase(
                case_id="u13-caso-circular",
                record_type=RecordType.CLAIM,
                channel=Channel.CHAT,
                origin=Origin.PUBLIC_CHAT,
                language="es",
                continues_case_id="u13-caso-circular",
            ),
            now=AHORA,
        )


# --- El reinicio nocturno -------------------------------------------------------------


async def test_borrar_el_caso_anterior_deja_al_nuevo_sin_enlace_y_sin_filas_colgando(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """El caso del que se viene se borra -- la retencion lo pide-- y el nuevo sigue entero.

    `SET NULL` a secas anularia tambien la aseguradora, que es parte de la llave y no admite
    nulo; la accion con lista de columnas anula solo el enlace."""
    _, propia = dos_aseguradoras
    viejo = await nuevo_caso(propia, now=AHORA - timedelta(days=2))
    nuevo = await nuevo_caso(propia, continues_case_id=viejo.case_id, now=AHORA)
    await _decir(propia, viejo.case_id, -60, persona="lo dicho en el caso viejo")
    await _decir(propia, nuevo.case_id, 1, persona="lo dicho en el caso nuevo")
    assert await _viene_de(propia, nuevo.case_id) == viejo.case_id

    resultado = await purge.CASE_RECORD_PURGER.purge(older_than=AHORA - timedelta(days=1))

    assert resultado.deleted == 1
    assert await casos.get_case(propia, viejo.case_id) is None
    assert await casos.get_case(propia, nuevo.case_id) is not None
    assert await _viene_de(propia, nuevo.case_id) is None
    assert _textos(await casos.conversation_transcript(propia, nuevo.case_id)) == [
        "lo dicho en el caso nuevo"
    ]


async def test_el_reinicio_borra_de_una_vez_toda_la_cadena(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    primero = await nuevo_caso(propia, now=AHORA - timedelta(days=2))
    segundo = await nuevo_caso(
        propia, continues_case_id=primero.case_id, now=AHORA - timedelta(days=2)
    )
    await nuevo_caso(propia, continues_case_id=segundo.case_id, now=AHORA - timedelta(days=2))

    resultado = await purge.CASE_RECORD_PURGER.purge(older_than=AHORA - timedelta(days=1))

    assert resultado.deleted == 3
    async with session.session_for(propia) as sesion:
        quedan = await session.fetch_one(sesion, "SELECT count(*) AS total FROM case_record")
    assert quedan is not None and int(quedan["total"]) == 0


# --- Lo que la pantalla recupera ------------------------------------------------------


async def test_recargar_dibuja_lo_hablado_antes_del_cambio_y_conserva_las_clausulas(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La respuesta de cobertura del caso anterior vuelve con sus tarjetas, aunque la
    conversacion ya este en el caso nuevo: copiar el turno la habria dejado sin ellas."""
    _, propia = dos_aseguradoras
    consulta = await nuevo_caso(propia, record_type=RecordType.COVERAGE_INQUIRY)
    await _sembrar_clausula(propia, "u13-cadena-D.EXCL.5")
    ambito = transcript_writer.TranscriptScope(
        tenant_id=propia, case_id=consulta.case_id, channel=Channel.CHAT, language="es"
    )
    pregunta = await transcript_writer.record_person_turn(
        ambito, text="¿Me cubren una llanta?", now=AHORA + timedelta(minutes=1)
    )
    await citas.record_answer(
        propia,
        case_id=consulta.case_id,
        turn_id=pregunta,
        question="¿Me cubren una llanta?",
        verification=VerificationResult(
            outcome=CoverageOutcome.VERIFIED,
            citations=(
                CitationVerdict(
                    clause_id="u13-cadena-D.EXCL.5",
                    claim="Trata de las llantas.",
                    outcome=CoverageOutcome.VERIFIED,
                    reasons=(),
                    amended_by=(),
                    clause_version="2026.1",
                ),
            ),
            clause_language="es",
        ),
        answer_language="es",
        now=AHORA + timedelta(minutes=1),
    )
    respuesta = await transcript_writer.record_agent_turn(
        ambito,
        text="En su póliza, esto lo trata la Parte D.",
        now=AHORA + timedelta(minutes=2),
        from_catalog=True,
        turn_id=f"{transcript_writer.COVERAGE_TURN_PREFIX}u13-cadena",
    )
    reporte = await nuevo_caso(
        propia,
        record_type=RecordType.CLAIM,
        continues_case_id=consulta.case_id,
        now=AHORA + timedelta(minutes=3),
    )
    await _decir(propia, reporte.case_id, 4, persona="quiero reportar eso como un accidente")
    conversacion, _ = await _conversacion_nueva(propia)
    conversacion = await chat_session.attach_case(conversacion, case_id=reporte.case_id)

    cargado = await history.load(conversacion, config=tenancy_config.require(propia))

    assert [t.text for t in cargado.turns] == [
        "¿Me cubren una llanta?",
        "En su póliza, esto lo trata la Parte D.",
        "quiero reportar eso como un accidente",
    ]
    por_turno = {t.turn_id: t for t in cargado.turns}
    assert [c.clause_id for c in por_turno[respuesta].citations] == ["u13-cadena-D.EXCL.5"]
    # El numero es el del caso en que esta la conversacion, el que la persona puede retomar.
    vista = await casos.get_case(propia, reporte.case_id)
    assert vista is not None and cargado.case_number == vista.case_number
    # Cada caso conserva lo suyo para la bandeja y para «Ver mi caso».
    assert _textos(await casos.transcript_of(propia, reporte.case_id)) == [
        "quiero reportar eso como un accidente"
    ]
