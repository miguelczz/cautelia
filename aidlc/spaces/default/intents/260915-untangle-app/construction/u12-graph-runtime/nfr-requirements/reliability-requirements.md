# Requisitos de confiabilidad — U12 `graph-runtime`

Lo que tiene que seguir siendo cierto: que nadie cuente su accidente dos veces, y
que un fallo que no es de la persona no le cueste lo que ya contó.

Esta unidad es la única donde "el proceso se murió" es un caso de uso y no un
incidente: el hospedaje gratuito duerme el proceso y lo despierta, así que
reanudar no es una función de emergencia, es el camino normal.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| REL-U12.1 | Campos confirmados que se vuelven a preguntar tras reanudar | **Exactamente 0** | Tarea nueva `mise run test:u12` |
| REL-U12.2 | Conversaciones perdidas cuando el proceso se reinicia a mitad de un turno | **Exactamente 0** | Tarea nueva `mise run test:u12` |
| REL-U12.3 | Llamadas al proveedor repetidas por un relanzamiento del mismo trabajo | **Exactamente 0** | Tarea nueva `mise run test:u12` |
| REL-U12.4 | Ejecuciones de nodo que quedan tomadas para siempre por un proceso muerto | **Exactamente 0** | Tarea nueva `mise run test:u12`, con arrendamiento vencido sembrado |
| REL-U12.5 | Turnos que quedan abiertos sin `FinalText`, `Handoff` ni `TurnError` | **Exactamente 0** | Tarea nueva `mise run test:u12`, con fallos inyectados |
| REL-U12.6 | Casos que reciben categoría o revisión de cierre con la captura incompleta | **Exactamente 0** | Tarea nueva `mise run test:u12` |
| REL-U12.7 | Turnos que esperan al trabajo de fondo, con el fondo retrasado a propósito | **Exactamente 0** | Tarea nueva `mise run test:u12` |
| NFR13.5 | Turnos de la agente hasta cerrar o derivar, en los casos completos simples (NFR13, dueña U21; AC1.5.6) | **14 o menos** por idioma; lo realiza U11 y U12 no lo empeora | `mise run evals:gate` |

## Los cinco ceros, y por qué son ceros

Ninguna de las siete primeras admite un porcentaje, y no por ambición: **un
promedio no describe ninguna de ellas**. "El 2 % de las conversaciones se pierde al
reiniciar" no es una degradación del 2 %, son personas que contaron su accidente
para nada. Lo mismo con el gasto duplicado, que se paga contra un tope de 5 USD, y
con un turno que queda abierto en silencio, que es la única forma de fallar que la
persona no puede distinguir de que el sistema la ignore.

## Cómo se comporta cuando algo falla

- **Un nodo falla:** el ejecutor aplica su política —tiempo máximo, un reintento,
  texto de degradación— y emite `TurnError` por el punto único de salida. El caso y
  el texto del turno se conservan, y la traza lleva el nodo, el tipo de error de la
  taxonomía cerrada y el intento (BR5.2, BR5.3).
- **El proceso muere:** el punto de control del último turno ya está escrito, así
  que reanudar no repite nada (BR3.1, BR3.2). El trabajo de fondo en vuelo queda con
  su arrendamiento vencido, y el barrido al arrancar lo retoma por su clave de
  idempotencia, sin volver a gastar (BR5.4, BR5.5).
- **La persona se va a mitad:** el caso queda esperando al asegurado con su
  completitud real y el motivo en la traza, y **no se decide nada** sobre datos
  incompletos (BR3.3).
- **La base de datos cae:** las tres superficies muestran la página de estado del
  catálogo, sin detalles técnicos (BR5.6).

## Sources

- `../functional-design/rules.md` — BR2.2, BR3.1 a BR3.3, BR5.1 a BR5.6.
- `../../../inception/requirements-analysis/requirements.md` — FR2.4, FR2.7, FR1.4,
  FR7.1.
- `../../../inception/domain-design/components.md` — ADR-004, el trabajo de fondo
  sin broker y el arrendamiento con latido.

## Assumptions & Open Questions

- **[Assumption]** El barrido al arrancar corre en el mismo proceso. Con un solo
  proceso no hay carrera; el día que haya dos, el arrendamiento es lo que la
  resuelve, y por eso existe desde ahora y no cuando haga falta.
