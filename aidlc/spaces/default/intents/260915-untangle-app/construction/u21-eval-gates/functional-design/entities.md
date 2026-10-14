# Entidades — U21 `eval-gates`

U1 ya dejó el corredor, el reporte por caso y por idioma, y las causas de "no
medida" y "no comparable". U21 no rehace nada de eso: **agrega la memoria entre
corridas**, que es lo que convierte un reporte en una compuerta.

- **Archivos versionados, no tablas.** Las tres entidades nuevas viven en
  `app/evals/` como archivos del repositorio, por la misma razón que los casos
  de golden set: la compuerta corre en GitHub Actions, donde no hay base de
  datos, y lo que decide si una entrega pasa tiene que poder leerse en un diff.
- **Completa dos campos de U1:** `EvalRun.comparable` y `CaseResult.root_cause`
  existen desde U1 y hasta ahora nadie los llenaba.

## Entidades

```yaml
entities:

  - name: Baseline
    description: La foto de una corrida que queda como referencia. Se publica por hito y solo con las compuertas duras en verde (AC4.5.4).
    stored_in: "app/evals/baselines/<fecha>-<commit_corto>.json, con app/evals/baselines/current.json apuntando a la vigente"
    attributes:
      - { name: baseline_id, type: identifier, required: true, unique: true, constraint: "Fecha y commit corto, por ejemplo 2026-09-24-ee8d21d." }
      - { name: run_id, type: identifier, required: true, references: "EvalRun (U1)" }
      - { name: commit_sha, type: string, required: true }
      - { name: published_at, type: timestamp, required: true }
      - { name: case_verdicts, type: "map case_key → status", required: true, constraint: "El veredicto de cada caso: es lo que permite decir qué caso pasó a fallar (AC5.9.2)." }
      - { name: metrics, type: "map (criterio, idioma) → valor", required: true, constraint: "Por idioma, nunca combinado (P12)." }
      - { name: model_ids, type: "map uso → identificador", required: true, constraint: "Los mismos de la cabecera del reporte: una línea base sin ellos no es comparable con nada." }

  - name: JudgeCalibration
    description: Lo que el juez acertó contra las etiquetas humanas de DS-7, por criterio y por idioma (AC4.6.1).
    stored_in: "app/evals/calibrations/<judge_model>-<rubric_version>.json"
    attributes:
      - { name: calibration_id, type: identifier, required: true, unique: true }
      - { name: judge_model, type: string, required: true, constraint: "Identificador exacto del modelo, nunca un alias móvil." }
      - { name: rubric_version, type: string, required: true }
      - { name: measured_at, type: timestamp, required: true }
      - { name: split, type: enum, required: true, allowed_values: [fit, dev, test], constraint: "La calibración que cuenta se mide sobre la partición de prueba." }
      - { name: rates, type: "list of {criterion, language, tpr, tnr, n, ci_low_tpr, ci_low_tnr}", required: true, constraint: "TPR y TNR con n e intervalo, por criterio y por idioma; reemplaza el agreement_rate del catálogo de componentes (ADR-014)." }

  - name: UnstableCase
    description: Un caso que cambia de veredicto entre corridas idénticas. No cuenta para la compuerta y nunca se borra del set (P5).
    stored_in: "app/evals/unstable-cases.yaml"
    attributes:
      - { name: case_key, type: identifier, required: true, unique: true, references: "GoldenCase (U1)" }
      - { name: reason, type: text, required: true, constraint: "Qué se observó, no una excusa." }
      - { name: marked_at, type: date, required: true }
      - { name: run_ids, type: "list of identifier", required: true, constraint: "Al menos dos corridas del mismo commit con veredictos distintos: es la evidencia de la inestabilidad." }
      - { name: work_item, type: string, required: true, constraint: "Dónde quedó abierta su estabilización." }

  - name: RegressionExplanation
    description: La explicación escrita que desbloquea una regresión. No es una entidad del catálogo: es el archivo que exige AC5.9.2.
    stored_in: "app/evals/regressions.yaml"
    attributes:
      - { name: case_keys, type: "list of identifier", required: true, constraint: "Una explicación que no nombra identificadores no cuenta (AC5.9.2)." }
      - { name: root_cause, type: enum, required: true, constraint: "De la taxonomía del PRD 11.3, la misma que llena CaseResult.root_cause." }
      - { name: explained_at, type: date, required: true }
      - { name: commit_sha, type: string, required: true, constraint: "Desde qué commit vale: una explicación no cubre regresiones futuras." }
```

## Lo que se completa de U1

| Campo | Quién lo creó | Qué le agrega U21 |
| --- | --- | --- |
| `EvalRun.comparable` y `non_comparable_cause` | U1 | Los llena la compuerta cuando la corrida se cae por causa externa (AC5.9.5) |
| `CaseResult.root_cause` | U1 | Lo llena el reporte con la taxonomía del PRD 11.3 (AC4.5.1) |
| `CaseRow.criteria_results` | U1 | Gana el **tipo de juicio** de cada criterio: código, juez o humano (AC4.5.1) |

## Sources

- `../../../inception/units-generation/unit-of-work.md` — sección U21 y la tabla
  "Entidades por unidad".
- `../../../inception/domain-design/components.md` — Evaluation y la tabla de
  propiedad de entidades.
- `../../../inception/user-stories/stories.md` — US4.5, US4.6, US4.14 y US5.9.
- `app/backend/src/untangle/evals/report.py` y `models.py` — lo que U1 ya dejó.

## Assumptions & Open Questions

- **El tamaño de DS-7** (40 transcripciones etiquetadas, 20 por idioma) y su
  reparto en particiones sale de US4.6; el momento de etiquetarlas lo decide
  Miguel y está en las preguntas de esta etapa.
