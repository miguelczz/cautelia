# Piezas lógicas — U5 `provider-platform`

En qué se parte esta unidad, qué puede importar qué, y dónde cae cada control.

**Fuentes consumidas.** `../nfr-requirements/security-requirements.md`,
`../nfr-requirements/observability-requirements.md` y
`../nfr-requirements/tech-stack-decisions.md`,
`../functional-design/functional-spec.md`, `../functional-design/rules.md` y
`../functional-design/entities.md`, y
`../../../inception/contract-design/contract-summary.md` (C-16, C-17 y C-23).

U5 ofrece **tres** contratos —C-16, C-17 y C-23— y viven en dos árboles distintos
del código, `providers/` y `telemetry/`. Eso no es desorden: es que la
contabilidad y las trazas tienen que poder existir sin el adaptador, y el corte
tiene que poder existir sin las trazas.

> **Corrección del 2026-09-21, aplicada en la compuerta de la unidad.** Este
> párrafo decía que U5 "es la primera unidad del proyecto que ofrece tres
> contratos en vez de uno". Es falso, y se comprobó contando la columna de dueño
> de la tabla de contratos: U1 y U2 ofrecen más, y U5 empata en tercer puesto con
> U6 y U14. La frase equivalente de `../infrastructure-design/` ya se escribió
> corregida. Se deja el rastro en vez de borrarlo porque el defecto no es la
> cifra sino el hábito: un superlativo es una cifra disfrazada, y hay que
> contarlo o sustituirlo por la distinción concreta.

## Las nueve piezas

| Pieza | Qué contiene | Por qué está separada |
| --- | --- | --- |
| `providers/ports.py` | Los cuatro `Protocol` que usa el núcleo, la taxonomía cerrada de errores y la señal de parada | Es lo que ven U7, U8, U10, U11, U15 y U21. No importa ningún SDK, así que se puede probar un nodo con un doble sin instalar nada |
| `providers/factory.py` | La fábrica de clientes por uso, con su clave y su proyecto | Es el único sitio que construye un cliente. Un contrato `protected` lo comprueba, y por eso las claves separadas siguen separadas en el código |
| `providers/adapters/gemini/` | El único sitio donde se importa el SDK de Gemini: la petición, la salida estructurada validada, la traducción de errores y el cortacircuitos | Un contrato `forbidden` impide ese import en cualquier otro sitio. El cortacircuitos está aquí porque la salud del proveedor es suya, no del nodo |
| `telemetry/spend/models.py` | El registro de gasto, los contadores, la ventana, el dinero con su estado y el total con su conteo | No importa nada del módulo. Es el suelo, y tenerlo aislado permite probar la aritmética del cupo y del techo sin base de datos |
| `telemetry/spend/repository.py` | La persistencia, por el punto único de sesión de U2: la transacción de dos sentencias y las lecturas por clave | Es la única pieza que sabe que hay una base. Aquí vive la propiedad de que el techo no se puede pasar dos veces a la vez |
| `telemetry/spend/api.py` | La superficie congelada del contrato C-17: gasto, presupuesto, cuota y reserva de la voz | Lo que ven U13, U16, U17 y U22. Todo lo demás puede cambiar sin avisarles |
| `telemetry/traces/api.py` | La superficie del contrato C-23: el ayudante de tramos con su lista cerrada de atributos y el resumen de traza | Es el único sitio que toca el SDK de trazas, y su lista cerrada es lo que impide que un tramo lleve texto |
| `telemetry/traces/export.py` | La exportación por lotes: al backend cuando hay destino, al archivo cuando no | Separado porque es lo único que puede fallar sin detener nada, y porque la tubería usa el otro camino |
| `telemetry/spend/purge.py` | El purgador de datos de visitante que implementa el contrato C-11 | Lo llama el reinicio nocturno de U20. Separarlo deja visible que el borrado tiene dueño y contrato, y qué **no** borra |

Una décima pieza que no es código: la carpeta de configuración versionada
`app/config/providers/`, **que esta unidad crea** —hoy no existe, y el árbol de
módulos de `unit-of-work.md` ya la tenía reservada—. Contiene proveedores,
modelos, precios de lista con su versión y su fecha, planes por uso, topes
declarados con su fecha de comprobación, reserva de grabación en minutos y
parámetros del cortacircuitos.
Son archivos versionados, no código: cambiar un precio es un cambio que queda en
el historial y dispara la compuerta.

## Qué puede importar qué

