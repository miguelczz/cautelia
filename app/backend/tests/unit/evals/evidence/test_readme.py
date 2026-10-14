"""Las dos secciones generadas del README (U22: BR4.1, BR4.2, tanda 3).

Puras: reciben el texto del README y una linea base, sin tocar el archivo real.
"""

from __future__ import annotations

import pytest

from untangle.evals.evidence import api as evidence
from untangle.evals.evidence import readme
from untangle.evals.evidence.snapshot import build_snapshot
from untangle.evals.gates.models import Baseline, LastRunDigest
from untangle.evals.latency_summary import ChannelLatency, LatencySummary
from untangle.evals.models import CaseStatus, Channel, NotMeasuredCause, RootCause

from .builders import PUBLICADA

Section = readme.Section
COMMIT = "0123456789abcdef0123456789abcdef01234567"

ESQUELETO = """# Untangle

Intro.

## What it does

Narrativa de Miguel.

## How it fails

{how}

## Evaluation report

{report}

## Run it

Otra narrativa.
"""


def _esqueleto() -> str:
    def vacio(s: Section) -> str:
        return f"{readme.begin_marker(s)}\n{readme.end_marker(s)}"

    return ESQUELETO.format(
        how=vacio(Section.HOW_IT_FAILS), report=vacio(Section.EVALUATION_REPORT)
    )


def _base(verdicts: dict[str, CaseStatus] | None = None) -> Baseline:
    return Baseline.model_validate(
        {
            "baseline_id": "2026-10-01-0123456",
            "run_id": "run-7",
            "commit_sha": COMMIT,
            "published_at": PUBLICADA,
            "case_verdicts": verdicts or {"DS-2/es/001": CaseStatus.PASSED},
            "metrics": {"field_extraction": {"es": 0.96, "en": 0.93}},
            "model_ids": {"chat": "modelo-de-prueba"},
        }
    )


#: El commit del resumen es **otro** que el de la linea base a proposito: una prueba
#: que cite el de la linea base en lugar del suyo tiene que caerse.
COMMIT_RESUMEN = "fedcba9876543210fedcba9876543210fedcba98"


def _resumen(
    verdicts: dict[str, CaseStatus],
    causas: dict[str, RootCause] | None = None,
    no_medidos: dict[str, NotMeasuredCause] | None = None,
) -> LastRunDigest:
    return LastRunDigest.model_validate(
        {
            "run_id": "run-9",
            "commit_sha": COMMIT_RESUMEN,
            "produced_at": PUBLICADA,
            "case_verdicts": verdicts,
            "root_causes": causas or {},
            "not_measured_causes": no_medidos
            if no_medidos is not None
            else {
                caso: NotMeasuredCause.PROVIDER_KEY_MISSING
                for caso, estado in verdicts.items()
                if estado is CaseStatus.NOT_MEASURED
            },
        }
    )


FALLOS = {
    "DS-2/es/017": CaseStatus.FAILED,
    "DS-2/es/003": CaseStatus.FAILED,
    "DS-3/en/004": CaseStatus.FAILED,
    "DS-6/es/001": CaseStatus.FAILED,
    "DS-2/en/001": CaseStatus.PASSED,
    "DS-5/es/002": CaseStatus.NOT_MEASURED,
}
CAUSAS = {
    "DS-2/es/017": RootCause.EXTRACTION,
    "DS-2/es/003": RootCause.EXTRACTION,
    "DS-3/en/004": RootCause.VERIFICATION,
}


def test_sin_linea_base_las_dos_secciones_dicen_no_medida_con_su_causa() -> None:
    secciones = readme.render_sections(None, None)
    cifras = secciones[Section.EVALUATION_REPORT]

    assert "Not measured" in secciones[Section.HOW_IT_FAILS]
    assert "no full evaluation run has been recorded" in secciones[Section.HOW_IT_FAILS]
    assert "Not measured" in cifras
    # Ninguna cifra en cero donde lo cierto es "no medida" (BR1.2).
    assert "0.0 %" not in cifras
    assert " 0 %" not in cifras
    # **Y cada celda con su causa, no solo el encabezado.** Sin estas dos lineas,
    # dibujar toda celda como un guion dejaba la prueba en verde: lo unico que se
    # caia era la comparacion contra el README del repositorio, y esa vuelve al
    # verde en cuanto alguien corre `readme:gen`.
    assert "  - Spanish: not measured (no criterion measures this yet)" in cifras
    assert "  - English: not measured (no criterion measures this yet)" in cifras
    assert "not measured (not recorded in the baseline; the live panel shows it)" in cifras


