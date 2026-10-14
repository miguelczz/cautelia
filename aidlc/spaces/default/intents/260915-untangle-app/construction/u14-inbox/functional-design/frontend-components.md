# Componentes de interfaz — U14 `inbox`

Tres pantallas y un flujo de eventos. Dos son de trabajo —la cola y la vista de
caso, para quien entra con credencial— y la tercera es del visitante que abre su
propio caso con un enlace.

**Las de trabajo y la del visitante no son la misma pantalla con un interruptor**
(decisión de Miguel, 2026-09-28). Comparten los bloques de evidencia y nada más:
`interaction-spec.md` prohíbe la jerga del sistema en cualquier pantalla de
visitante (regla U-07, "bandeja no significa nada para quien reporta"), y
sostener dos juegos de etiquetas sobre una sola pantalla es la forma segura de
que un día se cruce uno.

## Jerarquía

```
CasesQueuePage            ruta con credencial
├── QueueFilters          estado, canal, idioma, prioridad
├── QueueList
│   └── QueueRow          completitud, categoría, canal, idioma, prioridad, espera
└── EmptyFilterState      "ningún caso coincide" + quitar filtros

CaseDetailPage            ruta con credencial
├── CaseHeader            PEGAJOSO: motivo, categoría, completitud + acciones
│   └── DecisionDialog    decisión + comentario obligatorio
├── EvidenceSection[]     los seis bloques
│   ├── FieldCompleteness   abierto
│   ├── TranscriptView      abierto · cada dato personal como etiqueta de su tipo
│   ├── CitationList        abierto · reúsa la cita expandible de U13
│   ├── RuleEvaluation      plegado · titular: la regla disparada
│   ├── ComplianceResult    plegado · titular: "cuatro controles en verde"
│   └── TraceSummary        plegado · titular: "1,8 s · 0,003 USD"
└── FieldCorrection       en línea, en el bloque de completitud

VisitorCasePage           ruta del enlace firmado
├── VisitorHeader         qué estás viendo, hasta cuándo vale el enlace
├── EvidenceSection[]     los mismos bloques, sin corregir campos
├── DecisionDialog        las acciones que permite su aseguradora
└── VisitorOutcome        el caso se reanudó + el mensaje al asegurado + volver a la conversación
```

## Estado y de dónde sale

| Componente | Qué recibe | De dónde |
| --- | --- | --- |
| `CasesQueuePage` | filtros (en la dirección), página de casos | `GET /tenants/{t}/inbox/cases` (C-05) |
| `CaseDetailPage` | el caso con sus seis bloques | `GET /tenants/{t}/inbox/cases/{id}` (C-05) |
| `VisitorCasePage` | el mismo caso, por su cookie de caso | la misma ruta, con `caseCookie` |
| todas | eventos de la aseguradora | `GET /tenants/{t}/inbox/stream` (C-06) |

Los filtros viven **en la dirección** y no solo en memoria: una cola filtrada que
se pierde al recargar obliga a volver a filtrar en cada vuelta, y no se puede
compartir con nadie.

## El encabezado pegajoso

`CaseHeader` se queda arriba al desplazar y lleva junto el *por qué llegó* y el
*qué hago* (BR2.1). En el teléfono es lo único que garantiza que las acciones
estén al alcance sin recorrer seis bloques; en pantalla ancha se ve casi igual
que cualquier encabezado, así que la diferencia se juega entera en el móvil.

La alternativa —una barra de acción fija abajo— se descartó porque deja ver el
botón sin ver el motivo, y el criterio los nombra en la misma frase.

## Los bloques plegados no esconden su resultado

Un bloque plegado muestra **su titular con el resultado**: la regla disparada,
"cuatro controles en verde", "1,8 s · 0,003 USD". Plegar oculta el detalle, no el
dato. Sin esa condición, plegar tres de los seis bloques sería esconder un tercio
de la evidencia detrás de un clic que nadie da.

## Validación de formularios

| Campo | Regla | Mensaje |
| --- | --- | --- |
| Comentario de la decisión | Obligatorio, 1 a 2000 caracteres | Del catálogo; la decisión elegida y el texto **no se pierden** (BR4.1) |
| Valor de un campo corregido | El formato del campo, validado por U4 | Del catálogo, nombrando campo y formato esperado; conserva el anterior (BR3.3) |

Ninguna validación se reimplementa en la pantalla: la pantalla marca el campo y
muestra el mensaje que el servidor devuelve. Una segunda validación en el
navegador es una segunda definición de lo que es válido.

## Accesibilidad

La **vista de caso por enlace entra en la línea base** del arnés; la cola y la
vista con credencial no (D25). Las tres se recorren igual en los dos idiomas y
los dos modos, pero un hallazgo serio bloquea solo en la del visitante.

Consecuencias concretas: la lista de casos es una tabla que se desplaza dentro de
su contenedor y no arrastra la página; cada bloque plegable es un botón con
`aria-expanded`; el resultado de filtrar se anuncia ("12 casos"); y el encabezado
pegajoso no tapa el foco al tabular.

## Lo que se reúsa de U6 y de U13

- El marco, el selector de idioma y el de modo, y el cliente de la API: U6.
- La cita expandible con su cláusula etiquetada en otro idioma: **la misma pieza
  que U13**, no una copia. Es el mismo dato con la misma regla (el texto literal
  en su idioma, sin traducir), y dos implementaciones serían dos formas de
  mostrarlo que un día difieren.
- Las páginas de estado —enlace no válido, enlace vencido, datos reiniciados—:
  U6 ya las tiene; esta unidad las usa con su tipo.
