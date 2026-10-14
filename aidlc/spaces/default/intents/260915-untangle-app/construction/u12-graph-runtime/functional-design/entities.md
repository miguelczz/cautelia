# Entidades — U12 `graph-runtime`

U12 crea **tres tablas**, y las tres existen por la misma razón: el proceso se
puede morir a mitad de una conversación. Un punto de control que solo viviera en
memoria haría de cada reinicio del servidor una conversación perdida (AC1.19.4), y
una ejecución de nodo sin fila haría que un relanzamiento gastara el proveedor dos
veces por el mismo trabajo.

Las tres llevan columna de aseguradora, aislamiento por fila habilitado y forzado,
y su prueba de aislamiento, como cada tabla nueva del proyecto.

## Lo que U12 crea

| Entidad | Para qué | Regla |
| --- | --- | --- |
| `GraphCheckpoint` | El estado del grafo después de cada turno, para reanudar sin repetir lo confirmado | BR3.1, BR3.2 |
| `HumanReviewRequest` | La pausa hacia la bandeja: por qué se pausó, si sigue viva y cuándo se retiró | BR4.1, BR4.4 |
| `NodeRun` | Una fila por ejecución de nodo: su intento, su desenlace, su latencia y su arrendamiento | BR5.1, BR5.4, BR6.2 |

```yaml
entities:

  - name: GraphCheckpoint
    description: El estado del grafo de un caso, en un paso. Lo escribe el checkpointer de LangGraph, no el código del aplicativo, y por eso su aislamiento es la decisión de diseño más delicada de esta unidad (FD-U12-3).
    stored_in: "Tabla `graph_checkpoint`"
    attributes:
      - { name: checkpoint_id, type: identifier, required: true, constraint: "Lo genera el checkpointer." }
      - { name: tenant_id, type: identifier, required: true, references: "Tenant (U2)", constraint: "BR6.1: columna propia, no derivada del hilo. Un identificador de hilo que llevara la aseguradora dentro obligaría a parsear texto para aislar." }
      - { name: case_id, type: identifier, required: true, references: "Case (U4)" }
      - { name: thread_id, type: string, required: true, constraint: "El hilo de LangGraph. Es el caso: un caso, una conversación (BR3.1)." }
      - { name: step, type: integer, required: true, constraint: "Monótono por hilo. Reanudar es leer el mayor." }
      - { name: payload, type: bytes, required: true, constraint: "El estado serializado. **Cifrado en reposo con el mismo cifrador del caso** (BR6.3): lleva dentro el texto de la persona, y una tabla del grafo no es menos sensible que la del caso por estar en otro módulo." }
      - { name: created_at, type: timestamp, required: true }

  - name: HumanReviewRequest
    description: La pausa hacia la bandeja. Existe como fila y no solo como estado del caso porque la pausa se puede retirar (BR4.4) y un estado sin historia no puede decir que se retiró.
    stored_in: "Tabla `human_review_request`"
    attributes:
      - { name: request_id, type: identifier, required: true }
      - { name: tenant_id, type: identifier, required: true, references: "Tenant (U2)" }
      - { name: case_id, type: identifier, required: true, references: "Case (U4)" }
      - { name: reason, type: enum, required: true, allowed_values: [compliance_referral, abuse, provider_failure, incomplete_capture], constraint: "BR4.1: el motivo por el que se pausó, del conjunto cerrado. Sin él, la bandeja recibe casos sin saber qué mirar." }
      - { name: status, type: enum, required: true, allowed_values: [open, resolved, withdrawn], constraint: "BR4.4: `withdrawn` es la pausa que se retiró porque la persona volvió dentro de su ventana; colapsarla con `resolved` diría que alguien la decidió." }
      - { name: created_at, type: timestamp, required: true }
      - { name: resolved_at, type: timestamp, required: false }
      - { name: withdrawn_at, type: timestamp, required: false }

  - name: NodeRun
    description: Una fila por ejecución de nodo, del ritmo que sea. Es lo que hace que un relanzamiento tras la muerte del proceso no vuelva a gastar el proveedor por un trabajo que ya se hizo (BR5.4).
    stored_in: "Tabla `node_run`"
    attributes:
      - { name: node_run_id, type: identifier, required: true }
      - { name: tenant_id, type: identifier, required: true, references: "Tenant (U2)" }
      - { name: case_id, type: identifier, required: true, references: "Case (U4)" }
      - { name: node, type: enum, required: true, allowed_values: [intake, policy_verification, decision, compliance], constraint: "La misma grafía que el módulo, el tramo de la traza y la etiqueta del reporte (convención 3)." }
      - { name: rhythm, type: enum, required: true, allowed_values: [turn, background], constraint: "El del nodo, no el de la llamada: un nodo de fondo ejecutado desde un turno seguiría siendo de fondo, y eso sería el fallo que BR2.3 prohíbe." }
      - { name: attempt, type: integer, required: true, constraint: "1 el primero. Junto con `max_attempts` es lo que la traza publica cuando un turno se degrada (AC2.10.1)." }
      - { name: max_attempts, type: integer, required: true, constraint: "Copiado del `NodeSpec` en el momento de ejecutar, no leído después: cambiar la política no reescribe la historia." }
      - { name: outcome, type: enum, required: true, allowed_values: [running, succeeded, failed, degraded, abandoned], constraint: "BR5.1. `degraded` es agotó los intentos y se emitió su texto; `abandoned` es el arrendamiento venció y otro proceso lo tomó. Nunca se colapsan: el primero es una respuesta al asegurado y el segundo es una operación." }
      - { name: error_type, type: enum, required: false, allowed_values: [timeout, rate_limited, unavailable, invalid_response], constraint: "La taxonomía cerrada de la frontera del proveedor (convención 8a). El tipo del SDK nunca llega aquí." }
      - { name: latency_ms, type: integer, required: false, constraint: "Lo que publica PERF de esta unidad, por nodo." }
      - { name: idempotency_key, type: string, required: true, constraint: "BR5.4: derivada del caso, el nodo y la entrada, nunca del reloj ni de un aleatorio. Dos relanzamientos del mismo trabajo comparten clave y el segundo no gasta." }
      - { name: lease_owner, type: string, required: false, constraint: "Qué proceso lo tiene. Nulo cuando terminó." }
      - { name: lease_expires_at, type: timestamp, required: false }
      - { name: heartbeat_at, type: timestamp, required: false, constraint: "BR5.5: el latido. Un arrendamiento sin latido es indistinguible de un proceso muerto, y el barrido no tendría cómo decidir." }
      - { name: started_at, type: timestamp, required: true }
      - { name: finished_at, type: timestamp, required: false }
```

