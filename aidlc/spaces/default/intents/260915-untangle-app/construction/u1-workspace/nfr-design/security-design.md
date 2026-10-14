# Diseño de seguridad — U1 `workspace`

Cómo se construyen los ocho controles de `security-requirements.md`. La superficie
que U1 protege no es una aplicación en línea: es **el repositorio, la tubería y
la máquina de quien corre el comando**.

**Fuentes consumidas.** `../nfr-requirements/security-requirements.md` (la tabla
STRIDE y SEC-U1.1 a SEC-U1.8),
`../nfr-requirements/tech-stack-decisions.md` (lo que U1 instala),
`../functional-design/functional-spec.md` (Flujo 1 paso 1 y Flujo 3),
`../functional-design/rules.md` (BR1.2, BR1.10, BR3.6),
`../../../inception/contract-design/contract-summary.md` (C-24 raíz de
composición, C-25 configuración, C-28 contratos generados) y
`nfr-design-questions.md` (decisión Q1 de esta etapa).

## El principio que ordena todo lo demás

Los controles de esta unidad no se sostienen en disciplina. Cada uno es **una
herramienta, una regla de importación o un grep**, porque la práctica del equipo
lo exige: una convención que solo vive en la memoria del autor no está a la
semana seis. Donde un control no se puede automatizar, se dice.

## SEC-U1.1 — Escaneo de secretos

### Dónde corre y en qué orden

La práctica afirmada pide dos cosas a la vez: que el escaneo sea el **primer
trabajo** del flujo, y que el flujo **invoque el guion único** en lugar de
mantener su propia lista de pasos. La única lectura que cumple las dos:

```text
.github/workflows/verify.yml
  job 1: secrets   → scripts/verify.sh --only secrets     (falla → todo se detiene)
  job 2: verify    → scripts/verify.sh --skip secrets     (needs: secrets)
```

El guion sigue siendo la única definición de qué se escanea y cómo. Nada se
escribe dos veces y nada corre dos veces. Es una decisión aplicada sin preguntar,
por ser lectura de una práctica afirmada.

### Qué se escanea y cada cuánto (decisión Q3 de `nfr-requirements`)

| Alcance | Cuándo | Por qué |
| --- | --- | --- |
| El cambio | En cada corrida | Es donde puede aparecer una clave nueva |
| El historial completo | Por hito y antes de publicar el repositorio | El costo crece con el historial; el riesgo se materializa al publicar |

**La protección de inserción del propio GitHub no está disponible**, y esto es un
hecho comprobado el 2026-09-19, no una suposición: en un repositorio **privado**
de una cuenta personal, el escaneo de secretos y la protección de inserción son
parte de un producto de pago para empresas, y la pantalla de seguridad del
repositorio solo ofrece el grafo de dependencias y Dependabot. No se contrata: la
práctica afirmada la pedía "si está disponible", y no lo está.

La consecuencia hay que decirla en vez de suavizarla: **hoy el único escaneo de
secretos del proyecto es el nuestro, y corre después de que el cambio ya está en
`main`**. Eso hace que el primer trabajo del flujo y su corte inmediato dejen de
ser una segunda capa y pasen a ser la única. Cuando el repositorio se haga público
en la semana 12, las dos opciones de GitHub aparecen sin costo y se activan
entonces; esa activación entra en la lista de la decisión de publicar.

### El corte inmediato (decisión Q1)

El escaneo es el único paso del guion que **detiene la corrida en el acto**. Los
otros ocho corren hasta el final y reportan juntos. La razón no es de eficiencia:
una clave filtrada es un incidente, y seguir trabajando después de encontrarla
significa seguir produciendo registros y artefactos con ella dentro.

**Una clave que llegó a un commit se considera comprometida y se rota en el
proveedor.** Borrarla del archivo no cierra el incidente. Es regla del proyecto y
no hay herramienta que la haga cumplir: es lo primero que dice el mensaje de
fallo del escaneo, para que quien lo lea no tenga que acordarse.

## SEC-U1.2 — Ninguna clave en el repositorio

Tres piezas que se montan en el primer commit:

