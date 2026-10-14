# Requisitos de observabilidad — U12 `graph-runtime`

Esta unidad es la que puede decir qué pasó en un caso, porque es la única que ve el
turno entero: qué nodo corrió, en qué ritmo, cuántas veces, cuánto tardó y con qué
error. Si su traza está incompleta, ninguna métrica publicada del proyecto tiene de
dónde salir.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| OBS-U12.1 | Turnos sin su tramo en la traza | **Exactamente 0** | Tarea nueva `mise run test:u12` |
| OBS-U12.2 | Ejecuciones de nodo sin su fila `NodeRun` con nodo, ritmo, intento y desenlace | **Exactamente 0** | Tarea nueva `mise run test:u12` |
| OBS-U12.3 | Fallos de nodo sin su tipo de error de la taxonomía cerrada en la traza | **Exactamente 0** | Tarea nueva `mise run test:u12`, con fallos inyectados |
| OBS-U12.4 | Nombres de nodo en la traza que no coinciden con el directorio del módulo | **Exactamente 0** | `mise run test:u12` |
| OBS-U12.5 | Latencia por nodo y por turno, p50 y p95, publicadas por idioma | **Se publican desde la primera corrida** | `mise run evals:gate` |
| OBS-U12.6 | Sesiones abandonadas sin su motivo en la traza | **Exactamente 0** | Tarea nueva `mise run test:u12` |
| NFR11.12 | Datos personales sin redactar en los tramos que esta unidad emite (NFR11, dueña U3) | **Exactamente 0** | `mise run redaction:report` |

## Los cuatro ceros

Cada uno cierra una forma distinta de quedarse sin saber:

- **Un turno sin tramo** es un turno que no se puede explicar. La latencia
  publicada del proyecto sale de estos tramos; uno que falte la sesga sin avisar.
- **Una ejecución sin fila** es trabajo que nadie puede relanzar: el barrido toma lo
  pendiente de esta tabla, así que lo que no está aquí no existe para él (BR5.4).
- **Un fallo sin su tipo** obliga a leer el log a mano para saber si fue una cuota,
  una caída o una respuesta mal formada, y esas tres se arreglan de forma distinta.
- **Un nombre de nodo que no coincide** con el directorio del módulo obliga a
  traducir entre la traza, el reporte y el código, y esa traducción se hace mal una
  vez y se arrastra (convención 3).

## Lo que no es de esta unidad

El registro de costo y de tokens por llamada al proveedor es de **U5** (C-23 y
C-17): U12 abre el tramo del turno y del nodo, y la llamada al proveedor cuelga de
él con su propio registro. Publicar el costo por caso es de **U22**.

## Sources

- `../functional-design/rules.md` — BR5.3, BR6.2, BR3.3.
- `../../../inception/user-stories/stories.md` — AC4.8.1, los tres niveles de la
  traza.
- `../../../inception/contract-design/contract-summary.md` — C-23 (eventos de uso) y
  C-17 (la contabilidad).
- `../../../inception/units-generation/unit-of-work.md` — la tabla de metas: NFR11
  es de U3, NFR14 de U5.

## Assumptions & Open Questions

- **[Assumption]** La traza por turno se abre en esta unidad y no en el canal. Si
  algún día el canal necesitara abrirla antes —para medir lo que tarda el transporte
  antes de llegar al grafo—, el tramo del turno pasa a ser suyo y el de esta unidad
  cuelga de él; nada de lo medido aquí cambia de significado.
