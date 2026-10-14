"""Lo que las pruebas de integracion de U14 necesitan en la base efimera.

**Los casos son las colisiones de DS-8**, y eso no es un detalle del montaje: es
lo unico que hace que la prueba de aislamiento signifique algo. Con datos que no
colisionan, una consulta sin ningun filtro por aseguradora tambien devolveria
"solo lo mio", y la prueba pasaria contra una bandeja sin aislamiento.

Lo que colisiona entre las dos emisoras es el **numero de poliza** y el **nombre
del asegurado**. El identificador de caso no: es unico en toda la base, y esa fue
la decision de Miguel del 2026-09-28 cuando esta unidad descubrio que la fixture
declaraba una colision que `case_record` no admite. La razon entera esta en
`synthetic_data/ds8.py`.

Las dos filas viven en la misma tabla, asi que una consulta a la que le faltara el
filtro por aseguradora devolveria las dos y la asercion se cae igual.

Los casos se crean con la API de U4 y por el camino declarado de transiciones
--abierto, capturando, derivado--; ninguna aseguradora se escribe a mano: salen
de `app/config/tenants/`.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import pytest
from fastapi import FastAPI
from sqlalchemy import event as sqlalchemy_event

from untangle import paths
from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.case_record import rules as case_rules
from untangle.case_record.models import (
    Actor,
    ActorType,
    AttachmentKind,
    AttachmentState,
    CaseState,
    Channel,
    ClosingEvidence,
    DerivationReason,
    Origin,
    RecordType,
    Resolution,
)
from untangle.copy_catalog import api as copy_api
from untangle.rules.models import FiredRule, RuleEvaluation
from untangle.rules.repository import save_evaluation
from untangle.server import composition
from untangle.settings import Settings
from untangle.telemetry.spend import api as spend
from untangle.telemetry.traces import api as trazas
from untangle.tenancy import api as tenancy
from untangle.tenancy import ephemeral, session

#: Un instante fijo para toda la suite. El reloj entra por argumento: una conducta
#: que leyera el del proceso solo se podria probar esperando.
AHORA = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)

#: Marcas de clave que no valen para nada mas que firmar en la prueba. Si alguna
#: apareciera en una respuesta, se veria a simple vista.
CLAVE_DE_BANDEJA = "marca-de-clave-de-bandeja-que-no-debe-salir-00002"
CLAVE_DE_ENLACES = "marca-de-clave-de-enlaces-que-no-debe-salir-000003"

#: La cookie que lleva la credencial de la bandeja. Se nombra aqui igual que en
#: la ruta: si divergieran, estas pruebas dejarian de probar la ruta real.
COOKIE = "untangle_staff"


@dataclass(frozen=True)
class Colision:
    """Una fila de DS-8: el mismo caso en dos aseguradoras."""

    tenant_id: str
    case_id: str
    #: Lo que de verdad colisiona entre las dos emisoras, y el esquema lo admite.
    policy_number: str


def cargar_ds8() -> tuple[Colision, ...]:
    """Las colisiones de DS-8 desde su archivo versionado, nunca generadas al correr."""
    archivo = paths.fixtures_dir() / "ds8_isolation.json"
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    return tuple(
        Colision(
            tenant_id=fila["tenant_id"],
            case_id=fila["case_id"],
            policy_number=fila["policy_number"],
        )
        for fila in datos["rows"]["cases"]
    )


async def _vaciar() -> None:
    for tenant_id in tenancy.available_ids():
        async with session.session_for(tenant_id) as sesion:
            await session.execute_sql(sesion, "DELETE FROM inbox_event")
            await session.execute_sql(sesion, "DELETE FROM decision_receipt")
            await session.execute_sql(sesion, "DELETE FROM case_record")


@pytest.fixture
async def base_de_u14(sesiones: ephemeral.EphemeralDatabase) -> AsyncIterator[None]:
    await _vaciar()
    yield
    await _vaciar()


@pytest.fixture
async def colisiones(base_de_u14: None) -> tuple[Colision, ...]:
    """Siembra las colisiones de DS-8 como casos derivados, listos para la cola.

    Derivados y no abiertos: la cola es la lista de lo que **espera decision**, y
    un caso recien abierto todavia no la espera.
    """
    del base_de_u14
    filas = cargar_ds8()
    for fila in filas:
        await casos.create_case(
            fila.tenant_id,
            casos.NewCase(
                case_id=fila.case_id,
                record_type=RecordType.CLAIM,
                channel=Channel.CHAT,
                origin=Origin.GENERATOR,
                language="es",
                policy_ref=fila.policy_number,
            ),
            now=AHORA,
        )
        # Por el camino declarado --abierto, capturando, derivado-- y no
        # escribiendo el estado a mano: sembrar por una via que el aplicativo no
        # usa probaria una via que nadie usa.
        await casos.apply_transition(
            fila.tenant_id,
            fila.case_id,
            CaseState.CAPTURING,
            context=case_rules.TransitionContext(
                now=AHORA,
                actor=Actor(actor_type=ActorType.SYSTEM),
                channel=Channel.CHAT,
            ),
        )
        await casos.apply_transition(
            fila.tenant_id,
            fila.case_id,
            CaseState.DERIVED,
            context=case_rules.TransitionContext(
                now=AHORA,
                actor=Actor(actor_type=ActorType.SYSTEM),
                channel=Channel.CHAT,
                derivation_reason=DerivationReason.PERSON_REQUESTED,
            ),
        )
    return filas


@pytest.fixture(autouse=True)
def cifrador(monkeypatch: pytest.MonkeyPatch) -> Iterator[crypto.Cipher]:
    """Un cifrador de la prueba, instalado como lo instala la raiz de composicion.

    La clave sale del entorno, nunca del repositorio, igual que en produccion; aqui
    se genera una por corrida para que ninguna prueba dependa de otra.
    """
    monkeypatch.setenv(crypto.KEY_ENV_VAR, crypto.generate_key())
    cipher = crypto.Cipher.from_settings()
    crypto.install(cipher)
    yield cipher
    crypto.reset()


@pytest.fixture
def contador_de_consultas() -> Callable[[], AbstractContextManager[list[str]]]:
    """Cuenta las consultas que salen por el punto unico de sesion.

    Se engancha al motor de verdad y no a una capa intermedia: lo que interesa es
    cuantas veces se habla con la base, no cuantas veces se llama a una funcion.
    """

    @contextmanager
    def contar() -> Iterator[list[str]]:
        consultas: list[str] = []

        def anotar(conn: object, cursor: object, statement: str, *resto: object) -> None:
            del conn, cursor, resto
            primera = " ".join(statement.split())[:80]
            # Las sentencias del punto unico de sesion --fijar la aseguradora-- no
            # son consultas de la vista: las cuenta U2 y contarlas aqui haria que
            # el numero dependiera de cuantas sesiones se abrieron, no de cuantos
            # bloques se pidieron.
            if primera.lower().startswith(("set ", "select set_config", "begin", "commit")):
                return
            consultas.append(primera)

        motor = session._require_engine().sync_engine
        sqlalchemy_event.listen(motor, "before_cursor_execute", anotar)
        try:
            yield consultas
        finally:
            sqlalchemy_event.remove(motor, "before_cursor_execute", anotar)

    return contar


@pytest.fixture
def dos_aseguradoras() -> tuple[str, str]:
    """Dos aseguradoras cargadas, en orden de identificador. Ninguna escrita a mano."""
    disponibles = sorted(tenancy.available_ids())
    return disponibles[0], disponibles[1]


@pytest.fixture
async def app(sesiones: ephemeral.EphemeralDatabase, tmp_path: Path) -> AsyncIterator[FastAPI]:
    ajustes = Settings(
        env="local",
        database_url=sesiones.app_url,
        commit_sha="abc1234",
        staff_credential_signing_key=CLAVE_DE_BANDEJA,
        case_link_signing_key=CLAVE_DE_ENLACES,
    )
    construida = composition.build_app(ajustes, dist_dir=tmp_path)
    try:
        yield construida
    finally:
        await session.dispose()
        session.configure(sesiones.app_url)
        spend.reset()
        trazas.reset_summaries()
        copy_api.reset()


def cliente(app: FastAPI, *, credencial: str | None = None) -> httpx2.AsyncClient:
    """Un cliente contra la aplicacion, con su credencial puesta si la lleva.

    La credencial va en el cliente y no en cada peticion: el cliente de pruebas
    considera ambiguo lo segundo, y una credencial por peticion es justo lo que
    la ruta **no** acepta --viaja en la cookie del navegador, nunca suelta--.
    """
    transporte = httpx2.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx2.AsyncClient(
        transport=transporte,
        # `https` y no `http`: la cookie de caso se emite `Secure`, como debe, y
        # un cliente que hablara por texto plano la descartaria en silencio. Se
        # ajusta la prueba al aplicativo y no al reves.
        base_url="https://testserver",
        cookies={COOKIE: credencial} if credencial is not None else None,
    )


def credencial_de(tenant_id: str, *, now: datetime | None = None) -> str:
    """Una credencial firmada de la primera persona declarada por esa aseguradora.

    **Se emite con el reloj de verdad**, no con `AHORA`. Una credencial emitida a las
    doce del 2026-09-28 vence doce horas despues, y desde la medianoche UTC de ese dia
    esta caducada **para siempre**: la ruta la rechaza con `expired` y toda prueba que
    entre por la puerta se cae, no de vez en cuando sino a partir de una hora fija. Se
    descubrio en la tanda 4, cuando el guion de verificacion cruzo esa medianoche a
    mitad de una corrida y treinta pruebas que habian pasado veinte minutos antes se
    pusieron rojas.

    Es el mismo defecto que la tanda 3 arreglo para los enlaces firmados, en el mismo
    archivo y con la misma forma. Quedaba el otro lado sin arreglar: **un dato con
    caducidad sembrado con un reloj fijo es una bomba de tiempo, y las dos veces se vio
    como un fallo de otra cosa**.

    Quien necesite un instante concreto --las pruebas de los bordes-- lo pasa por
    argumento, que es lo que permite probar el vencimiento sin esperar doce horas.
    """
    from untangle.tenancy import staff_identity

    tenant = tenancy.require(tenant_id)
    return staff_identity.issue_credential(
        tenant_id=tenant_id,
        principal_id=tenant.staff[0].principal_id,
        signing_key=CLAVE_DE_BANDEJA,
        now=now if now is not None else datetime.now(UTC),
    )


def dos_aseguradoras_con_colision(filas: tuple[Colision, ...]) -> tuple[str, str]:
    """Las dos aseguradoras cuyos casos comparten numero de poliza.

    Se buscan por la colision y no por su nombre: el dia que DS-8 cambie de
    aseguradoras, estas pruebas siguen apuntando a las que colisionan en vez de a
    un identificador escrito a mano, que la regla del proyecto prohibe.
    """
    por_poliza: dict[str, list[str]] = {}
    for fila in filas:
        por_poliza.setdefault(fila.policy_number, []).append(fila.tenant_id)
    for tenants in por_poliza.values():
        if len(tenants) >= 2:
            return tenants[0], tenants[1]
    msg = "DS-8 dejo de traer dos aseguradoras con casos sobre la misma poliza"
    raise AssertionError(msg)


async def nuevo_caso(  # noqa: PLR0913 -- cada uno mueve una dimension de la cola
    tenant_id: str,
    *,
    case_id: str | None = None,
    motivo: DerivationReason = DerivationReason.RULE,
    derivado_en: datetime | None = None,
    estado: CaseState = CaseState.DERIVED,
    idioma: Locale = "es",
    canal: Channel = Channel.CHAT,
    origen: Origin = Origin.GENERATOR,
) -> str:
    """Un caso sembrado por el camino declarado, hasta el estado que se pida.

    El motivo decide la prioridad --`person_requested` la sube a alta por BR3.8 de
    U4-- y el instante decide la espera. Ninguno de los dos se escribe a mano en
    la fila: se piden como los pide el aplicativo y el modelo los deriva.
    """
    identificador = case_id or f"caso-{uuid.uuid4().hex[:12]}"
    cuando = derivado_en or AHORA
    await casos.create_case(
        tenant_id,
        casos.NewCase(
            case_id=identificador,
            record_type=RecordType.CLAIM,
            channel=canal,
            origin=origen,
            language=idioma,
            policy_ref=None,
        ),
        now=AHORA,
    )
    if estado is CaseState.OPEN:
        return identificador

    contexto = case_rules.TransitionContext(
        now=cuando,
        actor=Actor(actor_type=ActorType.SYSTEM),
        channel=canal,
    )
    await casos.apply_transition(tenant_id, identificador, CaseState.CAPTURING, context=contexto)
    if estado is CaseState.CAPTURING:
        return identificador

    # El camino de la evaluacion automatica, tal como lo sigue el aplicativo: la
    # captura cierra un bloque (T2) y las reglas evaluan (T4).
    if estado in (CaseState.VERIFYING, CaseState.DECIDING):
        await casos.apply_transition(
            tenant_id, identificador, CaseState.VERIFYING, context=contexto
        )
        if estado is CaseState.DECIDING:
            await casos.apply_transition(
                tenant_id, identificador, CaseState.DECIDING, context=contexto
            )
        return identificador

    await casos.apply_transition(
        tenant_id,
        identificador,
        CaseState.DERIVED,
        context=case_rules.TransitionContext(
            now=cuando,
            actor=Actor(actor_type=ActorType.SYSTEM),
            channel=canal,
            derivation_reason=motivo,
        ),
    )
    if estado is CaseState.DERIVED:
        return identificador

    await casos.apply_transition(
        tenant_id,
        identificador,
        CaseState.AWAITING_INSURED,
        context=case_rules.TransitionContext(
            now=cuando,
            actor=Actor(actor_type=ActorType.STAFF, actor_id="diana"),
            channel=canal,
        ),
    )
    return identificador


async def cerrado_por_las_reglas(tenant_id: str, *, case_id: str | None = None) -> str:
    """Un caso cerrado por **cierre directo** (US1.17): lo cierran las reglas, nadie decide.

    Por el camino que seguira el aplicativo: captura, verificacion, evaluacion y T6 con
    actor `system` y sin identificador, resolucion `registered` y una evaluacion de
    reglas de categoria `direct_close` guardada. Sembrarlo por otra via probaria una
    pantalla contra un caso que el aplicativo no produce.
    """
    identificador = await nuevo_caso(tenant_id, case_id=case_id, estado=CaseState.DECIDING)
    await save_evaluation(
        RuleEvaluation(
            evaluation_id=f"ev-{identificador}",
            tenant_id=tenant_id,
            case_id=identificador,
            ruleset_version="v1",
            category="direct_close",
            fired_rules=(FiredRule(id="R-CIERRE-DIRECTO", version=1, touches_money=False),),
            inputs_snapshot={"amount_mentioned": "false"},
            explanation_key="rules.explanation.direct_close",
            evaluated_at=AHORA,
        )
    )
    await casos.close_case(
        tenant_id,
        identificador,
        resolution=Resolution.REGISTERED,
        closing_evidence=ClosingEvidence(
            transcript=AttachmentState(kind=AttachmentKind.PRESENT, reference=identificador),
            cited_clauses=AttachmentState(kind=AttachmentKind.EMPTY),
            fired_rules=AttachmentState(kind=AttachmentKind.PRESENT, reference=identificador),
            trace_id=AttachmentState(kind=AttachmentKind.EMPTY),
            control_results=AttachmentState(kind=AttachmentKind.EMPTY),
        ),
        context=case_rules.TransitionContext(
            now=AHORA,
            actor=Actor(actor_type=ActorType.SYSTEM),
            channel=Channel.CHAT,
        ),
    )
    return identificador
