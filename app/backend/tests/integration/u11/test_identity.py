"""BR1.1, BR1.2, BR1.4, BR1.5: identidad, poliza y partes, contra la base de verdad.

Se escriben aqui, en la nube, y se corren en la sesion local con Docker
levantado (CG-U11-5): ninguna prueba de este archivo llama al proveedor, pero
todas tocan `case_record` o `policy_rag.corpus`, que es lo que las hace de
integracion.
"""

from __future__ import annotations

import pytest

from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.case_record.models import Channel, Origin, PartyRole, RecordType
from untangle.orchestration.nodes.intake import identity
from untangle.policy_rag.corpus import api as corpus
from untangle.policy_rag.corpus.models import IssuedPolicy

from .conftest import AHORA, nuevo_caso, sembrar_poliza

pytestmark = pytest.mark.usefixtures("base_de_u11")


async def _por_numero(tenant_id: str, policy_number: str) -> IssuedPolicy | None:
    """Adapta `corpus.find_policy` (parametro con nombre) a `PolicyLookupPort`.

    La misma adaptacion que hara la raiz de composicion al cablear el nodo de
    verdad (docstring de `identity.py`): aqui se escribe una vez para que las
    pruebas no repitan el `lambda` en cada llamada.
    """
    return await corpus.find_policy(tenant_id, policy_number=policy_number)


async def _por_cedula(tenant_id: str, national_id: str) -> IssuedPolicy | None:
    return await corpus.find_policy_by_national_id(tenant_id, national_id=national_id)


# --- BR1.1: el caso se abre en el primer turno -------------------------------


async def test_reportar_un_siniestro_abre_un_caso_de_tipo_claim(
    dos_aseguradoras: tuple[str, str],
) -> None:
    tenant_id = dos_aseguradoras[0]
    vista = await identity.open_case(
        tenant_id,
        identity.OpeningRequest(
            case_id="u11-abre-siniestro",
            intent=identity.ReportIntent.CLAIM,
            channel=Channel.CHAT,
            origin=Origin.PUBLIC_CHAT,
            language="es",
        ),
        now=AHORA,
    )
    assert vista.record_type is RecordType.CLAIM
    # Los cinco campos obligatorios de `fields.yaml`, incluida la pregunta de
    # seguridad (AC1.5.1): el tipo decide el denominador, no esta funcion. El
    # vehiculo y las otras personas son opcionales y quedan fuera de la cuenta
    # desde P4 (2026-10-06).
    assert vista.completeness.total == 5


