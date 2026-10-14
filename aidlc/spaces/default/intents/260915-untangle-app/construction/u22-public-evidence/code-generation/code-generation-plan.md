# Plan de generación de código — U22 `public-evidence`

Cuatro tandas. La 1 y la 3 fueron a sesiones en la nube y la 2 se hizo aquí; la 4
la añadió la revisión de la 3 y vuelve a la nube. El reparto no es por comodidad:
las que van a la nube son las que no necesitan base de datos, y allá no hay
ninguna.

## El reparto, y por qué

| Tanda | Qué | Dónde | Por qué ahí |
| --- | --- | --- | --- |
| 1 | La lectura de la línea base, las cinco cifras y el panel público | **Nube** | No toca la base: lee un archivo versionado. Mucha superficie mecánica y `pytest` y `vitest` corren allá |
| 2 | El panel de gasto | Aquí | Sus cuatro vistas consultan la base, y las pruebas de aislamiento necesitan dos aseguradoras sembradas |
| 3 | Las dos secciones del README y su chequeo | **Nube** | Ni base ni proveedores: la línea base se siembra escribiendo su archivo |
| 4 | El resumen de la última corrida completa, y «Cómo falla» leyéndolo | **Nube** | Un modelo, su escritor y un cambio en el generador. Nada de base: el resumen se siembra escribiendo su archivo, como la línea base |

El crédito de la nube vence el 5 de noviembre. La tanda 1 fue la que mejor lo
aprovechó: larga, mecánica y encargable de una sola vez.

**La tanda 4 existe porque el diseño estaba mal, no porque la 3 lo estuviera.**
BR4.1 mandaba leer la línea base, y una línea base publicada no puede traer fallos
(BR2.1 las rechaza): «Cómo falla» diría siempre «No case failed». Lo encontró la
tanda 3 y lo decidió Miguel el 2026-09-30 (FD-U22-10, opción B).

---

## Tanda 1 — Las cifras y su panel *(nube)*

1. `evals/evidence/snapshot.py`: leer la línea base vigente y construir
   `MetricsSnapshot` con sus cinco `Figure`. Sin línea base, las cinco salen
   `not_measured` con su causa; con línea base, las dos que salen de sus métricas
   se llenan y las otras tres siguen `not_measured` con la suya (BR1.1, BR1.2).
2. `evals/evidence/api.py`: la superficie pública del módulo, sin lógica.
3. La ruta del servidor que sirve el panel, **sin credencial**, que devuelve solo
   recuentos y nunca identificadores (BR2.1, SEC-U22.1).
4. `app/frontend/src/pages/evidence/`, carpeta nueva: la pantalla, con su tabla por idioma lado a
   lado, sus estados "no medida" con la causa a la vista, y la fecha, el commit y
   el enlace a la corrida en cada cifra (BR1.3, BR1.4, BR1.5).
5. Las claves del catálogo en español y en inglés. Ninguna cadena visible en línea.
6. PERF-U22.1 cronometrado.

**Pruebas.** Sin línea base las cinco cifras salen "no medida" **con causa**; con
una línea base sembrada, las dos que le corresponden se llenan y las otras tres no;
ninguna cifra sale en cero donde no hay medición; el recuento por aseguradora no
trae ningún identificador sembrado; las cifras por idioma nunca se promedian; cada
cifra lleva fecha, commit y enlace; y el presupuesto cronometrado.

**Reglas que cierra:** BR1.1 a BR1.5, BR2.1, BR2.2, SEC-U22.1.

---

## Tanda 2 — El panel de gasto *(aquí)*

1. La ruta con credencial, que responde igual que una ruta inexistente sin ella
   (SEC-U22.2).
2. Las cuatro vistas, sobre las consultas que ya existen: `spend_by_case`,
   `spend_by_provider`, `spend_by_month` y `load_window` (BR3.2).
3. La pantalla, con el acumulado de la ventana y cuánto queda del techo.
4. PERF-U22.2 cronometrado.

**Pruebas.** Sin credencial y con credencial de otra aseguradora se responde lo
mismo; el gasto de una aseguradora no aparece en la otra; el acumulado es de la
ventana de 90 días y no del mes; el panel no decide cortar, solo muestra (BR3.3).

**Reglas que cierra:** BR3.1 a BR3.3, SEC-U22.2, SEC-U22.3.

---

## Tanda 3 — El README que se regenera *(aquí)*

1. El generador de las dos secciones desde la línea base vigente.
2. El modo comprobación, que falla si lo publicado no coincide.
3. Su entrada en el guion de verificación.

**Pruebas.** Con una línea base sembrada con fallos, la sección agrupa por causa
raíz y nombra los identificadores; sin línea base dice "no medida" y el chequeo no
se pone rojo; con el README manipulado a mano, el chequeo falla nombrando la
sección.

**Reglas que cierra:** BR4.1, BR4.2.

---

## Tanda 4 — El resumen de la última corrida completa *(nube)*

1. `LastRunDigest` en `evals/gates/models.py`, con sus tres validadores, y su
   lectura y escritura en `evals/gates/loading.py`.
2. `evals:baseline` lo escribe **siempre**, en verde y en rojo, antes de decidir si
   publica la línea base.
3. «Cómo falla» lo lee en vez de la línea base. Las cinco cifras no cambian.
4. `Baseline.root_causes` se retira, y `build_baseline` deja de llenarlo.

**Pruebas.** Con un resumen sembrado con fallos, la sección agrupa por causa raíz,
nombra los identificadores y cita el commit y la corrida del resumen; los no medidos
van aparte con su causa; sin resumen dice "no medida" con su causa y el chequeo no se
pone rojo; una corrida completa en rojo escribe el resumen y **no** publica línea
base; un resumen que declara subconjunto no se construye.

**Reglas que cierra:** BR4.1 (corregida), BR4.3.

---

## Tareas nuevas

Esta unidad crea estas tareas del archivo de tareas:

| Tarea | Qué hace |
| --- | --- |
| `test:u22` | Solo las pruebas de esta unidad, incluidos los dos presupuestos cronometrados |
| `readme:gen` | Regenera las dos secciones del README desde la línea base vigente |
| `readme:check` | Falla si lo publicado no coincide con lo que producen la línea base vigente y el resumen de la última corrida completa. Entra en el guion de verificación |

## Lo que no se toca

- **La alerta y el corte del techo**: ya están en U15 y U16, con sus pruebas.
- **El reporte de evaluación y la línea base**: son de U21. Aquí solo se leen, con
  una excepción escrita: la tanda 4 añade a `evals:baseline` la escritura del resumen
  de la corrida, y retira el `Baseline.root_causes` que la tanda 3 había añadido.
- **Las seis secciones narrativas del README**: las escribe Miguel en la semana 11.
- **Publicar las pantallas**: es la pasada de publicación.
