# Resumen de código — U22 `public-evidence`

La evidencia: que nada de lo que este proyecto afirma se haya escrito a mano. Las
cinco cifras con su fecha y su commit, el gasto, y las dos secciones del README que
se regeneran solas: las cifras desde la línea base vigente y «Cómo falla» desde el
resumen de la última corrida completa.

**63 archivos, cuatro tandas.** Formato, lint, tipos, contratos de importación,
catálogo de textos, esquemas, contratos generados, chequeos de contenido y
`readme:check`, en verde en local. La compuerta de GitHub Actions sobre `main` es la
autoritativa. Los totales de pruebas de las tandas 1 y 2 están en sus `hallazgos`;
los de la 3 y la 4, en sus `hallazgos`.

## Lo que construyó

| Tanda | Qué | Dónde |
| --- | --- | --- |
| 1 | La lectura de la línea base, las cinco cifras (`MetricsSnapshot`) y el panel público sin credencial | `evals/evidence/`, `server/evidence_routes.py`, `pages/evidence/` |
| 2 | El panel de gasto detrás de la clave de operador, con sus cuatro vistas más la lista por caso | `server/spend_routes.py`, `telemetry/spend/repository.py`, `pages/spend/` |
| 3 | `README.md` con sus ocho encabezados, las dos secciones generadas («Cómo falla» y el reporte de evaluación) y su chequeo dentro del guion de verificación | `evals/evidence/readme.py`, `workspace/readme_check.py`, `scripts/verify.sh` |
| 4 | `LastRunDigest` (`app/evals/last-run.json`, que todavía no existe: lo crea la primera corrida completa), escrito siempre por `evals:baseline` —en verde y en rojo, nunca desde un subconjunto— y leído por «Cómo falla»; se retira `Baseline.root_causes` | `evals/gates/models.py`, `gates/loading.py`, `gates/baseline_cli.py`, `evals/evidence/readme.py`, `workspace/readme_check.py` |

## Las decisiones que cambiaron algo fuera de la unidad

1. **`LastRunDigest` y el retiro de `Baseline.root_causes`** (U21): la tanda 3 añadió
   el campo a la línea base, pero `publish()` rechaza los casos en rojo y la causa raíz
   solo se pone en ellos, así que ninguna ruta de producción podía llenarlo. FD-U22-10
   (Miguel, 2026-09-30) lo reemplaza por un resumen versionado de la última corrida
   completa. Toca de U21 solo `gates/models.py`, `gates/loading.py`, `gates/baseline.py`
   y `gates/baseline_cli.py`.
2. **`ModuleSpec.requires_setting`** (raíz de composición, tanda 2): un módulo sin su
   clave no se monta.
3. **Una arista de importación nombrada** (`server.evidence_routes` hacia
   `evals.evidence`), medida y no supuesta.

## Lo que se midió

PERF-U22.1 y PERF-U22.2 tienen su prueba cronometrada en `test:u22` (ver los
`hallazgos` de las tandas 1 y 2). Las latencias de voz y chat **no se miden** en esta
unidad: salen «no medidas» con su causa, que es el criterio. La causa es **por canal**
y no de la cifra, en el panel y en el README: la de la voz es una decisión (por hito) y
la del chat es trabajo pendiente (sus dos eventos no se emiten), y confundirlas manda a
esperar un hito donde hay que construir.

## Lo que esta unidad no construye

- **Las seis secciones narrativas del README y su resumen en español**: semana 11, de
  Miguel. El README las marca pendientes y el chequeo solo compara las dos generadas.
- **Los enlaces al chat, la voz y el video** del párrafo inicial: no están publicados.
- **La alerta y el corte del techo de gasto**: U15 y U16.
- **Publicar los paneles**: la pasada de publicación.
- **Correr la corrida completa de evaluaciones**: necesita claves y gasta dinero. Hasta
  que `evals:baseline` escriba el primer `last-run.json`, «Cómo falla» dice «no medida».

## Los documentos de revisión

`hallazgos-tanda-1.md` a `hallazgos-tanda-4.md`, cada uno con
lo que se rompió y qué se cayó.
