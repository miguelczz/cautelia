"""Dar de alta una aseguradora con una carpeta y un comando (US5.1, BR1.1 a BR1.4).

La bateria de humo de esta unidad corre contra **una cuarta aseguradora que no se
publica**: su carpeta vive en las fixtures, ninguna corrida del aplicativo la
carga, y aqui se le monta encima de las tres de verdad para que el aislamiento
tenga dos lados que comparar.

Es la unica prueba del proyecto que responde la pregunta de AC5.1.1 de verdad:
*anadir una aseguradora es anadir una carpeta?* Las demas usan las tres que ya
estan, que podrian funcionar por estar nombradas en algun sitio. Esta no: su
identificador no aparece en ningun archivo de codigo --`tenancy:literals` lo
comprueba en cada entrega-- y aun asi abre conversacion, aparece en su bandeja y
no ve los casos de nadie mas.

**La ingesta entra como doble**, y es la unica pieza que no corre de verdad aqui:
llamar al proveedor de embeddings cuesta dinero y la regla del proyecto es que
una prueba no gaste el presupuesto que protege. Lo que si se comprueba es lo que
BR1.3 pide: que el aprovisionamiento **la invoque** en vez de escribir la suya, y
con esa aseguradora.
"""

from __future__ import annotations

import shutil
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from untangle import paths
from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.chat import session as chat
from untangle.inbox import queue
from untangle.server import corpus_ingest, tenant_provision
from untangle.tenancy import config as tenancy_config
from untangle.tenancy import session
from untangle.tenancy.models import Role

from .conftest import AYER, contar_en

pytestmark = pytest.mark.usefixtures("base_de_u20")

CUARTA = "testhaven"
AHORA = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


def _fixture() -> Path:
    """La carpeta de la cuarta aseguradora, en las fixtures de las pruebas.

    No en `app/config/tenants/` --ahi estaria publicada-- y no en
    `app/data/fixtures/`, que es el andamiaje de datos del generador.
    """
    return Path(__file__).parents[2] / "fixtures" / "cuarta-aseguradora"


class _Ingesta:
    """Un doble de la ingesta que apunta a quien la llamo y con que.

    **Asincrono, y eso es el punto.** Antes este doble era sincrono porque imitaba
    la firma de `corpus_ingest.main` --recibe texto, devuelve numero-- y la
    docstring decia que esa era "la forma exacta". Lo era en el tipo y no en la
    naturaleza: `main` arranca un bucle de eventos, y `provision` lo llamaba desde
    dentro de uno. El doble pasaba y el aprovisionamiento de verdad reventaba con
    `RuntimeError` la primera vez que se corrio contra una base real.

    La leccion, para el catalogo: un doble que copia la firma pero no la
    restriccion no comprueba la frontera, la tapa.
    """

    def __init__(self, codigo: int = 0) -> None:
        self.codigo = codigo
        self.llamadas: list[str] = []

    async def __call__(self, tenant_id: str) -> int:
        self.llamadas.append(tenant_id)
        return self.codigo


@pytest.fixture
async def cuatro_aseguradoras(tmp_path: Path) -> AsyncIterator[Path]:
    """Las tres de verdad mas la cuarta de las fixtures, cargadas en el proceso.

    Se copian a un directorio temporal en vez de anadir la cuarta a
    `app/config/tenants/`: ahi estaria publicada, el inicio del sitio la
    anunciaria y el reinicio nocturno la barreria como a las otras.
    """
    raiz = tmp_path / "tenants"
    shutil.copytree(paths.tenants_dir(), raiz)
    shutil.copytree(_fixture() / "tenants" / CUARTA, raiz / CUARTA)
    tenancy_config.install(tenancy_config.load(raiz))
    yield raiz
    # Lo que esta aseguradora dejo en la base se borra **aqui**: la limpieza de
    # la carpeta recorre las aseguradoras cargadas, y cuando ella corre esta
    # cuarta ya no esta en la configuracion.
    async with session.session_for(CUARTA) as sesion:
        await session.execute_sql(sesion, "DELETE FROM case_record")
    tenancy_config.reset()


