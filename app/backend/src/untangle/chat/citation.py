"""La cita que el navegador puede expandir: su version y su texto (BR4.1, BR4.2).

**Por que esta pieza existe.** C-04 exige cinco campos en cada cita --identificador,
version, parte, texto y referencia de traza-- y lo que el grafo deja en el estado
(`CoverageCitationView` de U8/U12) tiene otros: identificador, parte, idioma de la
clausula, si el monto se difiere, y la frase de una sola oracion para la voz. Ese tipo
lo dice en su propio docstring: "nunca el texto de la clausula, que U13 despliega por
su cuenta". Esta es esa pieza.

Hasta aqui el cable leia los cinco campos de C-04 por atributo y **tres de ellos no
existian**, asi que salian vacios en cada respuesta real. No lo vio ninguna compuerta
porque su prueba usaba un doble con los cinco campos puestos: la prueba comprobaba el
doble, no lo que el grafo entrega.

**Lo que se muestra sale del corpus, no del estado.** La version y el texto se leen de
la clausula, que es lo que la persona va a comparar contra su poliza. Leerlo de otro
sitio seria arriesgarse a mostrar un texto que ya no es el del formulario vigente.

**Una cita cuya clausula no esta en el corpus no se muestra.** No se completa con
huecos ni se manda el identificador solo: una cita que la persona no puede abrir para
contrastarla es peor que ninguna, porque invita a confiar en algo que no puede leer.
Se cae del cable y deja su evento en la traza, que es donde se investiga por que el
corpus dejo de tener una clausula que se acababa de verificar.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from untangle import observability
from untangle.base import Locale
from untangle.policy_rag.corpus import repository as corpus
from untangle.policy_rag.corpus import translations as traducciones
from untangle.tenancy.models import TenantId

#: Un endoso se llama `<formulario base>-END-<n>`. La ingesta lo impone en los dos
#: sentidos --solo un endoso lleva `-END-<n>` y todo endoso lo lleva--, asi que el
#: numero se lee del identificador del formulario sin consultar su tipo.
_CONDICION_ESPECIAL = re.compile(r"-END-(\d+)$")


def _numero_de_condicion_especial(form_id: str) -> int | None:
    coincide = _CONDICION_ESPECIAL.search(form_id)
    return int(coincide.group(1)) if coincide else None


@dataclass(frozen=True)
class CitationDetail:
    """Una cita lista para el cable de C-04, con todo lo que la pagina muestra."""

    clause_id: str
    clause_version: str
    part: str
    text: str
    #: El idioma en que esta escrita la clausula. Es lo que deja etiquetarla cuando
    #: no coincide con el de la conversacion (BR4.2): sin este campo el navegador no
    #: puede decir en que idioma esta leyendo, y la unica alternativa seria
    #: traducirla, que es justo lo que la regla prohibe.
    clause_language: Locale
    #: Cierto cuando un endoso vigente modifica esta clausula (BR3.5 de U8). Viaja
    #: porque el texto completo de la clausula puede nombrar un monto que el endoso
    #: ya cambio: mostrarlo sin decirlo seria afirmar una cifra que no rige.
    amount_deferred: bool
    #: Quien **emitio** la clausula, tal como lo dice el corpus. Lo pide BR2.6 de
    #: U14: en una agencia, quien coloco la poliza no es quien la expidio, y sin
    #: este dato al lado las clausulas citadas parecen de la agencia. Sale de la
    #: misma fila que ya se leyo --no cuesta ninguna consulta mas-- y llega
    #: pegado a la clausula, que es donde nace la confusion que la regla evita.
    #:
    #: El chat no lo dibuja: el asegurado sabe de quien es su poliza. Que viaje
    #: igual es lo de siempre con esta pieza, que es **una sola** para las dos
    #: pantallas (BR4.2 de U13): dos copias serian dos formas de mostrar la misma
    #: cita, y un dia difieren.
    issuer_label: str
    #: La traduccion de referencia al idioma de la conversacion, cuando la clausula
    #: esta en otro (decision de Miguel del 2026-10-08). El texto que rige es `text`.
    translated_text: str | None = None
    translated_part: str | None = None
    #: El nombre de la parte en el idioma en que la clausula **no** esta escrita, siempre que
    #: haya traduccion (2026-10-13). `translated_part` depende del idioma que se pidio al
    #: leerla, y las pantallas que no conversan --la bandeja, «Ver mi caso», «Casos»-- no
    #: piden ninguno: con los dos idiomas que hay, este es el rotulo que corresponde cuando la
    #: pantalla esta en el otro. Quien dibuja decide con el idioma de la pantalla.
    part_in_other_language: str | None = None
    #: El numero de la condicion especial (endoso) a la que pertenece la clausula, o
    #: `None` si es de la poliza base o del territorio. El corpus no trae un titulo por
    #: clausula, y la parte de un endoso se llama "Endosos": con el numero la tarjeta se
    #: rotula como el panel de documentos, "Condicion especial 5", y no como "endoso".
    special_condition_number: int | None = None


def _atributo(cita: object, nombre: str, por_omision: Any) -> Any:
    """Un campo de la vista del grafo, leido por nombre.

    Por atributo y no por indice, igual que antes: el tipo concreto es de U12 y el
    dia que le anada un campo esta unidad sigue leyendo los suyos.
    """
    return getattr(cita, nombre, por_omision)


async def details_for(
    tenant_id: TenantId, citations: Sequence[object], *, language: Locale | None = None
) -> tuple[CitationDetail, ...]:
    """Las citas de una respuesta, completas, en el orden en que llegaron.

    Una sola consulta al corpus para todas: son las clausulas que el grafo acaba de
    recuperar y verificar, asi que ir una por una solo multiplicaria idas a la base.
    """
    if not citations:
        return ()

    ids = [str(_atributo(cita, "clause_id", "")) for cita in citations]
    clausulas = {
        clausula.clause_id: clausula
        for clausula in await corpus.clauses_by_ids(tenant_id, clause_ids=ids)
    }

    salida: list[CitationDetail] = []
    for cita in citations:
        clause_id = str(_atributo(cita, "clause_id", ""))
        clausula = clausulas.get(clause_id)
        if clausula is None:
            observability.emit(
                "chat.citation_without_clause",
                tenant_id=tenant_id,
                clause_id=clause_id,
            )
            continue
        salida.append(
            CitationDetail(
                clause_id=clausula.clause_id,
                clause_version=clausula.form_version,
                part=clausula.part,
                text=clausula.text,
                clause_language=clausula.language,
                amount_deferred=bool(_atributo(cita, "amount_deferred", False)),
                issuer_label=clausula.issuer_label,
                special_condition_number=_numero_de_condicion_especial(clausula.form_id),
                part_in_other_language=traducciones.part_text(
                    clausula.part, "en" if clausula.language == "es" else "es"
                ),
                translated_text=(
                    traducciones.clause_text(clausula.clause_id, language)
                    if language is not None and language != clausula.language
                    else None
                ),
                translated_part=(
                    traducciones.part_text(clausula.part, language)
                    if language is not None and language != clausula.language
                    else None
                ),
            )
        )
    return tuple(salida)


__all__ = ["CitationDetail", "details_for"]
