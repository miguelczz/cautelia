## Review

**Verdict:** NOT-READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-09-20T19:01:13Z
**Iteration:** 1

Revisión asesora de `functional-spec` de U3 `pii-redaction` y de los otros tres
artefactos de su etapa, por lectura cruzada contra `stories.md` (US4.12, US4.13
y US4.14, que es de U21), `unit-of-work.md` (las fichas de U3 y de U21),
`requirements.md` (FR7.3, FR12.3, NFR11), `components.md` (`PiiRedaction`) y
`contract-summary.md` (C-13 y C-14).

El documento está bien escrito y la mayoría de sus reglas y de sus nueve
criterios encajan, pero el mecanismo central —"una salida sin redacción es
imposible por construcción"— tenía dos huecos concretos, y a ellos se sumaban un
criterio cubierto por una regla que no describe el mecanismo que lo satisface,
una regla cuya única verificación era una revisión humana pese a que el
documento se autoexige comprobabilidad por herramienta, y una dependencia no
declarada desde U21 hacia la configuración de esta unidad.

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Critical | `rules.md` — BR3.3 y BR1.6 | BR3.3 exigía que el mismo dato repetido conservara su número a lo largo de la conversación, lo que obliga a mantener una correspondencia entre el valor real y su número entre turnos. C-13 define `redact(text, language)` sin estado ni identificador de sesión, y el Flujo 1 solo le pasa el texto del turno. Esa correspondencia es exactamente la bóveda que BR1.6 y la decisión FD-U3-2 declaran inexistente. Las dos reglas se contradecían. | Acotar el alcance de la numeración o declarar dónde vive ese estado, y reconciliar BR1.6 para que no quede en contradicción literal. | Resolved |
| R-02 | Major | `entities.md` — `Redacted`; `rules.md` — BR1.1, BR1.2 | La garantía descansaba en que `Redacted` es un `NewType`. `NewType` no existe en tiempo de ejecución y no impide que cualquier módulo escriba `Redacted(texto_sin_tapar)`: el comprobador de tipos lo acepta, porque es su uso previsto. La regla de importación citada comprueba la estructura de imports, no la construcción del tipo. Un escritor descuidado podía fabricar un `Redacted` falso sin que ninguna comprobación declarada lo detectara. | Especificar el mecanismo que cierra el hueco y ajustar la regla para que su prueba cubra ese caso. | Resolved |
| R-03 | Major | `traceability.json` — fila AC4.12.3; `rules.md` — BR3.1, BR3.2 | AC4.12.3 exige que en la transcripción parcial un dato nunca se vea con sus dígitos, y el Flujo 2 describe el mecanismo real: acumular y mostrar solo la porción segura. Ese mecanismo no tenía ninguna regla con disparador, lógica y prueba de violación. BR3.1 y BR3.2, marcadas como cobertura, solo gobiernan qué reemplaza a un hallazgo ya detectado. | Añadir la regla del comportamiento de acumulación y corte seguro, y apuntar AC4.12.3 a ella. | Resolved |
| R-04 | Major | `rules.md` — cabecera y BR1.6 | El archivo abría afirmando que cada regla es comprobable por una herramienta o por una prueba, pero la cláusula de violación de BR1.6 decía "hallazgo de revisión de seguridad", que es una revisión humana. La regla no cumplía el estándar que el propio documento se impone. | Reescribir su verificación como algo que una herramienta comprueba, o sacarla del recuento. | Resolved |
| R-05 | Major | `unit-of-work.md` — ficha de U21; `rules.md` — BR2.6, BR4.6 | AC4.14.1, propiedad de U21, exige revisar la configuración de los dos detectores para confirmar que no comparten mecanismo ni reconocedores. U3 declara el mecanismo de cada reconocedor justamente para eso, pero la ficha de U21 no lista a U3 entre sus dependencias y no quedaba dicho por dónde llega U21 a esa configuración. | Declarar la dependencia, o decir explícitamente que la comprobación lee un archivo versionado sin pasar por ninguna interfaz de U3, indicando su ruta. | Resolved |
| R-06 | Minor | `entities.md` — `Recognizer` | Se declaraba que la configuración de reconocedores es versionada, pero ningún artefacto decía en qué ruta ni en qué formato vive. Sin eso no se pueden implementar BR2.6 ni BR2.8. | Añadir la ruta y el formato. | Resolved |

### Evidencia de resolución

**R-01.** BR3.3 se acota al texto de una llamada: el mismo valor repetido dentro
de ese texto conserva su número y la numeración empieza de nuevo en el siguiente
turno. La regla dice ahora por qué, en lugar de dejarlo implícito: mantenerlo
entre turnos exigiría la bóveda que BR1.6 prohíbe. Queda registrado como
decisión FD-U3-10, y el archivo de preguntas recoge el acotamiento junto a la
respuesta de Q1 que lo originó. Donde la numeración sirve de verdad —distinguir
el teléfono del asegurado del del testigo— es dentro del mismo turno.

**R-02.** La garantía deja de apoyarse en el tipo. Entra **BR1.8**: un chequeo
de análisis estático prohíbe invocar el constructor de `Redacted` fuera de
`compliance/redaction/api.py`, con dos pruebas —una que planta esa llamada y
exige que el chequeo falle, y otra que comprueba que el árbol correcto pasa—.
`entities.md`, BR1.2 y el Flujo 5 dicen ahora explícitamente que el tipo señala
la obligación y el chequeo la impone, y que `NewType` se borra en tiempo de
ejecución. Es el mismo error que U1 cometió con la espera de tres días y aquí
queda nombrado como tal.

**R-03.** Entra **BR3.5**, con su disparador, su lógica y su prueba: se alimenta
un teléfono dígito a dígito y se exige que ningún fotograma intermedio de la
salida contenga dos dígitos consecutivos del número sembrado. `AC4.12.3` apunta
ahora a BR3.1, BR3.2 y BR3.5.

**R-04.** La violación de BR1.6 es ahora un chequeo de análisis estático que
falla si aparece cualquier estructura que relacione un valor detectado con su
original: un diccionario, una tabla, un índice o un campo que guarde el texto de
entrada.

**R-05 y R-06.** La configuración de reconocedores vive en
`app/backend/src/untangle/compliance/redaction/recognizers/<idioma>.yaml`, un
archivo por idioma, versionado y en YAML porque lo escribe una persona (CD-4).
La ruta está declarada en `entities.md`, en BR2.8 y en el Flujo del alcance. U21
la lee **como archivo**, sin importar este módulo, lo que satisface AC4.14.1 sin
romper BR4.6. Que la ficha de U21 no declare la dependencia queda escrito en la
sección de lo que esta unidad no hace, para su etapa de diseño: corregir la
ficha aprobada de otra unidad no es trabajo de esta.

### Un error que la revisión no detectó

La cabecera de `rules.md` decía "veintidós reglas" y el informe repitió la cifra.
Eran **veinticinco**, y con BR1.8 y BR3.5 son **veintisiete**. Contadas del
archivo, no a mano: BR1 ocho, BR2 ocho, BR3 cinco, BR4 seis. Corregidas la
cabecera, el resumen y la tabla de grupos.
