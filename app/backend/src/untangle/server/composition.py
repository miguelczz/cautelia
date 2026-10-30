"""Raiz de composicion del proceso servido (C-24).

Es el **unico** lugar que construye adaptadores y fabricas; un contrato
`protected` de `import-linter` lo comprueba. Los nodos reciben sus puertos por
closure y no importan la libreria del grafo ni los SDK de proveedor.

Inyeccion manual, sin contenedor: con 23 componentes y una sola persona
construyendo, un contenedor de inyeccion esconde el grafo de dependencias
justamente donde conviene verlo.

**La raiz no importa unidades que todavia no existen.** La lista de modulos de
abajo esta vacia a proposito: cada unidad agrega su linea cuando se construye. Lo
que si esta desde el primer commit es la comprobacion, para que un modulo
declarado sin su funcion falle **al arrancar**, con su nombre, y no en la primera
peticion.
"""

from __future__ import annotations

import asyncio
import importlib
import uuid
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yaml
from fastapi import APIRouter, FastAPI

from untangle import observability, paths
from untangle.base import Locale, Use
from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.case_record import purge as case_purge
from untangle.case_record.models import CaseState, Channel, FieldStatus, Resolution
from untangle.chat import api as chat_api
from untangle.chat import case_opening
from untangle.chat import notice as chat_notice
from untangle.chat import purge as chat_purge
from untangle.chat import resume as chat_resume
from untangle.compliance.controls import api as cumplimiento
from untangle.compliance.controls.signals import TurnSignals
from untangle.compliance.redaction import api as redaccion
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.demo_operations import api as demo
from untangle.inbox import annotation as inbox_annotation
from untangle.inbox import api as inbox_api
from untangle.inbox import decision as inbox_decision
from untangle.inbox import purge as inbox_purge
from untangle.inbox import triage_notes as inbox_triage_notes

# Importado por su efecto al cargarse, no por lo que expone: `graph.py` compone
# `GRAPH_STATE_FIELDS` desde los cuatro `NodeSpec` reales al ejecutarse (BR1.5,
# paso 3 de U12), y esa composicion **falla al importarse** si dos nodos
# llegaran a declarar el mismo campo de escritura. Sin esta linea, ese modulo no
# lo importa nadie del proceso servido -- "el proceso no arranca si dos nodos
# chocan" era cierto en la prueba y falso en produccion -- y esta linea, en la
# raiz de composicion, es lo que lo cierra (paso 4 de U12).
from untangle.orchestration import (
    case_context,
    eligibility_run,
    node_run_repository,
    pause_repository,
    transcript_writer,
    triage_inputs,
)
from untangle.orchestration import graph as orchestration_graph  # noqa: F401
from untangle.orchestration import turn as orchestration_turn
from untangle.orchestration.checkpoint import TenantCheckpointSaver
from untangle.orchestration.contracts import InboundTurn
from untangle.orchestration.executor import NodeExecutor
from untangle.orchestration.model_reply import agent_name_of
from untangle.orchestration.nodes.compliance import node as cumplimiento_node
from untangle.orchestration.nodes.compliance.node import ComplianceNode
from untangle.orchestration.nodes.decision import node as decision_node
from untangle.orchestration.nodes.intake import blocks as intake_blocks
from untangle.orchestration.nodes.intake import extraction as intake_extraction
from untangle.orchestration.nodes.intake import node as intake_node
from untangle.orchestration.nodes.intake import policy as intake_policy
from untangle.orchestration.nodes.intake import social, understanding
from untangle.orchestration.nodes.policy_verification import node as policy_verification_node
from untangle.orchestration.nodes.policy_verification import proposal
from untangle.orchestration.state import GraphState
from untangle.policy_rag.corpus import api as corpus
from untangle.providers import config as provider_config
from untangle.providers import factory, ports, prompts
from untangle.providers.adapters import anthropic as anthropic_adapter
from untangle.providers.adapters.gemini import api as gemini
from untangle.providers.adapters.gemini import breaker as circuitos
from untangle.providers.adapters.gemini import transport as gemini_transport
from untangle.providers.ceiling import CeilingGate
from untangle.providers.transport import CallTimeouts
from untangle.rules import repository as rules_repository
from untangle.rules.fields import RuleValue
from untangle.server import (
    corpus_ingest,
    health,
    policies,
    problems,
    site,
    speech,
    spend_wiring,
    surfaces,
    trace_shipping,
    voice_routes,
    web,
)
from untangle.settings import Settings
from untangle.surface_spec import SurfaceId, SurfaceSpec
from untangle.telemetry.activation import purge as activation_purge
from untangle.telemetry.spend import api as spend
from untangle.telemetry.spend import purge as spend_purge
from untangle.telemetry.traces import api as trazas
from untangle.telemetry.traces import export as trazas_export
from untangle.telemetry.traces import purge as trazas_purge
from untangle.telemetry.traces import repository as trazas_repo
from untangle.telemetry.traces.models import NodeName
from untangle.tenancy import api as tenancy
from untangle.voice import answers as voice_answers
from untangle.voice import purge as voice_purge
from untangle.voice import session as voice_session

Capability = Literal["router", "purgers", "eval_targets", "surfaces"]

#: Que funcion corresponde a cada capacidad declarada.
#:
#: `surfaces` la anade U6 (CG-U6-7), con el mismo nombre que la funcion, como las
#: otras tres: un modulo que monta una superficie expone `surfaces()` con su
#: `SurfaceSpec` y su sonda, y desde ese arranque su accion aparece en el inicio
#: y su sonda en la salud de listo **sin tocar ningun archivo de U6** (F8,
#: SCALE-U6.1).
FUNCION_DE_CAPACIDAD: dict[Capability, str] = {
    "router": "router",
    "purgers": "purgers",
    "eval_targets": "eval_targets",
    "surfaces": "surfaces",
}


class ModuleContractError(RuntimeError):
    """Un modulo declarado no cumple lo que declaro.

    Falla al arrancar y nombra el modulo. Descubrirlo en la primera peticion
    significa descubrirlo en produccion.
    """


@dataclass(frozen=True)
class ModuleSpec:
    """Un modulo que la raiz monta, y que declara que expone."""

    module: str
    provides: frozenset[Capability]
    #: El campo de `Settings` sin el cual el modulo **no se monta**. Es un dato y
    #: no un `if` en `build_app`: una superficie que existiria sin poder
    #: autenticar a nadie invita a probar (U22, BR3.1), y que la condicion este
    #: declarada junto al modulo la hace visible en la lista y no en una rama.
    requires_setting: str | None = None


#: Los modulos que la raiz monta. Cada unidad agrega el suyo cuando se construye.
#: U2 no aparece: es una biblioteca sin rutas propias --el canje por HTTP es de
#: U14-- y lo que aporta al reinicio nocturno se lee mas abajo, en el registro
#: escrito a mano.
MODULOS: tuple[ModuleSpec, ...] = (
    # U13 es el primero que se monta por este contrato. Declara sus dos rutas y
    # la superficie del chat con su sonda; su purgador sigue en el registro de
    # abajo, que es explicito y escrito a mano a proposito.
    ModuleSpec(module="untangle.chat.api", provides=frozenset({"router", "surfaces"})),
    # U14 monta la bandeja: su cola y la superficie `inbox`, que **no** es
    # publica --se entra con credencial y las credenciales no se publican
    # (D23)-- asi que no aparece en el inicio del sitio.
    ModuleSpec(module="untangle.inbox.api", provides=frozenset({"router", "surfaces"})),
    # U16 monta las tres rutas de C-08, el socket de C-29 y la superficie
    # `voice_console`, que **si** es publica --un visitante la abre sin
    # credencial-- y por eso aparece en el inicio del sitio.
    #
    # Sus rutas viven en `untangle.server` y no en la unidad, a diferencia del
    # chat y de la bandeja: para atender una llamada hace falta la plataforma de
    # voz, que se construye con los adaptadores, y solo este paquete los importa.
    ModuleSpec(module="untangle.server.voice_routes", provides=frozenset({"router", "surfaces"})),
    # U22 monta el panel de cifras: publico, sin credencial, y de solo lectura
    # sobre la linea base versionada. Vive en `untangle.server` por la misma
    # razon que la voz: lee el corredor de evaluaciones, que solo este paquete
    # puede importar (contrato `produccion-sin-evals`).
    ModuleSpec(
        module="untangle.server.evidence_routes", provides=frozenset({"router", "surfaces"})
    ),
    # U22 monta tambien el tablero de gasto, publico desde el 2026-10-09 por
    # decision de Miguel: muestra totales y distribuciones, y los casos descritos
    # sin su numero.
    ModuleSpec(module="untangle.server.spend_routes", provides=frozenset({"router", "surfaces"})),
)

#: **El registro de purgadores de datos de visitante** (C-11, BR3.6). Son nueve.
#:
#: Escrito a mano, una linea por dueno, y nunca descubierto solo. Un
#: descubrimiento automatico deja de encontrar lo que alguien nombro distinto, y
#: entonces la retencion acotada deja de estar acotada sin que nadie lo note.
#:
#: Que este completo no se confia a la memoria: una prueba le pregunta al
#: catalogo de la base que tablas llevan la marca de dato de visitante y falla si
#: alguna no esta cubierta aqui.
PURGADORES: tuple[tenancy.VisitorDataPurger, ...] = (
    tenancy.CASE_ACCESS_LINK_PURGER,
    tenancy.VISITOR_KEY_PURGER,
    # Uno solo para las cinco tablas de U4: el caso y lo que cuelga de el se
    # borran juntos, y la cascada de la base es lo que impide los huerfanos.
    case_purge.CASE_RECORD_PURGER,
    # U5 borra los contadores de cuota **de visitante y de sesion**, y conserva
    # el del sitio, la ventana de presupuesto y el libro mayor entero. Su tabla
    # no lleva la marca de dato de visitante --es dato del proyecto, excluida
    # del aislamiento-- pero si tiene filas de visitante, y este es el sitio
    # donde ese compromiso queda escrito con un nombre (BR7.6).
    spend_purge.SPEND_PURGER,
    # U6 borra el avance de activacion de cada sesion, que es dato de visitante,
    # y conserva el conteo por dia, aseguradora e hito, que no apunta a nadie y
    # es la cifra que tiene que sobrevivir a la noche (BR8.2, NFR19.3).
    activation_purge.ACTIVATION_PURGER,
    # U13 borra la conversacion entera --lleva el resumen de la clave del
    # navegador-- y el contador por origen, que apunta a una red aunque su tabla
    # no lleve la marca; conserva el conteo por dia del sitio, que es el que el
    # panel publico necesita vivo (BR3.1, NFR19).
    chat_purge.CHAT_PURGER,
    # U14 borra el aviso de que un caso cambio, que lleva un resumen salido de
    # lo que dijo una persona; conserva el recibo de idempotencia, que no lleva
    # texto de nadie y cuya desaparicion temprana dejaria a una decision
    # repetida creando una segunda (BR6.3, C-05).
    inbox_purge.INBOX_PURGER,
    # U16 borra la fila de la llamada entera. La cascada del caso ya se lleva las
    # que llegaron a tener uno; este purgador existe por las que no --microfono
    # concedido y colgar antes de decir nada--, que llevan el resumen de un
    # navegador y si no se quedarian para siempre (BR7.3, NFR19).
    voice_purge.CALL_SESSION_PURGER,
    # El noveno, y el unico que no cubre ninguna tabla: lo que ya **salio** hacia
    # las trazas. BR2.1 lo nombra aparte porque el backend no esta en la base, y
    # por eso la comprobacion que recorre el catalogo buscando la marca no podia
    # echarlo de menos: un registro sin el pasaba en verde. Va al final a
    # proposito --barre lo exportado, no una tabla-- y si el transporte instalado
    # no sabe barrerse, levanta: la corrida sale parcial con su alerta en vez de
    # declarar acotada una retencion que nadie acoto.
    trazas_purge.TRACES_BACKEND_PURGER,
)

