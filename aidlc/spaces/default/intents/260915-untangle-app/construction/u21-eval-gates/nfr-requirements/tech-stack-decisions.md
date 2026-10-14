# Decisiones de stack — U21 `eval-gates`

U21 no agrega ninguna dependencia de ejecución. Las cuatro decisiones de esta
unidad son sobre **qué se escribe a mano y qué no**.

| # | Decisión | Por qué |
| --- | --- | --- |
| TECH-U21.1 | El intervalo de confianza de TPR y TNR se calcula con el método de Wilson, escrito a mano (unas diez líneas), sin `scipy` ni `statsmodels` | Traer una biblioteca científica de decenas de megabytes para una fórmula cerrada no se justifica: la regla del equipo pide una razón por dependencia nueva, y aquí no la hay. Wilson además se comporta mejor que la aproximación normal con n de 20, que es el tamaño de DS-7 por idioma |
| TECH-U21.2 | El segundo detector es determinista: patrones propios y validadores de formato para teléfono, cédula, placa y número de póliza, sin modelo de lenguaje y sin `presidio` | Mecanismo distinto del reconocimiento estadístico de U3 (ADR-013, AC4.14.1). Además corre sin clave de proveedor y no puede caerse por cuota, que es lo que se le pide a una compuerta |
| TECH-U21.3 | El juez usa el modelo del tier gratuito ya configurado (ADR-006), con la rúbrica versionada por criterio y su identificador exacto de modelo en la configuración | Cambiar modelo o rúbrica dispara la recalibración (BR3.2); con un alias móvil esa regla no se podría hacer cumplir |
| TECH-U21.4 | La línea base, las calibraciones y los inestables son archivos versionados en `app/evals/`, leídos y escritos con el mismo cargador de esquemas que ya valida los casos | La compuerta corre sin base de datos, y un archivo versionado se revisa en un diff (FD-U21-1) |

## Dónde vive el código

- `app/backend/src/untangle/evals/gates/` — la compuerta, la comparación contra
  la línea base, la calibración y el segundo detector.
- `app/evals/baselines/`, `app/evals/calibrations/`,
  `app/evals/unstable-cases.yaml`, `app/evals/regressions.yaml` — los datos.
- Tareas nuevas del archivo de tareas: `evals:gate`, `evals:baseline`,
  `evals:calibrate`, `evals:label` y `test:u21`.

## Sources

- `../functional-design/functional-spec.md` — FD-U21-1 a FD-U21-5.
- `../../../inception/domain-design/decisions.md` — ADR-006, ADR-013 y ADR-014.
- `../../../inception/contract-design/contract-summary.md` — C-27, el reporte
  por caso que U21 extiende.
- `aidlc/spaces/default/codekb/untangle/technology-stack.md` — el stack del
  repositorio: U21 no agrega ninguna dependencia de ejecución.
- `aidlc/spaces/default/memory/team.md` — dependencia nueva con su justificación
  en una línea.

## Assumptions & Open Questions

- **[assumption]** El comando de etiquetado (`evals:label`) vive en esta unidad
  aunque lo use solo Miguel: es parte de la calibración, y sin él DS-7 no existe.
