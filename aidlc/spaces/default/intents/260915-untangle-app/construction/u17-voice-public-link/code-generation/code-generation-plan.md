# Plan de generación de código — U17 `voice-public-link`

Dos tandas, repartidas por **dónde puede correr cada una**. Y una advertencia de tamaño:
leer el código antes de planear mostró que **US5.11 es cableado, no lógica nueva**.

| Tanda | Qué | Dónde | Por qué ahí |
| --- | --- | --- | --- |
| 1 | La decisión pura de los dos carriles y la ventana de retoma, los dos campos de configuración, la tabla de topes, y los avisos públicos de la consola con la disponibilidad servida como dato | **Nube** | Todo es lógica pura con reloj inyectado y acumulados forzados, más interfaz con respuestas declaradas. Ni base ni proveedores |
| 2 | Los contadores, el cableado de la voz, la disponibilidad que deja de servir nulos, y la retoma contra sesiones reales | Aquí | Los contadores necesitan base; el cableado necesita la raíz de composición y sus pruebas de integración |

**En serie.** La tanda 2 enchufa lo que la 1 decide.

---

## Tanda 1 — Las decisiones y los avisos *(nube)*

1. `calls_per_visitor_day` y `calls_per_site_day` en `CallConfig`, aditivos y con
   omisión, con su validador si hace falta.
2. La **decisión pura** de admisión: configuración + contadores + reloj → admitir, o el
   código del carril que rechazó, o el caso que retoma. Con la asimetría de la retoma
   escrita en la decisión y no adivinada.
3. La **tabla versionada de topes del proveedor**, con su modelo y su cargador: una fila
   por proveedor de pago, con su tope, dónde se configuró y la fecha de su última
   comprobación. Un archivo sin fecha no carga.
4. Los avisos de la consola que solo dependen de la disponibilidad: los dos límites
   dichos antes del micrófono, el motivo cuando no hay voz con la oferta del chat, el
   aviso de la voz de respaldo, la póliza de ejemplo y qué probar.
5. Las claves del catálogo que falten, en los dos idiomas y con paridad.

**Pruebas.** Los bordes de cada carril con los contadores forzados; la retoma a los 14
min 59 s y a los 15 min 1 s; que una retoma no gaste la llamada del día y sí cuente
contra el sitio; que la decisión no mire el reloj del proceso; que la consola no pida el
micrófono antes de tener la disponibilidad; que un archivo de topes sin fecha de
comprobación no cargue; y el presupuesto cronometrado de PERF-U17.1.

**Reglas que cierra:** BR1.2, BR1.3, BR1.5, BR2.3, BR3.1, BR4.1.

---

## Tanda 2 — Los contadores y el cable *(aquí)*

1. Los dos contadores, con la asimetría de la retoma.
2. `quota.voice_mode` cableada: desaparecen los cuatro `VoiceMode.PRIMARY` escritos a
   mano del camino de una llamada pública.
3. La disponibilidad deja de servir los dos carriles en nulo.
4. El estado, el tiempo y el botón de colgar siempre visibles; la latencia del último
   turno cuadrada con la traza; y el final de la llamada con su caso, su estado y su
   enlace.

**Pruebas.** Que ninguna llamada se abra con un carril agotado, contra la base; que no
quede ningún `VoiceMode` escrito a mano en ese camino; que la latencia que muestra la
consola sea la de los eventos de la traza de ese turno.

**Reglas que cierra:** BR1.1, BR1.4, BR2.1, BR2.2, BR2.4, BR3.2, BR3.3, BR3.4.

---

## Tareas nuevas

| Tarea | Qué hace |
| --- | --- |
| `test:u17` | Solo las pruebas de esta unidad, incluido el presupuesto cronometrado de PERF-U17.1 |

## Lo que no se toca

- **La llamada y su transporte**: U16.
- **El corte a los tres minutos y el aviso de los treinta segundos**: ya existen.
- **La decisión de la voz**: existe y es pura; se cablea.
- **El techo de gasto y su alerta**: U5 y U15.
