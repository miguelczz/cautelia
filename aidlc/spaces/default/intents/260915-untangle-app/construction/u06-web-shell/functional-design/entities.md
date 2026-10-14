# Entidades — U6 `web-shell`

U6 casi no tiene dominio propio: tiene **el marco**. Lo que define existe para
que cada pantalla que llegue después nazca con el modo que eligió la persona, en
su idioma, con los errores dichos en palabras, sin prometer lo que no está
construido y revisada por el arnés de accesibilidad antes de publicarse.

Por eso la mayoría de las entidades **no se guardan en ninguna base**. Viven en
el navegador (la preferencia de modo y el idioma elegido), en la configuración
versionada de cada aseguradora (su presentación y su marca), en el proceso (el
registro de superficies montadas y el reporte de salud) o en el repositorio (el
registro de pantallas que recorre el arnés). Solo dos se guardan, y las dos son
de la telemetría de activación: el avance de cada sesión, que es dato de
visitante y se borra cada noche, y el conteo diario por aseguradora e hito, que
no apunta a nadie (Q3).

## Entidades

El bloque siguiente es la fuente de verdad; el resumen que va después se deriva
de él.

```yaml
entities:

  # --- En el navegador --------------------------------------------------------

  - name: ThemePreference
    description: >
      El modo que eligió la persona en este navegador. Es una preferencia de
      apariencia, no un dato de caso: puede sobrevivir a la sesión. Sin elección
      guardada, manda la preferencia del dispositivo.
    identifier: storage_key
    stored_in: "Almacenamiento local del navegador"
    attributes:
      - name: storage_key
        type: string
        required: true
        unique: true
        constraint: "Una sola clave fija para todo el aplicativo; ninguna pantalla guarda la suya."
      - name: value
        type: ThemeMode
        required: false
        allowed_values: [light, dark]
        default: null
        constraint: >
          Nulo significa "seguir al dispositivo". Cualquier otro valor leído
          (corrupto, de otra versión) se trata como nulo y no produce error
          visible (BR1.4).
    relationships: []

  - name: ResolvedTheme
    description: >
      El modo que efectivamente se pinta: el guardado si existe, si no el del
      dispositivo. Se calcula antes del primer pintado y se aplica a todo el
      documento a la vez.
    identifier: none
    stored_in: "Atributo del documento, en memoria"
    attributes:
      - name: mode
        type: ThemeMode
        required: true
        allowed_values: [light, dark]
      - name: source
        type: enum
        required: true
        allowed_values: [user, device]
    relationships:
      - target: ThemePreference
        cardinality: "0..1 a 1"
        direction: "ResolvedTheme se deriva de ThemePreference"

  - name: LanguageChoice
    description: >
      El idioma de la página. En las páginas sin aseguradora (inicio, estados)
      se inicia con el del dispositivo si empieza por español, si no en inglés
      (Q2). En las páginas de una aseguradora se inicia con su idioma por
      defecto. Dura la pestaña; solo se recuerda entre visitas donde el
      componente lo pide (`persist`, la bandeja).
    identifier: none
    stored_in: "Estado de la pestaña; almacenamiento local solo con persist"
    attributes:
      - name: locale
        type: Locale
        required: true
        allowed_values: [es, en]
      - name: source
        type: enum
        required: true
        allowed_values: [device, tenant_default, user, persisted]
    relationships:
      - target: TenantPresentation
        cardinality: "0..1 a 1"
        direction: "En páginas de aseguradora, LanguageChoice parte de su default_language"

  - name: ReadinessWatch
    description: >
      La espera de que el proceso esté listo, vista desde la interfaz. Es la
      máquina de estados de la página "la demo está despertando" (AC5.16.4); la
      transición está en `functional-spec.md`, sección 2.
    identifier: none
    stored_in: "Memoria de la pestaña"
    attributes:
      - name: state
        type: enum
        required: true
        allowed_values: [checking, ready, waking, unavailable]
      - name: started_at
        type: timestamp
        required: true
      - name: attempts
        type: integer
        required: true
        min: 0
      - name: requested_route
        type: string
        required: true
        constraint: "La ruta que pidió la persona, para devolverla ahí al despertar."
    relationships: []

  - name: ProblemView
    description: >
      Un error del servidor tal como lo ve la persona: solo una clave del
      catálogo y, si aplica, cuándo reintentar. Nunca el título ni el detalle
      técnico del error (C-01).
    identifier: none
    stored_in: "Memoria de la pestaña"
    attributes:
      - name: code
        type: ProblemCode
        required: true
        constraint: >
          Uno de los códigos cerrados de C-01, o `unknown` cuando el servidor
          manda uno que esta versión de la interfaz no conoce (BR3.3).
      - name: copy_key
        type: CopyKey
        required: true
        constraint: "Resuelta por una tabla única código → clave; la rama por defecto es obligatoria."
      - name: retry_after_s
        type: integer
        required: false
        min: 0
    relationships: []

  # --- En la configuración versionada de cada aseguradora --------------------

  - name: TenantPresentation
    description: >
      Lo que el inicio y las cabeceras muestran de una aseguradora. Sale entero
      de `app/config/tenants/<aseguradora>/tenant.yaml` (C-25): el código no
      tiene ninguna condición por aseguradora. Lo que la configuración todavía
      no trae —titular y vehículo de la póliza de ejemplo, que llegan con el
      corpus de U7— no se muestra ni se inventa (BR4.2).
    identifier: tenant_id
    stored_in: "Configuración versionada (C-25), servida por la API"
    attributes:
      - name: tenant_id
        type: TenantId
        required: true
        unique: true
      - name: display_name
        type: string
        required: true
      - name: kind
        type: enum
        required: true
        allowed_values: [carrier, agency]
      - name: default_language
        type: Locale
        required: true
        allowed_values: [es, en]
      - name: character_key
        type: CopyKey
        required: true
        constraint: "Clave del catálogo con el carácter de la aseguradora, en los dos idiomas."
      - name: example_policy
        type: string
        required: true
        constraint: "Forma `POL-` y seis dígitos (C-25, decisión del 2026-09-20)."
      - name: brand
        type: TenantBrand
        required: true
    relationships:
      - target: TenantBrand
        cardinality: "1 a 1"
        direction: "TenantPresentation contiene TenantBrand"

  - name: TenantBrand
    description: >
      La marca mínima de una aseguradora: su acento en cada modo y su
      monograma. Es un agregado **aditivo** a `tenant.yaml` (C-25 lo permite sin
      subir `config_version`), con su campo en el esquema JSON.
    identifier: none
    stored_in: "Configuración versionada (C-25)"
    attributes:
      - name: accent
        type: color
        required: true
        constraint: "Acento para el modo claro; con texto blanco encima pasa 4,5:1 (BR1.6)."
      - name: accent_on_dark
        type: color
        required: true
        constraint: "Variante para el modo oscuro; con la tinta #0B0B12 encima pasa 4,5:1."
      - name: monogram
        type: enum
        required: true
        allowed_values: [arch, horizon, rings]
        constraint: >
          Nombre de una forma geométrica que dibuja la interfaz. La
          configuración elige la forma; el código no sabe qué aseguradora la usa.
    relationships: []

  # --- En el proceso ----------------------------------------------------------

  - name: SurfaceSpec
    description: >
      Una superficie del aplicativo que una unidad monta en la raíz de
      composición: el chat, la consola de voz, la comparación, la bandeja, la
      vista por enlace, los dos paneles y la cotización. Lo que no está montado
      no existe para la interfaz ni para el chequeo periódico (Q1).
    identifier: surface_id
    stored_in: "Registro de módulos de la raíz de composición (C-24), en memoria del proceso"
    attributes:
      - name: surface_id
        type: enum
        required: true
        unique: true
        allowed_values: [chat, voice_console, comparison, inbox, case_link, metrics_panel, spend_panel]
        constraint: >
          Lista cerrada. La cotización no es una superficie: vive dentro del
          chat y de la bandeja (M12).
      - name: owning_unit
        type: string
        required: true
        constraint: "La unidad que la monta; sirve para leer el reporte sin adivinar."
      - name: public
        type: boolean
        required: true
        constraint: "Si la ve un visitante sin credencial. La bandeja con credencial no es pública."
      - name: per_tenant
        type: boolean
        required: true
      - name: probe
        type: SurfaceProbe
        required: true
        constraint: "Toda superficie montada declara su sonda; montar una sin sonda falla al arrancar (BR5.2)."
    relationships:
      - target: SurfaceProbeResult
        cardinality: "1 a 0..1 por reporte"
        direction: "SurfaceSpec produce SurfaceProbeResult"

  - name: SurfaceProbe
    description: >
      La comprobación barata de que una superficie responde. No llama al
      modelo, ni a la voz, ni a ningún proveedor, y no consume los límites de
      los visitantes (AC5.16.1).
    identifier: none
    stored_in: "Código de la unidad dueña de la superficie"
    attributes:
      - name: timeout_ms
        type: integer
        required: true
        min: 1
        max: 500
        constraint: "La suma de todas cabe en el presupuesto de 1 s de la salud (C-02)."
    relationships: []

  - name: SurfaceProbeResult
    description: Lo que devolvió una sonda en un reporte de salud.
    identifier: none
    stored_in: "Respuesta HTTP; no se guarda"
    attributes:
      - name: surface_id
        type: enum
        required: true
      - name: status
        type: enum
        required: true
        allowed_values: [ok, down]
      - name: duration_ms
        type: integer
        required: true
        min: 0
    relationships: []

  - name: HealthReport
    description: >
      La respuesta de salud del proceso (C-02). `live` dice que el proceso
      responde; `ready` dice que puede atender: base de datos, configuración de
      aseguradoras cargada y superficies montadas.
    identifier: none
    stored_in: "Respuesta HTTP; no se guarda"
    attributes:
      - name: status
        type: enum
        required: true
        allowed_values: [ready]
        constraint: "Solo en 200. Un proceso no listo responde 503 con el error de C-01."
      - name: version
        type: string
        required: true
        constraint: "El commit que corre."
      - name: checks.database
        type: enum
        required: true
        allowed_values: [ok, degraded, down]
      - name: checks.tenants
        type: integer
        required: true
        min: 0
      - name: checks.surfaces
        type: "map surface_id → SurfaceProbeResult"
        required: true
        constraint: "Aditivo a C-02. Vacío cuando no hay ninguna superficie montada, nunca con valores inventados."
      - name: checks.providers
        type: "objeto con priced_units (entero) y uses_with_key (lista de usos)"
        required: true
        constraint: >
          Aditivo a C-02. Son los indicadores de diagnóstico que U1 y U5
          publicaban en `/health`: nombres de uso y un conteo, nunca una clave.
          No vuelven no apto el proceso (FD-U6-6).
    relationships:
      - target: SurfaceProbeResult
        cardinality: "1 a 0..n"
        direction: "HealthReport contiene SurfaceProbeResult"

  - name: SiteDirectory
    description: >
      Lo que el inicio necesita para dibujarse: las aseguradoras, las
      superficies públicas montadas y los enlaces externos configurados.
    identifier: none
    stored_in: "Respuesta HTTP; no se guarda"
    attributes:
      - name: tenants
        type: "list TenantPresentation"
        required: true
      - name: surfaces
        type: "list surface_id"
        required: true
        constraint: "Solo las públicas y montadas (BR4.1)."
      - name: links.readme_url
        type: url
        required: false
        constraint: "Solo si está configurada con una dirección pública; si no, no aparece (BR4.4)."
      - name: links.video_url
        type: url
        required: false
    relationships:
      - target: TenantPresentation
        cardinality: "1 a 3"
        direction: "SiteDirectory lista TenantPresentation"

  - name: StatusPageKind
    description: >
      Los siete tipos de página de estado de la maqueta M11, con una sola
      plantilla (título, explicación, una acción).
    identifier: kind
    stored_in: "Código de la interfaz y catálogo de textos"
    attributes:
      - name: kind
        type: enum
        required: true
        unique: true
        allowed_values: [waking, unavailable, link_invalid, link_expired, data_reset, not_found, service_unavailable]
      - name: title_key
        type: CopyKey
        required: true
      - name: body_key
        type: CopyKey
        required: true
      - name: action
        type: enum
        required: true
        allowed_values: [auto_refresh, external_links, go_home, back_to_conversation, start_over, retry]
    relationships: []

  - name: SecurityHeaderSet
    description: >
      Las cabeceras de seguridad que lleva toda respuesta del proceso, de la API
      y de los estáticos. El valor exacto de la política de seguridad de
      contenido lo fija NFR Design (ADR-002); aquí se fija que el conjunto es
      uno solo y que ninguna respuesta sale sin él.
    identifier: none
    stored_in: "Configuración del proceso servido"
    attributes:
      - name: headers
        type: "map nombre → valor"
        required: true
        constraint: >
          Como mínimo: política de seguridad de contenido, prohibición de
          adivinar el tipo, política de referencia, prohibición de marcos y
          transporte estricto cuando se sirve por HTTPS.
    relationships: []

  # --- En el repositorio ------------------------------------------------------

  - name: VisitableRoute
    description: >
      Una pantalla a la que puede llegar una persona, registrada para que el
      arnés de accesibilidad la recorra. Cada unidad con pantallas agrega las
      suyas; una ruta de la interfaz que no está en el registro hace fallar la
      comprobación (BR7.1).
    identifier: route_id
    stored_in: "Registro versionado junto a las pruebas de extremo a extremo"
    attributes:
      - name: route_id
        type: string
        required: true
        unique: true
      - name: path
        type: string
        required: true
        constraint: "Con los parámetros de ejemplo ya puestos, para que el arnés la abra sin adivinar."
      - name: owning_unit
        type: string
        required: true
      - name: audience
        type: enum
        required: true
        allowed_values: [visitor, staff]
        constraint: >
          La línea base de AC1.33 obliga en las pantallas de visitante; las de
          la bandeja con credencial se recorren y se reportan, sin bloquear
          (D25).
      - name: needs_seed
        type: string
        required: false
        constraint: "El estado sembrado que necesita, por ejemplo un caso cerrado para la vista por enlace."
    relationships: []

  # --- En la base de datos ----------------------------------------------------

  - name: ActivationProgress
    description: >
      Qué hitos alcanzó ya una sesión, para contar cada uno una sola vez. La
      sesión es la clave del navegador de U2 (Q3). Es **dato de visitante**:
      lleva la marca, su política de aseguradora y su borrado en el reinicio
      nocturno (UG-3).
    identifier: "(tenant_id, visitor_key_hash, milestone)"
    stored_in: "Base de datos, tabla con aislamiento por aseguradora"
    attributes:
      - name: tenant_id
        type: TenantId
        required: true
        references: "Tenant (U2 `tenancy`)"
      - name: visitor_key_hash
        type: string
        required: true
        references: "VisitorKey (U2 `tenancy`)"
        constraint: "El resumen que U2 ya guarda, nunca la clave. Nada que identifique a una persona."
      - name: milestone
        type: ActivationMilestone
        required: true
        allowed_values: [first_message, third_turn, loop_closed]
      - name: reached_at
        type: timestamp
        required: true
    constraints:
      - "Única por (tenant_id, visitor_key_hash, milestone): el segundo intento de registrar el mismo hito no cuenta (BR8.1)."
      - "Sin columnas de texto libre."
    relationships:
      - target: ActivationDaily
        cardinality: "n a 1"
        direction: "Cada fila nueva suma uno en el conteo de su día, aseguradora e hito"

  - name: ActivationDaily
    description: >
      El conteo que sí sobrevive a la noche: cuántas sesiones alcanzaron cada
      hito, por día y por aseguradora. No apunta a ninguna persona ni a ningún
      navegador (BR8.2).
    identifier: "(tenant_id, day, milestone)"
    stored_in: "Base de datos, tabla con aislamiento por aseguradora"
    attributes:
      - name: tenant_id
        type: TenantId
        required: true
        references: "Tenant (U2 `tenancy`)"
      - name: day
        type: date
        required: true
        constraint: "Día en UTC."
      - name: milestone
        type: ActivationMilestone
        required: true
        allowed_values: [first_message, third_turn, loop_closed]
      - name: count
        type: integer
        required: true
        min: 0
    constraints:
      - "Única por (tenant_id, day, milestone)."
      - "Sin columnas de texto libre ni de dato personal; no lleva la marca de dato de visitante."
    relationships: []
```

