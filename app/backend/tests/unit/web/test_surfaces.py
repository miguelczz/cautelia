"""El registro de superficies y la capacidad `surfaces` de la raiz (BR5.2, BR5.3, F8).

Cubre REL-U6.4 (una superficie sin sonda impide arrancar y nombra el modulo),
SCALE-U6.1 (montar una superficie no toca U6) y SCALE-U6.3 (las sondas corren
en paralelo). Sin red, sin base y sin credenciales.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from fastapi import FastAPI

from untangle.server import composition, surfaces
from untangle.surface_spec import ProbeCheck, SurfaceId, SurfaceProbe, SurfaceSpec

from .eventos import Eventos

CON_SONDA = "tests.unit.web.superficies_con_sonda"
SIN_SONDA = "tests.unit.web.superficie_sin_sonda"
REPETIDA = "tests.unit.web.superficie_repetida"


async def _responde() -> None:
    return None


async def _lanza() -> None:
    msg = "la superficie no responde"
    raise RuntimeError(msg)


def _tarda(segundos: float) -> ProbeCheck:
    async def check() -> None:
        await asyncio.sleep(segundos)

    return check


def _superficie(
    surface_id: SurfaceId,
    *,
    public: bool = True,
    check: ProbeCheck = _responde,
    timeout_ms: int = 100,
) -> SurfaceSpec:
    return SurfaceSpec(
        surface_id=surface_id,
        owning_unit="prueba",
        public=public,
        per_tenant=True,
        probe=SurfaceProbe(check=check, timeout_ms=timeout_ms),
    )


# --- La declaracion ------------------------------------------------------------


@pytest.mark.parametrize("timeout_ms", [0, 501])
def test_una_sonda_declara_entre_uno_y_quinientos_milisegundos(timeout_ms: int) -> None:
    """Con medio segundo por sonda, la salud cabe en su segundo (C-02)."""
    with pytest.raises(ValueError, match="entre 1 y 500"):
        SurfaceProbe(check=_responde, timeout_ms=timeout_ms)


def test_la_raiz_monta_un_modulo_con_sonda_sin_tocar_u6() -> None:
    """SCALE-U6.1: el modulo de prueba expone `surfaces()` y ya esta montado."""
    registro = composition.mount_modules(
        FastAPI(),
        (composition.ModuleSpec(module=CON_SONDA, provides=frozenset({"surfaces"})),),
    )

    assert registro.mounted() == (SurfaceId.CHAT, SurfaceId.INBOX)
    # La bandeja con credencial se sondea pero no se ensena en el inicio.
    assert registro.public_mounted() == (SurfaceId.CHAT,)


def test_una_superficie_sin_sonda_impide_arrancar_nombrando_el_modulo() -> None:
    """REL-U6.4: el fallo es al arrancar y dice que modulo lo causo."""
    with pytest.raises(composition.ModuleContractError) as fallo:
        composition.mount_modules(
            FastAPI(),
            (composition.ModuleSpec(module=SIN_SONDA, provides=frozenset({"surfaces"})),),
        )

    mensaje = str(fallo.value)
    assert SIN_SONDA in mensaje
    assert "sin sonda" in mensaje


def test_dos_modulos_que_montan_la_misma_superficie_impiden_arrancar() -> None:
    with pytest.raises(composition.ModuleContractError) as fallo:
        composition.mount_modules(
            FastAPI(),
            (
                composition.ModuleSpec(module=CON_SONDA, provides=frozenset({"surfaces"})),
                composition.ModuleSpec(module=REPETIDA, provides=frozenset({"surfaces"})),
            ),
        )

    mensaje = str(fallo.value)
    assert CON_SONDA in mensaje
    assert REPETIDA in mensaje


def test_lo_que_no_es_un_surfacespec_se_rechaza() -> None:
    with pytest.raises(surfaces.SurfaceDeclarationError, match="no un SurfaceSpec"):
        surfaces.validate_declared(["chat"])
    with pytest.raises(surfaces.SurfaceDeclarationError, match="secuencia"):
        surfaces.validate_declared("chat")


def test_el_registro_ordena_por_la_lista_cerrada_y_filtra_las_publicas() -> None:
    registro = surfaces.SurfaceRegistry(
        [
            _superficie(SurfaceId.SPEND_PANEL),
            _superficie(SurfaceId.INBOX, public=False),
            _superficie(SurfaceId.CHAT),
        ]
    )

    assert registro.mounted() == (SurfaceId.CHAT, SurfaceId.INBOX, SurfaceId.SPEND_PANEL)
    assert registro.public_mounted() == (SurfaceId.CHAT, SurfaceId.SPEND_PANEL)


# --- Las sondas ----------------------------------------------------------------


async def test_una_sonda_que_lanza_o_se_pasa_de_tiempo_marca_su_superficie_caida(
    eventos: Eventos,
) -> None:
    """BR5.3: nunca se escribe `ok` por no saber, y la caida deja su evento."""
    registro = surfaces.SurfaceRegistry(
        [
            _superficie(SurfaceId.CHAT),
            _superficie(SurfaceId.VOICE_CONSOLE, check=_lanza),
            _superficie(SurfaceId.COMPARISON, check=_tarda(1.0), timeout_ms=50),
        ]
    )

    resultados = await registro.probe_all()

    assert resultados[SurfaceId.CHAT].status == "ok"
    assert resultados[SurfaceId.VOICE_CONSOLE].status == "down"
    assert resultados[SurfaceId.COMPARISON].status == "down"
    # La lenta se corta en su tiempo, no cuando termina.
    assert resultados[SurfaceId.COMPARISON].duration_ms < 500
    caidas = {e["surface"]: e for e in eventos() if e["event"] == "server.surface_down"}
    assert caidas["voice_console"]["reason"] == "error"
    assert caidas["voice_console"]["error_type"] == "RuntimeError"
    assert caidas["comparison"]["reason"] == "timeout"
    assert "chat" not in caidas


async def test_las_sondas_corren_en_paralelo() -> None:
    """SCALE-U6.3: la salud tarda lo que la sonda mas lenta, no la suma."""
    registro = surfaces.SurfaceRegistry(
        [
            _superficie(SurfaceId.CHAT, check=_tarda(0.2), timeout_ms=400),
            _superficie(SurfaceId.INBOX, check=_tarda(0.2), timeout_ms=400),
            _superficie(SurfaceId.CASE_LINK, check=_tarda(0.2), timeout_ms=400),
        ]
    )

    inicio = time.perf_counter()
    resultados = await registro.probe_all()
    transcurrido = time.perf_counter() - inicio

    assert {r.status for r in resultados.values()} == {"ok"}
    # En serie serian 0,6 s; en paralelo, algo mas de 0,2 s.
    assert transcurrido < 0.45


async def test_sin_superficies_montadas_no_hay_resultados_inventados() -> None:
    assert await surfaces.SurfaceRegistry().probe_all() == {}
