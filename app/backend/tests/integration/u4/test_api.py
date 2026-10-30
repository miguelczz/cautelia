"""Las seis operaciones del contrato C-12, contra PostgreSQL de verdad.

Lo que se prueba aqui no se puede probar en memoria: que la politica de fila
filtre antes de que el codigo mire, que el valor llegue cifrado a la columna, y
que un rechazo deje su entrada aunque la operacion levante.

La prueba del cifrado **lee la columna cruda** y no el objeto que devuelve el
repositorio. Leer el objeto comprobaria que el codigo hace lo que el codigo
dice; leer la columna comprueba lo que un volcado de la base ensenaria.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from untangle.case_record import (
    api,
    crypto,
    history,
    repository,
    rules,
    schema_loading,
    transcript,
)
from untangle.case_record.models import (
    Actor,
    ActorType,
    AttachmentKind,
    AttachmentState,
    CaseField,
    CaseState,
    ChangeKind,
    Channel,
    ClosingEvidence,
    ClosingRejectedError,
    DerivationReason,
    FieldStatus,
    InvalidTransitionError,
    Origin,
    RecordType,
    Resolution,
    Speaker,
)
from untangle.compliance.redaction.api import redact
from untangle.tenancy import ephemeral, session

AHORA = datetime(2026, 9, 20, 15, 0, tzinfo=UTC)
AGENTE = Actor(actor_type=ActorType.AGENT)

PRESENTE = AttachmentState(kind=AttachmentKind.PRESENT, reference="ref-1")
SIN_EVALUAR = AttachmentState(kind=AttachmentKind.NOT_EVALUATED)
COMPLETA = ClosingEvidence(
    transcript=PRESENTE,
    cited_clauses=PRESENTE,
    fired_rules=PRESENTE,
    trace_id=PRESENTE,
    control_results=PRESENTE,
)


@pytest.fixture
def cifrador(monkeypatch: pytest.MonkeyPatch) -> crypto.Cipher:
    monkeypatch.setenv(crypto.KEY_ENV_VAR, crypto.generate_key())
    return crypto.Cipher.from_settings()


def contexto(**cambios: object) -> rules.TransitionContext:
    base = {"now": AHORA, "actor": AGENTE, "channel": Channel.CHAT}
    return rules.TransitionContext(**{**base, **cambios})  # type: ignore[arg-type]


async def _abrir(tenant_id: str = "stonecroft", case_id: str = "CASO-1") -> api.CaseView:
    return await api.create_case(
        tenant_id,
        api.NewCase(
            case_id=case_id,
            record_type=RecordType.CLAIM,
            channel=Channel.CHAT,
            origin=Origin.PUBLIC_CHAT,
            language="es",
        ),
        now=AHORA,
    )


# --- Abrir y leer -------------------------------------------------------------


async def test_un_caso_nuevo_nace_con_su_numero_y_cero_de_cinco(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    vista = await _abrir()

    assert vista.case_number.startswith("STO-")
    assert vista.state is CaseState.OPEN
    # Cinco obligatorios: los dos opcionales del siniestro no cuentan (P4, 2026-10-06).
    assert (vista.completeness.complete, vista.completeness.total) == (0, 5)


async def test_dos_casos_de_la_misma_aseguradora_no_repiten_numero(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    primero = await _abrir(case_id="CASO-1")
    segundo = await _abrir(case_id="CASO-2")

    assert primero.case_number != segundo.case_number


async def test_un_tipo_sin_campos_no_abre_caso(
    sesiones: ephemeral.EphemeralDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un caso con completitud 0/0 se podria cerrar sin haber capturado nada (BR1.6).

    Hasta U19 lo ejercia `quote_request`, que estaba vacio a proposito; ahora declara
    sus diecisiete campos. La guarda se prueba vaciando ese tipo en el esquema: **lo
    que se protege es que un tipo sin campos no abra caso**, no que `quote_request` en
    particular este vacio. Su gemela unitaria
    (`unit/case_record/test_fields.py`) cubre la misma regla en `completeness_of`;
    esta cubre el otro sitio donde se comprueba, que es la creacion por la API.
    """
    vaciado = {**schema_loading.fields_by_record_type(), RecordType.QUOTE_REQUEST: ()}
    monkeypatch.setattr(schema_loading, "fields_by_record_type", lambda: vaciado)

    with pytest.raises(Exception, match="quote_request"):
        await api.create_case(
            "stonecroft",
            api.NewCase(
                case_id="CASO-X",
                record_type=RecordType.QUOTE_REQUEST,
                channel=Channel.CHAT,
                origin=Origin.PUBLIC_CHAT,
                language="es",
            ),
            now=AHORA,
        )


