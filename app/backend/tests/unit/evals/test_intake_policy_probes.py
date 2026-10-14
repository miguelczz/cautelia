"""Los casos de DS-2 de la poliza que el reconocedor entrega mal (2026-10-13).

Corren el nodo `intake` de verdad sobre el corpus versionado, sin modelo y sin base. Aqui se
comprueba que cada caso exista en los dos idiomas, que el manifiesto cuente sus archivos, que el
subconjunto de arranque los lleve, y que cada sonda pase por idioma y **falle cuando la conducta
que mide falta**.
"""

from __future__ import annotations

import pytest

from untangle import paths
from untangle.base import Locale
from untangle.evals import intake_policy_probes, loading
from untangle.evals.models import Dataset
from untangle.evals.runner import api

CRITERIOS = {
    "intake-policy-heard-incomplete": "intake_policy_heard_incomplete",
    "intake-policy-not-found-repeat": "intake_policy_not_found_repeat",
}
IDIOMAS: tuple[Locale, ...] = ("es", "en")


def test_cada_caso_existe_en_los_dos_idiomas_con_su_criterio() -> None:
    casos = {c.case_key: c for c in loading.load_cases()}
    for nombre, criterio in CRITERIOS.items():
        for idioma in IDIOMAS:
            caso = casos[f"DS-2/{idioma}/{nombre}"]
            assert caso.expected_verdicts == {criterio: "pass"}
            assert caso.requires_provider_key is False
            assert caso.channel is None, "es una sonda determinista, no una conversacion"


def test_el_manifiesto_cuenta_los_archivos_del_arbol() -> None:
    assert loading.check_manifest_counts(loading.load_manifest(), loading.load_cases()) == ()
    declaracion = loading.load_manifest().declaration_for(Dataset.DS_2)
    assert declaracion.count == 138


def test_el_subconjunto_de_arranque_los_lleva_porque_se_resuelven_sin_clave() -> None:
    arranque = loading.load_subset("smoke", paths.subsets_dir())
    for nombre in CRITERIOS:
        for idioma in IDIOMAS:
            assert f"DS-2/{idioma}/{nombre}" in arranque.case_keys


def test_las_dos_sondas_y_sus_objetivos_quedan_registrados() -> None:
    intake_policy_probes.register_intake_policy_probes()

    for criterio in CRITERIOS.values():
        assert api.async_check_for(criterio) is not None
    objetivos = {t.criterion for t in api.registered_targets()[intake_policy_probes.UNIT]}
    assert objetivos == set(CRITERIOS.values())


@pytest.mark.parametrize("idioma", IDIOMAS)
async def test_la_sonda_de_la_poliza_incompleta_pasa(idioma: Locale) -> None:
    resultado = await intake_policy_probes.SONDAS_ASINCRONAS["intake_policy_heard_incomplete"](
        language=idioma, root=paths.repo_root()
    )

    assert resultado.passed, resultado.detail


@pytest.mark.parametrize("idioma", IDIOMAS)
async def test_la_sonda_de_la_poliza_no_encontrada_pasa(idioma: Locale) -> None:
    resultado = await intake_policy_probes.SONDAS_ASINCRONAS["intake_policy_not_found_repeat"](
        language=idioma, root=paths.repo_root()
    )

    assert resultado.passed, resultado.detail
