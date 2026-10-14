# Requisitos de escala — U6 `web-shell`

Untangle es una demostración de portafolio con un solo proceso, y U6 no cambia
eso. Lo que escala en esta unidad no es el tráfico sino **el número de pantallas
y superficies** que las demás unidades le agregan al marco, y eso sí tiene que
crecer sin que nadie toque U6.

**`mise run test:u6` y `mise run a11y` no existen todavía**: los crea la
generación de código de esta unidad.

## Carga esperada

| Dimensión | Hoy | Al publicar (semana 7) | Mecanismo |
| --- | --- | --- | --- |
| Visitantes simultáneos | 1 (local) | Decenas en un pico tras una publicación en LinkedIn | Estáticos con caché larga (BR6.3); las dos rutas públicas no llaman a proveedores |
| Chequeos de salud | 0 | 1 cada 5 minutos (8.640 al mes) | Salud de 1 s sin gasto (NFR16.4, NFR16.6) |
| Pantallas registradas en el arnés | 8 (inicio y siete páginas de estado) | Del orden de 20, con U13, U14, U16 y U22 | Registro que cada unidad extiende (BR7.1) |
| Superficies montadas | 0 | Hasta 7, las de la lista cerrada de `SurfaceSpec` | Registro de módulos de la raíz de composición (F8) |
| Filas de activación | 0 | Avance: una por sesión e hito, borradas cada noche; conteo: 3 por aseguradora y día | Crecimiento acotado (`performance-requirements.md`) |

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| SCALE-U6.1 | Archivos de U6 que hay que tocar para montar una superficie nueva y que aparezca en el inicio y en la salud | **Cero** | `mise run test:u6` (monta una superficie de prueba y comprueba inicio y salud sin cambiar U6) |
| SCALE-U6.2 | Tiempo del arnés con las pantallas que existan | **4 minutos o menos** (PERF-U6.3); al pasarlo se paraleliza por pantalla o se sube con decisión escrita, nunca se recortan idiomas ni modos | `mise run a11y` |
| SCALE-U6.3 | Sondas de las superficies en la salud | **En paralelo**: la salud tarda lo que la sonda más lenta, no la suma | `mise run test:u6` |

## Lo que no se escala aquí

No hay réplicas, ni balanceo, ni caché distribuida: un solo proceso sirve la
demo, y decidir otra cosa sería del intent `infra` con datos que hoy no existen.
Si el pico de una publicación llegara a saturar el proceso, la página de espera
y la salud siguen siendo las primeras en responder, porque no tocan proveedores
ni hacen trabajo por petición más allá de las cabeceras.

## Sources

- `../functional-design/functional-spec.md` — F7, F8 y F9.
- `../functional-design/rules.md` — BR5.2, BR6.3 y BR7.1.
- `performance-requirements.md` y `reliability-requirements.md` de esta etapa.
- `../../../inception/delivery-planning/bolt-plan.md` — calendario de referencia
  (publicación del enlace en la semana 7).

## Assumptions & Open Questions

- **"Decenas de visitantes en un pico" es un supuesto**, no un dato: no hay
  tráfico medido todavía. Se revisa con la telemetría de activación después de la
  primera publicación.
