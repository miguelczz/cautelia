# Perfiles de usuario — Untangle

Seis perfiles ficticios desde cuyo punto de vista se escribe cada historia. No
son gente del proyecto: Miguel es su único integrante. Salen del PRD
(`docs/specs/prd.md`): los compradores del lado de quien contrata (sección 3.1),
la aseguradora ficticia y su asegurado (3.2), los recorridos narrados (7) y los
roles y permisos (9.3). El número lo fijó la entrevista de esta etapa
(`user-stories-questions.md`, Q1: seis perfiles).

Dos roles del PRD no son perfiles propios y aparecen solo dentro de las
historias que los necesitan: el **prospecto** que pide una cotización y el
**suscriptor** que decide su elegibilidad, ambos de la cotización (Should S1).
El **visitante del enlace público** tampoco es un perfil aparte: es Jordan
cuando prueba la demo, o cualquier persona que juega a ser asegurada con la
póliza de ejemplo.

Dos compradores del PRD 3.1 tampoco tienen perfil propio. El **engineering
manager** (10 minutos: alcance, decisiones de arquitectura, evidencia de
producción, comunicación escrita) queda cubierto por las historias de Jordan,
que revisan las decisiones de arquitectura, y por las de Taylor, que leen el
README y ven el video. La **persona del sector seguros** (ocasional, 10 minutos,
valida el realismo) participa en la validación del día 30 (S3), que se planifica
en Delivery Planning.

## Resumen

| Perfil | Lado | Qué busca en una frase | Épicas donde aparece |
| --- | --- | --- | --- |
| Jordan, staff AI engineer | Quien contrata | Comprobar por sí mismo, en 30 a 60 minutos, que lo declarado es lo que hay | Preguntar por cobertura, Decidir en la bandeja, Verificar la evidencia |
| Taylor, reclutadora técnica | Quien contrata | Decidir en 90 segundos si pasa el proyecto a un ingeniero | Verificar la evidencia |
| Camilo y Ana, asegurados | Ficción del producto | Reportar el accidente una sola vez y saber qué sigue | Reportar un siniestro, Preguntar por cobertura |
| Diana y Marcus Webb, ajustadores | Ficción del producto | Decidir con toda la evidencia a la vista, en minutos | Decidir en la bandeja |
| Priya Raman, agente de cuenta | Ficción del producto | Pasar el siniestro a la aseguradora que emitió la póliza | Decidir en la bandeja |
| Miguel, operador de la demo | El proyecto | Mantener la demo viva, honesta y dentro del presupuesto | Operar la demo |

## Jordan, staff AI engineer que evalúa

- **Rol:** ingeniero senior de IA en una empresa que ya despliega agentes. Revisa
  candidatos técnicamente y puede vetar. Es el cliente real del proyecto.
- **Objetivos:**
  - Verificar en 30 a 60 minutos que el README, las cifras y la demo dicen la
    verdad, sin confiar en la palabra de nadie.
  - Encontrar cómo falla el sistema, no solo cómo funciona.
  - Salir con material para una conversación técnica: decisiones de
    arquitectura, trazas, reglas, evaluaciones reproducibles.
- **Frustraciones:**
  - Portafolios de tutorial sin evaluaciones ni manejo de fallos.
  - Métricas sin línea base ni comando que las reproduzca.
  - "Multiagente" o "cumplimiento" usados como palabras de moda, sin controles
    detrás.
- **Comodidad técnica:** alta.
- **Frecuencia:** una sesión de 30 a 60 minutos por candidato; puede volver
  antes de la entrevista.
- **Contexto:** llega desde LinkedIn o la landing. Clona el repositorio, corre
  las evaluaciones, lee trazas, intenta romper el chat en vivo y juega a ser un
  asegurado para cerrar el ciclo en la bandeja con su propio caso. En la demo
  pública usa la misma póliza de ejemplo que cualquier otro visitante, así que
  solo ve y retoma los casos creados desde su propio navegador, y decide el suyo
  con un enlace firmado de una hora.

## Taylor, reclutadora técnica

- **Rol:** primer filtro de candidatos para puestos de ingeniería de IA en
  Estados Unidos o Europa.
- **Objetivos:**
  - Entender en 90 segundos qué hace el proyecto y si es serio.
  - Ver algo funcionando sin instalar nada.
- **Frustraciones:**
  - READMEs vacíos o que prometen lo que el proyecto no tiene.
  - Tener que leer código para saber de qué se trata.
- **Comodidad técnica:** media.
- **Frecuencia:** una vez por candidato, 90 segundos.
- **Contexto:** abre el README, mira el video corto y, si le convence, pasa el
  enlace a alguien como Jordan. Si la primera pantalla falla, nadie llega a la
  profundidad.

## Camilo y Ana, asegurados que acaban de tener un accidente

- **Rol:** clientes de una aseguradora ficticia que reportan un siniestro o
  preguntan por su cobertura, por voz o por chat.
  - **Camilo** es asegurado de Stonecroft Mutual, habla español y tuvo un choque
    leve en la autopista (recorrido 7.1 del PRD).
  - **Ana** es asegurada de Sunmeadow Auto, habla inglés y un árbol cayó sobre su
    carro estacionado (recorrido 7.4 del PRD).
  - Una variante de los dos es cliente de Knotwell Insurance Agency, con póliza
    emitida por cualquiera de las otras dos aseguradoras.
