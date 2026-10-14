# Contratos — Untangle

Los acuerdos formales entre las piezas del aplicativo y con quien lo consume
desde afuera. Cada contrato dice **qué datos cruzan la frontera, con qué forma,
por qué mecanismo, quién es su dueño y qué pasa cuando algo falla o tarda**.
Construcción parte de aquí: una unidad puede construirse contra el contrato de
otra sin esperar a que exista.

Esta etapa no reabre decisiones tomadas: el estilo de arquitectura, el lenguaje,
los proveedores y el mapa de dependencias ya están aprobados. Lo que hace es
convertir los **14 puntos de integración** que dejó Units Generation en acuerdos
verificables, y fijar la forma exacta de los archivos versionados, que
`unit-of-work.md` dejó explícitamente a esta etapa.

**Fuentes consumidas.**

- **Unidades de trabajo** (`../units-generation/unit-of-work.md`): las 22
  unidades con su tipo, lo que contiene y lo que no contiene cada una, sus
  entidades, el árbol del código y las preguntas abiertas PA-2 a PA-13 que pasan
  a Construcción.
- **Dependencias entre unidades**
  (`../units-generation/unit-of-work-dependency.md`): las 89 aristas del mapa,
  los 14 puntos de integración con su forma y su contrato, y las condiciones
  externas que afectan a una unidad sin ser dependencias.
- **Componentes** (`../domain-design/components.md`): los 23 componentes con sus
  dependencias, y sobre todo la tabla de propiedad de entidades, que fija qué
  atributos tiene cada entidad y quién es su único dueño; de ahí sale la forma
  de los datos que cruzan cada frontera.
- **Requisitos** (`../requirements-analysis/requirements.md`): los grupos FR1 a
  FR14 y los NFR con su valor esperado, que fijan los tiempos, los límites y los
  errores que cada contrato tiene que admitir.

También se aplican las decisiones de arquitectura de `../domain-design/decisions.md`
(ADR-001 a ADR-021), en particular ADR-001 (interfaz pública por módulo en
`api.py` y contratos de `import-linter`), ADR-002 (esquema OpenAPI, cliente
generado y chequeo de deriva), ADR-018 (puertos de proveedor) y ADR-021 (tiempo
real con SSE).

## Decisiones de esta etapa

Las siete que respondió Miguel, todas en la opción recomendada:

| # | Decisión | Qué se decidió |
| --- | --- | --- |
| CD-1 | Forma de los errores de la API | `application/problem+json` (RFC 9457) con `code` de lista cerrada y `trace_id`; el texto que lee una persona sale del catálogo por idioma, nunca del campo `detail` |
| CD-2 | Versionado | **Sin versión en la ruta: la base es `/api`.** Solo cambios aditivos; el disparador para versionar es que aparezca un consumidor fuera de este repositorio. *(Cambio de Miguel del 2026-09-18, después de la primera revisión: la primera versión de este documento proponía `/api/v1`)* |
| CD-3 | Qué cruza entre módulos del servidor | Modelos propios de solo lectura por módulo; los objetos de SQLAlchemy no salen de su módulo y las referencias viajan como identificador |
| CD-4 | Formato de los archivos versionados | YAML para lo que escribe una persona, JSON para lo que escribe una máquina; cada familia con su JSON Schema y su validación en `verify.sh` |
| CD-5 | Cómo viaja la credencial | Cookie `HttpOnly`, `Secure`, `SameSite=Lax` en los tres casos; el enlace firmado se canjea una vez y el token nunca llega al servidor por la dirección. *(Aclarado por Miguel el 2026-09-20: "se canjea una vez" es un canje por carga de pantalla, no un token de un solo uso; ver la nota en C-07)* |
| CD-6 | Escrituras repetidas | Clave de idempotencia del cliente en las tres escrituras que importan |
| CD-7 | Turno entre canal y grafo | Un flujo de eventos tipados de lista cerrada, el mismo para chat y voz |

Las que tomé yo aplicando documentos aprobados, con su razón:

| # | Decisión | Por qué |
| --- | --- | --- |
| CD-8 | Un contrato por **superficie que ofrece** una unidad, no uno por arista | El mapa tiene 89 aristas y solo 30 superficies; un contrato por arista repetiría el mismo acuerdo hasta diez veces y ninguna copia sería la autoritativa |
| CD-9 | Los eventos de SSE se especifican como **unión discriminada en el esquema OpenAPI**, no con AsyncAPI | ADR-021 rechazó AsyncAPI por escrito: hay un solo consumidor y vive en el mismo repositorio. Es una desviación del texto de la etapa, que sugiere AsyncAPI para contratos por eventos |
| CD-10 | Un caso de otra aseguradora responde exactamente igual que uno inexistente (`404`, `code: not_found`) | US3.x y RT-4: distinguirlos revela que el caso existe |
| CD-11 | La interfaz pública de un módulo vive en su `api.py` y es lo único importable desde fuera | ADR-001 (enmienda del 2026-09-17), comprobado con `import-linter` |
| CD-12 | El contrato de borrado de datos de visitante es un `Protocol` con registro explícito en la raíz de composición | UG-3 pide una definición única y que cada dueño implemente; el registro explícito se comprueba con una prueba que compara contra las tablas con datos de visitante |

## Tabla de contratos

Treinta contratos en cuatro familias. "Consumidor" nombra a quien depende del
acuerdo; `Externa` marca un consumidor fuera del aplicativo. Los números son
identificadores estables, no un orden: C-30 se añadió después de la primera
revisión y vive con los demás contratos de base de datos, sin renumerar nada.

| # | Unidad proveedora | Consumidor | Mecanismo | Dueño |
| --- | --- | --- | --- | --- |
| C-01 | U6 `web-shell` | Externa: interfaz web compilada; todas las unidades con rutas | Convenciones de la API HTTP (OpenAPI) | U6 |
| C-02 | U6 `web-shell` | Externa: chequeo periódico del intent `infra`; interfaz web | HTTP síncrono (OpenAPI) | U6 |
| C-03 | U13 `chat` | Externa: interfaz web, visitante público | HTTP síncrono (OpenAPI) | U13 |
| C-04 | U13 `chat` | Externa: interfaz web | SSE (unión tipada en OpenAPI) | U13 |
| C-05 | U14 `inbox` | Externa: interfaz web, ajustador con credencial | HTTP síncrono (OpenAPI) | U14 |
| C-06 | U14 `inbox` | Externa: interfaz web | SSE sobre `InboxEvent` (unión tipada en OpenAPI) | U14 |
| C-07 | U2 `tenancy` y U14 `inbox` | Externa: visitante con enlace firmado | HTTP síncrono + cookie de caso | U2 (token), U14 (ruta) |
| C-08 | U16 `voice-call` y U17 `voice-public-link` | Externa: consola de llamada | HTTP síncrono (OpenAPI) | U16; límites, U17 |
| C-09 | U22 `public-evidence` | Externa: cualquier visitante, sin credencial | HTTP síncrono (OpenAPI) | U22 |
| C-10 | U2 `tenancy` | Toda unidad con tablas | Llamada en proceso (`tenancy/api.py`) | U2 |
| C-30 | U2 `tenancy` (convención) y cada unidad con tablas | El proceso único al arrancar; `verify.sh` | Una sola historia de migraciones con SQL explícito | U2 (convención y aserción), cada unidad (sus revisiones) |
| C-11 | U2 `tenancy` | Dueños de datos de visitante; U20 lo ejecuta | `Protocol` en proceso con registro explícito | U2 |
| C-12 | U4 `case-record` | U8, U9, U10, U11, U12, U14, U19, U20 | Llamada en proceso (`case_record/api.py`) | U4 |
| C-13 | U3 `pii-redaction` | U4, U5, U10, U21 | Llamada en proceso (`compliance/redaction/api.py`) | U3 |
| C-14 | U12 `graph-runtime` | U13, U16, U18, U14 | Llamada en proceso con flujo de eventos tipados | U12 |
| C-15 | U8, U9, U10, U11 (nodos) | U12 `graph-runtime` | `Protocol` de nodo en proceso | Cada unidad del nodo |
| C-16 | U5 y U15 (`providers`) | U7, U8, U10, U11, U15, U21 | `Protocol` en proceso (`providers/ports.py`) | U5 (modelo y embeddings), U15 (voz) |
| C-17 | U5 `provider-platform` | U13, U16, U17, U22 | Llamada en proceso (`telemetry/spend/api.py`) | U5 |
| C-18 | U8 `policy-rag` | U11, U12, U14, U20 | Llamada en proceso (`policy_rag/api.py`) | U8 |
| C-19 | U9 `rules-decision` | U11, U12, U14, U19 | Llamada en proceso (`rules/api.py`) | U9 |
| C-20 | U10 `compliance` | U12, U14 | Llamada en proceso (`compliance/controls/api.py`) | U10 |
| C-21 | U1 `workspace` | Todas, y la interfaz por módulo generado | Llamada en proceso + módulo tipado | U1 |
| C-22 | U1 `workspace` | Unidades evaluadas, U13, U16, U21 | Registro en proceso + `Protocol` de conductor | U1 |
| C-23 | U5 `provider-platform` | Todas | Llamada en proceso (`telemetry/traces/api.py`) | U5 |
| C-24 | U1 `workspace` | Toda unidad con rutas, purgas u objetivos | Registro explícito en la raíz de composición | U1 |
| C-25 | U2 `tenancy` | U9, U10, U12, U13, U15, U16, U20 | Archivos YAML versionados + JSON Schema | U2 |
| C-26 | U7 `synthetic-data` | U8, U20 | Archivos JSON versionados + manifiesto | U7 |
| C-27 | U1 y U21 | U13, U16, U21, U22 | Archivos YAML (casos) y JSON (líneas base y reporte) | U1 (formato), U21 (línea base) |
| C-28 | U6 `web-shell` y U1 `workspace` | Interfaz web | Artefactos generados en `app/contracts/` con chequeo de deriva | U6 |
| C-29 | U16 `voice-call` | Externa: navegador del visitante | Transporte de audio en tiempo real | U16 — **pendiente del experimento 1** |

---

# Familia 1 — API HTTP y streams

Una sola API, servida desde el mismo origen que la interfaz (ADR-001, ADR-002).
Todo lo de esta familia entra en `app/contracts/openapi.json` y se regenera con
el cliente de TypeScript en el mismo commit (C-28).

## C-01 — Convenciones de la API HTTP

**Frontera:** todo lo que cruza entre el navegador y el servidor.
**Dueño:** U6 `web-shell`. Ninguna unidad define convenciones propias.

- **Base:** `/api`, **sin versión en la ruta**. Mismo origen que la interfaz; no
  hay CORS entre ellos. El único consumidor es la interfaz de este repositorio,
  que se compila y se despliega con el servidor, así que un prefijo de versión
  no protegería a ningún cliente que no podamos migrar en el mismo commit. La
  regla que lo sostiene es **solo cambios aditivos** dentro de `/api`, y el
  **disparador escrito** para introducir versión es que aparezca un consumidor
  fuera de este repositorio (otra aplicación, un socio, un cliente público). Ese
  día se introduce `/api/v2` y la ruta sin versión queda congelada como v1.
- **Errores:** `application/problem+json` (RFC 9457). El campo `title` y el
  campo `detail` son texto técnico en inglés para quien depura; **la interfaz
  nunca los muestra**: resuelve el mensaje por el catálogo de textos con la
  clave que corresponde a `code` (convención 4 de `team.md`).