#: Cuantas veces se espera a que la base responda antes de rendirse al arrancar.
#: Este aplicativo es una demostracion que se duerme y se despierta: esperar a
#: que la base conteste es conducta normal, no una caida.
INTENTOS_DE_ARRANQUE = 5
ESPERA_ENTRE_INTENTOS_SEGUNDOS = 2.0


class IsolationNotVerifiedError(RuntimeError):
    """No se pudo comprobar el aislamiento, asi que el proceso no arranca.

    Arrancar sin haberlo comprobado es exactamente el estado en el que una fuga
    entre aseguradoras pasa desapercibida (decision Q2 del diseno de calidad).
    """


def _instalar_lo_que_depende_de_la_base(opciones: Settings) -> None:
    """Lo que cambia segun haya base o no, en un solo sitio.

    Las tres lineas viven juntas porque responden la misma pregunta: que se
    puede prometer sin base. La direccion y el almacen de resumenes solo
    existen con ella; la ventana de la demostracion se instala en los dos
    casos y sin base **cierra**, que es lo que la regla pide.
    """
    # La base: una sola direccion, leida del entorno en el unico punto que lo
    # lee, y entregada al unico punto que abre conexiones.
    if opciones.database_url:
        tenancy.configure(opciones.database_url)
        # El almacen de verdad de los resumenes de traza (C-23, BR7.4). Sin esta
        # linea viven solo en el proceso y se pierden al reiniciar, que es el
        # valor por omision **a proposito**: hay un camino --el del corredor de
        # evaluaciones, la cifra publicada de NFR21-- que llega hasta el reporte
        # sin base de datos, y por eso la superficie de las trazas no importa su
        # repositorio: se lo instalan.
        trazas.install_summary_store(trazas_repo.DatabaseSummaryStore())

    # **La ventana del reinicio nocturno, enchufada al chat** (BR3.2, BR3.3 de
    # U20). El chat no puede preguntarlo por si mismo --`demo_operations` esta por
    # encima en el contrato de capas-- y por eso recibe la puerta enchufada, igual
    # que recibe el grafo. La voz no la necesita enchufada: sus rutas viven en
    # este paquete y preguntan directo.
    #
    # Se instala **tambien sin base**, y lo que instala entonces cierra: sin base
    # no hay corridas que leer, no se puede afirmar que lo que entre se borre esa
    # noche, y aceptar casos nuevos en ese estado es justo lo que la regla
    # prohibe. Con base, la respuesta la da el registro de corridas.
    chat_api.install_new_case_gate(_puerta_de_casos_nuevos(con_base=bool(opciones.database_url)))


def _puerta_de_casos_nuevos(*, con_base: bool) -> chat_api.NewCaseGate:
    """La ventana de 24 horas de U20, como la pregunta el chat (BR3.2).

    Pregunta solo por las corridas **exitosas**: el reloj cuenta desde la ultima
    que termino limpia y nunca desde el ultimo intento, y una consulta que
    devolviera "la ultima corrida" seria la forma de implementar mal esa regla
    sin que la regla cambiara.

    **Un fallo de lectura cierra**, como el del techo de gasto en la voz: si no se
    puede afirmar que la retencion esta acotada, seguir recibiendo datos de
    personas es peor que degradar a proposito.
    """

    async def puerta() -> bool:
        if not con_base:
            return False
        try:
            return demo.accepts_new_cases(await demo.successful_runs(), now=datetime.now(UTC))
        except Exception as error:  # noqa: BLE001 -- cualquier fallo de lectura cierra; lo que esta en juego son datos de personas
            observability.emit("chat.demo_window_unreadable", error_type=type(error).__name__)
            return False

    return puerta


async def verificar_aislamiento(
    intentos: int = INTENTOS_DE_ARRANQUE,
    espera: float = ESPERA_ENTRE_INTENTOS_SEGUNDOS,
) -> None:
    """La asercion de aislamiento como **condicion de arranque** (C-10).

    Reintenta mientras la base no conteste, y se rinde nombrando la causa. Un
    esquema sin aislamiento no se reintenta: eso no mejora esperando.
    """
    ultimo: Exception | None = None
    for intento in range(1, intentos + 1):
        try:
            informe = await tenancy.assert_rls_complete()
        except Exception as error:  # noqa: BLE001 -- la causa se reporta entera mas abajo
            ultimo = error
            observability.emit(
                "server.isolation_check_retry",
                attempt=intento,
                error=str(error),
            )
            if intento < intentos:
                await asyncio.sleep(espera)
            continue

        if informe.ok:
            return
        detalle = "; ".join(informe.lines())
        msg = f"el esquema no esta aislado y el proceso no arranca: {detalle}"
        raise IsolationNotVerifiedError(msg)

    msg = (
        f"no se pudo comprobar el aislamiento tras {intentos} intentos: {ultimo}. "
        "El proceso no arranca: hacerlo sin la comprobacion es el estado en el "
        "que una fuga pasa desapercibida."
    )
    raise IsolationNotVerifiedError(msg)


@dataclass(frozen=True)
class ProviderPlatform:
    """Las piezas de U5 ya cableadas, para que los nodos las reciban por closure.

    Se guarda en `app.state` y no en una variable de modulo: hay un proceso por
    despliegue, pero una variable global haria que dos aplicaciones construidas
    en la misma corrida de pruebas compartieran clientes.
    """

    clients: factory.ProviderClients
    transports: gemini_transport.GeminiTransportFactory
    text: gemini.GeminiTextGenerator
    embedder: gemini.GeminiEmbedder


def _tiempos_por_uso(
    proveedores: provider_config.ProvidersConfig,
) -> dict[Use, CallTimeouts]:
    """Los dos tiempos maximos de cada uso, leidos del archivo versionado.

    El adaptador los recibe construidos y no los busca: aqui es donde se ve, de
    un vistazo, que la voz espera dos segundos y una corrida de evaluaciones
    treinta.
    """
    return {
        uso.use: CallTimeouts(
            connect_timeout_ms=uso.connect_timeout_ms,
            read_timeout_ms=uso.read_timeout_ms,
        )
        for uso in proveedores.uses
    }


def build_provider_platform(
    settings: Settings, config: provider_config.ProviderPlatformConfig
) -> ProviderPlatform:
    """Los cuatro clientes por uso y los dos adaptadores que los usan (C-24).

    Con `server/speech.py`, que hace lo mismo para la voz, es el **unico** lugar
    del aplicativo que construye un adaptador o una fabrica: un contrato
    `protected` de `import-linter` deja importar los adaptadores solo a
    `untangle.server`.

    Un uso sin clave no tiene cliente y **no se inventa ninguna**: pedirlo falla
    nombrando la variable de entorno que falta. No se exige ninguna al arrancar
    porque hay un camino --del clon al reporte-- que llega hasta el final sin
    cuenta en ningun proveedor; quien necesite una la exige con
    `clients.require(...)` antes de gastar cuota.
    """
    transportes = gemini_transport.GeminiTransportFactory()
    clientes = factory.ProviderClients(
        settings=settings, config=config.providers, transports=transportes
    )
    # Un solo registro de circuitos para los dos adaptadores: el generador y el
    # calculador de embeddings del mismo uso hablan con la misma dependencia
    # externa, y dos registros dejarian a uno llamando a un proveedor que el otro
    # ya sabe caido.
    registro = circuitos.CircuitBreakerRegistry(config.providers.circuit_breaker)
    contabilidad = spend_wiring.LedgerUsageSink()
    tiempos = _tiempos_por_uso(config.providers)

    return ProviderPlatform(
        clients=clientes,
        transports=transportes,
        text=gemini.GeminiTextGenerator(
            clientes,
            config=config.providers,
            breakers=registro,
            usage=contabilidad,
            timeouts=tiempos,
        ),
        embedder=gemini.GeminiEmbedder(
            clientes,
            config=config.providers,
            breakers=registro,
            usage=contabilidad,
            timeouts=tiempos,
        ),
    )


@dataclass(frozen=True)
class ComplianceControls:
    """Los controles de U10 ya cableados, para que el runtime (U12) los reciba hechos.

    Se guardan en `app.state` por la misma razon que la plataforma de
    proveedores: una variable global haria que dos aplicaciones construidas en la
    misma corrida de pruebas compartieran puertos.

    **Ningun proveedor entra aqui** (BR5.3): la revision completa es de reglas,
    y un contrato de importacion falla si el paquete de los controles o el nodo
    llegan a importar uno. Lo que si entra son sus tres puertos de lectura y
    escritura, que son lo que el nodo no puede importar por su cuenta.
    """

    node: ComplianceNode
    review_ports: cumplimiento.ReviewPorts
    emergency_mode: cumplimiento.EmergencyPhraseMode


async def _transcripcion(tenant_id: str, case_id: str) -> tuple[cumplimiento.TranscriptLine, ...]:
    """El puerto de lectura de la transcripcion (decision 3 del conductor, C-15).

    Vive aqui porque es el unico sitio que ve los dos lados: `compliance` no
    puede importar el registro del caso sin cerrar el ciclo que el contrato
    `sin-ciclos` prohibe, y el registro del caso no tiene por que saber que
    forma lee la revision.
    """
    turnos = await casos.transcript_of(tenant_id, case_id)
    return tuple(
        cumplimiento.TranscriptLine.model_validate(
            {"turn_id": t.turn_id, "speaker": t.speaker.value, "text": t.text_redacted}
        )
        for t in turnos
    )


