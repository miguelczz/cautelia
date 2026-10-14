# Encargo para una sesión en la nube — U20 `demo-operations`, tanda 1

Pega este archivo entero como primer mensaje de una **sesión nueva**. Es la primera de
las dos tandas de U20; la segunda —las dos operaciones contra la base de verdad— se hace
en local.

---

## Antes de nada

**Primero ponte en `main`.** Tres sesiones han empezado con un clon anterior al commit
que trae sus documentos, y han concluido que no existían:

```bash
git fetch origin && git log --oneline -1 origin/main
```

Si tu rama no desciende de ese commit, ponte ahí antes de leer nada. Los documentos que
este encargo cita **están en `main`**: si no los ves, es el checkout, no el repositorio.

Después, las dependencias:

```bash
uv tool install --force uv==0.12.16
mise run deps:install
mise run models:install
```

**Los dos últimos fallan en algunos entornos de la nube, y no es tu culpa.** `mise`
descarga Python 3.13.15 y los modelos de spaCy desde las descargas de GitHub
(`objects.githubusercontent.com`), que el túnel a veces rechaza. Si pasa:

- **Python**: prueba `uv python install 3.13`, y si tampoco baja, usa cualquier 3.13.x
  que haya en el entorno con el lockfile tal cual. Después corre los comandos de
  `mise.toml` directamente en vez de `mise run`. **Anota en los hallazgos qué versión
  usaste.**
- **Modelos de spaCy**: si no bajan, las pruebas de redacción quedan rojas con
  `ModelsMissingError`. **Eso no es un defecto del código y no se arregla tocándolo**:
  anótalo en los hallazgos y sigue con lo que sí corre.

`models:install` va después de `deps:install` y no antes: el modo reproducible
**desinstala** los modelos, porque viven en un extra y no en el lockfile.

## Qué se construye

**La validación de la carpeta de una aseguradora** y **la orquestación del reinicio
nocturno con su registro**, las dos puras: la validación sobre archivos y la
orquestación sobre el contrato de borrado que ya existe, con purgadores dobles.

Aquí hay algo que conviene entender antes de escribir una línea: **el camino del fallo
es el que importa**, y probarlo con dobles es mejor que contra una base de verdad, donde
habría que romperla a propósito. Esta tanda existe para eso.

Lee esto, en este orden:

1. `aidlc/spaces/default/intents/260915-untangle-app/construction/u20-demo-operations/functional-design/functional-spec.md` — los cinco flujos
2. `.../u20-demo-operations/functional-design/rules.md` — **BR1.1, BR2.4, BR3.1 y BR3.2 son de esta tanda**
3. `.../u20-demo-operations/functional-design/entities.md` — **`ResetRun` y por qué `partial` existe**, y `TenantFolderReport`
4. `.../u20-demo-operations/nfr-requirements/reliability-requirements.md` — los cinco requisitos de confiabilidad, que son el corazón de esta tanda
5. `.../u20-demo-operations/functional-design/functional-design-questions.md` — las nueve decisiones, incluida la respuesta de Miguel sobre qué pasa con lo abierto (opción A)
6. `.../u20-demo-operations/code-generation/code-generation-plan.md` — la tanda 1 es la tuya

Y del código, en este orden:

- `app/backend/src/untangle/tenancy/models.py` — `VisitorDataPurger`, el `Protocol` que tu orquestación recibe: `name`, `tables`, `purge(older_than, dry_run)`. **Ya existe: no lo cambies**
- `app/backend/src/untangle/server/composition.py`, la lista `PURGADORES` — **los nueve, escritos a mano, con la razón de qué conserva cada uno al lado**. Léelos: son la mitad del diseño de esta unidad
- `app/backend/src/untangle/tenancy/purge.py` — cómo está escrito un purgador y su docstring sobre por qué el registro es explícito
- `app/backend/src/untangle/tenancy/config.py` — el cargador de configuración de una aseguradora: **de ahí sale qué tiene que traer una carpeta**
- `app/config/tenants/sunmeadow/` — una carpeta completa, para saber qué se valida
- `app/backend/src/untangle/evals/gates/models.py` — la forma de un modelo con validadores que impiden estados imposibles; `ResetRun` se escribe así
- `app/config/copy/es.yaml` y `en.yaml` — el catálogo, con paridad

## Las cinco piezas

