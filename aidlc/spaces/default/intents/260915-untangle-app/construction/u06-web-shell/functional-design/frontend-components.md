# Componentes de la interfaz — U6 `web-shell`

Los componentes que construye U6: la raíz de la aplicación con sus proveedores,
el marco común de todas las pantallas, el inicio, las páginas de estado y las
primitivas tematizadas. Los componentes de cada capacidad (mensaje, tarjeta de
fuente, consola, bandeja) son de sus unidades y se dibujan dentro de este marco.

Los nombres, estados, teclado y anuncios salen de
`../../../inception/refined-mockups/interaction-spec.md` y del inventario de
`design-system-mapping.md`; aquí se fija cómo se componen y qué recibe cada uno.
Las reglas citadas están en `rules.md`.

## 1. Jerarquía

```text
AppRoot
├── ThemeBootstrap              paso mínimo antes de cargar la aplicación (BR1.2)
├── QueryClientProvider         caché solo en memoria (BR3.5)
├── LocaleProvider              LanguageChoice (BR2.1, BR2.2)
├── ThemeProvider               ResolvedTheme y cambio inmediato (BR1.1, BR1.3)
├── Announcer                   una región cortés y una de alerta (BR7.5)
└── ReadinessGate               ReadinessWatch (functional-spec 2.1)
    ├── StatusPage kind=waking | unavailable
    └── RouterProvider
        └── AppShell
            ├── SkipLink                    primer foco de la página (BR7.4)
            ├── TopBar
            │   ├── BrandLink               "Untangle", vuelve al inicio
            │   ├── SurfaceNav              solo superficies montadas (BR4.1)
            │   ├── LanguageSelector        (BR2.5)
            │   └── ThemeToggle             (BR1.3)
            ├── <main id="content">
            │   ├── HomePage                ruta /
            │   │   ├── HomeIntro           solo con un canal montado (BR4.3)
            │   │   ├── HomeDemoLine        siempre: demostración con pólizas de ejemplo
            │   │   ├── NoChannelsNotice    solo sin canales (BR4.3)
            │   │   ├── HowItWorks          solo con un canal montado
            │   │   ├── InsurerList
            │   │   │   └── InsurerRow ×3
            │   │   │       ├── Monogram
            │   │   │       ├── SamplePolicyCard   (BR4.5)
            │   │   │       └── SurfaceActions     (BR4.1)
            │   │   ├── ComparisonLink      solo si comparison está montada
            │   │   └── WhatYouCanTry       solo con un canal montado
            │   ├── StatusRoutes            /status/* → StatusPage (BR5.5)
            │   └── NotFound                cualquier otra ruta → StatusPage not_found
            └── SiteFooter                  enlaces externos solo configurados (BR4.4)
```

`DemoNotice` también es de U6, pero no aparece en el inicio: lo usan las
pantallas de canal (chat, consola, comparación, vista por enlace), que lo
reciben ya construido.

## 2. Componentes

### AppRoot y proveedores

| Pieza | Estado que tiene | De dónde lo saca | Qué ofrece a los hijos |
| --- | --- | --- | --- |
| `ThemeBootstrap` | Ninguno | `ThemePreference` y la preferencia del dispositivo | El atributo de modo del documento, antes del primer pintado |
| `ThemeProvider` | `ResolvedTheme` | `ThemeBootstrap` | `useTheme()`: modo, origen y `setMode` |
| `LocaleProvider` | `LanguageChoice` | Ruta (aseguradora), navegador y selector | `useLocale()` y `t(clave)` tipado sobre el catálogo |
| `QueryClientProvider` | Caché en memoria | — | Datos del servidor; ninguna capa persistente (BR3.5) |
| `Announcer` | Cola de anuncios | Llamadas de los componentes | `announce(texto, "status" | "alert")`; lo transmitido se anuncia al terminar |
| `ReadinessGate` | `ReadinessWatch` | `GET /api/health/ready` | Dibuja el enrutador solo en `ready` |

### TopBar

| Prop | Tipo | Requerido | Por defecto | Descripción |
| --- | --- | --- | --- | --- |
| `surfaces` | lista de `surface_id` | sí | — | Superficies públicas montadas, de `SiteDirectory` |
| `tenant` | `TenantPresentation` o nulo | no | nulo | Si la página es de una aseguradora, su acento para el foco y el enlace activo |

- Escritorio: una fila con marca, navegación, idioma y modo. Teléfono: marca y
  menú; idioma y modo quedan visibles sin abrir el menú, como en M1.
