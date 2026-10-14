"""La identidad del personal de la bandeja (US5.7, BR2.1 a BR2.6, SEC-U2.5 a SEC-U2.7).

Dos cosas se prueban aqui de una forma concreta porque de otra no se probarian:

- **El rechazo indistinguible** se comprueba comparando las tres respuestas
  **entre si**, no contra una plantilla escrita a mano. Una plantilla se
  actualiza y deja de detectar que una de las tres divergio.
- **Las dos claves separadas** se comprueban presentando lo firmado con una al
  verificador de la otra y exigiendo rechazo. Que existan dos variables de
  entorno no prueba nada.

El reloj se controla: caducar doce horas de verdad no es una prueba, es una
espera.
"""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from untangle import observability
from untangle.tenancy import staff_identity, visitor_access
from untangle.tenancy.models import (
    Action,
    CredentialRejectedError,
    CredentialRejection,
    Role,
    UnknownTenantError,
)

# Claves de prueba de 32 bytes o mas: es el minimo que exige el codigo, y una
# prueba con una clave corta estaria probando otra cosa.
CLAVE_DE_BANDEJA = "clave-de-prueba-de-la-bandeja-para-la-firma-hs256"
CLAVE_DE_ENLACES = "clave-de-prueba-de-los-enlaces-para-la-firma-hmac"
AHORA = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def permisos_limpios() -> Iterator[None]:
    yield
    staff_identity.reset_permissions()


@pytest.fixture
def eventos() -> Iterator[io.StringIO]:
    """Captura lo que sale por el punto unico de salida."""
    destino = io.StringIO()
    observability.set_stream(destino)
    yield destino
    observability.set_stream(__import__("sys").stdout)


def _emitir(principal: str = "diana", tenant: str = "stonecroft", **extra: object) -> str:
    return staff_identity.issue_credential(
        tenant_id=tenant,
        principal_id=principal,
        signing_key=CLAVE_DE_BANDEJA,
        now=extra.get("now", AHORA),  # type: ignore[arg-type]
    )


def test_la_credencial_lleva_aseguradora_persona_rol_y_caducidad_a_las_doce_horas() -> None:
    """BR2.1, BR2.2, AC5.7.1."""
    token = _emitir()

    credencial = staff_identity.verify_credential(
        token, expected_tenant="stonecroft", signing_key=CLAVE_DE_BANDEJA, now=AHORA
    )

    assert credencial.tenant_id == "stonecroft"
    assert credencial.principal_id == "diana"
    assert credencial.role is Role.ADJUSTER
    assert credencial.issued_at == AHORA
    assert credencial.expires_at == AHORA + timedelta(hours=12)


def test_emitir_para_una_persona_no_declarada_falla_nombrandola() -> None:
    """Emitir para alguien que no esta en la carpeta produciria una credencial
    que despues nadie puede verificar, y el error llegaria doce horas tarde."""
    with pytest.raises(UnknownTenantError) as fallo:
        _emitir(principal="quien-sea")

    assert "quien-sea" in str(fallo.value)
    assert "diana" in str(fallo.value)


def test_las_tres_causas_de_rechazo_producen_respuestas_identicas_entre_si() -> None:
    """AC5.7.2, BR2.4, SEC-U2.6: identicas en bytes, no en significado.

    Se comparan las tres **entre si**. Contra una plantilla, el dia que una
    divergiera la plantilla se actualizaria con ella y nadie se enteraria.
    """
    caducada = _emitir()
    alterada = _emitir()[:-2] + ("aa" if not _emitir().endswith("aa") else "bb")
    de_otra = staff_identity.issue_credential(
        tenant_id="sunmeadow",
        principal_id="marcus-webb",
        signing_key=CLAVE_DE_BANDEJA,
        now=AHORA,
    )

    respuestas = []
    causas = []
    for token, momento in (
        (caducada, AHORA + timedelta(hours=13)),
        (alterada, AHORA),
        (de_otra, AHORA),
    ):
        with pytest.raises(CredentialRejectedError) as fallo:
            staff_identity.verify_credential(
                token,
                expected_tenant="stonecroft",
                signing_key=CLAVE_DE_BANDEJA,
                now=momento,
            )
        respuestas.append((fallo.value.denial.status, fallo.value.denial.body()))
        causas.append(fallo.value.cause)

    # Las tres respuestas, iguales byte a byte.
    assert respuestas[0] == respuestas[1] == respuestas[2]
    # Y las tres causas, distintas: si no, la comparacion de arriba no diria nada
    # porque los tres caminos habrian sido el mismo.
    assert causas == [
        CredentialRejection.EXPIRED,
        CredentialRejection.SIGNATURE_INVALID,
        CredentialRejection.WRONG_TENANT,
    ]