1. **La validación de la carpeta.** Devuelve **todas** las faltas, cada una con **su
   archivo y su campo**. No la primera: obligar a descubrir un campo por corrida
   convierte dar de alta una aseguradora en cinco intentos.
2. **La orquestación del reinicio**, pura sobre el `Protocol`: recibe los purgadores, el
   reloj y el corte; los llama **en el orden del registro**; devuelve qué borró cada uno
   y cuál falló. **No abre sesión, no mira el reloj del proceso y no escribe ninguna
   sentencia de borrado.**
3. **`ResetRun`** con sus tres resultados y una fila por purgador. Los tres son
   `succeeded`, `failed` y `partial`, y **`partial` no es un lujo**: siete purgadores que
   borraron y dos que fallaron no es ni un éxito ni un fallo completo, y de eso depende
   si el reintento repite todo o solo lo que falta.
4. **La regla de las 24 horas**: dado el último reinicio **exitoso** y el reloj, si las
   superficies públicas aceptan **casos nuevos**. El reloj cuenta desde el último
   **éxito**, nunca desde el último intento. Y lo que ya está abierto **no entra en esa
   decisión**: una conversación o una llamada en curso termina normalmente (decisión de
   Miguel, opción A de Q1).
5. **Las claves del catálogo**: el aviso a una conversación reiniciada y el mensaje de
   las superficies cerradas, en los dos idiomas.

## Lo que no se puede hacer mal

1. **El reinicio no borra nada por su cuenta** (BR2.3): llama al contrato de su dueño.
   Si te ves escribiendo un `DELETE`, está mal. El registro de los nueve está escrito a
   mano a propósito, y una consulta escrita aquí sería el sitio donde la retención deja
   de estar acotada sin que nadie lo note.
2. **`partial` no se colapsa.** En `failed`, el reintento borraría otra vez lo ya
   borrado; en `succeeded`, quedarían datos con el contador de 24 horas reiniciado.
3. **El contador de 24 horas cuenta desde el último éxito** (BR3.2). Atarlo al último
   intento deja la demo aceptando datos indefinidamente con el tablero en verde: es el
   requisito más fácil de implementar mal y el más difícil de notar.
4. **La validación reporta todas las faltas, no la primera** (BR1.1).
5. **Ninguna cadena visible en línea**, y paridad español-inglés.
6. **No bajes ningún umbral ni relajes ninguna prueba existente** para que algo pase.

## Lo que no puedes correr, y qué hacer

En este entorno **no hay base de datos ni motor de contenedores**: no corren
`scripts/verify.sh` entero, `mise run cov` ni la integración. Esta tanda no las necesita:
la validación lee archivos y la orquestación recibe dobles.

Lo que tiene que quedar en verde: `mise run fmt:check`, `lint`, `types`, `copy:check`,
`content:check`, `schema:check`, `tenancy:literals`, `contracts:check`, y las pruebas de
la unidad.

**`tenancy:literals` importa aquí**: comprueba que ningún identificador de aseguradora
aparezca fuera del cargador de configuración y de las fixtures. Tu validación lee
carpetas: no escribas `sunmeadow` en ninguna parte del código.

## Antes de terminar

1. Corre todo lo de arriba.
2. **Rompe cada regla y comprueba que se cae una prueba.** Las que más importan: haz que
   la validación devuelva solo la primera falta; colapsa `partial` en `failed`; ata el
   contador de 24 horas al último intento en vez del último éxito; haz que la
   orquestación mire el reloj del proceso; haz que un purgador que levanta detenga a los
   siguientes sin quedar en el registro. Si una rotura no cae nada, la prueba está
   escrita a la medida del código: corrígela, no la justifiques.
3. Escribe `hallazgos-tanda-1.md` en
   `aidlc/.../construction/u20-demo-operations/code-generation/`, con la tabla de roturas
   y **lo que no pudiste correr**.
4. Commit **en tu rama**, nunca a `main`.

## Lo que no se toca

- **Los nueve purgadores**: se llaman, no se tocan. Lo que cada uno conserva ya está
  decidido y escrito al lado de su línea.
- **`corpus:ingest`**: la invoca la tanda 2.
- **El disparador nocturno**: es del intent `infra`.
- **El generador sintético y su salida versionada.**
- **El cargador de configuración**: de él se lee qué validar; no se reescribe.
