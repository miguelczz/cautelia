"""El borrado nocturno del caso de un visitante (C-11, SEC-U4.4, SEC-U4.5).

U4 crea cinco tablas y las cinco guardan dato de visitante, asi que las cinco
llevan la marca. Lo que aporta este archivo es **un solo purgador que las cubre
a las cinco**, y no cinco purgadores sueltos: el caso y lo que cuelga de el se
borran juntos o no se borran, porque un caso sin sus campos no es medio caso, es
un caso roto.

**Por que un solo `DELETE` basta.** Las cuatro tablas hijas cuelgan del caso con
borrado en cascada, escrito en la misma revision que las crea. "Sin dejar
huerfanos" deja asi de depender de que este archivo recuerde el orden: lo impone
la forma de la base. Un purgador que se olvidara de los turnos no dejaria turnos
huerfanos, porque la base no se lo permitiria.

**Que se borra y que se conserva.** Solo el caso que nacio en una superficie
publica --el chat o la consola de voz-- porque es el unico que puede llevar
datos de una persona real. El caso del despliegue local y el del generador se
conservan: son sinteticos, y borrarlos cada noche vaciaria el corpus de
demostracion sin que nadie lo hubiera pedido. Esa cifra viaja en `kept`, y no en
un silencio: un purgador que solo dijera cuanto borro no dejaria ver el dia que
empezara a conservar de mas.

Recorre las aseguradoras una por una por la misma razon que los de U2: la
politica de fila no deja de aplicarse para borrar, asi que sin aseguradora
fijada un `DELETE` global borraria exactamente cero.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from untangle import observability
from untangle.case_record.models import VISITOR_ORIGINS
from untangle.tenancy import config, session
from untangle.tenancy.models import PurgeResult

#: Las tablas que este purgador se compromete a dejar vacias de dato de
#: visitante. Todas menos la primera no se nombran en ningun `DELETE`: las borra
#: la cascada. Se declaran igual porque el registro de la raiz de composicion se
#: compara contra lo que **la base** dice que lleva la marca, y una tabla que se
#: borra por cascada pero no se declara se leeria como una tabla sin dueno.
#:
#: `trace_summary` la crea U5 y no U4, y esta aqui por la misma razon que las
#: cuatro de arriba: **cuelga del caso en cascada** (BR7.4), asi que el `DELETE`
#: de este purgador es literalmente lo que la borra. Darle un purgador propio
#: seria declarar un segundo dueno de un borrado que ya ocurre, y el dia que los
#: dos discreparan no habria forma de saber cual manda.
#:
#: Las tres siguientes las crea U10 y estan aqui por la misma razon que
#: `trace_summary`: la divulgacion, las intervenciones de la guardia y la
#: revision **cuelgan del caso en cascada** (CG-U10-3, BR8.1), asi que este
#: purgador es quien las borra.
#:
#: La penultima la crea U9: la evaluacion de reglas tambien cuelga del caso en
#: cascada, con la misma llave compuesta `(tenant_id, case_id)` desde su primer
#: commit (CG-U9-4, BR4.1).
#:
#: La que sigue a `quote_eligibility` la crea la bandeja (U14): lo que el ajustador anota
#: para las reglas de triage -- monto estimado, cobertura disputada, sospecha de fraude--.
#: Cuelga del caso en cascada con la misma llave compuesta, y se declara aqui por la misma
#: razon que las demas: una tabla con la marca de dato de visitante que ningun purgador
#: nombra deja el reinicio nocturno diciendo que limpio algo que no acoto.
#:
#: Las dos siguientes las crea U8: la comprobacion de una cita y la respuesta de
#: cobertura tambien cuelgan del caso en cascada, con la misma llave compuesta
#: `(tenant_id, case_id)` desde su primer commit -- el hueco de U10 tampoco se
#: vuelve a abrir aqui (UG-3, BR4.5, SEC-U8.6).
#:
#: Las cuatro ultimas las crea U12: el punto de control, sus escrituras
#: pendientes, la pausa hacia la bandeja y la ejecucion de nodo. Misma razon y
#: misma llave compuesta desde su primer commit (BR6.4 de U12). Y aqui la cascada
#: no es solo comodidad: el punto de control -- y lo que quedo pendiente antes de
#: guardarse como uno -- guarda el estado serializado de la conversacion,
#: **cifrado pero completo**, asi que un caso de visitante borrado que dejara
#: alguna de las dos dejaria una copia de todo lo que la persona conto (M10, R7).
TABLAS = (
    "case_record",
    "case_field",
    "case_party",
    "case_transcript_turn",
    "case_change",
    "trace_summary",
    "disclosure_record",
    "guard_intervention",
    "compliance_review",
    "rule_evaluation",
    # La elegibilidad de una solicitud de cotizacion (U19). Cae por cascada con el
    # caso, como las demas, y se declara aqui porque declararla es lo que hace que
    # la comprobacion de completitud la cuente: una tabla marcada como dato de
    # visitante que ningun purgador nombre deja el reinicio nocturno diciendo que
    # limpio algo que no acoto. Lo caza su prueba, y lo cazo.
    "quote_eligibility",
    "case_triage_note",
    "citation_checks",
    "coverage_answers",
    "graph_checkpoint",
    "graph_checkpoint_write",
    "human_review_request",
    "node_run",
)

#: Los origenes que hacen publico a un caso. Salen del modelo y no de una lista
#: escrita aqui: anadir manana una superficie publica sin que su caso entre al
#: borrado seria la clase de olvido que nadie nota hasta que ya hay datos.
_ORIGENES = tuple(sorted(VISITOR_ORIGINS))

BORRAR = """
    DELETE FROM case_record
    WHERE created_at < :older_than
      AND origin = ANY(:origins)
