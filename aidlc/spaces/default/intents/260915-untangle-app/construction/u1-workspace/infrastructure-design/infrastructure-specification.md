# Especificación de infraestructura — U1 `workspace`

**U1 no se despliega.** No hay servidores, ni entornos, ni red que dibujar. Su
infraestructura son dos cosas reales —el entorno que alguien levanta en su
máquina y el flujo que corre la compuerta— y una tercera que es un encargo: lo
que queda escrito para que el intent `infra` no tenga que inventarlo.

**Fuentes consumidas.** `../nfr-design/performance-design.md` (el camino de los
15 minutos y su presupuesto por paso),
`../nfr-design/security-design.md` (los ocho controles y los dos trabajos del
flujo), `../nfr-design/scalability-design.md` (las tres válvulas),
`../nfr-design/reliability-design.md` (la política de fallo y los nueve pasos),
`../nfr-design/observability-design.md` (qué registra una corrida),
`../nfr-design/logical-components.md` (el inventario y los dominios de fallo),
`../../../inception/domain-design/components.md` y `.../decisions.md` (ADR-002,
ADR-010, ADR-015), `../functional-design/functional-spec.md` y
`../../../inception/contract-design/contract-summary.md` (C-24, C-27, C-28).

## Despliegue

| Faceta | Elección | Por qué |
| --- | --- | --- |
| Modelo de cómputo | **Ninguno.** U1 no se despliega: es un repositorio, un comando y una compuerta | Ponerle un modelo de cómputo sería inventar una decisión que le toca al intent `infra` y a las unidades que sí tienen superficie |
| Topología de red | **Ninguna.** Nada escucha en un puerto público | Los servicios locales escuchan solo en la máquina de quien desarrolla |
| Almacenamiento | Archivos versionados en el repositorio, más el volumen local de la base de datos | Los casos, los subconjuntos y las líneas base son archivos; el registro de corridas es local y prescindible |
| Entornos | **Dos, y ninguno es un servidor:** la máquina de quien desarrolla y el ejecutor efímero de la tubería | No hay `staging` ni `producción` en esta unidad; cuando existan, los define el intent `infra` |
| Infraestructura como código | `docker-compose.yml` para los servicios locales y el flujo de GitHub Actions. **Nada de CDK, Terraform ni CloudFormation** | No hay recursos en la nube que declarar. Introducir una herramienta de infraestructura para levantar dos contenedores sería andamiaje sin obra |
| Dimensionamiento | Los valores por defecto de cada imagen | Un contenedor de desarrollo con un corpus sintético no necesita dimensionado; ponerle cifras sería inventarlas |
| Anclaje de imágenes | **Por huella digital del contenido**, no por etiqueta (decisión Q1) | Una etiqueta se puede reescribir en el registro; entonces el mismo comando baja otra imagen y mueve la medición de los 15 minutos sin que nadie tocara el proyecto |

### Por qué el anclaje por huella, con su costo dicho

La huella es el identificador del contenido de la imagen: dos máquinas y la
tubería corren exactamente los mismos bytes, hoy y en seis meses. Es lo único que
sobrevive a que alguien reescriba una etiqueta en el registro.

**Lo que cuesta:** subir de versión deja de ser editar un número. El archivo de
tareas trae un comando que resuelve la huella nueva de una etiqueta dada y la
escribe; la actualización es correr ese comando y commitear el cambio, no buscar
la huella a mano. El archivo lleva la etiqueta legible en un comentario al lado de
cada huella, para que se sepa qué versión es sin resolver nada.

## Servicios de infraestructura

| Servicio | Papel | Configuración | Notas |
| --- | --- | --- | --- |
| PostgreSQL con pgvector | Base de datos y almacén vectorial | Imagen anclada por huella, un volumen local con nombre, puerto publicado solo en `localhost` | ADR-010. Levanta siempre: las pruebas y el registro local de corridas la necesitan |
| Langfuse | Backend de trazas, con su panel | Imagen anclada por huella, con su propia base de datos, **en un perfil aparte** | ADR-015. **No arranca en el camino de los 15 minutos**: BR1.3 ya exige que el reporte se genere con los enlaces marcados como no disponibles |
| Caché | **No hay** | — | No hay peticiones repetidas que amortiguar |
| Cola de mensajes | **No hay** | — | El trabajo de fondo corre en el mismo proceso, sin broker (ADR-004) |
| Búsqueda | **No hay servicio aparte** | — | La búsqueda léxica y la vectorial viven en la misma PostgreSQL (ADR-010) |
| Red de distribución, DNS, balanceador | **No hay** | — | No hay nada público que servir |

### Cómo se separan los dos servicios

