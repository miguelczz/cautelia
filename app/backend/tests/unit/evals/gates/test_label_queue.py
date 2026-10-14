"""La eleccion de turnos para la cola de DS-7: reproducible, con paridad y sin que lo facil mande.

Todo con una corrida de mentira escrita aqui: nada llama a un modelo ni lee la corrida real.
"""

from __future__ import annotations

from collections import Counter
from datetime import date

from untangle.base import Locale
from untangle.evals.gates import judged_criteria, label_queue
from untangle.evals.gates.label_queue import Existing, plan_queue
from untangle.evals.gates.models import HumanLabel, LabelingQueueEntry, LabelVerdict, Split
from untangle.evals.transcripts import TranscriptsFile

from .builders import conversacion, corrida, corrida_completa

CRITERIOS = judged_criteria.DEFAULT_NAMES


def _senales_de(archivo: TranscriptsFile) -> dict[tuple[str, int], tuple[str, ...]]:
    return {
        (label_queue.transcript_id(c.case_key, archivo.run_id), t.index): t.signals
        for c in archivo.conversations
        for t in c.turns
    }


def _por_idioma(
    entradas: tuple[LabelingQueueEntry, ...], idioma: Locale
) -> list[LabelingQueueEntry]:
    return [e for e in entradas if e.language == idioma]


# --- Reproducible ----------------------------------------------------------------


def test_dos_corridas_del_comando_dan_la_misma_cola() -> None:
    archivo = corrida_completa()

    assert plan_queue(archivo).new_entries == plan_queue(archivo).new_entries


def test_otra_semilla_da_otra_cola() -> None:
    archivo = corrida_completa()

    uno = {(e.transcript_id, e.turn_index, e.criterion) for e in plan_queue(archivo).new_entries}
    otro = {
        (e.transcript_id, e.turn_index, e.criterion)
        for e in plan_queue(archivo, seed="otra-semilla").new_entries
    }

    assert uno != otro


def test_el_orden_de_las_conversaciones_en_el_archivo_no_cambia_la_cola() -> None:
    archivo = corrida_completa()
    al_reves = corrida(*reversed(archivo.conversations))

    assert {
        (e.transcript_id, e.turn_index, e.criterion, e.split)
        for e in plan_queue(archivo).new_entries
    } == {
        (e.transcript_id, e.turn_index, e.criterion, e.split)
        for e in plan_queue(al_reves).new_entries
    }


# --- Paridad y cantidades --------------------------------------------------------


def test_veinte_por_idioma_repartidos_entre_los_criterios() -> None:
    plan = plan_queue(corrida_completa())

    assert plan.shortfall == {"es": 0, "en": 0}
    for idioma in ("es", "en"):
        propias = _por_idioma(plan.new_entries, idioma)
        assert len(propias) == 20
        por_criterio = Counter(e.criterion for e in propias)
        assert set(por_criterio) == set(CRITERIOS)
        # 20 entre 3 criterios: 7, 7 y 6 -- nadie queda sin criterio ni con mucho mas.
        assert sorted(por_criterio.values()) == [6, 7, 7]


def test_la_paridad_se_cuenta_por_el_idioma_del_texto_y_no_por_el_del_caso() -> None:
    """RT-10: un caso en espanol con turnos en ingles aporta a la cola en ingles."""
    mezclada = conversacion("mezcla", "es", turnos_de_la_agente=10)
    turnos = tuple(t.evolve(language="en") if t.index >= 11 else t for t in mezclada.turns)
    archivo = corrida(mezclada.evolve(turns=turnos))

    plan = plan_queue(archivo, per_language=20)

    assert plan.eligible == {"es": 5, "en": 5}
    assert {e.language for e in plan.new_entries} == {"es", "en"}
    en_ingles = [e for e in plan.new_entries if e.language == "en"]
    assert all(e.turn_index >= 11 for e in en_ingles)


