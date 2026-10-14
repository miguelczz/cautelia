"""BR3.3, con violaciones plantadas: el canal de voz no conoce ni el grafo ni los SDK.

Un contrato que nunca se ha visto fallar es un contrato del que nadie sabe si
funciona. Estas pruebas construyen un arbol minimo con los mismos nombres de
modulo, plantan **la** importacion que cada contrato existe para atrapar, y
exigen que la herramienta la encuentre y la nombre.

**Leen el archivo de configuracion real**, como las de U3 y no como las de U2: si
alguien saca `untangle.voice` de una de estas listas, estas pruebas fallan
nombrando la seccion. Con la configuracion transcrita dentro de la prueba
pasarian igual el dia que el archivo real dijera otra cosa.

Lo que protegen no es una regla de estilo. Que el canal no importe LangGraph es
lo que permite cambiar de framework de grafo sin tocar ni la voz ni el chat
(ADR-003), y que no importe un SDK es lo que mantiene el techo de gasto, el
registro y la taxonomia de errores en un solo sitio (ADR-018).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from untangle import paths

LINT_IMPORTS = Path(sys.executable).parent / "lint-imports"

CONFIGURACION_REAL = paths.repo_root() / "app" / "backend" / ".importlinter"

GRAFO = "grafo-solo-en-orchestration"
SIN_EVALS = "produccion-sin-evals"
SDK = "sdk-solo-en-su-adaptador"
CAPAS = "capas"

ENCABEZADO = """\
[importlinter]
root_packages =
    untangle