Langfuse vive en un **perfil** del mismo archivo de composición, no en un archivo
aparte. La diferencia importa: con un perfil hay una sola descripción de los
servicios y arrancar el conjunto completo es añadir una bandera; con dos archivos
habría dos descripciones que se pueden separar, que es el mismo error que este
diseño evita en la tubería.

```text
docker compose up -d                      # base de datos: el camino de los 15 minutos
docker compose --profile traces up -d     # además, el backend de trazas
```

### Puertos y colisiones

Los puertos se publican en `localhost` y se leen de variables con valor por
defecto, para que quien ya tenga una PostgreSQL corriendo pueda cambiarlos sin
editar el archivo. El comando de arranque comprueba que el puerto esté libre
antes de levantar y, si no lo está, **falla nombrando el puerto y la variable**;
no elige otro en silencio, porque un puerto elegido solo es un fallo que reaparece
a la semana siguiente en otra forma.

## Infraestructura compartida

Todo lo de esta unidad lo comparten las demás: U1 es la base.

| Recurso compartido | Unidad dueña | Unidades consumidoras | Frontera de acceso |
| --- | --- | --- | --- |
| `docker-compose.yml` | U1 | Todas | Cada unidad que necesite un servicio nuevo lo añade aquí; no se crean archivos de composición paralelos |
| PostgreSQL local | U1 la levanta; **U2 posee el punto único de sesión** | Todas | Ningún módulo abre una conexión por su cuenta; U2 fija el `tenant_id` antes de devolver la sesión |
| `mise.toml` | U1 | Todas | Cada unidad añade el nombre de sus acciones. Es el archivo con más manos encima del proyecto |
| `scripts/verify.sh` | U1 | Todas, y el intent `infra` lo **invoca** | Cada unidad que añade un chequeo lo añade a un paso existente; no se crea un segundo juego de chequeos |
| Flujo de GitHub Actions | U1 | Todas | Dos trabajos; una unidad nueva no añade trabajos, añade pasos al guion |
| `app/contracts/` | U1 (comando y compuerta) y U6 (esquema) | La interfaz | Generado, nunca editado a mano |

**El riesgo que esta tabla hace visible:** `mise.toml` y `verify.sh` los toca
todo el mundo. La mitigación no es un proceso, es una forma: los dos son listas
de nombres, sin lógica, de modo que dos unidades añadiendo su línea no se pisan.

## Secretos

| Dónde | Cómo llegan | Qué pasa si falta uno |
| --- | --- | --- |
| Máquina de quien desarrolla | Un `.env` local que el archivo de tareas carga al invocar el comando; el código no lo lee | El arranque termina con código distinto de cero **nombrando la variable**, antes de la primera llamada a un proveedor (BR1.2) |
| Tubería | Secretos del repositorio, pasados **al trabajo que los necesita**, nunca al flujo entero | Igual: el paso falla nombrando la variable |
| El repositorio | **Nunca.** `.env.example` lista nombres, jamás valores | El escaneo de secretos bloquea |

**Dato verificado, no supuesto:** el `.gitignore` ya ignora `.env` y `.env.*` y
ya exceptúa `.env.example` en la línea siguiente. Los requisitos de seguridad lo
daban como pendiente; está hecho, y esta especificación lo corrige.

**Rotación.** Una clave que llegó a un commit se considera comprometida y **se
rota en el proveedor**. Borrarla del archivo no cierra el incidente. Es regla del
proyecto; ninguna herramienta la hace cumplir, y por eso es lo primero que dice
el mensaje de fallo del escaneo.

## Lo que esta unidad deja encargado al intent `infra`

Escrito aquí para que ese intent no tenga que reconstruirlo:

| Encargo | Qué necesita saber |
| --- | --- |
| Hospedaje del aplicativo | Un solo proceso: la interfaz se compila a estáticos y se sirve desde el mismo origen que la API (ADR-002). La página de espera de la instancia dormida necesita un hospedaje estático que no se duerma |
| Base de datos gestionada | PostgreSQL con pgvector; el aislamiento por aseguradora es por seguridad a nivel de fila, así que el proveedor tiene que soportarla |
| Backend de trazas en el despliegue | Qué se exporta y a dónde lo decide ese intent; los resúmenes públicos y el techo de gasto **no dependen de él** (ADR-015) |
| Disparador del reinicio nocturno y del chequeo periódico | U1 deja el comando en el archivo de tareas; quién lo dispara es de ese intent |
| Tubería de despliegue | **Invoca el mismo `scripts/verify.sh`**, no crea un segundo juego de chequeos |

La landing (`site/`) se sigue publicando a mano y no comparte tubería con el
aplicativo.
