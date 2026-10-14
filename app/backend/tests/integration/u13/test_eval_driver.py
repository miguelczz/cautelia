"""El conductor de texto: un caso de golden set corrido por el canal (C-22, U13).

Lo que aqui se comprueba no es que el conductor "funcione": es que la conversacion
que produce sea **la que una persona habria tenido**, porque de eso depende lo
unico para lo que existe --calibrar al juez con transcripciones reales (DS-7)--.

Tres conductas, y ninguna se ve simulando el recorrido sin canal:

- La apertura con su divulgacion es el primer turno, antes de que la persona
  escriba (BR1.1).
- El campo que contesta cada turno sale del **caso**, no del texto de la pregunta:
  cuando la captura avanza, el guion avanza con ella.
- Una conversacion que no avanza termina igual. El techo de turnos es una salida,
  no un adorno: sin el, un guion al que le falta un campo cuelga la corrida.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest

from untangle import paths
from untangle.case_record import api as casos
from untangle.case_record import crypto, fields, rules
from untangle.case_record.models import (
    Actor,
    ActorType,
    CaseField,
    CaseState,
    Channel,
    FieldStatus,
    RecordType,
)
from untangle.chat import api as chat_api
from untangle.chat import delivery
from untangle.chat import session as chat
from untangle.chat.limits import LimitKind
from untangle.copy_catalog.api import CopyKey
from untangle.evals import compliance_fixtures as fx
from untangle.evals import loading, transcript_guard, transcript_prompts
from untangle.evals.drivers import chat as conductor
from untangle.evals.models import CaseStatus, Dataset, GoldenCase, ScriptAnswer
from untangle.evals.models import Channel as EvalChannel
from untangle.evals.runner import api as runner_api
from untangle.evals.runner import runner
from untangle.evals.runner.failures import TargetUnavailableError
from untangle.orchestration import contracts as u12
from untangle.tenancy import api as tenancy

pytestmark = pytest.mark.usefixtures("base_de_u13")

AHORA = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
_ASEGURADO = Actor(actor_type=ActorType.INSURED)

#: Los campos de un siniestro, leidos del esquema de U4 y no copiados: una lista
#: propia deja de coincidir el dia que el esquema cambie, y la prueba seguiria en
#: verde midiendo campos que ya no existen.
_CAMPOS = tuple(d.key for d in fields.definitions_for(RecordType.CLAIM))


def _caso(tenant_id: str, *, campos: tuple[str, ...] = _CAMPOS) -> GoldenCase:
    return GoldenCase(
        case_key="DS-2/es/prueba-del-conductor",
        dataset=Dataset.DS_2,
        language="es",
        tenant=tenant_id,
        channel=EvalChannel.CHAT,
        script=tuple(
            ScriptAnswer(field_key=campo, text=f"respuesta de {campo}") for campo in campos
        ),
    )


def _grafo_que_captura(tenant_id: str, cifrador: crypto.Cipher) -> delivery.TurnHandler:
    """Un grafo que va fijando el campo que le toca del caso **que ya recibe**.

    No es una segunda implementacion de la captura: fija el siguiente campo sin
    mirar el texto, que es lo justo para que la completitud avance y el conductor
    tenga algo distinto que leer en cada vuelta. Lo que se mide aqui es el
    conductor, no la extraccion.

    **Este doble abria su propio caso, y esa es la forma exacta en que se escondio
    el defecto de la costura.** El grafo de verdad nunca abre ninguno: exige que
    llegue en el turno y levanta si no llega (`UnaddressedTurnError`). Un doble que
    aceptaba lo que produccion no puede producir --un turno sin caso-- dejaba pasar
    en verde la unica cosa que habia que comprobar, y el chat estuvo sin poder
    atender a nadie desde que se construyo sin que ninguna de las 2.363 pruebas lo
    notara. Ahora usa `turn.case_id`, que es lo que el de verdad hace.
    """
    vistos: set[str] = set()

    async def _handle(turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        assert turn.case_id is not None, "el canal abre el caso antes de entregar (BR1.1)"
        case_id = turn.case_id
        if case_id not in vistos:
            vistos.add(case_id)
            # A captura, que es donde un caso tiene bloques que preguntar. Lo hace
            # el nodo real; aqui es lo minimo para que el recorrido exista.
            await casos.apply_transition(
                tenant_id,
                case_id,
                CaseState.CAPTURING,
                context=rules.TransitionContext(now=AHORA, actor=_ASEGURADO, channel=Channel.CHAT),
            )
        else:
            vista = await casos.get_case(tenant_id, case_id)
            assert vista is not None
            pendientes = [c for c, listo in vista.completeness.per_field.items() if not listo]
            if pendientes:
                await casos.set_field(
                    tenant_id,
                    CaseField(
                        case_id=case_id,
                        field_key=pendientes[0],
                        value=cifrador.seal(turn.text),
                        status=FieldStatus.CONFIRMED,
                        evidence_turn_id=f"turno-{len(vista.completeness.per_field)}",
                        confirmed_aloud_at=AHORA,
                        updated_at=AHORA,
                    ),
                    cipher=cifrador,
                    actor=_ASEGURADO,
                )
        yield u12.FinalText(
            message_id=f"m-{turn.session_ref}",
            text="Anotado.",
            language=turn.language,
            case_id=case_id,
        )

    return _handle


async def test_la_apertura_es_el_primer_turno_antes_de_que_nadie_escriba(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """BR1.1 vista desde la conversacion que queda registrada, que es donde alguien
    la va a leer al calibrar al juez."""
    _, propia = dos_aseguradoras
    chat_api.install_turn_handler(_grafo_que_captura(propia, cifrador))

    transcripcion = await conductor.ChatDriver().run_case(_caso(propia))

    primero = transcripcion.turns[0]
    assert primero.speaker == "agent"
    assert "demostración" in primero.text, "la divulgacion, antes de nada"
    # Y antes que cualquier turno del asegurado: no basta con que exista.
    primer_asegurado = next(
        indice for indice, turno in enumerate(transcripcion.turns) if turno.speaker == "insured"
    )
    assert primer_asegurado > 0


async def test_el_campo_de_cada_turno_sale_del_caso_y_no_del_texto(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """La conducta que hace util al conductor: la agente puede preguntar en otro
    orden y la conversacion sigue. Se comprueba que los campos del guion se
    recorren, no que se repita el primero."""
    _, propia = dos_aseguradoras
    chat_api.install_turn_handler(_grafo_que_captura(propia, cifrador))

    transcripcion = await conductor.ChatDriver().run_case(_caso(propia))

    contestados = [t.field_key for t in transcripcion.turns if t.speaker == "insured"]
    assert len(set(contestados)) > 1, "si se repitiera el primero, esto seria 1"
    assert transcripcion.off_script_turns == 0, "el guion cubre lo que el caso pide"
    assert transcripcion.record["record_type"] == "claim"


async def test_una_conversacion_que_no_avanza_termina_igual(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """El techo de turnos es una salida. Sin el, un guion sin el campo que se pide
    deja la corrida colgada, que es peor que un caso en rojo: no se puede leer."""
    _, propia = dos_aseguradoras

    async def _grafo_que_no_avanza(turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        yield u12.FinalText(message_id="m1", text="Anotado.", language=turn.language)

    chat_api.install_turn_handler(_grafo_que_no_avanza)

    transcripcion = await conductor.ChatDriver().run_case(_caso(propia))

    asegurado = [t for t in transcripcion.turns if t.speaker == "insured"]
    # Termina, y termina **acotada**. El numero exacto no es el techo propio del
    # conductor sino el limite de mensajes por conversacion de la aseguradora, que
    # suele ser menor: una conversacion que se detiene por un limite no se
    # completo, y eso se ve aqui en vez de parecerse a una que llego al final.
    assert 0 < len(asegurado) <= conductor.MAX_TURNS
    # El caso **existe** --lo abre el canal en el primer turno-- y no capturo nada:
    # eso es exactamente lo que hay que poder leer de una conversacion que no
    # avanzo. Antes esta linea afirmaba `record == {}`, que era la costura rota
    # escrita como criterio: sin caso no habia registro porque no habia caso, y no
    # haber caso era el defecto.
    assert transcripcion.record["complete"] == 0, "no avanzo: ningun campo capturado"
    total = transcripcion.record["total"]
    assert isinstance(total, int)
    assert total > 0, "y el caso si existe, con sus campos por llenar"


async def test_correr_el_mismo_caso_muchas_veces_no_agota_el_cupo_del_dia(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """El dia fijo del conductor empieza en cero en cada conversacion.

    El 2026-10-12 catorce conversaciones salieron en rojo sin que nada estuviera roto:
    todas las corridas escriben en el mismo dia simulado, sus mensajes se sumaban y el
    canal empezo a rechazarlos por cupo diario. Aqui se deja ese dia ya agotado para el
    origen del caso y para el sitio, y la conversacion se conduce igual.
    """
    _, propia = dos_aseguradoras
    chat_api.install_turn_handler(_grafo_que_captura(propia, cifrador))
    caso = _caso(propia)
    config = tenancy.require(propia).chat
    gastado = await chat.open_session(
        tenant_id=propia,
        visitor_key_digest="nav-de-una-corrida-anterior",
        origin_digest="org-de-una-corrida-anterior",
        language="es",
        now=conductor.INICIO,
    )
    for _ in range(config.messages_per_site_per_day):
        await chat.count_message(gastado, now=conductor.INICIO)

    transcripcion = await conductor.ChatDriver().run_case(caso)

    asegurado = [t for t in transcripcion.turns if t.speaker == "insured"]
    assert len(asegurado) > 1, "con el cupo del sitio agotado no habria pasado del primer turno"
    assert transcripcion.record["record_type"] == "claim"


@pytest.mark.parametrize("limite", [LimitKind.ORIGIN, LimitKind.SITE_DAY])
def test_un_cupo_diario_agotado_deja_el_caso_sin_medir_y_lo_dice(limite: LimitKind) -> None:
    with pytest.raises(TargetUnavailableError, match=limite.value):
        conductor._si_es_el_cupo_del_dia_no_se_midio(limite, "una-aseguradora")


@pytest.mark.parametrize("limite", [LimitKind.SESSION, LimitKind.RATE, LimitKind.SIZE, None])
def test_un_limite_de_la_conversacion_no_es_cupo_del_dia(limite: LimitKind | None) -> None:
    conductor._si_es_el_cupo_del_dia_no_se_midio(limite, "una-aseguradora")


async def test_el_numero_del_caso_viaja_en_la_transcripcion(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """La guardia que lee lo dicho necesita el numero del propio caso: sin el, la agente
    que lo diga en voz alta pareceria estar revelando el de otra persona."""
    _, propia = dos_aseguradoras
    chat_api.install_turn_handler(_grafo_que_captura(propia, cifrador))

    transcripcion = await conductor.ChatDriver().run_case(_caso(propia))

    numero = transcripcion.case_number
    assert numero is not None, "la conversacion abrio un caso y la transcripcion no lo dice"
    vista = await casos.get_case_by_number(propia, numero)
    assert vista is not None, "el numero entregado es el de un caso de esta aseguradora"
    assert vista.state.value == transcripcion.record["state"]


async def test_cada_turno_deja_su_latencia_medida_con_el_reloj_de_verdad_y_sin_contar_la_espera(
    dos_aseguradoras: tuple[str, str],
    cifrador: crypto.Cipher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La cifra que la linea base publica sale de aqui: lo que tardo la primera palabra de
    cada respuesta, por la entrega del canal. El grafo dice primero la frase de espera y
    contesta despues de 60 ms: la espera no es la primera palabra, asi que la latencia no
    puede ser menor que lo que tardo la respuesta de verdad. Con el reloj simulado del
    conductor --que solo mueve las fechas-- saldria cero."""
    _, propia = dos_aseguradoras
    base = _grafo_que_captura(propia, cifrador)

    async def _grafo_lento(turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        yield u12.Waiting(copy_key=CopyKey("chat.turn.waiting"), text="Un momento")
        await asyncio.sleep(0.06)
        async for evento in base(turn):
            yield evento

    chat_api.install_turn_handler(_grafo_lento)
    # La marca de cuando el servidor "recibe" el mensaje, como la toma la ruta: antes de
    # admitirlo. Se mira lo que el conductor le pasa a la entrega.
    marcas: list[float | None] = []
    entregar = delivery.deliver

    async def _espia(*args: Any, **kwargs: Any) -> delivery.Delivered:
        marcas.append(kwargs.get("received_monotonic"))
        return await entregar(*args, **kwargs)

    monkeypatch.setattr(delivery, "deliver", _espia)

    transcripcion = await conductor.ChatDriver().run_case(_caso(propia))

    asegurado = [t for t in transcripcion.turns if t.speaker == "insured"]
    assert len(asegurado) > 1
    assert len(transcripcion.chat_latencies) == len(asegurado), "un valor por turno contestado"
    for latencia in transcripcion.chat_latencies:
        assert latencia.language == "es", "el idioma en que se atendio el turno"
        assert latencia.first_word_ms >= 50
    assert len(marcas) == len(asegurado)
    ahora = time.monotonic()
    assert all(m is not None and m < ahora for m in marcas), "una marca del reloj monotono"


@pytest.mark.parametrize("que_dice", ["solo-espera", "solo-error"])
async def test_un_turno_sin_respuesta_no_deja_latencia(
    dos_aseguradoras: tuple[str, str], que_dice: str
) -> None:
    """Un error o una frase de espera sin respuesta no es una primera palabra: la cifra no se
    mejora con turnos que no contestaron."""
    _, propia = dos_aseguradoras

    async def _grafo_mudo(turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        if que_dice == "solo-espera":
            yield u12.Waiting(copy_key=CopyKey("chat.turn.waiting"), text="Un momento")
        else:
            yield u12.TurnError(
                code="internal_error", copy_key=CopyKey("chat.turn.error"), text="Tuve un problema"
            )

    chat_api.install_turn_handler(_grafo_mudo)

    transcripcion = await conductor.ChatDriver().run_case(_caso(propia))

    assert any(t.speaker == "insured" for t in transcripcion.turns), "si hubo turnos de la persona"
    assert transcripcion.chat_latencies == ()


@pytest.fixture
def corredor_con_el_conductor_de_chat() -> Iterator[None]:
    runner_api.reset()
    runner_api.register_driver(conductor.ChatDriver())
    transcript_guard.register_transcript_guard()
    transcript_prompts.register_transcript_prompts()
    yield
    runner_api.reset()


@pytest.mark.usefixtures("corredor_con_el_conductor_de_chat")
@pytest.mark.parametrize(
    ("dice", "guardia", "prompts"),
    [
        ("nada", "pass", "pass"),
        ("afirma-cobertura", "fail", "pass"),
        ("copia-su-prompt", "pass", "fail"),
    ],
)
async def test_por_el_conductor_de_verdad_lo_que_llega_a_la_persona_decide_el_caso(
    dos_aseguradoras: tuple[str, str],
    cifrador: crypto.Cipher,
    dice: str,
    guardia: str,
    prompts: str,
) -> None:
    """Un grafo que deja pasar una afirmacion de cobertura --la que la guardia de salida
    habria detenido-- o que copia su propio prompt pone el caso en rojo, aunque el registro
    quede exactamente como se esperaba. Es el hueco que tenia RT-10: media cuantos datos
    quedaron y no lo que se dijo."""
    _, propia = dos_aseguradoras
    base = _grafo_que_captura(propia, cifrador)
    afirmacion = next(
        fila.text
        for fila in fx.load_fixtures("es", paths.repo_root()).guard
        if fila.expected_category is not None and fila.expected_category.value == "coverage_promise"
    )
    prompt = (paths.repo_root() / "app" / "config" / "prompts" / "conversation.es.md").read_text(
        encoding="utf-8"
    )
    linea_del_prompt = max(prompt.splitlines(), key=len)
    extra = {"afirma-cobertura": afirmacion, "copia-su-prompt": linea_del_prompt}.get(dice)

    async def _grafo(turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        async for evento in base(turn):
            yield evento
        if extra is not None:
            yield u12.FinalText(
                message_id=f"extra-{turn.session_ref}",
                text=extra,
                language=turn.language,
                case_id=turn.case_id,
            )

    chat_api.install_turn_handler(_grafo)

    resultado, _ = await runner._run_one(
        _caso(propia), run_id="run-prueba", root=paths.repo_root(), traces_available=False
    )

    assert resultado.criteria_results == {
        runner_api.TRANSCRIPT_GUARD_CRITERION: guardia,
        runner_api.TRANSCRIPT_PROMPTS_CRITERION: prompts,
    }
    rojo = "fail" in (guardia, prompts)
    assert resultado.status is (CaseStatus.FAILED if rojo else CaseStatus.PASSED)


# --- Los ataques conversados de DS-6: que el guion se entregue como se escribio -------------

_ATAQUES_CONVERSADOS = (
    "rt1-direct-injection-chat",
    "rt1-humanity-claim-chat",
    "rt3-pressure-chat",
    "rt5-config-disclosure-chat",
    "rt6-fault-legal-advice-chat",
)


def _grafo_que_anota_lo_que_se_pidio(
    case: GoldenCase, cifrador: crypto.Cipher, *, se_come: frozenset[str] = frozenset()
) -> delivery.TurnHandler:
    """Un grafo que anota el campo al que responde cada texto del guion, y nada mas.

    Reconoce el campo por el texto del guion --el conductor eligio la respuesta por el campo
    que el caso pedia, asi que es el mismo--. `se_come` son textos que **no** anota: un
    ataque que se traga el dato, que es para lo que existe la segunda respuesta limpia. No
    es la captura de verdad: mide el conductor y el guion, no la extraccion.
    """
    campo_de = {respuesta.text: respuesta.field_key for respuesta in case.script}
    assert case.tenant is not None
    tenant_id = case.tenant
    abiertos: set[str] = set()

    async def _handle(turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        assert turn.case_id is not None
        if turn.case_id not in abiertos:
            abiertos.add(turn.case_id)
            await casos.apply_transition(
                tenant_id,
                turn.case_id,
                CaseState.CAPTURING,
                context=rules.TransitionContext(now=AHORA, actor=_ASEGURADO, channel=Channel.CHAT),
            )
        if turn.text not in se_come:
            await casos.set_field(
                tenant_id,
                CaseField(
                    case_id=turn.case_id,
                    field_key=campo_de[turn.text],
                    value=cifrador.seal(turn.text),
                    status=FieldStatus.CONFIRMED,
                    evidence_turn_id=f"turno-{len(abiertos)}-{campo_de[turn.text]}",
                    confirmed_aloud_at=AHORA,
                    updated_at=AHORA,
                ),
                cipher=cifrador,
                actor=_ASEGURADO,
            )
        yield u12.FinalText(
            message_id=f"m-{turn.session_ref}",
            text="Anotado.",
            language=turn.language,
            case_id=turn.case_id,
        )

    return _handle


@pytest.mark.parametrize("idioma", ["es", "en"])
@pytest.mark.parametrize("slug", _ATAQUES_CONVERSADOS)
@pytest.mark.parametrize(
    "el_ataque_se_come_el_dato", [False, True], ids=["anota", "se-come-el-dato"]
)
async def test_el_guion_de_un_ataque_conversado_se_entrega_en_su_orden_y_cierra_el_reporte(
    cifrador: crypto.Cipher, slug: str, idioma: str, el_ataque_se_come_el_dato: bool
) -> None:
    """Con el conductor de verdad: identidad, heridos, que paso, cuando y donde, cada uno una
    vez; el ataque va pegado al dato. Y si la agente no anota la respuesta con el ataque, la
    segunda respuesta limpia la reemplaza y el reporte termina igual: cinco de cinco."""
    caso = loading.load_case(paths.repo_root() / "app/evals/cases/ds6" / slug / f"{idioma}.yaml")
    ataques = frozenset(
        caso.answers_for(campo)[0].text
        for campo in ("injuries", "description", "incident_datetime")
    )
    chat_api.install_turn_handler(
        _grafo_que_anota_lo_que_se_pidio(
            caso, cifrador, se_come=ataques if el_ataque_se_come_el_dato else frozenset()
        )
    )

    transcripcion = await conductor.ChatDriver().run_case(caso)

    dicho = [t.text for t in transcripcion.turns if t.speaker == "insured"]
    por_campo = {
        campo: [r.text for r in caso.answers_for(campo)]
        for campo in (
            "identity_and_policy",
            "injuries",
            "description",
            "incident_datetime",
            "location",
        )
    }
    if el_ataque_se_come_el_dato:
        esperado = [
            por_campo["identity_and_policy"][0],
            *por_campo["injuries"],
            *por_campo["description"],
            *por_campo["incident_datetime"],
            por_campo["location"][0],
        ]
    else:
        esperado = [por_campo[c][0] for c in por_campo]
    assert dicho == esperado
    assert transcripcion.off_script_turns == 0, "el guion cubre cada campo que se pide"
    assert transcripcion.record["complete"] == transcripcion.record["total"] == 5
    assert transcripcion.record["language"] == idioma


# --- Las cotizaciones de DS-4: pedir por bloques sin leer de vuelta, confirmar al final ----------

_COTIZACIONES = (
    "ds4/quote-end-to-end",
    "ds4/quote-price-pressure-conversation",
)
#: Lo que el codigo deriva de lo que la persona dice, igual que `extraction._derived_fields`.
_DERIVADOS = {
    "vehicle_year": ("vehicle_age_years", "12"),
    "prior_coverage_active": ("lapse_months", "0"),
}


def _grafo_de_cotizacion_de_hoy(
    case: GoldenCase, cifrador: crypto.Cipher, *, no_anota: frozenset[str] = frozenset()
) -> delivery.TurnHandler:
    """Un grafo que se comporta como el de hoy ante una solicitud de cotizacion (2026-10-08).

    **No lee de vuelta cada bloque.** Anota cada respuesta como `stated` --los campos de la
    cotizacion exigen lectura, asi que no cuentan--, deriva lo que el codigo deriva y solo
    confirma cuando llega el si de la lectura de la solicitud entera, que es la respuesta que
    el guion da bajo la clave del ultimo bloque. Una respuesta que no es de ningun campo --una
    confirmacion de bloque que nadie pidio, o la frase de "no se" del asegurado simulado-- no
    anota nada, igual que la agente de verdad. `no_anota` son respuestas que la agente tampoco
    anota (una presion por un precio).
    """
    assert case.tenant is not None
    tenant_id = case.tenant
    campo_de = {r.text: r.field_key for r in case.script}
    es_de_un_campo = {d.key for d in fields.definitions_for(RecordType.QUOTE_REQUEST)}
    guardados: dict[str, str] = {}
    abiertos: set[str] = set()

    async def _guardar(
        case_id: str, campo: str, texto: str, estado: FieldStatus, turno: str
    ) -> None:
        guardados[campo] = texto
        await casos.set_field(
            tenant_id,
            CaseField(
                case_id=case_id,
                field_key=campo,
                value=cifrador.seal(texto),
                status=estado,
                evidence_turn_id=turno,
                confirmed_aloud_at=AHORA if estado is FieldStatus.CONFIRMED else None,
                updated_at=AHORA,
            ),
            cipher=cifrador,
            actor=_ASEGURADO,
        )

    async def _handle(turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
        assert turn.case_id is not None
        case_id = turn.case_id
        if case_id not in abiertos:
            abiertos.add(case_id)
            await casos.apply_transition(
                tenant_id,
                case_id,
                CaseState.CAPTURING,
                context=rules.TransitionContext(now=AHORA, actor=_ASEGURADO, channel=Channel.CHAT),
            )
        campo = campo_de.get(turn.text)
        turno = f"turno-{len(guardados)}"
        if campo in es_de_un_campo and turn.text not in no_anota:
            assert campo is not None
            await _guardar(case_id, campo, turn.text, FieldStatus.STATED, turno)
            if campo in _DERIVADOS:
                derivado, valor = _DERIVADOS[campo]
                await _guardar(case_id, derivado, valor, FieldStatus.STATED, turno)
        elif campo == "quote_history":
            # El si de la lectura entera: confirma todo lo dicho, de una vez.
            for dicho, texto in list(guardados.items()):
                await _guardar(case_id, dicho, texto, FieldStatus.CONFIRMED, turno)
        yield u12.FinalText(
            message_id=f"m-{turn.session_ref}",
            text="Anotado.",
            language=turn.language,
            case_id=case_id,
        )

    return _handle


@pytest.mark.parametrize("idioma", ["es", "en"])
@pytest.mark.parametrize("cotizacion", _COTIZACIONES)
async def test_una_cotizacion_con_el_grafo_de_hoy_llega_a_17_de_17_sin_salirse_de_guion(
    cifrador: crypto.Cipher, cotizacion: str, idioma: str
) -> None:
    """Pide por bloques sin leer de vuelta y confirma una sola vez al final: el conductor
    contesta lo que el nodo pregunta, y el guion llega a 17 de 17 con cada respuesta usada.

    Es la prueba que habria visto la primera corrida contra el modelo: el conductor de antes
    seguia a `next_block`, le contestaba la confirmacion del primer bloque a una agente que
    preguntaba por el vehiculo, y la solicitud se quedaba en 0 de 17.
    """
    slug = cotizacion.split("/")[1]
    caso = loading.load_case(paths.repo_root() / "app/evals/cases/ds4" / slug / f"{idioma}.yaml")
    es_presion = slug == "quote-price-pressure-conversation"
    pendientes_de_precio = caso.answers_for("use_type")[:-1] if es_presion else ()
    chat_api.install_turn_handler(
        _grafo_de_cotizacion_de_hoy(
            caso, cifrador, no_anota=frozenset(r.text for r in pendientes_de_precio)
        )
    )

    transcripcion = await conductor.ChatDriver().run_case(caso)

    dicho = [t.text for t in transcripcion.turns if t.speaker == "insured"]
    # El orden en que el conductor entrego el guion: un campo a la vez, las presiones del uso
    # antes de su respuesta, y la confirmacion al final.
    assert dicho == [r.text for r in caso.script]
    assert transcripcion.off_script_turns == 0, "el conductor pidio algo que el guion no tiene"
    assert transcripcion.record["record_type"] == "quote_request"
    assert transcripcion.record["complete"] == transcripcion.record["total"] == 17
    assert transcripcion.record["language"] == idioma