def build_compliance(settings: Settings) -> ComplianceControls:
    """Los puertos de la revision y el nodo `compliance`, cableados por closure (C-15).

    La revision lee la transcripcion por el registro del caso, las divulgaciones
    por su propio repositorio y guarda por su clave (caso, turno revisado), asi que la reejecucion del nodo
    al reanudar no la duplica (BR6.3).
    """
    puertos = cumplimiento.ReviewPorts(
        transcript=_transcripcion,
        disclosures=cumplimiento.disclosures,
        store=cumplimiento.save_review,
        library=cumplimiento.current_patterns,
        clock=lambda: datetime.now(UTC),
        new_id=lambda: f"review-{uuid.uuid4().hex}",
    )

    async def revisar(request: cumplimiento.ReviewRequest) -> cumplimiento.ComplianceReview:
        return await cumplimiento.final_review(request, ports=puertos)

    return ComplianceControls(
        node=ComplianceNode(review=revisar),
        review_ports=puertos,
        emergency_mode=cumplimiento.EmergencyPhraseMode(settings.emergency_phrase),
    )


#: Cuanto espera el chat a que la persona conteste «¿quieres agregar algo mas?» antes de dar
#: la oferta por rechazada y resolver el reporte (US1.17). Dos minutos: de sobra para escribir
#: la respuesta, y corto para que quien cerro la pestana no deje su caso en revision. Cada
#: turno que deja la oferta abierta vuelve a contar desde cero.
ESPERA_DE_LA_OFERTA_S = 120.0


async def _esperar_la_respuesta_a_la_oferta() -> None:
    await asyncio.sleep(ESPERA_DE_LA_OFERTA_S)


@dataclass(frozen=True)
class GraphWiring:
    """El runtime del grafo ya cableado, o la razon por la que no se pudo (C-24).

    **Este bloque existe porque faltaba, y su falta era el segundo muro detras del
    primero.** `install_runtime` no tenia ni un llamador en produccion: aunque el
    canal hubiera entregado el turno con su caso, `handle_turn` habria levantado
    "el runtime de orquestacion no esta instalado". Se descubrio arreglando el
    primero, que es lo que pasa cuando un fallo no se ve: esconde al siguiente.

    **Que queda cableado aqui.** El **ritmo del turno**, entero y real: el nodo
    `intake` de U11 con su extractor de verdad y su prompt versionado, el ejecutor
    comun con su almacen en base, los puntos de control cifrados y el almacen de
    pausas. Y el **ritmo de fondo**, los tres nodos: la verificacion de poliza, el
    motor de reglas y la revision completa de cumplimiento, encadenados por el
    ejecutor directo (PENDIENTES 1.8).

    **El grafo compilado sigue sin compilarse, y eso no es lo que faltaba.** Su
    fabrica de entrada se fija al compilar, y la de la cobertura depende del caso
    --el numero de poliza y el idioma-- asi que compilarlo convertiria toda pregunta
    de cobertura en "no pude verificar" por un fallo de cableado, que es lo que la
    convencion 8 del equipo prohibe. La secuencia no se duplica por encadenar a
    mano: la decide `transition()`, la misma funcion pura que enrutaria el grafo.

    **Los seis campos del vocabulario del motor de reglas tienen quien los produzca.** Tres se
    derivan de lo capturado --terceros, heridos y el conductor que no figura en la poliza-- y
    tres los anota un ajustador desde la bandeja, y los seis entran por `_insumos_de_triage`.
    Lo que no se puede producir sale en la traza con su evento en vez de resolverse con un valor
    inventado.
    """

    runtime: orchestration_turn.GraphRuntime | None
    #: Por que no hay runtime, cuando no lo hay. Nombra la pieza que falta.
    missing: str | None = None


def _instalar_cifrador(settings: Settings) -> crypto.Cipher | None:
    """Fija el cifrador de los campos del caso, si su clave esta (C-24).

    `crypto.install` tampoco tenia llamador en produccion, asi que todo lo que
    llama a `crypto.active()` --corregir un campo en la bandeja, los puntos de
    control del grafo-- fallaba con "no hay cifrador instalado".

    **Sin clave no se levanta aqui.** Hay caminos que llegan hasta el final sin
    cifrar nada --generar el esquema de contratos, el arnes de accesibilidad con sus
    respuestas declaradas-- y exigirla en todos seria pedir un secreto para no
    usarlo. Lo que si queda es el evento: quien arranque sin clave lo ve, y lo que la
    necesite falla nombrandola. (El mensaje de `crypto` decia "sin ella el proceso no
    arranca", que nunca fue cierto porque nadie instalaba el cifrador; se corrigio en
    la misma tanda, junto con el comando de generarla, que era el que imprimia la
    clave en la terminal.)
    """
    if not settings.case_field_encryption_key:
        observability.emit(
            "server.case_cipher_not_installed",
            variable=crypto.KEY_ENV_VAR,
        )
        return None
    cifrador = crypto.Cipher.from_settings(settings)
    crypto.install(cifrador)
    return cifrador


def _extractor_de_captura(plataforma: ProviderPlatform) -> intake_node.ExtractorPort:
    """El puerto de extraccion de `intake`, cableado al generador de U5 (C-15).

    `Use.CHAT` por la misma aproximacion que ya lleva escrita `preload`: el puerto
    de U11 no recibe el canal en su firma, y hoy el unico canal que entrega turnos
    es el chat. El dia que la voz entregue turnos, el uso tiene que viajar con el
    turno; ponerlo aqui en duro para los dos cobraria la voz a la cuota del chat,
    que es justo lo que las claves separadas por uso existen para evitar.

    El esquema se pide en la llamada: asi el adaptador valida la respuesta una sola
    vez y el nodo lee `parsed_as` en vez de volver a parsear el texto.
    """

    async def extraer(prompt: ports.Prompt) -> ports.GenerationResult:
        return await plataforma.text.generate(
            prompt, schema=intake_extraction.ExtractionResponse, use=Use.CHAT
        )

    return extraer


async def _buscador_de_poliza(
    tenant_id: str, policy_number: str
) -> intake_policy.PolicyMatch | None:
    """El puerto de busqueda de polizas de `intake`, cableado al corpus de U8 (P3).

    Devuelve la coincidencia ya reducida --numero, titular y primer vehiculo-- y
    no la poliza emitida: el nodo no importa el corpus (contrato del ritmo del
    turno), asi que la reduccion vive aqui, en la raiz, que si puede.
    """
    poliza = await corpus.find_policy(tenant_id, policy_number=policy_number)
    if poliza is None:
        return None
    return _como_coincidencia(poliza)


def _como_coincidencia(poliza: corpus.IssuedPolicy) -> intake_policy.PolicyMatch:
    """La poliza emitida, reducida a lo que el nodo necesita: numero, titular y primer vehiculo."""
    primero = poliza.vehicles[0] if poliza.vehicles else {}
    descripcion = primero.get("make_model_year")
    return intake_policy.PolicyMatch(
        policy_number=poliza.policy_number,
        holder_name=str(poliza.named_insured.get("full_name", "")),
        vehicle=str(descripcion) if descripcion else None,
    )


async def _polizas_del_titular(tenant_id: str, text: str) -> tuple[intake_policy.PolicyMatch, ...]:
    """Las polizas de **esta** aseguradora cuyo titular el texto nombra entero (2026-10-13).

    Es el puerto con el que el nodo `intake` busca por nombre cuando el numero se oyo mal.
    Pasa por `list_policies`, que abre su sesion por el punto unico de sesion (fija el
    `tenant_id` antes de devolverla): ni una poliza de otra aseguradora ni SQL armado con el
    texto de la persona. Cuantas coincidencias hay y si sus cifras se parecen lo decide el
    nodo; aqui solo se filtra por el nombre, con la misma regla que ya usa para el titular.
    """
    return tuple(
        _como_coincidencia(poliza)
        for poliza in await corpus.list_policies(tenant_id)
        if intake_policy.names_holder(text, str(poliza.named_insured.get("full_name", "")))
    )


def _instruccion_de_captura(locale: Locale) -> ports.SystemInstruction:
    """El prompt versionado de la extraccion, con su hash (BR1.7, BR2.3).

    Se lee del repositorio en cada turno y no se guarda en memoria: el hash tiene
    que identificar el archivo que esta en el commit, y un prompt cacheado al
    arrancar haria que un cambio en caliente publicara una cifra con el hash viejo.
    """
    return prompts.load_system_instruction("intake_extraction", locale)


def _entrada_de_captura(  # noqa: PLR0913 -- la firma de `IntakeInputBuilder`, con los dos ultimos por nombre
    context: case_context.CaseContext,
    turn: InboundTurn,
    signals: TurnSignals,
    emergency_instruction: str | None,
    *,
    awaiting_confirmation: intake_blocks.Block | None = None,
    stated_values: dict[str, str] | None = None,
    awaiting_policy_confirmation: intake_policy.PolicyMatch | None = None,
) -> intake_node.IntakeNodeInput:
    """La unica pieza que traduce el caso cargado mas el turno a la entrada de `intake`."""
    return case_context.build_intake_input(
        context,
        turn_text=turn.text,
        turn_id=f"turno-{uuid.uuid4().hex[:12]}",
        emergency_raised=signals.emergency,
        emergency_instruction=emergency_instruction,
        awaiting_confirmation=awaiting_confirmation,
        stated_values=stated_values,
        awaiting_policy_confirmation=awaiting_policy_confirmation,
    )


def _entrada_de_cobertura(
    context: case_context.CaseContext, question: str, turn_id: str
) -> policy_verification_node.PolicyVerificationNodeInput:
    """La entrada de `policy_verification`, traducida desde el caso ya cargado.

    `draft_citations` va vacío a propósito: son las citas que el modelo **propuso** y
    que el verificador tendría que comprobar. Hoy nadie las propone --la pregunta
    entra tal cual-- y mandar una lista inventada sería pedirle al verificador que
    confirme algo que nadie afirmó.
    """
    assert context.policy_ref is not None  # noqa: S101 -- `preload` lo comprobó antes
    return policy_verification_node.PolicyVerificationNodeInput(
        tenant_id=context.tenant_id,
        case_id=context.case_id,
        turn_id=turn_id,
        policy_number=context.policy_ref,
        question=question,
        answer_language=context.language,
    )