- **Idempotencia:** cabecera `Idempotency-Key` (UUID v4) obligatoria en las tres
  escrituras de CD-6. El alcance de la clave es ruta más principal; se guarda
  hasta el reinicio nocturno o 24 horas, lo que ocurra primero. La misma clave
  con el mismo cuerpo devuelve la respuesta original; con un cuerpo distinto
  devuelve `409` y `code: conflict_idempotency`.
- **Credenciales:** tres cookies `HttpOnly; Secure; SameSite=Lax; Path=/api`:
  `ut_staff` (persona de la bandeja, con aseguradora y rol), `ut_case` (un solo
  caso, vida igual a la del enlace firmado) y `ut_visitor` (clave del navegador,
  sin identidad). Toda petición que cambia estado comprueba además
  `Sec-Fetch-Site` o `Origin`; una discrepancia responde `403` con
  `code: forbidden_origin`.
- **Aislamiento:** un caso de otra aseguradora responde exactamente igual que
  uno inexistente: `404` con `code: not_found` (CD-10).
- **Paginación:** por cursor opaco, `?cursor=&limit=` con `limit` máximo 100 y
  `next_cursor` en la respuesta. Nunca por número de página.
- **Idioma:** el cuerpo lleva `language` explícito cuando el dato tiene idioma;
  `Accept-Language` solo decide el idioma de las claves de catálogo que devuelva
  el servidor.
- **Correlación:** toda respuesta lleva `X-Trace-Id`, el mismo valor que
  `trace_id` del error y que el identificador de traza del caso.
- **Tiempos:** cada ruta declara su presupuesto en su propio contrato. Agotado
  el presupuesto, el servidor responde `504` con `code: provider_timeout` o
  `503` con `code: provider_unavailable`, nunca un error genérico.

```yaml
# OpenAPI 3.1 — componentes compartidos por toda la API
openapi: 3.1.0
info: { title: Untangle API, version: "1.0.0" }
servers: [{ url: /api }]
components:
  securitySchemes:
    staffCookie:   { type: apiKey, in: cookie, name: ut_staff }
    caseCookie:    { type: apiKey, in: cookie, name: ut_case }
    visitorCookie: { type: apiKey, in: cookie, name: ut_visitor }
  parameters:
    IdempotencyKey:
      name: Idempotency-Key
      in: header
      required: true
      schema: { type: string, format: uuid }
    Cursor: { name: cursor, in: query, schema: { type: string } }
    Limit:  { name: limit,  in: query, schema: { type: integer, minimum: 1, maximum: 100, default: 25 } }
  schemas:
    Problem:
      type: object
      required: [type, title, status, code, trace_id]
      properties:
        type:     { type: string, format: uri, default: "about:blank" }
        title:    { type: string, description: "Texto tecnico en ingles; la interfaz no lo muestra" }
        status:   { type: integer }
        detail:   { type: string }
        instance: { type: string }
        trace_id: { type: string }
        retry_after_s: { type: integer, nullable: true }
        code:
          type: string
          enum:
            - validation_failed
            - not_found
            - forbidden_origin
            - link_invalid
            - conflict_idempotency
            - rate_limited_session
            - rate_limited_daily
            - rate_limited_site
            - budget_exhausted
            - provider_timeout
            - provider_unavailable
            - unverifiable
            - internal
    Page:
      type: object
      required: [items, next_cursor]
      properties:
        items: { type: array, items: {} }
        next_cursor: { type: string, nullable: true }
  responses:
    Problem:
      description: Error
      content:
        application/problem+json:
          schema: { $ref: "#/components/schemas/Problem" }
```

**Qué pasa cuando falla.** Todo error sale con esta forma, incluidos los de
degradación. Un `code` nuevo es un cambio aditivo solo si la interfaz ya tiene
un camino por defecto para códigos desconocidos; esa rama por defecto es
obligatoria en el cliente.

## C-02 — Salud y estado del proceso

**Frontera:** U6 → chequeo periódico del intent `infra` y páginas de estado.
**Mecanismo:** HTTP síncrono, sin credencial y sin aseguradora.

```yaml
paths:
  /health/live:
    get:
      summary: El proceso responde
      security: []
      responses:
        "200": { description: vivo }
  /health/ready:
    get:
      summary: El proceso puede atender (base de datos y configuracion cargada)
      security: []
      responses:
        "200":
          description: listo
          content:
            application/json:
              schema:
                type: object
                required: [status, checks, version]
                properties:
                  status:  { type: string, enum: [ready] }
                  version: { type: string, description: "commit sha" }
                  checks:
                    type: object
                    properties:
                      database: { type: string, enum: [ok, degraded, down] }
                      tenants:  { type: integer }
        "503":
          $ref: "#/components/responses/Problem"
```

**Qué pasa cuando falla.** `ready` en `503` mantiene el proceso vivo y la
interfaz muestra la página "la demo está despertando" (U6). El presupuesto de
respuesta es 1 segundo; el chequeo no toca proveedores externos ni gasta dinero.

## C-03 — Chat público

**Frontera:** U13 → interfaz web y visitante público.
**Presupuesto:** `POST` de mensaje responde en 300 ms o menos (solo acepta y
encola); la primera palabra llega por el stream antes de 3 s p95 (NFR4).

```yaml
paths:
  /tenants/{tenant}/chat/bootstrap:
    get:
      summary: Lo que la pantalla necesita antes del primer mensaje
      security: [{ visitorCookie: [] }]
      responses:
        "200":
          content:
            application/json:
              schema:
                type: object
                required: [tenant, language, disclosure_keys, limits, example_policy]
                properties:
                  tenant:   { type: string }
                  language: { type: string, enum: [es, en] }
                  disclosure_keys:
                    type: array
                    items: { type: string }
                    description: "Claves del catalogo: divulgacion de IA, demo con polizas de ejemplo y aviso de no escribir datos reales"
                  limits:
                    type: object
                    properties:
                      messages_per_session: { type: integer }
                      messages_per_day:     { type: integer }
                  example_policy: { type: string, description: "Numero de poliza de ejemplo del tenant" }
                  session_id: { type: string, nullable: true, description: "Sesion retomable de este navegador" }
  /tenants/{tenant}/chat/messages:
    post:
      summary: Enviar un turno del visitante
      security: [{ visitorCookie: [] }]
      parameters: [{ $ref: "#/components/parameters/IdempotencyKey" }]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [text, language]
              properties:
                text:     { type: string, maxLength: 4000 }
                language: { type: string, enum: [es, en] }
                case_id:  { type: string, nullable: true }
      responses:
        "202":
          description: Aceptado; la respuesta llega por el stream
          content:
            application/json:
              schema:
                type: object
                required: [message_id, session_id, stream_from]
                properties:
                  message_id:  { type: string }
                  session_id:  { type: string }
                  case_id:     { type: string, nullable: true }
                  stream_from: { type: string, description: "Id de evento desde el que leer el stream" }
        "409": { $ref: "#/components/responses/Problem" }
        "429": { $ref: "#/components/responses/Problem" }
  /tenants/{tenant}/chat/stream:
    get:
      summary: Stream de eventos del chat (ver C-04)
      security: [{ visitorCookie: [] }]
      parameters:
        - { name: Last-Event-ID, in: header, schema: { type: string } }
      responses:
        "200":
          content:
            text/event-stream: {}
  /compare:
    get:
      summary: La misma pregunta respondida por las tres aseguradoras
      security: [{ visitorCookie: [] }]
      parameters:
        - { name: question, in: query, required: true, schema: { type: string, maxLength: 500 } }
        - { name: language, in: query, required: true, schema: { type: string, enum: [es, en] } }
      responses:
        "200":
          content:
            application/json:
              schema:
                type: object
                required: [answers]
                properties:
                  answers:
                    type: array
                    items:
                      type: object
                      required: [tenant, outcome]
                      properties:
                        tenant:  { type: string }
                        outcome: { type: string, enum: [verified, no_clause_found, unverifiable] }
                        summary: { type: string, nullable: true }
                        citations:
                          type: array
                          items:
                            type: object
                            properties:
                              clause_id:      { type: string }
                              clause_version: { type: string }
                              part:           { type: string }
                              text:           { type: string }
```

**Qué pasa cuando falla.** Límite de sesión, de día o del sitio: `429` con
`rate_limited_session`, `rate_limited_daily` o `rate_limited_site` y
`retry_after_s`; la pantalla muestra el texto del catálogo, nunca un error
genérico (FR4.6). Techo de gasto: `503` con `budget_exhausted`; el chat del plan
gratuito sigue vivo aunque la voz esté cortada (FR10.4).

## C-04 — Stream del chat

**Frontera:** U13 → interfaz web. **Mecanismo:** SSE, `text/event-stream`.
**Dueño:** U13. La unión de eventos es la misma que devuelve C-14, serializada.

- Cada evento lleva `id:` creciente dentro de la sesión; el navegador reanuda
  solo con `Last-Event-ID` y el servidor reproduce lo posterior (ADR-021).
- Como mucho un stream por pestaña; se cierra cuando la pestaña se oculta.
- La autenticación es la cookie del navegador: `EventSource` no manda cabeceras.
- Latido cada 15 segundos para que los intermediarios no corten la conexión.

```yaml
# Union discriminada por `kind`; entra en openapi.json y en el chequeo de deriva
ChatStreamEvent:
  oneOf:
    - $ref: "#/components/schemas/TurnPartial"
    - $ref: "#/components/schemas/TurnFinal"
    - $ref: "#/components/schemas/TurnWaiting"
    - $ref: "#/components/schemas/TurnHandoff"
    - $ref: "#/components/schemas/TurnError"
    - $ref: "#/components/schemas/CaseUpdated"
    - $ref: "#/components/schemas/Heartbeat"
  discriminator: { propertyName: kind }
TurnPartial:
  type: object
  required: [kind, message_id, seq, text]
  properties:
    kind:       { type: string, const: turn.partial }
    message_id: { type: string }
    seq:        { type: integer }
    text:       { type: string, description: "Fragmento ya redactado y pasado por la guardia de salida" }
TurnFinal:
  type: object
  required: [kind, message_id, text, language]
  properties:
    kind:       { type: string, const: turn.final }
    message_id: { type: string }
    text:       { type: string }
    language:   { type: string, enum: [es, en] }
    case_id:    { type: string, nullable: true }
    citations:
      type: array
      items:
        type: object
        required: [clause_id, clause_version, part, text, trace_ref]
        properties:
          clause_id:      { type: string }
          clause_version: { type: string }
          part:           { type: string }
          text:           { type: string }
          trace_ref:      { type: string }
TurnWaiting:
  type: object
  required: [kind, copy_key]
  properties:
    kind:     { type: string, const: turn.waiting }
    copy_key: { type: string, description: "Clave del catalogo; el texto no viaja resuelto" }
TurnHandoff:
  type: object
  required: [kind, reason_code, copy_key]
  properties:
    kind:        { type: string, const: turn.handoff }
    reason_code: { type: string, enum: [rule, compliance, human_request, emergency, limit, unverifiable] }
    copy_key:    { type: string }
    case_id:     { type: string, nullable: true }
    case_link:   { type: string, nullable: true, description: "Enlace firmado del propio caso (C-07)" }
TurnError:
  type: object
  required: [kind, code, copy_key]
  properties:
    kind:     { type: string, const: turn.error }
    code:     { type: string, description: "Mismo vocabulario cerrado que Problem.code" }
    copy_key: { type: string }
CaseUpdated:
  type: object
  required: [kind, case_id, state]
  properties:
    kind:    { type: string, const: case.updated }
    case_id: { type: string }
    state:   { type: string }
    completeness: { type: number }
Heartbeat:
  type: object
  required: [kind]
  properties:
    kind: { type: string, const: heartbeat }
```

