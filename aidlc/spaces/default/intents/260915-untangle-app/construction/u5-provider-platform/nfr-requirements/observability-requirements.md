# Requisitos de observabilidad — U5 `provider-platform`

Esta unidad no *usa* la observabilidad: **la produce**. Las trazas por turno, por
nodo y por llamada que todas las demás emiten salen de aquí, y el resumen que el
visitante ve junto a cada respuesta también.

Eso obliga a una asimetría que conviene enunciar antes de las tablas: la
telemetría de este proyecto es a la vez la herramienta de diagnóstico **y** una
superficie por la que puede salir un dato personal. El escenario RT-14 es
exactamente eso, y es compuerta dura. Así que este documento pide dos cosas de
cada tramo: que diga lo suficiente para entender un fallo, y que no diga nada
más.

## Objetivos medibles

**Los dos comandos que esta tabla cita —`mise run test:u5` y `mise run
spend:report`— no existen todavía**: los crea la generación de código de esta
unidad y los declara su diseño de infraestructura, igual que U4 declaró los
suyos. Hasta entonces el comprobador de artefactos los marca, y esa marca es
correcta.

**NFR11.5 y NFR11.6 no están en esta tabla**, y no es un olvido: la tabla de
metas de `unit-of-work.md` registra NFR11 en `security-requirements.md`, y ahí
están las dos filas de esta unidad —los datos personales en los tramos y las
claves de proveedor en lo que el proceso emite—. Repetirlas aquí daría dos filas
de la matriz para una sola meta.

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| OBS-U5.1 | Turnos que producen los tres niveles de tramo —turno, nodo y llamada— sobre un caso sembrado completo | **Todos**; ningún nivel falta | `mise run test:u5` |
| OBS-U5.2 | Tramos de llamada que llevan los cinco atributos: modelo, tokens de entrada, tokens de salida, latencia y costo con su estado | **Todos** | `mise run test:u5` |
| OBS-U5.3 | Nombres de tramo de nodo que no son `intake`, `policy_verification`, `decision` ni `compliance` | **Exactamente 0** | `mise run test:u5` |
| OBS-U5.4 | Intentos fallidos que dejan su evento con nodo, tipo de error y número de intento | **Todos**, uno por intento | `mise run test:u5` |
| OBS-U5.5 | Tiempo desde que la respuesta terminó hasta que el resumen pasa a `ready` o a `lost` | **10 segundos o menos** hasta la resolución, en uno u otro sentido | `mise run test:u5` |
| OBS-U5.6 | Resúmenes de traza devueltos a un navegador distinto del que los produjo | **Exactamente 0**, y la respuesta es indistinguible de la de uno inexistente | `mise run test:u5` |

## Qué lleva un tramo, y qué no lleva nunca

**Lleva.** Identificadores —de caso, de turno, de traza, del prompt con su hash—,
nombres del conjunto cerrado —proveedor, modelo, nodo, uso, tipo de error—,
conteos —tokens de entrada y de salida, cláusulas recuperadas y verificadas,
número de intento—, tiempos y costo con su estado.

**No lleva nunca.** El texto del asegurado, la respuesta del modelo, el contenido
de una cláusula, el prompt completo, ninguna clave de proveedor, ni la clave del
navegador sin resumir.

**Por qué esa lista y no "todo redactado".** La redacción protege lo que sale, y
esta unidad la aplica a toda exportación (BR6.5). Pero un tramo que no lleva
texto no necesita que la redacción funcione para ser seguro. Es defensa en
profundidad y cuesta cero: los cinco atributos que los criterios piden son todos
números y nombres.

## Los tres niveles, y por qué son tres

| Nivel | Qué responde | Sin él |
| --- | --- | --- |
| Turno | Cuánto tardó y cuánto costó responderle a esta persona esta vez | No se puede publicar una latencia por idioma ni un costo por caso |
| Nodo | Qué parte del turno se llevó el tiempo y el dinero | Se sabe que el turno fue caro y no por qué |
| Llamada a proveedor | Qué modelo, cuántos tokens, cuánto tardó y a qué precio | El costo por caso sería una estimación, no una medición |

