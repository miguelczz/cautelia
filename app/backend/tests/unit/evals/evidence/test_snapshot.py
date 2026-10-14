"""Las cinco cifras desde la linea base vigente (U22: BR1.1 a BR1.5, tanda 1).

Sin base de datos y sin proveedor: la linea base se siembra escribiendo su archivo.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from untangle import paths
from untangle.evals.evidence import api as evidence
from untangle.evals.evidence.snapshot import (
    build_snapshot,
)
from untangle.evals.gates.loading import load_baseline
from untangle.evals.latency_summary import MIN_TURNS_PER_LANGUAGE
from untangle.evals.loading import LoadError

from .builders import CASOS_SEMBRADOS, PUBLICADA, latencia_de_chat, linea_base, sembrar

FigureKey = evidence.FigureKey
NO_MEDIDAS = {FigureKey.LATENCY, FigureKey.COST_PER_CASE, FigureKey.CASES_BY_TENANT}

#: Los nombres de criterio que **estas pruebas** siembran, y que no son los de
#: produccion: hoy en produccion los dos son nulos, porque ningun criterio mide
#: todavia estas dos cifras. Entran por argumento para poder probar el camino
#: "medida" sin inventar un nombre en el codigo, que es de donde vino el defecto.
CRITERIOS: Mapping[FigureKey, str | None] = {
    FigureKey.COMPLETENESS: "field_extraction",
    FigureKey.CITATION_PRECISION: "citation_precision",
}


def _figura(snapshot: evidence.MetricsSnapshot, key: evidence.FigureKey) -> evidence.Figure:
    [figura] = [f for f in snapshot.figures if f.key is key]
    return figura


def test_sin_linea_base_las_cinco_salen_no_medidas_con_causa_y_ningun_valor() -> None:
    snapshot = build_snapshot(None)

    assert {f.key for f in snapshot.figures} == set(FigureKey)
    assert snapshot.baseline_id is None
    for figura in snapshot.figures:
        assert figura.state is evidence.FigureState.NOT_MEASURED
        assert figura.not_measured_cause is not None
        assert figura.source is None
        for celda in figura.by_language.values():
            assert celda.value is None
            assert celda.not_measured_cause is not None
    # **Con el mapa de produccion la causa no es "no hay linea base"**: es que
    # todavia no existe el criterio, y eso no depende de que haya linea base. La
    # distincion manda a arreglar sitios distintos, asi que se comprueban las dos.
    assert (
        _figura(snapshot, FigureKey.COMPLETENESS).not_measured_cause
        is evidence.NotMeasuredCause.CRITERION_NOT_BUILT
    )
    con_criterio = build_snapshot(None, criteria=CRITERIOS)
    assert (
        _figura(con_criterio, FigureKey.COMPLETENESS).not_measured_cause
        is evidence.NotMeasuredCause.NO_BASELINE
    )


def test_con_linea_base_se_llenan_las_dos_que_le_corresponden_y_las_otras_tres_no() -> None:
    """Valores distintos por criterio e idioma, con las claves escritas a mano.

    Con los mismos numeros en todas partes --o con la clave tomada de la constante
    del modulo-- un cambio de criterio o de idioma pasaria igual.
    """
    base = linea_base(
        metrics={
            "field_extraction": {"es": 0.71, "en": 0.64},
            "citation_precision": {"es": 0.88, "en": 0.97},
        }
    )
    snapshot = build_snapshot(base, criteria=CRITERIOS)

    completitud = _figura(snapshot, FigureKey.COMPLETENESS)
    assert completitud.state is evidence.FigureState.MEASURED
    assert {i: c.value for i, c in completitud.by_language.items()} == {"es": 0.71, "en": 0.64}
    citacion = _figura(snapshot, FigureKey.CITATION_PRECISION)
    assert citacion.state is evidence.FigureState.MEASURED
    assert {i: c.value for i, c in citacion.by_language.items()} == {"es": 0.88, "en": 0.97}
    for clave in NO_MEDIDAS:
        figura = _figura(snapshot, clave)
        assert figura.state is evidence.FigureState.NOT_MEASURED, clave
        assert figura.not_measured_cause is not None
        assert all(c.value is None for c in figura.by_language.values())


def test_cada_cifra_medida_lleva_fecha_commit_y_corrida() -> None:
    snapshot = build_snapshot(linea_base(), criteria=CRITERIOS)

    medidas = [f for f in snapshot.figures if f.state is evidence.FigureState.MEASURED]
    assert len(medidas) == 2
    for figura in medidas:
        assert figura.source is not None
        assert figura.source.published_at == PUBLICADA
        assert figura.source.commit_sha == linea_base().commit_sha
        assert figura.source.run_id == "run-7"
        assert figura.source.run_url is None  # sin adonde llevar, no se inventa un enlace


def test_el_enlace_a_la_corrida_sale_de_quien_sabe_construirlo() -> None:
    snapshot = build_snapshot(
        linea_base(), run_url=lambda run: f"https://ejemplo.test/{run}", criteria=CRITERIOS
    )

    figura = _figura(snapshot, FigureKey.COMPLETENESS)
    assert figura.source is not None
    assert figura.source.run_url == "https://ejemplo.test/run-7"


def test_un_cero_medido_sigue_medido_y_un_criterio_ausente_nunca_es_cero() -> None:
    con_cero = build_snapshot(
        linea_base(metrics={"field_extraction": {"es": 0.0, "en": 0.0}, "citation_precision": {}}),
        criteria=CRITERIOS,
    )
    completitud = _figura(con_cero, FigureKey.COMPLETENESS)
    assert completitud.state is evidence.FigureState.MEASURED
    assert completitud.by_language["es"].value == 0.0

    citacion = _figura(con_cero, FigureKey.CITATION_PRECISION)
    assert citacion.state is evidence.FigureState.NOT_MEASURED
    assert citacion.not_measured_cause is evidence.NotMeasuredCause.CRITERION_ABSENT
    assert all(c.value is None for c in citacion.by_language.values())


def test_un_idioma_medido_y_el_otro_no_deja_cada_celda_en_su_estado() -> None:
    snapshot = build_snapshot(
        linea_base(metrics={"citation_precision": {"es": 0.9}}), criteria=CRITERIOS
    )

    citacion = _figura(snapshot, FigureKey.CITATION_PRECISION)
    assert citacion.state is evidence.FigureState.NOT_MEASURED
    assert citacion.by_language["es"].value == 0.9
    assert citacion.by_language["en"].value is None
    assert citacion.by_language["en"].not_measured_cause is not None
    assert citacion.source is None  # la cifra entera no se midio: no cita una corrida


def test_las_cifras_por_idioma_nunca_traen_un_promedio_combinado() -> None:
    snapshot = build_snapshot(linea_base(), criteria=CRITERIOS)

    for figura in snapshot.figures:
        assert set(figura.by_language) <= {"es", "en"}
    promedio = (0.96 + 0.93) / 2
    volcado = snapshot.model_dump_json()
    assert str(promedio) not in volcado
    assert str(round(promedio, 3)) not in volcado


def test_las_latencias_dicen_entre_que_eventos_sobre_que_conjunto_y_con_p50_y_p95() -> None:
    latencias = _figura(build_snapshot(linea_base()), FigureKey.LATENCY).latency

    assert {m.channel for m in latencias} == {"voice", "chat"}
    voz = next(m for m in latencias if m.channel == "voice")
    assert (voz.start, voz.end) == (
        evidence.LatencyEvent.SPEECH_END,
        evidence.LatencyEvent.FIRST_AUDIO,
    )
    chat = next(m for m in latencias if m.channel == "chat")
    assert (chat.start, chat.end) == (
        evidence.LatencyEvent.MESSAGE_SENT,
        evidence.LatencyEvent.FIRST_WORD,
    )
    for medida in latencias:
        assert medida.dataset
        assert {"p50", "p95"} <= set(medida.percentiles)
    assert (
        _figura(build_snapshot(None), FigureKey.LATENCY).not_measured_cause
        is evidence.NotMeasuredCause.MEASURED_PER_MILESTONE
    )


def test_las_cifras_salen_del_archivo_versionado_y_no_del_ultimo_reporte(raiz: Path) -> None:
    # Un reporte suelto en `tmp/` no cuenta (BR1.1): no tiene commit que citar.
    reportes = paths.reports_dir()
    reportes.mkdir(parents=True)
    (reportes / "ultimo.json").write_text('{"criteria": "no me lean"}', encoding="utf-8")

    sin_base = evidence.current_snapshot()
    assert sin_base.baseline_id is None
    assert all(f.state is evidence.FigureState.NOT_MEASURED for f in sin_base.figures)

    sembrar(linea_base())
    con_base = evidence.current_snapshot()
    # Lo que distingue "leyo la linea base" de "no leyo nada" es su cabecera, y no
    # que una cifra se llene: hoy ninguna puede, porque ningun criterio las mide.
    assert con_base.baseline_id == "base-0001"
    assert con_base.commit_sha == linea_base().commit_sha
    assert con_base.run_id == "run-7"


def test_una_linea_base_ilegible_falla_en_voz_alta_y_no_se_lee_como_no_medida(
    raiz: Path,
) -> None:
    archivo = paths.current_baseline_path()
    archivo.parent.mkdir(parents=True)
    archivo.write_text("{no es json", encoding="utf-8")

    with pytest.raises(LoadError, match=r"current\.json"):
        evidence.current_snapshot()


# --- Los invariantes estan en el tipo (BR1.2, BR1.3) -----------------------------


def _celda(**campos: Any) -> evidence.Measurement:
    return evidence.Measurement(**campos)


@pytest.mark.parametrize(
    "campos",
    [
        {"state": "not_measured"},
        {"state": "not_measured", "value": 0.0, "not_measured_cause": "no_baseline"},
        {"state": "not_measured", "value": 0.0},
        {"state": "measured"},
        {"state": "measured", "value": 0.5, "not_measured_cause": "no_baseline"},
    ],
    ids=["sin-causa", "cero-con-causa", "cero-sin-causa", "medida-sin-valor", "medida-con-causa"],
)
def test_una_celda_no_puede_afirmar_ni_un_cero_ni_un_hueco(campos: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _celda(**campos)


def test_una_cifra_no_medida_exige_su_causa() -> None:
    with pytest.raises(ValidationError):
        evidence.Figure(key=FigureKey.LATENCY, state=evidence.FigureState.NOT_MEASURED)


def test_una_cifra_medida_exige_su_origen() -> None:
    with pytest.raises(ValidationError):
        evidence.Figure(
            key=FigureKey.COMPLETENESS,
            state=evidence.FigureState.MEASURED,
            by_language={
                "es": evidence.Measurement(state=evidence.FigureState.MEASURED, value=0.9)
            },
        )


def test_el_panel_lleva_exactamente_las_cinco_cifras() -> None:
    cuatro = build_snapshot(None).figures[:4]
    with pytest.raises(ValidationError):
        evidence.MetricsSnapshot(figures=cuatro)
    with pytest.raises(ValidationError):
        evidence.MetricsSnapshot(figures=(*cuatro, cuatro[0]))


def test_hoy_ningun_criterio_mide_las_dos_cifras_y_el_panel_lo_dice_asi() -> None:
    """La primera version puso dos nombres inventados y el fallo era silencioso.

    Las dos cifras se quedaban "no medidas" con la causa equivocada --"la linea
    base no trae el criterio"--, que se lee como un problema de la linea base y
    manda a arreglar el sitio equivocado. La verdad es que **nadie ha construido
    todavia el criterio**: se comprobo sobre `app/evals/cases/`, donde los casos de
    citacion declaran `expected_verdicts: {}` a proposito.

    Esta prueba se cae el dia que alguien escriba un nombre en `CRITERIA`, que es
    justo el dia que hay que volver a leer por que estaba en nulo.
    """
    assert evidence.CRITERIA[FigureKey.COMPLETENESS] is None
    assert evidence.CRITERIA[FigureKey.CITATION_PRECISION] is None

    # Con linea base y sin criterio construido, la causa es la de "no construido",
    # no la de "la linea base no lo trae".
    snapshot = build_snapshot(linea_base())

    for clave in (FigureKey.COMPLETENESS, FigureKey.CITATION_PRECISION):
        figura = _figura(snapshot, clave)
        assert figura.state is evidence.FigureState.NOT_MEASURED
        assert figura.not_measured_cause is evidence.NotMeasuredCause.CRITERION_NOT_BUILT
        assert all(c.value is None for c in figura.by_language.values())


def test_cada_latencia_dice_por_que_no_esta_medida_y_no_es_la_misma_razon() -> None:
    """Las dos latencias no estan sin medir por lo mismo, y la diferencia manda a
    sitios distintos.

    La de la voz se mide por hito contra proveedores de verdad --una decision, y
    esperar el hito es lo correcto--. La del chat sale de la linea base y de ninguna otra
    parte: sin linea base la causa es esa, y con una que se publico antes de que la corrida
    midiera latencias es otra --no trae la seccion--. Una sola causa para todas diria "por
    hito" de algo que solo pide publicar una linea base.
    """
    sin_base = _figura(build_snapshot(None), FigureKey.LATENCY)
    assert {m.channel: m.not_measured_cause for m in sin_base.latency} == {
        "voice": evidence.NotMeasuredCause.MEASURED_PER_MILESTONE,
        "chat": evidence.NotMeasuredCause.NO_BASELINE,
    }

    # Una linea base publicada antes de que existiera la seccion: se lee igual, y dice la verdad.
    vieja = _figura(build_snapshot(linea_base()), FigureKey.LATENCY)
    assert {m.channel: m.not_measured_cause for m in vieja.latency} == {
        "voice": evidence.NotMeasuredCause.MEASURED_PER_MILESTONE,
        "chat": evidence.NotMeasuredCause.LATENCY_NOT_IN_BASELINE,
    }
    for latencia in (sin_base, vieja):
        for medida in latencia.latency:
            # Sin lecturas ni origen: un canal sin nada que decir no cita ninguna corrida.
            assert medida.by_language == {}
            assert medida.source is None
            # Y las dos siguen diciendo entre que eventos y sobre que conjunto (BR1.5).
            assert {"p50", "p95"} <= set(medida.percentiles)
            assert medida.dataset


# --- La latencia del chat que trae la linea base ----------------------------------


def _chat(snapshot: evidence.MetricsSnapshot) -> evidence.LatencyMeasure:
    [medida] = [m for m in _figura(snapshot, FigureKey.LATENCY).latency if m.channel == "chat"]
    return medida


def test_con_latencias_en_la_linea_base_el_chat_sale_medido_por_idioma_con_su_recuento() -> None:
    """Valores distintos por idioma y por percentil, escritos a mano: con los mismos numeros
    en todas partes un cambio de idioma o de percentil pasaria igual."""
    base = linea_base(
        latencies=latencia_de_chat(
            es=(52, 1180, 2810), en=(47, 1420, 3090), datasets=("DS-2", "DS-6")
        )
    )

    medida = _chat(build_snapshot(base))

    assert set(medida.by_language) == {"es", "en"}
    es, en = medida.by_language["es"], medida.by_language["en"]
    assert es.state is evidence.FigureState.MEASURED
    assert (es.p50_ms, es.p95_ms, es.turns) == (1180, 2810, 52)
    assert (en.p50_ms, en.p95_ms, en.turns) == (1420, 3090, 47)
    assert medida.not_measured_cause is None
    assert medida.dataset == "DS-2, DS-6"  # los conjuntos que de verdad aportaron turnos
    # Cita la corrida de la que sale, como toda cifra medida (BR1.3).
    assert medida.source is not None
    assert medida.source.run_id == "run-7"
    assert medida.source.published_at == PUBLICADA


def test_la_cifra_de_latencias_sigue_sin_medir_mientras_la_voz_lo_este() -> None:
    """El resumen de la cifra no se contradice con el de sus canales: medida solo si todas lo
    estan, y la voz se mide por hito."""
    snapshot = build_snapshot(
        linea_base(latencies=latencia_de_chat(es=(30, 900, 1500), en=(30, 800, 1400)))
    )

    figura = _figura(snapshot, FigureKey.LATENCY)
    assert figura.state is evidence.FigureState.NOT_MEASURED
    assert figura.by_language == {}
    assert figura.source is None


@pytest.mark.parametrize(
    ("turnos", "medida"),
    [(MIN_TURNS_PER_LANGUAGE, True), (MIN_TURNS_PER_LANGUAGE - 1, False), (0, False)],
    ids=["justo-el-minimo", "uno-menos", "ninguno"],
)
def test_con_pocos_turnos_la_latencia_sale_no_medida_con_su_recuento_y_no_una_cifra(
    turnos: int, medida: bool
) -> None:
    """El borde exacto: con el minimo se publica, con uno menos el «p95» seria el peor turno."""
    p50, p95 = (None, None) if turnos == 0 else (900, 2400)
    base = linea_base(
        latencies={
            "chat": {
                "datasets": ["DS-2"],
                "es": {"turns": turnos, "p50_ms": p50, "p95_ms": p95},
                "en": {"turns": 40, "p50_ms": 1000, "p95_ms": 2000},
            }
        }
    )

    es = _chat(build_snapshot(base)).by_language["es"]

    assert (es.state is evidence.FigureState.MEASURED) is medida
    assert es.turns == turnos
    if medida:
        assert (es.p50_ms, es.p95_ms) == (900, 2400)
        assert es.not_measured_cause is None
    else:
        assert (es.p50_ms, es.p95_ms) == (None, None)
        assert es.not_measured_cause is evidence.NotMeasuredCause.TOO_FEW_TURNS
    # El otro idioma no se contagia: cada uno se juzga por sus turnos.
    assert _chat(build_snapshot(base)).by_language["en"].state is evidence.FigureState.MEASURED


def test_las_latencias_nunca_traen_un_idioma_combinado_ni_un_promedio() -> None:
    base = linea_base(latencies=latencia_de_chat(es=(50, 1000, 2000), en=(50, 2000, 3000)))
    snapshot = build_snapshot(base)

    assert set(_chat(snapshot).by_language) <= {"es", "en"}
    volcado = snapshot.model_dump_json()
    # Los promedios de los dos idiomas (p50 = 1500, p95 = 2500) no aparecen en ninguna parte.
    assert '"p50_ms":1500' not in volcado
    assert '"p95_ms":2500' not in volcado


def test_las_latencias_no_cargan_ningun_identificador_de_caso_ni_de_turno() -> None:
    """Superficie publica (SEC-U22.1): la linea base trae casos con identificadores, y
    la respuesta del panel no puede heredarlos por el camino de las latencias."""
    base = linea_base(latencies=latencia_de_chat(es=(50, 1000, 2000), en=(50, 2000, 3000)))

    volcado = build_snapshot(base).model_dump_json()

    for caso in CASOS_SEMBRADOS:
        assert caso not in volcado


def test_una_linea_base_publicada_antes_de_las_latencias_se_sigue_leyendo(tmp_path: Path) -> None:
    """Aditiva: el archivo viejo no tiene la clave `latencies` y se lee con la seccion vacia."""
    viejo = json.loads(linea_base().model_dump_json())
    del viejo["latencies"]  # lo que habia en disco antes de este cambio
    archivo = tmp_path / "current.json"
    archivo.write_text(json.dumps(viejo), encoding="utf-8")

    leida = load_baseline(archivo)

    assert leida.latencies == {}
    assert _chat(build_snapshot(leida)).not_measured_cause is (
        evidence.NotMeasuredCause.LATENCY_NOT_IN_BASELINE
    )


@pytest.mark.parametrize(
    "campos",
    [
        {"state": "measured", "turns": 50},
        {
            "state": "measured",
            "p50_ms": 900,
            "p95_ms": 2000,
            "turns": 50,
            "not_measured_cause": "too_few_turns",
        },
        {"state": "measured", "p50_ms": 3000, "p95_ms": 2000, "turns": 50},
        {"state": "measured", "p50_ms": 900, "p95_ms": 2000, "turns": MIN_TURNS_PER_LANGUAGE - 1},
        {"state": "not_measured", "turns": 3},
        {"state": "not_measured", "p50_ms": 0, "p95_ms": 0, "not_measured_cause": "too_few_turns"},
    ],
    ids=[
        "medida-sin-tiempos",
        "medida-con-causa",
        "p50-mayor-que-p95",
        "medida-con-pocos-turnos",
        "no-medida-sin-causa",
        "cero-con-causa",
    ],
)
def test_una_lectura_de_latencia_no_puede_afirmar_un_cero_ni_un_p95_con_pocos_turnos(
    campos: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        evidence.LatencyReading(**campos)


def test_una_medida_de_latencia_es_un_canal_sin_nada_que_decir_o_lecturas_con_su_origen() -> None:
    lectura = evidence.LatencyReading(
        state=evidence.FigureState.MEASURED, p50_ms=900, p95_ms=2000, turns=50
    )
    comun: dict[str, Any] = {
        "channel": "chat",
        "start": evidence.LatencyEvent.MESSAGE_SENT,
        "end": evidence.LatencyEvent.FIRST_WORD,
        "dataset": "DS-2",
        "percentiles": ("p50", "p95"),
    }
    # Lecturas sin la corrida de la que salen.
    with pytest.raises(ValidationError):
        evidence.LatencyMeasure(**comun, by_language={"es": lectura})
    # Una causa para el canal entero y lecturas a la vez.
    with pytest.raises(ValidationError):
        evidence.LatencyMeasure(
            **comun,
            by_language={"es": lectura},
            not_measured_cause=evidence.NotMeasuredCause.NO_BASELINE,
        )
