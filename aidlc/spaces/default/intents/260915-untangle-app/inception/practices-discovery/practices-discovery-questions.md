# Preguntas de Practices Discovery

Ocho preguntas sobre cómo trabaja el equipo. Cubren las cinco áreas que se
promueven a la memoria del espacio: forma de trabajar, primer trozo de
construcción, posture de pruebas (dos preguntas), despliegue y estilo de código;
más dos que añadieron los especialistas al revisar el borrador (dónde corren los
controles antes de que exista la integración continua, y cómo se cuenta una
regresión).

Cada pregunta lleva su recomendación con la razón. Responde escribiendo la letra
en el `[Answer]:` correspondiente.

---

## Q1 — Cómo entran los cambios a la rama principal (Way of Working)

Trabajas solo. ¿Cada cambio de código pasa primero por una rama aparte que se
revisa sola con las pruebas automáticas, o commiteas directo a la rama principal
y dejas que las pruebas te avisen después?

- `A.` Rama corta con pull request para todo lo que sea código; el autor mergea cuando las pruebas están en verde; documentación y registro del flujo también por rama.
- `B.` Rama corta con pull request para el código; documentación y registro del flujo, directos a la rama principal.
- `C.` Commit directo a la rama principal para todo; las pruebas corren después del merge y se arregla hacia adelante.
- `X. Other (please specify)`

**Recomendación: B.** La rama existe para que las pruebas corran antes que la
rama principal, y un cambio en un documento del registro no tiene pruebas que
correr. Aviso: los defaults del espacio dicen que *todo* el trabajo entra por
rama, así que B necesita tu afirmación explícita para no leerse como una
contradicción. Aviso del especialista de seguridad: hasta la semana 3 o 4 no
existe integración continua, así que la rama no protege nada por sí sola; lo que
protege es la respuesta a Q7.

[Answer]: X. Other (please specify) — Commit directo a la rama principal (equivale a `C.`), con una precisión de Miguel: se usará GitHub Actions como integración continua y esas serán las pruebas. Palabras de Miguel: "Aunque es verdad, que trabajo solo vamos a hacer uso de GitHub actions, por lo mismo con el tema del CI/CD, este será las pruebas para los tests .Así usaremos la subida de código directa a la rama Main"

**Consecuencia registrada:** con commit directo, la integración continua corre *después* de que el cambio ya está en la rama principal. La compuerta existe, pero es posterior al aterrizaje. Eso hace que Q7 (controles locales antes del commit) pase de conveniente a necesario: es lo único que puede detener un fallo antes de que entre.

**Tensión con los defaults del espacio, registrada explícitamente:** `org.md` dice "All work merges to `main` via short-lived feature branches". La respuesta de Miguel afirma una práctica de equipo distinta para este proyecto. Sigue siendo desarrollo sobre tronco único (la variante sin rama intermedia), y esta etapa existe precisamente para que la práctica afirmada del equipo reemplace el default del framework en las cinco secciones. Se resuelve así, no se arrastra.

---

## Q2 — El primer trozo de construcción (Walking Skeleton)

¿Construimos primero una rebanada delgada que atraviese todo de punta a punta?
Un esqueleto de ese tipo es una versión mínima que corre el camino completo (en
texto: entra un relato, sale un caso con su cláusula citada), construida primero
para probar que las piezas conectan antes de que entren las funciones de verdad.

- `A.` Sí, y con parada formal: apruebas ese primer bloque antes de que arranque el siguiente, y el sistema te lo pregunta explícitamente.
- `B.` Sí, pero sin parada formal: el orden por capas basta y sigues de largo.
- `C.` No: empezar por piezas sueltas (corpus, reglas, recuperación) y conectarlas cuando estén; el camino completo aparece hacia la semana 3.
- `X. Other (please specify)`

