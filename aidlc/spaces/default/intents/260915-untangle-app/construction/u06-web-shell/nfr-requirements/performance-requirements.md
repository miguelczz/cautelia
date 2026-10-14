# Requisitos de rendimiento — U6 `web-shell`

U6 no tiene un camino caliente que se mida en milisegundos por turno: no llama a
ningún modelo ni guarda ningún caso. Lo que sí tiene son tres esperas que ve una
persona —la página de espera con la instancia dormida, la salud que decide si se
muestra, y el primer dibujo del inicio— y una que ve quien construye: el tiempo
que el arnés de accesibilidad le agrega a la compuerta.

Las respuestas de `nfr-requirements-questions.md` se aplican tal como quedaron:
los 3 segundos se miden en un teléfono de gama media con red lenta (Q2) y el
arnés tiene un presupuesto de 4 minutos (Q3).

## Objetivos medibles

**Los comandos `mise run test:u6` y `mise run a11y` no existen todavía**: los
crea la generación de código de esta unidad y los declara su diseño de
infraestructura, igual que U4 y U5 declararon los suyos.

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| NFR16.3 | Desde que empieza la navegación hasta que el título de la página de espera está pintado, con el proceso respondiendo 503, en teléfono de gama media emulado (red 4G lenta y CPU cuatro veces más lenta) | **Menos de 3 segundos** | `mise run a11y` (escenario de espera) |
| NFR16.4 | Respuesta de la salud de listo, con la base y las sondas de las superficies montadas | **1 segundo o menos en p95** (C-02) | `mise run test:u6` |
| PERF-U6.1 | Peso comprimido de todo lo que el navegador descarga antes de pintar la página de espera: HTML, JavaScript, CSS y la fuente del cuerpo de texto | **200 KB o menos** | `mise run a11y` (lee el tamaño de las respuestas de ese escenario) |
| PERF-U6.2 | Desde que empieza la navegación hasta que el inicio muestra sus tres filas, con el proceso listo, en el mismo perfil de teléfono | **4 segundos o menos** | `mise run a11y` (escenario del inicio) |
| PERF-U6.3 | Duración del paso completo del arnés de accesibilidad en el flujo de integración continua | **6 minutos o menos** (decisión de Miguel del 2026-10-07; antes 4), publicada en cada corrida | `mise run a11y`, cronometrado por el guion de verificación |
| PERF-U6.4 | Trabajo que la telemetría de activación le agrega al turno que informa un hito | **Una transacción de dos escrituras de fila única**; su fallo no demora el turno (BR8.3) | `mise run test:u6` |

## Por qué caen donde caen

**Los 3 segundos no se negocian; lo que se presupuesta es lo que los hace
posibles.** NFR16.3 es el criterio de AC5.16.4 medido como pidió Q2. El perfil de red es el que
Lighthouse usa para teléfono y llama "4G lenta": 1,6 Mbps de bajada, del orden de
200 KB por segundo, con 150 ms de latencia por ida y vuelta. A ese ritmo, 200 KB
tardan cerca de un segundo en llegar, y el resto de los 3 segundos se va en las
idas y vueltas y en ejecutar el código con la CPU ralentizada. De ahí PERF-U6.1: 200 KB comprimidos, con
el cuerpo de texto en la fuente del sistema de diseño y las otras dos familias
cargadas después, cuando hacen falta. Si el presupuesto no alcanza, lo que se
revisa es qué viaja en la primera carga, no el umbral.

**La salud, en 1 segundo.** Es el presupuesto que C-02 ya fija. Las sondas de las
superficies corren en paralelo y cada una tiene su tiempo máximo (BR5.2), así que
agregar una superficie no suma su tiempo al de las demás.

**El inicio, en 4 segundos.** No es un criterio del PRD: es el objetivo propio de
esta unidad para que el primer contacto con la demo no sea peor que la página de
espera. Un segundo más que ella, porque además de pintar tiene que pedir el
directorio del sitio.

**El arnés, en 4 minutos.** Es la respuesta a Q3. Lo que más pesa es la
combinación de pantallas por dos idiomas y dos modos (FD-U6-7). Pasarlo no
autoriza recortar idiomas ni modos: se paraleliza por pantalla o se sube el
presupuesto con una decisión escrita.

**Lo que esta unidad no promete.** No declara la latencia del chat (NFR4, de
U13) ni la de la voz (NFR1 y NFR2, de U16): U6 dibuja el marco, pero el tiempo
de una respuesta es de quien la produce.

## Recursos

- **Navegador:** ninguna caché persistente de datos (BR3.5). La caché en memoria
  de la pestaña se vacía al cerrarla.
- **Proceso:** los archivos compilados se sirven desde el disco del propio
  proceso con caché de navegador larga para los que llevan huella (BR6.3); no hay
  procesamiento por petición más allá de las cabeceras.
- **Base de datos:** dos tablas nuevas de activación, de crecimiento acotado: el
  avance se borra cada noche y el conteo diario suma a lo sumo tres filas por
  aseguradora y día (1.095 filas por aseguradora y año).

## Sources

- `../functional-design/functional-spec.md` — flujos F1, F2, F7, F9 y F10.
- `../functional-design/rules.md` — BR3.5, BR5.1, BR5.2, BR6.3 y BR8.3.
- `../../../inception/requirements-analysis/requirements.md` — NFR16.
- `../../../inception/contract-design/contract-summary.md` — C-02 (presupuesto de
  1 segundo).
- `../../../inception/refined-mockups/design-system-mapping.md` — criterio de
  peso inicial para la página de espera.
- `../../../inception/user-stories/stories.md` — AC5.16.4 y US1.33.

## Assumptions & Open Questions

- **La cuenta de 200 KB en un segundo es orden de magnitud**, no una medición:
  sale del perfil de red para teléfono que documenta Lighthouse. El número que
  cuenta es el que produce `mise run a11y` en su escenario de espera.
- **NFR16.3 mide la mitad que U6 controla.** Con la instancia dormida de verdad,
  el tiempo también depende de que los estáticos vivan en un hospedaje que no se
  duerme (OQ4, intent `infra`); aquí se mide con el proceso despierto
  respondiendo 503, que es lo que la interfaz ve en ese caso.