"""

#: El borrado de **un** caso sembrado, por su identificador y por su origen.
#:
#: La condicion del origen no es una precaucion: es el alcance. Este borrado
#: existe para que el reinicio nocturno pueda devolver un caso sembrado a su
#: estado sembrado (AC5.6.4), y un caso de visitante no se arregla volviendolo a
#: crear --no hay de donde-- asi que con `origin = 'generator'` esta sentencia no
#: puede tocar ninguno aunque alguien le pase su identificador.
BORRAR_SEMBRADO = """
    DELETE FROM case_record
    WHERE case_id = :case_id
      AND origin = 'generator'
"""

CONTAR = """
    SELECT count(*) AS total FROM case_record
    WHERE created_at < :older_than
      AND origin = ANY(:origins)
"""

CONTAR_CONSERVADOS = """
    SELECT count(*) AS total FROM case_record
    WHERE created_at < :older_than
      AND NOT (origin = ANY(:origins))
"""


@dataclass(frozen=True)
class _CasePurger:
    """El purgador del caso completo. Uno solo para las cinco tablas."""

    name: str = "case_record"
    tables: tuple[str, ...] = TABLAS

    async def purge(self, *, older_than: datetime, dry_run: bool = False) -> PurgeResult:
        borrados = 0
        conservados = 0
        for tenant_id in config.available_ids():
            async with session.session_for(tenant_id) as sesion:
                if dry_run:
                    fila = await session.fetch_one(
                        sesion, CONTAR, older_than=older_than, origins=list(_ORIGENES)
                    )
                    borrados += int(fila["total"]) if fila is not None else 0
                else:
                    borrados += await session.execute_sql(
                        sesion, BORRAR, older_than=older_than, origins=list(_ORIGENES)
                    )
                fila = await session.fetch_one(
                    sesion, CONTAR_CONSERVADOS, older_than=older_than, origins=list(_ORIGENES)
                )
                conservados += int(fila["total"]) if fila is not None else 0

        observability.emit(
            "case_record.visitor_data_purged",
            purger=self.name,
            deleted=borrados,
            kept=conservados,
            dry_run=dry_run,
        )
        return PurgeResult(name=self.name, deleted=borrados, kept=conservados)


#: El purgador de U4. La raiz de composicion lo apunta en su tupla explicita.
CASE_RECORD_PURGER = _CasePurger()


async def delete_seeded_case(tenant_id: str, case_id: str) -> bool:
    """Borra **un** caso sembrado, con sus hijos por cascada. Devuelve si habia uno.

    Es la otra mitad de AC5.6.4: el reinicio nocturno conserva los casos del
    generador --borrarlos cada noche vaciaria el corpus de demostracion-- pero
    tiene que poder devolver a su estado sembrado el que alguien movio, y un caso
    que ya esta en otro estado no se puede *volver a sembrar* encima: la siembra
    es idempotente y se detiene nombrandolo, que es correcto y no arregla nada.

    **Solo toca casos con origen `generator`**, y eso lo dice la sentencia y no
    quien llama: un caso de visitante borrado no se puede volver a crear, porque
    lo que contenia lo dijo una persona y no hay de donde sacarlo. Vive en este
    archivo, que es donde U4 declara lo que se puede borrar y como, y no en U20:
    quien es dueno de una tabla es quien dice como se borra (C-11).
    """
    async with session.session_for(tenant_id) as sesion:
        borrados = await session.execute_sql(sesion, BORRAR_SEMBRADO, case_id=case_id)
    if borrados:
        observability.emit("case_record.seeded_case_deleted", tenant_id=tenant_id)
    return bool(borrados)
