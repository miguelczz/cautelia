# Tubería de entrega — U1 `workspace`

El flujo que corre la compuerta, cómo se arregla un `main` en rojo, y qué queda
escrito para que el intent `infra` no invente un segundo juego de chequeos.

**Fuentes consumidas.** `../nfr-design/security-design.md` (los dos trabajos y
los ocho controles), `../nfr-design/reliability-design.md` (los nueve pasos del
guion y su política de fallo), `../nfr-design/performance-design.md` (el trabajo
semanal de los 15 minutos), `../nfr-design/scalability-design.md` (los filtros y
la cancelación), `infrastructure-specification.md` (los servicios locales) y
`infrastructure-design-questions.md` (decisiones Q2, Q3 y Q4).

## Lo primero que hay que entender de esta tubería

**La compuerta corre después de que el cambio ya entró a `main`.** No hay rama
corta, no hay pull request y no hay segundo revisor: es la forma de trabajo
afirmada por el equipo, elegida con los ojos abiertos. La consecuencia es que el
tronco puede ponerse rojo, y por eso este documento dedica una sección entera a
qué hacer cuando pasa. Una tubería que solo describe el camino feliz aquí sería
media tubería.

## El guion único

Todo control automático vive en `scripts/verify.sh`. El flujo lo **invoca**; no
mantiene su propia lista de pasos, y el intent `infra` lo invocará también en vez
de crear otro.

| # | Paso | Al fallar |
| --- | --- | --- |
| 1 | Escaneo de secretos | **Detiene todo en el acto** |
| 2 | Formato | Sigue, y el guion termina en rojo |
| 3 | Lint, con sus reglas de seguridad activadas | Sigue |
| 4 | Chequeo de tipos | Sigue |
| 5 | Pruebas deterministas | Sigue |
| 6 | Aserciones de esquema, incluido el chequeo de deriva de los contratos generados | Sigue |
| 7 | Chequeos de contenido: frases prohibidas, texto de cláusula, paridad de claves y claves sin consumidor | Sigue |
| 8 | Auditoría de dependencias | Sigue |
| 9 | Golden sets de texto | Sigue |

**Todo corre hasta el final menos el primero.** Una corrida te dice todo lo que
hay que arreglar, en lugar de descubrir un problema por vuelta. El escaneo es la
excepción porque una clave filtrada es un incidente y lo último que se quiere es
seguir trabajando y publicando registros encima.

El orden va **de barato a caro**: quien rompió el formato lo sabe en segundos
aunque el guion siga corriendo, y el único paso que puede gastar cuota es el
último.

**Dos banderas** para que el flujo pueda partirlo sin duplicar su definición:

```bash
scripts/verify.sh                 # los nueve pasos
scripts/verify.sh --only secrets  # solo el paso 1
scripts/verify.sh --skip secrets  # del 2 al 9
```

## El flujo de GitHub Actions

Dos trabajos, en este orden:

```text
disparador: push a main, y a mano

job 1  secrets
       └─ scripts/verify.sh --only secrets
          sin secretos del repositorio, sin base de datos, permisos vacíos
          si falla → todo se detiene

job 2  verify        (needs: secrets)
       ├─ levanta docker compose (base de datos; sin el perfil de trazas)
       ├─ scripts/verify.sh --skip secrets
       └─ publica el reporte de la corrida como artefacto
```

**Por qué el escaneo va primero y solo:** el aviso llega en minutos y no al final
de la corrida, que es lo que exige la práctica afirmada. Y va **sin credenciales**
a propósito: es el trabajo con más superficie de todo el flujo.

**De dónde sale la base de datos** (decisión Q2): del **mismo
`docker-compose.yml` que se usa en la máquina de quien desarrolla**. Una sola
descripción de la base de datos en todo el proyecto. Lo que corre la tubería es
literalmente lo que corre en local, así que un fallo que solo aparece en la
tubería deja de ser un misterio. Se paga medio minuto de arranque; se evita que
dos descripciones se separen y dejen de probar lo mismo, que es un fallo lento y
caro de encontrar.

**El perfil de trazas no se levanta**: ningún paso del guion lo necesita, y
levantarlo sería medio minuto más por corrida a cambio de nada.

### Ahorro de minutos

El plan trae 2.000 minutos al mes con bloqueo al agotarse, así que el flujo los
cuida:

| Medida | Qué ahorra |
| --- | --- |
| Cancelar la corrida anterior sobre el mismo cambio | Dos corridas sobre el mismo trabajo son minutos regalados |
| Filtros de ruta: un cambio que solo toca `docs/` o `aidlc/` no dispara la corrida completa | La mayor parte de los cambios de esta fase son documentos |
| Caché del gestor de paquetes | Un minuto largo por corrida |
| La medición de los 15 minutos corre aparte, semanal | Catorce minutos por cambio era el mayor gasto evitable del proyecto |

**Lo que los filtros nunca apagan:** la compuerta de evaluaciones. Un filtro que
la desactive la convierte en una sugerencia, y el fallo sería invisible: las
corridas siguen saliendo verdes porque no corren.

### Runner propio como reserva

Decisión del 2026-09-19. Si los 2.000 minutos se agotan, el flujo no se detiene
hasta el mes siguiente: **toma el relevo un runner propio** en la máquina de
Miguel, con minutos ilimitados y sin costo.

```text
job 2  verify
       runs-on: [github-hosted]  mientras queden minutos
       runs-on: [self-hosted]    cuando se agoten
```

El cambio se hace a mano cuando GitHub avisa, no con una etiqueta automática: un
relevo automático entre dos máquinas distintas escondería que el entorno cambió,
y este proyecto prefiere que un cambio de entorno se vea.