def test_si_un_idioma_no_alcanza_lo_dice_con_la_cifra_y_no_rellena() -> None:
    archivo = corrida(
        *(conversacion(f"c{n}", "es") for n in range(4)),
        conversacion("unica", "en", turnos_de_la_agente=3),
    )

    plan = plan_queue(archivo)

    assert plan.eligible == {"es": 40, "en": 3}
    assert plan.shortfall == {"es": 0, "en": 17}
    assert len(_por_idioma(plan.new_entries, "en")) == 3
    # Nada de rellenar con otro idioma: en espanol siguen siendo 20, no 37.
    assert len(_por_idioma(plan.new_entries, "es")) == 20
    assert all("unica" in e.transcript_id for e in _por_idioma(plan.new_entries, "en"))


def test_una_corrida_sin_ningun_turno_de_un_idioma_no_inventa_ninguno() -> None:
    archivo = corrida(*(conversacion(f"c{n}", "es") for n in range(4)))

    plan = plan_queue(archivo)

    assert _por_idioma(plan.new_entries, "en") == []
    assert plan.shortfall["en"] == 20


# --- Lo facil no es mayoria ------------------------------------------------------


def test_cuando_hay_turnos_marcados_por_el_codigo_son_la_mitad_o_mas_de_cada_criterio() -> None:
    archivo = corrida_completa()  # solo 1 de cada 5 turnos esta marcado
    senales = _senales_de(archivo)

    plan = plan_queue(archivo)

    for idioma in ("es", "en"):
        propias = _por_idioma(plan.new_entries, idioma)
        for criterio in ("voice_guide", "answer_relevance"):
            del_criterio = [e for e in propias if e.criterion == criterio]
            marcados = [
                e
                for e in del_criterio
                if judged_criteria.is_flagged(criterio, senales[(e.transcript_id, e.turn_index)])
            ]
            # Al azar saldria cerca del 20 %; aqui es la mitad o mas.
            assert len(marcados) * 2 >= len(del_criterio), (idioma, criterio)


def test_los_limpios_tambien_entran_no_solo_los_marcados() -> None:
    plan = plan_queue(corrida_completa())

    for estadistica in plan.stats:
        assert estadistica.added_clean > 0, (estadistica.language, estadistica.criterion)


def test_sin_ningun_turno_marcado_se_dice_y_no_se_inventa_una_dificultad() -> None:
    plan = plan_queue(corrida_completa(marcado_cada=None))

    for estadistica in plan.stats:
        assert estadistica.flagged_in_run == 0
        assert estadistica.added_flagged == 0
    # La cola se llena igual, de turnos limpios, y la cifra lo dice.
    for idioma in ("es", "en"):
        limpias = sum(s.added_clean for s in plan.stats if s.language == idioma)
        assert limpias == len(_por_idioma(plan.new_entries, idioma)) == 20


def test_el_criterio_de_alcance_solo_se_marca_con_la_guardia() -> None:
    """`scope_adherence` no se marca por preguntas ni por largo: solo por la guardia de salida."""
    con_guardia = corrida_completa(senal="guard:coverage_promise")

    plan = plan_queue(con_guardia)

    alcance = [s for s in plan.stats if s.criterion == "scope_adherence"]
    assert all(s.flagged_in_run > 0 and s.added_flagged > 0 for s in alcance)
    voz = [s for s in plan.stats if s.criterion == "voice_guide"]
    assert all(s.flagged_in_run == 0 for s in voz)


def test_si_hay_menos_marcados_de_los_que_se_quieren_se_toman_todos_y_se_completa_con_limpios() -> (
    None
):
    # Dos conversaciones por idioma con un turno marcado y dos sin ninguno: 2 marcados por
    # idioma, y `voice_guide` querria 4 (la mitad de 7, redondeada hacia arriba).
    archivo = corrida(
        *(
            conversacion(f"c{n}", idioma, marcado_cada=10 if n < 2 else None)
            for idioma in ("es", "en")
            for n in range(4)
        )
    )

    plan = plan_queue(archivo)

    voz_es = next(s for s in plan.stats if s.criterion == "voice_guide" and s.language == "es")
    assert voz_es.flagged_in_run == 2
    assert voz_es.added_flagged == 2
    assert voz_es.added_flagged + voz_es.added_clean == 7


# --- Que se elige y que no ---------------------------------------------------------