1. **`.env.example` versionado** con **nombres** de variables y nunca valores,
   agrupadas por uso (voz, chat, evaluaciones), porque las claves están separadas
   por uso y el archivo lo tiene que reflejar.
2. **El `.gitignore` con la negación**: hoy ignora `.env.*`; hay que añadir
   `!.env.example` en el mismo commit, o la plantilla nunca entra.
3. **Un chequeo en el guion** que compara los nombres de `.env.example` contra
   las variables que el código lee, en las dos direcciones: una variable que el
   código exige y la plantilla no lista es un fallo, y una variable listada que
   nadie lee también (es la misma comprobación que hace el catálogo con sus
   claves sin consumidor).

**Cómo se leen en ejecución.** Un solo punto: un objeto de configuración
construido en la raíz de composición (C-24) que lee del entorno. Ningún módulo
lee variables por su cuenta. En desarrollo, la carga de un `.env` local la hace
el archivo de tareas al invocar el comando, no el código del aplicativo: así el
código no tiene una ruta distinta en desarrollo y en la tubería.

**Lo que esto compra a BR1.2:** el arranque valida que estén las variables
requeridas y termina con código distinto de cero **nombrando la variable**, antes
de construir ningún cliente de proveedor y por lo tanto antes de la primera
llamada. Fallo cerrado, no fallo a mitad de la corrida.

## SEC-U1.3 y SEC-U1.4 — Cadena de suministro

| Control | Cómo se construye |
| --- | --- |
| Lockfile con hashes de integridad | Los dos gestores lo producen; se commitea en el mismo primer commit que el código |
| Instalación reproducible | El comando de instalación del archivo de tareas usa el modo que **falla si el lockfile no coincide**, nunca una resolución libre |
| Deriva del lockfile | El guion corre la instalación reproducible; un lockfile desactualizado hace fallar el paso sin necesidad de un chequeo aparte |
| Auditoría de vulnerabilidades | Un paso del guion en cada corrida; un hallazgo alto o crítico en una dependencia que el aplicativo ejecuta bloquea, y su excepción se escribe con fecha y razón |
| Espera de versiones recién publicadas | **Tres días**: una versión publicada hace menos de 72 horas no se instala. Configurado en el robot de dependencias y en los dos gestores. **Excepción escrita:** una versión que corrige un aviso de seguridad conocido entra sin esperar, porque esperarla dejaría abierta la vulnerabilidad que cierra |
| Licencias | Un paso del guion registra la licencia de cada dependencia y falla ante una que impida publicar el repositorio |

**Por qué tres días y no siete ni cero:** el ataque típico de cadena de
suministro vive en las primeras horas de una versión publicada, y la mayoría de
los paquetes comprometidos se retiran dentro del primer día. Tres días cubren esa
ventana con margen sin convertir cada actualización en una espera que empuja a
saltarse la regla. Siete darían más margen y harían que las actualizaciones se
acumularan; cero deja el proyecto expuesto al ataque más común que existe contra
un repositorio público.

## SEC-U1.5 — Permisos de la tubería

- **Permisos vacíos por defecto** a nivel del flujo, elevados por trabajo solo
  donde haga falta y solo a lo que haga falta.
- **Acciones de terceros fijadas por identificador de commit**, no por etiqueta:
  una etiqueta se puede mover y una etiqueta movida es código ajeno ejecutándose
  con los permisos de la tubería.
- **Un analizador de flujos** como paso del guion, para que la regla anterior sea
  comprobable y no una intención.
- **Los secretos del repositorio** se pasan al trabajo que los necesita, no al
  flujo entero.

**El trabajo del escaneo de secretos no necesita secretos.** Es el primero y el
que más superficie tiene; que corra sin credenciales es parte del diseño.

## SEC-U1.6 — Trazabilidad de lo publicado

Cada corrida registra, como campos obligatorios y no como nota: el commit, el
**identificador exacto de modelo por uso** —nunca un alias móvil— y el **hash del
prompt de cada nodo**. Es lo que permite responder "qué produjo esta cifra"
meses después, y lo que convierte un cambio de modelo en un cambio visible en el
diff contra la línea base en lugar de en una regresión inexplicable.

