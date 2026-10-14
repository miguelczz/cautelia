# Especificación funcional — U12 `graph-runtime`

U12 es la unidad que convierte cuatro nodos en un sistema. No añade ninguna
conducta nueva de cara al asegurado: añade **el orden en que la conducta ocurre**,
y lo que pasa cuando ese orden se rompe —un proveedor que no responde, un proceso
que muere, una persona que cierra el navegador a mitad del relato.

Es también donde el proyecto cumple o no su promesa más visible: que el
orquestador es código con contratos y no un modelo decidiendo con texto libre.

## El recorrido de un turno

```
  El canal entrega un turno (C-14)
        │
        ▼
  ┌─ Ritmo del turno ────────────────────────────────────────────┐
  │  1. Se carga el punto de control del caso (BR3.1, BR3.2)     │
  │  2. Corre el nodo `intake` con su política (BR5.1)           │
  │  3. Tres controles baratos de U10, y nada más (BR2.3)        │
  │  4. El punto único de salida emite los eventos (BR2.5)       │
  │  5. Se escribe el punto de control (BR3.1)                   │
  └──────────────────────────────────────────────────────────────┘
        │                                    │
        │ lanza sin esperar (BR2.2)          ▼  FinalText / Handoff / TurnError
        ▼
  ┌─ Ritmo de fondo ─────────────────────────────────────────────┐
  │  `policy_verification` → `decision` → `compliance`           │
  │  Cada uno con su `NodeRun`: arrendamiento, latido y clave     │
  │  de idempotencia (BR5.4, BR5.5)                              │
  └──────────────────────────────────────────────────────────────┘
        │
        ▼  si `compliance` deriva: interrupt() y pausa con su motivo (BR4.1)
```

Lo que el turno **no** hace está tan fijado como lo que hace: no espera al
trabajo de fondo (BR2.2), no corre verificación ni reglas ni la revisión completa
(BR2.3), y si necesita un resultado que no llegó dice la frase de espera antes de
que la persona crea que la llamada se cayó (BR2.4).

## Decisiones de esta etapa

| ID | Decisión | Por qué |
| --- | --- | --- |
| FD-U12-1 | El estado tipado y el grafo se **componen** desde los `NodeSpec`, y el proceso **no arranca** si dos nodos declaran el mismo campo | Una lista escrita a mano se desincroniza con el primer nodo que cambie su conjunto de escritura. Y un choque descubierto en producción es un campo que un nodo le pisa a otro a mitad de una conversación, sin dejar rastro (AC4.9.5) |
| FD-U12-2 | **Quién cuenta los reintentos es dato del `NodeSpec`**, no una rama del ejecutor. Se añade a C-15 un campo que dice si los reintentos los lleva el ejecutor o el nodo | Resuelve el aviso que U8 dejó escrito: `policy_verification` ya consume sus propios intentos —es el único de los cuatro— porque tras agotarlos todavía tiene que escribir su valor `unverifiable`, que nadie más sabe escribir. Sin esto, el ejecutor haría **cuatro** llamadas al proveedor en vez de dos. La alternativa era un `if` por nombre de nodo en el ejecutor común, que es exactamente la rama por inquilino-o-por-nodo que la convención 9 del equipo prohíbe. La política de fallo ya es dato; esto es una línea más del mismo dato |
| FD-U12-3 | **Los puntos de control los escribe una pieza propia**, sobre la tabla de esta unidad, con su columna de aseguradora, su política de aislamiento y su contenido cifrado | Decisión de Miguel del 2026-09-27, tomada en dos pasos. La primera versión de esta decisión (Q1) era envolver la pieza del framework, y su riesgo escrito era que no tolerara transacciones ajenas. Al instalarla apareció un obstáculo distinto y de más fondo: **trae sus propias tres tablas**, ninguna con columna de aseguradora, y **guarda el estado en claro**. Adaptarlas era posible —columna con valor por omisión desde la variable de sesión, más un serializador propio— pero deja las dos propiedades que no podemos fallar, el aislamiento y el cifrado, apoyadas en la forma interna de tablas ajenas que una actualización puede cambiar sin avisar. La salida que este mismo documento ya había escrito era escribir la nuestra, y es la que se toma. El paso 1 construyó su tabla pensando en esto |
| FD-U12-4 | Los campos de salida de cada nodo **conservan su prefijo**; no se unifican en un solo par "clave y texto del turno" | `intake` y `policy_verification` los dos componen texto hacia la persona, y con un par compartido serían dos nodos escribiendo el mismo campo (convención 6). Corren en ritmos distintos y hoy nunca compondrían el mismo turno, pero la separación no cuesta nada y el día que un tercer nodo hable, el choque no existe. Quien emite decide **cuál** de los pares sale, y esa decisión es del punto único de salida, donde se ve |
| FD-U12-5 | Los minutos de inactividad que cierran una sesión son **configuración del proyecto**, no de la aseguradora | La convención 9 manda que las diferencias entre aseguradoras vivan en su carpeta; un tiempo de inactividad no es una diferencia entre aseguradoras, es una propiedad de la demostración, como el techo de gasto. Ponerlo por aseguradora invitaría a tres valores que nadie eligió |
| FD-U12-6 | El desvío de cobertura **no es un nodo ni una rama del grafo**: es el turno leyendo lo que el ritmo de fondo ya dejó en el estado | Por eso volver al bloque pendiente no necesita recordar nada (BR4.2, BR4.3): el desvío no escribe ningún campo de la captura, y el bloque que toca se deduce del caso. Una rama del grafo para el desvío tendría que acordarse de dónde volver, y eso es el contador que ADR-003 evita |
| FD-U12-7 | El punto de control va **cifrado en reposo con el mismo cifrador del caso** | Lleva dentro el texto de la persona. Una tabla del grafo no es menos sensible que la del caso por vivir en otro módulo, y dejarla en claro sería guardar sin cifrar justo la copia que nadie mira (BR6.3) |
| FD-U12-8 | Un caso a medias se ofrece **por el origen que lo creó**, nunca por la póliza | Las tres pólizas de ejemplo son públicas a propósito, así que ofrecer por póliza le entrega el caso de un visitante a cualquier otro. La respuesta al segundo navegador es **idéntica, en texto y en estado**, a la de una sesión sin casos abiertos: una respuesta distinta ya dice que existe algo (BR3.4, compuerta dura) |

