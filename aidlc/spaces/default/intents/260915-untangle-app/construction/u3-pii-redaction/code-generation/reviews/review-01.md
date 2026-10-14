## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-09-20T21:40:00Z
**Iteration:** 1

Revisión asesora de `code-generation-plan` de U3 `pii-redaction` y del código que
produjo, con comprobación en vivo: `mise run test:u3` (175 pasan),
`redaction:constructor` y `redaction:report` en verde, el comprobador de
artefactos sin hallazgos, las 44 rutas del manifiesto existentes, la firma de
`redact` contra C-13 letra por letra, el chequeo del constructor contra las tres
formas plantadas, y los dos relojes en las pruebas de la transcripción en vivo.

El código cumple lo que promete medir, la sección de huecos declarados es
honesta y está medida, y no hay ningún hallazgo `Critical`.

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Major | `detector.py` — constante `PASADA_DEL_OTRO_IDIOMA`; §4.1 de `code-summary.md` | La acotación de BR2.9 hace que los reconocedores del modelo de lenguaje del idioma que no es el del turno nunca corran. RT-14 y RT-15 solo miden los cuatro tipos por formato, así que ningún caso ejercita un nombre propio cruzado de idioma. La medición que justifica la acotación se hizo sobre turnos con datos de dominio, no sobre un nombre, de modo que no descartaba ese caso. | Que un humano decida si un nombre propio dictado en el otro idioma debe quedar cubierto por compuerta dura, y si hace falta un caso que lo ejercite. | Unresolved |
| R-02 | Major | El directorio `code-generation/` completo | Faltaba `traceability.json`, que la etapa nombra entre sus entregables. El resumen traía una tabla en prosa, pero no el archivo estructurado que el comprobador valida. | Generarlo, o dejar escrito que la tabla basta. | Resolved |
| R-03 | Minor | `workspace/redaction_constructor.py` — `visit_Assign`, `visit_Dict` | La Regla 2, que busca bóvedas, cubre `ast.Assign` y `ast.Dict` con clave de rebanada, pero no `AugAssign`, el operador morsa ni las comprensiones de diccionario. Es defensa en profundidad y la garantía dura es la Regla 1, pero el hueco es real y no estaba declarado. | Ampliar el visitante, o declarar que la Regla 2 es heurística. | Resolved |
| R-04 | Minor | `detector.py` — memoria residente; §4.2 de `code-summary.md` | Ya declarado y medido por el equipo: 636 MB frente a los 71 MB que daba NFRD-U3-1. Se deja como fila para que quede visible en la compuerta y no se pierda entre los ocho puntos de la sección 4. | Confirmar que el intent que aprovisiona el despliegue hereda este número antes de fijar el plan de hospedaje. | Accepted risk |

### Evidencia de resolución

**R-02.** `traceability.json` escrito con sus **59 identificadores** —los nueve
criterios de aceptación, las treinta y siete reglas, los siete objetivos
medibles y los quince controles—, cada uno apuntando a un archivo que existe.
Pasa el comprobador sin hallazgos. Cuatro entradas en `reverse` declaran lo que
no nace de un identificador aguas arriba: la decisión CG-U3-1, la acotación de
BR2.9 con su medición, la memoria residente, y el alcance de la Regla 2.

**R-03.** Declarado, no disimulado, en `code-summary.md` §8 y en
`traceability.json`: la Regla 2 es defensa en profundidad y la garantía dura es
la Regla 1 sobre el tipo, que sí es exhaustiva en sus tres formas. Un control
heurístico presentado como exhaustivo es peor que uno heurístico dicho.

**R-01 queda abierto a propósito, y con una medición nueva.** El hallazgo era
correcto: la medición original usó datos de dominio. Medido ahora sobre nombres
propios cruzados de idioma, con el modelo del idioma del turno, que es lo único
que corre: `Jonathan Whitfield` y `Sarah O'Connell` en turno español, atrapados;
`Yeison Cuaran` en turno inglés, atrapado; `Nayibe Quintero Ospina` en turno
inglés, **parcial** —marcó `Quintero Ospina` y dejó `Nayibe` fuera—.

Un nombre no tiene idioma como lo tiene un formato: es una palabra con
mayúscula, y el modelo del turno la reconoce venga de donde venga. El hueco real
no es el cruce de idioma sino la captura parcial de un nombre de tres palabras,
y eso **no lo arregla correr el otro modelo**: lo arregla un reconocedor por
contexto, que es un patrón, corre en los dos idiomas siempre y no cuesta
memoria. Comprobado: recupera los cuatro nombres completos y no marca nada en
una frase de control. Va a Miguel junto con la decisión del tamaño de modelo,
porque las dos se deciden juntas.

### Una cosa que el resumen no vio

El paso 6 fallaba por `contracts:check`, pero ese chequeo es el **segundo de
siete** encadenados, así que los cinco siguientes nunca llegaron a correr. Se
ejecutaron uno por uno: los cinco en verde. Con los dos artefactos generados
preparados, el guion da 9 de 9.
