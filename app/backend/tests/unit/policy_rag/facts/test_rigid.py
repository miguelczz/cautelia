"""La respuesta de cada tema rigido, con el valor exacto del registro y la guardia de salida real.

Lo que se comprueba: que el texto trae el dato del registro y no otro, que el tema que no es rigido
no responde, y que ninguna plantilla afirma ni niega cobertura. De los montos: la guardia de salida
los interviene (categoria `amount`), salvo en las dos plantillas que el codigo compone con cifras
del registro --deducible y limites--, que Miguel autorizo el 2026-11-02 por su clave del catalogo.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest

from untangle.base import Locale, RigidTopic
from untangle.compliance.controls import guard, patterns
from untangle.compliance.controls.guard import GuardTurn
from untangle.compliance.controls.models import GuardCategory
from untangle.copy_catalog import api as copy_api
from untangle.policy_rag.corpus.models import IssuedPolicy
from untangle.policy_rag.facts import rigid
from untangle.tenancy import config as tenancy_config

from ...compliance.conftest import contexto_de
from .conftest import poliza

HOY = date(2026, 9, 1)
NBSP = "\xa0"


@pytest.fixture(autouse=True)
def _estado_limpio() -> Iterator[None]:
    copy_api.reset()
    patterns.reset()
    tenancy_config.reset()
    yield
    copy_api.reset()
    patterns.reset()
    tenancy_config.reset()


def test_el_deducible_trae_los_dos_montos_del_registro_y_el_numero_de_poliza(
    poliza_de_ejemplo: IssuedPolicy,
) -> None:
    respuesta = rigid.render(
        RigidTopic.DEDUCTIBLE, poliza_de_ejemplo, language="es", on=HOY, spoken=False
    )

    assert respuesta is not None
    assert respuesta.topic is RigidTopic.DEDUCTIBLE
    assert respuesta.text == (
        f"Según tu póliza POL-99, el deducible de pérdida parcial es ${NBSP}1.500.000 por daños "
        f"y ${NBSP}250.000 por hurto."
    )


def test_el_deducible_en_ingles_usa_el_formato_de_la_pestana(
    poliza_de_ejemplo: IssuedPolicy,
) -> None:
    respuesta = rigid.render(RigidTopic.DEDUCTIBLE, poliza_de_ejemplo, language="en", on=HOY)

    assert respuesta is not None
    assert respuesta.text == (
        f"According to your policy POL-99, the partial-loss deductible is COP{NBSP}1,500,000 "
        f"for damage and COP{NBSP}250,000 for theft."
    )


def test_en_una_llamada_el_monto_se_dice_con_la_palabra(poliza_de_ejemplo: IssuedPolicy) -> None:
    respuesta = rigid.render(
        RigidTopic.DEDUCTIBLE, poliza_de_ejemplo, language="es", on=HOY, spoken=True
    )

    assert respuesta is not None
    assert "1.500.000 pesos" in respuesta.text
    assert "$" not in respuesta.text


def test_los_limites_ponen_cada_monto_en_su_lugar(poliza_de_ejemplo: IssuedPolicy) -> None:
    respuesta = rigid.render(RigidTopic.LIMITS, poliza_de_ejemplo, language="es", on=HOY)

    assert respuesta is not None
    texto = respuesta.text.replace(NBSP, " ")
    assert "lesiones, $ 100.000.000 por persona y $ 200.000.000 por accidente" in texto
    assert "daños a bienes, $ 50.000.000;" in texto
    assert "gastos médicos, $ 10.000.000 por persona" in texto
    assert "accidentes personales del conductor, $ 100.000.000." in texto


@pytest.mark.parametrize(
    ("dia", "clave", "fragmento"),
    [
        (date(2026, 9, 1), "chat.rigid.validity.in_force", "está vigente desde el 14 de junio"),
        (date(2027, 6, 15), "chat.rigid.validity.expired", "ya venció"),
        (date(2026, 6, 1), "chat.rigid.validity.not_yet", "empieza a regir el 14 de junio de 2026"),
    ],
)
def test_la_vigencia_depende_de_la_fecha_del_turno(
    poliza_de_ejemplo: IssuedPolicy, dia: date, clave: str, fragmento: str
) -> None:
    respuesta = rigid.render(RigidTopic.VALIDITY, poliza_de_ejemplo, language="es", on=dia)

    assert respuesta is not None
    assert respuesta.copy_key == clave
    assert fragmento in respuesta.text
    assert "14 de junio de 2027" in respuesta.text


def test_los_vehiculos_se_listan_sin_placa(poliza_de_ejemplo: IssuedPolicy) -> None:
    respuesta = rigid.render(RigidTopic.VEHICLES, poliza_de_ejemplo, language="en", on=HOY)

    assert respuesta is not None
    assert respuesta.text == (
        "The vehicles listed on your policy POL-99 are: Kia Picanto 2013; Mazda 3 2020."
    )
    assert "JUH431" not in respuesta.text


def test_sin_vehiculos_lo_dice_en_vez_de_una_lista_vacia() -> None:
    respuesta = rigid.render(RigidTopic.VEHICLES, poliza(vehicles=()), language="es", on=HOY)

    assert respuesta is not None
    assert respuesta.copy_key == "chat.rigid.vehicles.none"


def test_los_conductores_se_listan_y_sin_ellos_no_se_afirma_que_no_haya(
    poliza_de_ejemplo: IssuedPolicy,
) -> None:
    con = rigid.render(RigidTopic.DRIVERS, poliza_de_ejemplo, language="es", on=HOY)
    sin = rigid.render(RigidTopic.DRIVERS, poliza(drivers=()), language="es", on=HOY)

    assert con is not None
    assert "son: Daniela Castaño; Hernán Castaño." in con.text
    assert sin is not None
    assert sin.text == "No tengo conductores declarados en tu póliza POL-99."


def test_los_endosos_se_dicen_por_lo_que_cambian(poliza_de_ejemplo: IssuedPolicy) -> None:
    respuesta = rigid.render(
        RigidTopic.ENDORSEMENTS,
        poliza_de_ejemplo,
        language="es",
        on=HOY,
        clause_keys={
            "SA-PAP-2026-END-1": ("B.INS",),
            "SA-PAP-2026-END-2": ("F.TERMINATION",),
        },
    )

    assert respuesta is not None
    assert respuesta.copy_key == "chat.rigid.endorsements.listed"
    assert "Los gastos médicos cubren también a peatones atropellados" in respuesta.text
    assert "Al menos 45 días de aviso antes de cancelar la póliza" in respuesta.text


def test_endosos_sin_detalle_se_cuentan_sin_inventar_su_efecto(
    poliza_de_ejemplo: IssuedPolicy,
) -> None:
    respuesta = rigid.render(RigidTopic.ENDORSEMENTS, poliza_de_ejemplo, language="es", on=HOY)

    assert respuesta is not None
    assert respuesta.copy_key == "chat.rigid.endorsements.count_only"
    assert respuesta.text.endswith("en total: 2.")


def test_sin_endosos_lo_dice() -> None:
    respuesta = rigid.render(
        RigidTopic.ENDORSEMENTS, poliza(endorsement_ids=()), language="en", on=HOY
    )

    assert respuesta is not None
    assert respuesta.text == "Your policy POL-99 has no special conditions."


def test_el_tema_none_no_responde(poliza_de_ejemplo: IssuedPolicy) -> None:
    assert rigid.render(RigidTopic.NONE, poliza_de_ejemplo, language="es", on=HOY) is None


@pytest.mark.parametrize("tema", [RigidTopic.DEDUCTIBLE, RigidTopic.LIMITS])
def test_si_el_registro_no_trae_el_dato_no_hay_respuesta_y_se_sigue_por_el_camino_de_siempre(
    tema: RigidTopic,
) -> None:
    sin_montos = poliza(limits_and_deductibles={})

    assert rigid.render(tema, sin_montos, language="es", on=HOY) is None


# --- La guardia de salida real ----------------------------------------------


def _intervenciones(
    texto: str, idioma: Locale, *, source_key: str | None = None
) -> set[GuardCategory]:
    aseguradoras = tuple(sorted(tenancy_config.load().available, key=lambda t: t.tenant_id))
    resultado = guard.evaluate(
        texto,
        library=patterns.load_library(),
        context=contexto_de(aseguradoras, idioma, source_key=source_key),
        turn=GuardTurn(),
    )
    return {i.category for i in resultado.interventions if i.category is not None}


_CLAVES_DE_ENDOSOS = {
    "SA-PAP-2026-END-1": ("DEF.FAMILY_MEMBER", "A.EXCL.A.5", "D.EXCL.3", "C.ARBITRATION"),
    "SA-PAP-2026-END-2": ("F.PERIOD_TERRITORY", "DEF.COVERED_AUTO", "D.EXCL.5", "D.TRANSPORT"),
}


@pytest.mark.parametrize("idioma", ["es", "en"])
@pytest.mark.parametrize(
    "tema",
    [RigidTopic.VALIDITY, RigidTopic.VEHICLES, RigidTopic.DRIVERS, RigidTopic.ENDORSEMENTS],
)
def test_los_temas_sin_montos_pasan_la_guardia_sin_intervencion(
    poliza_de_ejemplo: IssuedPolicy, tema: RigidTopic, idioma: Locale
) -> None:
    respuesta = rigid.render(
        tema, poliza_de_ejemplo, language=idioma, on=HOY, clause_keys=_CLAVES_DE_ENDOSOS
    )

    assert respuesta is not None
    assert _intervenciones(respuesta.text, idioma) == set()


@pytest.mark.parametrize("idioma", ["es", "en"])
@pytest.mark.parametrize("tema", [RigidTopic.DEDUCTIBLE, RigidTopic.LIMITS])
def test_el_deducible_y_los_limites_pasan_la_guardia_con_la_clave_de_su_plantilla(
    poliza_de_ejemplo: IssuedPolicy, tema: RigidTopic, idioma: Locale
) -> None:
    """Decision de Miguel, 2026-11-02: estas dos plantillas salen con sus cifras del registro.

    La guardia no distingue «el monto que declara la poliza» de «un monto que se promete»
    (AC1.11.1), asi que antes la persona recibia la frase generica. Ahora el codigo, que es quien
    compone el texto, entrega su clave y la categoria de montos no lo reemplaza.
    """
    respuesta = rigid.render(tema, poliza_de_ejemplo, language=idioma, on=HOY)

    assert respuesta is not None
    assert _intervenciones(respuesta.text, idioma, source_key=str(respuesta.copy_key)) == set()


@pytest.mark.parametrize("idioma", ["es", "en"])
@pytest.mark.parametrize("tema", [RigidTopic.DEDUCTIBLE, RigidTopic.LIMITS])
def test_el_mismo_texto_sin_su_clave_sigue_siendo_un_monto_para_la_guardia(
    poliza_de_ejemplo: IssuedPolicy, tema: RigidTopic, idioma: Locale
) -> None:
    """La exencion es de la clave, no del texto: lo que escriba un modelo con esas cifras cae."""
    respuesta = rigid.render(tema, poliza_de_ejemplo, language=idioma, on=HOY)

    assert respuesta is not None
    assert _intervenciones(respuesta.text, idioma) == {GuardCategory.AMOUNT}


def test_ninguna_plantilla_afirma_cobertura(poliza_de_ejemplo: IssuedPolicy) -> None:
    for idioma in ("es", "en"):
        for tema in RigidTopic:
            respuesta = rigid.render(
                tema, poliza_de_ejemplo, language=idioma, on=HOY, clause_keys=_CLAVES_DE_ENDOSOS
            )
            if respuesta is None:
                continue
            assert GuardCategory.COVERAGE_PROMISE not in _intervenciones(respuesta.text, idioma)
