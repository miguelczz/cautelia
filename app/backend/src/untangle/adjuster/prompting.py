"""Los datos que el modelo lee: delimitados, escapados y con las etiquetas que la instruccion nombra.

La instruccion de sistema sale de un archivo versionado (`app/config/prompts/adjuster.<idioma>.md`)
y no lleva huecos. Todo lo que cambia por caso --el relato de la persona, lo que dice la poliza,
el texto de las clausulas, lo que trajo la web-- entra como **contenido** del mensaje, cada cosa
en su etiqueta, y nunca en la posicion de instruccion.

**El texto de fuera no puede cerrar una etiqueta ni abrir otra**: `<` y `>` se cambian por sus
entidades y los saltos de linea se colapsan, igual que en el resto del aplicativo. Una orden escrita
en el relato llega entera al modelo, pero dentro de su etiqueta.

Los nombres de las etiquetas son los que la instruccion nombra; una prueba compara las dos listas,
porque una regla sobre una etiqueta que no existe es una instruccion sobre nada.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from untangle.base import Locale
from untangle.inbox.actions import InboxAction
from untangle.policy_rag.corpus.models import Clause
from untangle.providers import prompts
from untangle.providers.ports import ExternalText, Prompt, PromptPart

DECISION_PROMPT = "adjuster"
RESEARCH_PROMPT = "adjuster_research"

#: Las etiquetas, por idioma. Mismas claves en los dos.
DATA_LABELS: dict[Locale, dict[str, str]] = {
    "es": {
        "today": "hoy",
        "narrative": "relato",
        "fields": "campos",
        "policy": "poliza",
        "clauses": "clausulas",
        "clause": "clausula",
        "rules": "reglas",
        "vehicle_value": "valor_vehiculo",
        "allowed_actions": "acciones_permitidas",
        "vehicle": "vehiculo",
    },
    "en": {
        "today": "today",
        "narrative": "narrative",
        "fields": "fields",
        "policy": "policy",
        "clauses": "clauses",
        "clause": "clause",
        "rules": "rules",
        "vehicle_value": "vehicle_value",
        "allowed_actions": "allowed_actions",
        "vehicle": "vehicle",
    },
}

#: Las etiquetas que la instruccion de la decision tiene que explicar. `vehicle` es de la
#: investigacion y su instruccion es otra.
LABELS_THE_INSTRUCTION_MUST_NAME: tuple[str, ...] = (
    "today",
    "narrative",
    "fields",
    "policy",
    "clauses",
    "clause",
    "rules",
    "vehicle_value",
    "allowed_actions",
)

#: Lo que se le muestra al modelo de cada texto de fuera: ni un relato ni una clausula necesitan mas.
_LARGO_MAXIMO = 4000


def one_line(text: str, *, limit: int = _LARGO_MAXIMO) -> str:
    """Un texto de fuera en una sola linea y sin forma de abrir o cerrar una etiqueta."""
    plano = " ".join(text.split())[:limit]
    return plano.replace("<", "&lt;").replace(">", "&gt;")


def _attr(text: str) -> str:
    """Lo mismo para un atributo: tampoco puede cerrar la comilla."""
    return one_line(text, limit=200).replace('"', "&quot;")


def _tag(label: str, content: str) -> str:
    return f"<{label}>{content}</{label}>"


def _content(part: str) -> tuple[PromptPart, ...]:
    return (PromptPart(role="user", text=ExternalText(part)),)


def clause_block(clauses: Sequence[Clause], *, language: Locale) -> str:
    """Las clausulas recuperadas, cada una con su identificador y la parte de la poliza."""
    e = DATA_LABELS[language]
    return "\n".join(
        f'<{e["clause"]} id="{_attr(c.clause_id)}">{one_line(c.part)}: {one_line(c.text)}'
        f"</{e['clause']}>"
        for c in clauses
    )


def build_decision_prompt(  # noqa: PLR0913 -- la decision lee seis cosas distintas, ninguna derivable de otra
    *,
    language: Locale,
    today: date,
    narrative: str,
    fields: Sequence[tuple[str, str]],
    policy_text: str,
    clauses_text: str,
    clauses: Sequence[Clause],
    rules_text: str,
    vehicle_value_text: str,
    allowed_actions: Sequence[InboxAction],
) -> Prompt:
    """La decision: la instruccion versionada y, aparte, todo lo del caso como datos."""
    e = DATA_LABELS[language]
    campos = "\n".join(f"- {_attr(clave)}: {one_line(valor)}" for clave, valor in fields)
    clausulas = "\n".join(
        parte
        for parte in (one_line(clauses_text), clause_block(clauses, language=language))
        if parte
    )
    acciones = ",".join(sorted(accion.value for accion in allowed_actions))
    partes = (
        (e["today"], today.isoformat()),
        (e["narrative"], one_line(narrative)),
        (e["fields"], campos),
        (e["policy"], one_line(policy_text)),
        (e["clauses"], clausulas),
        (e["rules"], one_line(rules_text)),
        (e["vehicle_value"], one_line(vehicle_value_text)),
        (e["allowed_actions"], acciones),
    )
    contenido = "\n".join(_tag(etiqueta, valor) for etiqueta, valor in partes)
    return Prompt(
        instruction=prompts.load_system_instruction(DECISION_PROMPT, language),
        parts=_content(contenido),
    )


def build_research_prompt(*, language: Locale, vehicle: str, today: date) -> Prompt:
    """La investigacion del valor: el vehiculo y la fecha como datos, nunca en la instruccion."""
    e = DATA_LABELS[language]
    contenido = "\n".join(
        (_tag(e["vehicle"], one_line(vehicle, limit=200)), _tag(e["today"], today.isoformat()))
    )
    return Prompt(
        instruction=prompts.load_system_instruction(RESEARCH_PROMPT, language),
        parts=_content(contenido),
    )
