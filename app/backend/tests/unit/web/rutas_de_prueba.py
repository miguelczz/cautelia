"""Un modulo de prueba con dos rutas que provocan los errores que U6 da forma.

- Una levanta una excepcion **no prevista**, con un mensaje que parece un dato
  personal: lo que se prueba es que ese mensaje no llegue al cliente (BR6.4,
  SEC-U6.4).
- Otra exige un parametro entero, para provocar una validacion fallida sin que
  el valor enviado vuelva en la respuesta.

Se monta como lo hara cualquier unidad con rutas: exponiendo `router()`.
"""

from __future__ import annotations

from fastapi import APIRouter

#: Lo que la excepcion dice. Si aparece en la respuesta, se filtro.
MENSAJE_INTERNO = "fallo interno con el telefono 300 555 1234 del asegurado"


def router() -> APIRouter:
    enrutador = APIRouter(prefix="/api/_prueba")

    @enrutador.get("/falla")
    async def falla() -> dict[str, str]:
        raise RuntimeError(MENSAJE_INTERNO)

    @enrutador.get("/numero")
    async def numero(n: int) -> dict[str, int]:
        return {"n": n}

    return enrutador
