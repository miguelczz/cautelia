"""La siembra por la API de U4, contra PostgreSQL de verdad (BR6.3, BR6.4, AC5.6.3, AC5.6.4).

Lo que no se puede probar en memoria: que cada caso llegue a su estado por las
transiciones de la tabla de U4, que sus turnos se guarden redactados, que el
cierre lleve su evidencia y que dos pruebas que parten del mismo caso no se vean.

Cada prueba siembra **dentro de su propia transaccion** y la revierte al terminar
(ver `conftest.py`): ninguna deja filas para la siguiente y ninguna depende del
orden.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

import pytest

from untangle import paths
from untangle.case_record import api, repository
from untangle.case_record import history as historial
from untangle.case_record.crypto import Cipher
from untangle.case_record.models import ActorType, AttachmentKind, CaseState, ChangeKind, Origin
from untangle.case_record.rules import TransitionContext
from untangle.inbox import triage_notes
from untangle.rules import api as reglas
from untangle.server import composition, synthetic_seed
from untangle.synthetic_data.models import SeededCaseRecord, SeededField, SeededFieldStatus
from untangle.tenancy import api as tenancy
from untangle.tenancy import session
from untangle.tenancy.models import Action

from .conftest import AHORA, Sembrar, transaccion_de_prueba

VERIFICANDO = "SEED/sunmeadow/en/verifying"
CERRADO_POR_PERSONA = "SEED/stonecroft/es/closed-approved"
DERIVADO_POR_PERSONA = "SEED/knotwell/es/derived"
#: Un cerrado `registered` de Autos Poblado, la aseguradora que si cierra directo. Sus campos
#: los fija cada prueba que depende de ellos, para no atarse a lo que diga el archivo.
REGISTRADO_SIN_AJUSTADOR = "SEED/sunmeadow/en/closed"
EN_CAPTURA = "SEED/sunmeadow/en/capturing"
EN_DECISION = "SEED/sunmeadow/en/deciding"
ESPERANDO_AL_ASEGURADO = "SEED/sunmeadow/en/awaiting-insured"


def _con_campos(caso: SeededCaseRecord, **campos: str) -> SeededCaseRecord:
    """El mismo caso con **estos** campos, dichos y confirmados: lo que la prueba necesita.

    Las pruebas de insumos no pueden depender de lo que el generador escriba hoy en un
    archivo: si cambia el dato de ejemplo, el comportamiento que se prueba no cambia.
    """
    return caso.model_copy(
        update={
            "fields": {
                clave: SeededField(value=valor, status=SeededFieldStatus.CONFIRMED)
                for clave, valor in campos.items()
            }
        }
    )


async def _evaluaciones(caso: SeededCaseRecord) -> tuple[reglas.RuleEvaluation, ...]:
    return await reglas.evaluations_for(
        caso.tenant_id, synthetic_seed.seeded_case_id(caso.case_key)
    )


async def test_cada_caso_sembrado_llega_a_su_estado_por_la_api_de_u4(
    punto_unico_atado: str, cifrador: Cipher, casos_sembrados: dict[str, SeededCaseRecord]
) -> None:
    """Los setenta y dos, con origen generator, y cada uno en el estado de su archivo.

    Si una transicion del camino no estuviera en la tabla de U4, la API la
    rechazaria y esta prueba fallaria nombrando el caso: la siembra no tiene otra
    via que la de cualquier consumidor.
    """
    async with transaccion_de_prueba(punto_unico_atado):
        resultados = await synthetic_seed.seed_all(
            tuple(casos_sembrados.values()), cipher=cifrador, now=AHORA
        )

        assert len(resultados) == len(casos_sembrados) >= 42
        for resultado in resultados:
            caso = casos_sembrados[resultado.case_key]
            vista = await api.get_case(caso.tenant_id, resultado.case_id)
            assert vista is not None, resultado.case_key
            assert resultado.created
            assert vista.origin is Origin.GENERATOR
            assert vista.state.value == caso.state.value, resultado.case_key
            assert vista.policy_ref == caso.policy_number
            assert (vista.resolution.value if vista.resolution else None) == (
                caso.resolution.value if caso.resolution else None
            )
            assert vista.derivation_reason == (
                caso.derivation_reason.value if caso.derivation_reason else None
            ), resultado.case_key


async def test_los_turnos_se_guardan_redactados(
    sembrar: Sembrar, casos_sembrados: dict[str, SeededCaseRecord]
) -> None:
    """Ningun valor personal sembrado llega a la transcripcion (C-13, SEC-U4.6)."""
    resultado = await sembrar(VERIFICANDO)
    caso = casos_sembrados[VERIFICANDO]

    turnos = await api.transcript_of(caso.tenant_id, resultado.case_id)

    valores = [
        v["value"]
        for v in json.loads((paths.data_dir() / "personal_values.json").read_text("utf-8"))[
            "values"
        ]
    ]
    assert len(turnos) == len(caso.transcript)
    assert [v for t in turnos for v in valores if v in t.text_redacted] == []
    assert any("[" in t.text_redacted for t in turnos)


async def test_un_cerrado_lleva_la_evidencia_de_cierre_de_u4(
    sembrar: Sembrar, casos_sembrados: dict[str, SeededCaseRecord]
) -> None:
    """La transcripcion presente, con la clave del caso como referencia, y los otros
    cuatro vacios: el generador sabe que no existen (BR6.3 de U4, NFR-U4-9)."""
    for clave in (CERRADO_POR_PERSONA, REGISTRADO_SIN_AJUSTADOR):
        resultado = await sembrar(clave)
        caso = await repository.load_case(casos_sembrados[clave].tenant_id, resultado.case_id)

        assert caso is not None
        assert caso.closing_evidence is not None
        assert caso.closing_evidence.transcript.kind is AttachmentKind.PRESENT
        assert caso.closing_evidence.transcript.reference == clave
        assert caso.closing_evidence.missing() == ()
        assert caso.closed_at is not None


async def test_un_derivado_por_peticion_de_persona_lleva_su_motivo_y_prioridad_alta(
    sembrar: Sembrar, casos_sembrados: dict[str, SeededCaseRecord]
) -> None:
    resultado = await sembrar(DERIVADO_POR_PERSONA)
    caso = await repository.load_case(
        casos_sembrados[DERIVADO_POR_PERSONA].tenant_id, resultado.case_id
    )

    assert caso is not None
    assert caso.state is CaseState.DERIVED
    assert caso.derivation_reason is not None
    assert caso.derivation_reason.value == "person_requested"
    assert caso.priority.value == "high"


async def test_sembrar_dos_veces_no_duplica_nada(sembrar: Sembrar) -> None:
    """Idempotente: el segundo intento encuentra el caso en su estado y no lo toca."""
    primero = await sembrar(VERIFICANDO)
    segundo = await sembrar(VERIFICANDO)

    assert primero.created
    assert not segundo.created
    assert segundo.case_id == primero.case_id


async def test_un_caso_en_otro_estado_detiene_la_siembra_nombrandolo(
    sembrar: Sembrar, casos_sembrados: dict[str, SeededCaseRecord]
) -> None:
    """Una siembra a medias, o un caso que alguien movio, no se deja pasar en silencio."""
    resultado = await sembrar(VERIFICANDO)
    await api.apply_transition(
        casos_sembrados[VERIFICANDO].tenant_id,
        resultado.case_id,
        CaseState.DECIDING,
        context=TransitionContext(now=AHORA, actor=synthetic_seed.SEED_ACTOR),
    )

    with pytest.raises(synthetic_seed.SeedError, match=VERIFICANDO):
        await sembrar(VERIFICANDO)


async def test_lo_sembrado_en_una_prueba_no_sobrevive_a_su_transaccion(
    punto_unico_atado: str, cifrador: Cipher, casos_sembrados: dict[str, SeededCaseRecord]
) -> None:
    """La fixture revierte: una transaccion nueva no encuentra nada (BR6.4)."""
    caso = casos_sembrados[VERIFICANDO]
    async with transaccion_de_prueba(punto_unico_atado):
        resultado = await synthetic_seed.seed_case(caso, cipher=cifrador, now=AHORA)
        assert await api.get_case(caso.tenant_id, resultado.case_id) is not None

    async with transaccion_de_prueba(punto_unico_atado):
        assert await api.get_case(caso.tenant_id, resultado.case_id) is None


async def test_dos_pruebas_en_paralelo_sobre_el_mismo_caso_no_se_ven(
    punto_unico_atado: str, cifrador: Cipher, casos_sembrados: dict[str, SeededCaseRecord]
) -> None:
    """BR6.4 y AC5.6.3: dos transacciones a la vez, el mismo caso sembrado.

    La primera siembra el caso y lo mueve; la segunda arranca mientras la primera
    sigue abierta. La segunda no ve el caso de la primera, y cuando siembra el suyo
    lo encuentra tal como dice su archivo, sin el movimiento de la otra. Ninguna
    confirma nada. Las comparaciones no dependen de cuanto tarde cada una: la
    primera nunca confirma, asi que la segunda no puede verla en ningun orden.
    """
    caso = casos_sembrados[VERIFICANDO]
    primera_lista = asyncio.Event()

    async def primera() -> CaseState:
        async with transaccion_de_prueba(punto_unico_atado):
            sembrado = await synthetic_seed.seed_case(caso, cipher=cifrador, now=AHORA)
            vista = await api.apply_transition(
                caso.tenant_id,
                sembrado.case_id,
                CaseState.DECIDING,
                context=TransitionContext(now=AHORA, actor=synthetic_seed.SEED_ACTOR),
            )
            primera_lista.set()
            # Le da tiempo a la segunda para empezar mientras esta sigue abierta.
            await asyncio.sleep(0.2)
            return vista.state

    async def segunda() -> tuple[bool, CaseState]:
        await primera_lista.wait()
        async with transaccion_de_prueba(punto_unico_atado):
            id_del_caso = synthetic_seed.seeded_case_id(caso.case_key)
            veia_la_de_la_otra = await api.get_case(caso.tenant_id, id_del_caso) is not None
            sembrado = await synthetic_seed.seed_case(caso, cipher=cifrador, now=AHORA)
            return veia_la_de_la_otra, sembrado.state

    estado_de_la_primera, (veia_la_de_la_otra, estado_de_la_segunda) = await asyncio.gather(
        primera(), segunda()
    )

    assert estado_de_la_primera is CaseState.DECIDING
    assert not veia_la_de_la_otra
    assert estado_de_la_segunda is CaseState.VERIFYING


async def test_una_sesion_fuera_de_la_transaccion_de_la_prueba_falla_en_alto(
    punto_unico_atado: str, cifrador: Cipher, casos_sembrados: dict[str, SeededCaseRecord]
) -> None:
    """La atadura nunca cae a la base sin revertir: escribiria filas para la siguiente."""
    from .conftest import SesionFueraDeLaTransaccionError

    with pytest.raises(SesionFueraDeLaTransaccionError):
        await synthetic_seed.seed_case(casos_sembrados[VERIFICANDO], cipher=cifrador, now=AHORA)


# --- La evaluacion de reglas del caso de ejemplo ---------------------------------


async def test_el_caso_que_paso_por_la_decision_queda_con_la_evaluacion_de_sus_reglas(
    punto_unico_atado: str, cifrador: Cipher, casos_sembrados: dict[str, SeededCaseRecord]
) -> None:
    """Las reglas reales de su aseguradora, con los insumos que el caso dice, guardadas.

    Un registrado sin ajustador, con "nadie herido" y "ningun tercero", cumple la regla de
    cierre directo de Autos Poblado. Se compara con lo que da el motor con esos dos insumos
    escritos a mano: lo guardado no es un resultado puesto por la siembra.
    """
    caso = _con_campos(
        casos_sembrados[REGISTRADO_SIN_AJUSTADOR], injuries="No one injured", other_parties="None"
    )
    async with transaccion_de_prueba(punto_unico_atado):
        resultado = await synthetic_seed.seed_case(caso, cipher=cifrador, now=AHORA)
        (guardada,) = await _evaluaciones(caso)
        esperada = await reglas.evaluate(
            caso.tenant_id, {"injuries_present": False, "other_parties_data_pending": False}
        )
        cerrado = await repository.load_case(caso.tenant_id, resultado.case_id)

    assert resultado.created and resultado.evaluated_now
    assert resultado.rule_category == str(guardada.category) == "direct_close"
    assert guardada.category == esperada.category
    assert guardada.fired_rules == esperada.fired_rules
    assert guardada.inputs_snapshot == esperada.inputs_snapshot
    assert guardada.ruleset_version == esperada.ruleset_version
    assert cerrado is not None and cerrado.closed_at is not None
    # Se evalua **antes** de cerrar, como en vivo: la decision precede al cierre.
    assert guardada.evaluated_at < cerrado.closed_at
    # Y la evidencia de cierre ya no dice que las reglas no se miraron.
    assert cerrado.closing_evidence is not None
    assert cerrado.closing_evidence.fired_rules.kind is AttachmentKind.PRESENT
    assert cerrado.closing_evidence.fired_rules.reference == caso.case_key


async def test_lo_que_el_caso_dice_cambia_lo_que_dan_las_reglas(
    punto_unico_atado: str, cifrador: Cipher, casos_sembrados: dict[str, SeededCaseRecord]
) -> None:
    """El control de la de arriba: sin esta, una siembra que guardara siempre el mismo
    resultado pasaria. Con un herido, el mismo caso ya no se cierra solo."""
    caso = _con_campos(
        casos_sembrados[REGISTRADO_SIN_AJUSTADOR],
        injuries="Yes, my passenger hurt his neck",
        other_parties="None",
    )
    async with transaccion_de_prueba(punto_unico_atado):
        resultado = await synthetic_seed.seed_case(caso, cipher=cifrador, now=AHORA)
        (guardada,) = await _evaluaciones(caso)

    assert resultado.rule_category == str(guardada.category) == "referral"
    assert "SUN-R-05" in {regla.id for regla in guardada.fired_rules}


async def test_la_evaluacion_cae_entre_llegar_a_decidir_y_salir_de_ahi(
    punto_unico_atado: str, cifrador: Cipher, casos_sembrados: dict[str, SeededCaseRecord]
) -> None:
    """Un derivado por regla: la historia dice `-> deciding`, la evaluacion, y `-> derived`.

    Es el orden del aplicativo vivo, donde el nodo `decision` evalua mientras el caso esta en
    `deciding` y solo despues el caso sale a la bandeja.
    """
    caso = casos_sembrados[ESPERANDO_AL_ASEGURADO]
    async with transaccion_de_prueba(punto_unico_atado):
        resultado = await synthetic_seed.seed_case(caso, cipher=cifrador, now=AHORA)
        (guardada,) = await _evaluaciones(caso)
        cambios = await historial.of_case(caso.tenant_id, resultado.case_id)

    def _cuando(destino: str) -> datetime:
        (cambio,) = [
            c
            for c in cambios
            if c.change_kind is ChangeKind.TRANSITION_APPLIED
            and c.detail is not None
            and c.detail.endswith(f"-> {destino}")
        ]
        return cambio.changed_at

    assert _cuando("deciding") < guardada.evaluated_at < _cuando("derived")


async def test_sembrar_dos_veces_deja_una_sola_evaluacion(
    punto_unico_atado: str, cifrador: Cipher, casos_sembrados: dict[str, SeededCaseRecord]
) -> None:
    caso = casos_sembrados[REGISTRADO_SIN_AJUSTADOR]
    async with transaccion_de_prueba(punto_unico_atado):
        primero = await synthetic_seed.seed_case(caso, cipher=cifrador, now=AHORA)
        segundo = await synthetic_seed.seed_case(caso, cipher=cifrador, now=AHORA)
        guardadas = await _evaluaciones(caso)

    assert primero.evaluated_now and not segundo.evaluated_now
    assert segundo.rule_category == primero.rule_category
    assert len(guardadas) == 1


async def test_un_caso_ya_sembrado_sin_evaluacion_la_recibe_y_nada_mas_cambia(
    punto_unico_atado: str, cifrador: Cipher, casos_sembrados: dict[str, SeededCaseRecord]
) -> None:
    """Una base poblada antes de que la siembra evaluara: sembrar otra vez la completa.

    Se borra la evaluacion a mano para dejar el caso como estaba entonces. No se vuelve a crear
    ni a numerar el caso, y una tercera siembra ya no agrega nada.
    """
    caso = casos_sembrados[REGISTRADO_SIN_AJUSTADOR]
    async with transaccion_de_prueba(punto_unico_atado):
        primero = await synthetic_seed.seed_case(caso, cipher=cifrador, now=AHORA)
        antes = await api.get_case(caso.tenant_id, primero.case_id)
        async with session.session_for(caso.tenant_id) as sesion:
            borradas = await session.execute_sql(
                sesion,
                "DELETE FROM rule_evaluation WHERE case_id = :case_id",
                case_id=primero.case_id,
            )
        assert borradas == 1
        assert await _evaluaciones(caso) == ()

        completado = await synthetic_seed.seed_case(caso, cipher=cifrador, now=AHORA)
        tercero = await synthetic_seed.seed_case(caso, cipher=cifrador, now=AHORA)
        despues = await api.get_case(caso.tenant_id, primero.case_id)
        guardadas = await _evaluaciones(caso)

    assert not completado.created
    assert completado.evaluated_now
    assert completado.rule_category == primero.rule_category
    assert not tercero.evaluated_now
    assert len(guardadas) == 1
    assert antes is not None
    assert despues is not None
    assert despues.case_number == antes.case_number


@pytest.mark.parametrize("clave", [EN_CAPTURA, VERIFICANDO, EN_DECISION, DERIVADO_POR_PERSONA])
async def test_el_que_no_paso_por_la_decision_no_tiene_evaluacion(
    clave: str,
    punto_unico_atado: str,
    cifrador: Cipher,
    casos_sembrados: dict[str, SeededCaseRecord],
) -> None:
    """En captura, en verificacion, en `deciding` (la agente aun lo evalua) y el derivado a
    peticion de la persona: en vivo ninguno tiene evaluacion, y la vista dice que todavia no
    paso por las reglas. Inventarle una le pondria una categoria que nadie le dio."""
    caso = casos_sembrados[clave]
    async with transaccion_de_prueba(punto_unico_atado):
        resultado = await synthetic_seed.seed_case(caso, cipher=cifrador, now=AHORA)
        guardadas = await _evaluaciones(caso)

    assert guardadas == ()
    assert resultado.rule_category is None
    assert not resultado.evaluated_now


async def test_la_siembra_deja_evaluacion_solo_a_los_que_pasaron_por_la_decision(
    punto_unico_atado: str, cifrador: Cipher, casos_sembrados: dict[str, SeededCaseRecord]
) -> None:
    """Los setenta y dos juntos: quien debe tener evaluacion la tiene, una sola, y es la que dan
    las reglas con los insumos del caso; nadie mas la tiene.

    Y ninguna lleva lo que solo anota un ajustador: ni el monto, ni la cobertura disputada ni el
    fraude entran a la evaluacion de un caso de ejemplo, que se lee sin credencial. Por eso la
    pagina publica, que oculta las reglas que leen esos tres campos, no oculta ninguna aqui.
    """
    async with transaccion_de_prueba(punto_unico_atado):
        resultados = await synthetic_seed.seed_all(
            tuple(casos_sembrados.values()), cipher=cifrador, now=AHORA
        )
        for resultado in resultados:
            caso = casos_sembrados[resultado.case_key]
            guardadas = await _evaluaciones(caso)
            if not synthetic_seed.evaluates_rules(caso):
                assert guardadas == (), resultado.case_key
                continue
            (guardada,) = guardadas
            insumos = await composition.insumos_del_caso(
                caso.tenant_id, resultado.case_id, cipher=cifrador
            )
            esperada = await reglas.evaluate(caso.tenant_id, insumos)
            ocultas = reglas.rule_ids_reading(
                tenant_id=caso.tenant_id, fields=frozenset(triage_notes.NOTED_FIELDS)
            )
            assert guardada.category == esperada.category, resultado.case_key
            assert [r.id for r in guardada.fired_rules] == [r.id for r in esperada.fired_rules]
            assert set(insumos).isdisjoint(triage_notes.NOTED_FIELDS), resultado.case_key
            assert {r.id for r in guardada.fired_rules}.isdisjoint(ocultas), resultado.case_key

    assert sum(1 for r in resultados if r.evaluated_now) == sum(
        1 for c in casos_sembrados.values() if synthetic_seed.evaluates_rules(c)
    )
    assert any(r.evaluated_now for r in resultados)


async def test_ningun_ejemplo_termina_de_una_forma_que_sus_reglas_no_dan(
    punto_unico_atado: str, cifrador: Cipher, casos_sembrados: dict[str, SeededCaseRecord]
) -> None:
    """Los setenta y dos juntos: cada final sembrado es uno que las reglas de su aseguradora dan.

    En vivo solo la categoria de cierre directo cierra sin ajustador, y las otras dos --revision
    estandar y derivacion-- mandan el caso a uno. Entonces un cerrado `registered` tiene que
    haber salido de la primera, y uno que paso por un ajustador (derivado por una regla, y despues
    aprobado, rechazado o enviado a la aseguradora) de una de las otras dos. Si el dato de un
    ejemplo dice una cosa y sus reglas otra, la pantalla publica la muestra y esta prueba cae
    antes, nombrando el caso. Una aseguradora sin regla de cierre directo no puede tener ningun
    `registered`: sale de aqui sin decirlo, porque ninguno de sus ejemplos daria `direct_close`.
    """
    async with transaccion_de_prueba(punto_unico_atado):
        resultados = await synthetic_seed.seed_all(
            tuple(casos_sembrados.values()), cipher=cifrador, now=AHORA
        )

    sin_ajustador: list[str] = []
    con_ajustador: list[str] = []
    contradicciones: list[str] = []
    for resultado in resultados:
        caso = casos_sembrados[resultado.case_key]
        if caso.resolution is not None and caso.resolution.value == "registered":
            sin_ajustador.append(caso.case_key)
            if resultado.rule_category != "direct_close":
                contradicciones.append(
                    f"{caso.case_key}: cerrado sin ajustador y sus reglas dan {resultado.rule_category}"
                )
        elif caso.derivation_reason is not None and caso.derivation_reason.value == "rule":
            con_ajustador.append(caso.case_key)
            if resultado.rule_category not in ("standard_review", "referral"):
                contradicciones.append(
                    f"{caso.case_key}: paso por un ajustador y sus reglas dan {resultado.rule_category}"
                )

    assert contradicciones == []
    # Sin esto la prueba pasaria igual si ningun ejemplo cayera en alguno de los dos grupos.
    assert sin_ajustador
    assert con_ajustador


# --- Quien cerro el ejemplo -------------------------------------------------------


async def test_todo_ejemplo_cerrado_dice_quien_lo_cerro_como_lo_diria_en_vivo(
    punto_unico_atado: str, cifrador: Cipher, casos_sembrados: dict[str, SeededCaseRecord]
) -> None:
    """Los setenta y dos juntos: la ultima transicion de un cerrado la pone quien la pondria en vivo.

    Un cerrado `registered` lo cierran las reglas (T6) y su ultima transicion es del sistema. Uno
    que solo puede poner el personal de la aseguradora --aprobado, rechazado, enviado a la
    aseguradora (T9)-- termina con una transicion de actor `staff`, de una persona que esta en la
    configuracion de su aseguradora y cuyo rol tiene el permiso de esa decision. Y todo lo demas
    del historial sigue siendo del sistema: la siembra no inventa una persona en un camino donde en
    vivo no habria ninguna. Es la lectura que hace la vista del caso (`_quien_decidio`): la ultima
    transicion aplicada.
    """
    permiso_de = {
        "approved": Action.DECIDE_CASE,
        "rejected": Action.DECIDE_CASE,
        "sent_to_insurer": Action.MARK_SENT,
    }
    async with transaccion_de_prueba(punto_unico_atado):
        resultados = await synthetic_seed.seed_all(
            tuple(casos_sembrados.values()), cipher=cifrador, now=AHORA
        )
        historiales = {
            r.case_key: [
                c
                for c in await historial.of_case(casos_sembrados[r.case_key].tenant_id, r.case_id)
                if c.change_kind is ChangeKind.TRANSITION_APPLIED
            ]
            for r in resultados
        }

    cerrados = [c for c in casos_sembrados.values() if c.resolution is not None]
    por_el_personal = [c for c in cerrados if c.resolution and c.resolution.value != "registered"]
    por_las_reglas = [c for c in cerrados if c.resolution and c.resolution.value == "registered"]
    # Sin esto la prueba pasaria igual si ningun ejemplo cayera en alguno de los dos grupos.
    assert por_el_personal
    assert por_las_reglas

    for caso in cerrados:
        assert caso.resolution is not None
        cambios = sorted(historiales[caso.case_key], key=lambda c: c.changed_at)
        ultimo = cambios[-1]
        if caso.resolution.value == "registered":
            assert ultimo.actor.actor_type is ActorType.SYSTEM, caso.case_key
            continue
        assert ultimo.actor.actor_type is ActorType.STAFF, caso.case_key
        persona = tenancy.require(caso.tenant_id).principal(ultimo.actor.actor_id or "")
        assert persona is not None, (
            f"{caso.case_key}: {ultimo.actor.actor_id} no esta en su aseguradora"
        )
        assert tenancy.is_permitted(persona.role, permiso_de[caso.resolution.value]), caso.case_key
        assert ultimo.detail is not None
        assert ultimo.detail.endswith("-> closed"), caso.case_key

    # Y nadie mas lleva una persona: ni lo anterior al cierre, ni los casos que no se cerraron.
    con_persona = {
        clave
        for clave, cambios in historiales.items()
        for cambio in cambios
        if cambio.actor.actor_type is ActorType.STAFF
    }
    assert con_persona == {c.case_key for c in por_el_personal}
    for clave in con_persona:
        del_personal = [c for c in historiales[clave] if c.actor.actor_type is ActorType.STAFF]
        assert len(del_personal) == 1, f"{clave}: mas de una transicion a nombre del personal"


async def test_sembrar_otra_vez_un_cerrado_por_el_personal_no_agrega_nada(
    sembrar: Sembrar, casos_sembrados: dict[str, SeededCaseRecord]
) -> None:
    """Idempotente tambien con el autor nuevo: el segundo intento encuentra el caso en su estado
    y no le anade una transicion ni le cambia el autor."""
    caso = casos_sembrados[CERRADO_POR_PERSONA]
    primero = await sembrar(CERRADO_POR_PERSONA)
    antes = await historial.of_case(caso.tenant_id, primero.case_id)
    segundo = await sembrar(CERRADO_POR_PERSONA)
    despues = await historial.of_case(caso.tenant_id, primero.case_id)

    assert primero.created
    assert not segundo.created
    assert [c.change_id for c in despues] == [c.change_id for c in antes]


async def test_un_cerrado_sin_nadie_que_pueda_firmarlo_no_deja_un_caso_a_medias(
    punto_unico_atado: str,
    cifrador: Cipher,
    casos_sembrados: dict[str, SeededCaseRecord],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si la configuracion de la aseguradora no tiene a nadie con el permiso, la siembra se
    detiene nombrando el caso **antes** de escribir: ni el caso ni sus turnos quedan en la base."""
    caso = casos_sembrados[CERRADO_POR_PERSONA]
    sin_personal = tenancy.require(caso.tenant_id).model_copy(update={"staff": ()})
    monkeypatch.setattr(tenancy, "require", lambda _id: sin_personal)

    async with transaccion_de_prueba(punto_unico_atado):
        with pytest.raises(synthetic_seed.SeedError, match=CERRADO_POR_PERSONA):
            await synthetic_seed.seed_case(caso, cipher=cifrador, now=AHORA)
        existe = await api.get_case(caso.tenant_id, synthetic_seed.seeded_case_id(caso.case_key))

    assert existe is None
