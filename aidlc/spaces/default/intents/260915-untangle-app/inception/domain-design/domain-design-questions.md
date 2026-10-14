# Preguntas — Domain Design

Esta etapa define los componentes del aplicativo (qué piezas de software se
escriben, qué datos es dueña cada una y cómo se llaman entre sí) y registra las
decisiones de arquitectura que los documentos aprobados le asignan: el lenguaje
con sus herramientas (`team.md`, Code Style; pregunta abierta OQ2 de
`requirements.md`), el framework del grafo, la voz, los proveedores, el almacén
vectorial y la herramienta de evaluación (OQ3), el cambio de D-015 que dejó el
experimento 2, y las preguntas PA-1 y PA-5 que User Stories dejó para esta
etapa.

Casi todo lo resuelven ya el PRD (módulos MOD-01 a MOD-15 y su arquitectura
funcional), los requisitos, las historias aprobadas, las prácticas del equipo y
los resultados de los experimentos 02, 03 y 04. Esas decisiones las tomo yo con
su razón y las verás en la aprobación. Aquí solo quedan las cuatro que tienen
dos respuestas razonables y cambian lo que ve quien usa o evalúa el producto.

## Q1 — Idioma de las pólizas de cada aseguradora

Las cláusulas se muestran completas en el chat y se citan en la voz. User
Stories dejó abierto (PA-1) si cada aseguradora escribe sus pólizas en un idioma
o en los dos. Ya está aprobado que, si la cláusula está en otro idioma que la
conversación, se muestra en su idioma original con esa etiqueta y la explicación
va en el idioma de la persona, marcada como resumen, nunca como traducción
literal (AC2.3.4). De esto depende cuánto texto hay que generar y revisar, y qué
ve alguien que pregunta en el otro idioma.

A. Cada aseguradora escribe sus pólizas en su idioma por defecto: Stonecroft
   Mutual en español y Sunmeadow Auto en inglés; Knotwell guarda las copias de
   cada emisora en el idioma de la emisora. Una pregunta en el otro idioma recibe
   la cláusula original y el resumen en el idioma de la conversación
   (recomendada: la mitad del texto que generar y revisar, y muestra en vivo el
   comportamiento ya aprobado de AC2.3.4)
B. Pólizas bilingües: cada cláusula con su texto en español y en inglés bajo el
   mismo identificador, y la cita siempre en el idioma de la conversación (el
   doble de texto, y hay que comprobar que las dos versiones digan lo mismo)
C. Todas las pólizas en inglés, como una aseguradora de Estados Unidos, con
   resúmenes en español (lo más simple de generar, pero quien habla español
   nunca ve una cláusula en su idioma)
X. Other (please specify)

[Answer]: A

## Q2 — Qué pasa con un caso derivado por el límite de tres minutos si la persona vuelve a llamar

En el enlace público, al llegar a los tres minutos la agente resume, el caso
pasa a la bandeja con el motivo "límite de la demostración" y la consola da el
enlace del caso (AC5.12.1). También está aprobado que, si la persona vuelve a
llamar antes de quince minutos desde el mismo navegador, retoma su caso
(AC5.12.2). User Stories dejó abierto (PA-5) cómo conviven las dos cosas, porque
un caso en la bandeja está en pausa esperando una decisión humana.

A. Al retomar, el caso sale de la bandeja y vuelve a "en captura"; al terminar
   la llamada sigue el camino normal, a cierre o a derivación. Si alguien ya
   decidió el caso desde su enlace, no se retoma: la agente cuenta la decisión.
   Es una transición declarada solo para ese motivo y esa ventana (recomendada:
   en cada momento el caso tiene un solo dueño, la conversación o la bandeja)
B. El caso sigue en la bandeja mientras se retoma, y lo nuevo que se captura se
   agrega y se ve actualizado (sin transición nueva, pero alguien podría decidir
   el caso mientras la llamada todavía agrega datos)
C. Al llegar al límite, el caso queda "esperando al asegurado" durante los
   quince minutos y pasa a la bandeja solo cuando vence la ventana (el modelo de
   estados queda más simple, pero cambia AC5.12.1, que ya aprobaste, y la persona
   no recibe el enlace para decidir al colgar)
X. Other (please specify)

[Answer]: A

## Q3 — Con qué se construyen las pantallas

El centro del sistema va en Python, porque las librerías de las que depende
(LangGraph para el grafo, Presidio para los datos personales y los dos
frameworks de voz candidatos) tienen ahí su versión principal. Las pantallas
(inicio, chat, consola de llamada, comparación, bandeja, vista de caso y
paneles) necesitan además código en el navegador para el chat en streaming y la
llamada. Las prácticas piden un solo prefijo para el aplicativo, y cada lenguaje
suma su formatter, linter, comprobador de tipos y lockfile.

A. Páginas servidas por el mismo backend en Python, con HTML generado en el
   servidor y JavaScript liviano solo donde hace falta (el streaming del chat y
   la llamada). Un lenguaje principal y un solo juego de herramientas, pero sin
   un framework de interfaz reconocible para quien revisa el repositorio