**Qué pasa cuando falla.** Si el stream se corta, el navegador reconecta solo y
manda `Last-Event-ID`; el servidor no repite ni pierde eventos (es la prueba de
confirmación de ADR-021). Si el turno falla, llega `turn.error` con su clave de
catálogo: el turno **siempre** termina con `turn.final`, `turn.handoff` o
`turn.error`, nunca en silencio.

## C-05 — Bandeja del ajustador

**Frontera:** U14 → interfaz web, con credencial de aseguradora y rol.
**Presupuesto:** lista y vista de caso en 1 s p95 con la base tibia.

```yaml
paths:
  /tenants/{tenant}/inbox/cases:
    get:
      summary: Cola de casos de la aseguradora
      security: [{ staffCookie: [] }]
      parameters:
        - { name: state,    in: query, schema: { type: string } }
        - { name: channel,  in: query, schema: { type: string, enum: [voice, chat] } }
        - { name: language, in: query, schema: { type: string, enum: [es, en] } }
        - { name: priority, in: query, schema: { type: string } }
        - { $ref: "#/components/parameters/Cursor" }
        - { $ref: "#/components/parameters/Limit" }
      responses:
        "200":
          content:
            application/json:
              schema:
                allOf:
                  - $ref: "#/components/schemas/Page"
                  - type: object
                    properties:
                      items:
                        type: array
                        items:
                          type: object
                          required: [case_id, case_number, state, record_type, channel, language, completeness, updated_at]
                          properties:
                            case_id:      { type: string }
                            case_number:  { type: string }
                            state:        { type: string }
                            record_type:  { type: string, enum: [claim, coverage_inquiry, quote_request] }
                            channel:      { type: string, enum: [voice, chat] }
                            language:     { type: string, enum: [es, en] }
                            priority:     { type: string }
                            completeness: { type: number }
                            derivation_reason: { type: string, nullable: true }
                            updated_at:   { type: string, format: date-time }
  /tenants/{tenant}/inbox/cases/{case_id}:
    get:
      summary: Caso con toda su evidencia (FR8.2)
      security: [{ staffCookie: [] }, { caseCookie: [] }]
      responses:
        "200":
          content:
            application/json:
              schema:
                type: object
                required: [case, fields, transcript, coverage_answers, rule_evaluation, compliance, trace]
                properties:
                  case:   { type: object, description: "Vista de solo lectura de Case (C-12)" }
                  fields: { type: array, items: { type: object } }
                  parties: { type: array, items: { type: object } }
                  transcript:
                    type: array
                    items:
                      type: object
                      properties:
                        turn_id:      { type: string }
                        speaker:      { type: string, enum: [insured, agent, staff] }
                        text_redacted: { type: string }
                        started_at:   { type: string, format: date-time }
                  coverage_answers: { type: array, items: { type: object }, description: "Con sus citas verificadas (C-18)" }
                  rule_evaluation:  { type: object, nullable: true, description: "Categoria, reglas disparadas e insumos (C-19)" }
                  compliance:       { type: object, nullable: true, description: "Resultado de los cuatro controles (C-20)" }
                  trace:            { type: object, description: "Resumen por nodo con costo y latencia (C-23)" }
                  history:          { type: array, items: { type: object } }
        "404": { $ref: "#/components/responses/Problem" }
  /tenants/{tenant}/inbox/cases/{case_id}/fields/{field_key}:
    patch:
      summary: Corregir un campo dejando rastro (FR8.3)
      security: [{ staffCookie: [] }]
      parameters: [{ $ref: "#/components/parameters/IdempotencyKey" }]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [value]
              properties:
                value: { type: string }
      responses:
        "200": { description: Campo corregido; devuelve la entrada de historial }
        "409": { $ref: "#/components/responses/Problem" }
  /tenants/{tenant}/inbox/cases/{case_id}/decision:
    post:
      summary: Aprobar o rechazar; reanuda el grafo desde su punto de control (FR8.4)
      security: [{ staffCookie: [] }, { caseCookie: [] }]
      parameters: [{ $ref: "#/components/parameters/IdempotencyKey" }]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [decision, comment]
              properties:
                decision: { type: string, enum: [approve, reject, request_more] }
                comment:  { type: string, minLength: 1, maxLength: 2000 }
      responses:
        "202":
          description: Decision registrada; el grafo se reanuda de fondo
          content:
            application/json:
              schema:
                type: object
                properties:
                  decision_id: { type: string }
                  case_state:  { type: string }
        "400": { $ref: "#/components/responses/Problem" }
        "409": { $ref: "#/components/responses/Problem" }
  /tenants/{tenant}/inbox/stream:
    get:
      summary: Stream de la bandeja (ver C-06)
      security: [{ staffCookie: [] }, { caseCookie: [] }]
      responses:
        "200":
          content:
            text/event-stream: {}
```

**Qué pasa cuando falla.** Aprobar sin comentario es `400` con
`validation_failed` (FR8.4). Un caso de otra aseguradora, o inexistente, es
`404` con `not_found` (CD-10). Una decisión repetida con la misma clave de
idempotencia devuelve la primera decisión, no crea otra.

**Enmienda del 2026-09-28 (U14, generación de código).** La ruta de decisión
acepta `approve` y `reject` —y `mark_sent` en una agencia—, y **no acepta
`request_more`**. El boceto de arriba la declara; ninguna historia la describe,
ningún criterio la ejercita y ninguna de las cuatro resoluciones de U4 le
corresponde, así que construirla habría sido inventarle una conducta. Un caso que
necesita más información ya tiene camino probado: queda *esperando al asegurado* y
el asegurado lo retoma. Decisión de Miguel del 2026-09-28; añadirla después es un
cambio aditivo. El enum del cuerpo es cerrado, así que un cliente que la mande
recibe un error de forma y no una conducta improvisada.

**Y dos precisiones que lo construido añade**, registradas aquí porque el esquema
las declara y el servidor tiene que cumplirlas:

- `mark_sent` es la acción de una agencia y viaja por la misma ruta. Cuál ofrece
  cada aseguradora sale de su configuración; cuál puede cada rol, de la tabla de
  permisos de U2, que ganó su fila `mark_sent` en este mismo cambio.
- El `409` de esta ruta cubre dos cosas —clave de idempotencia reciclada y estado
  que no admite la acción— y el vocabulario de C-01 solo nombraba la primera. Se
  añadió `conflict_state` a la lista cerrada de códigos. Una ruta no puede elegir
  su código todavía, porque el vocabulario vive en `untangle.server` y las
  unidades están por debajo en el contrato de capas; moverlo es de U6.

## C-06 — Stream de la bandeja

**Frontera:** U14 → interfaz web. **Mecanismo:** SSE sobre `InboxEvent`.
**Dueño:** U14.

- El `id:` del evento es `InboxEvent.event_id`, creciente y con RLS.
- Al conectar se reproducen los eventos posteriores a `Last-Event-ID`.
- Las escrituras del propio proceso despiertan a los suscriptores; una consulta
  de respaldo cada 5 a 10 segundos cubre los reinicios (ADR-021).
- Con cookie de caso (`ut_case`) el stream se filtra a ese único caso.

```yaml
InboxStreamEvent:
  oneOf: [ { $ref: "#/components/schemas/InboxCaseCreated" },
           { $ref: "#/components/schemas/InboxCaseUpdated" },
           { $ref: "#/components/schemas/InboxCaseDecided" },
           { $ref: "#/components/schemas/Heartbeat" } ]
  discriminator: { propertyName: kind }
InboxCaseCreated:
  type: object
  required: [kind, case_id, case_number, state, created_at]
  properties:
    kind:        { type: string, const: case.created }
    case_id:     { type: string }
    case_number: { type: string }
    state:       { type: string }
    summary_redacted: { type: string }
    created_at:  { type: string, format: date-time }
InboxCaseUpdated:
  type: object
  required: [kind, case_id, state]
  properties:
    kind:    { type: string, const: case.updated }
    case_id: { type: string }
    state:   { type: string }
    completeness: { type: number }
    summary_redacted: { type: string }
InboxCaseDecided:
  type: object
  required: [kind, case_id, decision]
  properties:
    kind:     { type: string, const: case.decided }
    case_id:  { type: string }
    decision: { type: string, enum: [approve, reject, request_more] }
```

**Qué pasa cuando falla.** El contenido de cada evento ya viene redactado
(`summary_redacted`), así que un evento nunca es una vía de fuga. Si el proceso
se reinicia y se pierden suscriptores, la consulta de respaldo los recupera sin
que la pantalla haga nada.

## C-07 — Acceso del visitante por enlace firmado

**Frontera:** U2 (token) y U14 (ruta) → visitante que creó su caso en público.
**Regla dura:** el token **no viaja al servidor por la dirección**. El enlace
lleva el token en el fragmento (`https://…/c#<token>`), que el navegador nunca
manda en la petición ni en `Referer`; la pantalla lo lee, lo canjea una vez y
limpia la dirección. Así el token no aparece en la barra, ni en `Referer`, ni en
los registros del servidor (AC3.8.6).

> **Aclaración del 2026-09-20 (decisión de Miguel, en el diseño funcional de
> U2).** "Lo canjea una vez" describe lo que hace **la pantalla al cargar**: una
> sola llamada de canje por carga, y después limpia la dirección. **No** es un
> token de un solo uso: mientras no haya caducado ni esté revocado, el mismo
> enlace se puede volver a canjear, y quien cierre la pestaña vuelve a entrar.
> La lista de causas de rechazo de más abajo sigue siendo cerrada y de cuatro
> entradas, sin "ya canjeado", precisamente porque el canje no quema el token.

```yaml
paths:
  /case-links/redeem:
    post:
      summary: Canjear el token del enlace por una cookie limitada a ese caso
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [token]
              properties:
                token: { type: string }
      responses:
        "200":
          description: Cookie ut_case establecida
          headers:
            Set-Cookie:
              schema: { type: string, example: "ut_case=...; HttpOnly; Secure; SameSite=Lax; Path=/api; Max-Age=<vida restante>" }
          content:
            application/json:
              schema:
                type: object
                required: [case_id, tenant, expires_at, access]
                properties:
                  case_id:    { type: string }
                  tenant:     { type: string }
                  access:     { type: string, enum: [view_and_decide] }
                  expires_at: { type: string, format: date-time }
        "404": { $ref: "#/components/responses/Problem" }
```

- **Vida:** una hora desde que se emite (FR8.7). La cookie nunca vive más que el
  enlace; al vencer, la pantalla muestra "enlace vencido" (página de estado de
  U6) y el servidor responde `404` con `link_invalid`.
- **Alcance:** la cookie abre **solo su caso** y nunca la lista (D6). Con
  `ut_case`, `GET /inbox/cases` responde `404`.
- **Qué pasa cuando falla:** token inválido, vencido, revocado o de otro caso
  responden todos `404` con `link_invalid`, sin distinguir cuál de los cuatro
  fue.

**Enmienda del 2026-09-28 (U14).** U2 gana `verify_case_link`, idéntica a
`redeem_case_link` salvo que **no sube el contador de canjes**. Canjear es lo que
hace la pantalla una vez al cargar, y su contador existe para que un canje repetido
sea un hecho observable; comprobar es lo que hace cada petición siguiente con la
cookie, y contarlas como canjes convertiría el contador en un contador de clics.
Las dos comparten un único camino interno, así que las cuatro causas de rechazo y
su respuesta única no se pueden separar.