**Recomendación: B.** El PRD ya exige el orden por capas (riesgo R1 y la línea
base de la semana 3), y el archivo de configuración de este flujo tiene la
ceremonia de parada apagada. Si quieres A, hay que cambiar esa configuración, no
las prácticas del equipo.

[Answer]: X. Other (please specify) — No al esqueleto delgado de punta a punta primero (se aparta de `A.` y `B.`, y matiza `C.`). Palabras de Miguel: "No la gracia de que tengamos una base construida la cual sea solida. Después de eso haremos la creación de componente Uno A uno para mí eso es lo más indicado en lugar de dejar un componente a medias es que después nos puede quedar mal construir"

**Lectura registrada:** primero una base sólida y terminada (caso, inquilinos con aislamiento, corpus, grafo); después los componentes **uno a uno**, cada uno completo antes de empezar el siguiente. El criterio explícito es no dejar componentes a medias.

**Consecuencia para la planificación de la entrega:** esto describe un recorrido por componente (cada pieza atraviesa todas sus etapas antes de pasar a la siguiente), no un recorrido por etapa (una etapa para todas las piezas, luego la siguiente). El framework admite ambos y la elección se fija al entrar en Construcción; queda anotada aquí como preferencia afirmada del equipo.

---

## Q3 — Cuándo se escriben las pruebas (Testing Posture)

Con evaluaciones automáticas de por medio, ¿en qué orden trabajas: primero el
caso de prueba y después el código, primero el código y después la prueba, o
distinto según de qué se trate?

- `A.` Distinto según el tipo: el caso del conjunto de evaluación se escribe antes de implementar el comportamiento que mide; las pruebas unitarias del código determinista se escriben junto con su capa, después de implementarla.
- `B.` Todo primero la prueba, incluidas las unitarias del motor de reglas y del verificador de citas.
- `C.` Todo primero el código y las pruebas al cerrar cada capa; los conjuntos de evaluación se escriben cuando haya algo que medir.
- `X. Other (please specify)`

**Recomendación: A.** Es lo que el calendario del PRD ya describe y lo único
compatible con tu principio de no publicar una métrica sin su conjunto de
evaluación. El especialista de calidad advierte que, si eliges A, la frase que
describe ese orden **es** el plan de pruebas completo que recibe la etapa de
generación de código, así que hay que redactarla con dos ramas exhaustivas y sin
ambigüedad; eso lo corrige el lead al integrar.

[Answer]: A

---

## Q4 — El piso de cobertura (Testing Posture)

El default de la casa pide que el 80 % de las líneas de código esté cubierto por
pruebas. ¿Lo medimos sobre todo el aplicativo junto, o exigimos ese 80 % pieza
por pieza?

- `A.` 80 % agregado sobre el aplicativo, con piso del 80 % también en las piezas críticas (motor de reglas, verificador de citas, aislamiento entre inquilinos, esquema del caso); la interfaz y los adaptadores de proveedor pueden quedar por debajo mientras el agregado se cumpla.
- `B.` 80 % exigido en cada paquete por separado, sin excepciones.
- `C.` 80 % agregado y sin piso por pieza.
- `X. Other (please specify)`

**Recomendación: A.** Pone la exigencia estricta donde el riesgo es real, sin
obligarte a cubrir al 80 % una capa de interfaz que el video demuestra mejor que
un test. Hallazgo del especialista de calidad: para este tipo de flujo el piso
del 80 % **no se activa solo**, así que hay que escribirlo como obligación
propia con su comando y su lista de exclusión; si no, sobrevive solo como prosa.

[Answer]: A

---

## Q5 — Qué se publica y cuándo (Deployment)

Las tuberías de integración y despliegue son un trabajo aparte (semanas 3 y 4).
Mientras tanto, ¿qué queremos que esté vivo en internet y con qué condición para
publicarlo?

- `A.` Solo el chat web y la bandeja de demostración, en tier gratuito, publicados cuando las compuertas duras estén en verde y el checklist del segundo día cumplido; la voz nunca se publica, solo se demuestra en video.
- `B.` Lo anterior más un enlace en vivo de la voz, con límite por visitante.
- `C.` Nada en vivo hasta la semana 11; todo se demuestra en video y en local.
- `X. Other (please specify)`

