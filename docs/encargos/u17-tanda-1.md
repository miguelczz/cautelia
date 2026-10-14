# Encargo para una sesión en la nube — U17 `voice-public-link`, tanda 1

Pega este archivo entero como primer mensaje de una **sesión nueva**. Es la primera de
las dos tandas de U17; la segunda —los contadores y el cableado— se hace en local porque
necesita base de datos y la raíz de composición.

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

**Las decisiones puras que hacen publicable la voz**, los dos campos de configuración
que las alimentan, la tabla versionada de topes del proveedor, y los avisos que la
consola da antes de pedir el micrófono.

Antes de escribir nada, lee esto en este orden:

1. `aidlc/spaces/default/intents/260915-untangle-app/construction/u17-voice-public-link/functional-design/functional-spec.md` — los cinco flujos
2. `.../u17-voice-public-link/functional-design/rules.md` — **BR1.2, BR1.3, BR1.5, BR2.3, BR3.1 y BR4.1 son de esta tanda**
3. `.../u17-voice-public-link/functional-design/entities.md` — los dos campos, `PublicCallDecision` y `ProviderCap`
4. `.../u17-voice-public-link/functional-design/functional-design-questions.md` — **la sección «Lo que el código ya tenía hecho» te ahorra media tanda**
5. `.../u17-voice-public-link/nfr-requirements/performance-requirements.md` — PERF-U17.1
6. `.../u17-voice-public-link/code-generation/code-generation-plan.md` — la tanda 1 es la tuya

Y del código, en este orden:

- `app/backend/src/untangle/chat/limits.py` — **la forma exacta que tiene que tener tu decisión**: pura, con la configuración y los contadores como argumentos, devolviendo cuál límite y nunca la frase. Lee también su docstring: explica por qué el orden de las comprobaciones no es alfabético
- `app/backend/src/untangle/tenancy/models.py` — `CallConfig`, y **su docstring dice que los dos carriles son de esta unidad**
- `app/backend/src/untangle/voice/availability.py` — `VoiceOffCode`: los dos códigos que vas a emitir **ya existen** con su frase, y su comentario dice que esperaban a U17
- `app/backend/src/untangle/telemetry/spend/quota.py` — `voice_mode` y `covers_primary_voice`, que **ya existen y son puras**. No las reescribas
- `app/backend/src/untangle/voice/loop.py` — el corte y el aviso de los treinta segundos, **ya construidos**. No los toques
- `app/frontend/src/pages/voice/` — la consola que ya existe, y de dónde sale su texto
- `app/config/copy/es.yaml` y `en.yaml` — el catálogo, con paridad

## Las cinco piezas

1. **Los dos campos en `CallConfig`**: `calls_per_visitor_day` (omisión 1) y
   `calls_per_site_day` (omisión 15). Aditivos, **sin subir `config_version`**: una
   aseguradora que no los declara sigue cargando igual.
2. **La decisión pura de admisión.** Recibe la configuración, lo que los contadores ya
   dicen y el reloj; devuelve admitir, o el código del carril que rechazó, o el caso que
   retoma. Tres cosas que no se pueden confundir:
   - una retoma **dentro** de la ventana no consume la llamada del día;
   - **sí** cuenta contra las llamadas del sitio;
   - fuera de la ventana es una llamada nueva.
3. **La tabla versionada de topes del proveedor**: una fila por proveedor de pago, con
   su tope, dónde se configuró y **la fecha de su última comprobación**. Un archivo con
   una fila sin fecha **no carga**, y su mensaje nombra la fila.
4. **Los avisos de la consola** que solo dependen de la disponibilidad: los dos límites
   dichos **antes** de pedir el micrófono, el motivo cuando no hay voz con la oferta del
   chat, el aviso de la voz de respaldo —que dice que puede sonar distinta en cada
   idioma—, la póliza de ejemplo de la aseguradora y qué probar.
5. **Las claves del catálogo** que falten, en los dos idiomas.

## Lo que no se puede hacer mal

1. **La decisión no consulta la base, no mira el reloj del proceso y no devuelve texto**
   (BR1.2). Si te ves pasándole una sesión, está mal.
2. **"Desde esta conexión", nunca "por persona"** (BR1.4). Un visitante cambia de
   navegador, así que este carril no controla el gasto y la consola no puede insinuar que
   sí.
3. **No reescribas la decisión de la voz.** `quota.voice_mode` existe, es pura y ya
   responde "respaldo" cuando falta un dato. Cablearla es la tanda 2.
4. **No toques el corte ni el aviso de los treinta segundos**: U16 los construyó y están
   probados.
5. **La consola no pide el micrófono antes de saber si hay voz** (BR3.1). Pedirlo para
   después decir que no hay es la peor pantalla posible.
6. **Ninguna cadena visible en línea**, y paridad español-inglés.
7. **No bajes ningún umbral ni relajes ninguna prueba existente** para que algo pase.

## Lo que no puedes correr, y qué hacer

En este entorno **no hay base de datos, ni motor de contenedores, ni navegadores**: no
corren `scripts/verify.sh` entero, `mise run cov`, la integración ni el arnés. La
decisión y la tabla se prueban enteras sin nada de eso, que es por lo que esta tanda va
aquí.

Lo que tiene que quedar en verde: `mise run fmt:check`, `lint`, `types`, `copy:check`,
`content:check`, `schema:check`, `contracts:check`, `voice:frases`, y las pruebas de la
unidad más `pnpm --dir app/frontend exec vitest run src/pages/voice`.

**`voice:frases` importa aquí**: comprueba que cada aviso que el servidor manda por el
socket la consola sabe decirlo. Si añades un aviso y no su frase, ese chequeo lo caza.

## Antes de terminar

1. Corre todo lo de arriba.
2. **Rompe cada regla y comprueba que se cae una prueba.** Las que más importan:
   que una retoma gaste la llamada del día; que no cuente contra el sitio; que la
   ventana se compare con `<=` en vez de `<` en el borde exacto; que la decisión mire el
   reloj del proceso; que un archivo de topes sin fecha cargue igual; que la consola
   pida el micrófono antes de la disponibilidad. Si una rotura no cae nada, la prueba
   está escrita a la medida del código: corrígela.
3. Escribe `hallazgos-tanda-1.md` en
   `aidlc/.../construction/u17-voice-public-link/code-generation/`, con la tabla de
   roturas y **lo que no pudiste correr**.
4. Commit **en tu rama**, nunca a `main`.

## Lo que no se toca

- **La llamada, su transporte y su consola base**: U16.
- **El corte y el aviso de los treinta segundos**: ya existen.
- **`quota.voice_mode`**: existe y es pura. Se cablea en la tanda 2.
- **El techo de gasto y su alerta**: U5 y U15.
- **Los contadores**: son la tanda 2, porque necesitan base.