## Lo que U12 no hace

- **Los cuatro nodos:** U8, U9, U10 y U11. U12 los ejecuta; no sabe lo que hacen
  por dentro.
- **El transporte de cada canal:** U13 (chat, con su flujo de eventos por HTTP) y
  U16 (la llamada). U12 entrega eventos tipados; serializarlos o sintetizarlos es
  del canal.
- **Los tres controles del turno:** U10 los construye; U12 los invoca en el punto
  único de salida.
- **La decisión humana:** U14. U12 abre la pausa y la reanuda con lo que la
  bandeja decidió.
- **La conversación de punta a punta de los golden sets:** U13 trae el conductor
  que la mide.

## Fronteras con lo ya construido

| Con quién | Qué le pide | Contrato |
| --- | --- | --- |
| Los cuatro nodos | Su `NodeSpec` y su `run` | C-15 |
| U4 `case-record` | Crear el caso y aplicarle las transiciones: pausa, reanudación, retiro | C-12 |
| U2 `tenancy` | La sesión con la aseguradora fijada, y la configuración | C-25, C-26 |
| U10 `compliance` | Los tres controles del turno, para el punto único de salida | C-20 |
| U1 `workspace` | El catálogo por idioma: espera, degradación, error | C-1 |
| U5 `provider-platform` | El registro de uso por turno y por nodo | C-23 |
| U13, U16, U18, U14 | Nada: son los consumidores de C-14 | C-14 |

**Lo que U12 le añade a un contrato ya escrito.** C-15 gana un campo: quién lleva
los reintentos (FD-U12-2). Es aditivo —los cuatro nodos siguen validando sin
tocarlos, con el valor por omisión "los lleva el ejecutor"— y solo
`policy_verification` declara el otro.

## Riesgos de esta unidad

- ~~La pieza de puntos de control del framework puede no tolerar que otro maneje
  sus transacciones.~~ **Se materializó el 2026-09-27, con otra cara:** sus tablas
  son suyas, sin columna de aseguradora y con el estado en claro. Se tomó la salida
  que estaba escrita (FD-U12-3). El riesgo que queda es el de la pieza propia:
  equivocarse en la semántica de reanudación es sutil, y por eso la reanudación
  tiene su prueba de integración antes que nada que se apoye en ella.
- **El trabajo de fondo sin broker depende de que el proceso siga vivo.** El
  hospedaje gratuito duerme el proceso. El arrendamiento con latido y el barrido
  al arrancar son lo que hace que eso sea una demora y no una pérdida (BR5.4,
  BR5.5); si el barrido tiene un error, el síntoma es trabajo que nunca termina y
  nadie reclama.
- **Los dos ritmos son la parte más fácil de romper sin notarlo.** Basta un
  `await` de más en el camino del turno para que el turno empiece a esperar al
  trabajo de fondo. Por eso BR2.3 se comprueba analizando la cadena de llamadas y
  no leyendo el código.
- **El presupuesto de latencia del turno todavía no tiene número.** Esta unidad lo
  fija en su etapa de requisitos de calidad, y tres unidades ya escribieron sus
  tiempos máximos "a la espera de que U12 fije el suyo desde la medición". Si se
  publica un número inventado, esas tres se ajustan a algo falso.

## Sources

- `../../../inception/units-generation/unit-of-work.md` — U12, sus historias, sus
  notas de implementación y PA-3.
- `../../../inception/units-generation/unit-of-work-story-map.md` — el mapa de
  historias de esta unidad.
- `../../../inception/requirements-analysis/requirements.md` — FR2.1 a FR2.7,
  FR1.4, FR4.2, FR7.1, FR7.6.
- `../../../inception/domain-design/components.md` — el componente Orchestration,
  con sus tres entidades, y ADR-003 y ADR-004.
- `../../../inception/contract-design/contract-summary.md` — C-14, C-15, C-20,
  C-12, C-25.
- `orchestration/nodes/policy_verification/node.py` — el aviso que U8 dejó escrito
  sobre los reintentos, que FD-U12-2 resuelve.
- `orchestration/nodes/intake/node.py` — el conjunto de escritura de `intake` y su
  prefijo, que FD-U12-4 conserva.

## Assumptions & Open Questions

- **[Q]** ¿Cuántas llamadas al modelo caben en un turno? Es de esta unidad y se
  responde en su etapa de requisitos de calidad, con el presupuesto del turno.
  U11 publica su medición y se ajusta a lo que salga.
