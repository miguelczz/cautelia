# Diseño de rendimiento — U1 `workspace`

Cómo se construye para que alguien llegue del clon al reporte en menos de quince
minutos, y para que la corrida de evaluaciones tarde lo que dice que tarda.

**Fuentes consumidas.** `../nfr-requirements/performance-requirements.md`
(NFR21.1, NFR21.2, NFR17.1 y el presupuesto por paso),
`../nfr-requirements/tech-stack-decisions.md` (lo que U1 instala y NFR18),
`../functional-design/functional-spec.md` (Flujo 1 y sus ocho pasos),
`../functional-design/rules.md` (BR1.1, BR1.3, BR1.6, BR1.7, BR1.8),
`../../../inception/contract-design/contract-summary.md` (C-24 raíz de
composición, C-27 casos y reporte, C-28 contratos generados) y
`nfr-design-questions.md` (decisiones Q3 y Q4 de esta etapa).

## De qué trata el rendimiento en esta unidad

U1 no atiende peticiones. No hay percentiles de latencia, no hay peticiones por
segundo y no hay usuarios concurrentes. Lo que sí hay son **dos relojes**, y todo
el diseño de esta sección existe para que los dos den un número que se pueda
publicar:

| Reloj | Qué mide | Meta |
| --- | --- | --- |
| El del recién llegado | Clon → reporte, en máquina limpia | Menos de 15 minutos (NFR21.1, NFR21.2) |
| El de la corrida | Duración de la corrida de evaluación de texto | Se mide y se publica siempre (NFR17.1); la meta de 10 minutos la fija U21 |

## Cómo se construye el camino de los 15 minutos

### Un solo comando, y lo que hace por dentro

BR1.1 exige un solo comando, invocado igual desde el archivo de tareas, el README
y la tubería. El diseño lo cumple con **una tarea de arranque que encadena las
demás**, y no con un guion aparte que duplique la lista:

```text
mise run bootstrap        # una sola tarea; encadena, en este orden:
  → mise install          # herramientas del archivo de versiones
  → deps:install          # los dos proyectos, en modo reproducible
  → services:up           # base de datos con su extensión vectorial
  → db:migrate            # migraciones
  → evals:run --subset smoke
```

Cada eslabón es también una tarea nombrada que se puede correr sola, porque quien
ya tiene el entorno montado no debería pagar la instalación otra vez. La tarea de
arranque no es un atajo escondido: es la composición de las mismas piezas.

### Las cinco decisiones que compran los minutos

| Decisión | Qué ahorra | Qué cuesta |
| --- | --- | --- |
| **No levantar el backend de trazas** en este camino | Una imagen menos que descargar y arrancar | Los enlaces del reporte salen marcados como no disponibles; BR1.3 ya lo permite y el reporte se genera igual |
| **Imágenes ancladas por versión exacta**, no por etiqueta móvil | Que el tiempo de arranque no cambie solo entre máquinas | Hay que subir la versión a mano cuando toque |
| **Instalación en modo reproducible** desde el lockfile | Resolución de dependencias: cero | El lockfile tiene que estar al día, y la instalación falla si no coincide |
| **Subconjunto de arranque propio** (decisión Q3) | Que el paso final tarde tres minutos y no los que tarde la corrida completa | Dos listas que mantener, no una |
| **Los dos proyectos se instalan en paralelo** | Un minuto, aproximadamente | Nada: son gestores distintos sobre árboles distintos |

### El subconjunto de arranque (decisión Q3)

U1 declara su propia lista, con el formato de `SubsetDefinition` que ya fija
`entities.md`:

```yaml
# app/evals/subsets/smoke.yaml
name: smoke
reason: >
  Camino de arranque de NFR21: la lista más corta que demuestra que el sistema
  funciona, ejecutable SIN clave de ningún proveedor.
requires_provider_key: false   # la propiedad que define quién entra en la lista
case_keys: []   # arranca vacía; cada unidad añade su primer caso que no llame a un modelo
```

**La regla de admisión** (decisión del 2026-09-19): entra en `smoke` el caso que
se resuelve **sin llamar a ningún modelo**. Eso deja dentro el esquema del caso,
el aislamiento entre aseguradoras, la paridad del catálogo, las frases prohibidas
y la ausencia de texto de cláusula ajena; y deja fuera toda conversación.

**Qué ve quien no tiene clave:** un reporte real, con los casos deterministas
ejecutados y los de conversación marcados `not_measured` con la causa
`provider_key_missing`. El corredor **no se detiene**: la validación de entorno de
BR1.2 distingue entre una variable que el subconjunto necesita —sin ella sí para—
y una que solo necesitan casos que van a quedar no medidos.

**Por qué esto y no exigir la clave:** la meta mide a quien llega al repositorio,
y quien llega al repositorio no tiene una cuenta de Gemini. Una meta cuyo primer
paso es "crea una cuenta en un proveedor" no mide lo que dice medir.

Dos listas conviven y no se confunden:

- **`smoke`**, de U1: elegida por velocidad, para enseñar que funciona. Es la que
  corre el camino de los 15 minutos.
- **La de la compuerta**, de U21 (PA-11): elegida por cobertura, para bloquear.

