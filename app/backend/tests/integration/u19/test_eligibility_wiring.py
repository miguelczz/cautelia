"""La elegibilidad corre de verdad y su respuesta llega (U19, BR2.3, BR2.5).

**El hueco que esto cierra.** `compose_eligibility_reply` estaba escrita y probada
desde U19 y su **único consumidor era el corredor de evaluaciones**: en el camino
real, Sunmeadow ofrecía cotizar y no respondía nunca. Es el mismo hueco que U19
encontró en los siniestros, y es lo que mantenía la cotización como criterio
bloqueante de la pasada de publicación.

Lo que estas pruebas vigilan no es que el motor decida bien --eso lo prueban sus
unitarias contra los casos del propio YAML-- sino que **lo decidido llegue**: que se
evalúe fuera del turno, que quede guardado, y que el turno siguiente lo diga.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.case_record import fields as case_fields
from untangle.case_record.models import (
    Actor,
    ActorType,
    CaseField,
    CaseState,
    Channel,
    FieldStatus,
    RecordType,
    Speaker,
)
from untangle.chat import session as chat_session
from untangle.orchestration import eligibility_run, output, quote_reply, transcript_writer
from untangle.rules import eligibility
from untangle.rules import eligibility_repository as repositorio
from untangle.tenancy import api as tenancy

from .conftest import nueva_solicitud

pytestmark = pytest.mark.usefixtures("base_de_u19")

AHORA = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)

#: Una solicitud limpia: uso particular, sin título de salvamento, sin siniestros
#: con culpa, licencia veterana y vehículo nuevo. Los valores son los que el
#: esquema guarda, en el texto en que los guarda.
LIMPIA = {
    "use_type": "personal",
    "salvage_title": "false",
    "at_fault_losses_3y": "0",
    "license_years": "10",
    "vehicle_age_years": "2",
}


def _completa(valores: dict[str, str]) -> dict[str, str]:
    """La solicitud con sus diecisiete campos: los de las reglas y el resto rellenado.

    La respuesta al chat y la derivacion esperan a la solicitud completa (2026-10-08);
    las reglas leen solo cinco campos, y con esos cinco la evaluacion ya sale.
    """
    return {
        **{d.key: "dato" for d in case_fields.definitions_for(RecordType.QUOTE_REQUEST)},
        **valores,
    }


async def _sembrar_campos(
    tenant_id: str, case_id: str, cifrador: crypto.Cipher, valores: dict[str, str]
) -> None:
    for clave, valor in valores.items():
        await casos.set_field(
            tenant_id,
            CaseField(
                case_id=case_id,
                field_key=clave,
                value=cifrador.seal(valor),
                status=FieldStatus.CONFIRMED,
                evidence_turn_id=f"{case_id}-turno",
                confirmed_aloud_at=AHORA,
                updated_at=AHORA,
            ),
            cipher=cifrador,
            actor=Actor(actor_type=ActorType.INSURED),
            channel=Channel.CHAT,
        )


async def test_una_solicitud_completa_se_evalua_y_queda_guardada(
    aseguradora_que_cotiza: str, cifrador: crypto.Cipher
) -> None:
    """El camino entero: se evalúa y deja su fila, que es lo que el turno lee después."""
    case_id = await nueva_solicitud(aseguradora_que_cotiza, tipo=RecordType.QUOTE_REQUEST)
    await _sembrar_campos(aseguradora_que_cotiza, case_id, cifrador, LIMPIA)

    salida = await eligibility_run.evaluate_and_store(
        aseguradora_que_cotiza, case_id, cipher=cifrador, now=AHORA
    )

    assert salida is not None
    assert salida.outcome is eligibility.EligibilityOutcomeKind.ELIGIBLE
    # Y **está en la base**, no solo devuelta: el valor de retorno lo podría dar una
    # versión que no guardara nada, y entonces el turno siguiente no encontraría nada.
    guardada = await repositorio.eligibility_of(aseguradora_que_cotiza, case_id)
    assert guardada is not None
    assert guardada.outcome is salida.outcome
    assert guardada.band is salida.band


async def test_una_solicitud_incompleta_no_se_evalua_y_no_guarda_nada(
    aseguradora_que_cotiza: str, cifrador: crypto.Cipher
) -> None:
    """Con un campo de menos no se decide, y **no se dice que no**.

    Evaluar con datos que faltan es como una solicitud mal capturada terminaría
    "elegible" (BR1.3). Y dejar una fila diciendo "no elegible" sería peor: el turno
    la leería y le diría que no a quien todavía no ha terminado de contar.
    """
    case_id = await nueva_solicitud(aseguradora_que_cotiza, tipo=RecordType.QUOTE_REQUEST)
    sin_un_campo = {k: v for k, v in LIMPIA.items() if k != "license_years"}
    await _sembrar_campos(aseguradora_que_cotiza, case_id, cifrador, sin_un_campo)

    salida = await eligibility_run.evaluate_and_store(
        aseguradora_que_cotiza, case_id, cipher=cifrador, now=AHORA
    )

    assert salida is None
    assert await repositorio.eligibility_of(aseguradora_que_cotiza, case_id) is None


async def test_volver_a_evaluar_reemplaza_y_no_acumula(
    aseguradora_que_cotiza: str, cifrador: crypto.Cipher
) -> None:
    """Una fila por caso: si el visitante corrige un campo, vale lo último.

    Sin el reemplazo, la bandeja podría mostrar una evaluación vieja de un caso que
    ya cambió, y cuál de las dos sale dependería del orden de lectura.
    """
    case_id = await nueva_solicitud(aseguradora_que_cotiza, tipo=RecordType.QUOTE_REQUEST)
    await _sembrar_campos(aseguradora_que_cotiza, case_id, cifrador, LIMPIA)
    primera = await eligibility_run.evaluate_and_store(
        aseguradora_que_cotiza, case_id, cipher=cifrador, now=AHORA
    )
    assert primera is not None

    # El mismo caso, corregido a un título de salvamento: deja de ser elegible.
    await _sembrar_campos(aseguradora_que_cotiza, case_id, cifrador, {"salvage_title": "true"})
    segunda = await eligibility_run.evaluate_and_store(
        aseguradora_que_cotiza, case_id, cipher=cifrador, now=AHORA
    )

    assert segunda is not None
    assert segunda.outcome is not primera.outcome
    guardada = await repositorio.eligibility_of(aseguradora_que_cotiza, case_id)
    assert guardada is not None
    assert guardada.outcome is segunda.outcome


async def test_la_elegibilidad_de_un_caso_no_se_lee_desde_otra_aseguradora(
    aseguradora_que_cotiza: str, otra_aseguradora: str, cifrador: crypto.Cipher
) -> None:
    """El aislamiento de la tabla nueva, ejercido y no supuesto (M9).

    La política de fila filtra antes, así que desde la otra aseguradora el caso no
    existe --y no porque se compare y se disimule--.
    """
    case_id = await nueva_solicitud(aseguradora_que_cotiza, tipo=RecordType.QUOTE_REQUEST)
    await _sembrar_campos(aseguradora_que_cotiza, case_id, cifrador, LIMPIA)
    await eligibility_run.evaluate_and_store(
        aseguradora_que_cotiza, case_id, cipher=cifrador, now=AHORA
    )

    assert await repositorio.eligibility_of(aseguradora_que_cotiza, case_id) is not None
    assert await repositorio.eligibility_of(otra_aseguradora, case_id) is None


# --- El turno que la dice (BR2.3) ---------------------------------------------


async def test_el_turno_de_una_solicitud_completa_responde_con_su_elegibilidad(
    aseguradora_que_cotiza: str, cifrador: crypto.Cipher
) -> None:
    """La costura que faltaba, por el camino real: el turno **lee** y responde.

    Sin esto, quien terminara de dar sus diecisiete campos no recibiría nada: la
    frase está escrita desde U19 y su único consumidor era el corredor de
    evaluaciones. Se comprueba sobre el texto que sale del turno, no sobre la
    función que lo compone --esa ya tiene sus unitarias--.
    """
    case_id = await nueva_solicitud(aseguradora_que_cotiza, tipo=RecordType.QUOTE_REQUEST)
    await _sembrar_campos(aseguradora_que_cotiza, case_id, cifrador, LIMPIA)
    await eligibility_run.evaluate_and_store(
        aseguradora_que_cotiza, case_id, cipher=cifrador, now=AHORA
    )

    puerto = eligibility_run.EligibilityAdapter(cipher=cifrador, clock=lambda: AHORA)
    vista = await puerto.stored(aseguradora_que_cotiza, case_id)

    assert vista is not None
    # Lo que cruza al turno son **tres cadenas**, y los identificadores de las
    # reglas que decidieron no: son para la traza y la bandeja (BR2.3).
    assert vista.outcome == "eligible"
    assert not hasattr(vista, "deciding_rules")
    texto = quote_reply.compose_eligibility_reply(
        vista.outcome, vista.band, vista.explanation_key, language="es"
    )
    assert texto.strip(), "la respuesta salió vacía"
    # Compuerta dura BR3.1: ni una cifra, ni un símbolo de moneda, ni un porcentaje.
    assert not re.search(r"[\d%$€]", texto), texto


async def test_sin_elegibilidad_guardada_el_puerto_dice_que_todavia_no(
    aseguradora_que_cotiza: str, cifrador: crypto.Cipher
) -> None:
    """`None` es "espera", nunca "no elegible".

    El control contrario del de arriba: sin él, una versión que devolviera una
    salida por defecto le diría que no a quien todavía no se le ha mirado, y la
    diferencia entre las dos cosas es justo lo que esta unidad existe para no
    perder.
    """
    case_id = await nueva_solicitud(aseguradora_que_cotiza, tipo=RecordType.QUOTE_REQUEST)
    puerto = eligibility_run.EligibilityAdapter(cipher=cifrador, clock=lambda: AHORA)

    assert await puerto.stored(aseguradora_que_cotiza, case_id) is None


# --- La entrega sin turno siguiente (tanda 2) ---------------------------------


@dataclass
class _NotificadorFalso:
    """Un oyente que se queda con lo que le entregan, y dice si habia alguien."""

    hay_quien_escuche: bool = True
    entregados: list[tuple[str, str, str]] = field(default_factory=list)

    async def notify(  # noqa: PLR0913 -- la firma del puerto CaseNotifier
        self,
        tenant_id: str,
        case_id: str,
        *,
        text: str,
        citations: tuple[object, ...] = (),
        suggestions: tuple[str, ...] = (),
        coverage_outcome: str | None = None,
        language: str | None = None,
    ) -> bool:
        del citations, suggestions, coverage_outcome
        self.entregados.append((tenant_id, case_id, text))
        return self.hay_quien_escuche


async def test_la_respuesta_llega_sin_que_la_persona_vuelva_a_escribir(
    aseguradora_que_cotiza: str, cifrador: crypto.Cipher
) -> None:
    """El hueco que esta tanda cierra, por el camino real.

    Quien termina de dar sus diecisiete campos **no vuelve a escribir**. Hasta la
    tanda 1, la respuesta quedaba guardada y solo la leía un turno siguiente que
    nunca llegaba. Lo que se comprueba es que **sale por el canal**, no que esté en
    la base --eso ya lo prueban las de arriba--.
    """
    case_id = await nueva_solicitud(aseguradora_que_cotiza, tipo=RecordType.QUOTE_REQUEST)
    await _sembrar_campos(aseguradora_que_cotiza, case_id, cifrador, _completa(LIMPIA))
    oyente = _NotificadorFalso()
    puerto = eligibility_run.EligibilityAdapter(
        cipher=cifrador, clock=lambda: AHORA, notifier=oyente
    )

    vista = await puerto.evaluate(aseguradora_que_cotiza, case_id)

    assert vista is not None
    assert len(oyente.entregados) == 1, oyente.entregados
    _, entregado_a, texto = oyente.entregados[0]
    assert entregado_a == case_id
    assert texto.strip()
    # Compuerta dura BR3.1, sobre el texto que **de verdad sale**: ni cifra, ni
    # simbolo de moneda, ni porcentaje. La guardia de salida es quien los caza, y
    # esta aserción es la que comprueba que el texto pasó por ella.
    assert not re.search(r"[\d%$€]", texto), texto


async def test_lo_que_sale_en_pantalla_queda_en_la_transcripcion(
    aseguradora_que_cotiza: str, cifrador: crypto.Cipher
) -> None:
    """2026-10-12: todo texto de la agente que se publica se guarda. La respuesta de la
    cotizacion llegaba a la pantalla y, al volver a la pagina, ya no estaba."""
    case_id = await nueva_solicitud(aseguradora_que_cotiza, tipo=RecordType.QUOTE_REQUEST)
    await _sembrar_campos(aseguradora_que_cotiza, case_id, cifrador, _completa(LIMPIA))
    oyente = _NotificadorFalso()
    puerto = eligibility_run.EligibilityAdapter(
        cipher=cifrador, clock=lambda: AHORA, notifier=oyente
    )

    await puerto.evaluate(aseguradora_que_cotiza, case_id)

    [(_, _, publicado)] = oyente.entregados
    guardados = [
        t.text_redacted
        for t in await casos.transcript_of(aseguradora_que_cotiza, case_id)
        if t.speaker is Speaker.AGENT
    ]
    assert guardados == [publicado]


async def test_una_solicitud_incompleta_no_entrega_nada(
    aseguradora_que_cotiza: str, cifrador: crypto.Cipher
) -> None:
    """El control contrario: sin evaluación no hay nada que decir.

    Sin él, una versión que notificara siempre le mandaría a quien va por el tercer
    campo una respuesta sobre una solicitud que no ha terminado de dar.
    """
    case_id = await nueva_solicitud(aseguradora_que_cotiza, tipo=RecordType.QUOTE_REQUEST)
    sin_un_campo = {k: v for k, v in LIMPIA.items() if k != "license_years"}
    await _sembrar_campos(aseguradora_que_cotiza, case_id, cifrador, sin_un_campo)
    oyente = _NotificadorFalso()
    puerto = eligibility_run.EligibilityAdapter(
        cipher=cifrador, clock=lambda: AHORA, notifier=oyente
    )

    assert await puerto.evaluate(aseguradora_que_cotiza, case_id) is None
    assert oyente.entregados == []


async def test_sin_nadie_escuchando_la_respuesta_sigue_guardada(
    aseguradora_que_cotiza: str, cifrador: crypto.Cipher
) -> None:
    """Que la pestaña esté cerrada no pierde la respuesta.

    `False` del notificador no es un fallo --el caso pudo llegar por la voz-- y lo
    que importa es que la fila quede: el turno siguiente la lee si la persona
    vuelve. Sin esta prueba, una versión que solo notificara y no guardara pasaría
    la de arriba y perdería toda respuesta de quien cerró la pestaña.
    """
    case_id = await nueva_solicitud(aseguradora_que_cotiza, tipo=RecordType.QUOTE_REQUEST)
    await _sembrar_campos(aseguradora_que_cotiza, case_id, cifrador, _completa(LIMPIA))
    oyente = _NotificadorFalso(hay_quien_escuche=False)
    puerto = eligibility_run.EligibilityAdapter(
        cipher=cifrador, clock=lambda: AHORA, notifier=oyente
    )

    await puerto.evaluate(aseguradora_que_cotiza, case_id)

    assert len(oyente.entregados) == 1, "se intentó entregar, que es lo correcto"
    assert await repositorio.eligibility_of(aseguradora_que_cotiza, case_id) is not None


async def test_sin_notificador_la_evaluacion_sigue_funcionando(
    aseguradora_que_cotiza: str, cifrador: crypto.Cipher
) -> None:
    """Un despliegue sin el canal enchufado evalúa y guarda igual.

    Es el comportamiento de la tanda 1, que sigue siendo correcto: la respuesta
    queda y el turno siguiente la lee. Lo que no puede pasar es que la falta del
    canal haga fallar la evaluación.
    """
    case_id = await nueva_solicitud(aseguradora_que_cotiza, tipo=RecordType.QUOTE_REQUEST)
    await _sembrar_campos(aseguradora_que_cotiza, case_id, cifrador, LIMPIA)
    puerto = eligibility_run.EligibilityAdapter(cipher=cifrador, clock=lambda: AHORA)

    vista = await puerto.evaluate(aseguradora_que_cotiza, case_id)

    assert vista is not None
    assert await repositorio.eligibility_of(aseguradora_que_cotiza, case_id) is not None


# --- Del caso al navegador: la costura completa -------------------------------


async def test_del_caso_se_llega_al_navegador_que_escucha(
    aseguradora_que_cotiza: str, cifrador: crypto.Cipher
) -> None:
    """La pieza del canal: resolver **quién escucha** por un caso.

    Es lo que no existía en esa dirección. El núcleo dice "hay algo que decir de
    este caso" y no sabe que existen navegadores; esta consulta es la única que ata
    el caso con la pestaña abierta, y pasa por la conversación, que es lo único que
    conoce a los dos.
    """
    case_id = await nueva_solicitud(aseguradora_que_cotiza, tipo=RecordType.QUOTE_REQUEST)
    clave = tenancy.new_visitor_key()
    visitante = await tenancy.resolve_visitor_key(
        tenant_id=aseguradora_que_cotiza, visitor_key=clave, origin="prueba"
    )
    conversacion = await chat_session.open_session(
        tenant_id=aseguradora_que_cotiza,
        visitor_key_digest=visitante.visitor_key_hash,
        origin_digest=visitante.origin,
        language="es",
        now=AHORA,
    )
    await chat_session.attach_case(conversacion, case_id=case_id)

    escucha = await chat_session.listener_of(aseguradora_que_cotiza, case_id)

    assert escucha is not None
    assert escucha.visitor_key_digest == visitante.visitor_key_hash
    assert escucha.language == "es"


async def test_un_caso_sin_conversacion_no_tiene_a_quien_avisar(
    aseguradora_que_cotiza: str,
) -> None:
    """El control contrario, y no es decorativo.

    Un caso que llegó por la voz, o uno cuya pestaña se cerró, no tiene oyente. Sin
    esta prueba, una consulta que devolviera cualquier conversación de la
    aseguradora pasaría la de arriba y le mandaría la respuesta de un caso **a otro
    visitante**, que es una fuga entre personas dentro de la misma aseguradora.
    """
    case_id = await nueva_solicitud(aseguradora_que_cotiza, tipo=RecordType.QUOTE_REQUEST)
    clave = tenancy.new_visitor_key()
    visitante = await tenancy.resolve_visitor_key(
        tenant_id=aseguradora_que_cotiza, visitor_key=clave, origin="prueba"
    )
    # Una conversación viva de **otra** persona, sin caso atado.
    await chat_session.open_session(
        tenant_id=aseguradora_que_cotiza,
        visitor_key_digest=visitante.visitor_key_hash,
        origin_digest=visitante.origin,
        language="es",
        now=AHORA,
    )

    assert await chat_session.listener_of(aseguradora_que_cotiza, case_id) is None


async def test_la_respuesta_sale_por_la_guardia_y_no_por_el_lado(
    aseguradora_que_cotiza: str, cifrador: crypto.Cipher, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Todo texto que llega al asegurado pasa por la guardia de salida (M6).

    **Esta prueba existe porque la obvia no podía distinguir.** Comprobar que el
    texto no lleva cifras ni símbolos de moneda pasa igual con la guardia puesta y
    quitada: las frases salen del catálogo y no llevan ninguna de las dos. Se
    comprobó rompiéndolo --saltarse la puerta dejaba las doce pruebas en verde--.

    Lo que se comprueba es que **la puerta se usó**, y para un control obligatorio
    eso no es mirar la implementación: la regla es literalmente "pasa por aquí". La
    guardia se sustituye por una que marca lo que ve; si el texto entregado no
    lleva la marca, es que alguien la esquivó.

    Y no es ceremonia: la compuerta dura de esta unidad prohíbe que una respuesta
    lleve un importe, un símbolo de moneda o un porcentaje **en cualquier idioma**,
    y el módulo que compone la frase no construye su propio detector, precisamente
    porque la guardia existe. Esta es una salida nueva: antes el único texto que
    llegaba al asegurado salía del turno.
    """

    @dataclass
    class _Resultado:
        text_out: str
        copy_keys: tuple[str, ...] = ()

    vistos: list[str] = []

    async def _guardia_que_marca(text: str, **_: object) -> _Resultado:
        vistos.append(text)
        return _Resultado(text_out=f"[revisado] {text}")

    monkeypatch.setattr(output, "guard_output", _guardia_que_marca)

    case_id = await nueva_solicitud(aseguradora_que_cotiza, tipo=RecordType.QUOTE_REQUEST)
    await _sembrar_campos(aseguradora_que_cotiza, case_id, cifrador, _completa(LIMPIA))
    oyente = _NotificadorFalso()
    puerto = eligibility_run.EligibilityAdapter(
        cipher=cifrador, clock=lambda: AHORA, notifier=oyente
    )

    await puerto.evaluate(aseguradora_que_cotiza, case_id)

    assert len(vistos) == 1, "la guardia no vio el texto, o lo vio dos veces"
    _, _, entregado = oyente.entregados[0]
    assert entregado.startswith("[revisado] "), entregado


