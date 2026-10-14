# Preguntas — Contract Design

Esta etapa escribe los **acuerdos entre las piezas**: qué datos cruzan cada
frontera, con qué forma, por qué mecanismo, quién es dueño del acuerdo y qué
pasa cuando algo falla o tarda. Es el documento del que parte cada unidad en
Construcción, así que un acuerdo mal puesto aquí se paga en integración.

Units Generation dejó **14 puntos de integración** identificados. La mayoría ya
los resuelven documentos aprobados, y esas decisiones las tomo yo con su razón
escrita; las verás en la aprobación:

- **Llamadas dentro del proceso.** El aplicativo es un solo proceso; las piezas
  se hablan importando la interfaz pública del módulo (`api.py`), nunca sus
  archivos internos. Sin colas, sin bus de eventos, sin llamadas de red entre
  módulos (ADR-001 y ADR-004).
- **Una sola API HTTP, tipada de punta a punta.** El servidor publica su
  esquema OpenAPI, de ahí se genera el cliente de TypeScript y un chequeo de
  deriva falla si el esquema cambia sin regenerarlo (ADR-002).
- **Tiempo real por SSE.** El chat transmite la respuesta mientras se genera y
  la bandeja se actualiza sola; los eventos son tipados y reanudables con
  `Last-Event-ID` (ADR-021).
- **Proveedores detrás de puertos propios.** Cuatro interfaces (generar texto,
  embeddings, transcribir, sintetizar), un adaptador por proveedor y una
  taxonomía cerrada de errores (ADR-018).
- **Base de datos compartida con aislamiento.** Toda consulta pasa por el punto
  único de sesión que fija la aseguradora, con RLS en cada tabla (M9).
- **Contratos verificados por herramienta.** Las reglas de dirección de
  dependencias se comprueban con `import-linter` en el guion de verificación
  (ADR-001).

Quedan **siete decisiones** con más de una respuesta razonable, que cambian la
forma de los acuerdos y el trabajo de Construcción.

## Q1 — Qué forma tiene un error de la API

Todas las pantallas leen errores del mismo servidor: límite de mensajes
alcanzado, enlace vencido, caso ajeno, proveedor caído. Si cada endpoint
inventa su forma, el cliente generado no puede tratarlos igual y cada pantalla
escribe su propio manejo.

A. **Formato estándar `application/problem+json`** (RFC 9457, el sucesor del
   7807): campos `type`, `title`, `status`, `detail` e `instance`, más dos
   propios, `code` (valor de una lista cerrada, para que la pantalla decida sin
   leer el texto) y `trace_id`. El texto que ve la persona no viene aquí: sale
   del catálogo de textos por idioma con la clave que indica `code`
   (recomendada)
B. **Formato propio mínimo**: `{ "error": { "code": ..., "message": ... } }`.
   Menos campos que documentar, pero no es un estándar que alguien reconozca al
   revisar el repositorio
C. **El que trae FastAPI por defecto** (`{"detail": "..."}`): cero trabajo, pero
   sin código estable, así que la pantalla tendría que mirar el texto
X. Other (please specify)

> En la primera tanda Miguel respondió `Other`, literal: "La verdad tienes más
> experiencia que yo en el caso, usa la que más se recomiende". Se le presentó
> de nuevo con la razón de la recomendada y eligió A.

[Answer]: A

## Q2 — Cómo se versiona la API y qué pasa con un cambio que rompe

Hoy el único consumidor de la API es la interfaz de este mismo repositorio, que
se compila junto al servidor, así que no hay clientes viejos que puedan quedar
atrás. Pero el repositorio es candidato a publicarse y la API es de las primeras
cosas que mira quien lo evalúa.

A. **Prefijo `/api/v1` desde el primer archivo.** Dentro de v1 solo entran
   cambios aditivos (campos nuevos opcionales, endpoints nuevos); el cliente
   ignora lo que no conoce. Un cambio que rompe crea `/api/v2` y v1 sigue viva
   hasta que la interfaz migre. El chequeo de deriva del esquema obliga a
   regenerar el cliente en el mismo commit (recomendada)
B. **Sin prefijo de versión**, con la misma regla de solo cambios aditivos. Es
   honesto con la realidad (un solo consumidor), pero el día que haga falta
   versionar hay que tocar todas las rutas
C. **Versión por cabecera** (`Accept: application/vnd.untangle.v1+json`): más
   flexible y bastante más trabajo, y complica el cliente generado
X. Other (please specify)

> Cambio de Miguel el 2026-09-18, después de la revisión y antes de la
> compuerta, literal: "en las rutas no quiero api/v1, no es un proyecto que se
> vaya a escalar a futuro como para tener más versiones con que sea solo api/
> considero que queda bien, sin embargo es una opinión, si consideras que la
> buena práctica es como se planteó así lo dejamos". Se aceptó su razón: el
> único consumidor es la interfaz de este mismo repositorio, que se compila y se
> despliega con el servidor, así que el prefijo no protege a nadie. La respuesta
> pasa de A a B, con el disparador escrito: se versiona el día que aparezca un
> consumidor fuera del repositorio.

[Answer]: B

## Q3 — Qué cruza la frontera entre dos módulos del servidor

Cuando la bandeja pide el caso al módulo del caso, ¿qué recibe? Si recibe el
objeto de base de datos, puede recorrer relaciones, escribir en él y quedar
atada al esquema de tablas del otro módulo; el día que ese esquema cambie, se
rompen piezas que no lo declararon como dependencia.

