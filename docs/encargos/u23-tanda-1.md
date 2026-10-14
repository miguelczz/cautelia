# Encargo para una sesión en la nube — U23 `comparison-view`, tanda 1

Pega este archivo entero como primer mensaje de una **sesión nueva**. Es la primera de
las dos tandas de U23; la segunda, la costura con las tres conversaciones reales y la
prueba de aislamiento sobre las trazas, se hace en local porque necesita base y corpus.

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

**La pantalla de comparación**: la misma pregunta de cobertura respondida por las tres
aseguradoras lado a lado, cada columna con su propio estado de carga y su propio fallo.
Con respuestas **declaradas**, no reales: la costura es la tanda 2.

Lee estos, en este orden, y no escribas nada antes:

1. `aidlc/spaces/default/intents/260915-untangle-app/construction/u23-comparison-view/functional-design/functional-spec.md` — los cuatro flujos
2. `.../u23-comparison-view/functional-design/rules.md` — BR1.1 a BR2.4 son de esta tanda
3. `.../u23-comparison-view/functional-design/entities.md` — **`ComparisonColumn` y sus cinco estados**
4. `.../u23-comparison-view/functional-design/functional-design-questions.md` — las ocho decisiones, incluida la respuesta de Miguel sobre la divulgación (opción A)
5. `.../u23-comparison-view/code-generation/code-generation-plan.md` — la tanda 1 es la tuya

Y del código, en este orden:

- `app/frontend/src/pages/chat/` — la pantalla de chat: cómo se dibuja una respuesta con sus citas, y de dónde sale su texto
- `app/frontend/src/pages/evidence/metrics-page.tsx` — una pantalla con estados cerrados y su tabla de etiquetas en `metrics-labels.ts`: **esa es la forma** de resolver un conjunto cerrado a texto del catálogo
- `app/frontend/src/shared/ui/` — los componentes que ya existen; no escribas otro botón ni otra alerta
- `app/frontend/e2e/visitable-routes.ts` — el registro de pantallas del arnés, con sus respuestas declaradas. **Fíjate cómo está tipado el cuerpo de una respuesta**: con el tipo del contrato generado, para que el día que el contrato crezca rompa `tsc` y no el arnés
- `app/frontend/src/app/router.tsx` — dónde se registra una ruta nueva
- `app/config/copy/es.yaml` y `en.yaml` — el catálogo; toda cadena visible sale de aquí, con paridad

## Las cinco piezas

1. **La pantalla** en `app/frontend/src/pages/comparison/`, con su ruta en el enrutador.
   Tres columnas, cada una con su estado: `idle`, `loading`, `answered`, `failed`,
   `rejected`.
2. **La divulgación antes de la primera pregunta**: asistente de inteligencia
   artificial, demostración con pólizas de ejemplo, y **qué póliza de ejemplo usa cada
   columna**. La de Knotwell nombra además quién emitió su póliza, porque es una agencia
   y no emite. Tiene que estar **antes** de que exista el campo de pregunta.

   Esta es **la única** divulgación de la pantalla: las columnas no muestran la apertura
   de cada aseguradora (decisión de Miguel, opción A de Q1). Que además quede
   **registrada** en los tres casos es la tanda 2, porque toca la base.
3. **Las preguntas de ejemplo** (dos o tres) y **el texto de fuera de propósito**, que
   explica que la vista compara respuestas de cobertura y enlaza el chat de cada
   aseguradora. Los dos, del catálogo, en los dos idiomas.
4. **El apilado a 360 px** con el nombre de la aseguradora visible en cada columna.
5. **Su entrada en el registro de pantallas del arnés**, como pantalla de **visitante**,
   con sus respuestas declaradas.

## Lo que no se puede hacer mal

1. **`failed` y `rejected` no se dibujan igual.** Uno dice "no se pudo revisar la
   póliza" y el otro "se alcanzó un límite": se arreglan en sitios distintos, y quien
   evalúa necesita distinguirlos. Colapsarlos es el defecto que este proyecto persigue
   en todas partes.
2. **Una columna que responde no espera a las otras dos**, y una que falla no borra las
   otras (BR2.2). Si te ves con un solo estado para la vista, está mal.
3. **Ninguna cadena visible en el componente**: todo del catálogo, con paridad
   español-inglés.
4. **La vista no redacta la diferencia** entre columnas (BR3.2). La diferencia se lee en
   las cláusulas citadas. Un texto que explique por qué dos columnas difieren estaría
   afirmando cobertura.
5. **El cuerpo de la respuesta declarada del arnés va tipado** con el tipo del contrato
   generado. Un `unknown` ahí ya puso `main` en rojo una vez.
6. **No bajes ningún umbral ni relajes ninguna prueba existente** para que algo pase.

## Lo que no puedes correr, y qué hacer

En este entorno **no hay base de datos, ni motor de contenedores, ni navegadores**: no
corren `scripts/verify.sh` entero, `mise run cov`, las pruebas de integración ni el
arnés de accesibilidad. Lo que **sí** corre y tiene que quedar en verde: `mise run
fmt:check`, `lint`, `types`, `copy:check`, `content:check`, `contracts:check`, y
`pnpm --dir app/frontend exec vitest run src/pages/comparison`.

El arnés no lo puedes correr, así que **deja la pantalla registrada y dilo**: la
revisión local lo corre. Lo que sí puedes es no darle trabajo de más: contraste, un
solo `h1`, etiquetas en los controles y objetivos de 44 px son cosas que se escriben
bien de entrada.

## Antes de terminar

1. Corre todo lo de arriba.
2. **Rompe cada regla y comprueba que se cae una prueba.** Las que más importan:
   colapsa `failed` y `rejected`; haz que la vista espere a las tres columnas; quita el
   emisor de la póliza de la columna de la agencia; escribe una cadena visible en el
   componente; muestra el campo de pregunta antes de la divulgación. Si una rotura no
   cae nada, la prueba está escrita a la medida del código: corrígela.
3. Escribe `hallazgos-tanda-1.md` en
   `aidlc/.../construction/u23-comparison-view/code-generation/`, con la tabla de
   roturas y qué se cayó, y **lo que no pudiste correr**.
4. Commit **en tu rama**, nunca a `main`.

## Lo que no se toca

- **Las tres rutas del chat**: esta tanda no las llama todavía. Las respuestas son
  declaradas.
- **La respuesta de cobertura, la recuperación y el verificador de citas**: U13 y U8.
- **Los cinco controles de límites del chat.**
- **El contrato de borrado**: esta vista no añade tabla ni purgador.