La cookie lleva el propio token: esta unidad no acuña credenciales —emitirlas y
validarlas es de U2— e inventarse aquí una segunda cosa firmada sería un segundo
mecanismo de acceso que nadie pidió.

El canje **busca la aseguradora preguntando a cada una** bajo su propia política de
fila, porque el token no la nombra y eso es deliberado: si la nombrara, quien
tuviera uno sabría de quién es antes de canjearlo. Cuesta tantas consultas como
aseguradoras haya, que son tres y es público.

## C-08 — Llamada de voz: disponibilidad, sesión y límites

**Frontera:** U16 (llamada) y U17 (límites) → consola de llamada.
**Presupuesto:** `availability` en 300 ms; la creación de sesión en 1 s.

```yaml
paths:
  /tenants/{tenant}/voice/availability:
    get:
      summary: Lo que la consola dice antes de pedir el microfono
      security: [{ visitorCookie: [] }]
      responses:
        "200":
          content:
            application/json:
              schema:
                type: object
                required: [available, voice_mode, limits]
                properties:
                  available:   { type: boolean }
                  reason_code: { type: string, nullable: true, enum: [rate_limited_daily, rate_limited_site, budget_exhausted, provider_unavailable] }
                  voice_mode:  { type: string, enum: [primary, fallback], description: "Se decide antes de la llamada y no cambia a mitad (US5.11)" }
                  limits:
                    type: object
                    properties:
                      max_call_seconds:     { type: integer }
                      calls_per_visitor_day: { type: integer }
                      calls_per_site_day:    { type: integer }
                      warn_at_seconds:       { type: integer }
                  resume_until: { type: string, format: date-time, nullable: true }
  /tenants/{tenant}/voice/sessions:
    post:
      summary: Abrir una llamada
      security: [{ visitorCookie: [] }]
      parameters: [{ $ref: "#/components/parameters/IdempotencyKey" }]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [language]
              properties:
                language: { type: string, enum: [es, en] }
                case_id:  { type: string, nullable: true, description: "Retoma de una llamada cortada" }
      responses:
        "201":
          content:
            application/json:
              schema:
                type: object
                required: [call_id, voice_mode, max_call_seconds, transport]
                properties:
                  call_id:          { type: string }
                  case_id:          { type: string, nullable: true }
                  voice_mode:       { type: string, enum: [primary, fallback] }
                  max_call_seconds: { type: integer }
                  transport:
                    type: object
                    description: "Forma pendiente del experimento 1 (C-29); siempre lleva un token de vida corta emitido por esta API"
        "429": { $ref: "#/components/responses/Problem" }
        "503": { $ref: "#/components/responses/Problem" }
  /tenants/{tenant}/voice/sessions/{call_id}:
    delete:
      summary: Cerrar la llamada
      security: [{ visitorCookie: [] }]
      responses:
        "204": { description: Cerrada }
```

**Qué pasa cuando falla.** Límite por visitante, por sitio o duración máxima:
`429` con su `code` y el texto del catálogo en la consola. Techo de gasto:
`503` con `budget_exhausted`; el chat sigue vivo. La voz **nunca** cambia de
modo a mitad de llamada: `voice_mode` se fija al crear la sesión (US5.11).

## C-09 — Evidencia pública

**Frontera:** U22 → cualquier visitante, sin credencial.
**Regla dura:** solo recuentos, totales y distribuciones; nunca un número de
caso ni un identificador de un visitante (regla de `project.md`).

```yaml
paths:
  /public/metrics:
    get:
      summary: Las cinco cifras publicadas con su fecha y su commit (FR10.5)
      security: []
      responses:
        "200":
          content:
            application/json:
              schema:
                type: object
                required: [report_date, commit_sha, completeness, citation_precision, latency_by_language, cost_per_case, cases_by_tenant]
                properties:
                  report_date:        { type: string, format: date }
                  commit_sha:         { type: string }
                  completeness:       { type: number }
                  citation_precision: { type: number }
                  latency_by_language:
                    type: object
                    additionalProperties:
                      type: object
                      properties: { p50_ms: { type: integer }, p95_ms: { type: integer } }
                  cost_per_case:      { type: number }
                  cases_by_tenant:
                    type: object
                    additionalProperties: { type: integer }
  /public/spend:
    get:
      summary: Panel de gasto por caso, proveedor, mes y ventana de 90 dias
      security: []
      responses:
        "200":
          content:
            application/json:
              schema:
                type: object
                required: [window_start, window_end, total_usd, cap_usd, alert_usd, by_provider]
                properties:
                  window_start: { type: string, format: date }
                  window_end:   { type: string, format: date }
                  total_usd:    { type: number }
                  cap_usd:      { type: number }
                  alert_usd:    { type: number }
                  by_provider:
                    type: object
                    additionalProperties: { type: number }
                  unmeasured_entries: { type: integer, description: "Gastos sin precio de lista; se cuentan, nunca valen cero" }
```

**Qué pasa cuando falla.** Si no hay reporte todavía, `200` con
`report_date: null` y las cifras en `null`: la pantalla dice "no medida", nunca
un cero que parezca un resultado (P5).

---

# Familia 2 — Fronteras dentro del proceso

El aplicativo es un solo proceso (ADR-001, ADR-004): estas fronteras son
llamadas en proceso, no llamadas de red. Lo que las hace contratos es que
**solo se cruza por el `api.py` del módulo**, que `import-linter` lo comprueba
en `verify.sh`, y que lo que cruza son modelos propios de solo lectura, nunca
objetos de base de datos (CD-3, CD-11).

Las firmas de abajo son la forma del acuerdo, no código final: Functional
Design de cada unidad las completa con tipos exactos y validaciones.

## C-10 — Sesión de base de datos con la aseguradora fijada

**Dueño:** U2 `tenancy`. **Consumidor:** toda unidad con tablas.
**Regla dura:** ninguna otra unidad abre una conexión ni construye SQL por
concatenación (M9, F9.2).

```python
# tenancy/api.py
@asynccontextmanager
async def session_for(tenant_id: TenantId) -> AsyncIterator[AsyncSession]:
    """Unica via de acceso a la base. Abre transaccion, fija app.tenant_id y
    la cierra. Nadie mas crea engines ni sesiones."""

async def assert_rls_complete() -> RlsReport:
    """Falla si alguna tabla del aplicativo carece de RLS, de FORCE ROW LEVEL
    SECURITY o de politica de aseguradora. Corre en verify.sh y al arrancar."""

def current_tenant() -> TenantId: ...
```

- La variable de sesión se lee siempre como
  `NULLIF(current_setting('app.tenant_id', true), '')`: sin valor, las políticas
  no ven nada en vez de fallar abierto.
- El rol del aplicativo es `NOBYPASSRLS`; las pruebas con testcontainers se
  conectan con ese rol y no con el superusuario, porque con superusuario una
  prueba de aislamiento pasa sin aislamiento.
- **Qué pasa cuando falla:** sin aseguradora fijada, la consulta devuelve vacío
  y se registra un evento; nunca devuelve datos de otra aseguradora.
- **Pendiente:** el aislamiento de las tablas de puntos de control (PA-3) lo
  resuelve Functional Design de U12 entre un pool por aseguradora y un
  checkpointer propio con transacción; en los dos casos con columna de
  aseguradora, RLS y `FORCE ROW LEVEL SECURITY`.

## C-30 — Migraciones de base de datos

**Dueño compuesto:** U2 `tenancy` es dueña de la convención y de la aserción que
la hace cumplir; **cada unidad es dueña de las revisiones de sus propias
tablas**. **Consumidor:** el proceso único al arrancar y `verify.sh`.
Es el punto de integración "Migraciones" de `unit-of-work-dependency.md`: once
unidades crean tablas en la misma base y no hay forma de que cada una decida por
su cuenta.

- **Una sola historia lineal** en `app/backend/migrations/`, con Alembic y SQL
  explícito para todo lo que Alembic no modela (RLS, políticas, `FORCE ROW LEVEL
  SECURITY`), como fija ADR-002.
- **Una revisión por unidad y por cambio**, nombrada con la unidad
  (`u4_case_record_0001_case_tables`). Una sola cabeza: dos cabezas son un
  conflicto que la compuerta rechaza, no algo que se resuelva en producción.
- **Regla dura:** la revisión que crea una tabla del aplicativo trae, **en la
  misma revisión**, su columna `tenant_id`, `ENABLE ROW LEVEL SECURITY`, `FORCE
  ROW LEVEL SECURITY` y su política de aseguradora. No existe una revisión
  posterior "que agrega el aislamiento": entre una y otra habría una ventana con
  datos sin aislar.
- **Reversible:** cada revisión trae su `downgrade()` que funciona; la compuerta
  corre subir, bajar y volver a subir contra una base efímera con la imagen de
  `pgvector`, conectándose con el rol del aplicativo (`NOBYPASSRLS`), no con el
  superusuario.
- **Datos y esquema, separados:** una revisión de esquema no siembra datos. La
  siembra es el comando de aprovisionamiento de U20; el corpus es C-26.

```python
# La comprobacion que sostiene la regla dura, en verify.sh y al arrancar
await assert_rls_complete()   # C-10: falla nombrando la tabla sin RLS o sin politica
```

**Qué pasa cuando falla.** En PostgreSQL el DDL es transaccional: una revisión
que falla a la mitad deja la base como estaba, con su error. Una tabla nueva sin
RLS no llega a la entrega porque `assert_rls_complete` la nombra y la compuerta
se pone roja (M9, F9.1). Una segunda cabeza de migraciones bloquea la entrega
con las dos revisiones en conflicto.

## C-11 — Contrato de borrado de datos de visitante

**Dueño:** U2 declara la definición y el `Protocol`; cada dueño de datos lo
implementa; U20 lo ejecuta cada noche (UG-3).

```python
# tenancy/api.py
VISITOR_DATA = "dato ligado al origen publico o a la clave de navegador de un visitante"

class VisitorDataPurger(Protocol):
    name: str                       # nombre estable; aparece en ResetRun.purged_counts
    async def purge(self, *, older_than: datetime, dry_run: bool = False) -> PurgeResult: ...

@dataclass(frozen=True)
class PurgeResult:
    name: str
    deleted: int
    kept: int                       # lo que se conserva a proposito, como el registro de gasto
```

- El registro de purgadores es **explícito** en la raíz de composición (C-24):
  una lista escrita a mano, no descubrimiento automático.
- Una prueba compara esa lista contra las tablas que guardan datos de visitante
  y falla si alguna no tiene purgador (CD-12).
- **Qué pasa cuando falla:** un purgador que lanza no detiene a los demás; U20
  registra el `ResetRun` como `partial` con el nombre del que falló, y el
  reinicio se vuelve a intentar. Ninguna superficie pública se publica con un
  reinicio en rojo (`team.md`, Deployment).
- El registro de gasto (`SpendEntry`) **sobrevive** al reinicio: aparece como
  `kept`, nunca como `deleted`.

## C-12 — Registro del caso

**Dueño:** U4 `case-record`. **Consumidores:** U8, U9, U10, U11, U12, U14, U19,
U20.

