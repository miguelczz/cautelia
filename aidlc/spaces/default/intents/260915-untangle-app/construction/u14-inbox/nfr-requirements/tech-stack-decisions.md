# Decisiones de stack — U14 `inbox`

**Ninguna dependencia nueva de runtime.** Es la decisión entera, y no es
comodidad: cada dependencia nueva se justifica en una línea —qué hace, por qué no
la biblioteca estándar, y su licencia— y aquí no hay ninguna que justificar.

## Lo que se reúsa, y de quién

| Pieza | De quién | Por qué no se escribe otra |
| --- | --- | --- |
| Rutas HTTP y su esquema publicado | U6 (C-01, C-02, C-28) | La bandeja añade rutas al mismo servidor; un segundo estilo de error sería un segundo vocabulario que la interfaz tendría que aprender |
| Cola de eventos y flujo SSE | **U13** (`chat/wire.py`) | El mismo mecanismo: una cola por consumidor, latido, `retry:` y reanudación. Escribir otra sería repetir los dos defectos que U13 ya encontró —el flujo que no dice nada al conectar y la cola que descarta lo encolado al cerrarse— |
| Sesión de base de datos por aseguradora | U2 | Es el punto único; abrir una conexión fuera de él está prohibido |
| Caso, campos, transcripción e historial | U4 (C-12) | La bandeja lee y corrige por su API; no toca sus tablas |
| Citas verificadas, regla, controles, traza | U8, U9, U10, U5 | Cada bloque lo guarda su dueña |
| Reanudación del grafo | U12 (C-14) | Por su puerto, sin importar el módulo del runtime |
| Marco, idioma, modo, páginas de estado | U6 | Las tres pantallas viven dentro del mismo armazón |
| Cita expandible con su cláusula etiquetada | **U13** | Es el mismo dato con la misma regla: el texto literal en su idioma, sin traducir. Dos implementaciones serían dos formas de mostrarlo que un día difieren |

## Lo que sí es nuevo

- Dos tablas: `inbox_event` y `decision_receipt`, con su migración aditiva y su
  política de aislamiento.
- Un módulo `untangle/inbox/` en el backend y `app/frontend/src/pages/inbox/`
  más la pantalla del visitante en el frontend.
- Una tarea `mise run test:u14` que corre las pruebas de la unidad, igual que
  las unidades anteriores.

## La cola de eventos: reúso con una diferencia

El mecanismo es el de U13, pero **el alcance no**: allí una cola es de una
conversación y aquí es de una aseguradora, y el identificador del evento tiene
que ser creciente **por aseguradora** para que `Last-Event-ID` signifique algo.
Un identificador global dejaría huecos en la secuencia que ve un inquilino.

Esa diferencia se resuelve donde debe: la pieza compartida es el transporte —la
cola, el latido, la reanudación— y la numeración es de cada dueño. Si al
construirlo resulta que la pieza de U13 no admite esa separación, se sube a un
módulo común antes de copiarla, no después.
