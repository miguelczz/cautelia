"""El reinicio nocturno contra los nueve purgadores de verdad (BR2.1 a BR2.3, BR3.1).

Lo que la tanda 1 no podia probar con dobles: que lo que cada dueno declara como
dato de visitante **se va de verdad**, que el registro de gasto se queda, y que
la corrida quede escrita donde el contador de 24 horas la busca.

**La pregunta por las tablas se le hace al catalogo**, no a una lista escrita
aqui: la prueba recorre las que la base marca como dato de visitante y exige que
ninguna quede con una fila. Una lista escrita aqui no veria la tabla que nadie
apunto, que es justo el olvido que esta compuerta existe para atrapar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest

from untangle.demo_operations import repository
from untangle.demo_operations.api import ResetOutcome, accepts_new_cases
from untangle.server import composition, demo_reset
from untangle.telemetry.traces.purge import TraceBackendNotPurgeableError
from untangle.tenancy import purge as purga
from untangle.tenancy import session
from untangle.tenancy.models import PurgeResult

from .conftest import (
    HOY,
    aseguradora,
    contar_en,
    contar_sin_aseguradora,
    sembrar_caso_del_generador,
    sembrar_datos_de_visitante,
    sembrar_dinero,
)

pytestmark = pytest.mark.usefixtures("base_de_u20")


@dataclass(frozen=True)
class PurgadorCaido:
    """Un purgador que levanta, para el camino del fallo contra la base de verdad."""

    name: str = "purgador_caido"
    tables: tuple[str, ...] = ()

    async def purge(self, *, older_than: datetime, dry_run: bool = False) -> PurgeResult:
        del older_than, dry_run
        msg = "la base del backend no contesto"
        raise TraceBackendNotPurgeableError(msg)


async def test_tras_el_reinicio_ninguna_tabla_marcada_conserva_una_fila(
    sin_transporte: None,
) -> None:
    """BR2.1, compuerta dura: cero datos de visitante, y se le pregunta al catalogo.

    Las ocho tablas que la siembra toca se comprueban **no vacias antes**: sin
    eso, una tabla que nadie sembro pasaria la segunda mitad por estar vacia
    desde el principio, que es la prueba que no puede distinguir.
    """
    tenant_id = aseguradora()
    sembrado = await sembrar_datos_de_visitante(tenant_id)

    for tabla in sembrado.tablas:
        assert await contar_en(tenant_id, tabla) > 0, f"la siembra no dejo nada en '{tabla}'"

    corrida = await demo_reset.reset_now(composition.PURGADORES, now=HOY)

    assert corrida.outcome is ResetOutcome.SUCCEEDED
    marcadas = await purga.visitor_data_tables()
    con_filas = {
        tabla: await contar_en(tenant_id, tabla)
        for tabla in sorted(marcadas)
        if await contar_en(tenant_id, tabla) > 0
    }
    assert con_filas == {}, f"estas tablas marcadas conservan filas de visitante: {con_filas}"


async def test_los_nueve_purgadores_corren_en_el_orden_del_registro(
    sin_transporte: None,
) -> None:
    """BR2.3: el reinicio no borra ninguna tabla; llama al registro escrito a mano.

    Se exige el **orden** y no solo el conjunto: el registro es una tupla escrita
    a mano y su orden es parte de lo que se reviso.
    """
    corrida = await demo_reset.reset_now(composition.PURGADORES, now=HOY)

    assert [fila.name for fila in corrida.purgers] == [
        purgador.name for purgador in composition.PURGADORES
    ]
    assert len(corrida.purgers) == 9


async def test_el_registro_de_gasto_sobrevive_al_reinicio(sin_transporte: None) -> None:
    """BR2.2, compuerta dura: el acumulado no baja y el libro mayor no pierde una fila.

    Lo que conserva no lo decide esta unidad: lo declara el purgador de U5. Lo
    que esta prueba comprueba es que **sigue siendo cierto** cuando corre el
    registro entero, que es la unica forma en la que corre de verdad.
    """
    tenant_id = aseguradora()
    sembrado = await sembrar_datos_de_visitante(tenant_id)
    await sembrar_dinero(tenant_id, case_id=sembrado.case_id)

    antes = await _foto_del_dinero()
    corrida = await demo_reset.reset_now(composition.PURGADORES, now=HOY)

    assert corrida.outcome is ResetOutcome.SUCCEEDED
    despues = await _foto_del_dinero()
    assert despues["spend_entry"] == antes["spend_entry"] == 1
    assert despues["budget_window"] == antes["budget_window"] == 1
    assert despues["acumulado"] == antes["acumulado"]
    # El contador del sitio se queda y los dos del visitante se van: tres filas
    # antes, una despues.
    assert (antes["quota_counter"], despues["quota_counter"]) == (3, 1)
    assert await _alcance_del_unico_contador() == "voice_calls_site_day"


async def test_la_fila_del_gasto_sobrevive_al_caso_que_nombraba(sin_transporte: None) -> None:
    """BR7.5 de U5, vista desde el reinicio: la fila se queda y su caso se va.

    Es lo que hace que el acumulado no se pueda recalcular hacia abajo borrando
    casos. La columna queda en nulo, y lo hace la base.
    """
    tenant_id = aseguradora()
    sembrado = await sembrar_datos_de_visitante(tenant_id)
    await sembrar_dinero(tenant_id, case_id=sembrado.case_id)

    await demo_reset.reset_now(composition.PURGADORES, now=HOY)

    async with session.unscoped_session() as sesion:
        fila = await session.fetch_one(
            sesion, "SELECT case_ref, cost_usd FROM spend_entry WHERE entry_id = 'entrada-de-ayer'"
        )
    assert fila is not None
    assert fila["case_ref"] is None
    assert fila["cost_usd"] is not None


async def test_el_caso_del_generador_sobrevive_y_el_del_visitante_no(
    sin_transporte: None,
) -> None:
    """Lo que se conserva aparece en `kept`, no en un silencio (AC5.6.4).

    Borrar los casos sembrados cada noche vaciaria el corpus de demostracion sin
    que nadie lo hubiera pedido, y la bandeja amaneceria vacia.
    """
    tenant_id = aseguradora()
    sembrado = await sembrar_datos_de_visitante(tenant_id)
    del_generador = await sembrar_caso_del_generador(tenant_id)

    corrida = await demo_reset.reset_now(composition.PURGADORES, now=HOY)

    fila = next(f for f in corrida.purgers if f.name == "case_record")
    assert (fila.deleted, fila.kept) == (1, 1)
    async with session.session_for(tenant_id) as sesion:
        vivos = await session.fetch_all(sesion, "SELECT case_id FROM case_record")
    assert [f["case_id"] for f in vivos] == [del_generador]
    assert sembrado.case_id not in {f["case_id"] for f in vivos}


async def test_la_corrida_queda_registrada_y_se_lee_de_vuelta(sin_transporte: None) -> None:
    """BR3.1 y TECH-U20.4: cada corrida deja su registro, y en la base.

    Se lee de vuelta por la misma consulta que usan las superficies publicas, que
    es la unica lectura que importa: una corrida guardada que esa consulta no
    encontrara dejaria la demo cerrada con el reinicio funcionando.
    """
    corrida = await demo_reset.reset_now(composition.PURGADORES, now=HOY)

    leidas = await repository.successful_runs()

    assert [c.reset_run_id for c in leidas] == [corrida.reset_run_id]
    guardada = leidas[0]
    assert guardada.outcome is ResetOutcome.SUCCEEDED
    assert [f.name for f in guardada.purgers] == [f.name for f in corrida.purgers]
    # Un minuto despues de que la corrida terminara: el reloj de la corrida es el
    # del proceso --lo que se fija en la prueba es el **corte**, no el reloj-- asi
    # que el instante con el que se compara sale de la propia corrida.
    assert accepts_new_cases(leidas, now=guardada.finished_at + timedelta(minutes=1)) is True


async def test_una_corrida_de_ensayo_cuenta_y_no_deja_registro(sin_transporte: None) -> None:
    """El ensayo no puede reiniciar el contador de 24 horas.

    Es la regla con la consecuencia mas fea de todas las de esta unidad: una
    corrida de ensayo guardada como exitosa diria que la demo esta limpia
    habiendo borrado exactamente nada.
    """
    tenant_id = aseguradora()
    sembrado = await sembrar_datos_de_visitante(tenant_id)

    corrida = await demo_reset.reset_now(composition.PURGADORES, now=HOY, dry_run=True)

    assert corrida.outcome is ResetOutcome.SUCCEEDED
    assert await repository.successful_runs() == ()
    assert accepts_new_cases(await repository.successful_runs(), now=HOY) is False
    for tabla in sembrado.tablas:
        assert await contar_en(tenant_id, tabla) > 0, f"el ensayo borro '{tabla}'"


async def test_un_purgador_caido_deja_la_corrida_parcial_con_su_registro(
    sin_transporte: None,
) -> None:
    """REL-U20.1 a REL-U20.3 contra la base: el fallo de uno no detiene a los demas.

    Y la consecuencia que importa: una corrida parcial **no** reinicia el
    contador de 24 horas, aunque ocho de los nueve purgadores hayan borrado.
    """
    tenant_id = aseguradora()
    sembrado = await sembrar_datos_de_visitante(tenant_id)
    registro = (*composition.PURGADORES, PurgadorCaido())

    corrida = await demo_reset.reset_now(registro, now=HOY)

    assert corrida.outcome is ResetOutcome.PARTIAL
    assert [f.name for f in corrida.failures] == ["purgador_caido"]
    caida = corrida.failures[0]
    assert caida.error_type == "TraceBackendNotPurgeableError"
    assert (caida.deleted, caida.kept) == (None, None)
    # Los otros ocho si borraron: detener a los demas dejaria sin borrar lo que
    # si se podia borrar.
    for tabla in sembrado.tablas:
        assert await contar_en(tenant_id, tabla) == 0
    # Y queda registrada, como `partial`, de modo que la consulta de las
    # superficies no la ve.
    assert await repository.successful_runs() == ()
    async with session.unscoped_session() as sesion:
        fila = await session.fetch_one(
            sesion,
            "SELECT outcome, error_type FROM reset_run JOIN reset_run_purger USING (reset_run_id) "
            "WHERE purger = 'purgador_caido'",
        )
    assert fila is not None
    assert (fila["outcome"], fila["error_type"]) == ("partial", "TraceBackendNotPurgeableError")


async def test_repetir_la_corrida_tras_un_parcial_no_empeora_el_estado(
    sin_transporte: None,
) -> None:
    """REL-U20.4: el reintento es volver a correr el registro completo.

    Los purgadores borran lo anterior al corte, asi que repetir no vuelve a
    borrar lo mismo ni rompe nada: la segunda corrida sale exitosa y es la que
    reinicia el contador.
    """
    tenant_id = aseguradora()
    await sembrar_datos_de_visitante(tenant_id)
    parcial = await demo_reset.reset_now((*composition.PURGADORES, PurgadorCaido()), now=HOY)
    assert parcial.outcome is ResetOutcome.PARTIAL

    segunda = await demo_reset.reset_now(composition.PURGADORES, now=HOY)

    assert segunda.outcome is ResetOutcome.SUCCEEDED
    exitosas = await repository.successful_runs()
    assert [c.reset_run_id for c in exitosas] == [segunda.reset_run_id]
    assert accepts_new_cases(exitosas, now=segunda.finished_at + timedelta(minutes=1)) is True


async def _foto_del_dinero() -> dict[str, object]:
    async with session.unscoped_session() as sesion:
        acumulado = await session.fetch_one(
            sesion, "SELECT billable_spent_usd AS total FROM budget_window"
        )
    return {
        "spend_entry": await contar_sin_aseguradora("spend_entry"),
        "budget_window": await contar_sin_aseguradora("budget_window"),
        "quota_counter": await contar_sin_aseguradora("quota_counter"),
        "acumulado": None if acumulado is None else acumulado["total"],
    }


async def _alcance_del_unico_contador() -> str:
    async with session.unscoped_session() as sesion:
        fila = await session.fetch_one(sesion, "SELECT scope FROM quota_counter")
    assert fila is not None
    return str(fila["scope"])