```python
# case_record/api.py
@dataclass(frozen=True)
class CaseView:
    case_id: CaseId
    case_number: str
    record_type: Literal["claim", "coverage_inquiry", "quote_request"]
    state: CaseState                 # enum cerrado
    resolution: Resolution | None
    channel: Literal["voice", "chat"]
    language: Literal["es", "en"]
    policy_ref: PolicyId | None
    completeness: Completeness       # por campo y total
    derivation_reason: str | None

async def create_case(...) -> CaseView: ...
async def get_case(case_id: CaseId) -> CaseView: ...
async def apply_transition(case_id: CaseId, to: CaseState, *, actor: Actor) -> CaseView:
    """Rechaza toda transicion no declarada y deja evento (FR1.4)."""
async def set_field(case_id: CaseId, key: FieldKey, value: str, *,
                    status: Literal["stated", "confirmed"], evidence_turn_id: TurnId) -> None
async def append_turn(case_id: CaseId, turn: InboundTurn | AgentTurn) -> TurnId:
    """Guarda el turno ya redactado (C-13); no acepta texto sin redactar."""
async def record_change(...) -> None
```

- El tipo del texto de la transcripción es `Redacted` (C-13): guardar texto sin
  redactar no compila.
- **Qué pasa cuando falla:** una transición no declarada lanza
  `InvalidTransition` y deja un `CaseChange` con el intento; el llamador no la
  captura para seguir adelante (convención 8b).
- **Pendiente:** el cifrado en reposo de los campos del caso (PA-8) lo fija
  `nfr-requirements` de U4.
- **Corrección del 2026-09-20.** El tipo de registro se escribía aquí
  `coverage_question` y en ADR-005 `coverage_inquiry`, que son dos documentos
  aprobados diciendo cosas distintas. Manda ADR-005, que es donde se decidió el
  conjunto cerrado; este contrato solo lo reexpresaba. Se corrigieron las dos
  apariciones —esta y la del listado de la bandeja (C-05)— durante el diseño
  funcional de U4, que es la unidad dueña de este contrato (decisión FD-U4-5).
  Es un valor de enum y nunca se muestra: la etiqueta que ve una persona sale
  del catálogo de textos.

- **Enmienda del 2026-09-21, durante la generación de código de U4.** Las firmas
  de arriba son las del boceto y divergen de lo construido. Se registran aquí
  con su razón, igual que la corrección FD-U4-5, porque ocho unidades consumen
  este contrato y una divergencia sin registrar es un acuerdo que ya no
  describe nada:

  | Firma del boceto | Firma construida | Razón |
  | --- | --- | --- |
  | `get_case(case_id) -> CaseView` | `get_case(tenant_id, case_id) -> CaseView \| None` | El punto único de sesión de U2 exige la aseguradora explícita; devolver `None` es lo que hace que un caso ajeno y uno inexistente sean indistinguibles (SEC-U4.3) |
  | `set_field(case_id, key, value: str, *, status, evidence_turn_id)` | `set_field(tenant_id, campo: CaseField, *, cipher, actor, channel)` | El valor llega **ya sellado**: un `str` en la firma obligaría a esta superficie a cifrar, y el punto único de cifrado dejaría de ser único. El actor viaja porque todo cambio deja entrada con quién lo hizo (BR5.1) |
  | `apply_transition(case_id, to, *, actor)` | `apply_transition(tenant_id, case_id, to, *, context)` | Las cuatro condiciones de T12 necesitan reloj, clave de navegador y si empezó una decisión. Van juntas en un contexto en vez de seis argumentos sueltos |
  | `create_case(...)` | `create_case(tenant_id, nuevo: NewCase, *, now)` | El reloj entra por parámetro: leerlo dentro haría que los dos bordes de la ventana solo se pudieran probar esperando |
  | `append_turn(case_id, turn)` | `append_turn(tenant_id, draft, text: Redacted)` | El texto va aparte en la firma para que no se pueda colar dentro de un objeto con otras diez cosas sin que nadie mire su tipo |
  | `record_change(...)` | `record_change(tenant_id, cambio, *, cipher)` | El cifrador entra para sellar las copias del valor que van al historial (SEC-U4.8) |

  **Y dos operaciones más de las seis.** `close_case`, porque su rechazo nombra
  el adjunto que faltó y el del ejecutor genérico no podría; y
  `get_case_by_number`, porque BR7.3 se dispara al consultar «por su
  identificador **o por su número**» y solo existía la primera mitad. La segunda
  la encontró la revisión asesora de la generación de código de U4.

**Enmienda del 2026-09-21 (U10).** `case_record/api.py` gana `transcript_of`,
la lectura de la transcripción que usa el puerto de la revisión completa de
U10. Cambio aditivo; la prueba que fija la superficie pública de U4 se
actualizó en el mismo commit.

**Enmienda del 2026-09-21 (U7).** `TransitionContext` gana `derivation_reason`,
que solo cuenta al pasar a `derived`. Las transiciones T3, T5 y T7 exigen un
motivo de derivación, y C-12 no daba forma de declararlo: ningún consumidor
podía derivar un caso por la API. Lo destapó la siembra de casos de U7. Cambio
aditivo en `case_record/rules.py`, con su prueba.

## C-13 — Redacción de datos personales

**Dueño:** U3 `pii-redaction`. **Consumidores:** U4, U5, U10 y todo punto de
salida.
**Regla dura:** una salida sin redacción debe ser imposible por construcción, no
detectable por disciplina (regla de `project.md`).

```python
# compliance/redaction/api.py
Redacted = NewType("Redacted", str)          # el tipo que exigen los puntos de salida

def redact(text: str, *, language: Literal["es", "en"]) -> Redacted:
    """Reemplaza cada dato personal por la etiqueta de su tipo. Sin red y sin
    modelo de lenguaje (ADR-013)."""

def redaction_report(text: str, *, language: Literal["es", "en"]) -> RedactionReport:
    """Conteo por tipo de entidad e idioma; alimenta la medicion, que nunca se
    publica como promedio."""
```

- **Qué pasa cuando falla:** si el detector no puede cargar sus modelos, el
  punto de salida **no** emite texto: responde con la clave de degradación del
  catálogo. Fallar cerrado es la única opción admitida aquí.
- El segundo detector vive en U21 y **no importa este módulo**: su mecanismo es
  distinto a propósito (ADR-013).

**Enmienda del 2026-09-21 (U7).** La prueba de canarios de U7 encontró que "My
name is Megan Hughes." salía sin redactar, porque el modelo de inglés etiqueta
ese nombre como organización. La corrección se hizo hacia adelante, con las
regresiones escritas primero:
- **Autoidentificación:** tras "my name is", "this is", "I'm", "me llamo",
  "soy" y frases parecidas, la secuencia de dos a cuatro palabras con mayúscula
  se tapa como nombre, en los dos idiomas a la vez. La excepción son las
  secuencias con una palabra de organización declarada, como "Auto", "Mutual" o
  "Seguros".
- **VIN:** es un tipo nuevo, `vin`, y se tapa entero.

La firma no cambia; el conjunto de tipos que puede devolver `redact` gana
`vin`. En los conjuntos medidos no bajó ninguna precisión, y el p95 por texto
sube unos 0,3 ms.

## C-14 — Turno: cómo un canal habla con el grafo

**Dueño:** U12 `graph-runtime`. **Consumidores:** U13 (chat), U16 y U18 (voz),
U14 (reanudación tras decisión).
Es el contrato que hace que la conducta sea la misma por los dos canales
(FR2.6), y el que decide CD-7.

```python
# orchestration/api.py
@dataclass(frozen=True)
class InboundTurn:
    tenant_id: TenantId
    session_ref: str                   # sesion de chat o llamada
    case_id: CaseId | None
    text: str                          # texto del asegurado, SIEMPRE como dato delimitado
    language: Literal["es", "en"]
    channel: Literal["voice", "chat"]
    received_at: datetime

TurnEvent = PartialText | FinalText | Waiting | Handoff | TurnError   # union cerrada

async def handle_turn(turn: InboundTurn) -> AsyncIterator[TurnEvent]:
    """Un turno entra, un flujo de eventos sale. Termina SIEMPRE con FinalText,
    Handoff o TurnError."""

async def resume_case(case_id: CaseId, decision: HumanDecision) -> None:
    """Retira la pausa de interrupt() y reanuda desde el punto de control."""

async def preload(case_id: CaseId) -> None:
    """Dispara el ritmo de fondo; el turno nunca lo espera (FR2.3)."""
```

- Los eventos son los mismos que viajan por SSE en C-04: el chat los serializa
  tal cual; la voz convierte `PartialText` y `FinalText` en audio y usa
  `Waiting` como frase de espera.
- Todo evento sale por el **punto único de salida**, que aplica los tres
  controles del turno (C-20), también en los caminos de degradación y error
  (FR7.6).
- El texto del asegurado viaja en un campo del estado tipado, nunca concatenado
  al prompt de sistema (RT-1, RT-2, ADR-020).
- **Qué pasa cuando falla:** el ejecutor común aplica la política del nodo
  (tiempo máximo, un reintento, texto de degradación); si se agota, emite
  `TurnError` con su clave de catálogo y deja el valor distinguible en el caso y
  el evento en la traza. El turno nunca queda abierto en silencio.
- **Presupuesto:** el turno de voz hace una sola llamada al modelo y el trabajo
  de CPU va fuera del bucle de eventos (ADR-004, enmienda del 2026-09-17). El
  presupuesto de latencia de los tres controles del turno es PA-7, en
  `nfr-requirements` de U12.

## C-15 — Contrato de un nodo

**Dueños:** U11 (`intake`), U8 (`policy_verification`), U9 (`decision`) y U10
(`compliance`). **Consumidor:** U12, que compone el estado tipado.

```python
# orchestration/state.py  (el runtime declara la forma; cada nodo la llena)
@dataclass(frozen=True)
class NodeSpec:
    name: Literal["intake", "policy_verification", "decision", "compliance"]
    reads: frozenset[str]              # campos del estado que lee
    writes: frozenset[str]             # conjunto de escritura; dos nodos no comparten ninguno
    rhythm: Literal["turn", "background"]
    timeout_ms: int
    attempts: int                      # politica de fallo como dato
    degraded_copy_key: str
    # Enmienda del 2026-09-27 (FD-U12-2): quien cuenta los reintentos. Aditivo,
    # con "executor" por omision, asi que los cuatro nodos siguen validos sin
    # tocarlos. Solo `policy_verification` declara "node", porque tras agotar sus
    # intentos todavia tiene que escribir su `unverifiable` -- el valor
    # distinguible que nadie mas sabe escribir. Sin este campo, el ejecutor
    # volveria a aplicar `attempts` sobre un nodo que ya los consumio y haria
    # cuatro llamadas al proveedor en vez de dos; y la alternativa era un `if` por
    # nombre de nodo en el ejecutor comun, que es la rama que la convencion 9 del
    # equipo prohibe.
    retries_owned_by: Literal["executor", "node"] = "executor"

class Node(Protocol):
    spec: NodeSpec
    async def run(self, state: NodeInput) -> NodeOutput: ...
        # PURO: devuelve solo su conjunto de escritura. No abre transacciones,
        # no escribe en la base y no captura su propio fallo.
```

- **Pureza obligatoria:** LangGraph vuelve a ejecutar el nodo completo al
  reanudar tras `interrupt()`, así que un nodo que escriba duplicaría efectos.
  La persistencia la hacen los módulos de capacidad con clave idempotente
  (ADR-003, enmienda del 2026-09-17; es el caso de `CoverageAnswer` en C-18).
- Los nodos reciben sus puertos por *closure* desde la raíz de composición y
  **no importan LangGraph** (ADR-001).
- Los cuatro nodos son independientes entre sí: un contrato `independence` de
  `import-linter` lo comprueba.
- **Qué pasa cuando falla:** el nodo deja que la excepción suba; el ejecutor
  común aplica `timeout_ms`, `attempts` y `degraded_copy_key`, y registra el
  `NodeRun` con `error_type` de la taxonomía cerrada.

## C-16 — Puertos de proveedor

