"""La cita que el navegador puede expandir (BR4.1, BR4.2).

Lo que aqui se comprueba es que **la version y el texto salen del corpus**, que es
el defecto que esta tanda encontro: el cable los leia del evento del grafo, que no
los tiene, y salian vacios en cada respuesta real con las nueve compuertas en verde.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import pytest

from untangle import observability
from untangle.base import Locale
from untangle.chat import citation
from untangle.policy_rag.corpus.models import Clause, FormKind, PolicyForm
from untangle.policy_rag.corpus.repository import upsert_reference_data

pytestmark = pytest.mark.usefixtures("base_de_u13")


@dataclass(frozen=True)
class _VistaDelGrafo:
    """Lo que el grafo deja en `FinalText.citations`: sin version y sin texto."""

    clause_id: str
    amount_deferred: bool = False
    part: str = "lo que el grafo creia"
    clause_language: str = "en"


async def _sembrar_clausula(  # noqa: PLR0913 -- los datos de la clausula sembrada, por nombre
    tenant_id: str,
    *,
    clause_id: str,
    language: Locale = "es",
    text: str = "La compania responde por los danos a terceros hasta el limite.",
    form_id: str = "form-u13",
    form_kind: FormKind = FormKind.BASE,
) -> None:
    formulario = PolicyForm(
        tenant_id=tenant_id,
        form_id=form_id,
        form_version="2026.4",
        form_kind=form_kind,
        language=language,
        issuer_label=f"{tenant_id} Mutual",
        issuer_tenant=tenant_id,
        clause_ids=(clause_id,),
    )
    clausula = Clause(
        tenant_id=tenant_id,
        clause_id=clause_id,
        clause_key="A.1",
        form_id=formulario.form_id,
        form_version=formulario.form_version,
        part="Responsabilidad civil",
        language=language,
        text=text,
        is_distractor=False,
        issuer_label=formulario.issuer_label,
    )
    await upsert_reference_data(
        tenant_id, forms=(formulario,), clauses=(clausula,), relations=(), policies=()
    )


async def test_la_version_y_el_texto_salen_del_corpus_y_no_del_evento(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """El control positivo, y la razon por la que las dos de abajo significan algo.

    La vista del grafo trae `part` y `clause_language` **equivocados a proposito**:
    si el detalle los copiara de ella en vez de leerlos de la clausula, esta prueba
    lo diria. Es lo que una asercion contra el mismo valor por omision no puede
    distinguir.
    """
    _, propia = dos_aseguradoras
    await _sembrar_clausula(propia, clause_id="RC-04")

    detalles = await citation.details_for(propia, (_VistaDelGrafo(clause_id="RC-04"),))

    assert len(detalles) == 1
    cita = detalles[0]
    assert cita.clause_version == "2026.4", "la version es la del formulario del corpus"
    assert cita.text.startswith("La compania responde"), "el texto completo, no un resumen"
    assert cita.part == "Responsabilidad civil", "la parte sale de la clausula"
    assert cita.clause_language == "es", "el idioma sale de la clausula, no de la vista"


async def test_el_idioma_de_la_clausula_viaja_para_poder_etiquetarla(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR4.2: sin este campo el navegador no puede decir en que idioma esta leyendo,
    y la unica alternativa seria traducir la clausula, que es lo que la regla
    prohibe."""
    _, propia = dos_aseguradoras
    await _sembrar_clausula(propia, clause_id="LI-09", language="en", text="The company pays.")

    detalles = await citation.details_for(propia, (_VistaDelGrafo(clause_id="LI-09"),))

    assert detalles[0].clause_language == "en"
    assert detalles[0].text == "The company pays.", "literal, en su idioma, sin traducir"


async def test_el_monto_diferido_viaja_con_la_cita(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Un endoso vigente puede haber cambiado el monto que la clausula nombra.
    Mostrar el texto completo sin decirlo seria afirmar una cifra que no rige."""
    _, propia = dos_aseguradoras
    await _sembrar_clausula(propia, clause_id="RC-04")

    detalles = await citation.details_for(
        propia, (_VistaDelGrafo(clause_id="RC-04", amount_deferred=True),)
    )

    assert detalles[0].amount_deferred is True


async def test_una_cita_sin_clausula_en_el_corpus_no_se_muestra(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """No se completa con huecos: una cita que la persona no puede abrir para
    contrastarla invita a confiar en algo que no puede leer. Se cae y deja su
    evento, que es por donde se investiga."""
    _, propia = dos_aseguradoras
    await _sembrar_clausula(propia, clause_id="RC-04")
    rastro = io.StringIO()
    observability.set_stream(rastro)

    detalles = await citation.details_for(
        propia, (_VistaDelGrafo(clause_id="RC-04"), _VistaDelGrafo(clause_id="NO-EXISTE"))
    )

    assert [cita.clause_id for cita in detalles] == ["RC-04"]
    assert "chat.citation_without_clause" in rastro.getvalue()
    assert "NO-EXISTE" in rastro.getvalue()


async def test_la_clausula_de_otra_aseguradora_no_se_puede_expandir(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La misma via que el resto del proyecto: lo ajeno y lo inexistente se responden
    igual.

    Se comprueba por **identidad y no por ausencia**: las dos aseguradoras tienen una
    clausula con el mismo identificador y distinto texto, asi que recibir la propia no
    prueba nada si no se mira cual es. Comprobar solo que la ajena "no aparece" pasaria
    igual con una implementacion que no devolviera nunca nada -- por eso la primera
    asercion es la del texto propio.
    """
    ajena, propia = dos_aseguradoras
    await _sembrar_clausula(ajena, clause_id="RC-04", text="Texto de la otra aseguradora.")
    await _sembrar_clausula(propia, clause_id="RC-04", text="Texto de la propia.")

    detalles = await citation.details_for(propia, (_VistaDelGrafo(clause_id="RC-04"),))

    assert detalles[0].text == "Texto de la propia."
    assert "otra aseguradora" not in detalles[0].text


async def test_la_clausula_de_un_endoso_trae_el_numero_de_su_condicion_especial(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """2026-10-11: el corpus no trae un titulo por clausula y la parte de un endoso se
    llama "Endosos", asi que lo que distingue a la tarjeta es de que condicion
    especial viene. Una clausula de la poliza base no trae ninguna."""
    _, propia = dos_aseguradoras
    await _sembrar_clausula(
        propia,
        clause_id="STO-PAP-2026-END-5-F.TERMINATION",
        form_id="STO-PAP-2026-END-5",
        form_kind=FormKind.ENDORSEMENT,
    )
    await _sembrar_clausula(propia, clause_id="STO-PAP-2026-F.TERMINATION", form_id="STO-PAP-2026")

    detalles = await citation.details_for(
        propia,
        (
            _VistaDelGrafo(clause_id="STO-PAP-2026-END-5-F.TERMINATION"),
            _VistaDelGrafo(clause_id="STO-PAP-2026-F.TERMINATION"),
        ),
    )

    assert [d.special_condition_number for d in detalles] == [5, None]