def test_la_apertura_y_los_turnos_de_la_persona_nunca_se_etiquetan() -> None:
    archivo = corrida_completa()
    permitidos = {
        (label_queue.transcript_id(c.case_key, archivo.run_id), t.index)
        for c in archivo.conversations
        for t in c.turns
        if t.speaker == "agent" and not t.opening
    }

    plan = plan_queue(archivo)

    assert {(e.transcript_id, e.turn_index) for e in plan.new_entries} <= permitidos


def test_un_turno_no_se_reparte_a_dos_criterios() -> None:
    plan = plan_queue(corrida_completa())

    turnos = Counter((e.transcript_id, e.turn_index) for e in plan.new_entries)
    assert max(turnos.values()) == 1


def test_ninguna_conversacion_domina_la_cola() -> None:
    plan = plan_queue(corrida_completa())

    for idioma in ("es", "en"):
        por_conversacion = Counter(e.transcript_id for e in _por_idioma(plan.new_entries, idioma))
        assert len(por_conversacion) == 4
        assert max(por_conversacion.values()) - min(por_conversacion.values()) <= 1


def test_las_conversaciones_sin_senales_no_entran_y_se_cuentan() -> None:
    archivo = corrida(
        conversacion("con", "es"),
        conversacion("sin", "es").evolve(signals_read=False),
    )

    plan = plan_queue(archivo, per_language=5)

    assert plan.unsignaled_conversations == 1
    assert all("con@" in e.transcript_id for e in plan.new_entries)


def test_cada_entrada_lleva_lo_que_la_persona_dijo_justo_antes() -> None:
    plan = plan_queue(corrida_completa())

    for entrada in plan.new_entries:
        nombre = entrada.agent_text.split(" ", 2)[2]
        k = entrada.agent_text.split(" ")[1]
        assert entrada.context == f"persona {k} {nombre}"


def test_el_identificador_de_la_transcripcion_lleva_la_corrida() -> None:
    plan = plan_queue(corrida(conversacion("c0", "es"), run_id="run-abc"), per_language=3)

    assert all(e.transcript_id == "DS-2/es/c0@run-abc" for e in plan.new_entries)


# --- Particiones -------------------------------------------------------------------


def test_la_mitad_de_cada_idioma_queda_en_la_particion_de_prueba_y_las_tres_existen() -> None:
    plan = plan_queue(corrida_completa())

    for idioma in ("es", "en"):
        particiones = Counter(e.split for e in _por_idioma(plan.new_entries, idioma))
        assert set(particiones) == {Split.FIT, Split.DEV, Split.TEST}
        assert 8 <= particiones[Split.TEST] <= 12
    for estadistica in plan.stats:
        assert estadistica.test_total >= 2, (estadistica.language, estadistica.criterion)


def test_la_prueba_recibe_marcados_y_limpios() -> None:
    """Si `test` fuera solo de limpios, la calibracion no tendria ningun "falla" que medir."""
    archivo = corrida_completa()
    senales = _senales_de(archivo)

    plan = plan_queue(archivo)

    for idioma in ("es", "en"):
        en_prueba = [e for e in _por_idioma(plan.new_entries, idioma) if e.split is Split.TEST]
        marcadas = [
            judged_criteria.is_flagged(e.criterion, senales[(e.transcript_id, e.turn_index)])
            for e in en_prueba
        ]
        assert any(marcadas)
        assert not all(marcadas)


# --- Lo que ya hay ------------------------------------------------------------------


def _etiqueta(entrada: LabelingQueueEntry) -> HumanLabel:
    return HumanLabel(
        transcript_id=entrada.transcript_id,
        turn_index=entrada.turn_index,
        criterion=entrada.criterion,
        language=entrada.language,
        split=entrada.split,
        verdict=LabelVerdict.PASS,
        labeled_at=date(2026, 10, 14),
    )


def test_con_la_cola_ya_completa_no_agrega_nada() -> None:
    archivo = corrida_completa()
    primera = plan_queue(archivo)

    segunda = plan_queue(archivo, existing=Existing(queue=primera.new_entries))

    assert segunda.new_entries == ()
    assert segunda.shortfall == {"es": 0, "en": 0}