El identificador, el proveedor y sus parámetros viven en configuración
versionada. Cambiarlos es un cambio de código que dispara la compuerta de
evaluaciones.

## SEC-U1.7 — Ningún gasto no escrito

| Frente | Control |
| --- | --- |
| Proveedor del modelo | El subconjunto de arranque y el de la compuerta corren en el plan gratuito |
| Corte por cuota | El corredor detiene la corrida tras tres fallos seguidos de cuota o presupuesto (decisión Q2; el diseño está en `reliability-design.md`) |
| Minutos de integración continua | Filtros de ruta y cancelación de corridas anteriores sobre el mismo cambio; la medición de los 15 minutos corre semanal y por hito, no en cada entrega |
| Lo que nunca se filtra | La compuerta de evaluaciones: un filtro de rutas jamás la apaga |

**Las pruebas de límite no consumen el presupuesto que protegen.** El corte por
cuota se prueba inyectando la respuesta del proveedor en una prueba, nunca
llevando una clave real hasta su tope.

## SEC-U1.8 — Identidad en las operaciones contra el repositorio

La máquina tiene dos cuentas en el CLI de `gh`. Antes de cualquier operación
contra GitHub se comprueba que la activa sea `miguelczz`. **Es un control humano,
no automatizado**, y se dice así en lugar de fingir que una herramienta lo cubre.
Lo que sí se automatiza es su consecuencia: el repositorio es privado, y su
paso a público en la semana 12 es una decisión con su propia revisión de
licencias y su escaneo del historial completo.

## Lo que U1 deja preparado y no implementa

Estos controles son de otras unidades; U1 construye el sitio donde encajan y las
reglas de importación que impiden saltárselos:

| Control | Unidad | Qué deja U1 |
| --- | --- | --- |
| Aislamiento entre aseguradoras | U2 | El árbol de módulos y el contrato de importación que impide abrir conexiones fuera del punto único |
| Redacción de datos personales | U3 | El módulo `compliance/redaction/` en el árbol y la regla de que todo punto de salida pase por él |
| Guardia de salida y adversariales | U10, U21 | El corredor y el catálogo de frases |
| Límites de las superficies públicas | U13, U17 | Nada; U1 no tiene superficie pública |

## Datos personales en esta unidad

U1 **no guarda datos de personas**. Dos matices que sí le tocan y que el diseño
respeta:

- Los casos de golden set contienen valores con forma de dato personal, todos
  ficticios. Aun así pasan por la redacción cuando se escriben en una traza: la
  regla es "todo punto de salida redacta", sin excepción por origen, porque una
  excepción por origen es exactamente el agujero que después nadie encuentra.
- **Las grabaciones de audio de personas reales nunca entran al repositorio**
  (BR1.10). Lo que se versiona es el guion; cada voz registra su consentimiento
  fuera del repositorio. El guion de verificación incluye un chequeo de
  extensiones de audio en el árbol versionado, para que la regla sea un fallo y
  no un recordatorio.

## Modelo de amenazas, con su control de diseño

| Amenaza (STRIDE) | Control de requisitos | Cómo queda construido |
| --- | --- | --- |
| Divulgación de información | SEC-U1.1, SEC-U1.2 | Escaneo como primer trabajo con corte inmediato; plantilla de variables comprobada en las dos direcciones |
| Manipulación | SEC-U1.3, SEC-U1.4 | Instalación reproducible que falla ante un lockfile que no case; espera de versiones nuevas |
| Elevación de privilegios | SEC-U1.5 | Permisos vacíos por defecto, acciones fijadas por commit, analizador de flujos en el guion |
| Repudio | SEC-U1.6 | Commit, modelo exacto y hash de prompt como campos obligatorios de la corrida |
| Denegación de servicio | SEC-U1.7 | Corte del corredor por cuota; filtros y cancelación en la tubería, nunca sobre la compuerta |
| Suplantación | SEC-U1.8 | Comprobación de la cuenta activa antes de cada operación; control humano, declarado como tal |
