"""BR5.5: si una version contradice la ya confirmada. Sin ningun otro import.

Separado de `contradictions.py` (que ademas sabe **escribir** la version
alterna, y por eso importa `case_record.api`) para que el corredor de
evaluaciones -- que nunca importa la raiz de composicion ni la sesion de base
de datos, contrato `acyclic_siblings` de `import-linter` -- pueda medir esta
regla sin arrastrar todo el arbol de `case_record`. Es la misma razon de fondo
que separa `providers/ports.py` de sus adaptadores: una hoja sin dependencias
se puede importar desde cualquier sitio sin abrir ninguna puerta de mas.
"""

from __future__ import annotations

from untangle.compliance.controls.normalization import fold


def is_contradiction(confirmed_value: str | None, new_value: str) -> bool:
    """BR5.5: si `new_value` contradice lo que ya esta confirmado.

    Un campo que todavia no tiene valor confirmado no puede contradecirse: lo
    que llega es su primera version, no una segunda.

    Se comparan los valores **plegados** (minusculas, sin tildes): "12 de Marzo"
    y "12 de marzo" son el mismo dato dicho dos veces, y anotarlos como version
    alterna le pondria al caso una contradiccion que nadie dijo -- con
    consecuencias, porque la regla de la aseguradora que mira si **existe** una
    version alterna es la que puede derivar el caso.

    Lo que esto **no** resuelve, y es de U9: dos redacciones distintas del mismo
    hecho ("en la autopista, salida 12" y "salida 12 de la autopista") siguen
    contando como versiones distintas. Decidir cuando dos textos libres se
    contradicen de verdad es de la regla que las lee, no de esta comparacion.
    """
    return confirmed_value is not None and fold(confirmed_value) != fold(new_value)


__all__ = ["is_contradiction"]
