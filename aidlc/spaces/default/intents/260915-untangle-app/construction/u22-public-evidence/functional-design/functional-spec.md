# Especificación funcional — U22 `public-evidence`

La evidencia. Todo lo que este proyecto afirma tiene que poder comprobarse sin
creerle a nadie, y esta unidad es donde eso se mira: las cinco cifras con su fecha
y su commit, el gasto, y las dos secciones del README que se generan solas.

Su valor no está en lo que construye —son dos pantallas y un comando— sino en lo
que impide: que una cifra del video o del README se haya escrito a mano.

## Sources

- `functional-design-questions.md` — las tres respuestas de Miguel (1A, 2A, 3A) y
  las siete decisiones
- `../../../inception/user-stories/stories.md` — US4.16, US4.1 y AC5.14.1
- `../../../inception/delivery-planning/bolt-plan.md` — B17 y su definición de
  terminado
- El código: `evals/gates/` (la línea base y sus métricas), `telemetry/spend/`
  (`spend_by_case`, `spend_by_provider`, `spend_by_month`, `load_window`),
  `app/frontend/src/pages/` (las seis pantallas construidas)

## Assumptions & Open Questions

None.

---

## Flujo 1 — Las cinco cifras (US4.16)

Jordan abre el panel de cifras sin credencial.

1. El panel lee la **línea base vigente versionada** y muestra cinco cifras, cada
   una con su fecha, su commit y el enlace a la corrida que la produjo.
2. Las que se miden por idioma se muestran **lado a lado**, español e inglés,
   nunca un promedio combinado.
3. Las latencias dicen, por idioma, **entre qué eventos** se miden, sobre qué
   conjunto, y con p50 y p95.
4. Los casos por aseguradora son **recuentos**: cuántos, no cuáles.

**De dónde sale cada una, que es la mitad del diseño:**

| Cifra | De dónde | Hoy |
| --- | --- | --- |
| Completitud del caso | Tasa por criterio de la línea base | No medida: no hay línea base |
| Precisión de citación | Tasa por criterio de la línea base | No medida: no hay línea base |
| Latencias (turno y parada) | Los eventos de traza de la voz y del chat | **No medidas**: se miden por hito contra proveedores de verdad |
| Costo por caso | El registro de gasto | Disponible |
| Casos por aseguradora | Recuento en la base | Disponible |

**Tres de las cinco nacen como "no medida", y eso no es un defecto: es el
criterio.** AC4.16.4 pide exactamente eso —la causa escrita, nunca vacía ni en
cero— y es lo que separa este panel de una diapositiva.

---

## Flujo 2 — El gasto (AC5.14.1)

Miguel entra con credencial, igual que a la bandeja.

1. Ve el costo **por caso**, por proveedor y por mes, y el acumulado de la ventana
   de 90 días que empezó el 2026-09-16.
2. La alerta de los 3 USD y el corte de los 5 **ya existen** —los construyeron U15
   y U16—; aquí solo se muestran el acumulado y cuánto queda.

**Por qué con credencial y no público** (respuesta 1A): "costo por caso" es una
fila por caso, y ninguna superficie pública del aplicativo muestra identificadores
de casos de visitantes. La cifra que sí es evidencia —el costo por caso
promedio— está entre las cinco del panel público.

---

## Flujo 3 — Las dos secciones generadas del README (US4.1)

1. Un comando **regenera** dos secciones del README: "Cómo falla" y las cinco cifras.
   Cada una tiene su fuente, y son dos porque una no puede traer el dato de la otra:
   - las **cinco cifras** salen de la línea base vigente, por el mismo camino que el
     panel (`build_snapshot`);
   - **"Cómo falla"** sale del **resumen de la última corrida completa**, un archivo
     versionado que escribe el comando que publica la línea base, en verde y en rojo
     (FD-U22-10, BR4.3).
2. "Cómo falla" agrupa los fallos por la taxonomía de causa raíz del PRD, nombra
   los **identificadores de los casos** y cita el commit y la corrida de ese resumen.
   Los casos no medidos van aparte, con su causa, y nunca se cuentan como fallos.
3. El mismo comando, en modo comprobación, **falla** nombrando la sección si lo
   publicado no coincide con lo que producen sus fuentes. Corre en cada entrega
   (respuesta 2A).

**Sin línea base y sin resumen, cada sección dice "no medida" con su causa**, y el
chequeo compara contra eso: no se pone rojo por no haber medido todavía.

**Por qué el resumen y no la línea base.** BR2.1 rechaza publicar una línea base con
un solo caso en rojo, y hace bien: una línea base es una corrida verde. Leyéndola,
"Cómo falla" diría siempre "No case failed", y hoy el reporte tiene 42 de 100 casos
que fallan porque la conducta que miden todavía no existe. El resumen es lo que
AC4.1.3 llama "el último reporte de evaluación", reducido a lo que la sección necesita
y versionado: el reporte entero vive en `tmp/` a propósito.

**Las otras seis secciones del README no son de esta unidad**: las escribe Miguel
en la semana 11.

---

## Flujo 4 — Lo que el panel no puede decir

Es la mitad que protege el principio, y por eso tiene flujo propio.

- Ninguna cifra sin su golden set detrás.
- Ninguna capacidad sin construir aparece como disponible.
- Ningún identificador de caso de visitante en la superficie pública.
- Ninguna cifra en cero donde lo cierto es "no medida".

---

## Lo que esta unidad no construye

- **Las seis secciones narrativas del README**: semana 11, de Miguel.
- **La alerta y el corte del techo**: ya están en U15 y U16.
- **Publicar los paneles**: es la pasada de publicación, con su checklist del
  segundo día. Esta unidad los construye y los deja probados.
- **El video y la landing**: no son unidades.

## Resumen de reglas (vista derivada)

Las reglas están en `rules.md`. Dos llevan `[bloquea]`: que ninguna cifra del panel
público lleve identificadores de casos de visitantes, y que ninguna cifra sin medir
aparezca como cero.

## Modelo de entidades (vista derivada)

Esta unidad añade **una** entidad, `MetricsSnapshot`, que es la vista de lectura de
la línea base. Los detalles están en `entities.md`.