**Dueños:** U5 (modelo y embeddings) y U15 (transcripción y síntesis).
**Consumidores:** U7, U8, U10, U11, U15 y U21.
U16 **no** consume este contrato: la llamada de voz usa los adaptadores que U15
construye sobre él, inyectados desde la raíz de composición (C-24). La arista
U16 → U5 del mapa existe por otra razón — eventos de latencia y registro de uso
— y esos son C-23 y C-17. Escribir aquí a U16 invitaría justo a lo que la
convención 5b de `team.md` prohíbe: que el canal de voz importe un SDK o la
fábrica de proveedores fuera de su adaptador.
**Regla dura:** el SDK de un proveedor solo se importa dentro de su adaptador; un
contrato `forbidden` de `import-linter` lo comprueba (ADR-018).

```python
# providers/ports.py
class TextGenerator(Protocol):
    async def generate(self, prompt: Prompt, *, schema: type[BaseModel] | None,
                       use: Use) -> GenerationResult: ...

class Embedder(Protocol):
    async def embed(self, texts: Sequence[str], *, use: Use) -> list[Vector]: ...

class SpeechToText(Protocol):
    def stream(self, audio: AsyncIterator[bytes], *, language: str) -> AsyncIterator[Transcript]: ...

class TextToSpeech(Protocol):
    def synthesize(self, text: Redacted, *, voice: VoiceRef) -> AsyncIterator[bytes]: ...

Use = Literal["voice", "chat", "evals", "operations"]

class ProviderError(Exception):
    kind: Literal["timeout", "rate_limited", "unavailable", "invalid_response"]

class BudgetExhausted(Exception):
    """Saldo o cuota agotados: NO se reintenta y sale una senal explicita de parada."""
```

- Cada uso tiene su **proyecto propio** en el proveedor, no solo su clave,
  porque Gemini limita por proyecto (ADR-018, enmienda del 2026-09-17).
- La salida estructurada es nativa del proveedor y se valida con Pydantic dentro
  del adaptador; un fallo de validación se traduce a `invalid_response`.
- Los prompts son un archivo por nodo e idioma, con identificador y hash; el
  hash va en la traza y en `EvalRun`, y cambiarlo dispara la compuerta.
- **Qué pasa cuando falla:** ningún tipo del proveedor cruza al núcleo. Ante
  `BudgetExhausted` no hay reintento; ante `rate_limited` decide la política del
  nodo, nunca el adaptador.
- **Pendiente:** la forma de la confianza por palabra en streaming (PA-2) y qué
  sustituye el tope por clave donde el proveedor no lo tiene (PA-9).

## C-17 — Gasto, cuotas y techo

**Dueño:** U5 `provider-platform`. **Consumidores:** U13, U16, U17, U22.

```python
# telemetry/spend/api.py
async def record_spend(*, provider: str, use: Use, case_id: CaseId | None,
                       units: Decimal, unit_kind: str) -> None:
    """Calcula el costo con la tabla de precios versionada. Si falta el precio,
    registra 'no medido', nunca cero."""

async def budget_state() -> BudgetState:
    """total_usd, cap_usd, alert_usd y la ventana de 90 dias desde 2026-09-16."""

async def check_quota(scope: QuotaScope, subject_key: str) -> QuotaDecision:
    """Devuelve Allowed o Denied(reason_code). Nunca lanza por una negacion."""

async def reserve_primary_voice(call_id: str) -> VoiceMode:
    """Decide primary o fallback ANTES de la llamada; no cambia a mitad."""
```

- El corte de gasto funciona aunque la observación falle: `UsageBudget` no
  depende de `Telemetry` (justificación del catálogo).
- **Qué pasa cuando falla:** alcanzado el techo, la voz rechaza llamadas nuevas
  con el mensaje del catálogo y el chat sigue vivo (FR10.4). La alerta sale
  antes del techo, no al llegar.
- El techo es **acumulado en la ventana de 90 días**, nunca mensual, y su
  mensaje no menciona el mes (regla de `project.md`).

**Enmienda del 2026-09-21, escrita al construir U5.** La firma de `record_spend`
decía `units: float`, y es un defecto de este documento, no del código. Las
unidades son el otro factor de la multiplicación que produce el costo, y el
dinero de esta unidad se calcula con aritmética decimal exacta: con coma
flotante, sumar veinte fracciones de centavo da un total que depende del orden
en que se sumaron, el techo cortaría en un punto distinto según el orden de las
llamadas, y la cifra publicada dejaría de ser reproducible desde el mismo
commit. La firma dice ahora `Decimal`, que es lo que el código implementa y lo
que el comprobador de tipos exige.

**Segunda enmienda del 2026-09-21.** `BudgetState` tiene **cuatro** estados y no
tres: `ok`, `alerted`, `exhausted` y `unmeasured`. El cuarto rige cuando el
presupuesto público restante no se puede calcular porque la reserva de grabación
que FR3.11 aparta está declarada en minutos y su precio por minuto todavía no
existe en la tabla. La conducta con `unmeasured` es la misma que con
`exhausted` —una llamada facturable se rechaza, porque el corte falla cerrado
para lo que cuesta dinero—, pero el estado publicado dice la verdad: no es que
se haya agotado el presupuesto, es que no se pudo calcular. Colapsar los dos
sería el mismo error que la convención 8c del equipo prohíbe entre "no hay
cláusula" y "no pude verificar", y además convertiría una de las cinco cifras
publicadas en una que miente. El motivo que sale hacia C-08 sigue siendo
`budget_exhausted`: su enum tiene cuatro valores cerrados y ampliarlo es tocar la
superficie que la consola de voz ya consume; la discrepancia queda escrita aquí
y en un comentario del código en vez de heredarse en silencio.

**Tercera enmienda del 2026-09-21.** La firma de `record_spend` que este
documento escribió no alcanza para calcular el costo, y el defecto es de aquí.
La clave de la tabla de precios es la **terna** proveedor–modelo–unidad, así que
sin el modelo no hay precio que buscar; y la fila de gasto guarda además el
identificador exacto del modelo porque BR1.4 prohíbe los alias móviles: un alias
se mueve del lado del proveedor y la cifra publicada deja de poder reproducirse
desde su origen. La firma real añade `model`, y cambia `provider`, `unit_kind` y
la procedencia de `str` a enums cerrados, porque un proveedor escrito a mano que
no coincide con ninguna fila de precios produce "no medido" en vez de un error, y
un hueco silencioso en una cifra publicada es peor que un fallo ruidoso.

`units` admite además `None`, que **no** es cero: una llamada que salió y no
volvió pudo consumir sin que el adaptador tenga recuento que reportar. Cero
afirmaría que no consumió nada, y esa afirmación se sumaría como cierta.

Con eso, la firma implementada es:

```python
async def record_spend(*, provider: ProviderName, model: str, use: Use,
                       units: Decimal | None, unit_kind: UnitKind,
                       case_id: str | None = None, tenant_ref: str | None = None,
                       source: SpendSource = SpendSource.PROVIDER_REPORTED,
                       lane: BudgetLane = BudgetLane.PUBLIC,
                       now: datetime | None = None) -> None: ...
```

Y una consecuencia que los consumidores tienen que conocer: **BR3.1 dice "una
fila por llamada" y una generación deja dos**. El proveedor cobra la entrada y
la salida a precios distintos, y esta entidad lleva una sola clase de unidad por
fila, así que la llamada se reparte en dos filas con la misma procedencia. Quien
cuente llamadas contando filas contará el doble.

## C-18 — Corpus, recuperación y citas verificadas

**Dueño:** U8 `policy-rag`. **Consumidores:** U11, U12, U14, U20.

```python
# policy_rag/api.py
async def retrieve(*, tenant_id: TenantId, policy_id: PolicyId,
                   query: str, k: int) -> list[ClauseHit]:
    """Filtra por aseguradora y por poliza ANTES de ordenar; fusion lexica y
    vectorial por rango reciproco; cierre por relaciones de clausula."""

async def verify(*, case_id: CaseId, turn_id: TurnId, claim: str,
                 clause_ids: Sequence[ClauseId]) -> CoverageOutcome:
    """Existencia, pertenencia al tenant y a la poliza, vigencia, endoso vigente
    que modifique la clausula citada, y respaldo de la afirmacion."""

@dataclass(frozen=True)
class CoverageOutcome:
    outcome: Literal["verified", "rejected", "no_clause_found", "unverifiable"]
    citations: tuple[VerifiedCitation, ...]
    reasons: tuple[str, ...]

async def record_answer(outcome: CoverageOutcome, *, idempotency_key: str) -> AnswerId:
    """Escribe CoverageAnswer. La escritura vive aqui y no en el nodo, porque el
    nodo se vuelve a ejecutar al reanudar (ADR-003, enmienda del 2026-09-17)."""
```

- `no_clause_found` (resultado verificado) y `unverifiable` (fallo) son **dos
  valores distintos** en el estado, en la traza y en el reporte, y nunca se
  colapsan (FR5.5, P2).
- **Qué pasa cuando falla:** una cita sin `verified` bloquea la entrega del
  turno; el turno sale con `Handoff` (`reason_code: unverifiable`), nunca
  inventando cobertura.
- Cambiar el modelo de embeddings reconstruye el índice y pasa la compuerta de
  evaluación (ADR-010).

## C-19 — Motor de reglas

**Dueño:** U9 `rules-decision`. **Consumidores:** U12 (nodo `decision`), U14
(mostrar la regla con sus insumos), U19 (elegibilidad) y U11 (captura).

**Por qué U11 está aquí.** El mapa declara la arista U11 → U9 con esta razón:
"US1.4 y US1.12 se aceptan con las reglas de la aseguradora". No es una llamada
en el turno: la captura **no** evalúa reglas (eso es del nodo `decision`). Es la
otra clase de dependencia que define UG-8 — U11 necesita las reglas reales
cargadas para probarse, porque sus dos criterios terminan en "la categoría es
derivación, con la regla que la exige" (AC1.4.3 y AC1.12.3). De ahí sale una
obligación de contrato que sí es del turno: **la captura tiene que escribir los
campos que las reglas leen**, o la regla no dispara y el criterio falla sin que
nadie sepa por qué. Por eso U9 expone qué campos lee su conjunto de reglas.

```python
# rules/api.py
async def evaluate(case: CaseView, *, ruleset_version: str | None = None) -> RuleEvaluationView:
    """Determinista y sin modelo. Devuelve categoria, reglas disparadas, insumos
    y clave de explicacion del catalogo."""

@dataclass(frozen=True)
class RuleEvaluationView:
    category: Literal["direct_close", "standard_review", "referral"]
    fired_rules: tuple[FiredRule, ...]     # id y version de cada regla
    inputs_snapshot: Mapping[str, str]
    explanation_key: str                   # clave del catalogo, no texto

def required_inputs(*, tenant_id: TenantId,
                    ruleset_version: str | None = None) -> frozenset[FieldKey]:
    """Campos del caso que lee el conjunto de reglas de esa aseguradora.
    U11 los usa para saber que tiene que capturar; una prueba compara este
    conjunto contra los campos que la captura llega a escribir, y falla si una
    regla depende de un campo que nadie captura."""
```

- Ningún cliente de modelo aparece en la cadena de llamadas (FR6.3), y un
  contrato `forbidden` de `import-linter` lo comprueba.
- La política de la agencia (derivar siempre) vive en su archivo de
  configuración, no en una rama de código (FR6.4).
- **Qué pasa cuando falla:** un archivo de reglas inválido impide arrancar con
  esa aseguradora, con el identificador de la regla rota; no se degrada a "sin
  reglas".