async def _entrada_de_decision(
    context: case_context.CaseContext, state: GraphState, *, cipher: crypto.Cipher
) -> decision_node.DecisionNodeInput:
    """La entrada de `decision`: la aseguradora, el caso y los insumos de las reglas.

    **Los insumos se derivan de lo que el caso ya guarda** (PENDIENTES 1.8, mitad 2).
    Hasta el 2026-10-03 iban vacios: ninguno de los seis campos del vocabulario del
    motor lo producia nadie, y cada caso caia en la regla por defecto --revision
    estandar, la salida segura--. Hoy se derivan tres: `other_parties_data_pending` y,
    desde el 2026-10-13, `injuries_present` y `unlisted_driver` (este ultimo contra los
    conductores que declara la poliza del caso). Otros tres entran por la bandeja y nunca de
    la conversacion: `claim_amount`, `coverage_disputed` y `fraud_suspected` los anota un
    ajustador (decision del 2026-10-03: el monto lo estima el ajustador, y un juicio del
    modelo como insumo de una regla es lo mismo con un paso en medio), y esta funcion los
    lee tal como quedaron.

    Un campo que no se puede derivar **se deja ausente**, nunca en `False`: ausente
    no dispara (BR2.1 de U9) y es honesto; `False` afirmaria que se comprobo.

    Se sigue emitiendo el evento cuando los insumos salen vacios, para que la traza
    diga **cuantas** decisiones se tomaron sin ninguno: sin el, "todos los casos en
    revision estandar" se leeria como una propiedad del corpus y no como un
    cableado a medias.
    """
    del state
    inputs = await _insumos_de_triage(context, cipher=cipher)
    if not inputs:
        observability.emit(
            "orchestration.decision_without_inputs",
            tenant_id=context.tenant_id,
            case_id=context.case_id,
        )
    return decision_node.DecisionNodeInput(
        tenant_id=context.tenant_id,
        case_id=context.case_id,
        inputs=inputs,
    )


async def _insumos_de_triage(
    context: case_context.CaseContext, *, cipher: crypto.Cipher
) -> dict[str, RuleValue]:
    """Los insumos de las reglas para la cadena de fondo: lo derivado y lo anotado."""
    return await insumos_del_caso(context.tenant_id, context.case_id, cipher=cipher)


async def insumos_del_caso(
    tenant_id: str, case_id: str, *, cipher: crypto.Cipher
) -> dict[str, RuleValue]:
    """Todos los insumos de las reglas de un caso, en un solo sitio.

    Lo derivado de la conversacion y lo que anoto un ajustador. **Los tres llamadores leen
    esta funcion**: la cadena de fondo, por `_insumos_de_triage`; la bandeja, que la recibe
    por un puerto cuando un ajustador anota y las reglas se vuelven a evaluar; y la siembra
    de los casos de ejemplo (`synthetic_seed`), que por eso es publica y no tiene una
    segunda derivacion propia. Con dos mezclas, una evaluacion posterior de la cadena de
    fondo perderia lo anotado sin que nada se pusiera rojo. Los dos conjuntos de claves no
    se pisan.
    """
    derivados = await _insumos_de_la_conversacion(tenant_id, case_id, cipher=cipher)
    return derivados | await inbox_triage_notes.rule_inputs_of(tenant_id, case_id)


async def _insumos_de_la_conversacion(
    tenant_id: str, case_id: str, *, cipher: crypto.Cipher
) -> dict[str, RuleValue]:
    """Lee el caso y deriva lo que se puede derivar de lo que la persona conto.

    De los campos se mira el **estado**, y solo se abre el valor de tres: el de heridos, el de
    terceros y el del vehiculo y el conductor, que es lo que la derivacion lee. Los tres se
    abren en una sola lectura, y el valor no se emite ni se guarda: es dato personal y aqui solo
    se lee. La derivacion en si es pura y vive en `orchestration/triage_inputs.py`, para que se
    pueda romper regla por regla sin levantar ni base ni grafo.
    """
    resumen = await casos.summary_with_fields(tenant_id, case_id)
    if resumen is None:
        return {}
    _, campos = resumen
    estados = {c.field_key: c.status for c in campos}
    partes = await casos.parties_of(tenant_id, case_id)
    insumos: dict[str, RuleValue] = {}

    estado_de_terceros = estados.get(triage_inputs.OTHER_PARTIES_FIELD, FieldStatus.NOT_STATED)
    estado_de_heridos = estados.get(triage_inputs.INJURIES_FIELD, FieldStatus.NOT_STATED)
    estado_del_conductor = estados.get(triage_inputs.DRIVER_FIELD, FieldStatus.NOT_STATED)
    pedidos = tuple(
        clave
        for clave, estado in (
            (triage_inputs.INJURIES_FIELD, estado_de_heridos),
            (triage_inputs.OTHER_PARTIES_FIELD, estado_de_terceros),
            (triage_inputs.DRIVER_FIELD, estado_del_conductor),
        )
        if estado is not FieldStatus.NOT_STATED
    )
    abiertos = (
        await casos.open_field_values(tenant_id, case_id, pedidos, cipher=cipher) if pedidos else {}
    )

    pendientes = triage_inputs.other_parties_data_pending(
        partes,
        block_status=estado_de_terceros,
        value=abiertos.get(triage_inputs.OTHER_PARTIES_FIELD),
    )
    if pendientes is not None:
        insumos["other_parties_data_pending"] = pendientes
    elif estado_de_terceros is not FieldStatus.NOT_STATED:
        # Se dijo y no se pudo leer como «nadie mas»: es la salida segura, pero cuantas veces
        # pasa dice si la derivacion es demasiado estricta. Sin el valor: es dato personal.
        observability.emit(
            "orchestration.other_parties_not_derivable",
            tenant_id=tenant_id,
            case_id=case_id,
            field_status=estado_de_terceros.value,
        )

    heridos = triage_inputs.injuries_present(
        abiertos.get(triage_inputs.INJURIES_FIELD) or None,
        status=estado_de_heridos,
        parties=partes,
    )
    if heridos is not None:
        insumos["injuries_present"] = heridos
    elif estado_de_heridos is not FieldStatus.NOT_STATED:
        # Se dijo y no se pudo leer: es la salida segura, pero cuantas veces pasa dice si la
        # derivacion es demasiado estricta. Sin el valor: es dato personal.
        observability.emit(
            "orchestration.injuries_not_derivable",
            tenant_id=tenant_id,
            case_id=case_id,
            field_status=estado_de_heridos.value,
        )

    no_figura = await _conductor_que_no_figura(
        tenant_id,
        case_id,
        value=abiertos.get(triage_inputs.DRIVER_FIELD),
        status=estado_del_conductor,
    )
    if no_figura is not None:
        insumos["unlisted_driver"] = no_figura
    return insumos


async def _conductor_que_no_figura(
    tenant_id: str, case_id: str, *, value: str | None, status: FieldStatus
) -> bool | None:
    """`unlisted_driver` del caso: lo que dijo la persona contra los conductores de su poliza.

    Solo lee la poliza si se dijo algo del conductor, y la lee por el numero que el caso tiene
    atado (`policy_ref`, la que la persona confirmo): un caso sin poliza identificada no tiene
    contra que comparar y el insumo queda ausente. La traza dice **por que** queda ausente --si
    la poliza no declara conductores o si lo dicho no se pudo leer-- sin el valor, que es dato
    personal. La primera causa es la de una base cuyas polizas no se han vuelto a ingerir
    despues de que el generador empezara a declarar conductores.
    """
    if status is FieldStatus.NOT_STATED:
        return None
    declarados: tuple[str, ...] = ()
    vistas = await casos.cases_by_id(tenant_id, [case_id])
    referencia = vistas[0].policy_ref if vistas else None
    if referencia is not None:
        poliza = await corpus.find_policy(tenant_id, policy_number=referencia)
        declarados = tuple(d.full_name for d in poliza.drivers) if poliza is not None else ()
    no_figura = triage_inputs.unlisted_driver(value, status=status, declared_drivers=declarados)
    if no_figura is None:
        observability.emit(
            "orchestration.driver_not_derivable",
            tenant_id=tenant_id,
            case_id=case_id,
            field_status=status.value,
            policy_identified=referencia is not None,
            policy_declares_drivers=bool(declarados),
        )
    return no_figura


def _evidencia(state: GraphState) -> cumplimiento.ReviewEvidence:
    """Los tres adjuntos que el estado ya trae, cada uno con su estado propio.

    **`EMPTY` y `NOT_EVALUATED` no se colapsan** (BR8 de la convencion del equipo):
    "se miro y no habia" es una respuesta verificada sin clausula, y "no se miro" es
    un nodo que no corrio. Colapsarlos dejaria cerrar un caso que nadie reviso.
    """
    citas = state.written("citations")
    reglas = state.written("fired_rules")
    estado_de_las_citas = _estado_del_adjunto(citas)
    if (
        citas is None
        and state.written("outcome") is None
        and state.written("intake_capture_closed") is True
    ):
        # El reporte cerro sin que nadie preguntara por cobertura (2026-10-11): no
        # hay nada que citar, y eso se miro. No es "el nodo no corrio por un fallo":
        # es la misma lectura que hace la bandeja al cerrar un caso sin citas.
        estado_de_las_citas = cumplimiento.EvidenceState.EMPTY
    return cumplimiento.ReviewEvidence(
        citations=estado_de_las_citas,
        fired_rules=_estado_del_adjunto(reglas),
        # La traza existe: este trabajo corre dentro del tramo de turno que
        # `preload` abrio, y su identificador es el de esa traza.
        trace_id=cumplimiento.EvidenceState.PRESENT,
    )


def _estado_del_adjunto(valor: object) -> cumplimiento.EvidenceState:
    if valor is None:
        return cumplimiento.EvidenceState.NOT_EVALUATED
    if isinstance(valor, tuple | list) and not valor:
        return cumplimiento.EvidenceState.EMPTY
    return cumplimiento.EvidenceState.PRESENT


async def _entrada_de_cumplimiento(
    context: case_context.CaseContext, state: GraphState
) -> cumplimiento_node.ComplianceNodeInput | None:
    """La entrada de la revision completa, o `None` cuando no se puede acotar.

    **Los dos casos en los que devuelve `None` son los dos que no se pueden hacer
    bien**, y por eso se declaran aqui en vez de resolverse con un valor inventado:

    1. **Un caso sin un solo turno.** La revision llega "hasta un turno", y un caso
       sin transcripcion no tiene hasta donde llegar. No es una revision vacia: es
       una que no se puede acotar.
    2. **Un caso derivado sin turno de derivacion.** La revision necesita saber **en
       que turno** salio la frase: es lo que decide si una peticion de persona se
       derivo en el turno siguiente (BR5.1 de U10). El caso lo guarda desde que el
       canal lo escribe al derivar, pero hay derivaciones que no ocurren en un turno
       --el boton de pasar a una persona de la consola de voz, la decision de la
       bandeja-- y ahi no hay frase que acotar. Las dos formas de inventarlo son
       peores que no revisar: con el ultimo turno, la revision absolveria una
       derivacion que llego tarde; con `None`, acusaria de no haber derivado a un
       caso que si se derivo.
    """
    turnos = await casos.transcript_of(context.tenant_id, context.case_id)
    if not turnos:
        return None
    derivacion = _derivacion(context)
    if context.state is CaseState.DERIVED and derivacion is None:
        return None
    return cumplimiento_node.ComplianceNodeInput(
        tenant_id=context.tenant_id,
        case_id=context.case_id,
        language=context.language,
        last_turn_id=turnos[-1].turn_id,
        handoff=derivacion,
        closable=bool(state.written("closable")),
        evidence=_evidencia(state),
    )