def test_sin_credencial_se_responde_igual_que_con_una_invalida() -> None:
    """Sin cookie, como si el recurso no existiera."""
    with pytest.raises(CredentialRejectedError) as sin:
        staff_identity.verify_credential(
            None, expected_tenant="stonecroft", signing_key=CLAVE_DE_BANDEJA
        )
    with pytest.raises(CredentialRejectedError) as mala:
        staff_identity.verify_credential(
            "no-es-un-token", expected_tenant="stonecroft", signing_key=CLAVE_DE_BANDEJA
        )

    assert sin.value.denial.body() == mala.value.denial.body()


def test_la_clave_de_enlaces_no_valida_una_credencial_de_bandeja() -> None:
    """SEC-U2.5: lo unico que prueba que las dos claves estan separadas.

    Declarar dos variables de entorno no prueba nada; presentar lo firmado con
    una al verificador de la otra, si.
    """
    token = _emitir()

    with pytest.raises(CredentialRejectedError) as fallo:
        staff_identity.verify_credential(
            token, expected_tenant="stonecroft", signing_key=CLAVE_DE_ENLACES, now=AHORA
        )

    assert fallo.value.cause is CredentialRejection.SIGNATURE_INVALID


def test_la_clave_de_bandeja_no_valida_un_enlace_de_caso() -> None:
    """SEC-U2.5, el otro sentido: la separacion vale en las dos direcciones."""
    secreto = "un-secreto"
    firma_de_bandeja = visitor_access._sign(secreto, CLAVE_DE_BANDEJA.encode())
    token_cruzado = f"{secreto}.{firma_de_bandeja}"

    assert not visitor_access._token_valido(token_cruzado, CLAVE_DE_ENLACES.encode())
    assert visitor_access._token_valido(token_cruzado, CLAVE_DE_BANDEJA.encode())


def test_rotar_la_clave_invalida_en_el_acto_lo_firmado_antes() -> None:
    """SEC-U2.10, NFR-U2-3: no hay ventana de gracia ni clave anterior aceptada.

    El costo real de rotar es volver a emitir con un comando; a cambio, una clave
    comprometida deja de servir en el instante en que se rota.
    """
    antes_de_rotar = _emitir()

    with pytest.raises(CredentialRejectedError):
        staff_identity.verify_credential(
            antes_de_rotar,
            expected_tenant="stonecroft",
            signing_key=CLAVE_DE_BANDEJA + "-rotada",
            now=AHORA,
        )


def test_el_agente_de_cuenta_no_decide_un_caso() -> None:
    """AC5.7.3, BR2.5: la fila `account_agent` + `decide_case` de la tabla."""
    token = staff_identity.issue_credential(
        tenant_id="knotwell",
        principal_id="priya-raman",
        signing_key=CLAVE_DE_BANDEJA,
        now=AHORA,
    )
    credencial = staff_identity.verify_credential(
        token, expected_tenant="knotwell", signing_key=CLAVE_DE_BANDEJA, now=AHORA
    )

    # Ver el caso si; decidirlo no. Y la peticion directa recorre este mismo
    # paso que la que viene de la pantalla.
    staff_identity.authorize(credencial, Action.VIEW_CASE)
    with pytest.raises(CredentialRejectedError) as fallo:
        staff_identity.authorize(credencial, Action.DECIDE_CASE)

    assert fallo.value.cause is CredentialRejection.ACTION_NOT_PERMITTED