- La navegación usa las palabras de U-03 ("Resultados medidos", "Costo de la
  demo", "Cómo está hecho") y solo muestra las que apuntan a algo montado.
- Rol de navegación con nombre; el enlace activo se marca también con
  `aria-current`, no solo con color (BR7.6).

### LanguageSelector y ThemeToggle

Tal como los especifica `interaction-spec.md`: grupo de dos botones con
`aria-pressed`, textos completos ("Español", "English", "Claro", "Oscuro"),
flechas entre opciones, foco que se queda, cambio de modo sin transición y un
solo anuncio al cambiar de idioma. En teléfono, el selector de idioma es un
botón compacto con el código del idioma y nombre accesible completo.

### HomePage

| Estado | Qué se ve | Disparador |
| --- | --- | --- |
| Cargando | Título de la página y esqueleto de las tres filas | Petición de `GET /api/site` en curso |
| Sin canales | `HomeDemoLine`, `NoChannelsNotice` y las tres filas sin botones de canal | `surfaces` sin `chat` ni `voice_console` |
| Con canales | Título, `HomeDemoLine`, "Cómo funciona", filas con las acciones montadas, "Qué puedes probar" | `surfaces` con al menos un canal |
| Error | Mensaje del catálogo según BR3.2 y "Reintentar" | `GET /api/site` falla |

- `NoChannelsNotice` es una sola línea del catálogo (`home.no_channels`); no es
  una alerta ni una región en vivo.
- `HomeDemoLine` dice que es una demostración con aseguradoras ficticias y
  pólizas de ejemplo, y nada más. La segunda mitad de la frase de M1, "los datos
  se borran cada noche", la agrega U20 cuando el reinicio nocturno exista: hasta
  entonces sería prometer algo no construido (BR4.1).
- "Cómo funciona" es una secuencia real y por eso numerada (U-01); cada paso
  aparece solo si su superficie existe.

### InsurerRow

| Prop | Tipo | Requerido | Descripción |
| --- | --- | --- | --- |
| `tenant` | `TenantPresentation` | sí | Datos y marca de la aseguradora |
| `surfaces` | lista de `surface_id` | sí | Para dibujar solo sus acciones montadas |

- Fila, no tarjeta: las tres aseguradoras muestran información distinta
  (carácter, póliza, emisora), como pide M1.
- `Monogram` dibuja la forma `arch`, `horizon` o `rings` con el acento del modo
  actual; es decorativo y está oculto para el lector de pantalla, porque el
  nombre va escrito al lado (BR7.7).
- Las acciones ("Abrir chat", "Llamar") son botones de al menos 44 × 44 con el
  acento de la aseguradora como fondo y el texto que pide el contraste de cada
  modo (BR1.6, BR7.3).

### SamplePolicyCard

| Prop | Tipo | Requerido | Descripción |
| --- | --- | --- | --- |
| `policy` | texto | sí | Número de póliza de ejemplo, forma `POL-` y seis dígitos |
| `holder` | texto | no | Titular, cuando exista en el corpus (U7) |
| `vehicle` | texto | no | Vehículo, cuando exista en el corpus (U7) |

Lo que no llega no se dibuja: sin `holder` ni `vehicle`, la tarjeta muestra el
número y la ayuda "Cuando la agente te pida la póliza, usa este número" (U-02,
BR4.2). El número va en la fuente de datos, completo, y un lector de pantalla lo
lee carácter a carácter.

### StatusPage

| Prop | Tipo | Requerido | Descripción |
| --- | --- | --- | --- |
| `kind` | `StatusPageKind` | sí | Uno de los siete tipos |
| `onRetry` | función | no | Solo en `unavailable` y `service_unavailable` |

| Tipo | Título y cuerpo | Acción | Foco inicial |
| --- | --- | --- | --- |
| `waking` | "La demo está despertando…"; hilo decorativo o texto con movimiento reducido (BR5.7) | Se actualiza sola | Título |
| `unavailable` | "La demo no está disponible ahora." | Enlaces configurados (BR4.4) y "Reintentar" | Título |
| `link_invalid` | Mismo texto para enlace manipulado y caso inexistente (BR5.6) | Ir al inicio | Título |
| `link_expired` | El caso sigue guardado hasta el reinicio nocturno y cómo pedir otro | Volver a la conversación | Título |
| `data_reset` | "Los datos de la demostración se borran cada noche." | Empezar de nuevo | Título |
| `not_found` | "No encontramos esta página.", sin nombres de aseguradoras | Ir al inicio | Título |
| `service_unavailable` | Sin detalles técnicos | Reintentar | Título |

El título de cada página de estado es un encabezado de primer nivel que recibe
el foco al aparecer, para que el lector de pantalla diga el estado sin buscarlo.

### Primitivas

`Button`, `Input`, `Textarea`, `Select`, `Tag`, `Disclosure`, `Tabs`,
`Skeleton` e `InlineAlert` se generan con shadcn/ui sobre sus primitivas
accesibles y **ninguna se entrega con su aspecto por defecto**: todas toman sus
colores, radios, tipografía, foco y movimiento de los tokens (BR1.5). Cada una
trae sus siete estados (por defecto, encima, foco, activo, deshabilitado,
cargando y error) y mide al menos 44 × 44 cuando es táctil.

## 3. Flujos de interacción

| Flujo | Componentes | Especificación |
| --- | --- | --- |
| Primera carga | `ThemeBootstrap`, `LocaleProvider`, `ReadinessGate`, `AppShell` | `functional-spec.md` F1 |
| Inicio | `HomePage`, `InsurerRow`, `SamplePolicyCard` | F2 |
| Cambiar de modo | `ThemeToggle`, `ThemeProvider` | F3 |
| Cambiar de idioma | `LanguageSelector`, `LocaleProvider`, `Announcer` | F4 |
| Error del servidor | Cliente de la API, `InlineAlert` o `StatusPage` | F5 |
| Espera y no disponible | `ReadinessGate`, `StatusPage` | Sección 2.1 |

## 4. Validación de formularios

U6 no tiene formularios propios. Las primitivas de entrada traen el patrón que
usarán las demás unidades: la etiqueta visible siempre, el error debajo del
campo con texto del catálogo y asociado al campo, y el foco que va al primer
campo con error al enviar.

## 5. Puntos de integración con la API

| Ruta | Quién la usa | Credencial | Respuesta | Error |
| --- | --- | --- | --- | --- |
| `GET /api/health/ready` | `ReadinessGate` | Ninguna | `HealthReport` | 503 con C-01 → `waking` |
| `GET /api/site` | `HomePage`, `TopBar`, `SiteFooter` | Ninguna | `SiteDirectory` | C-01 → F5 |

Las dos entran al esquema OpenAPI y se llaman solo con el cliente generado
(BR3.1). La interfaz de activación no es una ruta HTTP: es una llamada en
proceso que usan el chat y la bandeja desde el servidor, porque el hito lo
decide el servidor al procesar el turno y no el navegador.