#: El motivo del caso traducido al del canal. Se **deriva** de la tabla de ida que
#: vive en el camino del turno, en vez de escribirse como una segunda tabla: dos
#: tablas inversas son dos sitios que el dia que discrepen dejarian una derivacion
#: con dos motivos distintos segun quien la lea.
_MOTIVO_DEL_CANAL: Mapping[str, cumplimiento.HandoffReason] = {
    motivo.value: razon for razon, motivo in case_context.MOTIVO_DEL_CASO.items()
}


def _derivacion(context: case_context.CaseContext) -> cumplimiento.Handoff | None:
    """La derivacion del caso tal como la lee la revision, o `None` si no se puede.

    `None` en los tres casos en los que no hay nada que acotar, y los tres son
    distintos de "no se derivo": el caso no esta derivado, la derivacion no ocurrio
    en un turno, o su motivo no tiene equivalente en el conjunto del canal.
    """
    if context.state is not CaseState.DERIVED:
        return None
    if context.derived_turn_id is None or context.derivation_reason is None:
        return None
    razon = _MOTIVO_DEL_CANAL.get(context.derivation_reason)
    if razon is None:
        return None
    return cumplimiento.Handoff(turn_id=context.derived_turn_id, reason=razon)


def _sin_etiquetas(texto: str) -> str:
    """El texto de fuera no puede cerrar una etiqueta y abrir otra."""
    return texto.replace("<", "&lt;").replace(">", "&gt;")


def _generador_de_claude(
    clave: str,
    config: provider_config.ProviderPlatformConfig,
    *,
    use: Use,
    read_timeout_ms: int | None = None,
    careful: bool = False,
) -> anthropic_adapter.AnthropicTextGenerator:
    """El cliente de Claude Haiku con la clave que se le da, para el uso que se le da.

    El modelo, los tiempos, el plan y si factura son los del uso en la
    configuracion: `chat_reply` para el chat y `evals_chat` para las evaluaciones
    de la comprension. Lo que cambia por uso es la clave y la atribucion del gasto.
    """
    declarado = config.providers.for_use(use)
    return anthropic_adapter.AnthropicTextGenerator(
        anthropic_adapter.build_client(
            clave,
            connect_timeout_ms=declarado.connect_timeout_ms,
            read_timeout_ms=read_timeout_ms or declarado.read_timeout_ms,
        ),
        use=use,
        model=declarado.model,
        gate=CeilingGate(spend.budget_state),
        usage=spend_wiring.LedgerUsageSink(),
        careful=careful,
    )


def build_understander(
    settings: Settings,
    config: provider_config.ProviderPlatformConfig,
    *,
    for_evals: bool = False,
) -> understanding.Understander | None:
    """Quien entiende cada mensaje y lo contesta, o nada si no hay clave (2026-10-07).

    Una sola llamada por turno (2026-10-12): el modelo ve la conversacion y el estado del
    caso, anota los datos que la persona dio y escribe la respuesta, todo en el mismo
    formulario cerrado. Sin clave el chat sigue por reglas para el tipo y extraccion para los
    datos, y sale la frase del catalogo. Con `for_evals` usa la clave de evaluaciones y
    atribuye su gasto al uso `evals`, para que una corrida no gaste el saldo que atiende a
    los visitantes.
    """
    clave = settings.anthropic_api_key_evals if for_evals else settings.anthropic_api_key_chat
    uso = Use.EVALS_CHAT if for_evals else Use.CHAT_REPLY
    if not clave:
        if not for_evals:
            observability.emit(
                "server.chat_understanding_not_installed",
                missing=factory.env_var_for(Use.CHAT_REPLY),
            )
        return None
    generador = _generador_de_claude(clave, config, use=uso)

    async def entender(
        peticion: understanding.UnderstandingRequest,
    ) -> understanding.UnderstandingResponse:
        resultado = await generador.generate(
            ports.Prompt(
                instruction=prompts.load_system_instruction("conversation", peticion.language),
                parts=(
                    ports.PromptPart(
                        role="user", text=ports.ExternalText(_contenido_de_comprension(peticion))
                    ),
                ),
            ),
            schema=understanding.UnderstandingResponse,
            use=uso,
        )
        return resultado.parsed_as(understanding.UnderstandingResponse)

    return entender


#: Cuanto se espera a la propuesta de citas. Holgado: corre en el fondo.
PROPOSAL_READ_MS = 30_000


def build_citation_proposer(
    settings: Settings,
    config: provider_config.ProviderPlatformConfig,
    *,
    for_evals: bool = False,
) -> proposal.ProposerPort | None:
    """Quien propone las citas de una respuesta de cobertura, o nada si no hay clave.

    Fase 1 (2026-10-08). Sin clave el nodo verifica solo lo que le llega, como antes,
    y toda pregunta termina en "no encuentro una clausula". Con `for_evals` usa la
    clave de evaluaciones y atribuye su gasto a `evals_chat`.
    """
    clave = settings.anthropic_api_key_evals if for_evals else settings.anthropic_api_key_chat
    uso = Use.EVALS_CHAT if for_evals else Use.CHAT_REPLY
    if not clave:
        if not for_evals:
            observability.emit(
                "server.citation_proposer_not_installed",
                missing=factory.env_var_for(Use.CHAT_REPLY),
            )
        return None
    # La propuesta corre en el ritmo de fondo, con el plazo de su nodo: no hereda los
    # 3 s del chat, que con ocho clausulas largas se vencian (medido el 2026-10-08).
    generador = _generador_de_claude(
        clave, config, use=uso, read_timeout_ms=PROPOSAL_READ_MS, careful=True
    )

    async def proponer(peticion: proposal.ProposalRequest) -> proposal.CitationProposal:
        resultado = await generador.generate(
            ports.Prompt(
                instruction=prompts.load_system_instruction(
                    "policy_verification", peticion.language
                ),
                parts=(
                    ports.PromptPart(
                        role="user", text=ports.ExternalText(_contenido_de_propuesta(peticion))
                    ),
                ),
            ),
            schema=proposal.CitationProposal,
            use=uso,
        )
        return resultado.parsed_as(proposal.CitationProposal)

    return proponer


#: Las etiquetas del contenido del prompt `policy_verification`, por idioma.
_ETIQUETAS_DE_PROPUESTA: dict[str, dict[str, str]] = {
    "es": {
        "pregunta": "pregunta",
        "clausulas": "clausulas",
        "clausula": "clausula",
        "parte": "parte",
        "relacionada": "relacionada_con",
    },
    "en": {
        "pregunta": "question",
        "clausulas": "clauses",
        "clausula": "clause",
        "parte": "part",
        "relacionada": "related_to",
    },
}


def _contenido_de_propuesta(peticion: proposal.ProposalRequest) -> str:
    """La pregunta y las clausulas recuperadas, cada una en su etiqueta y escapada:
    el texto del corpus es de origen externo igual que el de la persona."""
    e = _ETIQUETAS_DE_PROPUESTA[peticion.language]
    lineas = [f"<{e['pregunta']}>{_sin_etiquetas(peticion.question)}</{e['pregunta']}>"]
    lineas.append(f"<{e['clausulas']}>")
    for clausula in peticion.clauses:
        atributos = f'id="{_sin_etiquetas(clausula.clause_id)}" {e["parte"]}="{_sin_etiquetas(clausula.part)}"'
        if clausula.related_to:
            atributos += f' {e["relacionada"]}="{_sin_etiquetas(clausula.related_to)}"'
        lineas.append(
            f"<{e['clausula']} {atributos}>{_sin_etiquetas(clausula.text)}</{e['clausula']}>"
        )
    lineas.append(f"</{e['clausulas']}>")
    return "\n".join(lineas)


#: Las etiquetas del contenido del prompt `conversation`, por idioma, y las palabras con que
#: se le cuentan las cosas. Los nombres de las etiquetas son los que la instruccion
#: nombra: si una cambia y la otra no, el modelo recibiria una regla sobre un campo que no
#: existe (una prueba compara las dos). Van en el contenido y no en la instruccion: la
#: instruccion no lleva huecos (README de `app/config/prompts`).
_ETIQUETAS_DE_COMPRENSION: dict[str, dict[str, str]] = {
    "es": {
        "hoy": "hoy",
        "canal": "canal",
        "idioma": "idioma",
        "nombre": "tu_nombre",
        "aseguradora": "aseguradora",
        "cotiza": "aseguradora_cotiza",
        "tipo": "tipo_de_conversacion",
        "estado": "estado_del_caso",
        "poliza": "poliza_identificada",
        "pendiente": "respuesta_pendiente",
        "anotados": "datos_anotados",
        "faltan": "datos_que_faltan",
        "conversacion": "conversacion",
        "mensaje": "mensaje_de_la_persona",
        # Las palabras.
        "ninguna": "ninguna",
        "si": "sí",
        "no": "no",
        "chat": "chat",
        "voice": "voz",
        "idioma_es": "español",
        "idioma_en": "inglés",
        "ya_lo_dio": "(ya lo dio)",
        "persona": "persona",
        "agente": "tú",
        "estado_none": "sin caso",
        "estado_receiving": "recibiendo datos",
        "estado_in_review": "en revisión",
        "estado_with_adjuster": "ya con el ajustador",
        "estado_closed": "cerrado",
    },
    "en": {
        "hoy": "today",
        "canal": "channel",
        "idioma": "language",
        "nombre": "your_name",
        "aseguradora": "insurer",
        "cotiza": "insurer_quotes",
        "tipo": "conversation_type",
        "estado": "case_status",
        "poliza": "policy_identified",
        "pendiente": "answer_pending",
        "anotados": "noted_details",
        "faltan": "missing_details",
        "conversacion": "conversation",
        "mensaje": "person_message",
        "ninguna": "none",
        "si": "yes",
        "no": "no",
        "chat": "chat",
        "voice": "voice",
        "idioma_es": "Spanish",
        "idioma_en": "English",
        "ya_lo_dio": "(already given)",
        "persona": "person",
        "agente": "you",
        "estado_none": "no case",
        "estado_receiving": "receiving details",
        "estado_in_review": "under review",
        "estado_with_adjuster": "already with the adjuster",
        "estado_closed": "closed",
    },
}


def _una_linea(texto: str) -> str:
    """Una intervencion en una sola linea: un salto de linea dentro de lo que dijo la persona
    no puede hacerse pasar por el turno de otro ni por una etiqueta nueva."""
    return _sin_etiquetas(" ".join(texto.split()))


