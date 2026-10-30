"""El aviso de la decision del ajustador (BR5.1, BR5.2, BR5.3).

Es el **unico** texto de este sistema que puede afirmar un resultado, asi que lo que
aqui se comprueba no es que se componga bien: es que **no se compone sin una firma**.
"""

from __future__ import annotations

import pytest

from untangle.case_record.models import CaseState, Resolution
from untangle.chat import notice
from untangle.tenancy import config as tenancy_config

pytestmark = pytest.mark.usefixtures("catalogo_cargado")

COMENTARIO = "Solicitar placa del tercero"


def _aseguradora() -> str:
    return tenancy_config.available_ids()[0]


def _decidido(resolution: Resolution) -> notice.Decision:
    return notice.Decision(
        case_id="caso-1",
        case_number="SA-482",
        resolution=resolution,
        comment=COMENTARIO,
        ref="change-abc123",
    )


# --- BR5.2: sin firma no hay aviso --------------------------------------------


@pytest.mark.parametrize(
    ("nombre", "decision"),
    [
        (
            "sin resolucion",
            notice.Decision(
                case_id="caso-1",
                case_number="SA-482",
                resolution=None,
                comment=COMENTARIO,
                ref="change-abc123",
            ),
        ),
        (
            "sin referencia de la decision",
            notice.Decision(
                case_id="caso-1",
                case_number="SA-482",
                resolution=Resolution.APPROVED,
                comment=COMENTARIO,
                ref=None,
            ),
        ),
    ],
)
async def test_sin_decision_registrada_el_aviso_no_se_compone(
    nombre: str, decision: notice.Decision
) -> None:
    """**Levanta**, no devuelve un texto sin afirmar nada.

    Componerlo y dejar que la guardia lo pare despues seria dejar el texto escrito
    en memoria a la espera de que alguien lo mirara. Y hacen falta las dos cosas:
    la resolucion sin su referencia tampoco autoriza, porque lo que autoriza es la
    firma y no el desenlace.
    """
    with pytest.raises(notice.MissingDecisionError):
        await notice.for_decision(decision, tenant_id=_aseguradora(), language="es")


async def test_la_resolucion_que_pone_el_sistema_al_abrir_no_es_una_decision() -> None:
    """`registered` la escribe el sistema al abrir el caso, no una persona.
    Avisar de ella seria avisar de nada, y ademas afirmaria un resultado sin
    nadie detras."""
    with pytest.raises(notice.MissingDecisionError):
        await notice.for_decision(
            _decidido(Resolution.REGISTERED), tenant_id=_aseguradora(), language="es"
        )


# --- El control positivo: con firma, el aviso sale y afirma ------------------


@pytest.mark.parametrize(
    "resolution", [Resolution.APPROVED, Resolution.REJECTED, Resolution.SENT_TO_INSURER]
)
async def test_con_decision_registrada_el_aviso_sale_con_su_comentario(
    resolution: Resolution,
) -> None:
    """Sin esta, las de arriba pasarian con una implementacion que no avisara nunca.

    Y comprueba lo que de verdad importa: que **la guardia no lo reemplaza**. El
    texto afirma un resultado, que es justo lo que la guardia bloquea en cualquier
    otra frase; lo que lo deja pasar es su clave eximida, y lo que autoriza esa
    exencion es la firma que se comprobo arriba.
    """
    aviso = await notice.for_decision(
        _decidido(resolution), tenant_id=_aseguradora(), language="es"
    )

    assert COMENTARIO in aviso.text
    assert "SA-482" in aviso.text
    assert aviso.decision_ref == "change-abc123"


async def test_un_comentario_que_afirma_cobertura_no_llega_al_asegurado() -> None:
    """El hallazgo de esta tanda, con su prueba.

    El comentario es **texto libre de una persona**, y la firma del ajustador
    autoriza su decision, no cualquier frase que escriba. Empezo siendo una
    exencion de la guardia por clave del catalogo --el mecanismo existia y estaba
    vacio esperando consumidor-- y al medirlo se vio que eximia el texto entero,
    comentario incluido: un "su poliza cubre el choque" pasaba sin intervencion.
    Ahora el comentario pasa por la guardia por su cuenta y la plantilla se
    compone despues.
    """
    prometedor = "su póliza cubre el choque y le vamos a pagar 900 dólares"
    decision = notice.Decision(
        case_id="caso-1",
        case_number="SA-482",
        resolution=Resolution.APPROVED,
        comment=prometedor,
        ref="change-abc123",
    )

    aviso = await notice.for_decision(decision, tenant_id=_aseguradora(), language="es")

    assert "cubre el choque" not in aviso.text
    assert "900" not in aviso.text
    # Y el aviso sigue saliendo: lo que se sustituye es lo que sobra, no el aviso.
    assert "SA-482" in aviso.text


async def test_el_aviso_de_la_agencia_no_promete_que_la_aseguradora_llame() -> None:
    """AC1.18.3: el traspaso real no existe (W1), asi que no se promete."""
    aviso = await notice.for_decision(
        _decidido(Resolution.SENT_TO_INSURER), tenant_id=_aseguradora(), language="es"
    )

    assert "contact" not in aviso.text.lower()
    assert "se comunicar" not in aviso.text.lower()
    assert "llamar" not in aviso.text.lower()


# --- BR5.3: derivado y sin decidir -------------------------------------------


def test_un_caso_derivado_sin_decidir_lo_dice_sin_prometer_una_fecha() -> None:
    """Prometer un plazo que nadie puede cumplir es la forma barata de que la
    demostracion parezca mejor de lo que es."""
    aviso = notice.pending(state=CaseState.DERIVED, language="es")

    assert aviso is not None
    assert aviso.decision_ref == "", "no afirma ningun resultado, no necesita firma"
    for promesa in ("hora", "día", "dias", "mañana", "24"):
        assert promesa not in aviso.text.lower()


@pytest.mark.parametrize(
    "estado", [CaseState.OPEN, CaseState.CAPTURING, CaseState.VERIFYING, CaseState.CLOSED]
)
def test_un_caso_que_no_espera_decision_no_avisa_nada(estado: CaseState) -> None:
    """Un caso en captura no tiene nada que avisar, y decir algo seria ruido."""
    assert notice.pending(state=estado, language="es") is None