## Resumen

| Entidad | Dónde vive | Se guarda | Para qué |
| --- | --- | --- | --- |
| `ThemePreference` | Navegador | Sí, como preferencia | Recordar claro u oscuro |
| `ResolvedTheme` | Documento | No | Pintar el modo correcto antes del primer cuadro |
| `LanguageChoice` | Pestaña | Solo con `persist` | Idioma de la página |
| `ReadinessWatch` | Pestaña | No | Máquina de estados de "despertando" |
| `ProblemView` | Pestaña | No | Error dicho por el catálogo, nunca en crudo |
| `TenantPresentation` | Configuración | Versionada | Aseguradora en el inicio y las cabeceras |
| `TenantBrand` | Configuración | Versionada | Acento por modo y monograma |
| `SurfaceSpec` | Proceso | No | Qué superficies existen de verdad |
| `SurfaceProbe` | Código de la dueña | No | Comprobación barata de cada superficie |
| `SurfaceProbeResult` | Respuesta | No | Resultado de una sonda |
| `HealthReport` | Respuesta | No | Vivo y listo (C-02) |
| `SiteDirectory` | Respuesta | No | Datos del inicio |
| `StatusPageKind` | Interfaz | No | Siete páginas de estado, una plantilla |
| `SecurityHeaderSet` | Proceso | No | Cabeceras en toda respuesta |
| `VisitableRoute` | Repositorio | Versionada | Pantallas que recorre el arnés |
| `ActivationProgress` | Base | Sí, dato de visitante | Contar cada hito una vez por sesión |
| `ActivationDaily` | Base | Sí | El conteo publicable |

Dos tablas nuevas, las dos con aislamiento por aseguradora. Solo una es dato de
visitante y entra al registro de borrado de la raíz de composición.
