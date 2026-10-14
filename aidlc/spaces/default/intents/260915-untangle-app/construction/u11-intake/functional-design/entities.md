# Entidades — U11 `intake`

**U11 no crea ninguna entidad.** El catálogo de componentes se lo dice en una
línea —`entities: []` en `IntakeNode`— y la tabla de entidades por unidad lo
repite: *"Escribe en las entidades del caso de U4"*. No hay migración, no hay
tabla nueva, no hay esquema propio.

Lo que sí hay, y es lo que este documento fija, es **qué escribe y qué lee**.
Un nodo declara su conjunto de escritura y dos nodos no comparten ninguno
(convención 6), así que esa lista es un contrato y no una nota.

## Lo que U11 escribe

Todo en entidades de U4 `case-record`, a través de su API pública (C-12):

| Entidad de U4 | Qué escribe U11 | Regla |
| --- | --- | --- |
| `Case` | El tipo de registro al abrirlo —siniestro o consulta de cobertura—, la póliza asociada una vez identificada, y el estado cuando la sesión termina por abuso | BR1.1, BR1.6, BR5.4 |
| `CaseField` | Los siete campos, cada uno con su valor normalizado, su evidencia —el turno del que salió— y si está confirmado | BR2.1, BR3.1, BR3.3 |
| `CaseParty` | Las personas y vehículos que se nombran, incluido el tercero que reporta con su relación | BR1.5 |

**Lo que `CaseParty` necesita y hoy no tiene** (corrección del 2026-09-27, ver
FD-U11-5): un quinto rol para quien reporta —los cuatro de hoy son `injured`,
`witness`, `other_driver` y `other_vehicle`, y quien reporta no es ninguno— y
una columna para la relación con el asegurado, que AC1.4.1 pide por escrito.
Es una ampliación aditiva de la tabla de U4, no una entidad nueva: ninguna
fila existente cambia y ninguna operación cambia de firma.
| `TranscriptTurn` | Nada: el turno lo escribe el canal. U11 lo **lee** para citar de qué turno salió cada campo | BR2.2 |

## Lo que U11 lee

| De quién | Qué | Para qué |
| --- | --- | --- |
| U8 `policy-rag` (C-18) | La póliza emitida por número, o por cédula del titular | Identificar a la persona sin revelar nada ajeno (BR1.2) |
| U4 `case-record` (C-12) | El caso con sus campos y su estado | Saber qué bloque toca preguntar y qué ya está confirmado (BR3.2) |
| U5 `provider-platform` (C-16) | El modelo, para extraer y para redactar | Extracción por turno y composición de la respuesta (BR2.1) |
| U1 `workspace` (C-1) | El catálogo de copy por idioma | Toda frase que sale: apertura, preguntas, lecturas, calma, cierre (BR5.1) |

## Lo que U11 devuelve, que no se persiste

```yaml
entities:

  # Aterrizo como `IntakeNodeOutput` en `orchestration/nodes/intake/node.py`,
  # con dos correcciones de la revision del 2026-09-27:
  #
  # 1. **Sus campos llevan el prefijo `intake_`.** `policy_verification` ya
  #    escribe `response_key` y `response_text`, y dos nodos no comparten ningun
  #    campo del estado (convencion 6). Corren en ritmos distintos y nunca
  #    compondrian el mismo turno, pero un campo compartido es un campo
  #    compartido; si U12 los unifica al disenar el estado, que sea una decision
  #    escrita y no un choque que nadie vio.
  # 2. **`emergency_raised` es de entrada, no de salida.** La levanta el control
  #    barato de U10 y este nodo la respeta: declararla en el conjunto de
  #    escritura decia que U11 la escribe, que es lo contrario de FD-U11-3.
  - name: IntakeTurnResult
    description: El valor de retorno del nodo. No es una fila: es el conjunto de escritura que declara, más el texto compuesto para el canal. El nodo no muta el estado compartido (convención 6).
    stored_in: "En memoria; sus partes aterrizan en las entidades de U4 por la API de C-12"
    attributes:
      - { name: next_block, type: enum, required: true, allowed_values: [safety, identity_and_policy, what_happened, when_and_where, vehicle_and_driver, other_parties, final_confirmation, done], constraint: "El bloque que toca preguntar, leído del estado y no de un contador propio (BR3.2, AC1.5.2)." }
      - { name: extracted, type: "list of {field_key, value, normalized, evidence_turn_id}", required: true, constraint: "Solo lo dicho en este turno. Un campo sin evidencia no se escribe (BR2.2)." }
      - { name: parties, type: "list of CaseParty draft", required: false }
      - { name: awaiting_confirmation, type: "block or null", required: false, constraint: "El bloque cuya lectura se acaba de emitir. Hasta el sí, no cuenta como confirmado (BR3.1)." }
      - { name: response_key, type: string, required: true, constraint: "Clave del catálogo, nunca texto en línea (BR5.1)." }
      - { name: response_text, type: string, required: true, constraint: "Ya resuelta por idioma, lista para que el canal la pase por la guardia de salida de U10." }
      - { name: emergency_raised, type: boolean, required: true, constraint: "Lo levanta el control barato de U10, no este nodo; U11 lo respeta y rompe el orden (BR4.1)." }
      - { name: session_ended, type: "enum or null", required: false, allowed_values: [abuse], constraint: "El único motivo por el que la captura cierra la sesión (BR5.4, AC1.13.3)." }

  - name: FieldEvidence
    description: De qué turno salió un valor. No es entidad nueva: es el campo `evidence` que `CaseField` de U4 ya tiene, y se declara aquí porque U11 es quien lo llena.
    stored_in: "CaseField (U4)"
    attributes:
      - { name: turn_id, type: identifier, required: true, references: "TranscriptTurn (U4)" }
      - { name: verbatim_redacted, type: text, required: true, constraint: "Lo que la persona dijo, ya redactado, para poder comparar la lectura contra el dicho (AC1.7.4)." }
      - { name: normalization, type: string, required: false, constraint: "Qué regla versionada se aplicó: fecha relativa, placa, póliza, cédula, teléfono. Vacío cuando el valor entró tal cual." }
```

## Por qué no hay tabla nueva

Porque el caso ya existe y es de U4. Si U11 guardara su propio estado de la
conversación en una tabla aparte, habría dos sitios donde vive lo mismo y una
reanudación tendría que reconciliarlos. El bloque que toca preguntar **se
deduce del caso** —qué campos están confirmados— y no de un contador propio;
esa es la razón por la que AC1.5.2 pide leerlo del estado, y es lo que hace que
reanudar tras `interrupt()` no necesite nada más (ADR-003).