A. **Modelos propios de cada módulo.** Cada `api.py` expone tipos de solo
   lectura (modelos Pydantic o `dataclass` congeladas) con exactamente los
   campos que el otro necesita; los objetos de SQLAlchemy no salen del módulo
   que los posee, y las referencias entre módulos viajan como identificador
   (`case_id`, `clause_id`). Un contrato de `import-linter` prohíbe importar el
   módulo de tablas de otro (recomendada)
B. **Se comparten las entidades de base de datos.** Menos código de conversión
   hoy; cada cambio de tabla se vuelve un cambio de contrato mañana
C. **Mixto**: entidades compartidas dentro del servidor, modelos propios solo
   hacia la API HTTP
X. Other (please specify)

[Answer]: A

## Q4 — En qué formato se escriben los archivos versionados

Hay cuatro familias de archivos que no son código y que varias piezas leen: la
configuración de cada aseguradora (idioma, voz, reglas, políticas, póliza de
ejemplo), los casos de los golden sets (uno por archivo, con identificador
estable), el corpus y los datos que genera el generador sintético, y las líneas
base de las evaluaciones. Units Generation dejó esta forma explícitamente a esta
etapa.

A. **YAML para lo que escribe una persona y JSON para lo que escribe una
   máquina.** Configuración, reglas, políticas y casos de golden set en YAML
   (admite comentarios y texto de varias líneas, que las reglas y los guiones
   necesitan); corpus generado, manifiestos de hashes, reporte y líneas base en
   JSON (bytes estables, comparables entre corridas). Cada familia con su JSON
   Schema y su validación en el guion de verificación (recomendada)
B. **Todo en JSON**: una sola forma y bytes estables en todo; se pierden los
   comentarios justo donde más ayudan, que es la configuración y las reglas
C. **Todo en YAML**: cómodo de escribir en todo; el archivo generado deja de ser
   byte a byte comparable y complica la comprobación de "misma semilla, mismos
   bytes"
D. **TOML para la configuración** y JSON para el resto: TOML se lee muy bien
   plano, pero las reglas y los guiones tienen estructura anidada, que es
   justamente donde TOML se vuelve incómodo
X. Other (please specify)

[Answer]: A

## Q5 — Cómo viaja la credencial en cada petición

Hay tres formas de entrar: el ajustador con su credencial de aseguradora y rol,
el visitante con el enlace firmado de una hora que abre solo su caso, y el
visitante anónimo del chat público con la clave de su navegador. Además, la
bandeja y el chat reciben actualizaciones por un stream que el navegador abre
con `EventSource`, y `EventSource` **no permite mandar cabeceras propias**: solo
viajan las cookies.

A. **Cookie `HttpOnly`, `Secure`, `SameSite=Lax` en los tres casos.** El enlace
   firmado se canjea una sola vez al abrirlo: el servidor valida el token, deja
   una cookie limitada a ese caso y redirige a una dirección sin token, así que
   el token no queda en la barra, ni en la cabecera `Referer`, ni en los
   registros (lo pide AC3.8.6). Una sola forma de autenticar para las peticiones
   normales y para los streams (recomendada)
B. **Token `Bearer` en la cabecera para la bandeja** y cookie solo para los
   streams: dos mecanismos que mantener y probar, y el token del ajustador
   tendría que vivir en el navegador en un lugar accesible por JavaScript
C. **Token en la dirección en cada petición**: lo más simple de implementar y lo
   que AC3.8.6 prohíbe explícitamente
X. Other (please specify)

[Answer]: A

## Q6 — Qué pasa si una escritura llega dos veces

Un visitante con mala conexión toca "enviar" otra vez; el navegador reintenta un
`POST` que ya había llegado; el ajustador hace doble clic en "aprobar". Sin un
acuerdo, eso crea dos turnos de conversación, dos decisiones sobre el mismo caso
o dos correcciones.

A. **Clave de idempotencia del cliente** en las tres escrituras que importan
   (enviar un mensaje de chat, decidir un caso, corregir un campo): el cliente
   genera un identificador único, lo manda en la cabecera `Idempotency-Key`, y
   repetir la misma petición devuelve el mismo resultado sin crear nada nuevo.
   Es el mismo mecanismo que ya usa el registro de respuestas de cobertura y el
   relanzamiento del trabajo de fondo, así que el proyecto lo tendría en una
   sola forma (recomendada)
B. **Sin idempotencia**: la interfaz desactiva el botón mientras la petición
   viaja. Funciona hasta que el problema es la red y no el dedo
X. Other (please specify)

[Answer]: A

## Q7 — Cómo le entrega un canal un turno al grafo y cómo recibe la respuesta

El chat y la voz son dos transportes muy distintos sobre el mismo grafo: uno
manda texto y transmite texto, el otro manda audio transcrito y necesita audio
lo antes posible. El acuerdo entre el canal y el runtime del grafo es el que
hace que la conducta sea la misma en los dos (lo exige FR2.6) y el que decide
cuánto código de tiempo real se duplica.

A. **Un flujo de eventos tipados.** El canal llama una función asíncrona con el
   turno y recibe un flujo de eventos de una lista cerrada: `partial` (texto
   mientras se genera), `final`, `waiting` (frase de espera del catálogo),
   `handoff` (se derivó), `error`. El chat los reenvía tal cual por SSE; la voz
   convierte `partial` y `final` en audio. Un solo contrato, probado sin
   transporte, y los eventos son los mismos que viajan por SSE (recomendada)
B. **Funciones de retorno**: el canal registra qué hacer con cada tipo de salida
   y el grafo las llama. Funciona, pero el orden y el fin del turno dejan de
   estar en el tipo y pasan a ser convención
C. **El canal pregunta periódicamente** por el estado del turno: el más simple
   de razonar y el que no cabe en los 500 ms de la voz
X. Other (please specify)

[Answer]: A
