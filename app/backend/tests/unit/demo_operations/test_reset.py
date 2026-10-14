"""La orquestacion del reinicio y la regla de las 24 horas (US5.15, REL-U20.1 a REL-U20.4).

Todo con purgadores dobles y un reloj inyectado: el camino del fallo se prueba
aqui porque contra una base de verdad habria que romperla a proposito.
"""

from __future__ import annotations

import io
import sys
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from untangle import observability
from untangle.base import Locale
from untangle.copy_catalog.api import load
from untangle.demo_operations.api import (
    RESET_NOTICE,
    RESET_WINDOW,
    SURFACES_CLOSED,
    EmptyRegistryError,
    PurgerRow,
    ResetOutcome,
    ResetRun,
    accepts_new_cases,
    last_successful_reset,
    run_reset,
)
from untangle.tenancy.models import PurgeResult

AHORA = datetime(2026, 9, 30, 4, 0, tzinfo=UTC)
CORTE = datetime(2026, 9, 29, 4, 0, tzinfo=UTC)


class Doble:
    """Un purgador doble que cumple el `Protocol`: anota su llamada y puede levantar."""

    def __init__(
        self,
        name: str,
        *,
        deleted: int = 1,
        kept: int = 0,
        error: Exception | None = None,
        log: list[str] | None = None,
    ) -> None:
        self.name = name
        self.tables = (f"{name}_table",)
        self.deleted = deleted
        self.kept = kept
        self.error = error
        self.log = log if log is not None else []
        self.llamadas: list[tuple[datetime, bool]] = []

    async def purge(self, *, older_than: datetime, dry_run: bool = False) -> PurgeResult:
        self.log.append(self.name)
        self.llamadas.append((older_than, dry_run))
        if self.error is not None:
            raise self.error
        return PurgeResult(name=self.name, deleted=self.deleted, kept=self.kept)


def _reloj_fijo(*instantes: datetime) -> Callable[[], datetime]:
    """Un reloj que entrega los instantes dados y falla si se le pide uno de mas."""
    pendientes: Iterator[datetime] = iter(instantes)
    return lambda: next(pendientes)


def _reloj_que_avanza(
    inicio: datetime, paso: timedelta = timedelta(seconds=2)
) -> Callable[[], datetime]:
    estado = {"ahora": inicio - paso}

    def reloj() -> datetime:
        estado["ahora"] += paso
        return estado["ahora"]

    return reloj


@pytest.fixture
def eventos() -> Iterator[io.StringIO]:
    destino = io.StringIO()
    observability.set_stream(destino)
    yield destino
    observability.set_stream(sys.stdout)


async def _correr(purgadores: Sequence[Doble], **extra: object) -> ResetRun:
    return await run_reset(
        purgadores,
        clock=_reloj_que_avanza(AHORA),
        older_than=CORTE,
        reset_run_id="run-1",
        **extra,  # type: ignore[arg-type]
    )


def _corrida(outcome: ResetOutcome, terminada: datetime, run_id: str = "r") -> ResetRun:
    """Una corrida ya hecha, con las filas que su resultado exige."""
    bien = PurgerRow(name="a", deleted=1, kept=0, duration_seconds=0.1)
    mal = PurgerRow(name="b", duration_seconds=0.1, error_type="TimeoutError")
    filas = {
        ResetOutcome.SUCCEEDED: (bien,),
        ResetOutcome.FAILED: (mal,),
        ResetOutcome.PARTIAL: (bien, mal),
    }[outcome]
    return ResetRun(
        reset_run_id=run_id,
        started_at=terminada - timedelta(minutes=1),
        finished_at=terminada,
        outcome=outcome,
        purgers=filas,
    )


# --- La orquestacion ---------------------------------------------------------


async def test_llama_a_los_purgadores_en_el_orden_del_registro() -> None:
    log: list[str] = []
    purgadores = [Doble(n, log=log) for n in ("z", "a", "m")]

    await _correr(purgadores)

    assert log == ["z", "a", "m"]


