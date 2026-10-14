"""La pagina publica de casos de ejemplo: solo el generador sale, y solo se lee.

**La regla dura.** Una superficie publica no muestra casos de visitantes: ni su
numero, ni su identificador, ni su contenido. Los unicos casos que entrega
`/api/examples` son los del generador sintetico (origen `generator`); todo lo demas
--un caso de visitante, uno de otra aseguradora, uno que no existe-- responde **lo
mismo**, y se compara la respuesta entera: la filtracion no es el dato, es la
distincion.

**El control positivo va delante.** Las comprobaciones de rechazo pasan igual contra
una ruta que no entregue nada nunca; la primera prueba de cada bloque es que el caso
del generador si sale. Es la forma de prueba que el catalogo llama "la asercion que no
puede distinguir".
"""

from __future__ import annotations

import httpx2
import pytest
from fastapi import FastAPI

from untangle import paths
from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.case_record.models import (
    Actor,
    ActorType,
    CaseField,
    CaseState,
    FieldStatus,
    Origin,
)
from untangle.inbox import triage_notes
from untangle.rules import api as reglas
from untangle.server import synthetic_seed
from untangle.synthetic_data.cases import load_seeded_cases

from .conftest import AHORA, cliente, credencial_de, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u14")

#: Los tres origenes que **no** son del generador: dato de visitante o de un
#: despliegue local. Ninguno puede salir por la pagina publica.
ORIGENES_AJENOS = [
    Origin.PUBLIC_CHAT,
    Origin.PUBLIC_VOICE_CONSOLE,
    Origin.LOCAL_DEPLOYMENT,
]


def _lista(tenant_id: str) -> str:
    return f"/api/examples/{tenant_id}/cases"


def _detalle(tenant_id: str, case_id: str) -> str:
    return f"/api/examples/{tenant_id}/cases/{case_id}"


def _sin_rastro(respuesta: httpx2.Response) -> dict[str, object]:
    """El cuerpo del error sin `trace_id`, que es lo unico que puede diferir (C-01)."""
    cuerpo = dict(respuesta.json())
    assert cuerpo.pop("trace_id", None), "la respuesta de error no trae rastro (C-01)"
    return cuerpo


async def _numero(tenant_id: str, case_id: str) -> str:
    vista = await casos.get_case(tenant_id, case_id)
    assert vista is not None
    return vista.case_number


async def _inexistente(app: FastAPI, tenant_id: str) -> httpx2.Response:
    async with cliente(app) as http:
        return await http.get(_detalle(tenant_id, "caso-que-nadie-abrio"))


# --- La lista -------------------------------------------------------------------


async def test_la_lista_trae_los_casos_de_ejemplo(
    app: FastAPI, dos_aseguradoras: tuple[str, str]
) -> None:
    """El control positivo: lo que el generador dejo sale, con la forma del contrato."""
    propia, _ = dos_aseguradoras
    derivado = await nuevo_caso(propia, estado=CaseState.DERIVED)

    async with cliente(app) as http:
        respuesta = await http.get(_lista(propia))

    assert respuesta.status_code == 200, respuesta.text
    (fila,) = respuesta.json()["items"]
    assert fila == {
        "case_id": derivado,
        "case_number": await _numero(propia, derivado),
        "record_type": "claim",
        "state": "derived",
        "channel": "chat",
        "language": "es",
        "completeness_complete": 0,
        "completeness_total": fila["completeness_total"],
    }
    assert fila["completeness_total"] > 0


async def test_la_lista_va_por_estado_y_luego_por_numero_y_deja_fuera_los_abiertos(
    app: FastAPI, dos_aseguradoras: tuple[str, str]
) -> None:
    propia, _ = dos_aseguradoras
    esperando = await nuevo_caso(propia, estado=CaseState.AWAITING_INSURED)
    derivado_a = await nuevo_caso(propia, estado=CaseState.DERIVED)
    derivado_b = await nuevo_caso(propia, estado=CaseState.DERIVED)
    capturando = await nuevo_caso(propia, estado=CaseState.CAPTURING)
    abierto = await nuevo_caso(propia, estado=CaseState.OPEN)

    async with cliente(app) as http:
        filas = (await http.get(_lista(propia))).json()["items"]

    ids = [fila["case_id"] for fila in filas]
    assert abierto not in ids, "un caso abierto, vacio, no ensena lo que es un caso"
    derivados = sorted(
        [derivado_a, derivado_b],
        key=lambda c: next(f["case_number"] for f in filas if f["case_id"] == c),
    )
    # El camino de un caso: toma datos, queda con un ajustador, espera al asegurado.
    assert ids == [capturando, *derivados, esperando]


