# Especificación funcional — U11 `intake`

U11 es el nodo que habla con la persona mientras reporta. Un solo componente
—`IntakeNode`— y ninguna entidad propia: escribe en el caso de U4.

Es la primera unidad que corre **dentro del turno**. Todas las anteriores
—reglas, cumplimiento, pólizas— corren en el ritmo de fondo o se invocan desde
un comando. Aquí hay una persona esperando, y eso cambia qué se puede hacer:
unos 3.900 tokens de entrada por turno de voz (ADR-006), una sola pregunta por
turno, y nada que no quepa en ese presupuesto.

## El recorrido de un turno

```
turno de la persona
  │
  ├─ 1. ¿la señal de emergencia está levantada?        (la levanta U10, no U11)
  │      sí → la indicación de emergencia, y se ofrece seguir  (BR4.1)
  │
  ├─ 2. EXTRACCIÓN                                     (solo lo dicho en este turno)
  │      texto como campo delimitado, nunca instrucción  (BR2.1, BR2.3)
  │      normalización por reglas versionadas            (BR2.4)
  │      cada valor con su evidencia: de qué turno salió (BR2.2)
  │
  ├─ 3. ¿había un bloque esperando confirmación?
  │      sí   → confirmado, o se abre la corrección     (BR3.1)
  │      contradice algo ya confirmado → se guardan las dos versiones (BR5.5)
  │
  ├─ 4. ¿QUÉ BLOQUE TOCA?                              (se lee del caso, no de un contador)
  │      seguridad → identidad y póliza → qué pasó → cuándo y dónde
  │      → vehículo y conductor → otras partes → confirmación final  (BR3.2)
  │      lo ya dicho no se vuelve a preguntar           (BR3.3)
  │
  └─ 5. SE COMPONE LA SALIDA                           (clave del catálogo, por idioma)
         una idea, 25 palabras o menos                  (BR3.4)
         reconocimiento primero si hay emoción          (BR5.2)
         registro prohibido comprobado por código       (BR5.3)
         nunca cobertura, monto ni culpa                (BR5.6)
```

El paso 4 es el corazón: **el estado de la conversación no existe como tal.**
Se deduce del caso en cada turno, y por eso reanudar tras `interrupt()` no
necesita nada más.

## Decisiones de esta etapa

| Decisión | Qué se decide | Por qué |
| --- | --- | --- |
| FD-U11-1 | El bloque que toca se deduce de qué campos están confirmados en el caso, no de un contador que U11 lleve | Un contador propio sería un segundo sitio donde vive el estado de la conversación, y al reanudar tras `interrupt()` habría que reconciliarlos. AC1.5.2 pide justamente leerlo del estado |
| FD-U11-2 | La normalización de fechas, placas, pólizas, cédulas y teléfonos vive en configuración versionada y se aplica en **código**, después del modelo | Si normalizara el modelo, dos corridas del mismo commit escribirían valores distintos y la exactitud por campo de AC1.7.5 dejaría de ser reproducible |
| FD-U11-3 | U11 **no detecta** la emergencia: la señal la levanta el control barato de U10 dentro del turno, y U11 la respeta rompiendo su orden | D22 fija que dentro del turno corren solo tres controles y que son de U10. Un segundo detector aquí sería otro sitio donde arreglar el mismo fallo |
| FD-U11-4 | El registro prohibido y la forma del turno —primera frase, una pregunta, palabras prohibidas— los juzga el **código** sobre el texto ya compuesto | AC1.13.5 lo pide explícitamente: eso se publica aunque el juez esté descalibrado. Lo que queda para el juez es el tono, que es lo que el código no puede ver |
| FD-U11-5 | U11 no crea **entidades nuevas**: escribe en las del caso por la API de U4. Sí puede **ampliarlas de forma aditiva** cuando un criterio aprobado lo exige | Corregida el 2026-09-27, durante la revisión de la tanda 1. La primera redacción decía "ni migración" y eso dejaba AC1.4.1 sin dónde aterrizar: el criterio pide registrar a quien reporta **con su relación con el asegurado**, y `case_party` no tiene columna para ella ni un rol que signifique "quien reporta". Un criterio aprobado manda sobre una decisión de diseño de esta etapa; lo que la decisión protege —que U11 no guarde su propio estado de la conversación— sigue intacto |
| FD-U11-7 | El valor del caso es **el primero confirmado**; una versión que lo contradice se anota aparte, con su turno y su hora | Decisión de Miguel del 2026-09-27 (Q1). Con la última ganando, quien se corrige de buena fe puede acabar con el dato bueno reemplazado; con el campo en conflicto y sin valor, un caso bien reportado se vería incompleto por haberse corregido |
| FD-U11-8 | Los tres campos que se confirman antes de anotarse —lesiones, conductor y lugar— se cubren con la lectura del bloque, que tiene que **nombrarlos explícitamente** y no resumirlos | Decisión de Miguel del 2026-09-27 (Q2). Consigue lo mismo que una lectura por campo sin gastar tres turnos sobre una meta de catorce |
| FD-U11-6 | Cuántos insultos disparan la frase de calma y cuántos el cierre viven en la configuración de la aseguradora | AC1.13.3 dice "número que fija la configuración". Un número en el código sería una diferencia entre aseguradoras metida en una rama, que es justo lo que la convención 9 prohíbe |

