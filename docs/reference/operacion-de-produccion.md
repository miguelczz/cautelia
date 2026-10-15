# Operación de producción

Cómo está montada la demostración pública, cómo se publica una versión, cómo se
vuelve atrás y qué queda fuera del repositorio. Escrito el 2026-10-13 leyendo la
configuración viva (solo lectura, sin valores de claves); hasta ese día todo esto
vivía en las consolas y en la memoria de quien desplegaba.

**Estado de este documento:** los dos guiones se probaron en modo simulado contra
la configuración real (comprueban el commit, la revisión de GitHub y lo que hay
desplegado, e imprimen lo que cambiarían). **Ninguno se ha ejecutado de verdad
todavía.** La primera publicación que los use tiene que incluir la prueba de la
vuelta atrás, y este párrafo se cambia ese día por la fecha y el resultado.

## Qué hay desplegado

| Pieza | Dónde | Detalle |
| --- | --- | --- |
| El aplicativo (servidor y pantallas) | Cloud Run, servicio `cautelia`, región `us-east1` | 1 CPU, 1 GiB, **una sola instancia como máximo**, sin instancias mínimas, procesador asignado todo el tiempo, 80 peticiones simultáneas, espera máxima de 3.600 s por petición (los flujos del chat y la llamada) |
| El reinicio nocturno | Cloud Run, trabajo `cautelia-reset`, misma imagen que el servicio | Corre `python -m untangle.server.demo_reset`; sin reintentos, 15 minutos de plazo |
| Quién dispara el reinicio | Cloud Scheduler, `cautelia-reset-nocturno` | Todos los días a las 3:00 de Bogotá |
| Las imágenes | Artifact Registry, repositorio `cautelia` en `us-central1` | Una etiqueta por commit, con sus siete primeros caracteres |
| La base de datos | Neon (PostgreSQL) | La dirección va en la variable `UNTANGLE_DATABASE_URL` del servicio |
| El dominio y la landing | Cloudflare (`cautelia.app`) | La landing (`site/`) se publica aparte y a mano; `site/_routes.json` decide qué rutas atiende la landing y cuáles pasan al aplicativo |
| El tope de gasto de Google Cloud | Presupuesto «Tope duro de Cautelia» | 4.000 COP por periodo, con avisos al 50 %, 90 % y 100 %, y un tema de mensajes (`tope-de-gasto`) para el corte |

Dos consecuencias de esa configuración que el código da por hechas:

- **Una sola instancia.** Lo que el aplicativo guarda en memoria del proceso (los
  flujos abiertos del chat, los cierres de reporte en curso, la espera de dos
  minutos de una oferta sin contestar) funciona porque no hay una segunda
  instancia. Subir el máximo de instancias sin mover eso a la base rompe el chat.
- **Sin instancias mínimas.** Tras un rato sin visitas (hasta unos quince minutos) la instancia se
  apaga, y con ella lo que estuviera esperando en memoria. Por eso ninguna
  garantía depende de una espera en el proceso: un caso que se quede en revisión
  sigue en la cola y un ajustador lo puede tomar.

## Las variables del servicio

Son veintiuna. **Sus valores no están en el repositorio ni se imprimen nunca**: se
leen por nombre. Viven como variables de entorno de la revisión de Cloud Run, así
que nunca se exporta la descripción del servicio a un archivo ni se imprime
`env[].value`. La lista de nombres está en `.env.example`; para ver los que tiene
el servicio:

```bash
gcloud run services describe cautelia --region us-east1 --format="value(spec.template.spec.containers[0].env[].name)"
```

Publicar una versión **conserva** las variables como estén y solo actualiza
`UNTANGLE_COMMIT_SHA`. Una variable nueva la agrega Miguel (es una clave, o una
decisión), con `gcloud run services update cautelia --region us-east1
--update-env-vars NOMBRE=valor`, antes de publicar la versión que la necesita; el
trabajo `cautelia-reset` tiene su propio juego y hay que agregarla también ahí si
el reinicio la usa.

## Publicar una versión

Requisitos en la máquina: `git`, `gh` con la cuenta `miguelczz` activa y `gcloud`
con el proyecto configurado. No hace falta Docker: la imagen la construye Cloud
Build (decisión de Miguel del 2026-10-15, para no calentar la Mac), dentro de su
tramo gratis de 2.500 minutos al mes.

