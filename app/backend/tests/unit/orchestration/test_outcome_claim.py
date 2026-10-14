"""Cuando una respuesta da el reporte por hecho, o dice que lo revisa un ajustador (2026-10-13).

La comprobacion es una funcion pura sobre el texto. Se prueba por los **dos lados**, porque los
dos errores cuestan: dejar salir la promesa falsa manda a la persona a casa creyendo que su
reporte esta hecho, y marcar de mas una respuesta natural deja a la agente sonando a contestadora.
El docstring del modulo dice que se considera una afirmacion; aqui esta cada decision con su
ejemplo.
"""

from __future__ import annotations

import pytest

from untangle.orchestration import outcome_claim

#: La respuesta de la llamada simulada del 2026-10-13, con el lugar todavia sin decir.
LA_RESPUESTA_DE_LA_LLAMADA = (
    "De nada. Ya quedó anotado tu reporte; un ajustador lo revisará con tu póliza. Que estés bien."
)


def test_la_respuesta_de_la_llamada_se_marca_y_dice_que_oracion() -> None:
    assert outcome_claim.find_claim(LA_RESPUESTA_DE_LA_LLAMADA) == "Ya quedó anotado tu reporte"
    assert outcome_claim.claims_outcome(LA_RESPUESTA_DE_LA_LLAMADA) is True


@pytest.mark.parametrize(
    "texto",
    [
        # El reporte quedo hecho: registrado, anotado, enviado, completo, listo, cerrado.
        "Tu reporte quedó registrado.",
        "Listo, tu caso ya está completo.",
        "Sí, tu reporte ya quedó enviado.",
        "El caso quedó cerrado.",
        "Tu solicitud fue guardada.",
        "Ya registré tu reporte y lo tiene un ajustador.",
        "Anotamos tu solicitud, gracias.",
        "He guardado tu reporte.",
        "Todo quedó anotado, gracias.",
        "Ya quedó todo.",
        "Ya terminamos. Que estés bien.",
        "Ya tengo todo lo que necesito.",
        "Ya quedó anotado tu reporte, ¿algo más?",
        # Un ajustador lo revisa, lo revisara, lo tiene.
        "Un ajustador lo revisará pronto.",
        "El ajustador te contactará.",
        "Ya quedó anotado, un ajustador te contactará.",
        "Anoté tu solicitud, un ajustador se pondrá en contacto contigo.",
        "Tu reporte será revisado por un ajustador.",
        "Tu caso está con un ajustador.",
        "Pasé tu caso a un ajustador.",
        "Lo revisará un ajustador.",
        "Perfecto, ya quedó todo. Un ajustador te escribirá pronto.",
        # Ingles.
        "You're welcome. Your report is saved and an adjuster will review it with your policy.",
        "Your report's saved.",
        "I've recorded your report.",
        "We have logged your claim.",
        "Everything is saved.",
        "You're all set.",
        "We're all done.",
        "That completes your report.",
        "The report is now complete.",
        "An adjuster will be in touch.",
        "An adjuster'll review it.",
        "The adjuster is reviewing it.",
        "Your case has been reviewed by an adjuster.",
        "Your case is with an adjuster.",
        "I've passed your case to an adjuster.",
        "I now have everything I need.",
    ],
)
def test_lo_que_da_el_reporte_por_hecho_o_promete_la_revision_se_marca(texto: str) -> None:
    assert outcome_claim.claims_outcome(texto) is True, texto