**Tres condiciones, y la primera no es negociable:**

1. **Se apaga antes de hacer público el repositorio.** Con el repositorio
   público, un fork puede ejecutar código arbitrario en esa máquina a través de
   un pull request; es la advertencia explícita de GitHub. Esta decisión queda
   atada a la de visibilidad (OQ5), y la lista de la decisión de publicar lleva
   una línea nueva: apagar el runner propio.
2. **La máquina tiene que estar despierta.** Dormida, la corrida se queda en
   cola; para un `main` en rojo eso vale tanto como no tener compuerta.
3. **No corre el trabajo semanal de los 15 minutos.** Ese trabajo mide una
   máquina limpia, y un runner propio guarda caché entre corridas. Se queda en
   los runners de GitHub, con o sin minutos: si no hay minutos, esa medición
   espera al mes siguiente y se dice, en lugar de publicar un número que se
   obtuvo en una máquina que no estaba limpia.

## El trabajo semanal de los 15 minutos

Un flujo aparte, con su propio disparador:

```text
disparador: semanal en horario fijo, antes de cada hito, y a mano

job  fresh-clone
     ├─ entorno limpio, SIN caché de ningún tipo
     ├─ instalar herramientas → dependencias → servicios → migraciones
     ├─ correr el subconjunto de arranque y generar el reporte
     └─ publicar el tiempo total y el tiempo por paso
```

**No bloquea la entrega.** Es una medición, no una compuerta: su número entra en
la matriz de verificación y su caída se investiga, pero un cambio no se detiene
porque una medición semanal esté vieja. Corre **sin caché a propósito**, porque
mide a quien llega limpio al repositorio.

Publica el tiempo **por paso**, no solo el total, contra el presupuesto ya
escrito: sin el reparto, un número alto no dice qué atacar.

## Secretos en la tubería

| Qué | Dónde vive | Quién lo ve |
| --- | --- | --- |
| Claves de proveedor, separadas por uso | Secretos del repositorio | Solo el trabajo que las necesita, nunca el flujo entero |
| Nada más | — | El trabajo del escaneo corre sin ninguna |

**Cuando falta una clave**, el paso de evaluaciones no se salta en silencio: la
corrida se marca **no comparable** con esa causa y el reporte lo dice. Una
compuerta que no se pudo ejecutar se declara "no medida", jamás se omite. La
diferencia entre "esto está bien" y "no lo sé" es justo lo que este proyecto se
niega a colapsar.

**Permisos y acciones**: permisos vacíos por defecto a nivel del flujo, elevados
por trabajo solo a lo que haga falta; acciones de terceros fijadas por
identificador de commit, nunca por etiqueta, porque una etiqueta movida es código
ajeno corriendo con los permisos de la tubería. Un analizador de flujos, como
paso del guion, hace que esto sea comprobable y no una intención.

## Despliegue

**No hay.** U1 no despliega nada. Aquí no se elige entre azul-verde, canario o
por lotes: no habría a qué aplicarlo. Esa decisión es del intent `infra`, junto
con el hospedaje, y cuando llegue **invocará este mismo guion**.

La landing (`site/`) se sigue publicando a mano y no comparte tubería con el
aplicativo.

## Vuelta atrás: qué se hace con un `main` en rojo

Esto es lo que en otro proyecto sería el plan de reversión del despliegue. Aquí
lo que se revierte es un commit del tronco.

| Momento | Qué se hace |
| --- | --- |
| Llega el aviso | Arreglar el tronco pasa por delante de cualquier otra tarea |
| Primeros 30 minutos | Se arregla **hacia adelante**: un commit nuevo que corrige |
| Pasados 30 minutos sin verde | **Se revierte el commit que lo rompió** (decisión Q3), y el arreglo se vuelve a intentar con calma |
| Mientras tanto | **Ningún cambio nuevo se apila** sobre un `main` en rojo, salvo el que lo arregla |

**Por qué el corte a los 30 minutos y no "siempre hacia adelante":** sin punto de
corte, "hacia adelante" se convierte en dos horas de tronco bloqueado en el que
no puede entrar nada más. El corte escrito convierte un `main` verde en una
propiedad del proyecto y no en una aspiración.

**Por qué no revertir siempre de inmediato:** para un error de una línea, la
reversión es más ceremonia que arreglo y cuesta un viaje de ida y vuelta.

**Cómo se revierte, sin reescribir historia:** con un commit de reversión, nunca
con un `push` forzado. El historial del tronco es evidencia y no se reescribe.

## Por dónde llega el aviso

Las **notificaciones del propio GitHub** (decisión Q4): correo y aviso en la
aplicación móvil cuando una corrida falla sobre `main`. Sin instalar, sin pagar,
sin una credencial nueva y sin un servicio más que se pueda romper en silencio.

Hay que activarlas una vez, en las notificaciones de la cuenta, para las corridas
fallidas de Actions. Es lo único que hay que configurar, y es lo que hace que la
palabra "incidente" signifique algo: sin aviso, un `main` roto deja de ser un
incidente y pasa a ser el estado normal.

## Lo que todavía no existe, y cuándo aparece

| Pieza | Cuándo |
| --- | --- |
| El propio `scripts/verify.sh` | En el mismo commit que el primer código de aplicación |
| El flujo de GitHub Actions | El mismo commit |
| Los pasos 5 a 9 con contenido real | Van creciendo: hoy no hay pruebas, ni esquemas, ni casos. **Un paso sin nada que comprobar pasa; no se omite**, para que el día que tenga contenido ya esté en su sitio |
| La tubería de despliegue | Intent `infra` |
