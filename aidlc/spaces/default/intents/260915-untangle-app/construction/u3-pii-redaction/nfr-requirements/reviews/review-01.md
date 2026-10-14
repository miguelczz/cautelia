## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-09-20T19:39:56Z
**Iteration:** 1

Revisión asesora de `security-requirements` de U3 `pii-redaction`, cotejando sus
objetivos y controles contra el diseño funcional ya cerrado de la misma unidad,
contra `requirements.md`, `unit-of-work.md`, ADR-013 y C-13, y contra lo que hoy
existe de verdad en `mise.toml` y en `scripts/verify.sh`.

El documento es sólido en su método —fuentes citadas, decisiones justificadas y
un hueco de cobertura señalado explícitamente en vez de decidido en silencio— y
la frontera con U21 está bien resuelta: U21 lee la configuración de
reconocedores como archivo y su segundo detector no importa este módulo, sin
invasión de alcance ni hueco entre las dos unidades. Los cuatro hallazgos son
puntuales y ninguno toca la arquitectura de la unidad.

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Major | `security-requirements.md` — NFR11.3 y SEC-U3.11 | NFR11.3 dice medir el coste de cómputo de la pasada de redacción, pero su comando era `mise run test:u3` "con el reloj controlado". Un reloj simulado sirve para NFR11.4, que prueba lógica de temporización, pero no puede cronometrar trabajo real: con el reloj congelado, una implementación que tarde 500 ms pasaría igual. El documento medía una cosa distinta de la que decía medir, que es el mismo defecto de clase que esta etapa ya corrigió una vez con el tope de 300 ms. | Separar el método: NFR11.3 con el reloj del sistema alrededor de la llamada real; NFR11.4 con el reloj controlado. Actualizar SEC-U3.11 para separar las dos mitades por método. | Resolved |
| R-02 | Major | `security-requirements.md` — tabla "Qué puede salir mal" | La tabla de riesgos citaba 12 de los 15 controles. SEC-U3.13, SEC-U3.14 y SEC-U3.15 no colgaban de ningún riesgo declarado, lo que contradice el marco que el propio documento usa para justificar su cobertura. | Asignarles riesgo, o justificar por qué quedan fuera del marco. | Resolved |
| R-03 | Minor | `tech-stack-decisions.md` y `nfr-requirements-questions.md` — Q1 | La cifra "923 MB" se presentaba como el costo de pasar de pequeño a grande, pero es el peso total de los dos modelos grandes (541 más 382). El incremento real desde los pequeños es de 899 MB. En un documento que se apoya en que sus cifras son medidas, la etiqueta incorrecta es un error verificable, aunque no cambia la conclusión. | Corregir la cifra o reetiquetarla como peso total. | Resolved |
| R-04 | Minor | `security-requirements.md` — párrafo final de "Controles"; `scripts/verify.sh` paso 6 | El documento metía `test:u3` en el paso 6 del guion, que hoy agrupa chequeos estáticos y de esquema. Las pruebas de unidad ya corren completas en el paso 5 con `mise run cov`, y el precedente de `test:u1` y `test:u2` es que esos comandos son de uso local y no se invocan desde el guion. Tal como estaba, duplicaría la ejecución o rompería el patrón sin decirlo. | Aclarar que `test:u3` es de uso local como sus antecesoras, y que solo entran al paso 6 los dos comandos nuevos. | Resolved |

### Evidencia de resolución

**R-01.** NFR11.3 se cronometra ahora con el **reloj del sistema** alrededor de
la llamada real al detector; NFR11.4 sigue con el **reloj controlado**, porque
ahí lo que se prueba es cuándo aparece el indicador y no cuánto cuesta el
trabajo. SEC-U3.11 nombra los dos métodos por separado en vez de decir "en sus
dos mitades", que era lo que permitía confundirlos.

**R-02.** SEC-U3.13 y SEC-U3.14 pasan a "Divulgación de información", cuya
descripción se amplía para nombrar las dos vías que faltaban: tratar un dato
ficticio como si no hiciera falta taparlo, y que el reporte imprima el valor al
describir una diferencia. SEC-U3.15 recibe una fila propia, "Fallo común de los
dos detectores", que es el riesgo que de verdad evita: si comparten mecanismo o
biblioteca, un mismo error los tumba a la vez y el segundo deja de comprobar
nada.

**R-03.** Corregido en los dos archivos: los dos modelos grandes pesan 923 MB
juntos frente a los 24 MB de los dos pequeños, es decir 899 MB más. La
conclusión no cambia.

**R-04.** `test:u3` **no entra** al guion, y queda escrito por qué: sigue el
precedente de `test:u1` y `test:u2`, la compuerta ya corre esas pruebas en el
paso 5 con `mise run cov`, y meterlo también en el paso 6 las correría dos veces
en la misma corrida. Entran solo `redaction:constructor` y `redaction:report`.
Los objetivos siguen citando `mise run test:u3` porque es el comando que produce
su cifra a mano, no un paso añadido a la compuerta.

### Nota sobre lo que el revisor confirmó y no reportó

El hueco declarado al final del documento —la redacción es compuerta dura y no
está en la lista de módulos críticos del piso de cobertura de `team.md`— se
comprobó contra la tabla de `unit-of-work.md` y es exacto. No se reporta como
hallazgo porque está correctamente escalado a Miguel en vez de decidido por
iniciativa propia.
