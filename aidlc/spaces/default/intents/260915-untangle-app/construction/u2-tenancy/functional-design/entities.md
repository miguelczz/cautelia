# Entidades — U2 `tenancy`

El modelo de datos de las aseguradoras y la identidad: quién es cada
aseguradora, quién trabaja en su bandeja, qué enlace abre qué caso y qué
navegador es dueño de qué. Es una descripción lógica, independiente de la
tecnología: no dice tipos de base de datos ni nombres de tabla.

**Fuentes consumidas.** `../../../inception/units-generation/unit-of-work.md`
(U2 crea `Tenant`, `StaffPrincipal`, `CaseAccessLink` y `VisitorKey`),
`../../../inception/units-generation/unit-of-work-story-map.md` (US4.11 y
US5.7), `../../../inception/requirements-analysis/requirements.md` (FR8.7,
FR9.1 a FR9.6), `../../../inception/domain-design/components.md` (los atributos
que fija la tabla de propiedad de entidades) y
`../../../inception/contract-design/contract-summary.md` (C-07 enlace firmado,
C-10 sesión con la aseguradora fijada, C-11 borrado de datos de visitante, C-25
configuración por aseguradora, C-30 migraciones).

**Dónde vive cada entidad.** Es la distinción que ordena esta unidad, y no es
cosmética: decide qué cae bajo la aserción de aislamiento y qué no.

| Entidad | Dónde vive | ¿La revisa la aserción de aislamiento? |
| --- | --- | --- |
| `Tenant` | Carpeta de configuración versionada | No: no es una tabla |
| `StaffPrincipal` | Carpeta de configuración versionada | No: no es una tabla |
| `RolePermission` | Tabla de permisos versionada en el repositorio | No: no es una tabla |
| `StaffCredential` | No se guarda: es el contenido firmado de una cookie | No |
| `CaseAccessLink` | Tabla | Sí |
| `VisitorKey` | Tabla | Sí |
| `RlsReport` | No se guarda: es el resultado de la aserción | No |
| `PurgeResult` | No se guarda: es el resultado de un purgador | No |

**Lo que este diseño añade o precisa sobre la lista aprobada en Domain Design**,
cada cosa con la regla que la obliga:

- `VisitorKey` gana `tenant_id` y su identidad pasa a ser la pareja
  (`tenant_id`, `visitor_key_hash`). El catálogo la listaba sin aseguradora, y
  FR9.1 exige que **toda** tabla lleve el identificador de aseguradora con su
  política. Sin ese campo, la clave de navegador sería la única tabla del
  aplicativo fuera de la aserción, y el mismo navegador que visita dos
  demostraciones compartiría fila entre ellas (BR3.5).
- `CaseAccessLink` gana `token_digest` y `redeemed_count`. El primero es lo
  único que se guarda del token; el segundo es el dato que hace auditable la
  decisión Q3 (el enlace se puede canjear más de una vez dentro de su hora).
- `Tenant` recoge los campos que C-25 fija y el catálogo no listaba:
  `quote_enabled`, `example_policy`, `copy_overrides` y el bloque de voz.
- Tres entidades nuevas que el catálogo no nombraba porque no son tablas:
  `RolePermission` (la tabla de permisos que exige la decisión Q4),
  `StaffCredential` (el contenido firmado que AC5.7.1 describe) y `RlsReport`
  (el resultado que C-10 declara para la aserción).

Ninguna contradice el catálogo: lo precisan donde una conducta acordada
necesitaba un dato que no tenía nombre.

## Modelo