```
   providers/ports.py ◄──────────── el nucleo (U8, U10, U11, U21...)
        ▲          ▲
        │          │
   factory.py   adapters/gemini/ ──► telemetry/spend/api.py   (reporta uso)
                      │             ──► telemetry/traces/api.py (emite tramo)
                      ▼
                (SDK de Gemini)            telemetry/traces/api.py
                                                    │
                                                    ▼
                                            traces/export.py ──► (SDK de trazas)

   telemetry/spend/api.py ──► spend/repository.py ──► spend/models.py
            ▲                        ▲
            │                        │
     purge.py ────────────────────────┘
```

**Cinco reglas de dirección**, cada una un contrato de importación que el linter
comprueba:

1. **`ports.py` no importa ningún SDK ni nada de `telemetry/`.** Es lo que
   permite que un nodo se pruebe con un doble sin instalar un proveedor.
2. **El SDK de Gemini solo dentro de `adapters/gemini/`.** Contrato `forbidden`.
3. **El SDK de trazas solo dentro de `telemetry/traces/`.** Contrato `forbidden`,
   hermano del anterior y nuevo en esta unidad: es lo que sostiene que ningún
   tramo se emita saltándose la lista cerrada de atributos.
4. **`telemetry/spend/` no importa `telemetry/traces/`.** Es la regla que hace
   verdadera la frase "el corte funciona aunque la observación falle". La flecha
   contraria sí existe: las trazas leen costo para los resúmenes.
5. **Los modelos no importan el repositorio.** El suelo no conoce la base.

## Dominios de fallo y radio de daño

| Si falla… | Radio | Qué sigue vivo |
| --- | --- | --- |
| El SDK o la API de Gemini | Los nodos que llaman al modelo, por su política de fallo | El gasto, el corte, las cuotas, las trazas y el chat en modo degradado |
| El cortacircuitos abre | Ese proveedor **para ese uso** | Los otros tres usos, cada uno con su clave y su circuito |
| El backend de trazas | Los resúmenes de ese rato pasan a `lost` | Todo lo demás, sin excepción (regla 4) |
| La base de datos | Las llamadas facturables se rechazan | El chat en plan gratuito, que no consulta el presupuesto |
| El techo alcanzado | El carril público de la voz | El chat, y la reserva de grabación por su carril |
| Un precio falta en la tabla | La exactitud de una cifra, que se marca no medida | El corte, que suma lo que sí se midió y cuenta lo que no |

**El radio más grande de esta unidad es la base**, y es compartido con todo el
aplicativo: el proceso es único. Lo que U5 aporta al respecto es que su parte
falla **cerrada** para lo que cuesta dinero y abierta para lo que no.

## Recursos compartidos, y con quién

| Recurso | Con quién se comparte | Qué lo protege |
| --- | --- | --- |
| La base de datos | Todo el aplicativo | El punto único de sesión de U2; esta unidad no abre conexiones propias |
| El punto único de salida redactada | U3, U4, U10, U13, U16 | El registro cerrado de puntos de salida; U5 declara los suyos, no inventa uno nuevo |
| El catálogo de textos | Todas | Claves literales, comprobadas por paridad y por consumidor |
| El proceso y su memoria | Todo el aplicativo | La cola diferida está acotada, y al llenarse pasa a síncrona en vez de crecer |

## Lo que esta unidad deja preparado para U15

U15 `speech-providers` añade transcripción y síntesis. Lo hereda todo de aquí y
no cambia nada:

- Implementa `SpeechToText` y `TextToSpeech`, que ya están declarados en
  `ports.py`.
- Sus adaptadores viven en `adapters/<proveedor>/` con su propio contrato
  `forbidden`, uno por proveedor.
- Reporta uso por `telemetry/spend/api.py` y emite tramos por el mismo ayudante,
  con la misma lista cerrada de atributos.
- Llena sus filas en la tabla de topes siguiendo el esquema que esta unidad fija,
  con la figura que ofrezca cada proveedor de voz y su fecha de comprobación.

## Sources

- `../nfr-requirements/` — los seis documentos de esta unidad
- `../functional-design/functional-spec.md` y `../functional-design/rules.md`
- `<record>/inception/contract-design/contract-summary.md` — C-11, C-13, C-16,
  C-17, C-23, C-24
- `<record>/inception/domain-design/decisions.md` — ADR-018 y su enmienda
- `<record>/inception/units-generation/unit-of-work.md` — el árbol de módulos y
  dónde vive esta unidad en el código
- `nfr-design-questions.md` — Q1 y Q4

## Assumptions & Open Questions

- Los nombres exactos de archivo dentro de cada pieza se fijan en la generación
  de código; lo que esta etapa fija son las fronteras y las cinco reglas de
  dirección, que son lo que el linter comprueba.
- U15 hereda los puertos y la tabla de topes. Si alguno de sus proveedores de voz
  no ofreciera ninguna de las cuatro figuras de tope, lo declara
  `none_available` con lo que lo sustituye, siguiendo la política que esta unidad
  fija.
