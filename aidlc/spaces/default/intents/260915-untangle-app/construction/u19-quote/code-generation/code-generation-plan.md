# Plan de generación de código — U19 `quote`

Dos tandas, y el reparto no es por tamaño: **es por dónde puede correr cada una**
(FD-U19-8). La nube no tiene base de datos ni motor de contenedores.

## El reparto, y por qué

| Tanda | Qué | Dónde | Por qué ahí |
| --- | --- | --- | --- |
| 1 | La solicitud: los cuatro bloques de captura, el esquema del tipo `quote_request`, las reglas de elegibilidad con sus casos, la banda, y los casos de DS-4 | **Nube** | Todo es dato y lógica pura: esquema, YAML versionado y frases del catálogo. Se prueba sembrando archivos, sin base |
| 2 | La bandeja del suscriptor: el rol, su permiso, la lista filtrada y la decisión que reanuda | Aquí | Necesita dos aseguradoras sembradas, las pruebas de aislamiento con colisiones detectables y el puerto de reanudación |

**En serie, no en paralelo.** La tanda 2 decide solicitudes que la tanda 1 crea: mandar
las dos a la vez es pagar el rehacer dos veces.

**Y no al mismo tiempo que el cableado del grafo de fondo** (PENDIENTES 1.8): UG-7 dice
que esta unidad toca captura, esquema, reglas y bandeja, que son los mismos archivos.

---

## Tanda 1 — La solicitud y su elegibilidad *(nube)*

1. Los campos del tipo `quote_request` en el esquema del caso, con sus cuatro bloques y
   su completitud. El tipo ya existe, declarado sin campos.
2. Los cuatro bloques de captura, una idea a la vez y con confirmación por bloque, sobre
   el nodo que ya existe. **Sin nodos nuevos.**
3. `vehicle_age_years` derivado en un solo sitio, desde el año y el reloj que la captura
   ya inyecta.
4. Los cinco campos de elegibilidad en el vocabulario cerrado del motor, cada uno con el
   bloque que lo escribe.
5. El conjunto de reglas de elegibilidad de Sunmeadow Auto, versionado y con sus casos
   dentro del YAML; `quote_enabled` pasa a `true` solo ahí.
6. La salida de elegibilidad con sus tres valores y la banda con sus cuatro, y las frases
   del catálogo en los dos idiomas: la razón en lenguaje llano, la negativa a dar un
   precio, y la respuesta donde la cotización está apagada.
7. Los casos de DS-4 por idioma, incluidos los que presionan por un precio.

**Pruebas.** Cada regla con sus casos; la captura que no cierra un bloque sin
confirmarlo; un campo de elegibilidad que ningún bloque escriba no se puede declarar;
una derivación con banda afirmada no se puede construir; ninguna respuesta de DS-4 pasa
la guardia con un importe; y la lista de nodos del grafo sigue siendo de cuatro.

**Reglas que cierra:** BR1.1 a BR1.5, BR2.1 a BR2.5, BR3.1, BR3.2.

---

## Tanda 2 — La bandeja del suscriptor *(aquí)*

1. `Role.UNDERWRITER` y la acción de decidir una solicitud, con su fila en la tabla de
   permisos.
2. La lista filtrada: solo solicitudes de cotización derivadas, filtrada en el servidor.
3. La decisión con comentario obligatorio, que se registra y reanuda de fondo por el
   puerto que ya existe, y que cierra con aprobado o rechazado.
4. La pantalla, con el mismo esqueleto de la bandeja que ya existe.

**Pruebas.** Las tres credenciales contra la API y no solo contra la pantalla; dos
aseguradoras sembradas con colisiones detectables; la decisión registrada antes de la
reanudación, con un doble que anota el orden; y quien preguntó ve la decisión en su
conversación.

**Reglas que cierra:** BR4.1, BR4.2, BR4.3.

---

## Tareas nuevas

| Tarea | Qué hace |
| --- | --- |
| `test:u19` | Solo las pruebas de esta unidad, incluido el presupuesto cronometrado de PERF-U19.1 |

## Lo que no se toca

- **La guardia de salida y sus patrones**: ya cazan importes y porcentajes en los dos
  idiomas.
- **Los reconocedores de datos personales**: los de nombre y VIN ya existen.
- **Los cuatro nodos del grafo**: no se añade ninguno.
- **La cotización de Stonecroft y Knotwell**: se queda apagada, y AC6.1.3 comprueba qué
  pasa entonces.
- **El cableado del grafo de fondo**: trabajo aparte, y no al mismo tiempo.