**Recomendación: A.** Es lo que el PRD ya clasifica (el chat y la bandeja son
obligatorios; el enlace en vivo de la voz es un "podría") y lo único que respeta
el tope de 5 USD: un visitante hablando con la agente es gasto sin techo. El
especialista de seguridad añade que el límite de mensajes del chat debe ser
condición para publicar, y configurado también en el proveedor, porque un límite
que vive solo en la aplicación falla abierto cuando lo que falla es la
aplicación.

[Answer]: B

**Decisión de Miguel:** además del chat y la bandeja, un enlace en vivo de la voz con límite por visitante. Se le explicó el punto completo antes de decidir y eligió B.

**Condiciones que hacen viable B, afirmadas como parte de la práctica:** (a) límite duro por visitante (una llamada, con duración máxima) y por día, configurado **también en el proveedor** y no solo en la aplicación, porque un límite que vive solo en la aplicación falla abierto cuando lo que falla es la aplicación; (b) techo mensual de gasto con corte automático: alcanzado el tope, la voz rechaza llamadas nuevas con un mensaje honesto y el chat sigue vivo; (c) alerta de consumo antes del techo; (d) la condición de publicación es la misma que para el chat: compuertas duras en verde y checklist del segundo día cumplido.

**Tensión con el alcance del PRD, registrada para la siguiente etapa:** el PRD clasifica el enlace en vivo de la voz como `C5` ("podría", fuera del MVP) precisamente por el costo, y fija el tope en 5 USD (D-015, M20). Esta decisión lo mueve hacia lo intencionado. Eso es un cambio de alcance, y esta etapa no es donde se cambia el alcance: `requirements-analysis` (2.3) debe reconciliarlo con el PRD y decidir explícitamente si el tope de gasto sube o si el límite por visitante se calibra para caber en los 5 USD. La práctica afirmada aquí es la **condición de publicación**; la promoción de `C5` al alcance necesita su propia decisión.

---

## Q6 — El estilo del código sin lenguaje elegido (Code Style)

Todavía no está decidido en qué lenguaje se escribe el aplicativo. ¿Qué hacemos
con el formateo y las reglas de estilo mientras tanto?

- `A.` Afirmar la obligación sin la herramienta ("formatter y linter del lenguaje, configurados en la raíz del aplicativo, corriendo antes del merge y bloqueándolo") y elegir las herramientas concretas en el mismo bloque de trabajo que el primer código. Además, fijar hoy las convenciones que no dependen del lenguaje: un solo directorio raíz para el aplicativo, un directorio por módulo, una sola grafía para los cuatro nodos en código, trazas y evaluaciones, y reglas de dirección de dependencias que hagan verificable que el orquestador es código.
- `B.` Decidir el lenguaje ahora, aquí, y con él las herramientas.
- `C.` Dejar el estilo sin regla hasta después del primer código y añadir el linter cuando haya algo que analizar.
- `X. Other (please specify)`

**Recomendación: A.** Deja la práctica escrita hoy y viva mañana, sin adelantarse
a una decisión de arquitectura que tiene su propia etapa. La segunda mitad de A
la propuso el especialista de desarrollo: diez convenciones que sobreviven a
Python o a Node y que son las que deciden si "el orquestador es código" es
verificable o solo una intención. Importante: el alcance del linter debe excluir
la landing y el andamiaje del flujo, o la compuerta arranca en rojo el primer
día por código que no escribimos.

[Answer]: A

---

## Q7 — Dónde corren los controles antes de que exista la integración continua

Los controles del borrador terminan todos en "antes del merge", pero la
integración continua es otro trabajo aparte que llega en las semanas 3 y 4,
justo después de que se escriba el código de mayor riesgo (aislamiento entre
inquilinos, tokens, esquema del caso, motor de reglas). ¿Qué hacemos en el
intervalo?