**Enmienda del 2026-09-21 (U9, generación de código).** Lo construido difiere
del boceto en tres puntos:

- `evaluate(tenant_id, inputs, *, ruleset_version=None)` en lugar de
  `evaluate(case: CaseView, ...)`: `rules` está por debajo de `case_record` en
  el contrato de capas y no puede importar `CaseView`. El nodo `decision`
  traduce el estado del caso a `inputs`.
- Los campos que leen las reglas son un vocabulario propio del motor
  (`rules/fields.py`), más fino que los bloques de captura: "hay heridos" no es
  lo mismo que "se capturó el bloque de heridos". `required_inputs` devuelve
  esos nombres como `frozenset[str]`.
- La API suma `save_evaluation` y `evaluations_for`, que usa el nodo
  `decision` para guardar sin duplicar al reanudar (ADR-003).

## C-20 — Controles de cumplimiento

**Dueño:** U10 `compliance`. **Consumidores:** U12 (punto único de salida y nodo
`compliance`), U14.

```python
# compliance/controls/api.py
async def guard_output(text: str, *, tenant_id: TenantId, language: str,
                       case_id: CaseId | None) -> GuardResult:
    """Control del turno. Detecta promesa de cobertura, monto, culpa y consejo
    legal, y sustituye por una frase del catalogo. Presupuesto: PA-7."""

async def detect_human_request(text: str) -> bool      # control del turno, cualquier idioma
async def detect_emergency(text: str) -> bool          # control del turno
async def final_review(case_id: CaseId) -> ComplianceReviewView   # al cierre, ritmo de fondo
async def record_disclosure(case_id: CaseId, *, channel: str, language: str) -> None
```

- Dentro del turno corren **solo** esos tres controles baratos, cada uno con su
  presupuesto declarado; la verificación de póliza, las reglas y la revisión
  completa van en el ritmo de fondo (D22).
- **Qué pasa cuando falla:** si la guardia no puede evaluar, el texto **no
  sale**: se emite la clave de degradación. Falla cerrado.

**Enmienda del 2026-09-21 (U10, generación de código).** Lo construido difiere
de la firma de arriba en cambios que exigieron sus propias reglas; la tabla
completa, función por función, está en la cabecera de
`app/backend/src/untangle/compliance/controls/api.py`, que manda sobre este
bloque. En resumen: `guard_output` recibe además `case_number`, `turn` y
`source_key` opcionales (BR1.4, BR1.7 y BR1.8); `final_review` recibe su
petición y un puerto de lectura del caso inyectado por la raíz de composición,
para que `compliance` no importe `case_record`; `record_disclosure` recibe
`tenant_id`, `catalog_key` y `disclosed_at`; y hay dos funciones nuevas,
`detect_identity_question` y `delimit_untrusted` (FD-U10-4). Todos son cambios
de su dueño y ningún consumidor existía todavía.

## C-21 — Catálogo de textos

**Dueño:** U1 `workspace`. **Consumidores:** todas las unidades y la interfaz.

```python
# copy_catalog/api.py
def t(key: CopyKey, *, locale: Literal["es", "en"], **vars: str) -> str: ...
def keys_for(surface: str) -> frozenset[CopyKey]: ...
```

- Ninguna cadena visible se escribe en línea en un nodo, un adaptador o una
  pantalla (convención de `team.md`).
- La interfaz consume un **módulo tipado generado** desde el mismo catálogo, así
  que una clave inexistente es un error de tipos, no un texto vacío en pantalla.
- Los chequeos de paridad EN↔ES y de claves sin consumidor corren en
  `verify.sh`.
- **Qué pasa cuando falla:** una clave faltante en un idioma falla la compuerta;
  en tiempo de ejecución se devuelve la clave misma y se registra el evento,
  nunca una cadena vacía.

## C-22 — Registro de objetivos y conductores de evaluación

**Dueño:** U1 `workspace`. **Consumidores:** cada unidad evaluada, U13 (conductor
de texto), U16 (conductor de audio), U21 (compuertas).

```python
# evals/runner/api.py
def register_targets(unit: str, targets: Sequence[EvalTarget]) -> None: ...

class EvalDriver(Protocol):
    channel: Literal["chat", "voice"]
    async def run_case(self, case: GoldenCase) -> CaseTranscript: ...

def register_driver(driver: EvalDriver) -> None: ...
```

- Los conductores viven en `app/backend/src/untangle/evals/drivers/` e importan
  la interfaz pública del canal; **el código de producción nunca importa
  `untangle.evals`**, y un contrato `forbidden` de `import-linter` lo comprueba
  (UG-4, enmienda del 2026-09-17).
- El corredor **no llama al modelo**: el juez vive en U21.
- **Qué pasa cuando falla:** un caso inestable se marca con su identificador en
  un archivo versionado, deja de contar para la compuerta y se reporta aparte;
  nunca se borra del set (P5).

## C-23 — Telemetría

**Dueño:** U5 `provider-platform`. **Consumidores:** todas.

```python
# telemetry/traces/api.py
def span(name: str, **attrs: str) -> AbstractContextManager[Span]:
    """Convenciones GenAI: modelo, tokens, latencia y costo por turno, nodo y
    proveedor."""

async def trace_summary_for(case_id: CaseId, *, tenant_id: TenantId,
                            visitor_key_hash: str | None) -> TraceSummaryView:
    """Resumen publico; solo se muestra al navegador que lo produjo."""
```

**Enmienda del 2026-09-21, escrita al construir U5.** La firma gana la
aseguradora y recibe el **resumen** de la clave del navegador en vez de la clave.
Las dos razones son de construcción y ninguna es cosmética:

- **`tenant_id`** porque esta superficie abre la sesión de base y la política de
  fila exige la aseguradora antes de que haya nada que comparar. El contrato la
  omitía por abreviatura, no por decisión.
- **`visitor_key_hash`** porque digerir la clave aquí obligaría a importar el
  módulo de acceso del visitante, y ese arrastra el punto único de sesión. Eso
  rompería el contrato de importación `evals-sin-base-de-datos`, que es lo que
  mantiene vivo el camino "del clon al reporte sin base de datos" y con él la
  cifra publicada de NFR21. El resumen lo calcula quien tiene la clave, con la
  única función del proyecto que lo hace; envolverla habría creado dos funciones
  que hoy dan el mismo resumen y mañana pueden dejar de darlo, y ese día ningún
  visitante volvería a ver el suyo.

La asincronía se mantiene tal como el contrato la declaraba.

- Toda exportación pasa por la redacción (C-13) antes de salir.
- **Qué pasa cuando falla:** si el backend de trazas cae, **nada del caso ni del
  gasto se detiene**; se registra la pérdida de trazas y se sigue.

## C-24 — Raíz de composición

**Dueño:** U1 `workspace`. **Consumidores:** toda unidad con rutas, purgas u
objetivos de evaluación.
Es el único lugar que construye adaptadores y fábricas; un contrato `protected`
de `import-linter` lo comprueba (ADR-001).

```python
# Lo que cada modulo expone en su api.py para que la raiz lo monte
def router() -> APIRouter: ...                       # solo modulos con rutas HTTP
def purgers() -> Sequence[VisitorDataPurger]: ...    # solo duenos de datos de visitante
def eval_targets() -> Sequence[EvalTarget]: ...      # solo unidades de la rama evaluada

# server/composition.py
def build_app(settings: Settings) -> FastAPI:
    """Construye adaptadores y puertos, los pasa por closure a los nodos, monta
    los routers y registra purgadores y objetivos. Inyeccion manual, sin
    contenedor."""
```

- La raíz **no importa unidades que todavía no existen**: cada unidad agrega su
  línea cuando se construye.
- Las capacidades y la plataforma no importan FastAPI; solo la raíz y los
  módulos de entrada lo hacen (contrato `forbidden`).
- **Qué pasa cuando falla:** si un módulo declarado no expone `router()`,
  `purgers()` o `eval_targets()` cuando debía, falla al arrancar con el nombre
  del módulo, no en la primera petición.

---

# Familia 3 — Archivos versionados

Cuatro familias de archivos que no son código y que varias unidades leen.
`unit-of-work.md` dejó su forma explícitamente a esta etapa. Regla general
(CD-4): **YAML para lo que escribe una persona, JSON para lo que escribe una
máquina**, y cada familia con su JSON Schema versionado en `app/contracts/schemas/`
y validado en `verify.sh`.

## C-25 — Configuración por aseguradora

**Dueño:** U2 `tenancy`. **Consumidores:** U9 (reglas), U10 (políticas), U12,
U13, U15 y U16 (voz e idioma), U20 (aprovisionamiento).
**Ubicación:** `app/config/tenants/<tenant>/`.

> **Forma del número de póliza (decidido por Miguel el 2026-09-20, aplicado en
> Construcción U2).** Una sola forma en todo el proyecto: `POL-` seguido de seis
> dígitos, **sin iniciales de la aseguradora**. Rige sobre cualquier otra grafía
> que quede en documentos anteriores, incluidas las maquetas refinadas, que
> todavía llevan `SMA-731045`, `SMU-482913` y `KIA-1188-4402`. Tres razones, en
> orden: el visitante **teclea** ese número en el chat y se lo **dice a la voz**
> (FR4.3), así que tiene que leerse sin descifrar nada; `POL` se entiende igual
> en español y en inglés, mientras que `PAP` es jerga de seguros y las iniciales
> ya se contradecían entre sí (`SM` era Stonecroft en la configuración y `SMU`
> era Sunmeadow en las maquetas); y sin iniciales, una **agencia** puede tener
> como ejemplo una póliza emitida por otra aseguradora, que es exactamente su
> modelo de negocio. Consecuencia buscada: dos aseguradoras **pueden** emitir el
> mismo número, que es lo que la prueba de aislamiento de DS-8 existe para
> demostrar; con iniciales esa colisión sería imposible por construcción y la
> prueba no probaría nada. Quien construya pantallas (U6, U14) o genere el
> corpus (U7, U8) usa esta forma y no la de las maquetas.

```yaml
# app/config/tenants/stonecroft/tenant.yaml   (esquema: tenant.schema.json)
config_version: 1              # sube cuando se quita o renombra una clave
tenant_id: stonecroft
display_name: Stonecroft Mutual
kind: carrier                  # carrier | agency
default_language: es
jurisdiction: corvane
quote_enabled: false           # la agente ofrece cotizar solo si esta activo (D4)
example_policy: POL-100042
copy_overrides: []             # claves del catalogo que este tenant reemplaza
voice:
  primary_voice: catalina
  fallback_voice: <pendiente del experimento 1>
  language_default: es
staff:                         # personas de la bandeja (FR9.6); credenciales NO viven aqui
  - principal_id: diana
    role: adjuster
    display_name: Diana
```

```yaml
# app/config/tenants/stonecroft/rules/triage.yaml   (esquema: ruleset.schema.json)
ruleset_version: "2026-09-18"
rules:
  - id: SM-R-003
    version: 1
    when:                      # expresiones sobre campos del caso, sin codigo
      all:
        - field: injuries.any
          equals: true
    then:
      category: referral
      explanation_key: rules.referral.injuries
    tests:                     # cada regla trae su caso (M5); el runner los ejecuta
      - given: { injuries.any: true }
        expect: referral
```

- Las **credenciales no viven en la configuración**: se generan con un guion
  para Miguel, el despliegue local y las pruebas, y nunca se publican (D23).
- Añadir una cuarta aseguradora es añadir una carpeta, sin tocar código
  (FR9.3).