**Cómo crece `smoke` sin romper su presupuesto:** la lista tiene un tope escrito
—un caso por conjunto que corre por entrega y por idioma— y ese tope se comprueba
en el guion de verificación. Una lista que crece sin control deja de ser un
arranque rápido, y el fallo sería silencioso: se notaría como un cronómetro que
sube, meses después.

### Qué pasa si no se cumple

Se publica el tiempo real con su causa. **El umbral no se baja.** Las palancas,
en orden: recortar `smoke`, y precargar en la imagen declarada lo que se pueda
precargar (los modelos de detección de datos personales son la pieza más pesada
que no es código). Si con las dos no cabe, el número que se publica es el real y
el criterio queda escrito como no alcanzado.

## Cuándo corre la medición automática (decisión Q4)

NFR21.2 pide un número producido sin intervención humana. El trabajo que lo
produce parte de un entorno limpio y consume unos catorce minutos de un
presupuesto de 2.000 al mes.

| Disparador | Por qué |
| --- | --- |
| **Semanal**, en horario fijo | Produce el número solo y fechado; lo que mide se mueve por semanas |
| **Antes de cada hito** | Es cuando la cifra se publica |
| **A mano**, cuando alguien lo pida | Para comprobar una mejora sin esperar a la semana |

**Lo que este trabajo no hace:** no bloquea la entrega. Es una medición, no una
compuerta; su número entra en la matriz de verificación y su caída se investiga,
pero un cambio no se detiene porque una medición semanal esté vieja. La compuerta
que sí corre en cada cambio es el guion de verificación.

**Cómo se guarda su resultado:** el trabajo publica el tiempo total y el tiempo
por paso como artefacto de la corrida, con su commit y su fecha, en el mismo
formato que el presupuesto por paso de `nfr-requirements`. Así se compara contra
el presupuesto y se ve **qué paso** se salió, que es lo único accionable.

## El reloj de la corrida (NFR17.1)

La duración se mide siempre, con o sin meta cumplida (BR1.8). El diseño:

- El corredor toma la hora al abrir la corrida y al cerrarla, y guarda
  `duration_seconds` en el registro de la corrida.
- El reporte la publica como un campo propio, no como una nota al pie.
- **Además se guarda la duración por caso**, porque el total sin el reparto no
  dice qué atacar. Es el mismo principio que el presupuesto por paso del camino
  de los 15 minutos.

**Concurrencia entre casos.** Los casos se ejecutan **de uno en uno** en la
primera versión. No es pereza: es lo que exige REL-U1.1, que dos corridas del
mismo commit ejecuten los mismos casos en el mismo orden, y lo que hace que un
corte por cuota agotada sea predecible. Cuando la corrida completa deje de caber,
la válvula es el subconjunto declarado, no la concurrencia. Si algún día se
introduce paralelismo, tendrá que llegar con una respuesta escrita a cómo
conserva el orden del reporte y cómo reparte un tope de gasto entre hilos.

## Lo que no se construye aquí, y por qué

| Patrón que la etapa sugiere | Por qué no aplica |
| --- | --- |
| Caché de aplicación | No hay peticiones repetidas que amortiguar. El catálogo se carga una vez al arrancar el proceso y eso ya es todo el "caché" que existe |
| Red de distribución de contenido | No hay activos que servir; la interfaz llega con U6 |
| Pool de conexiones dimensionado | El punto único de sesión llega con U2; U1 no abre conexiones |
| Procesamiento asíncrono | La corrida es un proceso de línea de comandos que termina |
| Paginación | No hay listados que devolver |

**Lo que sí es un patrón de rendimiento aquí y suele pasarse por alto:** la caché
del gestor de paquetes y la de las imágenes en la tubería. El trabajo semanal de
NFR21.2 corre **sin caché a propósito**, porque mide a quien llega limpio; los
demás trabajos sí la usan, porque miden otra cosa.

## Carga del catálogo de textos

El catálogo (C-21) se lee de sus archivos por idioma **una vez al arrancar el
proceso** y queda en memoria como estructura inmutable. No se relee por llamada y
no tiene invalidación, porque no cambia en caliente: un cambio de texto es un
cambio de archivo versionado y llega con un despliegue.

- En el proceso servido: carga al construir la aplicación, en la raíz de
  composición (C-24).
- En el corredor y en las pruebas: la misma carga, mismo código, sin ruta
  especial.
- **Qué pasa si un archivo no está**: falla al arrancar nombrando el archivo, no
  en la primera frase que alguien pida.

## Presupuestos que quedan escritos

| Presupuesto | Valor | Dónde se comprueba |
| --- | --- | --- |
| Camino completo de arranque | 15 min (14 de presupuesto repartido) | Trabajo semanal de NFR21.2 |
| Paso final del arranque (`smoke`) | 3 min | El mismo trabajo, por paso |
| Guion de verificación completo en la tubería | Sin meta numérica en esta unidad | Se mide y se publica desde la primera corrida, para tener contra qué comparar |
| Corrida de evaluación de texto | Se mide siempre; la meta de 10 min es de U21 | `duration_seconds` de la corrida |

El guion de verificación **no lleva meta de tiempo en U1** a propósito: fijarla
hoy, sin una sola prueba escrita, sería inventar un número. Lo que sí se hace
desde la primera corrida es medirlo y publicarlo, que es lo que permite ponerle
meta cuando haya con qué compararla.