async def test_el_paso_de_ingesta_por_omision_se_puede_esperar_desde_el_bucle(
    cuatro_aseguradoras: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El defecto que ningun doble veia: `provision` corre dentro de un bucle de
    eventos, y su ingesta **por omision** arrancaba otro con `asyncio.run`. Las
    pruebas pasaban porque todas pasaban un doble; la primera corrida real contra
    una base contesto `RuntimeError: asyncio.run() cannot be called from a running
    event loop`.

    Por eso esta prueba **no pasa `ingest=`**: recorre el paso de verdad y sustituye
    solo el otro lado, el nucleo de la ingesta, que es lo que cuesta dinero. Si
    alguien devuelve el paso a su forma sincrona, esto se cae aqui y no en un
    despliegue.
    """
    pedidas: list[list[str]] = []

    async def nucleo(argv: list[str] | None = None) -> int:
        pedidas.append(list(argv or []))
        return 0

    monkeypatch.setattr(corpus_ingest, "run", nucleo)

    resultado = await tenant_provision.provision(
        CUARTA,
        cipher=crypto.active(),
        now=AHORA,
        roots=_raices(cuatro_aseguradoras),
    )

    assert pedidas == [["--tenant", CUARTA]]
    assert resultado.created == 1


async def test_da_de_alta_la_cuarta_aseguradora_invocando_la_ingesta_que_ya_existe(
    cuatro_aseguradoras: Path,
) -> None:
    """BR1.3 y el camino completo: validar, ingerir y sembrar, en ese orden."""
    ingesta = _Ingesta()

    resultado = await tenant_provision.provision(
        CUARTA,
        cipher=crypto.active(),
        now=AHORA,
        ingest=ingesta,
        roots=_raices(cuatro_aseguradoras),
    )

    assert ingesta.llamadas == [CUARTA]
    assert [caso.case_key for caso in resultado.seeded] == ["SEED/testhaven/es/derived"]
    assert resultado.created == 1
    assert resultado.staff == ("tess-haven",)
    assert await contar_en(CUARTA, "case_record") == 1


async def test_correrlo_dos_veces_deja_el_mismo_estado(cuatro_aseguradoras: Path) -> None:
    """BR1.2: la segunda corrida no duplica nada y lo dice.

    `created` en cero es la mitad que importa: un comando que dijera "sembrado"
    las dos veces no se podria distinguir de uno que duplica.
    """
    await _aprovisionar(cuatro_aseguradoras)

    segunda = await _aprovisionar(cuatro_aseguradoras)

    assert segunda.created == 0
    assert await contar_en(CUARTA, "case_record") == 1


async def test_una_carpeta_incompleta_no_crea_nada_y_nombra_cada_falta(
    cuatro_aseguradoras: Path,
) -> None:
    """BR1.1: todas las faltas, con archivo y campo, y la ingesta sin llamar.

    Se le quitan **dos** cosas a la vez a proposito: una validacion que se
    detuviera en la primera pasaria esta prueba si solo faltara una.
    """
    (cuatro_aseguradoras / CUARTA / "rules" / "triage.yaml").unlink()
    _sin_personas(cuatro_aseguradoras / CUARTA / "tenant.yaml")
    ingesta = _Ingesta()

    with pytest.raises(tenant_provision.FolderIncompleteError) as fallo:
        await tenant_provision.provision(
            CUARTA,
            cipher=crypto.active(),
            now=AHORA,
            ingest=ingesta,
            roots=_raices(cuatro_aseguradoras),
        )

    faltas = fallo.value.report.missing
    assert {falta.field for falta in faltas} >= {"staff", "(archivo)"}
    assert all(falta.file for falta in faltas)
    assert ingesta.llamadas == []
    assert await contar_en(CUARTA, "case_record") == 0


async def test_si_la_ingesta_falla_no_se_siembra_ningun_caso(
    cuatro_aseguradoras: Path,
) -> None:
    """Media aseguradona no existe: con el corpus sin indexar, la bandeja se queda vacia."""
    ingesta = _Ingesta(codigo=2)

    with pytest.raises(tenant_provision.IngestFailedError, match="devolvio 2"):
        await tenant_provision.provision(
            CUARTA,
            cipher=crypto.active(),
            now=AHORA,
            ingest=ingesta,
            roots=_raices(cuatro_aseguradoras),
        )

    assert await contar_en(CUARTA, "case_record") == 0


async def test_una_aseguradora_sin_casos_sembrados_no_se_da_de_alta(
    cuatro_aseguradoras: Path, tmp_path: Path
) -> None:
    """Y se comprueba **antes** de ingerir, porque ingerir ya es crear."""
    datos = tmp_path / "datos"
    shutil.copytree(_fixture() / "data", datos)
    shutil.rmtree(datos / "tenants" / CUARTA / "cases")
    ingesta = _Ingesta()

    with pytest.raises(tenant_provision.NoSeededCasesError, match="bandeja"):
        await tenant_provision.provision(
            CUARTA,
            cipher=crypto.active(),
            now=AHORA,
            ingest=ingesta,
            roots=tenant_provision.ProvisionRoots(
                tenants=cuatro_aseguradoras, corpus=datos / "tenants", data=datos
            ),
        )

    assert ingesta.llamadas == []


async def test_la_cuarta_aseguradora_pasa_chat_bandeja_y_aislamiento(
    cuatro_aseguradoras: Path,
) -> None:
    """La bateria de humo de AC5.1.1, con los tres lados que se pueden comprobar aqui.

    El cuarto --la pregunta de cobertura-- necesita el corpus indexado por el
    proveedor de embeddings, que es gasto: lo comprueba `mise run smoke` contra
    el aplicativo vivo y no esta aqui, y decirlo es parte del resultado.
    """
    resultado = await _aprovisionar(cuatro_aseguradoras)
    (sembrado,) = resultado.seeded

    # Chat: abre conversacion con el idioma por omision de **su** carpeta.
    conversacion = await chat.open_session(
        tenant_id=CUARTA,
        visitor_key_digest="resumen-de-un-navegador-de-prueba",
        origin_digest="origen-de-prueba",
        language=tenancy_config.require(CUARTA).default_language,
        now=AYER,
    )
    assert conversacion.language == "es"

    # Bandeja: su caso sembrado aparece en la cola de su ajustador, con el numero
    # del prefijo que declara su carpeta.
    pagina = await queue.page(CUARTA, filters=queue.QueueFilters(), role=Role.ADJUSTER)
    assert [item.case_id for item in pagina.items] == [sembrado.case_id]
    # El prefijo sale de **su** carpeta: tres letras que no se confunden con las
    # de las otras tres al dictarse.
    assert pagina.items[0].case_number.startswith("TST-")

    # Aislamiento: ninguna otra aseguradora lo ve, y no porque este codigo filtre.
    otra = next(t for t in tenancy_config.available_ids() if t != CUARTA)
    ajena = await queue.page(otra, filters=queue.QueueFilters(), role=Role.ADJUSTER)
    assert sembrado.case_id not in {item.case_id for item in ajena.items}
    assert await casos.get_case(otra, sembrado.case_id) is None


def _raices(tenants: Path) -> tenant_provision.ProvisionRoots:
    """Las carpetas de la prueba: las aseguradoras en el temporal y el corpus en la fixture."""
    return tenant_provision.ProvisionRoots(
        tenants=tenants,
        corpus=_fixture() / "data" / "tenants",
        data=_fixture() / "data",
    )


async def _aprovisionar(raiz: Path) -> tenant_provision.ProvisionOutcome:
    return await tenant_provision.provision(
        CUARTA,
        cipher=crypto.active(),
        now=AHORA,
        ingest=_Ingesta(),
        roots=_raices(raiz),
    )


@pytest.fixture(autouse=True)
def cifrador(monkeypatch: pytest.MonkeyPatch) -> Iterator[crypto.Cipher]:
    """Un cifrador de la prueba, instalado como lo instala la raiz de composicion.

    La clave sale del entorno y se genera una por corrida, igual que en las demas
    carpetas de integracion: ninguna prueba depende de la clave de otra.
    """
    monkeypatch.setenv(crypto.KEY_ENV_VAR, crypto.generate_key())
    cipher = crypto.Cipher.from_settings()
    crypto.install(cipher)
    yield cipher
    crypto.reset()


def _sin_personas(archivo: Path) -> None:
    """Le quita el bloque `staff` a la carpeta, dejando el resto intacto."""
    lineas = archivo.read_text(encoding="utf-8").splitlines()
    salida: list[str] = []
    dentro = False
    for linea in lineas:
        if linea.startswith("staff:"):
            dentro = True
            continue
        if dentro and (linea.startswith(("  -", "    ")) or not linea.strip()):
            continue
        dentro = False
        salida.append(linea)
    archivo.write_text("\n".join(salida) + "\n", encoding="utf-8")
