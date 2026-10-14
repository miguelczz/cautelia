"""El noveno purgador: lo que ya salio hacia las trazas (BR2.1 de U20).

Sin base: lo que este purgador barre no esta en la base, y eso es exactamente por
lo que hacia falta nombrarlo aparte. La comprobacion que recorre el catalogo
buscando la marca de dato de visitante no puede verlo, asi que un registro sin el
pasaba en verde.

Las tres ramas se prueban las tres, porque la que importa no es la que borra: es
la que **levanta**. Un purgador que declarara limpio un backend al que no sabe
llegar convertiria el reinicio en una promesa sin respaldo.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from untangle.settings import Settings
from untangle.telemetry.traces import export
from untangle.telemetry.traces.purge import (
    TRACES_BACKEND_PURGER,
    TraceBackendNotPurgeableError,
)
from untangle.tenancy.models import VisitorDataPurger

CORTE = datetime(2026, 10, 2, 6, 0, tzinfo=UTC)
ANTES = datetime(2026, 10, 2, 3, 30, tzinfo=UTC)
DESPUES = datetime(2026, 10, 2, 7, 15, tzinfo=UTC)


def _ajustes(*, traces_endpoint: str | None = None) -> Settings:
    """Con el destino dicho en los dos casos: si la variable estuviera puesta en
    la maquina de quien corre la suite, estas pruebas cambiarian de rama sin que
    nadie lo pidiera."""
    return Settings(env="ci", traces_endpoint=traces_endpoint)


def _lote(*instantes: datetime) -> str:
    """Un lote OTLP/JSON con un tramo por instante, como lo escribe el transporte."""
    return json.dumps(
        {
            "resourceSpans": [
                {
                    "resource": {"attributes": []},
                    "scopeSpans": [
                        {
                            "scope": {"name": "untangle.telemetry.traces"},
                            "spans": [
                                {
                                    "traceId": f"tr{indice}",
                                    "spanId": f"sp{indice}",
                                    "name": "chat.turn",
                                    "startTimeUnixNano": int(momento.timestamp() * 1_000_000_000),
                                    "endTimeUnixNano": int(momento.timestamp() * 1_000_000_000),
                                    "attributes": [],
                                }
                                for indice, momento in enumerate(instantes)
                            ],
                        }
                    ],
                }
            ]
        }
    )


def _archivo(tmp_path: Path, *lineas: str) -> Path:
    destino = tmp_path / "traces.otlp.jsonl"
    destino.write_text("".join(f"{linea}\n" for linea in lineas), encoding="utf-8")
    return destino


def _con_archivo(destino: Path) -> VisitorDataPurger:
    """El purgador apuntando a un archivo concreto, sin tocar el entorno."""
    export.install_transport(export.FileTransport(destino))
    return dataclasses.replace(TRACES_BACKEND_PURGER, settings_factory=_ajustes)


@pytest.fixture(autouse=True)
def _sin_transporte_instalado() -> object:
    """Cada prueba empieza y termina sin transporte instalado.

    Sin esto, la que instala uno se lo deja puesto a la siguiente y la suite deja
    de poder correr en cualquier orden.
    """
    export.install_transport(None)
    yield None
    export.install_transport(None)


async def test_el_archivo_de_la_corrida_pierde_los_lotes_anteriores_al_corte(
    tmp_path: Path,
) -> None:
    """BR2.1: lo que un visitante dejo escrito no sobrevive a la noche."""
    destino = _archivo(tmp_path, _lote(ANTES), _lote(ANTES, ANTES), _lote(DESPUES))
    purgador = _con_archivo(destino)

    resultado = await purgador.purge(older_than=CORTE)

    assert resultado.deleted == 3
    assert resultado.kept == 1
    assert destino.read_text(encoding="utf-8").splitlines() == [_lote(DESPUES)]


async def test_el_ensayo_cuenta_y_no_toca_el_archivo(tmp_path: Path) -> None:
    """El ensayo tiene que poder correrse sin consecuencias: si borrara, nadie lo usaria."""
    destino = _archivo(tmp_path, _lote(ANTES), _lote(DESPUES))
    purgador = _con_archivo(destino)
    antes = destino.read_text(encoding="utf-8")

    resultado = await purgador.purge(older_than=CORTE, dry_run=True)

    assert resultado.deleted == 1
    assert destino.read_text(encoding="utf-8") == antes


async def test_un_lote_a_medio_escribir_se_borra_en_vez_de_tumbar_la_corrida(
    tmp_path: Path,
) -> None:
    """Una linea que no es JSON --el proceso se cayo anexando-- no se conserva.

    De las dos direcciones posibles, esta es la unica que no deja dato de
    visitante detras por no haber sabido leerlo.
    """
    destino = _archivo(tmp_path, '{"resourceSpans": [{"scopeSpans', _lote(DESPUES))
    purgador = _con_archivo(destino)

    resultado = await purgador.purge(older_than=CORTE)

    assert resultado.deleted == 1
    assert destino.read_text(encoding="utf-8").splitlines() == [_lote(DESPUES)]


async def test_un_tramo_sin_instante_legible_tampoco_se_conserva(tmp_path: Path) -> None:
    """Sin reloj no se puede afirmar que es posterior al corte, asi que se va."""
    sin_reloj = json.dumps(
        {
            "resourceSpans": [
                {
                    "scopeSpans": [
                        {"spans": [{"traceId": "tr", "startTimeUnixNano": "no-es-un-numero"}]}
                    ]
                }
            ]
        }
    )
    destino = _archivo(tmp_path, sin_reloj)
    purgador = _con_archivo(destino)

    resultado = await purgador.purge(older_than=CORTE)

    assert resultado.deleted == 1
    assert not destino.exists()


async def test_un_archivo_que_no_existe_no_es_un_fallo(tmp_path: Path) -> None:
    """El reinicio corre tambien la noche en la que nadie escribio una traza."""
    purgador = _con_archivo(tmp_path / "no-esta.jsonl")

    resultado = await purgador.purge(older_than=CORTE)

    assert (resultado.deleted, resultado.kept) == (0, 0)


async def test_con_destino_declarado_y_sin_exportador_no_salio_nada() -> None:
    """Declarar ceros es distinto de no haber mirado.

    `UnavailableTransport` levanta en cada envio, asi que ningun tramo llego nunca
    al backend: el cero es comprobable y no una suposicion.
    """
    purgador = dataclasses.replace(
        TRACES_BACKEND_PURGER,
        settings_factory=lambda: _ajustes(traces_endpoint="http://localhost:3001"),
    )

    resultado = await purgador.purge(older_than=CORTE)

    assert (resultado.deleted, resultado.kept) == (0, 0)


async def test_un_transporte_que_no_sabe_barrerse_levanta() -> None:
    """La rama que importa. La corrida sale parcial, con su alerta, y la retencion
    del backend queda declarada como lo que es: sin acotar."""

    class Propio:
        def send(self, payload: str) -> None: ...

    export.install_transport(Propio())
    purgador = dataclasses.replace(TRACES_BACKEND_PURGER, settings_factory=_ajustes)

    with pytest.raises(TraceBackendNotPurgeableError, match="Propio"):
        await purgador.purge(older_than=CORTE)


def test_el_purgador_no_declara_ninguna_tabla() -> None:
    """Y es a proposito: lo que barre no esta en la base.

    Las cinco tablas de esta unidad ya tienen dueno --`trace_summary` cuelga del
    caso en cascada-- y declarar una aqui seria un segundo dueno de un borrado
    que ya ocurre.
    """
    assert tuple(TRACES_BACKEND_PURGER.tables) == ()
    assert TRACES_BACKEND_PURGER.name == "traces_backend"
