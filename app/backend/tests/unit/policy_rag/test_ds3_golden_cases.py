"""La prueba que sostiene DS-3 contra el corpus real (CG-U8-2).

Los 46 casos son el conjunto contra el que se mide todo lo demas, y es
justamente donde un agente barato -- o una persona con prisa -- puede escribir
un identificador de clausula plausible y falso. Esta prueba lo ataja siempre:
recorre los 46 archivos y comprueba, contra `app/data/` de verdad (nunca un
corpus sembrado en un directorio temporal: ese es justamente el punto), que
cada `citation.clause_id`:

1. existe en el corpus real;
2. es de la aseguradora que el caso declara (`tenant`), leyendo la copia que
   corresponde cuando el cliente es de la agencia Knotwell (BR2.5);
3. pertenece a la poliza del caso (mismo `form_id`/`form_version`, o al
   endoso vigente que `amended_by` nombra);
4. no esta marcada `is_distractor`.

Un caso con `clause_id: null` (eje "sin clausula") no tiene nada que
comprobar aqui: lo que afirma es que **no existe** ninguna clausula para esa
pregunta, y esta prueba no inventa una.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from untangle import paths
from untangle.evals import loading as evals_loading
from untangle.evals.models import Dataset, GoldenCase

pytestmark = pytest.mark.filterwarnings("ignore")


def _ds3_cases() -> tuple[GoldenCase, ...]:
    todos = evals_loading.load_cases()
    return tuple(caso for caso in todos if caso.dataset is Dataset.DS_3)


def _read_json(path: Path) -> dict[str, Any]:
    resultado: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return resultado


def _clauses_for(tenant_id: str) -> dict[str, dict[str, Any]]:
    """Todas las clausulas de un corpus, indexadas por `clause_id` (BR2.5).

    Para Knotwell esto lee **su propia carpeta** -- las copias de las dos
    emisoras -- que es exactamente lo que un cliente de la agencia recupera
    (BR2.5): el corpus lo decide la emisora de la poliza, dentro de la copia
    que Knotwell tiene, y no la carpeta de la emisora directamente.
    """
    tenant_dir = paths.corpus_tenants_dir() / tenant_id / "clauses"
    indice: dict[str, dict[str, Any]] = {}
    for archivo in sorted(tenant_dir.glob("*.json")):
        datos = _read_json(archivo)
        for clausula in datos.get("clauses", []):
            indice[clausula["clause_id"]] = clausula
    return indice


def _policy_for(tenant_id: str, policy_number: str) -> dict[str, Any]:
    ruta = paths.corpus_tenants_dir() / tenant_id / "issued_policies" / f"{policy_number}.json"
    assert ruta.is_file(), (
        f"no existe la poliza '{policy_number}' de '{tenant_id}': se esperaba '{ruta}'"
    )
    return _read_json(ruta)


@pytest.fixture(scope="module")
def ds3_cases() -> tuple[GoldenCase, ...]:
    casos = _ds3_cases()
    assert len(casos) == 46, f"DS-3 deberia tener 46 casos y tiene {len(casos)}"
    return casos


def test_ds3_tiene_sus_veintitres_parejas(ds3_cases: tuple[GoldenCase, ...]) -> None:
    """Veinte de FD-U8-2 y, desde el 2026-10-11, tres de 'sin clausula' que repusieron las
    que se perdieron al corregir tres casos que si tenian respuesta (auditoria, E10)."""
    por_idioma = {"es": 0, "en": 0}
    for caso in ds3_cases:
        por_idioma[caso.language] += 1
    assert por_idioma == {"es": 23, "en": 23}


def test_el_eje_sin_clausula_es_solo_de_los_casos_que_no_citan_ninguna(
    ds3_cases: tuple[GoldenCase, ...],
) -> None:
    """El resultado esperado, la clausula y el eje cuentan la misma historia.

    El eje 'sin_clausula' contaba como tal tres casos cuya respuesta correcta es una
    clausula, y falseaba todo recuento por eje. Ahora no puede volver a pasar:
    `no_clause_found` es 'no hay clausula' y 'verified' es 'hay una'.
    """
    for caso in ds3_cases:
        registro = caso.citation
        assert registro is not None, caso.case_key
        sin_clausula = registro.clause_id is None
        assert sin_clausula == (registro.expected_outcome == "no_clause_found"), caso.case_key
        assert sin_clausula == ("sin_clausula" in caso.axes), caso.case_key


def test_la_poliza_de_cada_caso_existe_en_el_corpus_de_su_aseguradora(
    ds3_cases: tuple[GoldenCase, ...],
) -> None:
    """Tambien los de 'sin clausula', que no tienen identificador que comprobar: una
    pregunta sobre una poliza que no existe no mide que la poliza no trate el tema."""
    for caso in ds3_cases:
        assert caso.citation is not None
        assert caso.tenant is not None, caso.case_key
        _policy_for(caso.tenant, caso.citation.policy_number)


@pytest.mark.parametrize(
    "case_key",
    [caso.case_key for caso in _ds3_cases()],
)
def test_expected_clause_id_existe_es_de_la_aseguradora_y_de_la_poliza_y_no_es_distractor(
    case_key: str,
) -> None:
    caso = next(c for c in _ds3_cases() if c.case_key == case_key)
    registro = caso.citation
    assert registro is not None, f"'{case_key}' no trae su bloque `citation`"
    clause_id = registro.clause_id

    if clause_id is None:
        # Eje "sin clausula": lo que el caso afirma es que no existe ninguna,
        # y no hay nada mas que comprobar contra el corpus (AC2.5.1).
        return

    tenant_id = caso.tenant
    assert tenant_id is not None, f"'{case_key}' no declara `tenant`"
    policy_number = registro.policy_number

    clausulas = _clauses_for(tenant_id)
    assert clause_id in clausulas, (
        f"'{case_key}' cita '{clause_id}', que no existe en el corpus de '{tenant_id}' (CG-U8-2)"
    )
    clausula = clausulas[clause_id]

    assert clausula["is_distractor"] is False, (
        f"'{case_key}' cita '{clause_id}', que esta marcada `is_distractor` en el corpus (CG-U8-2)"
    )

    poliza = _policy_for(tenant_id, policy_number)
    endorsement_ids: set[str] = set(poliza.get("endorsement_ids", []))
    form_id_de_la_clausula = clausula["form_id"]

    pertenece_al_formulario_base = form_id_de_la_clausula == poliza["form_id"]
    pertenece_a_un_endoso_vigente = form_id_de_la_clausula in endorsement_ids
    assert pertenece_al_formulario_base or pertenece_a_un_endoso_vigente, (
        f"'{case_key}' cita '{clause_id}' (formulario '{form_id_de_la_clausula}'), que no "
        f"pertenece al formulario de la poliza '{policy_number}' ('{poliza['form_id']}') ni "
        f"a uno de sus endosos vigentes ({sorted(endorsement_ids)}) (CG-U8-2)"
    )

    amended_by = registro.amended_by
    if amended_by is not None:
        assert amended_by in endorsement_ids, (
            f"'{case_key}' declara `amended_by: {amended_by}`, que no es un endoso vigente "
            f"de la poliza '{policy_number}' ({sorted(endorsement_ids)})"
        )


@pytest.mark.parametrize(
    "case_key",
    [caso.case_key for caso in _ds3_cases()],
)
def test_forbidden_clause_ids_existen_son_distractores_y_no_pertenecen_a_la_poliza(
    case_key: str,
) -> None:
    """La comprobacion espejo de CG-U8-2, para los casos de distractor (PASO 0.1).

    `citation.clause_id` dice que se debe citar; `forbidden_clause_ids`
    dice que **no** se puede recuperar ni citar la cláusula gemela. Sin este
    espejo, una corrida que recuperara y citara el distractor junto a la buena
    pasaría igual, porque nada en el archivo lo prohibía (AC2.1.2).
    """
    caso = next(c for c in _ds3_cases() if c.case_key == case_key)
    registro = caso.citation
    assert registro is not None, f"'{case_key}' no trae su bloque `citation`"
    forbidden_ids = list(registro.forbidden_clause_ids) or None

    if "distractor" in caso.axes:
        # Las tres parejas de distractor son exactamente donde este campo
        # existe para atajar algo: sin el, un identificador prohibido plausible
        # y falso pasaria igual (PASO 0.1 de la tanda 2). Un eje "distractor"
        # sin `forbidden_clause_ids` es el hueco que esta prueba existe para
        # cerrar.
        assert forbidden_ids, (
            f"'{case_key}' tiene el eje 'distractor' y no declara "
            "`forbidden_clause_ids`: sin el, nada comprueba que el distractor no "
            "se recupere ni se cite (PASO 0.1)"
        )
    elif forbidden_ids is None:
        # Los demas casos no tienen distractor gemelo declarado: no hay nada
        # que comprobar aqui, igual que "sin clausula" no tiene nada que
        # comprobar en la prueba de arriba.
        return

    tenant_id = caso.tenant
    assert tenant_id is not None, f"'{case_key}' no declara `tenant`"
    policy_number = registro.policy_number

    clausulas = _clauses_for(tenant_id)
    poliza = _policy_for(tenant_id, policy_number)
    endorsement_ids: set[str] = set(poliza.get("endorsement_ids", []))

    assert isinstance(forbidden_ids, list), (
        f"'{case_key}' declara `forbidden_clause_ids` y no es una lista (PASO 0.1)"
    )
    for forbidden_id in forbidden_ids:
        assert forbidden_id in clausulas, (
            f"'{case_key}' prohibe citar '{forbidden_id}', que no existe en el corpus "
            f"de '{tenant_id}' (PASO 0.1)"
        )
        clausula = clausulas[forbidden_id]

        assert clausula["is_distractor"] is True, (
            f"'{case_key}' prohibe citar '{forbidden_id}', pero esa clausula no esta "
            f"marcada `is_distractor` en el corpus de '{tenant_id}': no es un distractor "
            "de verdad (PASO 0.1)"
        )

        form_id_de_la_clausula = clausula["form_id"]
        pertenece_al_formulario_base = form_id_de_la_clausula == poliza["form_id"]
        pertenece_a_un_endoso_vigente = form_id_de_la_clausula in endorsement_ids
        assert not (pertenece_al_formulario_base or pertenece_a_un_endoso_vigente), (
            f"'{case_key}' prohibe citar '{forbidden_id}' (formulario "
            f"'{form_id_de_la_clausula}'), pero esa clausula si pertenece al formulario "
            f"vigente de la poliza '{policy_number}' o a uno de sus endosos: el distractor "
            "gemelo tiene que estar fuera de lo que la poliza reconoce (PASO 0.1)"
        )
