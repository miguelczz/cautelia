"""El servidor MCP de los datos rigidos, llamado en proceso: sin cliente, sin base y sin red.

`MCPServer` deja listar las herramientas y llamarlas directamente, que es lo que hace un cliente
por el protocolo; aqui se hace sin el transporte. La base se sustituye en el limite del repositorio
(como en `policy_rag/facts/test_api.py`); el aislamiento por aseguradora lo prueba la base de verdad.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult

from untangle.copy_catalog import api as copy_api
from untangle.policy_mcp import server as policy_server
from untangle.tenancy import config as tenancy_config

from ..policy_rag.facts.conftest import CorpusEnMemoria, corpus_de_ejemplo, instalar_corpus

TENANT = "stonecroft"
POLIZA = "POL-99"


@pytest.fixture(autouse=True)
def _catalogo_y_aseguradoras() -> Iterator[None]:
    copy_api.reset()
    tenancy_config.install(tenancy_config.load())
    yield
    copy_api.reset()
    tenancy_config.reset()


@pytest.fixture
def corpus(monkeypatch: pytest.MonkeyPatch) -> CorpusEnMemoria:
    return instalar_corpus(monkeypatch, corpus_de_ejemplo())


@pytest.fixture
def servidor(corpus: CorpusEnMemoria) -> MCPServer:
    return policy_server.build_server(today=lambda: date(2026, 9, 1))


async def _llamar(servidor: MCPServer, herramienta: str, **argumentos: Any) -> Any:
    resultado = await servidor.call_tool(herramienta, argumentos)
    assert isinstance(resultado, CallToolResult)
    return resultado.structured_content


ARGUMENTOS_PERMITIDOS = {"tenant_id", "policy_number", "on", "language", "clause_id"}


async def test_expone_las_siete_herramientas_de_solo_lectura(servidor: MCPServer) -> None:
    herramientas = {t.name: t for t in await servidor.list_tools()}

    assert set(herramientas) == {
        "get_policy_summary",
        "get_limits",
        "get_deductibles",
        "get_insured_vehicles",
        "get_listed_drivers",
        "get_endorsements",
        "get_clause",
    }
    for herramienta in herramientas.values():
        assert herramienta.annotations is not None
        assert herramienta.annotations.read_only_hint is True
        assert herramienta.annotations.destructive_hint is False
        assert herramienta.description


async def test_toda_herramienta_pide_aseguradora_y_poliza_y_nada_de_casos(
    servidor: MCPServer,
) -> None:
    """Ningun dato de caso ni de visitante: no hay argumento que lo pida, y el paquete no importa
    `case_record` (lo comprueba el contrato de importacion)."""
    for herramienta in await servidor.list_tools():
        propiedades = set(herramienta.input_schema["properties"])
        assert {"tenant_id", "policy_number"} <= set(herramienta.input_schema["required"])
        assert propiedades <= ARGUMENTOS_PERMITIDOS, herramienta.name


async def test_el_resumen_calcula_la_vigencia_contra_la_fecha_pedida(servidor: MCPServer) -> None:
    hoy = await _llamar(servidor, "get_policy_summary", tenant_id=TENANT, policy_number=POLIZA)
    vencida = await _llamar(
        servidor, "get_policy_summary", tenant_id=TENANT, policy_number=POLIZA, on="2027-06-15"
    )

    assert hoy["status"] == "in_force"
    assert hoy["as_of"] == "2026-09-01"
    assert hoy["holder_name"] == "Daniela Castaño"
    assert hoy["period_end"] == "2027-06-14"
    assert vencida["status"] == "expired"


async def test_los_limites_traen_el_monto_en_pesos_y_el_texto_del_idioma(
    servidor: MCPServer,
) -> None:
    salida = await _llamar(
        servidor, "get_limits", tenant_id=TENANT, policy_number=POLIZA, language="en"
    )

    limites = {f["key"]: f for f in salida["result"]}
    assert len(limites) == 6
    por_persona = limites["a.bodily_injury_per_person"]["amount"]
    assert por_persona["units"] == 100000
    assert por_persona["pesos"] == 100_000_000
    assert por_persona["formatted"] == "COP\xa0100,000,000"


async def test_los_deducibles_salen_aparte_de_los_limites(servidor: MCPServer) -> None:
    salida = await _llamar(servidor, "get_deductibles", tenant_id=TENANT, policy_number=POLIZA)

    deducibles = {f["key"]: f["amount"]["pesos"] for f in salida["result"]}
    assert deducibles == {
        "d.collision_deductible": 1_500_000,
        "d.other_than_collision_deductible": 250_000,
    }


async def test_los_vehiculos_no_traen_placa_ni_vin(servidor: MCPServer) -> None:
    salida = await _llamar(servidor, "get_insured_vehicles", tenant_id=TENANT, policy_number=POLIZA)

    assert [v["description"] for v in salida["result"]] == ["Kia Picanto 2013", "Mazda 3 2020"]
    assert "JUH431" not in str(salida)
    assert "B0UMB1VW2WD449075" not in str(salida)


async def test_los_conductores_traen_al_titular_primero(servidor: MCPServer) -> None:
    salida = await _llamar(servidor, "get_listed_drivers", tenant_id=TENANT, policy_number=POLIZA)

    assert [(d["full_name"], d["is_holder"]) for d in salida["result"]] == [
        ("Daniela Castaño", True),
        ("Hernán Castaño", False),
    ]


async def test_los_endosos_traen_las_clausulas_que_cambian(servidor: MCPServer) -> None:
    salida = await _llamar(servidor, "get_endorsements", tenant_id=TENANT, policy_number=POLIZA)

    assert salida["result"][0]["form_id"] == "SA-PAP-2026-END-1"
    assert salida["result"][0]["clause_keys"] == ["B.INS"]


async def test_una_clausula_se_devuelve_solo_si_es_de_la_poliza(servidor: MCPServer) -> None:
    propia = await _llamar(
        servidor, "get_clause", tenant_id=TENANT, policy_number=POLIZA, clause_id="C-BASE"
    )

    assert propia["clause_id"] == "C-BASE"
    for ajena in ("C-AJENA", "C-SENUELO", "C-NO-EXISTE"):
        with pytest.raises(ToolError, match="no clause"):
            await _llamar(
                servidor, "get_clause", tenant_id=TENANT, policy_number=POLIZA, clause_id=ajena
            )


async def test_una_poliza_inexistente_y_la_de_otra_aseguradora_dan_el_mismo_error(
    servidor: MCPServer,
) -> None:
    mensajes = []
    for tenant, numero in (("sunmeadow", POLIZA), (TENANT, "POL-00")):
        with pytest.raises(ToolError) as error:
            await _llamar(servidor, "get_limits", tenant_id=tenant, policy_number=numero)
        mensajes.append(str(error.value).replace(tenant, "<t>").replace(numero, "<p>"))

    assert mensajes[0] == mensajes[1]
    assert "no policy" in mensajes[0]


async def test_una_aseguradora_desconocida_dice_cuales_hay(servidor: MCPServer) -> None:
    with pytest.raises(ToolError, match=r"unknown tenant_id 'nadie'; available:.*stonecroft"):
        await _llamar(servidor, "get_limits", tenant_id="nadie", policy_number=POLIZA)


async def test_las_lecturas_van_con_el_tenant_pedido(
    servidor: MCPServer, corpus: CorpusEnMemoria
) -> None:
    await _llamar(servidor, "get_insured_vehicles", tenant_id=TENANT, policy_number=POLIZA)

    assert corpus.read_for == [TENANT]


async def test_un_argumento_que_falta_o_no_es_valido_se_rechaza(servidor: MCPServer) -> None:
    with pytest.raises(ToolError):
        await servidor.call_tool("get_limits", {"tenant_id": TENANT})
    with pytest.raises(ToolError):
        await servidor.call_tool(
            "get_limits", {"tenant_id": TENANT, "policy_number": POLIZA, "language": "fr"}
        )


async def test_un_cliente_mcp_en_proceso_ve_las_herramientas_y_sus_errores(
    servidor: MCPServer,
) -> None:
    """La misma conversacion que tendria Claude Desktop, sin el proceso ni el transporte."""
    from mcp import Client

    async with Client(servidor) as cliente:
        listado = await cliente.list_tools()
        bien = await cliente.call_tool(
            "get_insured_vehicles", {"tenant_id": TENANT, "policy_number": POLIZA}
        )
        mal = await cliente.call_tool(
            "get_limits", {"tenant_id": TENANT, "policy_number": "POL-00"}
        )

    assert len(listado.tools) == 7
    assert bien.is_error is False
    assert bien.structured_content is not None
    assert mal.is_error is True
    assert "no policy 'POL-00'" in str(mal.content[0])
