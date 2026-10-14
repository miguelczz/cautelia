# Requisitos de seguridad — U12 `graph-runtime`

El riesgo propio de esta unidad tiene un nombre: **guarda una copia del estado de
cada conversación, y la escribe una pieza que no es nuestra.**

Todo lo demás del proyecto pasa por un único punto que fija la aseguradora antes
de devolver la conexión. Los puntos de control, no: los escribe el framework del
grafo, con sus propias conexiones. Ese es el hueco, y cerrarlo es la decisión
principal del diseño de esta unidad (FD-U12-3, decisión de Miguel del 2026-09-27).

## Modelo de amenazas

| Qué puede pasar | Cómo se cierra | Regla |
| --- | --- | --- |
| Una conversación de una aseguradora lee el punto de control de otra | Las operaciones del checkpointer corren dentro de una transacción tomada del punto único, con la aseguradora fijada; y la tabla lleva su columna, su política y `FORCE ROW LEVEL SECURITY` | BR6.1, FD-U12-3 |
| El texto de la persona queda en claro en una tabla que nadie mira | El punto de control va cifrado en reposo con el mismo cifrador del caso | BR6.3 |
| Un visitante recibe el caso a medias de otro, porque comparten la póliza de ejemplo | El caso se ofrece por el origen que lo creó, y la respuesta al segundo es **idéntica en texto y en estado** a la de una sesión sin casos | BR3.4 |
| Un camino de error escribe al canal sin pasar por la guardia | Todo evento, incluidos degradación y error, sale por el punto único de salida | BR2.5 |
| Un mensaje de error de base de datos revela esquema, servidor o consulta | Las tres superficies muestran la página de estado del catálogo | BR5.6 |
| Un texto del modelo enruta el grafo | La transición es pura, cerrada y sin cliente de modelo en su cadena; lo comprueba una regla de importación | BR1.2, BR1.3 |

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| SEC-U12.1 | Tablas de esta unidad sin política de aislamiento o sin forzarla | **Exactamente 0** | `mise run rls:check` |
| SEC-U12.2 | Aperturas de conexión a la base fuera del punto único, incluida la del checkpointer | **Exactamente 0** | `mise run rls:check`, y la prueba que lee un punto de control de otra aseguradora |
| SEC-U12.3 | Puntos de control legibles en claro en la base | **Exactamente 0** | Tarea nueva `mise run test:u12` |
| SEC-U12.4 | Casos de otro visitante ofrecidos o revelados al identificarse con la misma póliza de ejemplo, por idioma (AC1.19.3, `[bloquea]`) | **Exactamente 0** | `mise run evals:gate` |
| SEC-U12.5 | Eventos hacia la persona que no pasaron por el punto único de salida, incluidos degradación y error | **Exactamente 0** | Tarea nueva `mise run test:u12` |
| SEC-U12.6 | Transiciones del grafo que dependen de texto del modelo | **Exactamente 0** | `mise run lint` (contrato de importación) y `mise run test:u12` |
| SEC-U12.7 | Datos de visitante de esta unidad que sobreviven al borrado del caso | **Exactamente 0** | Tarea nueva `mise run test:u12` |
| NFR11.11 | Datos personales sin redactar en el punto de control (NFR11, dueña U3) | **Exactamente 0** | `mise run redaction:report` |
| NFR12.5 | RT-4 resuelto en el canal de texto sobre las tablas de esta unidad (NFR12, dueña U10) | **En verde**, por idioma | `mise run evals:gate` |

## Sources

- `../functional-design/rules.md` — BR1.2, BR1.3, BR2.5, BR3.4, BR5.6, BR6.1,
  BR6.3, BR6.4.
- `../functional-design/functional-design-questions.md` — Q1 y su respuesta.
- `../../../inception/units-generation/unit-of-work.md` — PA-3 y UG-3.
- `../../../inception/user-stories/stories.md` — AC1.19.3 y AC4.11.1, las dos
  compuertas duras que esta unidad toca.

## Assumptions & Open Questions

- **[Assumption]** El cifrador del caso sirve para el punto de control sin cambios.
  Si su interfaz no admite un blob del tamaño del estado serializado, la salida no
  es dejarlo en claro: es partirlo o cambiar el cifrador, y decirlo.
