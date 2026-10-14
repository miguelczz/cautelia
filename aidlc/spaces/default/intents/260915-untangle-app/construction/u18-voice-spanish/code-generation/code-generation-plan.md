# Plan de generación de código — U18 `voice-spanish`

Tres tandas. Es una unidad pequeña en código y grande en pruebas, y el plan lo
refleja: la primera tanda mueve una pieza y no añade conducta, la segunda es
toda la conducta nueva, y la tercera son las pruebas del español que existen
precisamente para demostrar que **no** hizo falta código nuevo.

El orden no es el de las historias sino el de las dependencias: sin el detector
al alcance de la voz no hay nada que construir, y sin el cambio de idioma no hay
paridad que comprobar.

## Rama de pruebas

**Evaluada.** Realiza M15 y M6. Sus casos previos son las grabaciones de DS-5 en
español con al menos tres voces paisas; lo que no cabe en DS-5 —la petición de
cambio, el tercer idioma, la palabra suelta que no cambia nada— va con el
reconocedor simulado, que es el doble de U16.

DS-5 en español **no existe todavía**: llega en la semana 9, con voluntarios y su
consentimiento, y vive fuera del repositorio. Lo que corre en cada entrega es la
rama determinista completa con los dobles, y ahí están las veintiuna reglas.

## Dónde vive

| Qué | Dónde |
| --- | --- |
| El detector, que sube de `chat/` | `app/backend/src/untangle/language.py`, nuevo y hoja |
| La petición de cambio y el idioma no atendido | `app/backend/src/untangle/voice/` |
| El campo de configuración | `app/config/tenants/*/tenant.yaml` y `tenancy/models.py` |
| El chequeo del registro en español | `app/backend/src/untangle/evals/content_checks.py` |
| Las pruebas | `app/backend/tests/unit/voice/`, `integration/u18/`, nuevo |

---

## Tanda 1 — El detector sube a módulo hoja

Ninguna conducta nueva. Es un movimiento, y por eso va sola: una tanda que mueve
una pieza y además la cambia deja un diff donde no se puede ver cuál de las dos
cosas rompió algo.

1. `chat/language.py` pasa entero a `untangle/language.py`: los dos detectores, los
   dos umbrales medidos, el piso de cuatro palabras y el conjunto cerrado de
   desenlaces, **sin tocar un número**.
2. Los consumidores de U13 apuntan al nuevo. **No queda reexportador** (BR3.4).
3. El contrato de capas gana su renglón: el módulo hoja va debajo de todo, como
   `base.py` y `surface_spec.py`.

**Pruebas.** Las de U13 siguen pasando sin cambiar ninguna aserción: si alguna
hubiera que tocarla, es señal de que el movimiento cambió algo. Se añade la que
comprueba que no queda un segundo módulo con umbrales de idioma.

**Reglas que cierra:** BR3.4.

## Tanda 2 — El cambio de idioma

Toda la conducta nueva de la unidad.

1. `voice/language_request.py` — la lista cerrada y versionada de formas de pedir
   el cambio, en los dos idiomas, reconocida por código (BR2.1). Un solo lugar y
   con su prueba de que "el Toyota Highlander" no es una petición.
2. El ciclo de la llamada resuelve el idioma de cada turno **en este orden**: la
   petición primero (BR2.2), la detección automática después y solo si la
   aseguradora la tiene activa (BR3.1, BR3.2), y si no, el idioma que había.
3. El cambio escribe `CallSession.language` y **no toca el caso** (BR5.1,
   `[bloquea]`). El turno de la petición se contesta ya en el idioma nuevo (BR2.4).
4. La escalera del idioma no atendido: a la primera se pide repetir —la de U16—, a
   la segunda seguida la frase de los dos idiomas (BR4.1 a BR4.4).
5. Claves nuevas del catálogo en los dos idiomas: la frase bilingüe del idioma no
   atendido, y nada más.
6. `auto_language_detection` en la configuración de voz, apagado por omisión
   (BR3.1), con su entrada en el esquema generado.
7. Los dos eventos de traza, con el idioma y el motivo y **nunca el texto**.

**Pruebas.** La petición en los dos sentidos y dicha en cada uno de los dos
idiomas; el turno de la petición contestado ya en el nuevo; dos bloques
confirmados que siguen confirmados después del cambio (el `[bloquea]`); el caso
que **no** cambia de idioma; la identidad de voz que no cambia; una palabra suelta
que no cambia nada; dos turnos seguidos que sí, y solo con la detección activa; el
tercer idioma a la primera y a la segunda; el detector que falla y conserva el
idioma; y el presupuesto PERF-U18.1 cronometrado.

