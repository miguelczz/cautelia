# Instrucciones de prueba — U12 `graph-runtime`

U12 es de la **rama evaluada**: realiza M4 con US2.4, y su caso previo es el eje
de DS-2 de pregunta de cobertura durante el reporte. El resto se recorre por la
**rama determinista**, con fallos y retardos inyectados a propósito.

La diferencia con las unidades anteriores es dónde se prueba: **media docena de
las reglas de esta unidad no se pueden comprobar sin base de datos** —los puntos
de control, su aislamiento, los arrendamientos, la migración y la reanudación tras
el reinicio—, así que sus pruebas son de integración y corren con la base efímera,
no con dobles.

## El caso previo, antes del código

El eje de DS-2 **pregunta de cobertura durante el reporte** (US2.4, AC2.4.1 y
AC2.4.2), en los dos idiomas, se escribe primero, se corre y se comprueba que
falla nombrando su razón. Hoy no existe: es uno de los trece que le faltan a DS-2.

Se escribe aquí y no en el encargo reservado para la nube porque depende de la
conducta de esta unidad: que el desvío responda con lo que el fondo ya dejó y que
el bloque siguiente sea el que estaba pendiente.

## Lo que cada paso deja probado

| Paso | Pruebas | Dónde corren |
| --- | --- | --- |
| 1. Las tres tablas | Aserción de esquema; una fila de otra aseguradora no se encuentra; `migrate:check` sube, baja y vuelve a subir | Integración, con base |
| 2. El envoltorio del checkpointer | Dos aseguradoras con el mismo identificador de hilo: la segunda no ve el punto de control de la primera **ni sabe que existe** | Integración, con base |
| 3. Estado y transición | La composición falla al arrancar si dos nodos declaran el mismo campo; la transición devuelve la misma ruta con y sin el texto del modelo; el contrato de importación | Unitarias y `lint` |
| 4. El ejecutor | Un reintento y no más; el nodo que cuenta sus propios reintentos no se reintenta dos veces; la clave de idempotencia no cambia entre corridas; la traza con nodo, tipo de error e intento | Unitarias, con dobles |
| 5. Los dos ritmos | Con el fondo retrasado, el turno sale igual; la cadena de llamadas del turno no toca verificación, reglas ni revisión; la frase de espera antes de dos segundos; el barrido retoma lo pendiente | Unitarias y de integración |
| 6. Puntos de control | Reanudar no repite lo confirmado; el reinicio del proceso no pierde el caso; la sesión abandonada no decide nada; **la compuerta dura de la póliza compartida** | Integración, con base |
| 7. El turno y la salida | El flujo termina siempre con uno de los tres eventos; ningún evento esquiva el punto único, tampoco en degradación y error; el desvío vuelve al bloque pendiente | Unitarias y de integración |

## Las pruebas que aíslan una regla, escritas antes del código

Cada una rompe **una** regla y nada más, y se comprueba en rojo antes de escribir
lo que la satisface:

- **BR1.3** — un texto del modelo que dice "ir a decision" no cambia la ruta.
- **BR1.5** — dos nodos con el mismo campo: el proceso no arranca.
- **BR2.2** — con el fondo retrasado a propósito, el turno responde igual.
- **BR2.3** — la cadena de llamadas del turno no contiene verificación, reglas ni
  revisión completa.
- **BR3.2** — reanudar no vuelve a preguntar un campo confirmado.
- **BR3.4** — compuerta dura: el segundo navegador recibe exactamente lo mismo, en
  texto y en estado, que una sesión sin casos abiertos.
- **BR5.1** — el ejecutor aplica la política del `NodeSpec` sin ninguna rama por
  nombre de nodo.
- **BR5.4** — dos relanzamientos del mismo trabajo comparten clave y el segundo no
  vuelve a llamar al proveedor.

## Lo cronometrado

PERF-U12.2 (los tres controles, 1 ms o menos), PERF-U12.3 (el trabajo propio del
nodo del turno, 50 ms o menos) y PERF-U12.4 (el tiempo máximo declarado de un nodo
del ritmo del turno, 1.600 ms o menos) se comprueban en `mise run test:u12`, con
sus mediciones publicadas en la salida.

## Lo que ninguna prueba hace

- **Llamar al proveedor.** Los fallos —`timeout`, `rate_limited`, `unavailable`,
  `invalid_response`— se inyectan con dobles deterministas. Un ejecutor que solo se
  pudiera probar con el proveedor real no se podría probar en rojo.
- **Depender del reloj de la máquina.** Los arrendamientos y los tiempos máximos
  reciben su reloj por parámetro, como en las unidades anteriores.
- **Correr con dos procesos.** El arrendamiento existe para el día que los haya;
  probarlo con dos procesos es del intent `infra`.
