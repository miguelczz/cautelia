# Requisitos de fiabilidad — U6 `web-shell`

U6 es dueña de **NFR16**, la disponibilidad mensual del enlace en vivo, según la
tabla de metas de `unit-of-work.md`. Y es dueña de la mitad que se puede
construir aquí: que el proceso diga con honestidad si puede atender, que la
interfaz sepa esperar a que despierte, y que ninguna falla deje a una persona
frente a una pantalla vacía. La otra mitad —el chequeo cada cinco minutos, su
alerta y el cálculo del mes— la verifica el intent `infra` (PA-10), como dice la
misma tabla.

**`mise run test:u6` y `mise run a11y` no existen todavía**: los crea la
generación de código de esta unidad.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| NFR16.1 | Disponibilidad mensual del enlace en vivo: chequeos exitosos sobre chequeos totales del mes | **95 % o más**, publicada con su mes | Chequeo periódico del intent `infra` contra `GET /api/health/ready`; **hoy no medida**: el chequeo no existe hasta ese intent |
| NFR16.2 | La salud distingue "no despierta" de "una superficie caída": 503 solo cuando la base o la configuración no están; una superficie caída sale como `down` con 200 | **Siempre**, en las pruebas de base caída, configuración ausente y sonda caída | `mise run test:u6` |
| NFR16.3 | Página de espera pintada en un teléfono de gama media con red lenta | **Menos de 3 segundos** (detalle en `performance-requirements.md`) | `mise run a11y` |
| NFR16.4 | Salud de listo | **1 segundo o menos en p95** (detalle en `performance-requirements.md`) | `mise run test:u6` |
| NFR16.5 | La espera consulta cada 5 segundos, pasa a "no disponible" a los 60 y vuelve sola a la ruta pedida al despertar | **Los tres caminos**, con reloj simulado | `mise run test:u6` |
| NFR16.6 | Ninguna sonda de superficie llama a un proveedor, gasta o consume límites de visitantes | **Exactamente 0** llamadas | `mise run test:u6` |
| NFR20.1 | Las ocho pantallas de U6 —el inicio y las siete páginas de estado— existen en español y en inglés con las mismas claves del catálogo, y el arnés las recorre en los dos | **Sin excepción** para ningún idioma (NFR20, dueña U21) | `mise run copy:check` y `mise run a11y` |
| REL-U6.1 | Una falla del servidor, de la red o un código desconocido termina en un texto del catálogo con su acción, nunca en una pantalla vacía ni en texto crudo | **100 %** de los códigos de C-01, más `unknown`, red caída y cuerpo ilegible | `mise run test:u6` |
| REL-U6.2 | Almacenamiento del navegador bloqueado o con valor corrupto: la página se dibuja con el modo del dispositivo y sin error visible | **Siempre** | `mise run test:u6` |
| REL-U6.3 | Una falla al registrar un hito de activación no hace fallar ni demora el turno que lo produjo, y deja un evento en la traza | **Siempre** | `mise run test:u6` |
| REL-U6.4 | Un módulo que declara una superficie sin sonda impide arrancar y nombra el módulo | **Siempre** | `mise run test:u6` |

## Qué significa "disponible"

Un chequeo es exitoso cuando `GET /api/health/ready` responde 200 en su
presupuesto de 1 segundo. Que una superficie esté `down` no vuelve el proceso no
disponible —el chat caído no apaga la bandeja—, pero el chequeo lo registra
aparte, y la alerta por superficie es decisión del intent `infra`, que conoce el
canal.

El 95 % mensual permite unas 36 horas sin servicio al mes. Es holgado a propósito:
es una demostración de portafolio en un hospedaje gratuito que se duerme, y lo
que la meta protege es que quien llega **no encuentre una página muerta**, no
una disponibilidad de producción. Por eso la pieza que más pesa no es el
porcentaje sino la página de espera: con ella, una instancia dormida se ve como
"despertando" y no como caída.

## Degradación

| Qué falla | Qué ve la persona | Qué hace el sistema |
| --- | --- | --- |
| El proceso duerme o no responde | "La demo está despertando", y a los 60 s "no disponible" | Consulta cada 5 s (NFR16.5) |
| La base de datos | La misma página de espera: sin base no hay proceso listo | La salud responde 503 (NFR16.2) |
| Una superficie montada | El resto del aplicativo sigue; esa superficie muestra su propio error | La salud la reporta `down` con 200 |
| El directorio del sitio | El mensaje del catálogo y "Reintentar"; sin filas inventadas | Error por C-01 (BR3.2 a BR3.4) |
| El almacenamiento del navegador | Nada: el modo sigue al dispositivo | REL-U6.2 |
| El registro de un hito | Nada: el turno sigue | Evento en la traza (REL-U6.3) |

No hay copia de seguridad ni recuperación de datos propia: las dos tablas de
activación son telemetría. Perder el avance de una sesión cuenta de nuevo un
hito; perder el conteo de un día deja un hueco que la traza explica. Ninguna de
las dos pérdidas afecta a un caso.

## Sources

- `../functional-design/functional-spec.md` — sección 2.1 y flujos F2, F5, F7,
  F8 y F10.
- `../functional-design/rules.md` — BR1.4, BR3.2 a BR3.4, BR5.1 a BR5.4, BR8.3.
- `../../../inception/units-generation/unit-of-work.md` — tabla de metas: NFR16
  se registra en U6 y lo verifica el intent `infra`.
- `../../../inception/contract-design/contract-summary.md` — C-02.
- `../../../inception/user-stories/stories.md` — AC5.16.1 a AC5.16.4.

## Assumptions & Open Questions

- **NFR16.1 queda "no medida" hasta el intent `infra`.** Se declara así en la
  matriz de verificación; nunca se omite.
- **Los enlaces de la página "no disponible" (README y video) no existen
  todavía** y BR4.4 los omite mientras no estén configurados. AC5.16.4 queda
  cubierto en su conducta y pendiente en esos enlaces hasta la decisión de
  publicar el repositorio (semana 12) y el video (US4.2).