def test_la_tabla_declara_cada_pareja_de_rol_y_accion() -> None:
    """Ninguna pareja queda sin declarar, que es lo que este chequeo protege.

    Antes decia "el ajustador puede todo", y dejo de ser cierto el 2026-09-28
    cuando U14 anadio `mark_sent`: marcar un caso como enviado a la emisora es de
    la agencia, y una aseguradora que emite decide el caso en vez de traspasarlo.
    Lo que importa no es que un rol pueda todo --eso seria un rol sin limites--
    sino que **nadie se olvide de decidir** una pareja, porque lo que no aparece
    en la tabla se deniega y el sitio donde eso se descubre no puede ser una
    peticion directa a la API.
    """
    declaradas = {(p.role, p.action) for p in staff_identity.permissions()}

    faltan = {(rol, accion) for rol in Role for accion in Action} - declaradas
    assert not faltan, f"la tabla no declara {sorted((r.value, a.value) for r, a in faltan)}"


def test_cada_rol_tiene_lo_suyo_y_no_lo_del_otro() -> None:
    """El ajustador decide y no traspasa; la agencia traspasa y no decide.

    Las dos mitades juntas: con solo una, una tabla que se lo concediera todo a
    los dos pasaria igual.
    """
    assert staff_identity.is_permitted(Role.ADJUSTER, Action.DECIDE_CASE)
    assert not staff_identity.is_permitted(Role.ADJUSTER, Action.MARK_SENT)

    assert staff_identity.is_permitted(Role.ACCOUNT_AGENT, Action.MARK_SENT)
    assert not staff_identity.is_permitted(Role.ACCOUNT_AGENT, Action.DECIDE_CASE)

    # Y el suscriptor, que llego con U19: decide solicitudes de cotizacion y no
    # cobertura (BR4.1). Las dos mitades otra vez, porque la primera sola pasaria
    # igual con un rol que lo pudiera todo.
    assert staff_identity.is_permitted(Role.UNDERWRITER, Action.DECIDE_QUOTE)
    assert not staff_identity.is_permitted(Role.UNDERWRITER, Action.DECIDE_CASE)

    # Y lo que AC6.3.3 pide por su lado: ninguno de los otros dos cotiza.
    assert not staff_identity.is_permitted(Role.ADJUSTER, Action.DECIDE_QUOTE)
    assert not staff_identity.is_permitted(Role.ACCOUNT_AGENT, Action.DECIDE_QUOTE)


def test_una_pareja_que_la_tabla_no_declara_se_deniega(tmp_path: object) -> None:
    """BR2.5: no hay valor por defecto permisivo."""
    staff_identity.install_permissions(())

    assert staff_identity.is_permitted(Role.ADJUSTER, Action.VIEW_CASE) is False


def test_el_rechazo_deja_su_rastro_con_aseguradora_rol_y_causa_real(
    eventos: io.StringIO,
) -> None:
    """SEC-U2.11, NFR-U2-2: la causa real va al rastro, no al cliente."""
    de_otra = staff_identity.issue_credential(
        tenant_id="sunmeadow",
        principal_id="marcus-webb",
        signing_key=CLAVE_DE_BANDEJA,
        now=AHORA,
    )

    with pytest.raises(CredentialRejectedError):
        staff_identity.verify_credential(
            de_otra, expected_tenant="stonecroft", signing_key=CLAVE_DE_BANDEJA, now=AHORA
        )

    registros = [json.loads(linea) for linea in eventos.getvalue().splitlines() if linea.strip()]
    rechazos = [r for r in registros if r["event"] == "tenancy.staff_credential_rejected"]

    assert len(rechazos) == 1
    assert rechazos[0]["attempted_tenant"] == "sunmeadow"
    assert rechazos[0]["asserted_role"] == "adjuster"
    assert rechazos[0]["cause"] == "wrong_tenant"


def test_sin_clave_de_firma_se_falla_en_vez_de_aceptar_o_rechazar_en_silencio() -> None:
    """Verificar sin clave no puede devolver "no vale": seria indistinguible de
    una credencial mala y esconderia un despliegue mal configurado."""
    with pytest.raises(staff_identity.SigningKeyMissingError) as fallo:
        staff_identity.verify_credential(
            "lo-que-sea", expected_tenant="stonecroft", signing_key=None
        )

    assert "UNTANGLE_STAFF_CREDENTIAL_SIGNING_KEY" in str(fallo.value)
