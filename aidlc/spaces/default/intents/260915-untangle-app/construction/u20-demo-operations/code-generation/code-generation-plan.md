# Plan de generación de código — U20 `demo-operations`

Dos tandas, repartidas por **dónde puede correr cada una**. Aquí el reparto es más
marcado que en las otras unidades: casi todo lo que esta unidad hace toca la base, y lo
que no es exactamente lo que más conviene probar con dobles.

| Tanda | Qué | Dónde | Por qué ahí |
| --- | --- | --- | --- |
| 1 | La validación de la carpeta, la orquestación del reinicio sobre el contrato con dobles, `ResetRun` y la regla de las 24 horas | **Nube** | Todo es lógica pura con reloj inyectado y purgadores dobles. El camino del fallo se prueba mejor así que contra una base de verdad, donde habría que romperla |
| 2 | Las dos operaciones de verdad: aprovisionar con ingesta y siembra, el reinicio contra los nueve purgadores reales, el backend de trazas y el aviso a las conversaciones vivas | Aquí | Base, motor de contenedores, corpus ingerido y backend de trazas |

**En serie.** La tanda 2 enchufa lo que la 1 decide.

---

## Tanda 1 — La validación, la orquestación y su registro *(nube)*

1. **La validación de la carpeta de una aseguradora**: nombre, idioma, voz, reglas,
   políticas, corpus, póliza de ejemplo y personas. Devuelve **todas** las faltas, cada
   una con su archivo y su campo, y no la primera.
2. **La orquestación del reinicio**, pura sobre `VisitorDataPurger`: recibe los
   purgadores, el reloj y el corte; los llama en orden; devuelve qué borró cada uno y
   cuál falló. **No abre sesión y no escribe ninguna sentencia de borrado.**
3. **`ResetRun`** con sus tres resultados —`succeeded`, `failed`, `partial`— y una fila
   por purgador.
4. **La regla de las 24 horas**: una función pura que, dado el último reinicio exitoso y
   el reloj, dice si las superficies públicas aceptan **casos nuevos**. Lo ya abierto no
   entra en esa decisión y termina normalmente (BR3.3).
5. Las claves del catálogo que falten: el aviso a una conversación reiniciada y el
   mensaje de las superficies cerradas, en los dos idiomas.

**Pruebas.** Una carpeta a la que le falten dos cosas reporta las dos, con archivo y
campo; un purgador doble que levanta deja la corrida en `partial` y nombrado en el
registro; `partial` no se colapsa ni en `failed` ni en `succeeded`; repetir la corrida
tras un parcial no empeora el estado; **tres intentos fallidos seguidos no reinician el
contador de 24 horas**; y la orquestación no mira el reloj del proceso.

**Reglas que cierra:** BR1.1, BR2.4, BR3.1, BR3.2, BR3.3.

---

## Tanda 2 — Las dos operaciones de verdad *(aquí)*

1. El comando de aprovisionar: validar, crear, invocar `corpus:ingest`, sembrar un caso
   en cada estado, idempotente.
2. El reinicio contra los nueve purgadores registrados, incluido el backend de trazas.
3. El aviso a las conversaciones vivas y que su mensaje siguiente abra un caso nuevo.
4. Que ningún número de caso ni enlace firmado se repita.
5. La batería de humo contra una cuarta aseguradora de prueba que no se publica.
6. **`demo:reset` como último paso del despliegue.** Sin ningún reinicio exitoso conocido
   las superficies cierran, y eso es correcto: tratar «ninguna corrida» como abierto sería
   indistinguible de «el reinicio lleva tres días sin correr». Sobre una base recién
   creada no hay nada que borrar, la corrida sale `succeeded` en milisegundos y deja el
   reloj en marcha. Es una línea del checklist del segundo día, no una excepción en la
   regla.

**Pruebas.** La base sembrada con datos de visitante en cada tabla marcada, y una
consulta por tabla después; la ventana de presupuesto y el libro mayor antes y después;
el audio inexistente antes y después; y la aseguradora nueva pasando chat, cobertura,
bandeja y aislamiento.

**Reglas que cierra:** BR1.2, BR1.3, BR1.4, BR2.1, BR2.2, BR2.3, BR2.5, BR2.6.

---

## Tareas nuevas

| Tarea | Qué hace |
| --- | --- |
| `tenant:provision` | Valida una carpeta de aseguradora y la aprovisiona, con su ingesta y su siembra |
| `demo:reset` | Corre el reinicio nocturno y deja su registro |
| `test:u20` | Solo las pruebas de esta unidad |

## Lo que no se toca

- **Los nueve purgadores**: se llaman, no se tocan. Lo que cada uno conserva ya está
  decidido y escrito al lado de su línea.
- **`corpus:ingest`**: se invoca.
- **El disparador nocturno**: es del intent `infra`.
- **El generador sintético**: su salida ya está versionada.