def test_como_falla_agrupa_por_causa_raiz_nombra_los_casos_y_cita_el_commit() -> None:
    cuerpo = readme.render_how_it_fails(_resumen(FALLOS, CAUSAS))

    assert COMMIT_RESUMEN in cuerpo
    assert "run `run-9`" in cuerpo
    assert "- **extraction** (2): `DS-2/es/003`, `DS-2/es/017`" in cuerpo
    assert "- **verification** (1): `DS-3/en/004`" in cuerpo
    # Un fallo sin causa registrada no se adivina: se dice que no la tiene.
    assert "- **no root cause recorded** (1): `DS-6/es/001`" in cuerpo


def test_como_falla_cita_el_commit_del_resumen_y_no_el_de_la_linea_base() -> None:
    # Las dos fuentes tienen commits distintos: la seccion es del resumen (BR4.1).
    secciones = readme.render_sections(_base(), _resumen(FALLOS, CAUSAS))

    assert COMMIT_RESUMEN in secciones[Section.HOW_IT_FAILS]
    assert COMMIT not in secciones[Section.HOW_IT_FAILS]
    assert "run-7" not in secciones[Section.HOW_IT_FAILS]


def test_los_grupos_salen_en_el_orden_de_la_taxonomia_y_no_en_el_de_los_casos() -> None:
    cuerpo = readme.render_how_it_fails(_resumen(FALLOS, CAUSAS))

    assert cuerpo.index("**extraction**") < cuerpo.index("**verification**")


def test_un_caso_no_medido_se_nombra_aparte_con_su_causa_y_nunca_cuenta_como_fallo() -> None:
    cuerpo = readme.render_how_it_fails(_resumen(FALLOS, CAUSAS))

    assert "4 of 6 cases failed" in cuerpo
    assert "1 cases were not measured, which is not the same as failing:" in cuerpo
    assert "- `DS-5/es/002`: provider key missing" in cuerpo
    # Los cuatro fallos de 6: si el no medido contara, serian 5 de 6.
    assert "5 of 6" not in cuerpo
    assert "`DS-5/es/002`" not in cuerpo.split("not measured")[0]


def test_la_causa_de_cada_no_medido_es_la_suya_y_no_una_para_todos() -> None:
    cuerpo = readme.render_how_it_fails(
        _resumen(
            {"DS-5/es/001": CaseStatus.NOT_MEASURED, "DS-5/es/002": CaseStatus.NOT_MEASURED},
            no_medidos={
                "DS-5/es/001": NotMeasuredCause.QUOTA_EXHAUSTED,
                "DS-5/es/002": NotMeasuredCause.TARGET_UNAVAILABLE,
            },
        )
    )

    assert "- `DS-5/es/001`: quota exhausted" in cuerpo
    assert "- `DS-5/es/002`: no live deployment to run against" in cuerpo


def test_un_resumen_sin_fallos_lo_dice_y_no_inventa_grupos() -> None:
    cuerpo = readme.render_how_it_fails(_resumen({"DS-2/es/001": CaseStatus.PASSED}))

    assert "No case failed" in cuerpo
    assert "**" not in cuerpo


