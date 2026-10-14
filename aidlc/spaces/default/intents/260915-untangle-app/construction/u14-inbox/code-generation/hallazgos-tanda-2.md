# Hallazgos de la tanda 2 — U14 `inbox`

## 1. Un campo corregido desde la bandeja no podía cumplir su propio invariante

**Qué pasa.** U4 exige que un campo `stated` o `confirmed` lleve **exactamente una**
evidencia: o el turno donde se dijo, o la entrada de historial que lo cambió. Una
corrección desde la bandeja no tiene turno —no hay conversación— así que su evidencia
es la entrada. Pero la entrada la creaba `set_field` **por dentro**, después de
construir el campo: cuando el campo se validaba, la entrada todavía no existía y no
había a qué apuntar.

**Consecuencia.** Ninguna corrección desde la bandeja era posible. No lo veía nadie
porque hasta hoy nadie había corregido un campo por fuera de la conversación.

**Arreglo.** Quien llama acuña el identificador de la entrada **antes**, lo pone en el
campo como evidencia y se lo pasa a `set_field`, que lo reenvía a la entrada. Cambio
aditivo en `case_record/history.py` y `case_record/api.py`: quien no lo pase sigue
teniendo el comportamiento de siempre.

## 2. La expansión de citas era una consulta por respuesta

Lo encontró la prueba que cuenta consultas, que es exactamente para lo que existe.
Abrir un caso con dos respuestas de cobertura costaba once consultas en vez de diez:
`details_for` se llamaba dentro del bucle de respuestas. Ahora se llama **una vez**
para el caso entero y los detalles se reparten por identificador de cláusula.

La prueba siembra **dos** respuestas y **dos** turnos a propósito: con uno de cada,
una implementación que pidiera por elemento daría el mismo número que una que pide
por lote, y no distinguiría nada.

## 3. Lo que impone la numeración por aseguradora no es el `WHERE`

Segunda aparición de la forma que la tanda 1 dejó escrita. Quitar
`WHERE tenant_id = :tenant_id` del `MAX(event_id)` **no tumba ninguna prueba**: la
política de fila ya filtró la tabla, así que un `MAX` global es inalcanzable desde el
punto único de sesión. El filtro se escribe igual —es una segunda copia y hace la
consulta legible— pero no es el cerrojo. Queda escrito en el docstring de
`inbox/events.py`.

Que la misma forma aparezca dos veces en dos tandas seguidas dice que no es una
casualidad de esta unidad: en un sistema con aislamiento en la base, **buena parte de
lo que parece imponer una regla en el código es una segunda copia**. La regla de
revisión ya lo recoge; esto es su caso confirmatorio.

## 4. Una unidad no importa las excepciones del motor

Las dos escrituras idempotentes detectaban la carrera atrapando `IntegrityError` de
SQLAlchemy. El contrato de importaciones lo rechaza, y tiene razón: el resto del
repositorio resuelve lo mismo con `ON CONFLICT ... DO NOTHING RETURNING`, que además
lo dice mejor —un conflicto de clave de idempotencia es un **resultado previsto**, no
un fallo—. Reescrito así en `receipts.py` y en `events.py`, con las roturas repetidas
después del cambio para comprobar que las pruebas siguen mordiendo.

## Diez roturas, nueve caídas

| Rotura | Qué se cayó |
| --- | --- |
| El resumen del aviso se guarda sin redactar | La prueba que lee la fila de la base |
| La reanudación empieza desde el principio | Tres pruebas de reanudación |
| El identificador del aviso es global | **Nada** — ver el hallazgo 3 |
| La clave reciclada devuelve el resultado guardado | La prueba del conflicto |
| Sin clave de idempotencia se corrige igual | Su prueba |
| No se mira el recibo antes de escribir | La de repetir sin corregir dos veces |
| "Sin cláusula" y "no pude verificar" se colapsan | Su prueba |
| Los controles sin revisar se dan por buenos | Su prueba |
| La vista deja de traer la regla disparada | La de los seis bloques |
| La corrección no deja actor de personal | La del rastro |