async def test_cada_fila_dice_que_borro_y_que_conservo_su_purgador() -> None:
    corrida = await _correr([Doble("a", deleted=7, kept=2), Doble("b", deleted=0, kept=5)])

    assert corrida.outcome is ResetOutcome.SUCCEEDED
    assert [(f.name, f.deleted, f.kept) for f in corrida.purgers] == [("a", 7, 2), ("b", 0, 5)]
    assert corrida.purgers[0].tables == ("a_table",)
    assert corrida.failures == ()


async def test_pasa_el_corte_y_el_ensayo_a_cada_purgador() -> None:
    purgador = Doble("a")

    await _correr([purgador], dry_run=True)

    assert purgador.llamadas == [(CORTE, True)]


async def test_un_purgador_que_levanta_queda_en_el_registro_y_no_detiene_a_los_demas() -> None:
    """REL-U20.1: la corrida termina, el registro existe y dice cual fallo."""
    log: list[str] = []
    purgadores = [
        Doble("a", log=log),
        Doble("b", log=log, error=TimeoutError("la base no respondio")),
        Doble("c", log=log),
    ]

    corrida = await _correr(purgadores)

    assert log == ["a", "b", "c"]
    assert [f.name for f in corrida.failures] == ["b"]
    assert corrida.failures[0].error_type == "TimeoutError"
    assert corrida.purgers[2].deleted == 1


async def test_la_fila_de_un_fallo_no_inventa_cuanto_borro() -> None:
    corrida = await _correr([Doble("a", error=RuntimeError("x")), Doble("b")])

    fila = corrida.purgers[0]
    assert fila.deleted is None
    assert fila.kept is None


async def test_la_fila_no_guarda_el_mensaje_del_error() -> None:
    """Un mensaje de error de base puede llevar un valor, y la fila sale en logs."""
    corrida = await _correr(
        [Doble("a", error=RuntimeError("dato-de-un-visitante-123")), Doble("b")]
    )

    assert "dato-de-un-visitante-123" not in corrida.model_dump_json()


async def test_siete_que_borran_y_dos_que_fallan_es_partial() -> None:
    """REL-U20.3: ni un exito ni un fallo completo."""
    purgadores = [Doble(f"p{i}") for i in range(7)]
    purgadores += [Doble("p7", error=OSError()), Doble("p8", error=ValueError())]

    corrida = await _correr(purgadores)

    assert corrida.outcome is ResetOutcome.PARTIAL
    assert [f.name for f in corrida.failures] == ["p7", "p8"]


async def test_todos_fallan_es_failed() -> None:
    corrida = await _correr([Doble("a", error=OSError()), Doble("b", error=OSError())])

    assert corrida.outcome is ResetOutcome.FAILED


async def test_un_fallo_sale_como_alerta_con_el_identificador_de_la_corrida(
    eventos: io.StringIO,
) -> None:
    """REL-U20.2."""
    await _correr([Doble("a"), Doble("b", error=TimeoutError())])

    salida = eventos.getvalue()
    assert '"event": "demo_operations.reset_alert"' in salida
    assert '"reset_run_id": "run-1"' in salida
    assert '"outcome": "partial"' in salida
    assert '"purger": "b"' in salida


async def test_una_corrida_limpia_no_levanta_alerta(eventos: io.StringIO) -> None:
    await _correr([Doble("a"), Doble("b")])

    assert eventos.getvalue() == ""


async def test_un_registro_vacio_no_es_una_corrida_exitosa() -> None:
    with pytest.raises(EmptyRegistryError):
        await _correr([])


