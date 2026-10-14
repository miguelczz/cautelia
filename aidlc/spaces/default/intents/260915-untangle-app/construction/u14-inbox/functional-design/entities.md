# Entidades — U14 `inbox`

U14 guarda **muy poco**, y eso es el diseño y no una carencia. El caso, sus
campos, su transcripción y su historial son de U4; las citas son de U8; la regla
disparada es de U9; el resultado de los controles es de U10; el resumen de traza
es de U5. La bandeja **reúne y muestra** lo que esas unidades ya guardan, y el
día que guardara su propia copia de cualquiera de ellas habría dos versiones de
la verdad y una forma de que discrepen.

Lo que sí es suyo son dos cosas que ninguna otra unidad tiene dónde poner: el
aviso de que un caso cambió, para que la cola y la vista se actualicen solas, y
el recibo que hace que una decisión repetida no se aplique dos veces.

```yaml
entities:
  - name: InboxEvent
    description: >
      El aviso de que un caso cambió, que viaja por SSE a la cola y a la vista
      abiertas (C-06). Se guarda y no solo se emite: el navegador que se
      reconecta manda `Last-Event-ID` y el servidor reproduce lo posterior
      (ADR-021), y eso exige que los eventos existan después de haberse
      entregado.
    identifier: event_id
    attributes:
      - name: event_id
        type: integer
        required: true
        unique: true
        constraints: >
          Creciente **por aseguradora**. Es el `id:` del cable y la posición
          desde la que se reanuda; un identificador global dejaría huecos en la
          secuencia que ve un inquilino, y un navegador que pidiera desde el
          último hueco recibiría eventos de otra aseguradora o ninguno.
      - name: tenant_id
        type: string
        required: true
        references: Tenant (TenantIdentity, U2)
        constraints: "Con política de fila, como toda tabla del aplicativo"
      - name: case_id
        type: string
        required: true
        references: Case (CaseRecord, U4)
      - name: kind
        type: enum
        required: true
        allowed_values: [case_created, case_updated, case_decided]
        constraints: >
          Conjunto cerrado, el mismo que la unión de C-06. Un cuarto tipo es un
          cambio de contrato, no un valor más.
      - name: summary_redacted
        type: string
        required: true
        constraints: >
          Ya redactado al **escribirse**, no al leerse. Un evento lleva lo justo
          para que una fila se actualice sin volver a pedir el caso, y eso
          incluye texto que salió de una persona.
      - name: created_at
        type: datetime
        required: true
    constraints:
      - "Un evento nunca se modifica ni se borra salvo por el purgador de visitantes (C-11)"
      - "Un evento de un caso de otra aseguradora no existe para esta: lo impide la política de fila"
    relationships:
      - "InboxEvent (muchos) -> Case (uno): cada evento avisa de un caso"

  - name: DecisionReceipt
    description: >
      El recibo de una escritura idempotente de la bandeja: una decisión o una
      corrección de campo. C-05 promete que repetir la misma clave devuelve **la
      primera** decisión y no crea otra, y ninguna otra unidad tiene dónde
      guardar esa promesa. Es una sola entidad para las dos escrituras porque es
      un solo mecanismo; dos tablas serían dos sitios donde arreglar el mismo
      fallo.
    identifier: receipt_id
    attributes:
      - name: receipt_id
        type: string
        required: true
        unique: true
      - name: tenant_id
        type: string
        required: true
        references: Tenant (TenantIdentity, U2)
      - name: idempotency_key
        type: string
        required: true
        constraints: "Único por aseguradora y operación; lo elige quien llama"
      - name: operation
        type: enum
        required: true
        allowed_values: [decision, field_correction]
      - name: case_id
        type: string
        required: true
        references: Case (CaseRecord, U4)
      - name: request_digest
        type: string
        required: true
        constraints: >
          Resumen de lo que se pidió. Es lo que distingue "la misma petición otra
          vez" de "otra petición con la clave reciclada": la primera devuelve el
          resultado guardado y la segunda es un conflicto, porque devolverle a
          alguien el resultado de una petición que no hizo es peor que fallar.
      - name: result_ref
        type: string
        required: true
        constraints: "El identificador de lo que se escribió: la decisión o la entrada de historial"
      - name: created_at
        type: datetime
        required: true
    constraints:
      - "La pareja (tenant_id, operation, idempotency_key) es única"
      - "Un recibo no se modifica nunca: registra lo que ya ocurrió"
    relationships:
      - "DecisionReceipt (muchos) -> Case (uno)"
```

## Lo que no es una entidad, y por qué

| Lo que se muestra | De quién es | Por qué no se copia |
| --- | --- | --- |
| Fila de la cola | `Case` de U4 | Es una proyección de lo que U4 ya guarda, filtrada y ordenada al consultar. Una copia sería una segunda verdad que hay que mantener al día. |
| Evidencia del caso | U4, U8, U9, U10, U5 | Cada bloque lo guarda su dueña y la bandeja lo pide al abrirlo. Es lo que hace que la vista no pueda mostrar algo distinto de lo que decidió el sistema. |
| Decisión y su comentario | `Case.resolution` y el historial de U4 | U4 ya registra quién decidió, cuándo y con qué comentario. La bandeja aporta el recibo de idempotencia, no la decisión. |
| Credencial y enlace firmado | U2 | La bandeja los consume; emitirlos y validarlos es de U2 (C-07). |

## Resumen

Dos entidades guardadas, ambas de la bandeja y de nadie más: el aviso que
mantiene viva la pantalla y el recibo que impide decidir dos veces. Todo lo
demás que se ve en la bandeja pertenece a la unidad que lo produjo, y se pide al
mostrarlo.