def _contenido_de_comprension(peticion: understanding.UnderstandingRequest) -> str:
    """El contexto, la conversacion y el mensaje, cada uno en su etiqueta. Lo de fuera va escapado.

    Es lo que la instruccion `conversation` espera: la fecha, el canal, quien es la agente, en
    que va el caso, lo anotado **con su valor**, lo que falta en orden, las ultimas
    intervenciones y, aparte y sin tapar, lo que la persona acaba de decir.
    """
    e = _ETIQUETAS_DE_COMPRENSION[peticion.language]

    def _si_no(valor: bool) -> str:
        return e["si"] if valor else e["no"]

    anotados = "\n".join(
        f"{dato.field_key}: {e['ya_lo_dio'] if dato.value is None else _una_linea(dato.value)}"
        for dato in peticion.noted
    )
    conversacion = "\n".join(
        f"{e['persona'] if linea.speaker == 'person' else e['agente']}: {_una_linea(linea.text)}"
        for linea in peticion.history
    )
    partes = {
        e["hoy"]: peticion.today.isoformat(),
        e["canal"]: e["voice"] if peticion.channel == "voice" else e["chat"],
        e["idioma"]: e["idioma_es"] if peticion.language == "es" else e["idioma_en"],
        e["nombre"]: peticion.agent_name or agent_name_of(peticion.tenant_id, peticion.language),
        e["aseguradora"]: tenancy.require(peticion.tenant_id).display_name,
        e["cotiza"]: _si_no(peticion.quote_enabled),
        e["tipo"]: peticion.record_type.value if peticion.record_type else e["ninguna"],
        e["estado"]: e[f"estado_{peticion.case_status.value}"],
        e["poliza"]: _si_no(peticion.policy_identified),
        e["pendiente"]: _si_no(peticion.answer_pending),
        e["anotados"]: anotados,
        e["faltan"]: ", ".join(peticion.missing),
        e["conversacion"]: conversacion,
        e["mensaje"]: _sin_etiquetas(peticion.person_text),
    }
    return "\n".join(f"<{etiqueta}>{valor}</{etiqueta}>" for etiqueta, valor in partes.items())


def _enchufar_la_decision() -> None:
    """Lo que sigue a una decision de la bandeja: reanudar el grafo y avisar al chat."""
    # La reanudacion del grafo tras una decision (C-14). Por puerto y no por
    # importacion directa, igual que el manejador de turno del chat: asi la
    # decision se puede probar sin levantar el grafo entero, y el orden que
    # importa --registrar antes de reanudar-- se ve con un doble.
    inbox_decision.install_resume_handler(
        lambda case_id, resolucion, tenant_id: orchestration_turn.resume_case(
            case_id, resolucion, tenant_id=tenant_id
        )
    )
    # La decision vuelve al chat (fase 1, 2026-10-08): la frase de U13 ya escrita
    # (`chat.notice.for_decision`), pasada por la guardia, por el mismo aviso que usa
    # la respuesta de cobertura.
    inbox_decision.install_decision_listener(_avisar_la_decision_al_chat)


def _enchufar_las_anotaciones() -> None:
    """Lo que la bandeja necesita de la raiz para anotar para las reglas: sus insumos.

    La misma funcion que lee la cadena de fondo (`insumos_del_caso`), por puerto y no por
    importacion: la bandeja esta por debajo de esta raiz en el contrato de capas. El
    cifrador se pide al llamar y no al montar, igual que las rutas que abren campos: sin
    clave, anotar falla nombrandola en vez de reevaluar sin lo que la persona conto.
    """
    inbox_annotation.install_rule_inputs(
        lambda tenant_id, case_id: insumos_del_caso(tenant_id, case_id, cipher=crypto.active())
    )


def _enchufar_la_bandeja() -> None:
    """Los puertos que la bandeja recibe de esta raiz: lo que sigue a una decision y los
    insumos con que se reevaluan las reglas cuando un ajustador anota."""
    _enchufar_la_decision()
    _enchufar_las_anotaciones()


class _FirstTheCall:
    """Lo que el fondo calculo, llevado a donde este la persona (2026-10-11).

    Primero a su llamada, si hay una viva por ese caso; si no, al chat. Antes solo
    existia el del chat, y en una llamada la respuesta de cobertura no llegaba
    nunca: la agente decia "dejame revisar tu poliza" y no volvia al tema.
    """

    async def notify(  # noqa: PLR0913 -- la firma del puerto CaseNotifier
        self,
        tenant_id: str,
        case_id: str,
        *,
        text: str,
        citations: tuple[object, ...] = (),
        suggestions: tuple[str, ...] = (),
        coverage_outcome: str | None = None,
        language: Locale | None = None,
    ) -> bool:
        for canal in (voice_answers.CASE_NOTIFIER, chat_api.CASE_NOTIFIER):
            if await canal.notify(
                tenant_id,
                case_id,
                text=text,
                citations=citations,
                suggestions=suggestions,
                coverage_outcome=coverage_outcome,
                language=language,
            ):
                return True
        return False


#: El puerto que se enchufa en el ritmo de fondo.
CASE_NOTIFIER = _FirstTheCall()


async def _avisar_la_decision_al_chat(decision: inbox_decision.DecisionMade) -> None:
    aviso = await chat_notice.for_decision(
        chat_notice.Decision(
            case_id=decision.case_id,
            case_number=decision.case_number,
            resolution=Resolution(decision.resolution),
            comment=decision.comment,
            ref=decision.ref,
        ),
        tenant_id=decision.tenant_id,
        language=decision.language,  # type: ignore[arg-type]
    )
    # Tambien a la transcripcion: el enlace al caso abre en la misma pestana, asi que
    # quien decidio desde ahi no tiene el chat escuchando, y al volver el historial es
    # lo unico que ve (B2, 2026-10-08). Molde del catalogo y comentario ya redactado.
    await transcript_writer.say_without_turn(
        chat_api.CASE_NOTIFIER,
        transcript_writer.TranscriptScope(
            tenant_id=decision.tenant_id,
            case_id=decision.case_id,
            channel=Channel.CHAT,
            language=decision.language,  # type: ignore[arg-type]
        ),
        text=aviso.text,
        now=datetime.now(UTC),
    )


def _piezas_de_claude(
    opciones: Settings,
    configuracion: provider_config.ProviderPlatformConfig,
    *,
    for_evals: bool = False,
) -> ClaudePorts:
    """Las dos piezas de Claude del chat, construidas una vez.

    Fase 0 (2026-10-07): las comparten el turno y el primer mensaje del canal. Con
    `for_evals` las dos usan la clave de evaluaciones: la corrida completa no
    gasta el saldo que atiende a los visitantes.
    """
    return ClaudePorts(
        understander=build_understander(opciones, configuracion, for_evals=for_evals),
        proposer=build_citation_proposer(opciones, configuracion, for_evals=for_evals),
    )


def _cablear_el_chat(
    plataforma: ProviderPlatform,
    controles: ComplianceControls,
    cifrador: crypto.Cipher | None,
    claude: ClaudePorts,
    *,
    wait_for_offer: bool = True,
) -> GraphWiring:
    """El grafo del turno, y la agente que entiende y contesta."""
    chat_api.install_understanding(claude.understander, orchestration_turn.ChatCaseTurnSupport())
    # Escribir en el chat el numero de un caso empezado por llamada lo retoma (US1.20): el chat
    # pregunta de quien es el caso con el mismo resumen de la clave del navegador que la voz
    # guardo, y la voz no se importa desde el chat (son hermanos en el contrato de capas).
    chat_resume.install_call_cases(voice_session.case_ids_of_visitor)
    return build_graph_wiring(
        plataforma, controles, cipher=cifrador, claude=claude, wait_for_offer=wait_for_offer
    )


@dataclass(frozen=True)
class ClaudePorts:
    """Lo que hace Claude Haiku en el chat: entender y contestar cada mensaje, y proponer
    las citas de cobertura. Cada uno es `None` sin clave."""

    understander: understanding.Understander | None = None
    proposer: proposal.ProposerPort | None = None


def build_graph_wiring(
    plataforma: ProviderPlatform,
    controles: ComplianceControls,
    *,
    cipher: crypto.Cipher | None,
    claude: ClaudePorts | None = None,
    wait_for_offer: bool = True,
) -> GraphWiring:
    """El runtime del ritmo del turno, o la razon de que no haya (C-24).

    Sin cifrador no hay runtime: los puntos de control del grafo van cifrados y
    los campos del caso tambien, y un runtime con un cifrador inventado escribiria
    datos personales que nadie podria volver a abrir.

    `wait_for_offer` apagado quita la espera de la oferta sin contestar (2026-10-14): la
    corrida de evaluaciones la resuelve ella misma al terminar cada conversacion
    (`evals.drivers.chat`), y la espera de dos minutos quedaba viva despues de cerrar la
    aplicacion, buscando una base que ya no estaba.
    """
    if cipher is None:
        return GraphWiring(runtime=None, missing=crypto.KEY_ENV_VAR)
    claude = claude or ClaudePorts()

    ejecutor = NodeExecutor(
        store=node_run_repository.DatabaseNodeRunStore(),
        clock=lambda: datetime.now(UTC),
    )
    return GraphWiring(
        runtime=orchestration_turn.GraphRuntime(
            intake=intake_node.IntakeNode(
                extract=_extractor_de_captura(plataforma),
                instruction=_instruccion_de_captura,
                # El reloj de `intake` es de **fecha**, no de instante: lo usa la
                # regla que normaliza una fecha relativa ("ayer", "el martes").
                clock=lambda: datetime.now(UTC).date(),
                # P3: la poliza que la persona da se busca en el corpus de U8, por
                # el mismo puerto que `identity` declara (BR1.2).
                lookup=_buscador_de_poliza,
                # Y por nombre, para cuando el numero se oyo mal (2026-10-13): propone, no ata.
                holder_lookup=_polizas_del_titular,
            ),
            build_intake_input=_entrada_de_captura,
            policy_lookup=_buscador_de_poliza,
            # La respuesta de cobertura llega sola al chat cuando el fondo termina.
            notifier=CASE_NOTIFIER,
            offer_wait=_esperar_la_respuesta_a_la_oferta if wait_for_offer else None,
            # Ver el docstring de `GraphWiring`: el ritmo de fondo va con su propio
            # trabajo, y hasta entonces `preload` lo dice en vez de suponerlo.
            background_graph=None,
            executor=ejecutor,
            checkpointer=TenantCheckpointSaver(cipher=cipher),
            pause_store=pause_repository.DatabaseHumanReviewRequestStore(),
            cipher=cipher,
            emergency_mode=controles.emergency_mode,
            # Quien entiende y contesta cada mensaje (fase 0, 2026-10-07; la respuesta,
            # 2026-10-12). Sin clave es `None` y el turno sigue por reglas y extraccion,
            # con las frases del catalogo.
            understander=claude.understander,
            # **La elegibilidad de la cotizacion, enchufada** (U19, BR2.5). Por
            # puerto y no por importacion: el motor de reglas no puede aparecer en
            # la cadena de llamadas del turno --un contrato de capas lo prohibe-- y
            # la razon es que importarlo lo meteria en el camino que BR2.5 quiere
            # mantener fuera. Sin esto, `compose_eligibility_reply` seguiria escrita
            # y probada con el corredor de evaluaciones como unico consumidor, que
            # es exactamente el hueco que mantenia la cotizacion de Sunmeadow como
            # criterio bloqueante de la pasada de publicacion.
            eligibility=eligibility_run.EligibilityAdapter(
                cipher=cipher,
                clock=lambda: datetime.now(UTC),
                # **La direccion que no existia**: del nucleo hacia el canal. El chat
                # importa el nucleo y nunca al reves (convencion 5a), asi que el
                # nucleo declara el puerto y aqui se enchufa quien lo cumple. Sin
                # esto, quien termina de dar sus diecisiete campos no vuelve a
                # escribir y la respuesta --calculada y guardada-- no le llega nunca.
                notifier=CASE_NOTIFIER,
            ),
            # El nodo de cobertura de U8, con el calculador de embeddings de U5 y el
            # único modelo de embeddings que declara la carpeta de proveedores. Corre
            # por el ejecutor directo, no dentro de un grafo compilado: ver el
            # docstring de `GraphRuntime.coverage`.
            coverage=policy_verification_node.PolicyVerificationNode(
                embed=lambda textos: plataforma.embedder.embed(textos, use=Use.CORPUS),
                embedding_model=corpus_ingest.embedding_model_for(
                    provider_config.load().providers
                ).model_id,
                clock=lambda: datetime.now(UTC),
                # Quien propone las citas (fase 1): sin el, todo termina en "no
                # encuentro una clausula".
                propose=claude.proposer,
            ),
            build_coverage_input=_entrada_de_cobertura,
            # **La cadena del fondo, enchufada** (PENDIENTES 1.8): lo que sigue a
            # la cobertura. Los dos nodos son los reales --el motor de reglas de U9
            # con su guardado, y la revision completa de U10 con sus tres puertos--
            # y corren por el ejecutor directo, encadenados por `transition()`.
            #
            # No se compila el grafo de fondo, y la razon sigue siendo la misma: su
            # fabrica de entrada se fija al compilar, y la de la cobertura depende
            # del caso. Encadenar no duplica la secuencia: la decide la misma
            # funcion pura que enrutaria el grafo.
            background={
                NodeName.DECISION: orchestration_turn.BackgroundStep(
                    node=decision_node.DecisionNode(
                        clock=lambda: datetime.now(UTC),
                        save=rules_repository.save_evaluation,
                    ),
                    build_input=lambda contexto, estado: _entrada_de_decision(
                        contexto, estado, cipher=cipher
                    ),
                ),
                NodeName.COMPLIANCE: orchestration_turn.BackgroundStep(
                    node=controles.node,
                    build_input=_entrada_de_cumplimiento,
                ),
            },
        )
    )