Los tres van anidados: la llamada dentro del nodo, el nodo dentro del turno. La
ruta que recorrió el grafo, la pausa hacia la bandeja con su hora y la
reanudación con quién decidió viven en la traza del **mismo** caso, no en trazas
separadas que alguien tenga que coser.

## Una grafía para los nodos, en cuatro sitios

`intake`, `policy_verification`, `decision` y `compliance`. El mismo token nombra
el directorio del módulo, el valor del enum de transición, el nombre del tramo y
la etiqueta por nodo del reporte de evaluaciones y del panel. Cuatro grafías del
mismo nodo obligarían a traducir entre la traza, el reporte y el código cada vez
que alguien mira un fallo, que es justo el momento en que nadie quiere traducir
nada.

## El resumen de traza, y su plazo

Lo que el visitante ve junto a una respuesta del chat: por qué nodos pasó,
cuántas cláusulas recuperó y verificó, cuánto tardó y cuánto costó.

- Nace en `recording` cuando la respuesta sale, y eso es una respuesta y no un
  hueco: la interfaz muestra "registrándose".
- Pasa a `ready` cuando el rastro llega completo, o a `lost` a los **diez
  segundos**. El plazo está atado a la meta del chat, que es p95 menor que 3 s
  del envío a la primera palabra: diez segundos son más del triple de la
  respuesta entera, así que un resumen que no llegó no está llegando tarde.
- Solo se le muestra al navegador que lo produjo. A cualquier otro responde
  igual que si no existiera.

## La alerta

Una sola, y sale una sola vez: al cruzar los 3 USD acumulados de la ventana.

- **Qué la dispara.** El incremento del acumulado que lo lleva de menos de la
  alerta a igual o más, con la marca de enviada vacía.
- **Qué escribe.** La marca de enviada, en la misma transacción. Que exista es lo
  que impide la segunda.
- **Qué dice.** Cuánto lleva gastado, cuánto queda del techo, cuántos días quedan
  de la ventana y cuántas llamadas no se pudieron medir. La última cifra va
  porque un acumulado con veinte llamadas sin precio no significa lo mismo que
  uno sin ninguna.
- **Por dónde sale.** Lo fija el intent `infra` (PA-10). Esta unidad emite el
  evento; quién lo entrega no es suyo. La alerta de prueba del checklist del
  segundo día tiene que llegar por ese mismo canal, para que el día que importe
  ya se sepa que funciona.

**Lo que no se alerta.** El techo alcanzado no emite alerta: emite una conducta
—el carril público se cierra y la consola lo dice con el texto del catálogo—.
Alertar de algo que el sistema ya resolvió solo por sí mismo es ruido, y el ruido
es cómo una alerta deja de leerse.

## Sources

- `<record>/inception/requirements-analysis/requirements.md` — FR10.1, FR10.2,
  FR10.3, FR10.4, NFR4 (la meta del chat que fija el plazo de `lost`), NFR11
- `<record>/inception/user-stories/stories.md` — US4.8 con AC4.8.1 a AC4.8.5;
  US4.12 con AC4.12.1, AC4.12.2 y AC4.12.4
- `<record>/inception/contract-design/contract-summary.md` — C-23, C-13
- `<record>/construction/u5-provider-platform/functional-design/rules.md` —
  BR2.5, BR6.1 a BR6.7, BR7.3
- `aidlc/spaces/default/memory/team.md` — la convención 3, una sola grafía para
  los cuatro nodos
- `<record>/construction/u5-provider-platform/nfr-requirements/nfr-requirements-questions.md`
  — Q4

## Assumptions & Open Questions

- El destino público de las trazas y el canal de la alerta los decide el intent
  `infra` (PA-10). En local, el backend de trazas corre con los servicios del
  repositorio y su endpoint ya es una variable opcional: sin él, el aplicativo
  funciona y los resúmenes se declaran perdidos.
- La estrategia de muestreo no se fija aquí. A este volumen —una demostración de
  portafolio con cupos diarios de un dígito— se traza todo, y muestrear
  introduciría una fuente de error en cifras que se publican. Si el volumen
  cambiara, es una decisión del intent `infra` con su medición.
- La retención de las trazas exportadas la fija el intent `infra`. Lo que esta
  unidad sí acota es lo que guarda: los resúmenes son dato de visitante y los
  borra el reinicio nocturno.