# --- El aislamiento (SEC-U4.3, SEC-U4.14) -------------------------------------


async def test_un_caso_de_otra_aseguradora_responde_igual_que_uno_inexistente(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Y no porque se compare y se disimule: la politica de fila filtra antes.

    Es la prueba que sostiene que el numero de caso no es una credencial. Quien
    prueba numeros no puede confirmar que uno ajeno existe.
    """
    await _abrir(tenant_id="stonecroft", case_id="CASO-DE-STONECROFT")

    ajeno = await api.get_case("sunmeadow", "CASO-DE-STONECROFT")
    inexistente = await api.get_case("sunmeadow", "CASO-QUE-NUNCA-EXISTIO")

    assert ajeno is None
    assert ajeno == inexistente


# --- El cifrado llega a la columna (SEC-U4.8) ---------------------------------


async def test_el_valor_del_campo_llega_cifrado_a_la_columna(
    sesiones: ephemeral.EphemeralDatabase, cifrador: crypto.Cipher
) -> None:
    """Se lee la columna cruda, no el objeto que devuelve el repositorio.

    Leer el objeto comprobaria que el codigo hace lo que dice; leer la columna
    comprueba lo que un volcado de la base ensenaria.
    """
    await _abrir()
    await api.set_field(
        "stonecroft",
        CaseField(
            case_id="CASO-1",
            field_key="description",
            value=cifrador.seal("Me choco un carro en la Calle 42"),
            status=FieldStatus.STATED,
            evidence_turn_id="turno-1",
            updated_at=AHORA,
        ),
        cipher=cifrador,
        actor=AGENTE,
    )

    async with session.session_for("stonecroft") as sesion:
        fila = await session.fetch_one(
            sesion, "SELECT value, sealed_key_id FROM case_field WHERE field_key = 'description'"
        )

    assert fila is not None
    assert b"Calle 42" not in bytes(fila["value"])
    assert b"choco" not in bytes(fila["value"])
    assert fila["sealed_key_id"] == cifrador.id


async def test_la_copia_del_historial_tambien_llega_cifrada(
    sesiones: ephemeral.EphemeralDatabase, cifrador: crypto.Cipher
) -> None:
    """Dejarla en claro desharia el cifrado para todo lo que se corrigio."""
    await _abrir()
    await api.set_field(
        "stonecroft",
        CaseField(
            case_id="CASO-1",
            field_key="description",
            value=cifrador.seal("Me choco un carro en la Calle 42"),
            status=FieldStatus.STATED,
            evidence_turn_id="turno-1",
            updated_at=AHORA,
        ),
        cipher=cifrador,
        actor=AGENTE,
    )

    async with session.session_for("stonecroft") as sesion:
        fila = await session.fetch_one(
            sesion, "SELECT new_value, sealed_key_id FROM case_change LIMIT 1"
        )

    assert fila is not None
    assert b"Calle 42" not in bytes(fila["new_value"])
    assert fila["sealed_key_id"] == cifrador.id


async def test_corregir_un_campo_guarda_el_valor_anterior_sellado(
    sesiones: ephemeral.EphemeralDatabase, cifrador: crypto.Cipher
) -> None:
    """El historial dice que habia antes, y esa es la mitad de su utilidad."""
    await _abrir()
    for texto in ("Calle 42", "Carrera 7"):
        await api.set_field(
            "stonecroft",
            CaseField(
                case_id="CASO-1",
                field_key="location",
                value=cifrador.seal(texto),
                status=FieldStatus.CONFIRMED,
                evidence_turn_id="turno-1",
                # El lugar exige lectura de confirmacion (BR2.2): sin esta marca
                # no llega a confirmado, y el esquema lo rechaza.
                confirmed_aloud_at=AHORA,
                updated_at=AHORA,
            ),
            cipher=cifrador,
            actor=AGENTE,
        )

    entradas = await history.of_case("stonecroft", "CASO-1")
    ultima = entradas[-1]

    assert ultima.previous_value is not None
    assert cifrador.unseal(ultima.previous_value, stored_key_id=cifrador.id) == "Calle 42"
    assert ultima.new_value is not None
    assert cifrador.unseal(ultima.new_value, stored_key_id=cifrador.id) == "Carrera 7"


# --- La completitud sube ------------------------------------------------------


async def test_la_completitud_sube_al_fijar_un_campo(
    sesiones: ephemeral.EphemeralDatabase, cifrador: crypto.Cipher
) -> None:
    await _abrir()
    await api.set_field(
        "stonecroft",
        CaseField(
            case_id="CASO-1",
            field_key="description",
            value=cifrador.seal("Me choco un carro"),
            status=FieldStatus.STATED,
            evidence_turn_id="turno-1",
            updated_at=AHORA,
        ),
        cipher=cifrador,
        actor=AGENTE,
    )

    vista = await api.get_case("stonecroft", "CASO-1")

    assert vista is not None
    assert vista.completeness.complete == 1


async def test_un_campo_que_el_tipo_no_declara_no_se_guarda(
    sesiones: ephemeral.EphemeralDatabase, cifrador: crypto.Cipher
) -> None:
    """Falla en el acto en vez de escribir algo que despues nadie sabria contar."""
    await _abrir()

    with pytest.raises(Exception, match=r"question_asked|no declara"):
        await api.set_field(
            "stonecroft",
            CaseField(
                case_id="CASO-1",
                field_key="question_asked",
                value=cifrador.seal("algo"),
                status=FieldStatus.STATED,
                evidence_turn_id="turno-1",
                updated_at=AHORA,
            ),
            cipher=cifrador,
            actor=AGENTE,
        )


# --- Las transiciones dejan rastro --------------------------------------------


async def test_una_transicion_legal_mueve_el_caso(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    await _abrir()

    vista = await api.apply_transition(
        "stonecroft", "CASO-1", CaseState.CAPTURING, context=contexto()
    )

    assert vista.state is CaseState.CAPTURING


async def test_una_transicion_rechazada_levanta_y_deja_su_entrada(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """La excepcion sale **despues** de que el rastro este guardado.

    Es la diferencia entre un rechazo que se puede auditar y uno que solo
    existio en la memoria del proceso.
    """
    await _abrir()

    with pytest.raises(InvalidTransitionError):
        await api.apply_transition("stonecroft", "CASO-1", CaseState.CLOSED, context=contexto())

    entradas = await history.of_case("stonecroft", "CASO-1")

    assert [e.change_kind for e in entradas] == [ChangeKind.TRANSITION_REJECTED]
    vista = await api.get_case("stonecroft", "CASO-1")
    assert vista is not None
    assert vista.state is CaseState.OPEN


async def test_cerrar_sin_un_adjunto_lo_nombra_y_deja_su_entrada(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    await _abrir()
    await api.apply_transition("stonecroft", "CASO-1", CaseState.CAPTURING, context=contexto())
    await api.apply_transition("stonecroft", "CASO-1", CaseState.VERIFYING, context=contexto())
    await api.apply_transition("stonecroft", "CASO-1", CaseState.DECIDING, context=contexto())

    with pytest.raises(ClosingRejectedError, match="trace_id"):
        await api.close_case(
            "stonecroft",
            "CASO-1",
            resolution=Resolution.APPROVED,
            closing_evidence=COMPLETA.model_copy(update={"trace_id": SIN_EVALUAR}),
            context=contexto(),
        )

    entradas = await history.of_case("stonecroft", "CASO-1")

    assert entradas[-1].change_kind is ChangeKind.CLOSE_REJECTED


async def test_cerrar_con_todo_guarda_la_evidencia_con_el_caso(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Un caso cerrado expone que se comprobo al cerrarlo (NFR-U4-9)."""
    await _abrir()
    for destino in (CaseState.CAPTURING, CaseState.VERIFYING, CaseState.DECIDING):
        await api.apply_transition("stonecroft", "CASO-1", destino, context=contexto())

    vista = await api.close_case(
        "stonecroft",
        "CASO-1",
        resolution=Resolution.APPROVED,
        closing_evidence=COMPLETA,
        context=contexto(),
    )

    assert vista.state is CaseState.CLOSED
    assert vista.resolution is Resolution.APPROVED
    guardado = await repository.load_case("stonecroft", "CASO-1")
    assert guardado is not None
    assert guardado.closing_evidence == COMPLETA
    assert guardado.closed_at == AHORA


# --- La transcripcion ---------------------------------------------------------


async def test_el_turno_se_guarda_ya_redactado(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    await _abrir()

    turn_id = await api.append_turn(
        "stonecroft",
        transcript.TurnDraft(
            turn_id="turno-1",
            case_id="CASO-1",
            speaker=Speaker.INSURED,
            channel=Channel.CHAT,
            language="es",
            started_at=AHORA,
        ),
        redact("Me llamo Nayibe Quintero y mi telefono es 3001112233", language="es"),
    )

    async with session.session_for("stonecroft") as sesion:
        fila = await session.fetch_one(
            sesion,
            "SELECT text_redacted FROM case_transcript_turn WHERE turn_id = :t",
            t=turn_id,
        )

    assert fila is not None
    assert "Nayibe" not in fila["text_redacted"]
    assert "3001112233" not in fila["text_redacted"]


# --- La superficie no ofrece lo que no debe ofrecer ---------------------------


def test_la_superficie_no_ofrece_editar_ni_borrar_el_historial() -> None:
    """SEC-U4.11 por la via de la ausencia.

    Se comprueba sobre lo exportado y no sobre el archivo entero: una funcion
    privada que editara seria una funcion que alguien puede exportar manana con
    una linea, y esta prueba la veria aparecer.
    """
    # Se busca por **lo que hace**, no por como se llama. Comparar contra cuatro
    # nombres literales dejaba pasar un `amend_change` sin cambiar nada del
    # codigo: afirmaba una convencion de nombres y no la conducta que SEC-U4.11
    # promete. Lo encontro la revision asesora de esta etapa.
    verbos = ("update", "delete", "edit", "remove", "amend", "fix", "modify", "set")
    superficie = [n for n in api.__all__ if not n[0].isupper()]
    superficie += [n for n in dir(history) if not n.startswith("_")]

    sospechosas = [
        nombre
        for nombre in superficie
        if "change" in nombre and any(nombre.startswith(v) for v in verbos)
    ]

    assert sospechosas == []
    # Y la conducta de verdad la comprueba el disparador de la base, en
    # `test_migration.py::test_el_historial_no_se_puede_editar`: esta prueba
    # cubre la superficie, aquella cubre lo que pasa si alguien la rodea.


def test_la_superficie_declara_exactamente_las_operaciones_del_contrato() -> None:
    """Las seis de C-12 mas el cierre, que es la transicion con nombre propio.

    Escrito aqui para que anadir una operacion sea una decision visible: la
    superficie es el acuerdo con ocho unidades, y crecer sin darse cuenta es
    como un acuerdo deja de significar algo.
    """
    operaciones = {nombre for nombre in api.__all__ if not nombre[0].isupper()}

    assert operaciones == {
        "append_turn",
        "apply_transition",
        # Varios casos por su llave, en una consulta, lo pidio la telemetria el
        # 2026-10-09: el tablero de gasto describe cada caso en palabras --tipo,
        # canal y hora-- y pedirlos de a uno eran sesenta consultas por pagina. Es
        # aditivo y solo lee lo que `get_case` ya entrega.
        "cases_by_id",
        "close_case",
        # La conversacion a traves de la cadena de casos la anadio el chat el
        # 2026-10-13: tras cambiar de tema, lo que la agente recuerda y lo que la
        # pantalla recupera al recargar salian solo del caso nuevo. Es aditivo y solo
        # lee; el enlace se escribe al crear (`NewCase.continues_case_id`).
        "conversation_transcript",
        "create_case",
        "get_case",
        # La consulta por numero legible se anadio tras la revision asesora de
        # esta etapa: BR7.3 se dispara al consultar "por su identificador **o
        # por su numero**", y solo existia la primera mitad.
        "get_case_by_number",
        # Las partes del caso las anadio U11 (2026-09-27): la captura registra
        # a las personas y vehiculos que se nombran --incluido quien reporta por
        # otro-- y las lee para no volver a preguntarlas (BR1.5 de U11, FR1.2).
        # Es aditivo: ninguna operacion existente cambia de firma.
        # La apertura del valor de un campo la pidio U11 el 2026-09-29: una lectura
        # de confirmacion tiene que **nombrar** lo que confirma (FD-U11-8), y hasta
        # entonces los valores se sellaban y nadie los volvia a abrir en produccion.
        # Es la puerta simetrica de `set_field`: esta unidad cierra al escribir y
        # abre al leer, con el cifrador por argumento en las dos, y abre solo las
        # claves que le nombran.
        "open_field_values",
        "parties_of",
        "record_change",
        "register_party",
        "set_field",
        # Atar la poliza al caso lo anadio la conversacion el 2026-10-06 (P3): la
        # persona da el numero, el corpus dice el titular, la persona confirma, y el
        # caso queda con la poliza de la que habla; antes `policy_ref` solo se
        # escribia al crear el caso. Es aditivo: ninguna firma existente cambia.
        "set_policy_ref",
        # La lectura de la transcripcion la anadio U10 (2026-09-21): la
        # revision completa de cumplimiento la lee para comprobar la ruta a
        # persona y los datos personales (BR5.1), y le llega por un puerto que
        # arma la raiz de composicion, porque `compliance` no puede importar
        # este modulo sin cerrar un ciclo.
        "transcript_of",
    }


# --- El campo y su entrada son una sola cosa (BR5.1) --------------------------


async def test_si_falla_el_anexado_el_campo_no_queda_escrito(
    sesiones: ephemeral.EphemeralDatabase, cifrador: crypto.Cipher, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un cambio sin rastro no es un cambio: es una perdida.

    Se provoca el fallo del segundo paso y se comprueba que el primero se
    revirtio. Sin la transaccion compartida quedaba un campo escrito y ninguna
    entrada que dijera quien lo puso ahi. Lo encontro la revision asesora.
    """
    await _abrir()

    async def falla(*args: object, **kwargs: object) -> None:
        msg = "fallo provocado al anexar la entrada"
        raise RuntimeError(msg)

    monkeypatch.setattr(history, "append", falla)

    with pytest.raises(RuntimeError, match="fallo provocado"):
        await api.set_field(
            "stonecroft",
            CaseField(
                case_id="CASO-1",
                field_key="description",
                value=cifrador.seal("Me choco un carro"),
                status=FieldStatus.STATED,
                evidence_turn_id="turno-1",
                updated_at=AHORA,
            ),
            cipher=cifrador,
            actor=AGENTE,
        )

    async with session.session_for("stonecroft") as sesion:
        fila = await session.fetch_one(sesion, "SELECT count(*) AS total FROM case_field")

    assert fila is not None
    assert int(fila["total"]) == 0


async def test_si_falla_el_movimiento_la_entrada_tampoco_queda(
    sesiones: ephemeral.EphemeralDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La asimetria inversa: un `transition_applied` de algo que no ocurrio."""
    await _abrir()

    async def falla(*args: object, **kwargs: object) -> None:
        msg = "fallo provocado al mover el caso"
        raise RuntimeError(msg)

    monkeypatch.setattr(repository, "update_case", falla)

    with pytest.raises(RuntimeError, match="fallo provocado"):
        await api.apply_transition("stonecroft", "CASO-1", CaseState.CAPTURING, context=contexto())

    assert await history.of_case("stonecroft", "CASO-1") == ()


# --- Dos que mueven el mismo caso a la vez (2026-10-13) -----------------------
#
# Desde el cierre directo, el sistema y un ajustador pueden mover un caso en los mismos
# segundos. Lo que se prueba es que el que llega tarde no pisa al que llego antes y que
# su intento deja rastro. La carrera se provoca en el unico punto donde existe: entre la
# lectura del caso y su escritura.


def _que_otro_llegue_antes(monkeypatch: pytest.MonkeyPatch, otro: object) -> None:
    """Tras la primera lectura del caso, `otro` lo mueve antes de que se escriba."""
    leer = api._caso_o_error
    paso = False

    async def leer_y_ceder(tenant_id: str, case_id: str) -> object:
        nonlocal paso
        leido = await leer(tenant_id, case_id)
        if not paso:
            paso = True
            await otro()  # type: ignore[operator]
        return leido

    monkeypatch.setattr(api, "_caso_o_error", leer_y_ceder)


async def _hasta_deciding() -> None:
    await _abrir()
    for destino in (CaseState.CAPTURING, CaseState.VERIFYING, CaseState.DECIDING):
        await api.apply_transition("stonecroft", "CASO-1", destino, context=contexto())


async def test_una_derivacion_que_llega_tarde_no_reabre_un_caso_cerrado(
    sesiones: ephemeral.EphemeralDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`closed` es terminal tambien cuando el otro intento ya habia leido el caso."""
    await _hasta_deciding()

    async def cierran_las_reglas() -> None:
        await api.close_case(
            "stonecroft",
            "CASO-1",
            resolution=Resolution.REGISTERED,
            closing_evidence=COMPLETA,
            context=contexto(actor=Actor(actor_type=ActorType.SYSTEM)),
        )

    _que_otro_llegue_antes(monkeypatch, cierran_las_reglas)

    with pytest.raises(InvalidTransitionError, match="otro cambio llego antes"):
        await api.apply_transition(
            "stonecroft",
            "CASO-1",
            CaseState.DERIVED,
            context=contexto(derivation_reason=DerivationReason.RULE),
        )

    guardado = await repository.load_case("stonecroft", "CASO-1")
    assert guardado is not None
    assert guardado.state is CaseState.CLOSED
    assert guardado.resolution is Resolution.REGISTERED
    assert guardado.derivation_reason is None
    entradas = await history.of_case("stonecroft", "CASO-1")
    # El cierre que gano y, despues, el rechazo del que llego tarde: ninguna
    # transicion aplicada hacia `derived`.
    assert [e.change_kind for e in entradas[-2:]] == [
        ChangeKind.TRANSITION_APPLIED,
        ChangeKind.TRANSITION_REJECTED,
    ]


async def test_un_cierre_que_llega_tarde_no_pisa_una_derivacion(
    sesiones: ephemeral.EphemeralDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El caso que alguien tomo no acaba cerrado por las reglas un instante despues."""
    await _hasta_deciding()

    async def lo_toma_un_ajustador() -> None:
        await api.apply_transition(
            "stonecroft",
            "CASO-1",
            CaseState.DERIVED,
            context=contexto(derivation_reason=DerivationReason.RULE),
        )

    _que_otro_llegue_antes(monkeypatch, lo_toma_un_ajustador)

    with pytest.raises(ClosingRejectedError, match="otro cambio llego antes"):
        await api.close_case(
            "stonecroft",
            "CASO-1",
            resolution=Resolution.REGISTERED,
            closing_evidence=COMPLETA,
            context=contexto(actor=Actor(actor_type=ActorType.SYSTEM)),
        )

    guardado = await repository.load_case("stonecroft", "CASO-1")
    assert guardado is not None
    assert guardado.state is CaseState.DERIVED
    assert guardado.resolution is None
    assert guardado.closing_evidence is None
    entradas = await history.of_case("stonecroft", "CASO-1")
    assert entradas[-1].change_kind is ChangeKind.CLOSE_REJECTED


async def test_atar_la_poliza_no_devuelve_el_caso_a_un_estado_anterior(
    sesiones: ephemeral.EphemeralDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Atar la poliza escribe la poliza: no vuelve a escribir el estado que leyo."""
    await _abrir()

    async def empieza_la_captura() -> None:
        await api.apply_transition("stonecroft", "CASO-1", CaseState.CAPTURING, context=contexto())

    _que_otro_llegue_antes(monkeypatch, empieza_la_captura)

    vista = await api.set_policy_ref("stonecroft", "CASO-1", "POL-1")

    assert vista.state is CaseState.CAPTURING
    assert vista.policy_ref == "POL-1"
    guardado = await repository.load_case("stonecroft", "CASO-1")
    assert guardado is not None
    assert guardado.state is CaseState.CAPTURING
    assert guardado.policy_ref == "POL-1"


# --- La otra mitad de BR7.3: la consulta por numero --------------------------


async def test_el_caso_se_encuentra_por_su_numero(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Es lo que una persona anota y teclea."""
    abierto = await _abrir()

    encontrado = await api.get_case_by_number("stonecroft", abierto.case_number)

    assert encontrado is not None
    assert encontrado.case_id == "CASO-1"


async def test_un_numero_de_otra_aseguradora_responde_igual_que_uno_inexistente(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """SEC-U4.14: el numero no es credencial, y adivinarlo no da acceso.

    Sin esta prueba, la verificacion que declara el control no existia. Lo
    encontro la revision asesora de esta etapa.
    """
    abierto = await _abrir(tenant_id="stonecroft")

    ajeno = await api.get_case_by_number("sunmeadow", abierto.case_number)
    inexistente = await api.get_case_by_number("sunmeadow", "AP-999999")

    assert ajeno is None
    assert ajeno == inexistente


# --- La ventana para retomar sale del historial, no de quien llama -----------


async def test_la_marca_de_cuando_derivo_la_pone_u4_y_no_el_consumidor(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Una condicion cuyo insumo aporta entero el consumidor no es una condicion.

    Se lleva el caso a derivado por el limite de la demostracion, y despues se
    pide retomarlo **sin** decir cuando derivo. U4 lo saca de su propio
    historial. Lo pedia la revision asesora de esta etapa.
    """
    await _abrir()
    await api.apply_transition("stonecroft", "CASO-1", CaseState.CAPTURING, context=contexto())

    async with session.session_for("stonecroft") as sesion:
        await session.execute_sql(
            sesion,
            "UPDATE case_record SET derivation_reason = 'demo_limit' WHERE case_id = 'CASO-1'",
        )
    await api.apply_transition("stonecroft", "CASO-1", CaseState.DERIVED, context=contexto())

    marca = await history.derived_at("stonecroft", "CASO-1")

    assert marca == AHORA


async def test_sin_historial_de_derivacion_no_hay_ventana(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Dar por buena una condicion que no se pudo comprobar es como una
    condicion deja de ser una condicion."""
    await _abrir()

    assert await history.derived_at("stonecroft", "CASO-1") is None
