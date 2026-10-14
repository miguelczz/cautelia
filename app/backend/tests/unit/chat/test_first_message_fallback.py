"""El respaldo por reglas del primer mensaje del chat (2026-10-13).

Cuando el modelo que entiende los mensajes falla, tarda o no esta enchufado, el primer mensaje
se clasifica por reglas. El defecto: un mensaje que **no dice a que viene** --«queria consultar
algo», «tengo una pregunta», «necesito ayuda»-- caia en `intent_of`, que devuelve un siniestro
por omision, y abria el reporte de un accidente. El modelo y la llamada ya lo leian bien.

Estas pruebas recorren `_primer_mensaje` por el camino del respaldo, sin base: lo que se
comprueba es la decision (contestar sin abrir caso, o seguir a abrir uno) y lo que la persona
lee, no el caso abierto, que es de las pruebas de integracion.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from untangle.chat import delivery
from untangle.chat import opening as chat_opening
from untangle.orchestration.contracts import InboundTurn
from untangle.orchestration.nodes.intake import understanding
from untangle.tenancy import config as tenancy_config

pytestmark = pytest.mark.usefixtures("catalogo_cargado")


class _Cola:
    """Una cola que guarda lo publicado."""

    def __init__(self) -> None:
        self.publicados: list[dict[str, Any]] = []

    def publish(self, wire: dict[str, Any]) -> bool:
        self.publicados.append(wire)
        return True


def _tenant_id() -> str:
    return sorted(c.tenant_id for c in tenancy_config.loaded().available)[0]


def _entrante(texto: str, *, idioma: str) -> InboundTurn:
    return InboundTurn(
        tenant_id=_tenant_id(),
        session_ref=f"navegador-{idioma}",
        case_id=None,
        text=texto,
        language=idioma,  # type: ignore[arg-type]
        channel="chat",
        received_at=datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
    )


async def _entendedor_caido(
    peticion: understanding.UnderstandingRequest,
) -> understanding.UnderstandingResponse:
    """El modelo que tarda: `understand` lo trata como «no se entendio»."""
    del peticion
    raise TimeoutError


@pytest.fixture(params=["sin_modelo", "modelo_que_falla"])
def respaldo(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> str:
    """Los dos caminos que llegan a las reglas: no hay modelo, o lo hay y no contesto."""
    entendedor = None if request.param == "sin_modelo" else _entendedor_caido
    monkeypatch.setattr(delivery, "_ENTENDEDOR", entendedor)
    monkeypatch.setattr(delivery, "_HISTORIA_SIN_CASO", {})
    monkeypatch.setattr(delivery, "_DATOS_SIN_CASO", {})
    return str(request.param)


@pytest.mark.parametrize(
    ("texto", "idioma"),
    [
        ("Quería consultar algo", "es"),
        ("Hola, tengo una pregunta", "es"),
        ("Necesito ayuda", "es"),
        ("Quisiera hacer una consulta", "es"),
        ("I have a question", "en"),
        ("Hi, I need some help", "en"),
        ("I'd like to ask something", "en"),
    ],
)
async def test_un_mensaje_que_no_dice_a_que_viene_no_abre_caso_y_pregunta(
    respaldo: str, texto: str, idioma: str
) -> None:
    del respaldo
    cola = _Cola()

    decidido = await delivery._primer_mensaje(cola, _entrante(texto, idioma=idioma))

    assert isinstance(decidido, delivery.Delivered), "siguio a abrir un caso"
    assert decidido.case_id is None
    assert decidido.turn_id is None
    assert len(cola.publicados) == 1
    # La frase del catalogo para quien todavia no dijo a que viene: la misma de un saludo suelto.
    config = tenancy_config.require(_tenant_id())
    esperada = chat_opening.greeting_reply(config, language=idioma)  # type: ignore[arg-type]
    assert cola.publicados[0]["text"] == esperada.text


@pytest.mark.parametrize(
    ("texto", "idioma"),
    [
        # Una sola palabra de contenido y el mensaje ya dice algo: sigue como siempre.
        ("Quería consultar sobre un choque", "es"),
        ("Tengo una pregunta sobre un accidente que tuve ayer", "es"),
        ("Me chocaron ayer", "es"),
        ("Necesito ayuda, me chocaron", "es"),
        ("I have a question about my claim", "en"),
        ("Someone rear-ended me yesterday", "en"),
        # Las dos intenciones que se reconocen por reglas tampoco se frenan.
        ("¿Mi póliza cubre el granizo?", "es"),
        ("Quiero cotizar", "es"),
    ],
)
async def test_un_mensaje_que_si_dice_algo_sigue_a_abrir_su_caso(
    respaldo: str, texto: str, idioma: str
) -> None:
    cola = _Cola()
    entrante = _entrante(texto, idioma=idioma)

    decidido = await delivery._primer_mensaje(cola, entrante)

    assert not isinstance(decidido, delivery.Delivered), "contesto sin abrir caso"
    assert cola.publicados == []
    turno, intencion = decidido
    assert turno.text == texto
    assert intencion is None, "el tipo lo deciden las reglas de `intent_of`, no el canal"
    # Lo que ya intento el modelo se recuerda para no volver a llamarlo en el turno.
    assert turno.understood_by_channel is (respaldo == "modelo_que_falla")


@pytest.mark.parametrize(
    ("texto", "idioma"), [("Hola, buenas tardes", "es"), ("Hello there", "en")]
)
async def test_el_saludo_suelto_sigue_sin_abrir_caso(
    respaldo: str, texto: str, idioma: str
) -> None:
    """Lo de antes no se pierde: el respaldo ya atendia el saludo."""
    del respaldo
    decidido = await delivery._primer_mensaje(_Cola(), _entrante(texto, idioma=idioma))

    assert isinstance(decidido, delivery.Delivered)
    assert decidido.case_id is None