**Reglas que cierra:** BR2.1 a BR2.6, BR3.1 a BR3.3, BR4.1 a BR4.3, BR5.1.

## Tanda 3 — La paridad, que son pruebas

Esta tanda **casi no escribe código de producción**, y eso es lo que demuestra.

1. El recorrido entero de U16 en español, con los dobles: el orden de los bloques,
   la confirmación de cada uno, la cédula y la placa dígito a dígito, la escalera
   de "no le entendí", la pregunta de cobertura, el cierre, la interrupción, los
   silencios y la retoma (AC1.29.x, AC1.30.1 a AC1.30.4).
2. El idioma de arranque: sin elegir, el de la aseguradora (BR1.1). El cuerpo de
   abrir deja `language` opcional y la consola lo omite cuando la procedencia del
   selector es `tenant_default` (D5).
3. La identidad única de voz de cada aseguradora, comprobada sobre la carpeta
   versionada (BR1.2).
4. El chequeo del registro en español: ninguna forma de tuteo, "pues" como mucho
   una vez por turno (BR5.4), con identificador estable como los tres que ya
   existen.
5. La tarea `test:u18`.

**Lo que esta tanda vigila de sí misma.** Si alguna de estas pruebas obliga a
ramificar por idioma dentro de U18, la corrección va a U16 (BR5.2). Una rama aquí
sería tapar allí un defecto que nadie buscaría.

**Reglas que cierra:** BR1.1, BR1.2, BR1.3, BR5.2, BR5.3, BR5.4.

---

## Lo que no se toca

- **U16.** Su llamada, su interrupción, su retoma y su consola están cerradas y
  esta unidad las habla en el segundo idioma sin duplicar nada. La excepción está
  escrita: si una prueba de paridad obliga a ramificar, se corrige allí.
- **El chat.** Solo cambia de dónde importa el detector.
- **La voz de U15.** La identidad es la misma en los dos idiomas por configuración.

## Lo que queda anotado y no se abre

Los defectos ya diagnosticados en `docs/PENDIENTES-MIGUEL.md` no se abren en esta
unidad. Uno la toca de cerca y conviene decirlo: **1.8, el ritmo de fondo** —las
reglas y el cierre no corren porque `decision` lee seis campos que nadie escribe—
afecta igual a los dos idiomas, así que no es un hueco del español. Se abre
después, con su propio diseño.

## Cómo se revisa cada tanda

Por `.claude/skills/revisar-tanda/SKILL.md`. Con una atención propia de esta
unidad: **la forma de defecto que más se parece a lo que aquí se puede hacer mal
es la prueba que afirma el mecanismo en vez de la regla** —la que U16 encontró al
cerrar—, porque casi todas las pruebas de la tanda 3 comprueban que algo sigue
comportándose igual, y "igual" es fácil de escribir de manera que pase siempre.

## Tareas nuevas

| Tarea | Qué hace | En qué tanda |
| --- | --- | --- |
| `test:u18` | Solo las pruebas de esta unidad, sin red | 3 |

Se declaran aquí y no en una etapa de infraestructura porque esa etapa **no corre
desde la decisión de modo ligero** del 2026-09-21 (DP-12). El chequeo de
artefactos las buscaba solo allí, así que daba por no declarada cualquier tarea de
una unidad nueva; se le enseñó a mirar también este documento el 2026-09-29, al
tropezar con ello aquí.

## Contrato de pruebas

Este plan se escribe **sin directiva del motor del flujo**, que va dos unidades
atrasado (PENDIENTES 1.13), así que no se reproduce su bloque JSON con sus dos
hashes: inventarlos sería afirmar que unos insumos se verificaron cuando no los
verificó nadie.

Lo que sí manda, y es lo que ese bloque transporta, es la postura de pruebas
afirmada del equipo, que no ha cambiado: metodología `custom`, con sus dos ramas
—evaluada y determinista— y el runner, la cobertura y el corredor de evaluaciones
ya instalados. Esta unidad es de la **rama evaluada** y lo declara arriba, con sus
casos previos y con lo que va por los dobles mientras DS-5 no exista. El piso del
80 % agregado, los pisos por módulo crítico, `scripts/verify.sh` y la compuerta de
GitHub Actions se aplican sin cambio.

## Sources

- `../functional-design/functional-spec.md`, `rules.md`, `entities.md`, `functional-design-questions.md`
- `../nfr-requirements/` — los cinco documentos de esta unidad
- `../../../inception/units-generation/unit-of-work.md` — U18
- `../../u16-voice-call/code-generation/code-summary.md`
- `aidlc/spaces/default/memory/team.md` — la postura de pruebas afirmada
- `docs/reference/como-se-revisa-el-codigo.md`

## Assumptions & Open Questions

None.