```bash
mise run deploy -- --simular
```

Hace las comprobaciones y solo imprime lo que cambiaría. Sin `--simular` publica
el último commit de `origin/main` (o el que se le pase):

```bash
mise run deploy
```

Lo que hace `scripts/desplegar.sh`, en orden:

1. **Comprueba la compuerta.** El commit tiene que estar en `origin/main` y su
   revisión de GitHub Actions tiene que haber terminado en verde. Un commit en rojo
   o sin corrida no se publica.
2. **Anota a qué se vuelve.** Imprime la revisión que sirve ahora y la imagen del
   reinicio, con el comando exacto de la vuelta atrás.
3. **Construye la imagen desde `git archive`** en Cloud Build, que ya corre la
   arquitectura de Cloud Run. Lleva exactamente lo que hay en el commit.
4. **Despliega** el servicio y pone el trabajo de reinicio en la misma imagen.
5. **Prueba de humo** contra la dirección directa del servicio y contra el
   dominio: que esté listo, que responda la pestaña de calidad y que cargue la
   portada. Si falla, se detiene y repite el comando de la vuelta atrás.
6. **Corre el reinicio de la demostración.** Es el último paso de todo despliegue:
   sin un reinicio exitoso en las últimas 24 horas el chat y la llamada se cierran
   a casos nuevos.

Las migraciones de la base no son un paso aparte: el servidor las sube al
arrancar, antes de declararse listo.

### Lo que el guion no hace y a veces hace falta

- **Las pólizas de ejemplo y los casos sembrados viven en la base.** Publicar
  código no los cambia. Si la versión cambia `app/data/` (pólizas, cláusulas,
  titulares), hay que volver a ingerir el corpus y refrescar los casos sembrados
  con el trabajo de reinicio; refrescar borra también los casos de visitantes,
  igual que el reinicio nocturno.
- **La próxima publicación necesita volver a ingerir el corpus.** Desde el
  2026-10-13 las pólizas de ejemplo declaran sus conductores, y la base de
  producción no los tiene hasta que se corra la ingesta contra ella. No recalcula
  nada del índice de búsqueda (las cláusulas no cambiaron) y no borra nada. Hasta
  entonces la regla de «conductor que no figura en la póliza» no dispara, que es
  como estaba antes.
- **Un archivo nuevo que el servidor lea en ejecución necesita su línea `COPY`**
  en el `Dockerfile`, que copia carpetas concretas de `app/`. Pasó con
  `app/evals/last-run.json`: la pestaña de calidad salía vacía en producción y
  bien en local. Después de publicar se prueba la ruta nueva en producción, no
  solo la portada.
- **La landing** (`site/`) no viaja en la imagen. Su comando de publicación no
  está escrito en ningún sitio del repositorio: queda pendiente anotarlo aquí la
  próxima vez que se publique.
- **Las sondas contra el dominio** necesitan su propio `User-Agent`: Cloudflare
  responde 403 al cliente por omisión de Python.

## Volver atrás

```bash
mise run deploy:rollback -- <revisión> <imagen-del-reinicio>
```

Los dos datos los imprime `mise run deploy` antes de cambiar nada. Manda todo el
tráfico a esa revisión del servicio, devuelve el trabajo de reinicio a su imagen y
comprueba que responda. Las últimas revisiones se listan con:

```bash
gcloud run revisions list --service cautelia --region us-east1 --limit 5
```

**No toca la base.** Las migraciones que subió la versión nueva se quedan. Hasta
hoy todas son aditivas (columnas y tablas nuevas), y el código anterior funciona
con ellas. Una migración que no lo sea necesita su propio paso de vuelta atrás,
escrito aquí antes de publicar la versión que la trae.

## El reinicio nocturno

Corre solo a las 3:00 de Bogotá. Para correrlo a mano y esperar el resultado:

```bash
gcloud run jobs execute cautelia-reset --region us-east1 --wait
```

Para ver si corrió anoche:

```bash
gcloud run jobs executions list --job cautelia-reset --region us-east1 --limit 3
```