async def test_el_reintento_tras_un_parcial_no_empeora_el_estado() -> None:
    """REL-U20.4: repetir la corrida completa tras un parcial termina limpio.

    El doble modela lo que hace un purgador real con un corte: lo anterior ya
    borrado no vuelve a contarse, y lo que fallo se borra ahora.
    """
    pendiente = {"a": 4, "b": 6}

    class Con(Doble):
        falla = True

        async def purge(self, *, older_than: datetime, dry_run: bool = False) -> PurgeResult:
            if self.name == "b" and Con.falla:
                raise TimeoutError
            self.deleted = pendiente[self.name]
            pendiente[self.name] = 0
            return PurgeResult(name=self.name, deleted=self.deleted, kept=0)

    purgadores = [Con("a"), Con("b")]

    primera = await _correr(purgadores)
    Con.falla = False
    segunda = await _correr(purgadores)

    assert primera.outcome is ResetOutcome.PARTIAL
    assert segunda.outcome is ResetOutcome.SUCCEEDED
    assert [f.deleted for f in segunda.purgers] == [0, 6]
    assert pendiente == {"a": 0, "b": 0}


async def test_los_instantes_salen_del_reloj_inyectado_y_no_del_del_proceso() -> None:
    """BR2.4: con un reloj fijo en el 2000, el registro dice el 2000."""
    instantes = [datetime(2000, 1, 1, 0, 0, s, tzinfo=UTC) for s in (0, 1, 5, 6, 9)]
    # empieza, (inicio, fin) de a, (inicio, fin) de b, termina... en ese orden.
    reloj = _reloj_fijo(
        instantes[0], instantes[1], instantes[2], instantes[3], instantes[4], instantes[4]
    )

    corrida = await run_reset(
        [Doble("a"), Doble("b")], clock=reloj, older_than=CORTE, reset_run_id="r"
    )

    assert corrida.started_at == instantes[0]
    assert corrida.finished_at.year == 2000
    assert [f.duration_seconds for f in corrida.purgers] == [4.0, 3.0]


# --- El registro: estados imposibles ------------------------------------------


def test_una_corrida_no_puede_declararse_exitosa_con_un_purgador_caido() -> None:
    mal = PurgerRow(name="b", duration_seconds=0.1, error_type="OSError")
    bien = PurgerRow(name="a", deleted=1, kept=0, duration_seconds=0.1)

    for declarado in (ResetOutcome.SUCCEEDED, ResetOutcome.FAILED):
        with pytest.raises(ValidationError, match="sus filas dicen 'partial'"):
            ResetRun(
                reset_run_id="r",
                started_at=AHORA,
                finished_at=AHORA,
                outcome=declarado,
                purgers=(bien, mal),
            )


def test_una_corrida_sin_purgadores_no_existe() -> None:
    with pytest.raises(ValidationError):
        ResetRun(
            reset_run_id="r",
            started_at=AHORA,
            finished_at=AHORA,
            outcome=ResetOutcome.SUCCEEDED,
            purgers=(),
        )


def test_un_purgador_aparece_una_sola_vez() -> None:
    fila = PurgerRow(name="a", deleted=1, kept=0, duration_seconds=0)
    with pytest.raises(ValidationError, match="repite los purgadores"):
        ResetRun(
            reset_run_id="r",
            started_at=AHORA,
            finished_at=AHORA,
            outcome=ResetOutcome.SUCCEEDED,
            purgers=(fila, fila),
        )


def test_los_relojes_de_una_corrida_traen_zona_y_van_en_orden() -> None:
    fila = PurgerRow(name="a", deleted=1, kept=0, duration_seconds=0)
    base = {"reset_run_id": "r", "outcome": ResetOutcome.SUCCEEDED, "purgers": (fila,)}

    with pytest.raises(ValidationError, match="zona horaria"):
        ResetRun(started_at=datetime(2026, 9, 30), finished_at=AHORA, **base)  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="antes de empezar"):
        ResetRun(started_at=AHORA, finished_at=AHORA - timedelta(seconds=1), **base)  # type: ignore[arg-type]


def test_una_fila_distingue_no_se_cuanto_borro_de_borro_cero() -> None:
    with pytest.raises(ValidationError, match="no declara cuanto borro"):
        PurgerRow(name="a", duration_seconds=0)
    with pytest.raises(ValidationError, match="un numero inventado"):
        PurgerRow(name="a", deleted=0, kept=0, duration_seconds=0, error_type="OSError")


# --- La regla de las 24 horas ---------------------------------------------------