async def _con_un_turno(tenant_id: str, case_id: str) -> None:
    """La derivacion se ata a un turno que exista: la conversacion ya tuvo uno."""
    await transcript_writer.record_person_turn(
        transcript_writer.TranscriptScope(
            tenant_id=tenant_id, case_id=case_id, channel=Channel.CHAT, language="es"
        ),
        text="Quiero una cotización",
        now=AHORA,
    )


async def test_la_solicitud_que_va_a_suscriptor_llega_a_su_cola(
    aseguradora_que_cotiza: str, cifrador: crypto.Cipher
) -> None:
    """C8, visto el 2026-10-07: quedaba en captura y la cola del suscriptor solo lista
    casos derivados. Con el control positivo: la elegible no se deriva."""
    # En captura, como queda una solicitud mientras la persona da sus datos.
    referida = await nueva_solicitud(
        aseguradora_que_cotiza, tipo=RecordType.QUOTE_REQUEST, estado=CaseState.CAPTURING
    )
    elegible = await nueva_solicitud(
        aseguradora_que_cotiza, tipo=RecordType.QUOTE_REQUEST, estado=CaseState.CAPTURING
    )
    for caso, valores in (
        (referida, _completa({**LIMPIA, "at_fault_losses_3y": "2"})),
        (elegible, _completa(LIMPIA)),
    ):
        await _con_un_turno(aseguradora_que_cotiza, caso)
        await _sembrar_campos(aseguradora_que_cotiza, caso, cifrador, valores)
        await eligibility_run.evaluate_and_store(
            aseguradora_que_cotiza, caso, cipher=cifrador, now=AHORA
        )

    vista_referida = await casos.get_case(aseguradora_que_cotiza, referida)
    vista_elegible = await casos.get_case(aseguradora_que_cotiza, elegible)
    assert vista_referida is not None
    assert vista_elegible is not None
    assert vista_referida.state is CaseState.DERIVED
    assert vista_elegible.state is not CaseState.DERIVED


async def test_a_mitad_de_la_captura_la_respuesta_espera(
    aseguradora_que_cotiza: str, cifrador: crypto.Cipher
) -> None:
    """Visto en produccion el 2026-10-08: con los cinco datos de las reglas el chat ya
    decia "su solicitud puede seguir adelante" y la persona seguia contestando
    preguntas. Se evalua y se guarda, pero no se dice hasta que la solicitud esta
    completa."""
    case_id = await nueva_solicitud(aseguradora_que_cotiza, tipo=RecordType.QUOTE_REQUEST)
    await _sembrar_campos(aseguradora_que_cotiza, case_id, cifrador, LIMPIA)
    oyente = _NotificadorFalso()
    puerto = eligibility_run.EligibilityAdapter(
        cipher=cifrador, clock=lambda: AHORA, notifier=oyente
    )

    assert await puerto.evaluate(aseguradora_que_cotiza, case_id) is not None
    assert oyente.entregados == []
    assert await repositorio.eligibility_of(aseguradora_que_cotiza, case_id) is not None