def test_las_cifras_por_idioma_salen_lado_a_lado_con_su_fecha_y_su_commit() -> None:
    base = _base()
    snapshot = build_snapshot(base, criteria={evidence.FigureKey.COMPLETENESS: "field_extraction"})

    cuerpo = readme.render_evaluation_report(snapshot)

    assert "Spanish: 96.0 %" in cuerpo
    assert "English: 93.0 %" in cuerpo
    assert "commit `0123456`" in cuerpo
    assert "2026-10-01" in cuerpo
    # Cada cifra medida trae **su propia** fecha, commit y corrida (BR1.3), y no
    # basta con que el encabezado los repita: quitar la linea por cifra no caia
    # ninguna prueba, porque el commit del encabezado satisfacia la asercion.
    assert "  - source: baseline `2026-10-01-0123456`, commit `0123456`, run `run-7`" in cuerpo
    # Nunca un promedio combinado (BR1.4): 94.5 es el que saldria de mezclarlos.
    assert "94.5" not in cuerpo


def test_las_latencias_dicen_entre_que_eventos_sobre_que_conjunto_y_con_que_percentiles() -> None:
    cuerpo = readme.render_sections(None, None)[Section.EVALUATION_REPORT]

    assert "`speech_end` to `first_audio` on DS-5, p50 and p95" in cuerpo
    assert "`message_sent` to `first_word` on DS-2, p50 and p95" in cuerpo


def _con_latencias(es: LatencySummary, en: LatencySummary) -> Baseline:
    return _base().evolve(
        latencies={Channel.CHAT: ChannelLatency(datasets=("DS-2", "DS-6"), es=es, en=en)}
    )


def test_la_latencia_del_chat_medida_sale_por_idioma_con_su_recuento_y_su_corrida() -> None:
    base = _con_latencias(
        LatencySummary(turns=52, p50_ms=1180, p95_ms=2810),
        LatencySummary(turns=47, p50_ms=420, p95_ms=3090),
    )

    cuerpo = readme.render_evaluation_report(build_snapshot(base))

    assert "`message_sent` to `first_word` on DS-2, DS-6, p50 and p95" in cuerpo
    # Que mide y que no incluye: una cifra de latencia sin decirlo esta prohibida (P4).
    assert "from the moment the server receives the message" in cuerpo
    assert "the visitor's network is not included" in cuerpo
    assert "    - Spanish: p50 1.2 s, p95 2.8 s, over 52 turns" in cuerpo
    assert "    - English: p50 420 ms, p95 3.1 s, over 47 turns" in cuerpo
    assert "    - source: baseline `2026-10-01-0123456`, commit `0123456`, run `run-7`" in cuerpo
    # Y nunca la causa de la voz (por hito) donde el chat ya midio.
    chat = next(linea for linea in cuerpo.splitlines() if linea.startswith("  - chat:"))
    assert "milestone" not in chat
    # Nunca un promedio de los dos idiomas.
    assert "p50 800 ms" not in cuerpo


def test_con_pocos_turnos_el_readme_dice_no_medida_y_cuantos_hubo_y_no_una_cifra() -> None:
    base = _con_latencias(
        LatencySummary(turns=12, p50_ms=900, p95_ms=2400),
        LatencySummary(turns=47, p50_ms=420, p95_ms=3090),
    )

    cuerpo = readme.render_evaluation_report(build_snapshot(base))

    assert "    - Spanish: not measured (only 12 turns measured; at least 20 are needed)" in cuerpo
    assert "2.4 s" not in cuerpo and "2400" not in cuerpo
    assert "    - English: p50 420 ms, p95 3.1 s, over 47 turns" in cuerpo


def test_una_linea_base_sin_latencias_dice_la_verdad_en_el_readme() -> None:
    cuerpo = readme.render_evaluation_report(build_snapshot(_base()))

    chat = next(linea for linea in cuerpo.splitlines() if linea.startswith("  - chat:"))
    assert chat.endswith("not measured (the published baseline carries no latencies)")


@pytest.mark.parametrize(
    ("ms", "texto"),
    [
        (0, "0 ms"),
        (999, "999 ms"),
        (1000, "1.0 s"),
        (1249, "1.2 s"),
        (1250, "1.3 s"),
        (12_340, "12.3 s"),
    ],
)
def test_los_tiempos_se_dicen_como_el_panel_los_dice(ms: int, texto: str) -> None:
    """La mitad hacia arriba y en enteros: las dos superficies muestran lo mismo en los empates."""
    assert readme._duration(ms) == texto