- `A.` Un solo guion de verificación en el repositorio (pruebas, tipos, formato, linter, chequeos de contenido) que se invoca igual en local y, cuando exista, desde la integración continua; más un gancho que lo corra antes de cada commit. Se crea en el primer bloque de construcción.
- `B.` Solo el guion de verificación, corrido a mano cuando te acuerdes; sin gancho automático antes del commit.
- `C.` Esperar a la integración continua de las semanas 3 y 4; hasta entonces sin controles automáticos.
- `X. Other (please specify)`

> **Contexto actualizado tras la respuesta a Q1.** Miguel ya decidió usar GitHub
> Actions como integración continua, así que la tubería existirá antes de lo que
> suponía esta pregunta. Pero al commitear directo a la rama principal, esa
> compuerta corre **después** de que el cambio ya aterrizó. El guion local y el
> gancho previo al commit dejan de ser un puente hasta que llegue la integración
> continua y pasan a ser lo único capaz de detener un fallo *antes* de que entre.

**Recomendación: A.** Es el hallazgo más importante de la revisión de seguridad:
sin esto, las semanas de mayor riesgo transcurren sin ninguna compuerta. Un solo
guion evita además que lo local y la integración continua se desincronicen. El
plan ya lo anticipaba en su paso 8.

[Answer]: C

**Decisión de Miguel:** confiar solo en GitHub Actions; sin gancho previo al commit ni obligación de correr el guion en local. Se le presentó explícitamente la consecuencia sobre el historial y aun así eligió C, así que es su decisión y se registra como tal.

**Riesgo residual registrado, con su mitigación compatible con C:** el fallo entra a la rama principal antes de que nada lo revise, y un secreto commiteado permanece en el historial aunque se borre después (D-017 contempla hacer público el repositorio en la semana 12). Mitigaciones que **no** reabren la decisión: (a) el escaneo de secretos es el primer trabajo del flujo de GitHub Actions, para que el aviso llegue en minutos; (b) se activa la protección de inserción del propio GitHub si está disponible para el repositorio, que rechaza el envío en el servidor sin depender de nada local; (c) toda clave detectada se rota, no solo se borra; (d) el guion único de verificación se escribe igual (es lo que GitHub Actions invoca), simplemente no se exige correrlo antes del commit.

---

## Q8 — Cuándo una caída de métrica bloquea el merge

El PRD fija que una caída mayor de 2 puntos porcentuales frente a la línea base
bloquea el merge. El especialista de calidad hizo la cuenta: con 30 casos por
idioma, **un solo caso** mueve 3,3 puntos, y con los conjuntos más pequeños hasta
10 puntos. Tal como está, la compuerta se dispararía casi siempre y acabarías
apagándola. Además no hay salida escrita para cuando una compuerta se pone roja
por una causa externa al cambio (un proveedor caído, el juez descalibrado).

- `A.` Contar casos, no porcentajes, en los conjuntos pequeños: cualquier caso que pase a fallar bloquea y exige explicación escrita; el umbral de 2 puntos se reserva para métricas de denominador grande. Y documentar una salida explícita para causas externas: se registra la causa, se marca la corrida como no comparable y no se toca el umbral.
- `B.` Mantener el 2 % tal cual y aceptar que la compuerta exija explicación a menudo.
- `C.` Subir el umbral a 10 puntos para que no moleste.
- `X. Other (please specify)`

**Recomendación: A.** B convierte la compuerta en ruido, y el ruido termina en
apagarla. C la vacía de contenido: con 30 casos, 10 puntos son tres casos rotos
pasando sin aviso. A conserva el rigor y lo hace operable. Tu PRD marca el 2 %
como valor por defecto, así que ajustarlo aquí es legítimo.

[Answer]: A

---

## Registro de modo de interacción

[Answer]: Guide me