def _resolve(spec: ModuleSpec) -> object:
    try:
        return importlib.import_module(spec.module)
    except ImportError as error:
        msg = f"el modulo declarado '{spec.module}' no se pudo importar: {error}"
        raise ModuleContractError(msg) from error


def _superficies_del_modulo(
    spec: ModuleSpec, funcion: Callable[[], object]
) -> tuple[SurfaceSpec, ...]:
    """Lo que declaro `surfaces()`, validado. El fallo nombra el modulo (BR5.2)."""
    try:
        return surfaces.validate_declared(funcion())
    except surfaces.SurfaceDeclarationError as error:
        msg = f"el modulo '{spec.module}' declara 'surfaces' y no cumple su contrato: {error}"
        raise ModuleContractError(msg) from error


def mountable_modules(modules: Sequence[ModuleSpec], settings: Settings) -> tuple[ModuleSpec, ...]:
    """Los modulos que este despliegue puede montar: los que no exigen un ajuste ausente.

    El motivo de cada omision va al rastro, con el nombre del ajuste y **nunca su
    valor**: que un modulo no se monte por falta de clave es una decision del
    despliegue y quien lo opera tiene que poder verla.
    """
    montables: list[ModuleSpec] = []
    for spec in modules:
        if spec.requires_setting is not None and not getattr(settings, spec.requires_setting):
            observability.emit(
                "server.module_not_mounted",
                module=spec.module,
                missing_setting=spec.requires_setting,
            )
            continue
        montables.append(spec)
    return tuple(montables)


def mount_modules(app: FastAPI, modules: Sequence[ModuleSpec]) -> surfaces.SurfaceRegistry:
    """Monta los modulos declarados, comprueba su contrato y devuelve sus superficies.

    Todo lo que un modulo declara se comprueba **aqui, al arrancar**, y el fallo
    nombra el modulo: un router que no es router, una superficie sin sonda, la
    misma superficie montada por dos modulos. Descubrirlo en la primera peticion
    --o en el chequeo periodico-- seria descubrirlo en produccion.
    """
    declaradas: list[SurfaceSpec] = []
    duenos: dict[SurfaceId, str] = {}
    for spec in modules:
        modulo = _resolve(spec)
        for capacidad in sorted(spec.provides):
            nombre = FUNCION_DE_CAPACIDAD[capacidad]
            funcion = getattr(modulo, nombre, None)
            if not callable(funcion):
                msg = (
                    f"el modulo '{spec.module}' declara '{capacidad}' y no expone "
                    f"'{nombre}()' (C-24)"
                )
                raise ModuleContractError(msg)
            if capacidad == "router":
                enrutador = funcion()
                if not isinstance(enrutador, APIRouter):
                    msg = (
                        f"el modulo '{spec.module}' expone 'router()' y no devuelve "
                        "un APIRouter (C-24)"
                    )
                    raise ModuleContractError(msg)
                app.include_router(enrutador)
            elif capacidad == "surfaces":
                for superficie in _superficies_del_modulo(spec, funcion):
                    previo = duenos.get(superficie.surface_id)
                    if previo is not None:
                        msg = (
                            f"la superficie '{superficie.surface_id}' la montan dos "
                            f"modulos: '{previo}' y '{spec.module}'"
                        )
                        raise ModuleContractError(msg)
                    duenos[superficie.surface_id] = spec.module
                    declaradas.append(superficie)
    return surfaces.SurfaceRegistry(declaradas)


def _indicadores_de_proveedor(plataforma: ProviderPlatform) -> health.ProviderIndicators:
    """Los indicadores de U1 y U5 para la salud, calculados **una vez** (FD-U6-6).

    Nombres de uso y un conteo, nunca una clave. Se calculan al arrancar y no en
    cada consulta de salud: ninguno cambia sin reiniciar, y asi la salud no
    toca la plataforma de proveedores ni por accidente (SEC-U6.9).
    """
    return health.ProviderIndicators(
        priced_units=len(spend.current_runtime().prices.entries),
        uses_with_key=tuple(uso.value for uso in plataforma.clients.available()),
    )


def _agentes() -> tuple[str, ...]:
    """Como se llama la agente de cada aseguradora cargada, mas el nombre del catalogo."""
    propios = (t.agent_name for t in tenancy.loaded().available if t.agent_name)
    return (copy_api.t(CopyKey("insurer.agent.name"), locale="es"), *propios)


def _carros_de_ejemplo() -> tuple[str, ...]:
    """Las marcas y modelos de los repertorios de vehiculos ficticios, si estan.

    Salen de los mismos archivos con que se generan las polizas de ejemplo
    (`app/data/sources/*/*/pools.yaml`), asi que no hay una segunda lista que
    mantener. Si no estan --un despliegue sin datos--, no hay carros que perdonar.
    """
    carros: list[str] = []
    for archivo in sorted(paths.synthetic_sources_dir().glob("*/*/pools.yaml")):
        datos = yaml.safe_load(archivo.read_text(encoding="utf-8")) or {}
        carros.extend(
            linea.strip()
            for fuente in datos.get("texts", ())
            if fuente.get("kind") == "vehicle_pool"
            for linea in str(fuente.get("text", "")).splitlines()
            if linea.strip()
        )
    return tuple(carros)


async def _cargar_el_detector() -> None:
    """Carga los modelos de la redaccion **antes** de aceptar conexiones.

    Se cargaban la primera vez que habia que tapar un texto, y en una llamada eso
    es el primer transcrito: la carga dura unos siete segundos, bloquea el bucle
    de eventos y en ese tiempo no entra audio al reconocedor ni sale nada. Medido
    en produccion el 2026-10-07: la persona hablo a los 17 s, nada llego hasta los
    24 s y la agente pregunto «¿sigue ahi?» en medio. Cada instancia nueva de Cloud
    Run lo pagaba en su primera llamada.

    Va en un hilo para no congelar el arranque, y si falla no lo tumba: la
    redaccion lo vuelve a intentar al primer uso y, si alli falla, no sale texto
    (BR1.7), que es lo que ya pasaba.
    """
    # Los nombres publicos de la demo no son datos de nadie: sin esto, "Autos Poblado"
    # en una respuesta de la agente se guardaba como "[LUGAR 1]" (2026-10-08).
    redaccion.allow_public_terms(
        [
            *(t.display_name for t in tenancy.loaded().available),
            *_agentes(),
            "Cautelia",
            # Las marcas y los modelos de los carros de las polizas de ejemplo: "yo
            # iba manejando el Logan" se guardaba "el [NOMBRE 1]" (2026-10-10).
            *_carros_de_ejemplo(),
            # Los nombres de atributo del lote de trazas: la redaccion lee el lote como
            # texto, y su modelo de nombres tomaba por una persona una clave
            # (`langfuse.observation.type` salia siempre como `[NAME 1]`, 2026-10-14).
            *trazas_export.wire_vocabulary(),
        ]
    )
    # "Hola Isabel" es un saludo y no un dato: lo que mide si un mensaje trae algo
    # necesita conocer a las agentes, y las conoce por aqui y no por su nombre.
    social.install_agent_names(_agentes())
    case_opening.install_agent_names(_agentes())
    # Y las palabras de nuestras propias frases, para lo que la agente dice y se
    # guarda: sus datos se tapan y sus palabras no se confunden con nombres.
    redaccion.allow_own_vocabulary([entrada.text for entrada in copy_api.load().entries.values()])
    try:
        await asyncio.to_thread(redaccion.warm_up)
    except Exception as error:  # noqa: BLE001 -- precarga: el fallo real se levanta al primer uso, con su propio manejo
        observability.emit("redaction.preload_failed", error=type(error).__name__)


def _montar_el_directorio(
    app: FastAPI, registro: surfaces.SurfaceRegistry, opciones: Settings
) -> None:
    """Las rutas publicas de solo lectura: el directorio del sitio y las polizas."""
    app.include_router(
        site.router(
            site.SiteDeps(
                registry=registro,
                links=site.SiteLinks(readme_url=opciones.readme_url, video_url=opciones.video_url),
                tenants=lambda: tenancy.loaded().available,
            )
        )
    )
    app.include_router(
        policies.router(policies.PoliciesDeps(tenants=lambda: tenancy.loaded().available))
    )


