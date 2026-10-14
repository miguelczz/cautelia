# Integración continua — U2 `tenancy`

Qué cambia en el flujo de verificación cuando entra la primera unidad con
tablas. Es poco a propósito: U1 dejó el flujo montado y U2 añade lo mínimo para
que la base de datos exista donde hace falta y **no exista donde no**.

**Alcance de esta etapa para U2.** La unidad es de tipo `library`, así que el
contrato pide este documento y la trazabilidad.
`infrastructure-specification.md` y `monitoring-design.md` los piden las
unidades de tipo `service`, `ui` o `packaging`: U2 no despliega nada por su
cuenta ni tiene superficie propia que monitorizar. Va embebida en el proceso
único, y la observabilidad de ese proceso es de otra unidad.

**Fuentes consumidas.** `../nfr-design/security-design.md`,
`../nfr-design/correcciones-tras-revision.md` (**rige donde contradiga al
anterior**), `../nfr-design/logical-components.md`,
`../functional-design/functional-spec.md`,
`../../../inception/contract-design/contract-summary.md` (C-10, C-30) y el flujo
que U1 dejó escrito en `.github/workflows/verify.yml`.

## Lo que no cambia

- **Dos trabajos.** El escaneo de secretos sigue siendo el primero y sigue
  cortando en el acto; el resto corre después. Un `main` en rojo es un
  incidente.
- **El guion sigue teniendo nueve pasos.** Lo que crece es el archivo de tareas,
  con tres entradas nuevas que se invocan desde el paso 6, donde ya conviven
  `schema:check`, `contracts:check`, `env:check` y `supply:check`.
- **La tubería no mantiene su propia lista.** Invoca el guion, como siempre.
- **El intent `infra` seguirá invocando este mismo guion** en vez de inventar un
  segundo juego de chequeos.

## Lo que añade U2

| Pieza | Dónde | Por qué |
| --- | --- | --- |
| `rls:check` | Archivo de tareas, invocado desde el paso 6 | Pregunta al catálogo vivo qué tablas hay y al rol vivo qué privilegios tiene |
| `migrate:check` | Archivo de tareas, invocado desde el paso 6 | Sube, baja y vuelve a subir contra una base efímera |
| `tenancy:literals` | Archivo de tareas, invocado desde el paso 6 | Busca identificadores de aseguradora literales fuera del cargador y las fixtures |
| `test:u2` | Archivo de tareas | Las pruebas acotadas de esta unidad, como ya existe `test:u1` |

## De dónde sale la base de datos

**No de un contenedor de servicio del flujo.** El contrato C-10 lo fija
textualmente: *"las pruebas con testcontainers se conectan con ese rol y no con
el superusuario"*. Así que la suite levanta y destruye su propia base, con la
misma imagen anclada por huella que usa el entorno local.

La razón de fondo es que **hay un solo camino**: lo que corre en la máquina de
Miguel es lo mismo que corre en la tubería, con el mismo rol y la misma imagen.
Un contenedor de servicio del flujo sería un segundo camino que solo existe en
la tubería, y los fallos de aislamiento son tan a menudo de configuración como
de código.

**El rol importa más que la imagen.** La base efímera se crea con el rol del
aplicativo, que no puede saltarse las políticas. Conectarse como superusuario
haría que toda la suite de aislamiento pasara sin que exista aislamiento: es el
fallo que no avisa, y por eso `rls:check` pregunta por los privilegios del rol
vivo en vez de confiar en cómo se creó.

## Dónde **no** hay base de datos

Decisión Q1 de esta etapa: **el camino "del clon al reporte" sigue sin tocar una
base.** Las tres cosas que ese camino hace —instalar herramientas, instalar
dependencias y correr el subconjunto de evaluación— siguen sin necesitar
PostgreSQL ni Docker.

| Comando | ¿Necesita base? |
| --- | --- |
| `mise run bootstrap` | No |
| `mise run deps:install` | No |
| `mise run evals:run -- --subset smoke` | No |
| `mise run test:u2` | Sí |
| `mise run rls:check` | Sí |
| `mise run migrate:check` | Sí |

Dos razones. La primera es NFR21: es una cifra que se publica, y empeorarla por
el arranque de un contenedor sería empeorar una métrica publicada por algo que
no es calidad del producto. La segunda es quién clona el repositorio: alguien
que lo está evaluando, que quiere ver un reporte en minutos y no instalar
Docker para conseguirlo.

Esto se mantiene mientras las unidades siguientes no metan una tabla en el
camino del subconjunto de arranque. El día que una lo haga, esta decisión se
revisa en su etapa y la cifra de NFR21 se vuelve a medir.

## Cada cuánto corre cada cosa

Decisión Q2: **los dos chequeos con base corren en cada corrida**, no solo
cuando el cambio toca la carpeta de migraciones.

Un filtro por ruta parece gratis y no lo es: lo que rompe una migración muchas
veces no vive en esa carpeta —renombrar un modelo, cambiar un tipo— y el filtro
dejaría fuera justo ese caso. La compuerta autoritativa es este flujo; que una
migración irreversible se descubra el día que se escribe vale el contenedor.

## Lo que esto le cuesta a la corrida

El coste real es el arranque de un contenedor de PostgreSQL, que hoy no existe
en la corrida. **No se estima aquí: se mide.** La primera corrida verde de U2 en
la tubería da la cifra, y esa cifra entra en el resumen de la generación de
código como cualquier otro número medido. Publicar una estimación al lado de
métricas medidas sería exactamente lo que el proyecto no hace.

Si esa cifra resultara incompatible con el presupuesto de la corrida, el camino
**no** es apagar un chequeo: es el que ya fija la práctica del equipo —correr un
subconjunto declarado y reproducible— y la corrida completa pasa a ser
obligatoria por hito. El umbral no se toca.

## Variables de entorno nuevas

Dos, las dos claves de firma separadas por uso. Se declaran por **nombre** en la
plantilla de variables, nunca por valor, y `env:check` compara esa plantilla
contra lo que el código lee, en las dos direcciones.

En la tubería llegan como secretos del repositorio. Una clave que llegue a un
commit se considera comprometida y **se rota en el proveedor**: borrarla del
archivo no cierra el incidente.
