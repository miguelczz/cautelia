"""La puerta de la ventana de la demostracion, vista desde el chat (BR3.2 de U20).

Dos conductas, las dos sin base y las dos sobre la decision de composicion que
mas facil seria tomar al reves:

1. **Sin puerta enchufada, el chat no adivina**: falla nombrando la funcion que la
   instala. Un valor por omision "acepta" dejaria la regla declarada y sin cumplir
   en cualquier proceso que monte el chat sin enchufarla, y nadie se enteraria.
2. **Sin base, la puerta cierra.** No hay corridas que leer, asi que no se puede
   afirmar que lo que entre se borre esa noche, y aceptar casos nuevos en ese
   estado es justo lo que la regla prohibe.
"""

from __future__ import annotations

import pytest

from untangle.chat import demo_window
from untangle.server import composition


@pytest.fixture(autouse=True)
def _sin_puerta() -> object:
    """Cada prueba empieza y termina sin puerta: una no hereda la de otra."""
    demo_window.reset()
    yield None
    demo_window.reset()


async def test_sin_puerta_enchufada_el_chat_falla_nombrando_quien_la_instala() -> None:
    with pytest.raises(demo_window.NewCaseGateNotInstalledError, match="install_new_case_gate"):
        demo_window.current_new_case_gate()


async def test_sin_base_la_puerta_cierra() -> None:
    """Un proceso sin base no puede prometer que la retencion esta acotada."""
    # Se llama al ayudante de la raiz directamente: lo que se comprueba es la
    # rama "sin base", y montar la aplicacion sin base para llegar a ella pasaria
    # por media composicion para preguntar una sola cosa.
    puerta = composition._puerta_de_casos_nuevos(con_base=False)

    assert await puerta() is False


async def test_la_puerta_enchufada_es_la_que_el_chat_usa() -> None:
    """Instalarla y pedirla son la misma puerta: sin esto, la del arranque no es la
    que contesta."""

    async def abierta() -> bool:
        return True

    demo_window.install_new_case_gate(abierta)

    assert await demo_window.current_new_case_gate()() is True