async def test_preguntar_por_cobertura_abre_un_caso_sin_pregunta_de_seguridad(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """AC1.3.6, FD-U4-7: la consulta de cobertura no trae la pregunta de seguridad."""
    tenant_id = dos_aseguradoras[0]
    vista = await identity.open_case(
        tenant_id,
        identity.OpeningRequest(
            case_id="u11-abre-consulta",
            intent=identity.ReportIntent.COVERAGE_INQUIRY,
            channel=Channel.CHAT,
            origin=Origin.PUBLIC_CHAT,
            language="es",
        ),
        now=AHORA,
    )
    assert vista.record_type is RecordType.COVERAGE_INQUIRY
    assert vista.completeness.total == 2


# --- BR1.2: la compuerta dura ------------------------------------------------


async def test_poliza_de_otra_aseguradora_responde_igual_que_una_inexistente(
    dos_aseguradoras: tuple[str, str],
) -> None:
    propia, ajena = dos_aseguradoras
    await sembrar_poliza(ajena, policy_number="POL-32")

    resultado_ajena = await identity.identify_by_policy_number(propia, "POL-32", lookup=_por_numero)
    resultado_inexistente = await identity.identify_by_policy_number(
        propia, "POL-99", lookup=_por_numero
    )

    assert resultado_ajena.outcome is identity.IdentificationOutcome.NOT_FOUND
    assert resultado_ajena == resultado_inexistente


async def test_poliza_propia_se_identifica(dos_aseguradoras: tuple[str, str]) -> None:
    propia = dos_aseguradoras[0]
    await sembrar_poliza(propia, policy_number="POL-50")

    resultado = await identity.identify_by_policy_number(propia, "POL-50", lookup=_por_numero)
    assert resultado.outcome is identity.IdentificationOutcome.IDENTIFIED
    assert resultado.policy is not None
    assert resultado.policy.policy_number == "POL-50"


async def test_identifica_por_cedula_del_titular_contra_la_poliza_real(
    dos_aseguradoras: tuple[str, str],
) -> None:
    propia = dos_aseguradoras[0]
    await sembrar_poliza(propia, policy_number="POL-50", national_id="43218907")

    resultado = await identity.identify_by_national_id(propia, "43218907", lookup=_por_cedula)
    assert resultado.outcome is identity.IdentificationOutcome.IDENTIFIED
    assert resultado.policy is not None
    assert resultado.policy.policy_number == "POL-50"


async def test_cedula_de_otra_aseguradora_responde_igual_que_una_inexistente(
    dos_aseguradoras: tuple[str, str],
) -> None:
    propia, ajena = dos_aseguradoras
    await sembrar_poliza(ajena, policy_number="POL-32", national_id="99887766")

    resultado_ajena = await identity.identify_by_national_id(propia, "99887766", lookup=_por_cedula)
    resultado_inexistente = await identity.identify_by_national_id(
        propia, "00000000", lookup=_por_cedula
    )
    assert resultado_ajena == resultado_inexistente
    assert resultado_ajena.outcome is identity.IdentificationOutcome.NOT_FOUND


# --- BR1.4: el caso de otra persona no existe para quien pregunta -----------


async def test_un_caso_de_otra_aseguradora_y_uno_inexistente_devuelven_lo_mismo(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La garantia la da U4 (`get_case_by_number`); esta prueba la fija en U11
    para que ninguna version futura de este modulo le anada una rama."""
    propia, ajena = dos_aseguradoras
    caso_ajeno = await nuevo_caso(ajena)

    vista_ajena = await casos.get_case_by_number(propia, caso_ajeno.case_id)
    vista_inexistente = await casos.get_case_by_number(propia, "no-existe-este-caso")

    assert vista_ajena is None
    assert vista_ajena == vista_inexistente


# --- BR1.5: el tercero que reporta -------------------------------------------


async def test_registra_al_tercero_que_reporta_solo_con_lo_que_aporto(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    tenant_id = dos_aseguradoras[0]
    caso = await nuevo_caso(tenant_id)
    tercero = identity.ThirdPartyReporter(name="Ana Torres", relation="vecina del asegurado")

    registrado = await identity.register_reporter(
        tenant_id,
        case_id=caso.case_id,
        party_id="u11-tercero-1",
        reporter=tercero,
        language="es",
        cipher=cifrador,
    )

    # AC1.4.1: el quinto rol, no `WITNESS` (FD-U11-5 corregida).
    assert registrado.role is PartyRole.REPORTER
    assert registrado.relation == "vecina del asegurado"
    partes = await casos.parties_of(tenant_id, caso.case_id)
    assert len(partes) == 1
    assert partes[0].party_id == "u11-tercero-1"
    assert partes[0].role is PartyRole.REPORTER
    assert partes[0].relation == "vecina del asegurado"
    assert partes[0].name is not None
    assert cifrador.unseal(partes[0].name, stored_key_id=cifrador.id) == "Ana Torres"


async def test_un_tercero_sin_contacto_no_registra_contacto_inventado(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """BR1.8, `parties.py`: lo que no se sabe queda vacio, nunca un valor supuesto."""
    tenant_id = dos_aseguradoras[0]
    caso = await nuevo_caso(tenant_id)
    tercero = identity.ThirdPartyReporter(relation="companero de trabajo")

    registrado = await identity.register_reporter(
        tenant_id,
        case_id=caso.case_id,
        party_id="u11-tercero-2",
        reporter=tercero,
        language="es",
        cipher=cifrador,
    )

    assert registrado.name is None
    assert registrado.contact is None
    partes = await casos.parties_of(tenant_id, caso.case_id)
    assert partes[0].name is None
    assert partes[0].contact is None


async def test_la_relacion_del_tercero_se_guarda_redactada(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """PASO 0 de la tanda 2: un dato personal colado en la relacion no sobrevive.

    "Se llama Ana Torres" trae un nombre propio dentro de la relacion misma --
    la persona podia haberlo dicho asi -- y M6 exige que pase por el punto
    unico de redaccion antes de persistirse, igual que cualquier otro texto
    dictado (BR2.3).
    """
    tenant_id = dos_aseguradoras[0]
    caso = await nuevo_caso(tenant_id)
    tercero = identity.ThirdPartyReporter(relation="es mi vecina, se llama Ana Torres")

    registrado = await identity.register_reporter(
        tenant_id,
        case_id=caso.case_id,
        party_id="u11-tercero-3",
        reporter=tercero,
        language="es",
        cipher=cifrador,
    )

    assert registrado.relation is not None
    assert "Ana Torres" not in registrado.relation
    partes = await casos.parties_of(tenant_id, caso.case_id)
    assert partes[0].relation is not None
    assert "Ana Torres" not in partes[0].relation