- **Compatibilidad:** una clave nueva llega opcional y con valor por defecto;
  quitar o renombrar una clave sube `config_version` y actualiza las tres
  carpetas en el mismo commit.
- **Qué pasa cuando falla:** una carpeta que no valida contra su esquema impide
  arrancar **esa** aseguradora, con el archivo y la clave rota en el mensaje;
  las demás siguen vivas. Una configuración de voz rota apaga la voz y deja vivo
  el chat (U15).

## C-26 — Corpus y salida del generador

**Dueño:** U7 `synthetic-data`. **Consumidores:** U8 (ingesta), U20
(aprovisionamiento). **Ubicación:** `app/data/`.

```text
app/data/
  manifest.json                       # semilla, version del generador, hashes de cada salida
  tenants/<tenant>/
    forms/<form_id>.json              # formulario base con su estructura y version
    clauses/<form_id>.json            # una clausula por elemento, con encabezado estructural
    clause_relations.json             # endoso_modifica, define, remite_a (ADR-010)
    issued_policies/<policy_id>.json  # poliza emitida con declaraciones y endosos vigentes
    cases/<case_key>.json             # un caso sembrado por estado
  fixtures/ds8_isolation.json         # colisiones a proposito entre aseguradoras
```

```json
{
  "clause_id": "SM-PAP-2026-A.4.b",
  "form_id": "SM-PAP-2026",
  "form_version": "2026.1",
  "clause_key": "A.4.b",
  "part": "Part A — Liability Coverage",
  "language": "es",
  "text": "…texto propio, estructura inspirada, nunca texto de ISO o ACORD…",
  "is_distractor": false,
  "issuer_label": "Stonecroft Mutual"
}
```

- Bytes idénticos con la misma semilla; se regenera **solo con un comando
  explícito** y su salida se commitea (FR11.2).
- El `manifest.json` lleva el hash de contenido de cada archivo: la ingesta de
  U8 lo compara y se niega a ingerir un corpus que no case con su manifiesto.
- **Qué pasa cuando falla:** un chequeo de contenido en `verify.sh` bloquea si
  aparece texto de cláusula de ISO o ACORD (P8, W6); la estructura y la
  numeración sí están permitidas y documentadas.

## C-27 — Casos de golden set, líneas base y reporte

**Dueños:** U1 (formato de caso y del reporte) y U21 (línea base y regresión).
**Consumidores:** U13 y U16 (conductores), U21 (compuertas), U22 (cifras).
**Ubicación:** `app/evals/`.

```yaml
# app/evals/cases/ds2/es/017.yaml      (esquema: golden-case.schema.json)
case_key: DS-2/es/017              # identificador estable; es la moneda de todo el sistema
dataset: DS-2
language: es
channel: chat
tenant: stonecroft
axes: [correcciones, emocion]
script:                            # turnos del asegurado simulado, por reglas e indexado por campo
  - insured: "Choqué ayer en la 80 con la 33, como a las 6 de la tarde"
  - insured: "No, perdón, fue a las 7"
expected_record:
  state: derived
  fields:
    incident.datetime: "2026-09-16T19:00"
expected_verdicts:
  citation_precision: n/a
  out_of_scope: none
  language_adherence: es
```

`app/evals/baselines/v0.json` (esquema: `baseline.schema.json`):

```json
{
  "baseline_id": "v0",
  "run_id": "…",
  "commit_sha": "…",
  "published_at": "2026-10-07",
  "by_case": { "DS-2/es/017": "pass" },
  "by_criterion_language": { "citation_precision": { "es": 0.96, "en": 0.97 } }
}
```

- Un archivo por caso, nunca generados en tiempo de corrida (práctica de
  pruebas).
- El reporte de la corrida es JSON con el mismo vocabulario de identificadores,
  y publica **los dos idiomas lado a lado**, nunca un promedio (FR11.6).
- **Qué pasa cuando falla:** en los conjuntos pequeños, cualquier caso que pase
  a fallar bloquea y exige explicación que **nombre los identificadores**
  (FR11.5). Una compuerta que no se pudo ejecutar se declara "no medida", jamás
  se omite.
- **Pendiente:** el subconjunto declarado para cuando la corrida completa no
  quepa en 10 minutos o en el plan gratuito (PA-11).

## C-28 — Contratos generados y chequeo de deriva

**Dueños:** U6 (esquema) y U1 (comando y compuerta). **Consumidor:** la interfaz
web. **Ubicación:** `app/contracts/`.

```text
app/contracts/
  openapi.json                 # generado desde FastAPI; incluye las uniones de SSE (C-04, C-06)
  schemas/
    tenant.schema.json         # C-25
    ruleset.schema.json        # C-25
    golden-case.schema.json    # C-27
    baseline.schema.json       # C-27
    eval-report.schema.json    # C-27
    manifest.schema.json       # C-26
```

- El cliente de TypeScript se genera con `@hey-api/openapi-ts` en versión exacta
  hacia `app/frontend/src/shared/api/`, y solo desde ahí se importa
  (`eslint-plugin-boundaries`).
- El comando de generación vive en `mise.toml`; `verify.sh` lo corre y después
  `git diff --exit-code`: si el esquema cambió sin regenerar, **la compuerta
  falla** (ADR-002).
- Los JSON Schema se generan desde los modelos Pydantic, no se escriben a mano.
- **Qué pasa cuando falla:** una deriva bloquea la entrega con el nombre del
  archivo que no se regeneró; nunca se arregla editando el archivo generado.

---

# Familia 4 — Fronteras pendientes

## C-29 — Transporte de audio en tiempo real

**Dueño:** U16 `voice-call`. **Consumidor:** navegador del visitante.
**Estado: pendiente del experimento 1** (ADR-009), que elige entre LiveKit
Agents y Pipecat y fija el transporte.

Lo que el contrato ya fija, gane quien gane:

- El token de conexión lo emite **esta** API en C-08, con vida corta y ligado al
  `call_id`; el navegador nunca recibe credenciales del proveedor.
- **No se persiste audio** (NFR19): solo la transcripción redactada.
- La llamada emite los cuatro eventos de latencia a la traza: fin del habla,
  primer audio, parada por interrupción y recuperación tras corte (FR10.2).
- El grafo **no importa nada** de la librería de voz: los complementos de la
  librería envuelven los puertos de C-16 (ADR-018).
- Cortada la llamada, el caso queda `esperando al asegurado` con
  `resume_until`; volver a llamar dentro de la ventana retoma desde el último
  bloque confirmado (FR3.6).

Lo que decide el experimento 1: la forma exacta del objeto `transport` de C-08,
si el proceso de voz es el mismo o uno aparte, y el proveedor de WebRTC.

---

# Reglas de propiedad de los contratos

1. **Cada parte de un contrato tiene un solo dueño.** El dueño es quien escribe
   esa parte, quien la cambia y quien responde cuando se rompe; un consumidor que
   necesita algo distinto lo pide, no lo cambia. La mayoría de los contratos
   tienen una sola unidad dueña. Siete unen dos superficies que no se pueden
   separar sin partir el acuerdo en dos mitades inútiles, y entonces el dueño es
   **compuesto y con el reparto escrito**: C-07 (U2 emite y valida el token, U14
   sirve la ruta y la vista), C-08 (U16 la llamada, U17 los límites y el
   presupuesto), C-15 (cada unidad es dueña del contrato de su nodo; U12 es dueño
   de la forma `NodeSpec`), C-16 (U5 el puerto de modelo y embeddings, U15 los de
   voz), C-25 (U2 el esquema del archivo, y U15 y U16 el significado de su bloque
   `voice`), C-27 (U1 el formato del caso y del reporte, U21 la línea base y la
   regresión) y C-28 (U6 el esquema, U1 el comando y la compuerta). Un dueño
   compuesto sin ese reparto escrito es un contrato incompleto.
2. **Cambios aditivos, libres.** Añadir un campo opcional, un endpoint, un
   `code` de error o un tipo de evento no rompe a nadie: **los consumidores
   ignoran lo que no conocen**, y esa rama por defecto es obligatoria en el
   cliente generado y en cada lector de archivos.
3. **Cambios rompientes, por camino explícito.** En la API HTTP, mientras el
   único consumidor sea la interfaz de este repositorio, el cambio rompiente y la
   interfaz entran en **el mismo commit**, con el cliente regenerado; el día que
   aparezca un consumidor fuera del repositorio se introduce `/api/v2` y la ruta
   sin versión queda congelada (CD-2). En las fronteras dentro del
   proceso, el cambio y todos sus consumidores entran en **el mismo commit**:
   son un solo proceso y un solo repositorio, así que mypy y `import-linter`
   convierten el error en rojo antes de la entrega, no en una sorpresa en
   ejecución. En los archivos versionados, sube el número de versión del esquema
   y se actualizan todas las carpetas en el mismo commit.
4. **El contrato y su artefacto generado viajan juntos.** Cambiar la API sin
   regenerar `openapi.json` y el cliente hace fallar `verify.sh` (C-28).
5. **Nada de contratos por copia.** Ningún módulo redeclara el modelo de otro:
   lo importa de su `api.py`. Un `import-linter` `forbidden` impide importar el
   módulo de tablas de otro.
6. **Lo que cruza es de solo lectura.** Modelos congelados; las referencias
   entre módulos viajan como identificador (CD-3).
7. **Todo contrato dice qué pasa cuando falla.** Un contrato sin su modo de
   fallo declarado está incompleto: es la parte que Construcción implementa
   primero, porque es la que ninguna prueba feliz descubre.
8. **Verificable por herramienta, no por memoria.** Cada regla de este documento
   tiene su comprobación en `verify.sh`: `import-linter` para las direcciones de
   dependencia, `git diff --exit-code` para la deriva de contratos, los JSON
   Schema para los archivos, Schemathesis contra el esquema OpenAPI y la
   aserción de RLS para el aislamiento (práctica de `team.md`: una convención
   que solo vive en la memoria del autor no es una práctica).

# Preguntas abiertas

Ninguna bloquea el inicio de Construcción; cada una bloquea a la unidad que
dice, y todas vienen de la lista que Units Generation pasó a Construcción.

| Contrato | Pregunta | Bloquea |
| --- | --- | --- |
| C-29 | Librería de voz y transporte: la forma exacta del objeto `transport` y si la voz corre en el mismo proceso (experimento 1, ADR-009) | U15 y U16 no empiezan sin su resultado |
| C-16 | Forma de la confianza por palabra de Deepgram en streaming (PA-2) | Functional Design de U15 |
| C-10 | Aislamiento de las tablas de puntos de control: pool por aseguradora o checkpointer propio con transacción (PA-3) | Functional Design de U12 |
| C-01 | Navegadores declarados, con el dato de WebRTC del experimento 1 (PA-4) | `nfr-requirements` de U6 |
| C-08 | Definición exacta del fin del habla, que fija el punto de partida de la latencia (PA-6) | `nfr-requirements` de U16 |
| C-14 | Presupuesto de latencia de los tres controles del turno (PA-7) | `nfr-requirements` de U12 |
| C-12 | Mecanismo de cifrado en reposo de los campos del caso y de los puntos de control (PA-8) | `nfr-requirements` de U4 y U12 |
| C-17 | Qué sustituye el tope por clave donde el proveedor no lo ofrece (PA-9) | `nfr-requirements` de U5 y U15 |
| C-02 | Origen del chequeo periódico y del disparador nocturno, y canal de alertas (PA-10) | Intent `infra`; U6 y U20 dejan los endpoints y el comando |
| C-27 | Subconjunto declarado de la corrida de evaluaciones (PA-11) | `nfr-requirements` de U21 |
