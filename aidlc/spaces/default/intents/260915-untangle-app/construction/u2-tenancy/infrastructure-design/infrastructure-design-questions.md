# Preguntas — Diseño de infraestructura de U2 `tenancy`

U2 es la primera unidad con tablas, así que es la primera que necesita una base
de datos para probarse. Esta etapa decide **dónde y cuándo** corre esa base.

**Alcance de esta etapa para U2.** La unidad es de tipo `library`, así que el
contrato solo pide dos artefactos: el flujo de integración continua y la
trazabilidad. `infrastructure-specification` y `monitoring-design` los piden las
unidades de tipo `service`, `ui` o `packaging`; U2 no despliega nada por su
cuenta y no tiene superficie propia que monitorizar.

**Fuentes consumidas.** `../nfr-design/security-design.md` (las cuatro capas y
los tres comandos nuevos), `../nfr-design/correcciones-tras-revision.md` (que
rige donde contradiga al anterior), `../nfr-design/logical-components.md`,
`../functional-design/functional-spec.md`,
`../../../inception/contract-design/contract-summary.md` (C-10 y C-30) y el
flujo de verificación que U1 dejó escrito.

Aplico sin preguntar lo que ya está decidido: las pruebas levantan su base con
contenedores desde la propia suite y se conectan con el rol del aplicativo, no
con el superusuario (lo fija el contrato C-10 textualmente); la imagen es la
misma anclada por huella que ya usa el entorno local; los tres comandos nuevos
se invocan desde el paso 6 del guion, que ya existe; y el escaneo de secretos
sigue siendo el primer trabajo.

Quedan **dos decisiones**.

## Q1 — Si el camino "del clon al reporte" sigue sin necesitar base de datos

NFR21 mide el tiempo desde clonar el repositorio hasta ver el reporte de
evaluación, con meta de menos de quince minutos en máquina limpia, y se publica.
Hoy ese camino son tres comandos y ninguno toca una base. U2 introduce la
primera.

A. **Sigue sin base** (recomendada): arrancar, instalar y correr el subconjunto
   de evaluación siguen sin necesitar base de datos. La base la necesitan solo
   las pruebas de U2 y los dos chequeos nuevos. Quien clone el repositorio para
   mirarlo sigue viendo un reporte en minutos sin instalar nada más, y la cifra
   publicada de NFR21 no se mueve por una razón que no es de calidad del
   producto
B. **A partir de U2 el arranque incluye levantar la base**: un solo camino para
   todo, más fácil de explicar. A cambio, la cifra publicada de NFR21 empeora de
   golpe por el arranque de un contenedor, y quien solo quiera ver el reporte
   necesita tener Docker vivo
X. Other (please specify)

[Answer]: A

## Q2 — Cada cuánto corren los dos chequeos que necesitan base

`rls:check` y `migrate:check` cuestan lo que cuesta levantar un contenedor de
base de datos. Corren dentro del paso 6 del guion de verificación.

A. **En cada corrida** (recomendada): la compuerta autoritativa es el flujo de
   GitHub Actions, y una migración que no se puede deshacer se descubre el día
   que se escribe. Además, un cambio que rompe una migración muchas veces no
   está en la carpeta de migraciones —renombrar un modelo, por ejemplo—, así que
   filtrar por ruta dejaría fuera justo el caso que más duele
B. **Solo cuando el cambio toca migraciones**: la mayoría de las corridas
   terminan antes. A cambio, la compuerta pasa a depender de un filtro de rutas
   que puede estar mal, y un `main` en rojo descubierto tarde es un incidente
   según nuestra propia práctica
X. Other (please specify)

[Answer]: A