- **Objetivos:**
  - Contar lo que pasó una sola vez, sin repetirlo al cambiar de canal o si la
    llamada se cae.
  - Saber si está cubierto y en qué se basa la respuesta.
  - Saber qué sigue y cómo seguir el caso.
- **Frustraciones:**
  - Llamar en uno de sus peores días y tener que pelear con una máquina.
  - Recibir promesas de cobertura que después nadie sostiene.
  - Camilo: un servicio en español de segunda.
  - Ana: que la hagan repetir el accidente cada vez que cambia de canal.
- **Comodidad técnica:** media; llama desde el carro o escribe desde el teléfono.
- **Frecuencia:** rara; una vez cada varios años.
- **Contexto:** puede estar asustado, con prisa o enojado. En la demo pública,
  quien juega este papel usa la póliza de ejemplo de la aseguradora.

## Diana y Marcus Webb, ajustadores

- **Rol:** personas de la aseguradora que deciden cobertura y dinero sobre los
  casos derivados.
  - **Diana** es ajustadora de Stonecroft Mutual, la aseguradora conservadora;
    atiende casos en español (recorrido 7.2 del PRD).
  - **Marcus Webb** es ajustador de Sunmeadow Auto, la aseguradora flexible;
    atiende casos en inglés.
- **Objetivos:**
  - Decidir un caso derivado en minutos, con la transcripción, las cláusulas,
    la regla y la traza a la vista.
  - Corregir lo que la transcripción capturó mal sin borrar lo que dijo el
    asegurado.
- **Frustraciones:**
  - Casos incompletos que obligan a devolver la llamada.
  - Respuestas de cobertura dadas por alguien más, sin cláusula, que después
    tiene que desmentir.
- **Comodidad técnica:** media.
- **Frecuencia:** diaria.
- **Contexto:** trabajan desde la bandeja de su aseguradora y no ven nada de
  otra. La interfaz abre en inglés y cambia a español con el selector.

## Priya Raman, agente de cuenta de la agencia

- **Rol:** agente de cuenta de Knotwell Insurance Agency, que coloca pólizas de
  Stonecroft Mutual y de Sunmeadow Auto.
- **Objetivos:**
  - Pasar cada siniestro a la aseguradora que emitió la póliza, con todo lo
    capturado.
  - Que sus clientes reciban respuestas de cobertura citando la póliza de la
    emisora.
- **Frustraciones:**
  - Que alguien espere de la agencia una decisión de cobertura que no le
    corresponde.
- **Comodidad técnica:** media.
- **Frecuencia:** diaria.
- **Contexto:** en esta versión el caso se queda en la agencia marcado como
  enviado a la aseguradora; el traspaso real entre aseguradoras no existe (W1).
  Existe para demostrar que la misma pregunta recibe respuestas distintas según
  la póliza y que la regla de derivar siempre vive en configuración.

## Miguel, operador de la demo

- **Rol:** quien aprovisiona las aseguradoras, fija proveedores, límites y techo
  de gasto, regenera los datos sintéticos y mantiene publicada la demo. Absorbe
  al administrador de la aseguradora del PRD, que en esta versión no tiene
  interfaz: edita archivos de configuración versionados, igual que el operador.
- **Objetivos:**
  - Que la demo siga viva y honesta aunque él no esté mirando.
  - No gastar un dólar que no haya decidido gastar.
  - Cambiar proveedores, voz y límites según el tráfico real sin tocar código.
- **Frustraciones:**
  - Un cambio que rompe la demo en silencio.
  - Descubrir el gasto cuando ya se pasó del techo.
- **Comodidad técnica:** alta.
- **Frecuencia:** continua, con revisión semanal y por hito.
- **Contexto:** trabaja solo, con commits directos a `main` y GitHub Actions
  como compuerta (`team-practices.md`).

## Relaciones entre perfiles

- Jordan y Taylor evalúan a Miguel; Camilo, Ana, Diana, Marcus Webb y Priya
  Raman son la ficción que les permite hacerlo.
- En la demo pública, Jordan juega a ser Camilo o Ana con la póliza de ejemplo y
  después decide su propio caso en la bandeja con un enlace de una hora, en el
  papel de ajustador.
- Camilo y Ana generan los casos que Diana, Marcus Webb o Priya Raman reciben.
- Miguel no aparece en la conversación de nadie, pero sus límites, su techo de
  gasto y su reinicio nocturno condicionan lo que todos los demás ven.

## Orden de prioridad

Cuando dos perfiles quieren cosas distintas, gana el de más arriba. El PRD fija
que quien contrata va antes que la ficción del producto (decisión del
Segmento 3).

1. **Jordan.** Es el cliente real y puede vetar. Toda afirmación del sistema debe
   ser comprobable por él.
2. **Taylor.** Filtra antes que nadie. Si sus 90 segundos fallan, Jordan nunca
   llega.
3. **Camilo y Ana.** Su conversación es lo que se demuestra; la mayoría de las
   historias son suyas.
4. **Diana y Marcus Webb.** Cierran el ciclo con la persona que decide
   (principio P1).
5. **Priya Raman.** Demuestra la diferencia entre aseguradoras con un conjunto
   pequeño de historias.

Miguel queda fuera de este orden a propósito. Lo que él necesita (techo de
gasto, límites, datos sintéticos, aislamiento) no es una preferencia que se
negocia contra la de otro perfil: es una frontera que ninguna preferencia de los
demás puede cruzar.