include_external_packages = True
"""

#: El arbol minimo con la direccion **correcta**: la voz consume los tipos del
#: turno (C-14) y los puertos de la voz (C-16), que es todo lo que BR3.3 permite.
#: Cada prueba planta encima la violacion que le toca.
ARBOL: dict[str, str] = {
    "untangle/__init__.py": "",
    "untangle/base.py": "",
    "untangle/copy_catalog/__init__.py": "",
    "untangle/copy_catalog/api.py": "",
    "untangle/tenancy/__init__.py": "",
    "untangle/tenancy/models.py": "",
    "untangle/telemetry/__init__.py": "",
    "untangle/telemetry/spend/__init__.py": "",
    "untangle/telemetry/spend/models.py": "",
    "untangle/compliance/__init__.py": "",
    "untangle/compliance/controls/__init__.py": "",
    "untangle/compliance/redaction/__init__.py": "",
    "untangle/compliance/redaction/api.py": "",
    "untangle/case_record/__init__.py": "",
    "untangle/case_record/api.py": "",
    "untangle/policy_rag/__init__.py": "",
    "untangle/rules/__init__.py": "",
    "untangle/synthetic_data/__init__.py": "",
    "untangle/providers/__init__.py": "",
    "untangle/providers/ports.py": "",
    # La puerta legitima al cliente de red, que el contrato de SDK nombra en su
    # `ignore_imports`. Tiene que existir: ese contrato declara que una exclusion
    # sin coincidencia es un **error**, y sin este archivo fallaria por el
    # andamiaje en vez de por lo que la prueba planta.
    "untangle/providers/adapters/__init__.py": "",
    "untangle/providers/adapters/wire.py": "import websockets\n",
    # La puerta legitima al SDK de Anthropic (2026-10-07), por la misma razon que
    # `wire.py`: el contrato de SDK la nombra en su `ignore_imports`.
    "untangle/providers/adapters/anthropic/__init__.py": "",
    "untangle/providers/adapters/anthropic/api.py": "import anthropic\n",
    # Las cuatro capas de arriba de la voz. El contrato de capas se niega a
    # correr si una de sus capas no existe, y lo dice nombrandola.
    "untangle/server/__init__.py": "",
    # La arista que la enmienda de esta unidad deja fuera, y la que sigue dentro.
    "untangle/server/voice_cli.py": "from untangle.evals.drivers import voice\n",
    "untangle/server/composition.py": "from untangle.server import voice_routes\n",
    "untangle/server/voice_routes.py": "from untangle.voice import api\n",
    "untangle/evals/drivers/__init__.py": "",
    "untangle/evals/drivers/voice.py": "from untangle.voice import api\n",
    # La **segunda** arista, del 2026-09-30 (U22): la ruta del panel de cifras lee
    # la linea base, que es del corredor. Tiene que existir en el arbol por lo
    # mismo que `wire.py`: este contrato declara que una exclusion sin coincidencia
    # es un error, y sin estos archivos las pruebas fallarian por el andamiaje.
    "untangle/evals/evidence/__init__.py": "",
    "untangle/evals/evidence/api.py": "",
    "untangle/server/evidence_routes.py": "from untangle.evals.evidence import api\n",
    # La **tercera**, del 2026-10-07 (fase 0): el comando a mano que evalua la
    # comprension. Existe por lo mismo que las dos de arriba.
    "untangle/server/understanding_cli.py": "from untangle.evals import cli\n",
    "untangle/evals/cli.py": "",
    "untangle/workspace/__init__.py": "",
    "untangle/demo_operations/__init__.py": "",
    "untangle/evals/__init__.py": "",
    "untangle/orchestration/__init__.py": "",
    "untangle/orchestration/contracts.py": "",
    "untangle/inbox/__init__.py": "",
    "untangle/chat/__init__.py": "",
    "untangle/voice/__init__.py": "",
    "untangle/voice/models.py": "from untangle.telemetry.spend import models\n",
    "untangle/voice/wire.py": "from untangle.voice import models\n",
    "untangle/voice/call.py": (
        "from untangle.orchestration import contracts\n"
        "from untangle.providers import ports\n"
        "from untangle.voice import models\n"
    ),
    "untangle/voice/api.py": "from untangle.voice import call, models, wire\n",
}


def _seccion(nombre: str) -> str:
    """La seccion de un contrato, extraida del archivo real."""
    texto = CONFIGURACION_REAL.read_text(encoding="utf-8")
    patron = re.compile(
        rf"^\[importlinter:contract:{re.escape(nombre)}\]$.*?(?=^\[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    encontrada = patron.search(texto)
    if encontrada is None:
        pytest.fail(
            f"'{CONFIGURACION_REAL}' no declara el contrato '{nombre}'. Sin el, la "
            "regla que esta prueba comprueba no existe en el proyecto: lo unico "
            "que quedaria es esta prueba pasando sobre una configuracion inventada."
        )
    return encontrada.group(0)


def _declara_la_voz(nombre: str) -> bool:
    """Si la seccion nombra `untangle.voice` entre sus modulos de origen.

    Se mira aparte de correr la herramienta porque es la mitad que se pierde en
    silencio: un contrato sin este renglon pasa siempre, y pasa **verde**.
    """
    seccion = _seccion(nombre)
    origenes = seccion.split("forbidden_modules")[0]
    return "untangle.voice" in origenes


def _config(*nombres: str) -> str:
    return ENCABEZADO + "\n" + "\n".join(_seccion(nombre) for nombre in nombres)


def _sembrar(raiz: Path, extra: dict[str, str] | None = None) -> None:
    contenido = dict(ARBOL)
    contenido.update(extra or {})
    for ruta, texto in contenido.items():
        archivo = raiz / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(texto, encoding="utf-8")


def _correr(raiz: Path, configuracion: str) -> subprocess.CompletedProcess[str]:
    archivo = raiz / ".importlinter"
    archivo.write_text(configuracion, encoding="utf-8")
    return subprocess.run(  # noqa: S603 -- ruta absoluta y argumentos fijos, sin shell
        [str(LINT_IMPORTS), "--config", str(archivo)],
        cwd=raiz,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


@pytest.fixture(autouse=True)
def la_herramienta_existe() -> None:
    if not LINT_IMPORTS.is_file():
        pytest.fail(
            f"no se encontro '{LINT_IMPORTS}'. Corra `mise run deps:install`: sin "
            "la herramienta, estos contratos no se comprueban y su ausencia no "
            "puede pasar por verde."
        )


def test_los_dos_contratos_nombran_a_la_voz_entre_sus_origenes() -> None:
    """La mitad que se pierde en silencio.

    Sacar `untangle.voice` de una de las dos listas no rompe nada visible: la
    herramienta sigue corriendo y sigue en verde. Lo unico que cambia es que
    desde ese dia el canal puede importar LangGraph o un SDK sin que nadie se
    entere, que es exactamente lo que BR3.3 existe para impedir.
    """
    assert _declara_la_voz(GRAFO), f"'{GRAFO}' ya no vigila untangle.voice"
    assert _declara_la_voz(SDK), f"'{SDK}' ya no vigila untangle.voice"


def test_el_arbol_correcto_cumple_los_tres_contratos(tmp_path: Path) -> None:
    """La linea base: sin violacion plantada, los tres pasan.

    Sin esta prueba, las de abajo podrian estar fallando por un error del
    andamiaje y pareceria que los contratos funcionan.
    """
    _sembrar(tmp_path)

    resultado = _correr(tmp_path, _config(CAPAS, GRAFO, SDK))

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_el_canal_de_voz_no_puede_importar_el_framework_del_grafo(tmp_path: Path) -> None:
    """ADR-003: cambiar de framework de grafo no debe tocar ningun canal.

    El ciclo de la llamada consume `handle_turn` **enchufado**, no importado, y
    es esta regla la que hace que esa costura sea obligatoria y no una
    preferencia de quien la escribio.
    """
    _sembrar(
        tmp_path,
        {
            "untangle/voice/call.py": (
                "import langgraph\n"
                "from untangle.orchestration import contracts\n"
                "from untangle.providers import ports\n"
            )
        },
    )

    resultado = _correr(tmp_path, _config(GRAFO))

    assert resultado.returncode != 0
    assert "langgraph" in resultado.stdout
    assert "voice" in resultado.stdout


def test_el_canal_de_voz_no_puede_importar_el_sdk_de_un_proveedor(tmp_path: Path) -> None:
    """ADR-018. El canal habla con la voz por los puertos de C-16 y por nada mas.

    Un SDK aqui saltaria el techo de gasto, el registro y la taxonomia de errores
    a la vez: los tres viven en el adaptador, y lo que los hace inevitables es
    que no haya otra puerta.
    """
    _sembrar(
        tmp_path,
        {
            "untangle/voice/call.py": (
                "import deepgram\n"
                "from untangle.orchestration import contracts\n"
                "from untangle.providers import ports\n"
            )
        },
    )

    resultado = _correr(tmp_path, _config(SDK))

    assert resultado.returncode != 0
    assert "deepgram" in resultado.stdout


def test_el_canal_de_voz_no_puede_abrir_un_canal_de_red(tmp_path: Path) -> None:
    """`websockets` no es un SDK y esta en la misma lista, por la misma fuga.

    Es el cliente con el que se habla con los dos proveedores de voz: un modulo
    fuera de los adaptadores que lo importara podria abrir un canal saltandose el
    techo. El transporte del socket del navegador **no** lo necesita: quien habla
    WebSocket con el navegador es el servidor, y eso es de `untangle.server`.
    """
    _sembrar(
        tmp_path,
        {"untangle/voice/wire.py": ("import websockets\nfrom untangle.voice import models\n")},
    )

    resultado = _correr(tmp_path, _config(SDK))

    assert resultado.returncode != 0
    assert "websockets" in resultado.stdout


def test_la_voz_no_puede_importar_al_canal_que_esta_encima(tmp_path: Path) -> None:
    """El contrato de capas: la bandeja esta arriba y la voz no la conoce.

    Es lo que impide que la llamada empiece a decidir lo que ve una ajustadora.
    """
    _sembrar(
        tmp_path,
        {"untangle/voice/call.py": "from untangle import inbox\n"},
    )

    resultado = _correr(tmp_path, _config(CAPAS))

    assert resultado.returncode != 0
    assert "voice" in resultado.stdout


def test_el_comando_a_mano_puede_llegar_al_conductor_de_voz(tmp_path: Path) -> None:
    """La enmienda del 2026-09-29, comprobada: una arista y no el paquete.

    Correr un caso de DS-5 por el transporte necesita a la vez los adaptadores de
    proveedor --que solo `untangle.server` importa-- y el corredor de
    evaluaciones. No hay ninguna capa donde las dos cosas se encuentren salvo
    esa, y prohibirlo dejaba la regla imposible de cumplir.
    """
    _sembrar(tmp_path)

    resultado = _correr(tmp_path, _config(SIN_EVALS))

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_el_proceso_servido_sigue_sin_poder_ver_el_corredor(tmp_path: Path) -> None:
    """Lo que la enmienda **no** aflojo, y es la mitad que la justifica.

    Si la exclusion hubiera sido el paquete entero en vez de una arista, la raiz
    de composicion podria arrastrar el corredor de evaluaciones al proceso
    publico, y con el sus casos de golden set y sus sondas. Esta prueba es la que
    dice que eso sigue prohibido.
    """
    _sembrar(
        tmp_path,
        {
            "untangle/server/composition.py": (
                "from untangle.evals import runner\nfrom untangle.server import voice_routes\n"
            )
        },
    )

    resultado = _correr(tmp_path, _config(SIN_EVALS))

    assert resultado.returncode != 0
    assert "composition" in resultado.stdout


def test_el_panel_de_cifras_llega_a_la_evidencia_pero_no_al_corredor(tmp_path: Path) -> None:
    """La segunda arista (U22), con sus dos mitades.

    El proceso servido **si** alcanza `untangle.evals.evidence` --monta la ruta del
    panel, que lee la linea base-- y eso es lo que la arista permite. Lo que no
    alcanza, ni por esa ruta ni por ninguna, es el corredor de evaluaciones.

    La segunda mitad es la que se pierde en silencio: si un dia la ruta importara
    el corredor, la primera mitad seguiria verde y nadie lo notaria.
    """
    _sembrar(tmp_path)
    permitido = _correr(tmp_path, _config(SIN_EVALS))
    assert permitido.returncode == 0, permitido.stdout + permitido.stderr

    _sembrar(
        tmp_path,
        {"untangle/server/evidence_routes.py": "from untangle.evals import runner\n"},
    )
    prohibido = _correr(tmp_path, _config(SIN_EVALS))

    assert prohibido.returncode != 0
    assert "evidence_routes" in prohibido.stdout


def test_el_contrato_sigue_nombrando_al_proceso_servido() -> None:
    """La otra mitad que se pierde en silencio: la exclusion podria crecer.

    `untangle.server` tiene que seguir entre los origenes. Sacarlo dejaria pasar
    cualquier importacion del paquete y ninguna prueba de arriba lo notaria: la de
    la arista permitida seguiria verde, porque lo permitido es un subconjunto.
    """
    seccion = _seccion(SIN_EVALS)
    origenes = seccion.split("forbidden_modules")[0]

    assert "untangle.server" in origenes
    assert "untangle.server.voice_cli -> untangle.evals.**" in seccion