async def test_la_lista_no_trae_casos_de_otra_aseguradora(
    app: FastAPI, dos_aseguradoras: tuple[str, str]
) -> None:
    propia, ajena = dos_aseguradoras
    mio = await nuevo_caso(propia)
    ajeno = await nuevo_caso(ajena)

    async with cliente(app) as http:
        ids = {fila["case_id"] for fila in (await http.get(_lista(propia))).json()["items"]}

    assert ids == {mio}
    assert ajeno not in ids


@pytest.mark.parametrize("origen", ORIGENES_AJENOS)
async def test_la_lista_no_trae_casos_que_no_son_del_generador(
    app: FastAPI, dos_aseguradoras: tuple[str, str], origen: Origin
) -> None:
    """La compuerta de la lista: un caso de visitante no sale, ni su numero ni su id."""
    propia, _ = dos_aseguradoras
    de_ejemplo = await nuevo_caso(propia)
    ajeno = await nuevo_caso(propia, origen=origen)
    numero_ajeno = await _numero(propia, ajeno)

    async with cliente(app) as http:
        respuesta = await http.get(_lista(propia))

    ids = [fila["case_id"] for fila in respuesta.json()["items"]]
    assert ids == [de_ejemplo], "la lista dejo salir un caso que no es del generador"
    # Ni el identificador ni el numero aparecen en ningun sitio del cuerpo.
    assert ajeno not in respuesta.text
    assert numero_ajeno not in respuesta.text


async def test_la_lista_publica_no_emite_cookies_ni_pide_credencial(
    app: FastAPI, dos_aseguradoras: tuple[str, str]
) -> None:
    propia, _ = dos_aseguradoras
    await nuevo_caso(propia)

    async with cliente(app) as http:
        respuesta = await http.get(_lista(propia))

    assert respuesta.status_code == 200
    assert "set-cookie" not in respuesta.headers


# --- El detalle -----------------------------------------------------------------