@pytest.mark.parametrize(
    "texto",
    [
        # Anotar un dato no es dar el reporte por hecho.
        "Anoté el lugar. ¿Qué carro era?",
        "Ya anoté que nadie resultó herido.",
        "Quedó anotado el lugar del accidente.",
        "Ya lo anoté.",
        "Sí, ya te anoté ese dato.",
        "Anoté el número de caso.",
        "I noted the location. What car was it?",
        "I've noted the case number.",
        # Una pregunta no afirma nada.
        "¿Quieres que un ajustador lo revise?",
        "¿Ya quedó registrado tu reporte?",
        "Are you all set?",
        "Would you like an adjuster to review it?",
        # Ofrecer pasar el caso, o prometerlo bajo una condicion, es lo que el producto dice.
        "Si prefieres, paso tu caso a un ajustador.",
        "Puedo pasar tu caso a un ajustador si lo prefieres.",
        "Cuando me digas el lugar, tu reporte quedará registrado y un ajustador lo revisará.",
        "Una vez que terminemos, un ajustador lo revisará.",
        "If you'd like, I can pass your case to an adjuster.",
        "Once you tell me where it happened, your report will be saved and an adjuster will review it.",
        # Decir que NO esta hecho es justo lo contrario.
        "Todavía no queda registrado tu reporte: me falta el lugar.",
        "Tu reporte aún no está completo.",
        "Tu reporte todavía no ha quedado enviado.",
        "Your report isn't complete yet; I still need the location.",
        "Your report is not saved yet.",
        # Lo que solo se acerca.
        "Con esto tu reporte queda casi completo.",
        "Tu reporte va casi completo; falta el lugar.",
        "We're done with the vehicle questions. When did it happen?",
        "Ya terminamos con esa parte. ¿Dónde pasó?",
        # Explicar lo que hace un ajustador sin prometer que lo haga con este caso.
        "Un ajustador confirma si aplica y por cuánto.",
        "An adjuster can confirm whether it applies.",
        # «caso» y «reporte» en otra construccion.
        "En ese caso, queda registrado el lugar.",
        "No te preocupes, anota lo que recuerdes.",
        # Lo corriente de una conversacion de captura.
        "Qué alivio que estén bien. ¿Me cuentas cuándo fue?",
        "Gracias. ¿Dónde ocurrió el accidente?",
        "Thanks. Where did it happen?",
        "",
    ],
)
def test_lo_que_anota_pregunta_ofrece_o_niega_no_se_marca(texto: str) -> None:
    assert outcome_claim.claims_outcome(texto) is False, texto


def test_el_si_afirmativo_no_es_el_si_condicional() -> None:
    """Sin la tilde son la misma palabra: «Sí, ya quedó enviado tu reporte» no es una condicion."""
    assert outcome_claim.claims_outcome("Sí, tu reporte ya quedó registrado.") is True
    assert outcome_claim.claims_outcome("Si me das el lugar, tu reporte queda registrado.") is False


def test_la_negacion_solo_cuenta_si_esta_en_la_misma_clausula() -> None:
    # «No te preocupes» es otra clausula: no niega lo que viene despues de la coma.
    assert outcome_claim.claims_outcome("No te preocupes, tu reporte quedó registrado.") is True
    assert outcome_claim.claims_outcome("Tu reporte no quedó registrado.") is False


def test_una_pregunta_no_cubre_la_afirmacion_que_la_precede() -> None:
    assert outcome_claim.find_claim("Tu reporte quedó registrado. ¿Algo más?") == (
        "Tu reporte quedó registrado."
    )
    # En una sola oracion, el «¿» abre otra.
    assert outcome_claim.find_claim("Ya quedó anotado tu reporte, ¿algo más?") is not None


def test_se_busca_en_los_dos_idiomas_sea_cual_sea_el_de_la_conversacion() -> None:
    """Una afirmacion falsa lo es en el idioma que sea; un idioma equivocado se descarta aparte."""
    assert outcome_claim.claims_outcome("Your report is saved.") is True
    assert outcome_claim.claims_outcome("Tu reporte está guardado.") is True


@pytest.mark.parametrize("texto", [None, "", "   ", "\n"])
def test_sin_texto_no_hay_afirmacion(texto: str | None) -> None:
    assert outcome_claim.find_claim(texto) is None