## Lo que U12 compone y no persiste

El **estado tipado** es la entidad central de esta unidad y no es una tabla: se
compone de los conjuntos de escritura que declaran los cuatro nodos, y lo que se
guarda de él es el `payload` del punto de control.

```yaml
entities:

  - name: GraphState
    description: El estado tipado del grafo. **Se compone, no se escribe a mano**: sus campos son la unión de los conjuntos de escritura de los cuatro `NodeSpec`, más los campos de entrada que el canal entrega. Escribirlo a mano lo dejaría divergir del primer nodo que añadiera un campo.
    stored_in: "En memoria; su serialización es el `payload` de `GraphCheckpoint`"
    attributes:
      - { name: tenant_id, type: identifier, required: true }
      - { name: case_id, type: identifier, required: true }
      - { name: turn, type: "InboundTurn (C-14)", required: true, constraint: "BR1.4: el texto de la persona vive aquí, como campo delimitado, y nunca se concatena a un prompt de sistema." }
      - { name: node_writes, type: "unión de los writes de los cuatro NodeSpec", required: true, constraint: "BR1.5: dos nodos no comparten ningún campo, y la composición **falla al arrancar** si dos los declaran (AC4.9.5)." }
      - { name: pending_background, type: "set of node names", required: false, constraint: "Qué trabajo de fondo está en vuelo. Es lo que deja al turno decidir si emite la frase de espera sin preguntarle a la base (BR2.4)." }

  - name: NodeName
    description: El conjunto cerrado que devuelve la transición. No es una entidad nueva: es el enum que ya vive en la traza (`telemetry/traces/models.py`), y se reusa en vez de declararse otra vez (convención 3).
    stored_in: "Código; ya existe"
    attributes:
      - { name: value, type: enum, required: true, allowed_values: [intake, policy_verification, decision, compliance], constraint: "AC4.9.2: la transición devuelve uno de estos cuatro y nada más. Un texto libre del modelo no puede nombrar una ruta que no esté aquí." }
```

## Lo que U12 lee

| De quién | Qué | Para qué |
| --- | --- | --- |
| Los cuatro nodos (C-15) | Su `NodeSpec` y su `run` | Componer el estado y ejecutarlos con su política (BR1.1, BR5.1) |
| U4 `case-record` (C-12) | El caso, su estado y su completitud; y le aplica las transiciones | Crear el caso, pausarlo, reanudarlo (BR3.1, BR4.1) |
| U2 `tenancy` (C-25, C-26) | La sesión con la aseguradora ya fijada, y la configuración | Puntos de control aislados y los minutos de inactividad (BR3.3, BR6.1) |
| U10 `compliance` (C-20) | Los tres controles del turno | El punto único de salida (BR2.5, BR6.4) |
| U1 `workspace` (C-1) | El catálogo por idioma | Frases de espera, de degradación y de error (BR5.2) |
| U5 `provider-platform` (C-23) | El registro de uso por turno y por nodo | Los tramos de la traza (BR6.2) |

## Por qué los puntos de control son una tabla y no un archivo

Porque el proceso único se reinicia —en el hospedaje gratuito se duerme y
despierta— y porque la bandeja tiene que poder reanudar un caso que nadie tiene
abierto. Un punto de control en memoria convierte cada despertar en una
conversación perdida, que es exactamente lo que AC1.19.4 prohíbe.