def test_agrega_solo_lo_que_falta_y_deja_lo_puesto_intacto_y_primero() -> None:
    archivo = corrida_completa()
    ya = plan_queue(archivo, per_language=10).new_entries
    ya_etiquetadas = tuple(_etiqueta(e) for e in ya[:6])

    plan = plan_queue(archivo, existing=Existing(queue=ya, labels=ya_etiquetadas))

    juntas = label_queue.merge(ya, plan.new_entries)
    assert juntas[: len(ya)] == ya
    claves = [(e.transcript_id, e.turn_index, e.criterion) for e in juntas]
    assert len(claves) == len(set(claves)), "una entrada se repitio"
    for idioma in ("es", "en"):
        assert len(_por_idioma(juntas, idioma)) == 20
    # Y los turnos que ya estaban no se vuelven a elegir para otro criterio.
    turnos = Counter((e.transcript_id, e.turn_index) for e in juntas)
    assert max(turnos.values()) == 1


def test_una_etiqueta_sin_su_entrada_en_la_cola_cuenta_y_su_turno_no_se_vuelve_a_elegir() -> None:
    archivo = corrida_completa()
    puestas = plan_queue(archivo).new_entries
    solo_etiquetas = tuple(_etiqueta(e) for e in _por_idioma(puestas, "es")[:3])

    plan = plan_queue(archivo, existing=Existing(labels=solo_etiquetas))

    assert len(_por_idioma(plan.new_entries, "es")) == 17
    etiquetados = {(e.transcript_id, e.turn_index) for e in solo_etiquetas}
    assert not etiquetados & {(e.transcript_id, e.turn_index) for e in plan.new_entries}


def test_un_criterio_con_mas_entradas_ya_puestas_recibe_menos_nuevas() -> None:
    archivo = corrida_completa()
    puestas = plan_queue(archivo).new_entries
    solo_voz = tuple(e for e in _por_idioma(puestas, "es") if e.criterion == "voice_guide")

    plan = plan_queue(archivo, existing=Existing(queue=solo_voz))
    nuevas_es = _por_idioma(plan.new_entries, "es")

    por_criterio = Counter(e.criterion for e in nuevas_es) + Counter(e.criterion for e in solo_voz)
    assert max(por_criterio.values()) - min(por_criterio.values()) <= 1


def test_la_cola_de_otra_corrida_no_estorba_a_esta() -> None:
    """El mismo caso en otra corrida es otro texto: sus entradas no bloquean las de esta."""
    vieja = plan_queue(corrida(conversacion("c0", "es"), run_id="run-vieja"), per_language=3)

    plan = plan_queue(
        corrida(conversacion("c0", "es"), run_id="run-nueva"),
        existing=Existing(queue=vieja.new_entries),
        per_language=6,
    )

    assert len(_por_idioma(plan.new_entries, "es")) == 3
    assert all(e.transcript_id.endswith("@run-nueva") for e in plan.new_entries)


# --- El orden en que se etiqueta -------------------------------------------------------


def test_la_cola_alterna_idioma_y_criterio_para_que_dejarla_a_medias_no_sesgue() -> None:
    plan = plan_queue(corrida_completa())
    entradas = plan.new_entries

    assert [e.language for e in entradas[:4]] == ["es", "en", "es", "en"]
    for corte in (6, 12, 18, 30):
        prefijo = entradas[:corte]
        assert len(_por_idioma(prefijo, "es")) == len(_por_idioma(prefijo, "en"))
    assert {e.criterion for e in entradas[:6]} == set(CRITERIOS)


# --- La aritmetica de la calibracion -----------------------------------------------------


def test_para_encender_al_juez_hacen_falta_16_etiquetas_de_cada_clase_en_prueba() -> None:
    """Con el umbral vigente de 0,80 sobre el limite inferior de Wilson, un juez perfecto
    necesita 16 aciertos de 16: con 15 el limite es 0,796. Es aritmetica, no una opinion."""
    assert label_queue.min_labels_per_class() == 16
    assert label_queue.min_labels_per_class(0.5) < 16
