"""La composicion del corpus sobre los textos fuente reales (paso 9 del plan de U7).

Las pruebas que miran el corpus lo componen desde `app/data/sources/` del
repositorio, que es lo que se versiona. Las que rompen una regla copian esas
fuentes a un repositorio temporal y cambian **una** cosa: nunca se toca una
fuente real.

Reglas: BR3.1 a BR3.7, BR4.1 a BR4.3, BR6.1, BR6.2, BR7.1 y BR7.3; objetivos
TECH-U7.3, NFR20.4, SEC-U7.3 y NFR10.7.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
import yaml

from untangle.rules.models import CATEGORIES
from untangle.synthetic_data import corpus as corpus_mod
from untangle.synthetic_data import generator, manifest
from untangle.synthetic_data.cases import DIRECT_CLOSE, check_criteria, direct_close_tenants
from untangle.synthetic_data.chooser import ChooserFactory
from untangle.synthetic_data.cli import CORPUS_COMPOSERS
from untangle.synthetic_data.models import (
    SeededCaseRecord,
    SeededCriteriaFile,
    vin_check_digit,
)
from untangle.synthetic_data.sources import load_sources
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.models import TenantKind

from .apoyo import RAIZ_REAL, repo

EMISORAS = ("stonecroft", "sunmeadow")
AGENCIA = "knotwell"

#: El contenido de DS-8, sin `generated` ni su motivo: SHA-256 de su JSON compacto
#: con claves ordenadas. Es el contrato de BR7.3: esta cifra existe para que nadie
#: cambie una fila o una colision sin decirlo.
#:
#: **Cambiada una vez**, el 2026-09-28, por decision de Miguel. La version de U2
#: --`105f741c9f2808fb44fe9d4e77aac5d6749cb923981275121cbb632f64e337b1`, tomada del
#: archivo original en el commit 139bac4-- declaraba el mismo identificador de caso
#: en dos aseguradoras, y `case_record` no lo admite: su llave primaria es `case_id`
#: a secas. La contradiccion vivio sin que nada la dijera porque hasta U14 nadie
#: habia sembrado esas filas. Manda el esquema: la fila de la segunda emisora lleva
#: su propio identificador y conserva las dos colisiones que si caben, numero de
#: poliza y nombre del asegurado. La colision del identificador sigue declarada
#: sobre los enlaces de caso, que es donde U2 la ejercita y donde si cabe. La razon
#: entera esta en `synthetic_data/ds8.py`.
#:
#: **Cambio intencional del 2026-10-30** (decision de Miguel): los numeros de poliza de DS-8
#: pasan de seis cifras a dos --`POL-480915` es `POL-50` y `POL-173620` es `POL-32`--. Es lo
#: unico que cambia en el contrato: las mismas filas y las mismas colisiones, con otro numero.
CONTRATO_DS8_U2 = "86ae2e146c305a28054ce61175d496983335ce5b0b94e836ecdd863ae5f4dc4b"


def _render(raiz: Path = RAIZ_REAL, destino: Path | None = None) -> generator.RenderedGeneration:
    return generator.render(
        generator.GenerationRequest(
            repo_root=raiz,
            data_dir=destino if destino is not None else raiz / "app" / "data",
            composers=CORPUS_COMPOSERS,
        )
    )


def _json(generacion: generator.RenderedGeneration, ruta: str) -> Any:
    return json.loads(generacion.files[ruta])


def _con_fuentes_reales(tmp_path: Path) -> Path:
    """Un repositorio temporal con la configuracion y los textos fuente reales."""
    raiz = repo(tmp_path)
    shutil.copytree(RAIZ_REAL / "app" / "data" / "sources", raiz / "app" / "data" / "sources")
    return raiz


def _problemas(raiz: Path) -> str:
    with pytest.raises(generator.GenerationError) as error:
        _render(raiz)
    return "\n".join(error.value.problems)


def _editar_yaml(ruta: Path, cambio: Any) -> None:
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    cambio(datos)
    ruta.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _corpus() -> corpus_mod.CorpusResult:
    tenants = tenancy_config.load(RAIZ_REAL / "app" / "config" / "tenants")
    fuentes = load_sources(
        RAIZ_REAL / "app" / "data" / "sources", repo_root=RAIZ_REAL, tenants=tenants
    )
    return corpus_mod.compose_corpus_texts(fuentes, tenants)


def _casos(generacion: generator.RenderedGeneration) -> list[SeededCaseRecord]:
    return [
        SeededCaseRecord.model_validate_json(contenido)
        for ruta, contenido in generacion.files.items()
        if "/cases/" in ruta
    ]


# --- BR3.1 a BR3.4: partes, endosos y distractores ----------------------------


def test_cada_emisora_tiene_todas_las_partes_cinco_endosos_y_ocho_distractores() -> None:
    compuesto = _corpus()
    assert not compuesto.problems

    for emisora in EMISORAS:
        uno = compuesto.issuers[emisora]
        base = uno.current_base
        assert base is not None
        partes = {uno.part_of[c.clause_id] for c in uno.clauses[base.form_id]}
        assert {p.value for p in corpus_mod.BASE_PARTS} <= partes, emisora
        # El documento de jurisdiccion de Corvane existe y el base lo referencia.
        assert base.jurisdiction_ref is not None
        assert uno.forms[base.jurisdiction_ref].form_kind.value == "jurisdiction"
        assert len(uno.clauses[base.jurisdiction_ref]) >= 4
        assert len(uno.endorsement_ids) == 5, emisora

        distractores = [c for grupo in uno.clauses.values() for c in grupo if c.is_distractor]
        assert len(distractores) == 8, emisora
        # Viven en la edicion anterior, que ninguna poliza usa.
        assert {c.form_id for c in distractores} == {base.form_id.replace("2026", "2025")}


def test_los_distractores_mezclan_versiones_anteriores_y_casi_duplicados() -> None:
    tenants = tenancy_config.load(RAIZ_REAL / "app" / "config" / "tenants")
    fuentes = load_sources(
        RAIZ_REAL / "app" / "data" / "sources", repo_root=RAIZ_REAL, tenants=tenants
    )
    por_emisora = Counter(
        (t.tenant_id, t.distractor_reason.value)
        for t in fuentes.texts
        if t.distractor_reason is not None
    )
    for emisora in EMISORAS:
        assert por_emisora[(emisora, "superseded_version")] >= 1
        assert por_emisora[(emisora, "near_duplicate")] >= 1
        assert (
            por_emisora[(emisora, "superseded_version")] + por_emisora[(emisora, "near_duplicate")]
            == 8
        )


def test_una_parte_que_falta_detiene_la_generacion_nombrandola(tmp_path: Path) -> None:
    raiz = _con_fuentes_reales(tmp_path)
    (raiz / "app" / "data" / "sources" / "stonecroft" / "es" / "part_f.yaml").unlink()

    problemas = _problemas(raiz)

    assert "'SA-PAP-2026': le faltan partes de la referencia: part_f" in problemas
    assert not (raiz / "app" / "data" / "tenants").exists()


def test_menos_de_cuatro_endosos_detienen_la_generacion(tmp_path: Path) -> None:
    raiz = _con_fuentes_reales(tmp_path)
    endosos = raiz / "app" / "data" / "sources" / "sunmeadow" / "en" / "endorsements.yaml"
    _editar_yaml(endosos, lambda d: d.update(texts=d["texts"][:3]))

    problemas = _problemas(raiz)

    assert "'sunmeadow': tiene 3 endoso(s) y el minimo es 4 (BR3.3)" in problemas


def test_un_distractor_sin_clausula_vigente_se_nombra(tmp_path: Path) -> None:
    raiz = _con_fuentes_reales(tmp_path)
    parte = raiz / "app" / "data" / "sources" / "stonecroft" / "es" / "part_c.yaml"

    def apuntar_a_nada(datos: dict[str, Any]) -> None:
        for texto in datos["texts"]:
            if texto["kind"] == "distractor":
                texto["distractor_of"] = "SA-PAP-2026-C.NO_EXISTE"

    _editar_yaml(parte, apuntar_a_nada)

    assert "se confunde con 'SA-PAP-2026-C.NO_EXISTE'" in _problemas(raiz)


# --- BR3.5: las relaciones ------------------------------------------------------


def test_las_relaciones_tienen_sus_dos_extremos_y_las_tres_clases() -> None:
    compuesto = _corpus()
    for emisora in EMISORAS:
        uno = compuesto.issuers[emisora]
        ids = uno.all_clause_ids()
        clases = Counter(r.relation.value for r in uno.relations)
        assert set(clases) == {"endorsement_modifies", "defines", "refers_to"}, emisora
        assert clases["endorsement_modifies"] == 5
        for relacion in uno.relations:
            assert relacion.from_clause in ids
            assert relacion.to_clause in ids


def test_un_endoso_que_modifica_algo_inexistente_se_nombra(tmp_path: Path) -> None:
    raiz = _con_fuentes_reales(tmp_path)
    endosos = raiz / "app" / "data" / "sources" / "stonecroft" / "es" / "endorsements.yaml"

    def huerfano(datos: dict[str, Any]) -> None:
        primero = datos["texts"][0]
        primero["clause_key"] = "Z.NADA"
        primero["source_id"] = "SA-PAP-2026-END-1-Z.NADA"

    _editar_yaml(endosos, huerfano)

    assert "modifica 'Z.NADA', que no esta en 'SA-PAP-2026' (BR3.5)" in _problemas(raiz)


# --- BR4.1 a BR4.3: la agencia --------------------------------------------------


def test_la_agencia_tiene_copias_identicas_de_cada_formulario_de_sus_emisoras() -> None:
    generacion = _render()
    for ruta, contenido in generacion.files.items():
        coincide = re.fullmatch(r"tenants/(\w+)/(forms|clauses)/(.+\.json)", ruta)
        if coincide is None or coincide[1] not in EMISORAS:
            continue
        copia = f"tenants/{AGENCIA}/{coincide[2]}/{coincide[3]}"
        assert generacion.files[copia] == contenido, copia
        if coincide[2] == "forms":
            assert _json(generacion, copia)["issuer_tenant"] == coincide[1]


def test_una_copia_alterada_de_la_agencia_falla_aunque_el_manifiesto_se_ajuste(
    tmp_path: Path,
) -> None:
    datos = tmp_path / "data"
    generator.write(_render(RAIZ_REAL, datos), datos)
    copia = datos / "tenants" / AGENCIA / "clauses" / "AP-PAP-2026.json"
    contenido = json.loads(copia.read_text(encoding="utf-8"))
    contenido["clauses"][0]["text"] = "Texto cambiado en la copia de la agencia."
    copia.write_text(json.dumps(contenido, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Quien altera la copia ajusta tambien el hash del manifiesto: ni asi pasa.
    ruta_manifiesto = datos / "manifest.json"
    registro = json.loads(ruta_manifiesto.read_text(encoding="utf-8"))
    registro["outputs"][f"app/data/tenants/{AGENCIA}/clauses/AP-PAP-2026.json"] = hashlib.sha256(
        copia.read_bytes()
    ).hexdigest()
    ruta_manifiesto.write_text(json.dumps(registro, indent=2) + "\n", encoding="utf-8")

    problemas = manifest.verify_tree(RAIZ_REAL, datos)

    assert problemas == [
        f"'app/data/tenants/{AGENCIA}/clauses/AP-PAP-2026.json': la copia no es identica a su "
        "original de 'sunmeadow'; las copias salen del original en la misma generacion (BR4.2)"
    ]


def test_cada_poliza_de_la_agencia_declara_su_emisora_y_cada_ejemplo_existe() -> None:
    generacion = _render()
    tenants = tenancy_config.load(RAIZ_REAL / "app" / "config" / "tenants")
    for tenant in tenants.available:
        ruta = f"tenants/{tenant.tenant_id}/issued_policies/{tenant.example_policy}.json"
        assert ruta in generacion.files, tenant.tenant_id

    emisoras_de_la_agencia = set()
    for ruta in generacion.files:
        if not ruta.startswith(f"tenants/{AGENCIA}/issued_policies/"):
            continue
        poliza = _json(generacion, ruta)
        assert poliza["issuer_tenant"] in EMISORAS
        prefijo = {"stonecroft": "SA-", "sunmeadow": "AP-"}[poliza["issuer_tenant"]]
        assert poliza["form_id"].startswith(prefijo)
        assert all(e.startswith(f"{poliza['form_id']}-END-") for e in poliza["endorsement_ids"])
        emisoras_de_la_agencia.add(poliza["issuer_tenant"])
    assert emisoras_de_la_agencia == set(EMISORAS)


def test_cada_aseguradora_tiene_las_seis_polizas_de_su_decena_y_la_compartida_es_la_50() -> None:
    """Decision de Miguel del 2026-10-30: el numero de poliza dice de quien es.

    La de ejemplo es la primera de la decena, las otras cinco la siguen sin huecos, y la que
    dos emisoras comparten a proposito (DS-8) cae fuera de todas las decenas.
    """
    generacion = _render()
    tenants = tenancy_config.load(RAIZ_REAL / "app" / "config" / "tenants")
    emisoras = {t.tenant_id for t in tenants.available if t.kind is TenantKind.CARRIER}
    numeros_por_tenant: dict[str, list[int]] = {}
    for ruta in generacion.files:
        coincidencia = re.fullmatch(r"tenants/([^/]+)/issued_policies/POL-(\d{2})\.json", ruta)
        assert coincidencia is not None or "/issued_policies/" not in ruta, ruta
        if coincidencia is not None:
            numeros_por_tenant.setdefault(coincidencia[1], []).append(int(coincidencia[2]))

    decenas: set[int] = set()
    for tenant in tenants.available:
        ejemplo = int(tenant.example_policy.removeprefix("POL-"))
        decenas.add(ejemplo // 10)
        propios = sorted(
            n for n in numeros_por_tenant[tenant.tenant_id] if n // 10 == ejemplo // 10
        )
        assert propios == list(range(ejemplo, ejemplo + 6)), tenant.tenant_id
    assert len(decenas) == len(tenants.available), "dos aseguradoras comparten decena"

    compartidas = [
        t for t, numeros in numeros_por_tenant.items() if 50 in numeros and t in emisoras
    ]
    assert len(compartidas) == 2
    assert 50 // 10 not in decenas


# --- BR6.1 y BR6.2: los casos sembrados -----------------------------------------


def test_los_casos_cubren_cada_estado_aseguradora_e_idioma_y_cada_resolucion() -> None:
    casos = _casos(_render())
    estados = {
        "open",
        "capturing",
        "verifying",
        "deciding",
        "derived",
        "awaiting_insured",
        "closed",
    }
    presentes = {(c.tenant_id, c.language, c.state.value) for c in casos}
    for tenant in (*EMISORAS, AGENCIA):
        for estado in estados:
            # TECH-U7.3 y NFR20.4: la misma combinacion en los dos idiomas.
            assert (tenant, "es", estado) in presentes, (tenant, estado)
            assert (tenant, "en", estado) in presentes, (tenant, estado)

    resoluciones = {(c.tenant_id, c.resolution.value) for c in casos if c.resolution is not None}
    assert {r for _, r in resoluciones} == {"registered", "approved", "rejected", "sent_to_insurer"}
    assert {t for t, r in resoluciones if r == "sent_to_insurer"} == {AGENCIA}
    assert {r for t, r in resoluciones if t == AGENCIA} == {"sent_to_insurer"}


def test_falta_un_caso_de_la_matriz_y_la_generacion_lo_nombra(tmp_path: Path) -> None:
    raiz = _con_fuentes_reales(tmp_path)
    turnos = raiz / "app" / "data" / "sources" / "stonecroft" / "en" / "case_turns.yaml"
    _editar_yaml(
        turnos, lambda d: d.update(texts=[t for t in d["texts"] if t["case"]["name"] != "open"])
    )

    assert "falta un caso sembrado en 'open' de 'stonecroft' en 'en' (BR6.1)" in _problemas(raiz)


def test_la_categoria_de_cierre_directo_del_generador_es_la_del_motor() -> None:
    """El generador no puede importar el motor de reglas, y por eso copia el nombre: aqui se
    comprueba que la copia no se separe."""
    assert DIRECT_CLOSE in CATEGORIES


def test_las_aseguradoras_que_cierran_directo_se_leen_de_sus_reglas() -> None:
    """Sin lista: solo la que tiene una regla de esa categoria en su carpeta, y ninguna mas.

    El control es el otro lado: la emisora estricta y la agencia tienen reglas de triage y
    ninguna es de cierre directo, asi que la lectura no confunde "tiene reglas" con "cierra".
    """
    tenants_dir = RAIZ_REAL / "app" / "config" / "tenants"
    tenants = tenancy_config.load(tenants_dir)

    assert direct_close_tenants(tenants_dir, tenants) == {"sunmeadow"}


def test_un_registrado_donde_las_reglas_no_cierran_directo_detiene_la_generacion(
    tmp_path: Path,
) -> None:
    """Un cerrado `registered` es un cierre sin ajustador, y una aseguradora cuyas reglas no
    tienen ninguna de cierre directo no cierra asi nunca: el ejemplo diria algo imposible."""
    raiz = _con_fuentes_reales(tmp_path)
    turnos = raiz / "app" / "data" / "sources" / "stonecroft" / "en" / "case_turns.yaml"

    def _registrado(datos: dict[str, Any]) -> None:
        caso = next(t["case"] for t in datos["texts"] if t["case"]["name"] == "closed")
        caso["resolution"] = "registered"
        del caso["derivation_reason"]

    _editar_yaml(turnos, _registrado)

    problemas = _problemas(raiz)
    assert "'SEED/stonecroft/en/closed': se cierra como 'registered', sin ajustador" in problemas
    assert "no tienen ninguna de cierre directo ('direct_close')" in problemas


def test_cada_criterio_declarado_tiene_su_caso_y_ninguno_sobra() -> None:
    generacion = _render()
    casos = _casos(generacion)
    criterios = SeededCriteriaFile.model_validate(
        yaml.safe_load(
            (RAIZ_REAL / "app" / "data" / "sources" / "seeded_criteria.yaml").read_text(
                encoding="utf-8"
            )
        )
    )
    assert check_criteria(casos, criterios) == []

    otro = criterios.model_copy(
        update={
            "criteria": (
                *criterios.criteria,
                criterios.criteria[0].model_copy(update={"ac_id": "AC9.9.9"}),
            )
        }
    )
    assert check_criteria(casos, otro) == [
        "el criterio AC9.9.9 parte de un caso sembrado y ningun caso lo nombra en used_by (BR6.2)"
    ]
    menos = criterios.model_copy(
        update={"criteria": tuple(c for c in criterios.criteria if c.ac_id != "AC4.15.2")}
    )
    assert check_criteria(casos, menos) == [
        "un caso nombra el criterio AC4.15.2, que no esta en seeded_criteria.yaml (BR6.2)"
    ]


def test_el_manifiesto_lista_cada_caso_con_su_clave_estable_y_sus_criterios() -> None:
    primera, segunda = _render(), _render()
    assert primera.manifest.seeded_cases == segunda.manifest.seeded_cases

    por_clave = {c.case_key: c for c in primera.manifest.seeded_cases}
    derivado = por_clave["SEED/stonecroft/es/derived"]
    assert {"AC1.9.4", "AC1.16.4"} <= set(derivado.used_by)
    registro = SeededCaseRecord.model_validate_json(
        primera.files[derivado.path.removeprefix("app/data/")]
    )
    # El derivado por solicitud de persona con tres de siete campos confirmados.
    assert registro.derivation_reason is not None
    assert registro.derivation_reason.value == "person_requested"
    assert sum(1 for c in registro.fields.values() if c.status.value == "confirmed") == 3


# --- BR7.1 y BR7.2: los datos personales ficticios -------------------------------


def _valores(generacion: generator.RenderedGeneration) -> list[dict[str, str]]:
    valores: list[dict[str, str]] = _json(generacion, "personal_values.json")["values"]
    return valores


def test_todo_valor_personal_sembrado_esta_en_su_rango_ficticio() -> None:
    """SEC-U7.3: cero valores fuera de sus rangos ficticios."""
    fuera: list[str] = []
    formas = {
        ("phone", "es"): r"3\d{2} 555 01\d{2}",
        ("phone", "en"): r"\d{3}-555-01\d{2}",
        ("national_id", "es"): r"[1-9]\d\.\d{3}\.\d{3}",
        ("national_id", "en"): r"9\d{2}-(0[1-9]|[1-4]\d)-\d{4}",
        ("email", "es"): r"[a-z0-9.]+@example\.(com|org)",
        ("email", "en"): r"[a-z0-9.]+@example\.(com|org)",
        ("plate", "es"): r"[A-Z]{3}\d{3}",
        ("plate", "en"): r"[A-Z]{3}-\d{4}",
        ("policy_number", "es"): r"POL-\d{2}",
        ("policy_number", "en"): r"POL-\d{2}",
    }
    for valor in _valores(_render()):
        clave = (valor["kind"], valor["language"])
        if valor["kind"] == "vin":
            if len(valor["value"]) != 17 or valor["value"][8] == vin_check_digit(valor["value"]):
                fuera.append(str(valor))
        elif clave in formas and not re.fullmatch(formas[clave], valor["value"]):
            fuera.append(str(valor))
    assert fuera == []


def test_la_lista_incluye_cada_persona_vehiculo_y_tercero_sembrado() -> None:
    generacion = _render()
    valores = {(v["kind"], v["value"]) for v in _valores(generacion)}
    for ruta in generacion.files:
        if "/issued_policies/" not in ruta:
            continue
        poliza = _json(generacion, ruta)
        persona = poliza["named_insured"]
        for kind, campo in (("name", "full_name"), ("phone", "phone"), ("email", "email")):
            assert (kind, persona[campo]) in valores
        assert ("national_id", persona["national_id"]) in valores
        assert ("policy_number", poliza["policy_number"]) in valores
        for vehiculo in poliza["vehicles"]:
            assert ("plate", vehiculo["plate"]) in valores
            assert ("vin", vehiculo["vin"]) in valores
    # Los terceros del caso con dos lesionados y dos conductores.
    caso = SeededCaseRecord.model_validate_json(
        generacion.files["tenants/stonecroft/cases/es/injured-and-other-drivers.json"]
    )
    texto = " ".join(t.text for t in caso.transcript)
    terceros = [v for k, v in valores if k == "name" and v in texto]
    assert len(terceros) >= 4


# --- BR7.3: DS-8 ----------------------------------------------------------------


def test_ds8_regenerada_es_la_de_u2_salvo_generated() -> None:
    """NFR10.7: cero filas y colisiones distintas de las de U2."""
    ds8 = _json(_render(), "fixtures/ds8_isolation.json")
    assert ds8["generated"] is True
    contrato = {k: v for k, v in ds8.items() if k not in {"generated", "generated_reason"}}
    compacto = json.dumps(contrato, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    assert hashlib.sha256(compacto.encode("utf-8")).hexdigest() == CONTRATO_DS8_U2


def test_la_colision_de_ds8_tambien_esta_en_las_polizas_emitidas() -> None:
    generacion = _render()
    ds8 = _json(generacion, "fixtures/ds8_isolation.json")
    for fila in ds8["rows"]["policies"]:
        poliza = _json(
            generacion,
            f"tenants/{fila['tenant_id']}/issued_policies/{fila['policy_number']}.json",
        )
        assert poliza["named_insured"]["full_name"] == fila["insured_name"]
        assert poliza["period_start"] == fila["effective_from"]


# --- BR3.7: las diferencias declaradas ------------------------------------------


def test_las_diferencias_declaradas_coinciden_con_el_corpus() -> None:
    generacion = _render()
    declaradas = {d.difference_id: d for d in generacion.manifest.declared_differences}
    assert len(declaradas) == 5
    transporte = declaradas["transport-expense-extension"]
    assert transporte.present_in == ("AP-PAP-2026-END-3",)
    assert all(f.startswith("SA-PAP-2026-END-") for f in transporte.absent_in)

    clausulas = json.loads(generacion.files["tenants/sunmeadow/clauses/AP-PAP-2026-END-3.json"])
    assert [c["clause_key"] for c in clausulas["clauses"]] == ["D.TRANSPORT"]
    for form_id in transporte.absent_in:
        clausulas = json.loads(generacion.files[f"tenants/stonecroft/clauses/{form_id}.json"])
        assert all(c["clause_key"] != "D.TRANSPORT" for c in clausulas["clauses"])


def test_una_diferencia_que_el_corpus_contradice_se_nombra(tmp_path: Path) -> None:
    raiz = _con_fuentes_reales(tmp_path)
    diferencias = raiz / "app" / "data" / "sources" / "differences.yaml"

    def al_reves(datos: dict[str, Any]) -> None:
        primera = datos["differences"][0]
        primera["present_in"], primera["absent_in"] = primera["absent_in"], primera["present_in"]

    _editar_yaml(diferencias, al_reves)

    problemas = _problemas(raiz)
    assert (
        "diferencia 'transport-expense-extension': dice que 'D.TRANSPORT' esta en "
        "'SA-PAP-2026-END-1', y el corpus dice lo contrario (BR3.7)"
    ) in problemas


# --- BR1.1 sobre las fuentes reales ---------------------------------------------


def test_dos_generaciones_sobre_las_fuentes_reales_dan_los_mismos_bytes(tmp_path: Path) -> None:
    uno, dos = tmp_path / "uno", tmp_path / "dos"
    generator.generate(
        generator.GenerationRequest(repo_root=RAIZ_REAL, data_dir=uno, composers=CORPUS_COMPOSERS)
    )
    generator.generate(
        generator.GenerationRequest(repo_root=RAIZ_REAL, data_dir=dos, composers=CORPUS_COMPOSERS)
    )

    assert generator.compare(uno, dos) == []
    # Y lo versionado en app/data/ es exactamente eso (TECH-U7.1).
    assert generator.compare(uno, RAIZ_REAL / "app" / "data") == []


def test_la_composicion_pide_cada_flujo_de_azar_una_sola_vez() -> None:
    """Un flujo repetido haria dos salidas con las mismas elecciones (BR1.2)."""
    tenants = tenancy_config.load(RAIZ_REAL / "app" / "config" / "tenants")
    fuentes = load_sources(
        RAIZ_REAL / "app" / "data" / "sources", repo_root=RAIZ_REAL, tenants=tenants
    )
    fabrica = ChooserFactory(manifest.SEED)
    contexto = generator.CompositionContext(
        sources=fuentes,
        tenants=tenants,
        chooser=fabrica,
        tenants_dir=RAIZ_REAL / "app" / "config" / "tenants",
    )

    composicion = CORPUS_COMPOSERS[0](contexto)

    assert composicion.problems == ()
    with pytest.raises(ValueError, match="ya se entrego"):
        fabrica.for_output("tenants/stonecroft/issued_policies/POL-11.json")