Si falla, la demostración sigue abierta hasta que pasen 24 horas desde el último
reinicio exitoso y después se cierra sola a casos nuevos, con un mensaje honesto.
El chequeo diario (abajo) avisa cuando eso pasa.

## El chequeo diario

Una vez al día, a las 7:30 de Bogotá, un flujo de GitHub Actions
(`.github/workflows/chequeo-publico.yml`) lee tres datos públicos del sitio y
**falla** si algo está mal. Cuando un flujo programado falla, GitHub le manda un
correo a quien editó por última vez su línea de horario. No hay servicio nuevo, ni
costo fijo, ni un correo configurado en el repositorio. Gasta cerca de un minuto
de GitHub al día.

| Qué mira | De dónde | Cuándo falla |
| --- | --- | --- |
| Que el sitio responda | `GET /api/health/ready` | No responde 200 tras un reintento |
| Que el reinicio nocturno esté al día | `checks.demo_reset` de esa misma respuesta | Vencido (24 horas sin un reinicio exitoso) o no se pudo leer |
| El gasto de los proveedores | `GET /api/spend` | La alerta se cruzó en las últimas 26 horas (un correo, no uno diario), el presupuesto se agotó, o el gasto no se pudo medir |

A mano, contra el sitio publicado o contra otro:

```bash
mise run ops:check
```

Lo que conviene saber:

- **«No medida» no falla.** Es lo que dice cuando la versión publicada todavía no
  trae el dato del reinicio, o cuando no hay ventana de presupuesto.
- **Un presupuesto agotado falla todos los días** hasta que se decida qué hacer.
  Para silenciarlo a conciencia, el flujo acepta `--tolerar-agotado`.
- **El correo depende de la cuenta de GitHub.** Tiene que estar activado en
  Settings → Notifications → Actions («Send notifications for failed workflows»).
- **Si se agotan los minutos del mes, el chequeo calla**: sin minutos, GitHub no
  corre ningún flujo, tampoco este.
- Se descartaron las alertas de Google Cloud porque cobran una cuota mensual por
  cada condición de alerta.

## El gasto

Hay dos topes distintos y no se deben confundir:

- **El de Google Cloud** (hospedaje): el presupuesto «Tope duro de Cautelia»,
  4.000 COP por periodo. Avisa al 50 %, 90 % y 100 %; el correo a los
  administradores de la cuenta de facturación es el comportamiento por omisión de
  Google Cloud y no está desactivado, y además publica en el tema `tope-de-gasto`.
- **El de los proveedores de voz y modelo**: 40 USD a precio de lista en la
  ventana de 90 días que empezó el 2026-09-16, con alerta a los 24 USD. Lo lleva
  el propio aplicativo en la base (la fila de la ventana de presupuesto) y, al
  llegar al tope, la voz deja de aceptar llamadas y el chat sigue. Ningún
  proveedor tiene recarga ni cobro automático.

## Lo que falta

- **Ejecutar de verdad los dos guiones** y probar la vuelta atrás en la próxima
  publicación.
- **Quién corta al llegar al tope de Google Cloud.** El presupuesto publica en
  `tope-de-gasto`; qué está suscrito a ese tema y si de verdad detiene la
  facturación solo se ve en la consola, y no se pudo leer desde aquí.
- **Ver fallar el chequeo diario una vez.** El flujo no se ha ejecutado en GitHub
  todavía (empieza con la primera subida que lo traiga), y el dato del reinicio
  solo existe en el sitio a partir de la versión que lo publica: hasta entonces
  esa comprobación dice «no medida». Falta confirmar que el correo de un fallo
  llega.
- **Langfuse en producción.** Las tres variables (`UNTANGLE_LANGFUSE_PUBLIC_KEY`,
  `UNTANGLE_LANGFUSE_SECRET_KEY`, `UNTANGLE_LANGFUSE_HOST`) con las claves del proyecto
  `cautelia-produccion` van al gestor de secretos y se ponen **en el servicio y en el
  trabajo del reinicio** (`cautelia-reset`): el reinicio es otro proceso y es quien borra
  de Langfuse lo anterior al corte. `scripts/desplegar.sh` solo cambia la imagen; las
  variables se ponen una vez, a mano, al publicar. Sin ellas, producción no envía trazas.
- **El comando de publicación de la landing**, que hoy no está escrito.
