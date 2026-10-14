"""Los casos de ejemplo: lo unico que una pagina publica puede mostrar de la bandeja.

**La regla dura, y donde esta de verdad.** Una superficie publica no muestra casos de
visitantes: ni su numero, ni su identificador, ni su contenido. Los unicos casos que
esta pagina entrega son los que escribe el generador sintetico (origen `generator`,
los que el reinicio nocturno conserva). El caso propio del visitante no pasa por
aqui: lo ve por su sesion de chat, que ya lo hacia.

La compuerta tiene dos mitades y cada una vive en un solo sitio:

- **La lista** recorta por origen **dentro de la consulta** (`ListingFilters.origin`).
  Filtrar despues de traer la pagina contaria el limite con filas que la lista no
  muestra, y una fila de visitante ya habria salido de la base.
- **El detalle** lee primero el origen del caso y solo abre los seis bloques si es del
  generador. Un caso de visitante, uno de otra aseguradora y uno que no existe
  devuelven lo mismo --`None`, que la ruta convierte en el mismo `404`--: la politica
  de fila ya filtro el de otra aseguradora, y el origen filtra el de visitante. Una
  respuesta distinta por causa diria a quien prueba identificadores cuales son de un
  visitante, que es justo lo que esta pagina no puede confirmar.

Son dos lecturas. No escribe filas, no emite enlaces ni cookies, y el detalle sale sin
ninguna accion posible (la ruta lo fija): para decidir un caso como ajustador, el
visitante crea el suyo en el chat.
"""

from __future__ import annotations

from untangle.case_record import api as casos
from untangle.case_record import repository as case_repo
from untangle.case_record.api import CaseSummary
from untangle.case_record.models import CaseState, Origin
from untangle.inbox import case_view
from untangle.tenancy.models import TenantId

#: El unico origen que esta pagina publica. No se calcula ni se lee de una lista: un
#: origen nuevo no entra aqui por accidente, entra el dia que alguien lo escribe.
ORIGEN_PUBLICO = Origin.GENERATOR

#: Los estados que la lista no ofrece. `open` es un caso sin nada dentro --la agente
#: acaba de saludar--: no ensena lo que es un caso y llenaria la pagina de filas
#: vacias. El detalle de uno sigue abriendose si se pide por su identificador.
FUERA_DE_LA_LISTA: tuple[CaseState, ...] = (CaseState.OPEN,)

#: El techo de una respuesta. Los casos de ejemplo son los que siembra el generador
#: --unas decenas por aseguradora--; el techo existe para que una base con muchos mas
#: no convierta una lectura publica en un recorrido de la tabla entera.
MAXIMO_DE_EJEMPLOS = 100

#: Lo mas largo que puede medir un identificador de caso para llegar a la base. Los del
#: generador miden 29; el techo existe para no mandar a la base lo que cualquiera
#: escriba en la direccion.
LARGO_MAXIMO_DE_IDENTIFICADOR = 128

#: El orden de los estados es el del camino de un caso, de que la agente toma datos a
#: que se cierra. Se toma de la declaracion del enum y no se repite aqui: un estado
#: nuevo entra en su sitio sin tocar esta lista.
_RANGO_DE_ESTADO = {estado: rango for rango, estado in enumerate(CaseState)}


def ordenados(filas: tuple[CaseSummary, ...]) -> tuple[CaseSummary, ...]:
    """Por estado, en el camino de un caso, y dentro de cada estado por numero.

    El orden lo decide el servidor y no la pantalla: dos visitantes mirando la misma
    aseguradora ven la misma lista.
    """
    return tuple(sorted(filas, key=lambda f: (_RANGO_DE_ESTADO[f.state], f.case_number)))


async def listar(tenant_id: TenantId) -> tuple[CaseSummary, ...]:
    """Los casos de ejemplo de esa aseguradora, ya ordenados.

    La aseguradora llega resuelta por la ruta y la consulta pasa por la sesion con el
    tenant fijado (`case_record`), asi que esta funcion no tiene forma de mirar otra.
    """
    pagina = await casos.list_cases(
        tenant_id,
        filters=case_repo.ListingFilters(
            origin=ORIGEN_PUBLICO.value,
            excluded_states=tuple(estado.value for estado in FUERA_DE_LA_LISTA),
        ),
        limit=MAXIMO_DE_EJEMPLOS,
    )
    return ordenados(pagina.items)


async def detalle(tenant_id: TenantId, case_id: str) -> case_view.CaseDetail | None:
    """El caso de ejemplo con sus seis bloques, o `None`.

    `None` quiere decir tres cosas a la vez --no existe, es de otra aseguradora, no es
    del generador-- y esta bien que no se puedan distinguir desde fuera. Un
    identificador que ni siquiera se puede preguntar (vacio, larguisimo o con
    caracteres de control como el NUL, que la base rechaza con un error) responde
    igual: es una direccion publica y escrita por cualquiera, y un `500` ahi
    distinguiria "esto no lo pregunte bien" de "no existe".

    El origen se lee con una consulta barata del caso (`cases_by_id`, una sola fila)
    **antes** de armar los seis bloques: no se arma lo que no se va a entregar.
    """
    if not 0 < len(case_id) <= LARGO_MAXIMO_DE_IDENTIFICADOR or not case_id.isprintable():
        return None
    encontrados = await casos.cases_by_id(tenant_id, [case_id])
    if not encontrados or encontrados[0].origin is not ORIGEN_PUBLICO:
        return None
    return await case_view.detail_for(tenant_id, case_id)