def build_app(  # noqa: PLR0915 -- la raiz de composicion crece una linea por pieza que cablea (C-24), y partirla esconderia el orden de arranque que su docstring explica
    settings: Settings | None = None,
    modules: Sequence[ModuleSpec] | None = None,
    dist_dir: Path | None = None,
    *,
    for_evals: bool = False,
) -> FastAPI:
    """Construye la aplicacion.

    `for_evals` la arma para la corrida completa de evaluaciones
    (`untangle.server.understanding_cli --subset completa`): las piezas de Claude
    con la clave de evaluaciones. No se sirve.

    El orden importa y es parte del diseno: primero el objeto de configuracion,
    que valida el entorno, y solo despues cualquier adaptador. Un diseno que
    validara al primer uso fallaria a mitad de la corrida, con cuota ya gastada.

    `dist_dir` es donde estan los estaticos compilados de la interfaz; por
    omision, `app/frontend/dist/` (CG-U6-5). Las pruebas pasan uno propio.
    """
    opciones = settings if settings is not None else Settings()

    # El catalogo se carga una vez, aqui, y queda inmutable. Si un archivo no
    # esta, falla al arrancar nombrandolo, no en la primera frase que alguien
    # pida (diseno de rendimiento).
    copy_api.install(copy_api.load())

    # Los patrones de los controles de cumplimiento, tambien al arrancar. Un
    # archivo invalido --un patron que no compila, o con mayusculas o tildes que
    # nunca coincidirian-- impide arrancar nombrando el archivo y el patron
    # (TECH-U10.1): una guardia viva con sus patrones rotos parece que funciona.
    cumplimiento.install_patterns(cumplimiento.load_patterns())

    # Las aseguradoras, tambien una sola vez. Una carpeta rota apaga **solo la
    # suya**, nombrando el archivo y la clave; las demas siguen vivas (BR4.1).
    aseguradoras = tenancy.load()
    tenancy.install(aseguradoras)
    for caida in aseguradoras.unavailable:
        observability.emit(
            "server.tenant_unavailable",
            tenant_id=caida.tenant_id,
            detail=caida.detail,
        )

    # La carpeta de proveedores: los modelos anclados, el plan de cada uso, los
    # precios con su version y los limites. Una sola vez y sin recarga en
    # caliente, porque cambiar un precio o un identificador de modelo mueve una
    # cifra publicada y tiene que quedar en el historial.
    configuracion = provider_config.load()
    spend.install(spend_wiring.spend_runtime(configuracion))
    plataforma = build_provider_platform(opciones, configuracion)

    # La voz (U15): los clientes de Deepgram y Cartesia con las claves del uso
    # `voice`, el techo y el registro de gasto delante de cada llamada, y la
    # disponibilidad de la voz de cada aseguradora, decidida aqui una sola vez y
    # sin preguntarle a ningun proveedor. Una configuracion de voz rota apaga la
    # voz de **esa** aseguradora, con su motivo y su evento, y el proceso y el
    # chat arrancan igual (BR2.2). Sin claves de voz no hay cliente y nada se
    # exige al arrancar: quien llame la pide y el fallo nombra la variable. Sin
    # base, el techo no se puede leer y la voz queda cerrada (BR5.1).
    voz = speech.build_speech_platform(opciones, configuracion, aseguradoras.available)

    _instalar_lo_que_depende_de_la_base(opciones)

    # Las trazas hacia Langfuse Cloud (2026-10-14): con las tres variables puestas se
    # instala su transporte y, en el ciclo de vida de abajo, arranca la tarea que
    # exporta cada 15 segundos. Sin ellas `build` devuelve `None` y no corre nada
    # nuevo. Tampoco en la corrida de evaluaciones, que no se sirve y no exporta: sus
    # casos no son trazas de nadie y gastarian el cupo del plan gratuito.
    envio_de_trazas = None if for_evals else trace_shipping.build(opciones)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await _cargar_el_detector()
        # La asercion de aislamiento es condicion de arranque cuando hay base
        # (C-10). Sin base declarada no hay nada que comprobar y no se inventa
        # una: es el caso del arranque de quince minutos, que no la necesita.
        if opciones.database_url:
            await verificar_aislamiento()
            # La cola de lo no facturable solo tiene sentido con base: sin ella
            # no hay donde escribir, y una cola sin quien la drene creceria en
            # silencio. Sin base, esas escrituras son sincronas y fallan a la
            # vista.
            spend.start_deferred_writer()
        # Despues de la asercion de aislamiento, como la cola del gasto: un proceso que
        # no arranca no exporta nada.
        if envio_de_trazas is not None:
            await envio_de_trazas.start()
        try:
            yield
        finally:
            # El orden importa: primero se drena lo pendiente --un apagado que
            # descartara filas tendria el mismo efecto que descartarlas al
            # llenarse--, despues se cierran los clientes del proveedor, y solo
            # entonces se suelta la base. La ultima exportacion de trazas va antes de
            # todo: si falla, marca perdidos resumenes que viven en la base.
            if envio_de_trazas is not None:
                await envio_de_trazas.stop()
            await spend.stop_deferred_writer()
            await plataforma.transports.aclose()
            await tenancy.dispose()

    # Sin paginas de documentacion ni esquema publicados. Las paginas cargan
    # sus scripts de un tercero, que la politica de contenido bloquea (CG-U6-2)
    # y que el arnes de accesibilidad cuenta como peticion ajena (SEC-U6.2). El
    # esquema se genera sin servirlo, con `mise run contracts:gen` (C-28).
    app = FastAPI(
        title="Untangle",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = opciones
    app.state.providers = plataforma
    # U16 lee aqui, en proceso, si la voz de una aseguradora puede atender
    # (`availability_for`) y pide por aqui la sintesis y la transcripcion.
    app.state.speech = voz
    controles = build_compliance(opciones)
    app.state.compliance = controles
    # El cifrador de los campos del caso y el runtime del grafo: las dos piezas que
    # `install`/`install_runtime` esperaban de esta raiz y que nadie enchufaba.
    cifrador = _instalar_cifrador(opciones)
    cableado = _cablear_el_chat(
        plataforma,
        controles,
        cifrador,
        _piezas_de_claude(opciones, configuracion, for_evals=for_evals),
        wait_for_offer=not for_evals,
    )
    if cableado.runtime is not None:
        orchestration_turn.install_runtime(cableado.runtime)
    else:
        # Sin runtime el chat no atiende. Se dice aqui, al arrancar, en vez de
        # descubrirse con una persona escribiendo: lo que faltaba antes no era el
        # cableado sino el aviso de que faltaba.
        observability.emit(
            "server.graph_runtime_not_installed",
            missing=cableado.missing or "",
        )
    problems.install_handlers(app)
    problems.install_openapi(app)

    # Primero los modulos, con sus rutas y sus superficies; despues la salud y
    # el directorio, que leen el registro; al final las dos ramas que atrapan
    # todo lo que quede. El enrutador prueba las rutas en ese orden (BR6.1).
    # El chat declara el puerto y aqui se enchufa el grafo: un canal que
    # importara el modulo del runtime arrastraria LangGraph por transitividad, y
    # el contrato "LangGraph solo dentro del runtime del grafo" lo prohibe.
    chat_api.install_turn_handler(orchestration_turn.handle_turn)
    # **El mismo manejador por el otro canal.** Es lo que hace cierto AC1.23.1:
    # el mismo guion entregado por voz y por chat deja los mismos campos, porque
    # la conversacion la decide el grafo y no el canal. Entra enchufado por la
    # misma razon que en el chat: importarlo arrastraria LangGraph a la unidad.
    #
    # La plataforma de voz entra por aqui tambien, ya construida: la llamada la
    # necesita para transcribir y sintetizar, y `app.state.speech` de arriba es
    # la misma instancia --una segunda abriria un segundo juego de clientes con
    # las mismas claves--.
    voice_routes.install(
        voice_routes.VoiceDeps(
            speech=voz,
            handle_turn=orchestration_turn.handle_turn,
            # La misma lectura que el chat hace antes de entregar un mensaje, para que la
            # llamada la adelante mientras corre la tolerancia de fin de habla.
            understand_turn=orchestration_turn.understand_turn,
            # El fin de una llamada resuelve un reporte que quedo en revision (US1.17).
            settle_review=orchestration_turn.settle_review,
            # Dos claves y no una (PENDIENTES 1.16): el token de socket firma con
            # la suya, y el enlace de caso que la ruta de desenlace entrega sigue
            # con la de U2, que es la que la bandeja verifica.
            token_signing_key=opciones.voice_token_signing_key,
            case_link_signing_key=opciones.case_link_signing_key,
        )
    )
    # La bandeja verifica cada credencial con la clave que esta raiz resolvio,
    # no con la que haya en el entorno cuando llegue la peticion: son dos cosas
    # distintas y cuando difieren la ruta rechaza credenciales validas.
    inbox_api.install_keys(
        staff_credential=opciones.staff_credential_signing_key,
        case_link=opciones.case_link_signing_key,
    )
    # El chat muestra el caso mientras avanza, con el mismo enlace que la llamada
    # da al colgar (decision de Miguel, 2026-10-06): la misma clave de U2.
    chat_api.install_case_link_key(opciones.case_link_signing_key)
    _enchufar_la_bandeja()
    # El canje del enlace del visitante (C-07). Va aparte del router de la bandeja
    # porque no cuelga de ninguna aseguradora: quien lo usa no tiene credencial.
    app.include_router(inbox_api.visitor_router())
    # Los casos de ejemplo de la pagina publica "Casos": dos lecturas, sin credencial,
    # que solo entregan casos del generador (`inbox.examples`).
    app.include_router(inbox_api.examples_router())

    registro = mount_modules(
        app,
        mountable_modules(modules if modules is not None else MODULOS, opciones),
    )
    app.state.surfaces = registro

    # La salud de C-02 reemplaza al `/health` de U1 (CG-U6-8, FD-U6-6): una sola
    # salud, con la forma del contrato. Los indicadores de U5 siguen sin volver
    # no apto al proceso.
    app.include_router(
        health.router(
            health.HealthDeps(
                version=opciones.commit_sha or health.VERSION_UNKNOWN,
                providers=_indicadores_de_proveedor(plataforma),
                registry=registro,
                database_check=health.database_check if opciones.database_url else None,
                tenant_count=lambda: len(tenancy.available_ids()),
                demo_reset_check=health.demo_reset_check if opciones.database_url else None,
            )
        )
    )
    _montar_el_directorio(app, registro, opciones)
    web.install(app, dist_dir=dist_dir if dist_dir is not None else paths.frontend_dist_dir())
    return app
