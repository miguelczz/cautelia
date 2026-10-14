"""Si la demostracion acepta **casos nuevos**, visto desde el chat (BR3.2 de U20).

La regla es de U20 y su dato vive en la base: pasadas 24 horas sin un reinicio
nocturno exitoso, las superficies publicas dejan de aceptar casos nuevos, porque
la retencion dejo de estar acotada y seguir recibiendo datos que nadie va a
borrar es peor que degradar a proposito.

**Por que entra como puerta enchufable y no como una llamada.** `demo_operations`
esta **por encima** del chat en el contrato de capas: el chat no puede importarlo
ni preguntarle. Lo mismo que pasa con el grafo, que el chat tampoco construye y
recibe enchufado (`install_turn_handler`), y por la misma razon.

**Y por que no tiene valor por omision.** Un valor por omision "acepta" dejaria
la regla declarada y sin cumplir en cualquier proceso que monte el chat sin
enchufarla, y nadie se enteraria: el chat seguiria abriendo casos para siempre y
el tablero en verde. Falla nombrando la funcion que la instala, que es lo mismo
que hace el grafo. La forma contraria --un valor por omision "cierra"-- apagaria
el chat en el primer proceso que lo monte sin enchufarla, que es un fallo igual de
ruidoso pero que ademas apaga lo que si funcionaba.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

#: Si ahora mismo se puede abrir un caso nuevo. La implementa U20 con la ventana
#: de 24 horas y la instala la raiz de composicion.
type NewCaseGate = Callable[[], Awaitable[bool]]

_PUERTA: NewCaseGate | None = None


class NewCaseGateNotInstalledError(RuntimeError):
    """Se pregunto por la ventana de la demostracion sin haberla enchufado.

    Es un error de composicion y no del visitante: la raiz la enchufa al
    arrancar.
    """


def install_new_case_gate(gate: NewCaseGate) -> None:
    """Enchufa la ventana de la demostracion. La llama la raiz de composicion (C-24)."""
    global _PUERTA
    _PUERTA = gate


def current_new_case_gate() -> NewCaseGate:
    if _PUERTA is None:
        msg = (
            "el chat no sabe si la demostracion acepta casos nuevos: la raiz de "
            "composicion llama a 'chat.install_new_case_gate' al arrancar (BR3.2 de U20)"
        )
        raise NewCaseGateNotInstalledError(msg)
    return _PUERTA


def reset() -> None:
    """Olvida la puerta. Existe para que una prueba no herede la de otra."""
    global _PUERTA
    _PUERTA = None


__all__ = [
    "NewCaseGate",
    "NewCaseGateNotInstalledError",
    "current_new_case_gate",
    "install_new_case_gate",
    "reset",
]