async def test_el_detalle_de_un_caso_de_ejemplo_sale_con_sus_seis_bloques(
    app: FastAPI, dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """El control positivo del detalle, con lo anotado en claro: son datos sinteticos."""
    propia, _ = dos_aseguradoras
    caso = await nuevo_caso(propia, estado=CaseState.DERIVED)
    await casos.set_field(
        propia,
        CaseField(
            case_id=caso,
            field_key="injuries",
            value=cifrador.seal("nadie salió herido"),
            status=FieldStatus.CONFIRMED,
            evidence_turn_id="turno-heridos",
            confirmed_aloud_at=AHORA,
            updated_at=AHORA,
        ),
        cipher=cifrador,
        actor=Actor(actor_type=ActorType.SYSTEM),
    )

    async with cliente(app) as http:
        respuesta = await http.get(_detalle(propia, caso))

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["case_id"] == caso
    assert cuerpo["case_number"] == await _numero(propia, caso)
    heridos = next(c for c in cuerpo["fields"] if c["field_key"] == "injuries")
    assert heridos["value"] == "nadie salió herido"
    for bloque in ("transcript", "coverage_answers", "fired_rules", "control_findings"):
        assert bloque in cuerpo
    assert "set-cookie" not in respuesta.headers


async def test_el_detalle_no_ofrece_ninguna_accion(
    app: FastAPI, dos_aseguradoras: tuple[str, str]
) -> None:
    """Se lee y nada mas. Para decidir un caso como ajustador, se crea el propio en el chat."""
    propia, _ = dos_aseguradoras
    caso = await nuevo_caso(propia, estado=CaseState.DERIVED)

    # El control: con credencial, el mismo caso SI ofrece acciones. Sin esto, la
    # asercion de abajo pasaria contra una ruta que nunca ofrece nada.
    async with cliente(app, credencial=credencial_de(propia)) as staff:
        con_credencial = (await staff.get(f"/api/inbox/{propia}/cases/{caso}")).json()
    assert con_credencial["available_actions"], "el caso derivado deberia ofrecer decidir"
    assert con_credencial["can_correct_fields"] is True

    async with cliente(app) as http:
        publico = (await http.get(_detalle(propia, caso))).json()

    assert publico["available_actions"] == []
    assert publico["can_correct_fields"] is False


@pytest.mark.parametrize("origen", ORIGENES_AJENOS)
async def test_el_detalle_de_un_caso_de_visitante_responde_igual_que_uno_inexistente(
    app: FastAPI, dos_aseguradoras: tuple[str, str], origen: Origin
) -> None:
    """La compuerta del detalle, comparando respuestas **enteras**.

    Un `404` distinto para el caso de un visitante diria a quien prueba
    identificadores cuales existen, y esta pagina no puede confirmarlo.
    """
    propia, _ = dos_aseguradoras
    de_ejemplo = await nuevo_caso(propia)
    ajeno = await nuevo_caso(propia, origen=origen)

    async with cliente(app) as http:
        control = await http.get(_detalle(propia, de_ejemplo))
        respuesta = await http.get(_detalle(propia, ajeno))
    inexistente = await _inexistente(app, propia)

    assert control.status_code == 200, "el caso del generador deberia abrirse"
    assert respuesta.status_code == 404
    assert _sin_rastro(respuesta) == _sin_rastro(inexistente)
    assert ajeno not in respuesta.text


async def test_un_caso_de_ejemplo_de_otra_aseguradora_responde_igual_que_uno_inexistente(
    app: FastAPI, dos_aseguradoras: tuple[str, str]
) -> None:
    propia, ajena = dos_aseguradoras
    de_ajena = await nuevo_caso(ajena)

    async with cliente(app) as http:
        control = await http.get(_detalle(ajena, de_ajena))
        respuesta = await http.get(_detalle(propia, de_ajena))
    inexistente = await _inexistente(app, propia)

    assert control.status_code == 200, "el caso deberia abrirse en su propia aseguradora"
    assert respuesta.status_code == 404
    assert _sin_rastro(respuesta) == _sin_rastro(inexistente)


@pytest.mark.parametrize("identificador", ["'; DROP TABLE case_record; --", "%00", "x" * 500])
async def test_un_identificador_raro_responde_igual_que_uno_inexistente(
    app: FastAPI, dos_aseguradoras: tuple[str, str], identificador: str
) -> None:
    propia, _ = dos_aseguradoras
    async with cliente(app) as http:
        respuesta = await http.get(_detalle(propia, identificador))
    inexistente = await _inexistente(app, propia)

    assert respuesta.status_code == 404
    assert _sin_rastro(respuesta) == _sin_rastro(inexistente)


async def test_una_aseguradora_que_no_existe_responde_el_404_de_siempre(
    app: FastAPI, dos_aseguradoras: tuple[str, str]
) -> None:
    propia, _ = dos_aseguradoras
    caso = await nuevo_caso(propia)

    async with cliente(app) as http:
        lista = await http.get(_lista("aseguradora-que-no-existe"))
        detalle = await http.get(_detalle("aseguradora-que-no-existe", caso))
    inexistente = await _inexistente(app, propia)

    assert lista.status_code == 404
    assert detalle.status_code == 404
    assert _sin_rastro(lista) == _sin_rastro(inexistente)
    assert _sin_rastro(detalle) == _sin_rastro(inexistente)


# --- Lo que la siembra deja evaluado ---------------------------------------------


async def test_un_caso_de_ejemplo_sembrado_muestra_las_reglas_que_lo_dejaron_donde_esta(
    app: FastAPI,
) -> None:
    """La contradiccion que se veia: «sin ajustador, lo cerraron las reglas» y, dos renglones
    arriba, «todavia no paso por el motor de reglas».

    Se siembra con la siembra de verdad y se lee por la ruta publica, sin credencial. El
    cerrado por las reglas trae categoria, las reglas que dispararon y la respuesta «regla»
    de la explicacion ocupada. El control es el de captura: no pasa por las reglas, igual que en
    vivo, y sigue diciendolo (sin categoria, y la respuesta «regla» vacia).
    """
    registros = {r.case_key: r for r in load_seeded_cases(paths.data_dir())}
    cerrado = registros["SEED/sunmeadow/en/closed"]
    captura = registros["SEED/sunmeadow/en/capturing"]
    sembrado = await synthetic_seed.seed_case(cerrado, cipher=crypto.active(), now=AHORA)
    en_captura = await synthetic_seed.seed_case(captura, cipher=crypto.active(), now=AHORA)

    async with cliente(app) as http:
        con_reglas = await http.get(_detalle(cerrado.tenant_id, sembrado.case_id))
        sin_reglas = await http.get(_detalle(captura.tenant_id, en_captura.case_id))

    assert con_reglas.status_code == 200, con_reglas.text
    cuerpo = con_reglas.json()
    assert cuerpo["state"] == "closed"
    assert cuerpo["explanation"]["decided_by_kind"] == "system"
    assert cuerpo["rule_category"] == sembrado.rule_category
    assert cuerpo["rule_category"] is not None
    assert cuerpo["fired_rules"], "el cerrado por reglas no dice que regla lo permitio"
    assert cuerpo["explanation"]["rule"] == "present"

    assert sin_reglas.status_code == 200, sin_reglas.text
    assert sin_reglas.json()["rule_category"] is None
    assert sin_reglas.json()["fired_rules"] == []
    assert sin_reglas.json()["explanation"]["rule"] == "none"


@pytest.mark.parametrize(
    ("clave", "tipo_esperado"),
    [
        # Cierres que en vivo solo pone el personal: aprobado, rechazado y el envio de la agencia.
        ("SEED/stonecroft/es/closed-approved", "staff"),
        ("SEED/sunmeadow/en/closed-rejected", "staff"),
        ("SEED/knotwell/es/closed", "staff"),
        # Y el que cierran las reglas, que sigue sin ajustador.
        ("SEED/sunmeadow/en/closed", "system"),
    ],
)
async def test_un_ejemplo_cerrado_dice_quien_lo_cerro_y_la_pagina_publica_no_nombra_a_nadie(
    app: FastAPI, clave: str, tipo_esperado: str
) -> None:
    """Lo que viaja por el cable sin credencial: el tipo de quien cerro, y nunca su identificador.

    Antes de esto la siembra cerraba todo con el sistema y la pagina decia «Sin decision
    registrada» de un caso aprobado. Ahora el tipo es `staff` donde en vivo cierra el personal, y
    `system` donde cierran las reglas. El identificador de la persona de la aseguradora se parece
    demasiado a una credencial para una pagina publica, asi que no sale; el **control** es la
    misma lectura con credencial, que si lo trae: sin el, la asercion de ausencia pasaria contra un
    dato que nadie escribio.
    """
    registro = next(r for r in load_seeded_cases(paths.data_dir()) if r.case_key == clave)
    sembrado = await synthetic_seed.seed_case(registro, cipher=crypto.active(), now=AHORA)
    autor = synthetic_seed.closing_actor_for(registro)

    async with cliente(app) as http:
        publica = await http.get(_detalle(registro.tenant_id, sembrado.case_id))
    async with cliente(app, credencial=credencial_de(registro.tenant_id)) as staff:
        con_credencial = await staff.get(
            f"/api/inbox/{registro.tenant_id}/cases/{sembrado.case_id}"
        )

    assert publica.status_code == 200, publica.text
    explicacion = publica.json()["explanation"]
    assert explicacion["decided_by"] == "present"
    assert explicacion["decided_by_kind"] == tipo_esperado
    assert explicacion["decided_by_id"] is None
    assert explicacion["decided_at_iso"] is not None

    assert con_credencial.status_code == 200, con_credencial.text
    del_personal = con_credencial.json()["explanation"]
    assert del_personal["decided_by_kind"] == tipo_esperado
    if tipo_esperado == "staff":
        assert autor.actor_id
        assert del_personal["decided_by_id"] == autor.actor_id
        # En ningun renglon de la respuesta publica, ni como valor: no solo en el campo.
        assert f'"{autor.actor_id}"' not in publica.text
    else:
        assert del_personal["decided_by_id"] is None


async def test_lo_sembrado_no_le_muestra_al_publico_reglas_de_monto_cobertura_ni_fraude(
    app: FastAPI,
) -> None:
    """La pagina publica oculta las reglas que leen lo que anota un ajustador; la evaluacion
    que deja la siembra no lleva ninguna de esas, asi que no hay nada que ocultar ni filtrado
    que se rompa. Se comprueba con la respuesta de la ruta publica de cada cerrado de una
    aseguradora: lo que ve el publico es exactamente lo guardado."""
    cerrados = [
        r
        for r in load_seeded_cases(paths.data_dir())
        if r.tenant_id == "sunmeadow" and r.state.value == "closed"
    ]
    assert cerrados
    ocultas = reglas.rule_ids_reading(
        tenant_id="sunmeadow", fields=frozenset(triage_notes.NOTED_FIELDS)
    )
    assert ocultas, "el control: la aseguradora si tiene reglas de monto, cobertura o fraude"

    for registro in cerrados:
        sembrado = await synthetic_seed.seed_case(registro, cipher=crypto.active(), now=AHORA)
        (guardada,) = await reglas.evaluations_for(registro.tenant_id, sembrado.case_id)
        async with cliente(app) as http:
            publico = await http.get(_detalle(registro.tenant_id, sembrado.case_id))

        assert publico.status_code == 200, publico.text
        vistas = publico.json()["fired_rules"]
        assert vistas == [r.id for r in guardada.fired_rules], registro.case_key
        assert set(vistas).isdisjoint(ocultas), registro.case_key