def test_toda_causa_cerrada_tiene_su_frase() -> None:
    # Si alguien anade un valor a una taxonomia cerrada, el README no puede caer a
    # un KeyError en la compuerta: esta prueba lo atrapa primero.
    assert set(readme.NOT_MEASURED_TEXT) == set(evidence.NotMeasuredCause)
    assert set(readme.CASE_NOT_MEASURED_TEXT) == set(NotMeasuredCause)
    assert set(readme.ROOT_CAUSE_TEXT) == set(RootCause)
    assert set(readme.FIGURE_TEXT) == set(evidence.FigureKey)


def test_regenerar_reemplaza_solo_entre_las_marcas_y_respeta_el_resto() -> None:
    texto = _esqueleto()

    nuevo = readme.regenerate(texto, _base(), _resumen(FALLOS, CAUSAS))

    assert "DS-2/es/017" in nuevo
    assert "Narrativa de Miguel." in nuevo
    assert "Otra narrativa." in nuevo
    assert nuevo.startswith("# Untangle\n\nIntro.\n\n## What it does")
    assert nuevo.rstrip().endswith("Otra narrativa.")


def test_regenerar_dos_veces_da_lo_mismo() -> None:
    una = readme.regenerate(_esqueleto(), _base(), _resumen(FALLOS, CAUSAS))

    assert readme.regenerate(una, _base(), _resumen(FALLOS, CAUSAS)) == una


def test_lo_regenerado_pasa_el_chequeo_con_cualquier_combinacion_de_fuentes() -> None:
    for base in (None, _base()):
        for resumen in (None, _resumen(FALLOS, CAUSAS)):
            texto = readme.regenerate(_esqueleto(), base, resumen)
            assert readme.check(texto, base, resumen) == []


def test_editar_a_mano_una_seccion_falla_nombrandola() -> None:
    resumen = _resumen(FALLOS, CAUSAS)
    texto = readme.regenerate(_esqueleto(), _base(), resumen).replace("DS-3/en/004", "DS-3/en/999")

    problemas = readme.check(texto, _base(), resumen)

    assert [p.section for p in problemas] == [Section.HOW_IT_FAILS]
    assert "section 'How it fails'" in str(problemas[0])
    assert "DS-3/en/999" in str(problemas[0])


def test_un_resumen_nuevo_deja_obsoleta_solo_la_seccion_de_fallos() -> None:
    viejo = readme.regenerate(_esqueleto(), _base(), None)

    problemas = readme.check(viejo, _base(), _resumen(FALLOS, CAUSAS))

    assert [p.section for p in problemas] == [Section.HOW_IT_FAILS]


def test_una_linea_base_nueva_deja_obsoleta_solo_la_seccion_de_cifras() -> None:
    viejo = readme.regenerate(_esqueleto(), None, _resumen(FALLOS, CAUSAS))

    problemas = readme.check(viejo, _base(), _resumen(FALLOS, CAUSAS))

    assert [p.section for p in problemas] == [Section.EVALUATION_REPORT]


def test_cambiar_una_narrativa_no_pone_rojo_el_chequeo() -> None:
    resumen = _resumen(FALLOS, CAUSAS)
    texto = readme.regenerate(_esqueleto(), _base(), resumen).replace(
        "Narrativa de Miguel.", "Otra cosa."
    )

    assert readme.check(texto, _base(), resumen) == []


def test_unas_marcas_que_faltan_o_se_repiten_son_un_problema_y_no_un_silencio() -> None:
    generado = readme.regenerate(_esqueleto(), None, None)
    sin = generado.replace(readme.begin_marker(Section.EVALUATION_REPORT), "")
    doble = generado + generado

    assert [p.section for p in readme.check(sin, None, None)] == [Section.EVALUATION_REPORT]
    assert {p.section for p in readme.check(doble, None, None)} == {
        Section.HOW_IT_FAILS,
        Section.EVALUATION_REPORT,
    }
    with pytest.raises(readme.MarkersError, match="How it fails"):
        readme.regenerate(doble, None, None)
