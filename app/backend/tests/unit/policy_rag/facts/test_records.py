"""Los datos tipados de una poliza, funcion por funcion, con valores escritos a mano."""

from __future__ import annotations

from datetime import date

import pytest

from untangle.policy_rag.corpus.models import DeclaredDriver, IssuedPolicy
from untangle.policy_rag.facts import records
from untangle.policy_rag.facts.models import PolicyStatus

from .conftest import poliza


@pytest.mark.parametrize(
    ("dia", "estado"),
    [
        (date(2026, 6, 13), PolicyStatus.NOT_YET_IN_FORCE),
        # Los dos extremos del periodo cuentan como vigentes, igual que en el verificador de citas.
        (date(2026, 6, 14), PolicyStatus.IN_FORCE),
        (date(2027, 1, 1), PolicyStatus.IN_FORCE),
        (date(2027, 6, 14), PolicyStatus.IN_FORCE),
        (date(2027, 6, 15), PolicyStatus.EXPIRED),
    ],
)
def test_la_vigencia_depende_de_la_fecha_que_se_entrega(
    poliza_de_ejemplo: IssuedPolicy, dia: date, estado: PolicyStatus
) -> None:
    assert records.status_on(poliza_de_ejemplo, dia) is estado
    assert records.summarize(poliza_de_ejemplo, on=dia).status is estado


def test_el_resumen_trae_el_titular_el_periodo_y_los_recuentos(
    poliza_de_ejemplo: IssuedPolicy,
) -> None:
    resumen = records.summarize(poliza_de_ejemplo, on=date(2026, 9, 1))

    assert resumen.policy_number == "POL-99"
    assert resumen.holder_name == "Daniela Castaño"
    assert resumen.issuer_tenant == "stonecroft"
    assert (resumen.form_id, resumen.form_version) == ("SA-PAP-2026", "2026.1")
    assert (resumen.period_start, resumen.period_end) == (date(2026, 6, 14), date(2027, 6, 14))
    assert resumen.as_of == date(2026, 9, 1)
    assert (resumen.vehicle_count, resumen.driver_count, resumen.endorsement_count) == (2, 2, 2)


def test_los_limites_salen_del_registro_y_no_incluyen_los_deducibles(
    poliza_de_ejemplo: IssuedPolicy,
) -> None:
    limites = {f.key: f for f in records.limits_of(poliza_de_ejemplo, language="es")}

    assert set(limites) == {
        "a.bodily_injury_per_person",
        "a.bodily_injury_per_accident",
        "a.property_damage",
        "b.medical_payments_per_person",
        "c.driver_personal_accident",
    }
    por_persona = limites["a.bodily_injury_per_person"].amount
    assert (por_persona.units, por_persona.pesos) == (100000, 100_000_000)
    assert por_persona.formatted == "$\xa0100.000.000"
    assert limites["a.property_damage"].amount.units == 50000
    assert limites["a.property_damage"].label == "Responsabilidad civil: daños a bienes de terceros"


def test_los_deducibles_son_solo_las_claves_de_deducible(poliza_de_ejemplo: IssuedPolicy) -> None:
    deducibles = {f.key: f for f in records.deductibles_of(poliza_de_ejemplo, language="en")}

    assert set(deducibles) == {"d.damage_deductible", "d.theft_deductible"}
    assert deducibles["d.damage_deductible"].amount.formatted == "COP\xa01,500,000"
    assert deducibles["d.theft_deductible"].amount.pesos == 250_000
    assert deducibles["d.damage_deductible"].label == "Partial loss by damage deductible"


def test_una_clave_que_el_catalogo_no_conoce_se_rotula_con_la_clave() -> None:
    p = poliza(limits_and_deductibles={"z.new_limit": 7, "z.new_deductible": 3})

    assert [f.label for f in records.limits_of(p, language="es")] == ["z.new_limit"]
    assert [f.label for f in records.deductibles_of(p, language="es")] == ["z.new_deductible"]


def test_los_vehiculos_no_sacan_la_placa_ni_el_vin(poliza_de_ejemplo: IssuedPolicy) -> None:
    vehiculos = records.vehicles_of(poliza_de_ejemplo)

    assert [v.description for v in vehiculos] == ["Kia Picanto 2013", "Mazda 3 2020"]
    assert "plate" not in vehiculos[0].model_dump()
    assert "vin" not in vehiculos[0].model_dump()


def test_los_conductores_traen_al_titular_primero_y_marcado(
    poliza_de_ejemplo: IssuedPolicy,
) -> None:
    conductores = records.drivers_of(poliza_de_ejemplo)

    assert [(d.full_name, d.is_holder) for d in conductores] == [
        ("Daniela Castaño", True),
        ("Hernán Castaño", False),
    ]


def test_sin_conductores_declarados_la_lista_es_vacia_y_no_inventa_al_titular() -> None:
    assert records.drivers_of(poliza(drivers=())) == ()


def test_los_endosos_traen_sus_clausulas_y_lo_que_cambian() -> None:
    p = poliza(endorsement_ids=("E-1", "E-2", "E-3"))

    hechos = records.endorsements_of(
        p,
        clause_keys={"E-1": ("A.EXCL.A.5", "D.TRANSPORT"), "E-2": ("CLAVE.DESCONOCIDA",)},
        language="es",
    )

    assert [h.form_id for h in hechos] == ["E-1", "E-2", "E-3"]
    assert hechos[0].clause_keys == ("A.EXCL.A.5", "D.TRANSPORT")
    assert hechos[0].summaries == (
        "Cubre la responsabilidad civil al manejar para una plataforma de viajes",
        "Más dinero diario y total para transporte tras un robo o daño",
    )
    # Una clausula que el catalogo no conoce queda en `clause_keys` y no inventa una frase.
    assert hechos[1].clause_keys == ("CLAVE.DESCONOCIDA",)
    assert hechos[1].summaries == ()
    # El endoso del que no se sabe que cambia figura igual: que la poliza lo trae es un dato.
    assert hechos[2].clause_keys == ()


def test_un_titular_sin_nombre_no_marca_a_nadie_como_titular() -> None:
    p = poliza(named_insured={}, drivers=(DeclaredDriver(full_name="Alguien"),))

    assert [d.is_holder for d in records.drivers_of(p)] == [False]