B. Pantallas en React y TypeScript con Vite, compiladas a archivos estáticos que
   sirve el mismo backend en Python: un solo proceso desplegado, dos lenguajes
   con sus herramientas y una API tipada entre las dos partes (recomendada tras
   la investigación: es la forma del template oficial de FastAPI, los dos
   frameworks de voz candidatos traen sus componentes en React y no suma un
   segundo servidor)
C. Una aplicación web aparte con su propio servidor (por ejemplo Next.js) que
   usa la API del backend: dos lenguajes y dos procesos que desplegar y mantener
   despiertos
X. Other (please specify)

Discusión (guiada): en la primera ronda Miguel eligió Other y escribió: «Explícame el porqué de la decisión, además de que necesito saber arquitecturas, patrones de diseño, porque sería una app aparte la según opción sabiendo que veo que es la mejor opcion?». La opción B original (aplicación aparte en TypeScript) se separó en B y C para distinguir un solo despliegue de dos.

Segunda ronda: Miguel eligió Other y escribió: «Lo mejor creería, yo sería trabajar con la opción B puesto que hay dos razones muy importantes la primera buena prácticas y segundo me interesa que aquellas personas que entren a ver el proyecto vean cómo está construido y que pueden identificar que de verdad es un proyecto muy bien hecho ver una página o un desarrollo desarrollo de Software actualmente sin un framework es algo que no considero buena opción, sin embargo, si te pido que investigues a fondo que es lo mejor teniendo en cuenta esas cosas que menciona». Se investiga antes de pedir la respuesta final.

Investigación (2026-09-17): el template oficial full-stack de FastAPI usa React, TypeScript, Vite, TanStack Router y Query, Tailwind con shadcn/ui, cliente generado y Playwright, y compila el frontend dentro del backend, que lo sirve en el mismo dominio; Pipecat UI y los Agents UI de LiveKit son componentes de React sobre shadcn; en State of JavaScript 2025, React es el más usado (83,6 %) y Vite tiene 98 % de satisfacción, mientras Next.js bajó de 68 % a 55 %; el export estático de Next.js desactiva server actions y route handlers dinámicos. Con los criterios de Miguel (buenas prácticas y que quien revisa vea un proyecto bien construido), la recomendación pasa de A a B.

[Answer]: B

## Q4 — Cuándo se elige la librería de la voz

La voz necesita una librería que conecte el micrófono del navegador con la
transcripción, el grafo y la síntesis. Las dos candidatas del PRD son LiveKit
Agents y Pipecat. El experimento 1, que las compara con una llamada real y
prueba el hospedaje gratuito, todavía no se ha corrido. La frontera del
componente de voz es la misma con cualquiera de las dos, porque el grafo no
importa nada de la librería de voz.

A. Registro la decisión como pendiente con sus criterios, el experimento 1 corre
   antes de construir la voz (que llega después del camino completo en texto) y
   Domain Design se aprueba sin esperarlo (recomendada: no frena el diseño ni la
   construcción de la base)
B. Corro el experimento 1 ahora, hasta tres días y con cuentas de hospedaje y de
   transporte que abrirías tú, y cierro la decisión antes de aprobar Domain Design
X. Other (please specify)

[Answer]: A

## Q5 — En qué plan del modelo corre el chat público (pregunta de seguimiento)

Al escribir las decisiones de arquitectura apareció un conflicto que ningún
documento resolvía. El PRD (MOD-04) y D-015 ponen el chat público en el plan
gratuito de Gemini para no gastar el tope de 5 USD. Las condiciones de la API de
Gemini, consultadas el 2026-09-17, dicen que en el plan gratuito Google usa lo
enviado para mejorar sus productos, que personas pueden leerlo, y piden no
enviar información personal. Las prácticas del equipo tratan lo que entra por el
chat público como dato personal potencialmente real. Las evaluaciones y la
generación de datos usan solo datos sintéticos, así que para ellas el plan
gratuito no cambia.

A. Chat público en el plan de pago, con proyecto y clave propios, crédito
   prepagado sin recarga automática y los límites de mensajes ya aprobados,
   incluidos los embeddings de sus preguntas; el gasto cuenta contra el techo de
   5 USD y el prepago lo decides tú cuando el chat se publique. Las evaluaciones
   y la generación siguen en el plan gratuito (recomendada: nada de lo que
   escribe un visitante queda en manos de Google para entrenar, y es coherente
   con lo que el proyecto dice de cumplimiento)
B. Chat público en el plan gratuito, con un aviso al inicio de no escribir datos
   reales (costo cero, pero depende de que el visitante obedezca y contradice la
   instrucción del proveedor)
C. Chat público en el plan gratuito, redactando los datos personales antes de
   enviarlos al modelo (costo cero y nada personal sale, pero la agente no puede
   anotar placas, teléfonos ni cédulas escritos por el visitante, y el reporte se
   ve roto en la demo)
X. Other (please specify)

Discusión (guiada): Miguel eligió Other y escribió: «Explicame mejor esto». Se explicó con un ejemplo antes de volver a preguntar.

[Answer]: B