def test_la_ventana_es_de_24_horas() -> None:
    assert timedelta(hours=24) == RESET_WINDOW


def test_con_un_reinicio_exitoso_reciente_acepta_casos_nuevos() -> None:
    exito = _corrida(ResetOutcome.SUCCEEDED, AHORA - timedelta(hours=10))

    assert accepts_new_cases([exito], now=AHORA)


def test_el_limite_es_exacto_a_las_24_horas() -> None:
    exito = _corrida(ResetOutcome.SUCCEEDED, AHORA - timedelta(hours=24) + timedelta(seconds=1))
    assert accepts_new_cases([exito], now=AHORA)

    exito = _corrida(ResetOutcome.SUCCEEDED, AHORA - timedelta(hours=24))
    assert not accepts_new_cases([exito], now=AHORA)


def test_tres_intentos_fallidos_seguidos_no_reinician_el_contador() -> None:
    """BR3.2: el reloj cuenta desde el ultimo exito, no desde el ultimo intento."""
    historial = [
        _corrida(ResetOutcome.SUCCEEDED, AHORA - timedelta(hours=25), "exito"),
        _corrida(ResetOutcome.FAILED, AHORA - timedelta(hours=3), "i1"),
        _corrida(ResetOutcome.FAILED, AHORA - timedelta(hours=2), "i2"),
        _corrida(ResetOutcome.FAILED, AHORA - timedelta(hours=1), "i3"),
    ]

    assert not accepts_new_cases(historial, now=AHORA)


def test_un_parcial_reciente_no_reinicia_el_contador() -> None:
    """Quedan datos sin borrar: contarlo como exito reabre la demo con retencion sin acotar."""
    historial = [
        _corrida(ResetOutcome.SUCCEEDED, AHORA - timedelta(hours=25), "exito"),
        _corrida(ResetOutcome.PARTIAL, AHORA - timedelta(minutes=5), "parcial"),
    ]

    assert not accepts_new_cases(historial, now=AHORA)


def test_el_orden_de_la_lista_no_decide_cual_es_el_ultimo_exito() -> None:
    viejo = _corrida(ResetOutcome.SUCCEEDED, AHORA - timedelta(hours=30), "viejo")
    nuevo = _corrida(ResetOutcome.SUCCEEDED, AHORA - timedelta(hours=2), "nuevo")

    assert last_successful_reset([nuevo, viejo]) is nuevo
    assert accepts_new_cases([nuevo, viejo], now=AHORA)
    assert accepts_new_cases([viejo, nuevo], now=AHORA)


def test_sin_ningun_reinicio_exitoso_conocido_cierra() -> None:
    assert not accepts_new_cases([], now=AHORA)
    assert not accepts_new_cases([_corrida(ResetOutcome.FAILED, AHORA)], now=AHORA)


def test_un_exito_en_el_futuro_no_mantiene_la_demo_abierta() -> None:
    """Un dato corrupto hacia adelante la dejaria abierta para siempre."""
    futuro = _corrida(ResetOutcome.SUCCEEDED, AHORA + timedelta(days=30))

    assert not accepts_new_cases([futuro], now=AHORA)


def test_el_instante_sin_zona_se_rechaza() -> None:
    with pytest.raises(ValueError, match="zona horaria"):
        accepts_new_cases([], now=datetime(2026, 9, 30))


def test_la_ventana_se_puede_pasar_como_argumento() -> None:
    exito = _corrida(ResetOutcome.SUCCEEDED, AHORA - timedelta(hours=2))

    assert not accepts_new_cases([exito], now=AHORA, window=timedelta(hours=1))


# --- El catalogo -----------------------------------------------------------------


@pytest.mark.parametrize("locale", ["es", "en"])
@pytest.mark.parametrize("clave", [RESET_NOTICE, SURFACES_CLOSED])
def test_las_dos_frases_existen_en_los_dos_idiomas(clave: str, locale: Locale) -> None:
    catalogo = load()

    frase = catalogo.t(clave, locale=locale)  # type: ignore[arg-type]

    assert frase != clave
    assert frase.strip()
