"""Lo que las pruebas de integracion de U19 necesitan en la base efimera.

**Dos aseguradoras con el mismo contenido**, y eso no es un detalle del montaje:
las dos solicitudes sembradas llevan el mismo idioma, el mismo canal y el mismo
motivo de derivacion, asi que **nada en la fila distingue una de otra salvo su
aseguradora**. Una consulta a la que le faltara el filtro por aseguradora
devolveria las dos y la asercion del conjunto exacto se cae; con contenidos
distintos, una lista contaminada seguiria pareciendo plausible.

Las dos se crean por la API de U4 y por el camino declarado de transiciones
--abierto, capturando, derivado--, nunca escribiendo el estado a mano: sembrar
por una via que el aplicativo no usa probaria una via que nadie usa.

Ninguna aseguradora se nombra a mano: la que cotiza se busca por su bandera en la
configuracion versionada, y la otra por ser distinta de ella.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import pytest
from fastapi import FastAPI

from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.case_record import rules as case_rules
from untangle.case_record.models import (
    Actor,
    ActorType,
    CaseState,
    Channel,
    DerivationReason,
    Origin,
    RecordType,
)
from untangle.copy_catalog import api as copy_api
from untangle.server import composition
from untangle.settings import Settings
from untangle.telemetry.spend import api as spend
from untangle.telemetry.traces import api as trazas
from untangle.tenancy import api as tenancy
from untangle.tenancy import ephemeral, session, staff_identity
from untangle.tenancy.models import Role

#: Un instante fijo para los datos sembrados. El reloj entra por argumento: una
#: conducta que leyera el del proceso solo se podria probar esperando.
AHORA = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)

#: Marcas de clave que no valen para nada mas que firmar en la prueba. Si alguna
#: apareciera en una respuesta, se veria a simple vista.
CLAVE_DE_BANDEJA = "marca-de-clave-de-bandeja-que-no-debe-salir-00019"
CLAVE_DE_ENLACES = "marca-de-clave-de-enlaces-que-no-debe-salir-000019"

#: La cookie que lleva la credencial de la bandeja. Se nombra aqui igual que en
#: la ruta: si divergieran, estas pruebas dejarian de probar la ruta real.
COOKIE = "untangle_staff"


async def _vaciar() -> None:
    for tenant_id in tenancy.available_ids():
        async with session.session_for(tenant_id) as sesion:
            await session.execute_sql(sesion, "DELETE FROM inbox_event")
            await session.execute_sql(sesion, "DELETE FROM decision_receipt")
            await session.execute_sql(sesion, "DELETE FROM case_record")


@pytest.fixture
async def base_de_u19(sesiones: ephemeral.EphemeralDatabase) -> AsyncIterator[None]:
    del sesiones
    await _vaciar()
    yield
    await _vaciar()


@pytest.fixture(autouse=True)
def cifrador(monkeypatch: pytest.MonkeyPatch) -> Iterator[crypto.Cipher]:
    """Un cifrador de la prueba, instalado como lo instala la raiz de composicion."""
    monkeypatch.setenv(crypto.KEY_ENV_VAR, crypto.generate_key())
    cipher = crypto.Cipher.from_settings()
    crypto.install(cipher)
    yield cipher
    crypto.reset()


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


@pytest.fixture
def aseguradora_que_cotiza() -> str:
    """La que tiene la cotizacion activa en su configuracion versionada.

    Se busca por la bandera y no por su nombre: el dia que otra la active, estas
    pruebas siguen apuntando a la que cotiza en vez de a un identificador escrito
    a mano, que la regla del proyecto prohibe.
    """
    activas = sorted(c.tenant_id for c in tenancy.loaded().available if c.quote_enabled)
    if not activas:
        msg = "ninguna aseguradora declara `quote_enabled: true`"
        raise AssertionError(msg)
    return activas[0]


@pytest.fixture
def otra_aseguradora(aseguradora_que_cotiza: str) -> str:
    """Cualquier otra aseguradora cargada. Es el otro lado del aislamiento."""
    otras = sorted(t for t in tenancy.available_ids() if t != aseguradora_que_cotiza)
    if not otras:
        msg = "hace falta una segunda aseguradora para probar el aislamiento"
        raise AssertionError(msg)
    return otras[0]


def cliente(app: FastAPI, *, credencial: str | None = None) -> httpx2.AsyncClient:
    """Un cliente contra la aplicacion, con su credencial puesta si la lleva."""
    transporte = httpx2.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx2.AsyncClient(
        transport=transporte,
        # `https` y no `http`: la cookie de caso se emite `Secure`, como debe, y un
        # cliente que hablara por texto plano la descartaria en silencio.
        base_url="https://testserver",
        cookies={COOKIE: credencial} if credencial is not None else None,
    )


def credencial_de_rol(tenant_id: str, rol: Role) -> str:
    """Una credencial firmada de la persona que esa aseguradora declara con ese rol.

    **Con el reloj de verdad**, no con `AHORA`: una credencial emitida con un
    instante fijo caduca doce horas despues de ese instante y a partir de entonces
    toda prueba que entre por la puerta se cae. Le paso a U14 dos veces, en los
    enlaces y en las credenciales, y las dos veces se vio como un fallo de otra
    cosa.
    """
    tenant = tenancy.require(tenant_id)
    persona = next((p for p in tenant.staff if p.role is rol), None)
    if persona is None:
        declaradas = ", ".join(f"{p.principal_id}:{p.role.value}" for p in tenant.staff)
        msg = f"'{tenant_id}' no declara ninguna persona con rol '{rol.value}'; hay: {declaradas}"
        raise AssertionError(msg)
    return staff_identity.issue_credential(
        tenant_id=tenant_id,
        principal_id=persona.principal_id,
        signing_key=CLAVE_DE_BANDEJA,
        now=datetime.now(UTC),
    )


async def nueva_solicitud(
    tenant_id: str,
    *,
    tipo: RecordType = RecordType.QUOTE_REQUEST,
    estado: CaseState = CaseState.DERIVED,
    idioma: Locale = "en",
) -> str:
    """Un caso sembrado por el camino declarado, hasta el estado que se pida.

    El tipo entra por argumento porque la mitad de lo que U19 comprueba es que la
    bandeja del suscriptor **no** trae los otros tipos.
    """
    identificador = f"caso-{uuid.uuid4().hex[:12]}"
    await casos.create_case(
        tenant_id,
        casos.NewCase(
            case_id=identificador,
            record_type=tipo,
            channel=Channel.CHAT,
            origin=Origin.GENERATOR,
            language=idioma,
            # Una solicitud de cotizacion es de quien todavia no tiene poliza.
            policy_ref=None,
        ),
        now=AHORA,
    )
    if estado is CaseState.OPEN:
        return identificador

    contexto = case_rules.TransitionContext(
        now=AHORA,
        actor=Actor(actor_type=ActorType.SYSTEM),
        channel=Channel.CHAT,
    )
    await casos.apply_transition(tenant_id, identificador, CaseState.CAPTURING, context=contexto)
    if estado is CaseState.CAPTURING:
        return identificador

    await casos.apply_transition(
        tenant_id,
        identificador,
        CaseState.DERIVED,
        context=case_rules.TransitionContext(
            now=AHORA,
            actor=Actor(actor_type=ActorType.SYSTEM),
            channel=Channel.CHAT,
            # La derivan las reglas de elegibilidad de la tanda 1 (BR2.3).
            derivation_reason=DerivationReason.RULE,
        ),
    )
    return identificador