## Lo que U11 no hace

- **La conversación por canal:** U13 (chat) y U16 (voz). U11 entrega la clave y
  el texto compuesto; quién lo muestra o lo sintetiza es del canal.
- **La detección de emergencia, de petición de persona y la guardia de salida:**
  U10. Son los tres controles baratos del turno.
- **Las reglas y la categoría del caso:** U9, en el ritmo de fondo. La captura
  no decide si el caso se deriva; escribe los campos que las reglas leen.
- **La respuesta de cobertura:** U8. La captura solo no descarrila cuando la
  pregunta llega (BR4.2).
- **La cotización:** U19, que extiende este mismo componente.
- **El ejecutor del nodo y su política de fallo:** U12.

**Una consecuencia de FD-U11-7 que no es de esta unidad.** Si el valor del caso
sigue siendo el primero confirmado, la regla que deriva por contradicción no
puede mirar el valor del campo: tiene que mirar que **exista** una versión
alternativa. Eso es una línea en el conjunto de reglas de cada aseguradora, y es
de **U9** —o de U19, que extiende ese conjunto—. U11 deja el dato escrito con su
turno y su hora para que esa regla lo pueda leer; escribirla no es de aquí.

## Fronteras con lo ya construido

| Con quién | Qué le pide U11 | Contrato |
| --- | --- | --- |
| U4 `case-record` | Abrir el caso, leer y escribir campos, partes y confirmaciones | C-12 |
| U8 `policy-rag` | La póliza emitida, por número o por cédula del titular | C-18 |
| U5 `provider-platform` | El modelo para extraer y para componer | C-16 |
| U1 `workspace` | El catálogo de preguntas, lecturas y frases por idioma | C-1 |
| U10 `compliance` | La señal de emergencia y la de petición de persona, ya levantadas | C-20 |
| U12 `graph-runtime` | El nodo con la forma de C-15: `INTAKE_SPEC` y su `run` puro, en `orchestration/nodes/intake/node.py` | C-15 |

## Riesgos de esta unidad

- **El que más duele: volver a preguntar lo ya dicho.** Es la queja que US1.5
  existe para evitar y la que más rápido delata a un sistema que no escucha.
  BR3.3 lleva prueba que lo aísla.
- **La lectura que no coincide con lo dicho.** AC1.7.4 pide 98 % de fidelidad.
  Una lectura que "mejora" lo que la persona dijo es peor que una que lo repite
  mal: la persona confirma algo que no dijo.
- **El presupuesto de tokens.** 3.900 por turno de voz es poco, y el prompt de
  extracción crece con cada campo. Si no cabe, se recorta lo que se le manda al
  modelo, nunca lo que se le exige.
- **Confundir "no lo dijo" con "no aplica".** Un campo vacío porque la persona
  no lo mencionó y uno vacío porque no corresponde no son lo mismo para la
  completitud de AC1.7.3.

## Sources

- `../../../inception/units-generation/unit-of-work.md` — sección U11.
- `../../../inception/units-generation/unit-of-work-story-map.md` — las seis
  historias y las comprobaciones de punta a punta con U9, U10, U12 y U13.
- `../../../inception/requirements-analysis/requirements.md` — FR1.1, FR1.3,
  FR4.2, NFR7, NFR8, NFR10.
- `../../../inception/domain-design/components.md` — IntakeNode, con
  `entities: []`; ADR-003, ADR-006.
- `../../../inception/contract-design/contract-summary.md` — C-12, C-15, C-16,
  C-18, C-20.
- `../../../inception/user-stories/stories.md` — US1.3, US1.4, US1.5, US1.7,
  US1.12 y US1.13.