```yaml
entities:
  - name: Tenant
    description: >
      Una aseguradora de la demostración. Vive en su carpeta de configuración
      versionada, no en una tabla: añadir una cuarta aseguradora es añadir una
      carpeta y no tocar código (FR9.3). Es la fuente de verdad de todo lo que
      distingue a una aseguradora de otra.
    identifier: [tenant_id]
    attributes:
      - name: tenant_id
        type: string
        required: true
        unique: true
        constraints: >
          Identificador legible en minúsculas, sin espacios (`stonecroft`). Es
          el mismo valor que viaja en la variable de sesión y en la columna de
          cada tabla, así que nunca cambia una vez publicado.
      - name: display_name
        type: string
        required: true
        constraints: El nombre que ve una persona; nunca se deriva del identificador.
      - name: kind
        type: enum
        allowed_values: [carrier, agency]
        required: true
        constraints: >
          Una agencia deriva siempre a la aseguradora que emitió la póliza; una
          aseguradora decide. La diferencia la aplican las reglas de U9 y las
          políticas de U10, no el código de esta unidad.
      - name: default_language
        type: enum
        allowed_values: [es, en]
        required: true
      - name: jurisdiction
        type: string
        required: true
        constraints: Jurisdicción ficticia; hoy siempre `corvane` (FR9.5).
      - name: config_version
        type: integer
        required: true
        default: 1
        constraints: >
          Sube en uno cuando se quita o se renombra una clave. Una clave nueva
          llega opcional y con valor por defecto, y no lo sube (C-25).
      - name: quote_enabled
        type: boolean
        required: true
        default: false
        constraints: La agente ofrece cotizar solo si está activo.
      - name: example_policy
        type: string
        required: true
        constraints: Identificador de la póliza de ejemplo que el chat público muestra.
      - name: copy_overrides
        type: list
        required: false
        constraints: Claves del catálogo de textos que esta aseguradora reemplaza; lista vacía por defecto.
      - name: voice
        type: object
        required: true
        constraints: >
          Voz primaria, voz de reserva e idioma por defecto de la voz. Una
          configuración de voz rota apaga la voz de esa aseguradora y deja vivo
          su chat (BR4.1).
    entity_constraints:
      - Cada carpeta valida contra su esquema antes de que su aseguradora quede disponible; una rota no impide arrancar a las demás (BR4.1).
      - Las tres aseguradoras son Stonecroft Mutual, Sunmeadow Auto y Knotwell Insurance Agency (FR9.5).
      - Ningún `tenant_id` literal existe en el código del aplicativo fuera del cargador y de las fixtures (BR4.2).
    relationships:
      - target: StaffPrincipal
        cardinality: one-to-many
        direction: "Tenant → StaffPrincipal"
        description: Cada aseguradora declara las personas de su bandeja en su propia carpeta.
      - target: CaseAccessLink
        cardinality: one-to-many
        direction: "Tenant → CaseAccessLink"
        description: Todo enlace pertenece a una aseguradora.
      - target: VisitorKey
        cardinality: one-to-many
        direction: "Tenant → VisitorKey"
        description: Toda clave de navegador se registra dentro de la aseguradora donde se usó.

  - name: StaffPrincipal
    description: >
      Una persona que entra a la bandeja de una aseguradora. Vive en la carpeta
      de configuración, junto a su aseguradora. Las credenciales NO viven aquí:
      se emiten con un comando y nunca se publican (D23).
    identifier: [tenant_id, principal_id]
    attributes:
      - name: tenant_id
        type: string
        required: true
        references: Tenant.tenant_id
      - name: principal_id
        type: string
        required: true
        constraints: Identificador legible dentro de su aseguradora (`diana`).
      - name: role
        type: enum
        allowed_values: [adjuster, account_agent]
        required: true
        constraints: >
          Lo que puede hacer cada rol lo decide `RolePermission`, no este campo
          por sí solo (BR2.5).
      - name: display_name
        type: string
        required: true
    entity_constraints:
      - Las tres personas son Diana en Stonecroft, Marcus Webb en Sunmeadow y Priya Raman en Knotwell (FR9.6).
      - Ninguna contraseña, clave ni token aparece en esta entidad ni en su archivo.
    relationships:
      - target: Tenant
        cardinality: many-to-one
        direction: "StaffPrincipal → Tenant"
        description: Una persona pertenece a exactamente una aseguradora.

  - name: RolePermission
    description: >
      Qué acciones puede hacer cada rol. Una sola tabla versionada en el
      repositorio, no en la configuración de cada aseguradora: los permisos no
      son una diferencia entre aseguradoras, y ponerlos ahí dejaría que una se
      conceda a sí misma la aprobación (decisión Q4).
    identifier: [role, action]
    attributes:
      - name: role
        type: enum
        allowed_values: [adjuster, account_agent]
        required: true
      - name: action
        type: enum
        allowed_values: [view_case, list_cases, decide_case, correct_field, send_message]
        required: true
      - name: allowed
        type: boolean
        required: true
    entity_constraints:
      - Una pareja rol-acción que no aparece en la tabla se deniega; no existe un valor por defecto permisivo (BR2.5).
      - Cada fila tiene su caso de prueba; la fila `account_agent` + `decide_case` con `allowed: false` es la que realiza AC5.7.3.
    relationships: []

  - name: StaffCredential
    description: >
      El contenido firmado que identifica a una persona de la bandeja. No se
      guarda en ninguna tabla: viaja en una cookie y se verifica con la firma en
      cada petición. Se emite con un comando, para Miguel, el despliegue local y
      las pruebas.
    identifier: []
    attributes:
      - name: tenant_id
        type: string
        required: true
        references: Tenant.tenant_id
      - name: principal_id
        type: string
        required: true
        references: StaffPrincipal.principal_id
      - name: role
        type: enum
        allowed_values: [adjuster, account_agent]
        required: true
      - name: issued_at
        type: datetime
        required: true
      - name: expires_at
        type: datetime
        required: true
        constraints: Doce horas después de `issued_at` (decisión Q2).
    entity_constraints:
      - Se verifica en cada petición, no solo al entrar (BR2.3).
      - Caducada, con la firma alterada o de otra aseguradora se rechazan con la misma respuesta y sin devolver datos (BR2.4).
    relationships:
      - target: StaffPrincipal
        cardinality: many-to-one
        direction: "StaffCredential → StaffPrincipal"
        description: Toda credencial nombra a una persona declarada en la configuración de su aseguradora.

  - name: CaseAccessLink
    description: >
      El enlace firmado que abre un solo caso a su visitante. Vive en una tabla
      porque hace falta poder revocarlo y borrarlo cada noche; el token en sí
      nunca se guarda en claro.
    identifier: [link_id]
    attributes:
      - name: link_id
        type: string
        required: true
        unique: true
      - name: tenant_id
        type: string
        required: true
        references: Tenant.tenant_id
        constraints: Columna de aislamiento; la tabla lleva su política (BR1.2).
      - name: case_id
        type: string
        required: true
        references: "Case.case_id (propiedad de CaseRecord, U4)"
      - name: token_digest
        type: string
        required: true
        unique: true
        constraints: >
          Resumen del token, no el token. Sirve para encontrar la fila desde el
          token que presenta el visitante; quien lea la tabla no puede
          reconstruir ningún enlace.
      - name: access
        type: enum
        allowed_values: [view_and_decide]
        required: true
        constraints: >
          Abre la vista de su caso y nunca la lista de la aseguradora. Con esta
          credencial, pedir la lista responde como un caso inexistente.
      - name: created_at
        type: datetime
        required: true
      - name: expires_at
        type: datetime
        required: true
        constraints: Una hora después de `created_at` (FR8.7).
      - name: revoked_at
        type: datetime
        required: false
        constraints: Vacío mientras el enlace vale. Una vez puesto, no se quita.
      - name: redeemed_count
        type: integer
        required: true
        default: 0
        constraints: >
          Sube en cada canje. No limita nada: el enlace es reutilizable mientras
          no caduque ni esté revocado (decisión Q3). Existe para que un canje
          repetido sea un hecho observable y no una conjetura.
    entity_constraints:
      - Un enlace abre exactamente un caso; no existe un enlace que abra dos.
      - Caducado, revocado, inválido o de otro caso responden todos igual, sin decir cuál de los cuatro fue (BR3.3).
      - Es dato de visitante: tiene purgador declarado y el reinicio nocturno lo borra (BR3.6).
    relationships:
      - target: Tenant
        cardinality: many-to-one
        direction: "CaseAccessLink → Tenant"
        description: Todo enlace pertenece a la aseguradora del caso que abre.

  - name: VisitorKey
    description: >
      La clave del navegador de un visitante, sin identidad. Limita el chat, la
      consola y los resúmenes de traza a quien los produjo. Se guarda su resumen,
      nunca la clave.
    identifier: [tenant_id, visitor_key_hash]
    attributes:
      - name: tenant_id
        type: string
        required: true
        references: Tenant.tenant_id
        constraints: >
          Columna de aislamiento. El mismo navegador que visita dos
          aseguradoras tiene una fila por cada una, y una no ve la otra (BR3.5).
      - name: visitor_key_hash
        type: string
        required: true
        constraints: Resumen de la clave que viaja en la cookie; la clave en claro no se guarda.
      - name: origin
        type: string
        required: true
        constraints: Origen público desde el que se emitió.
      - name: created_at
        type: datetime
        required: true
      - name: last_seen_at
        type: datetime
        required: true
    entity_constraints:
      - No guarda nada que identifique a una persona: ni nombre, ni correo, ni dirección de red.
      - Es dato de visitante: tiene purgador declarado y el reinicio nocturno lo borra (BR3.6).
    relationships:
      - target: Tenant
        cardinality: many-to-one
        direction: "VisitorKey → Tenant"
        description: Una clave se registra dentro de la aseguradora donde se usó.

  - name: RlsReport
    description: >
      El resultado de la aserción de aislamiento. No se guarda: se devuelve, y
      su contenido es lo que hace roja o verde la compuerta.
    identifier: []
    attributes:
      - name: checked_tables
        type: list
        required: true
        constraints: >
          Los nombres que la base respondió al preguntarle qué tablas tiene el
          esquema del aplicativo, menos las de la lista de exclusión
          (decisión Q1).
      - name: excluded_tables
        type: list
        required: true
        constraints: >
          Cada entrada con su razón escrita. Hoy tiene una sola: la tabla de
          versiones de migraciones, que no guarda datos del aplicativo.
      - name: failures
        type: list
        required: true
        constraints: >
          Una entrada por tabla que falla, con el nombre de la tabla y qué le
          falta de las tres: aislamiento habilitado, aislamiento forzado, o al
          menos una política de aseguradora.
    entity_constraints:
      - Una lista de fallos no vacía hace que la aserción termine con código distinto de cero.
      - El mensaje nombra la tabla y qué le falta; nunca dice solo "falta RLS".
    relationships: []

  - name: PurgeResult
    description: >
      Lo que devuelve un purgador de datos de visitante. No se guarda aquí: U20
      lo recoge en su registro de reinicio.
    identifier: []
    attributes:
      - name: name
        type: string
        required: true
        constraints: Nombre estable del purgador; aparece en el registro del reinicio.
      - name: deleted
        type: integer
        required: true
      - name: kept
        type: integer
        required: true
        constraints: Lo que se conserva a propósito, como el registro de gasto.
    entity_constraints:
      - Un purgador que falla no detiene a los demás; el reinicio queda parcial con el nombre del que falló.
    relationships: []
```

## Resumen

Ocho entidades, de las cuales **solo dos son tablas**: `CaseAccessLink` y
`VisitorKey`. Las demás viven en configuración versionada (`Tenant`,
`StaffPrincipal`, `RolePermission`) o son valores que se devuelven y no se
guardan (`StaffCredential`, `RlsReport`, `PurgeResult`).

Esa proporción es el diseño, no una casualidad. Todo lo que distingue a una
aseguradora de otra vive en archivos que se leen en una revisión de código, y lo
único que llega a la base de datos son las dos cosas que necesitan poder
revocarse y borrarse cada noche. Las dos llevan su columna de aseguradora, de
modo que la aserción de aislamiento las cubre desde el primer día y no hay
ninguna tabla del aplicativo fuera de ella.

`Tenant` es además la primera entidad del proyecto cuya fuente de verdad es una
carpeta y no una fila: es lo que hace que añadir una cuarta aseguradora sea
añadir un directorio y no una migración.
