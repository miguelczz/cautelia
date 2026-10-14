"""El asegurado simulado, por reglas indexadas por campo (BR2.1 a BR2.4).

**No hay ninguna fuente de azar y no se llama a ningun modelo** (BR1.11). Un
asegurado simulado por modelo hace que dos corridas del mismo commit dejen de ser
comparables, que es exactamente lo que la compuerta necesita poder afirmar.

El guion se indexa por campo y no por orden: emparejar por el orden del guion
rompe el caso en cuanto la agente pregunta en otro orden, que es la conducta
normal (decision Q1 del diseno funcional).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from untangle.copy_catalog import api as copy_api
from untangle.evals.models import AnswerKind, GoldenCase

# La frase de desconocimiento sale del catalogo, como toda frase que lee una
# persona. La clave es literal para que el chequeo de claves sin consumidor la
# encuentre (BR3.2, BR3.4).
CLAVE_DESCONOCIMIENTO = copy_api.CopyKey("evals.scripted_insured.unknown_field")


@dataclass(frozen=True)
class Reply:
    """Lo que el asegurado simulado contesta a un turno."""

    text: str
    #: Verdadero cuando el guion no tenia respuesta para el campo pedido.
    off_script: bool = False
    #: Verdadero cuando lo entregado fue una correccion del guion.
    correction: bool = False


@dataclass
class ScriptedInsured:
    """Responde un caso segun su guion. Una instancia por caso y por corrida.

    Lleva estado -- que correccion ya entrego -- y por eso no se comparte entre
    casos: dos casos compartiendo el mismo respondedor serian dos corridas
    distintas segun el orden en que se ejecutaran.
    """

    case: GoldenCase
    _entregadas: set[tuple[str, int]] = field(default_factory=set)
    _off_script: int = 0

    @property
    def off_script_turns(self) -> int:
        """Turnos en los que el guion no tenia respuesta para el campo pedido."""
        return self._off_script

    def answer(self, field_key: str) -> Reply:
        """La respuesta al campo que el turno declara.

        Orden de resolucion, y cada rama es una regla:

        1. Si el campo tiene una respuesta sin entregar, se entrega la de menor
           secuencia. Las secuencias siguientes son correcciones, y se entregan
           una sola vez, la primera vez que se vuelve sobre el bloque (BR2.3).
        2. Si todas las respuestas del campo ya se entregaron, se repite la
           ultima: el sistema esta confirmando, y confirmar no es corregir otra
           vez. Un respondedor que repitiera la correccion dejaria el caso en un
           bucle y nunca produciria su registro esperado.
        3. Si el campo no esta en el guion, se contesta la frase de
           desconocimiento del catalogo en el idioma del caso y el turno suma un
           desvio (BR2.2).
        """
        respuestas = self.case.answers_for(field_key)

        if not respuestas:
            self._off_script += 1
            return Reply(
                text=copy_api.t(CLAVE_DESCONOCIMIENTO, locale=self.case.language),
                off_script=True,
            )

        for respuesta in respuestas:
            marca = (respuesta.field_key, respuesta.sequence)
            if marca not in self._entregadas:
                self._entregadas.add(marca)
                return Reply(
                    text=respuesta.text,
                    correction=respuesta.kind is AnswerKind.CORRECTION,
                )

        ultima = respuestas[-1]
        return Reply(text=ultima.text, correction=False)
