"""BR1.5: lo que un tercero aporta de si mismo, y nada mas. Sin ningun otro import.

Separado de `identity.py` (que ademas sabe **registrar** al tercero, y por eso
importa `case_record.api`) para que el corredor de evaluaciones -- que nunca
importa la raiz de composicion ni la sesion de base de datos, contrato
`acyclic_siblings` de `import-linter` -- pueda medir esta regla sin arrastrar
todo el arbol de `case_record`. Misma razon que separa `versions.py` de
`contradictions.py`.
"""

from __future__ import annotations

from pydantic import Field

from untangle.base import Frozen


class ThirdPartyReporter(Frozen):
    """Lo que se supo de quien reporta por otro, antes de registrarse (BR1.5).

    Todo lo que la persona no dio queda fuera: un tercero que solo dio su
    relacion no trae nombre ni contacto inventados.
    """

    name: str | None = None
    contact: str | None = None
    relation: str = Field(min_length=1)


#: Los tres atributos que un tercero puede aportar de si mismo. Sirve para que
#: `disclosed_fields` no tenga que enumerarlos dos veces (uno aqui y otro en su
#: cuerpo) y para que anadir un cuarto atributo a `ThirdPartyReporter` sin
#: tocar esta lista sea un olvido visible, no silencioso.
_REPORTER_ATTRIBUTES: tuple[str, ...] = ("name", "contact", "relation")


def disclosed_fields(reporter: ThirdPartyReporter) -> frozenset[str]:
    """BR1.5: exactamente lo que el tercero aporto de si mismo, ni un dato mas.

    Quien componga la confirmacion del turno (fuera de esta unidad) tiene que
    poder construir su pregunta de confirmacion leyendo solo de aqui: si esta
    funcion devolviera un campo que el tercero no dio, la confirmacion le
    revelaria un dato que nunca aporto -- el fallo exacto que BR1.5 prohibe.
    """
    return frozenset(
        atributo for atributo in _REPORTER_ATTRIBUTES if getattr(reporter, atributo) is not None
    )


__all__ = ["ThirdPartyReporter", "disclosed_fields"]
