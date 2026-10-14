# Requisitos de escalabilidad — U1 `workspace`

Esta unidad no atiende carga concurrente: no hay usuarios simultáneos, ni
peticiones por segundo, ni auto-escalado. Lo que sí crece con el tiempo, y por
eso se mide, es **el conjunto de casos de prueba y el repositorio**.

**Fuentes consumidas.** `../functional-design/functional-spec.md` (Flujo 1 paso 3
y la definición de subconjunto), `../functional-design/rules.md` (BR1.6, BR1.7 y
BR1.9), `../../../inception/requirements-analysis/requirements.md` (FR11.1 y
NFR17), `../../../inception/contract-design/contract-summary.md` (C-27, un
archivo por caso) y `../../../../codekb/untangle/technology-stack.md`.

## Qué crece y hasta dónde

| Dimensión | Hoy | Al terminar el proyecto | Qué pasa cuando crece |
| --- | --- | --- | --- |
| Casos de golden set | 0 | Unos 130 entre los conjuntos que corren por entrega (DS-2 60, DS-3 40, DS-6 30) | La corrida completa deja de caber en el presupuesto de tiempo; la compuerta pasa a correr el **subconjunto declarado**, nunca se apaga |
| Archivos del corpus generado | 0 | Tres corpus con sus pólizas y relaciones | El manifiesto de hashes crece; la ingesta la hace U8, no U1 |
| Tamaño del historial del repositorio | Solo la landing | Con corpus, datos generados y líneas base versionadas | El escaneo del historial completo se vuelve caro: por eso corre por hito y no en cada corrida (decisión Q3) |
| Minutos de integración continua | 0 | Limitados a 2.000 al mes | Filtros de rutas y cancelación de corridas anteriores; **los filtros nunca apagan la compuerta de evaluaciones** |

## Estrategia

- **No se escala horizontalmente nada**: la corrida es un proceso, y su unidad de
  crecimiento son los casos, no las máquinas.
- **La válvula es el subconjunto declarado**, no bajar el umbral ni saltar casos:
  la corrida completa pasa a ser obligatoria por hito y antes de publicar
  cualquier línea base.
- **Qué se degrada primero** cuando el presupuesto aprieta: la corrida completa
  se convierte en subconjunto. Lo que nunca se degrada: las compuertas duras y
  la publicación de la duración real.

## Lo que no le toca a esta unidad

La concurrencia del proceso servido, los límites por visitante y el gasto por
llamada son de U5, U13 y U17. U1 no tiene tráfico que escalar.
