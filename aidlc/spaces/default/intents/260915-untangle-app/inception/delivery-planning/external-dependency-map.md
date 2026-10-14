# Lo que no depende de nosotros — Untangle

Todo lo que puede detener o retrasar un **Bolt** (una pasada de construcción
sobre una pieza del trabajo) y que no está en nuestras manos: decisiones de
Miguel, personas de fuera, resultados de experimentos y otro intent. Cada fila
dice quién lo tiene, para cuándo, qué Bolt bloquea y qué se hace si no llega.

**Fuentes consumidas.** `../requirements-analysis/requirements.md` (la pregunta
abierta OQ4 de hospedaje), `../user-stories/stories.md` (las actividades con
personas que no son historias), `../refined-mockups/mockups.md` (las pantallas
que dependen del hospedaje), `../domain-design/components.md` (las dependencias
externas por componente), `../units-generation/unit-of-work.md` (las preguntas
abiertas PA-2 a PA-13), `../units-generation/unit-of-work-dependency.md` (la
tabla de condiciones externas por unidad),
`../units-generation/unit-of-work-story-map.md` (las historias afectadas),
`../contract-design/contract-summary.md` (el contrato del transporte de audio,
declarado pendiente) y `../practices-discovery/team-practices.md` (la regla de
cero renovaciones y el checklist del segundo día).

## Bloqueantes: sin esto, el Bolt no empieza

| Dependencia | Quién la tiene | Para cuándo | Bloquea | Plan B |
| --- | --- | --- | --- | --- |
| **Experimento de voz**: librería (LiveKit Agents o Pipecat), transporte y voz de respaldo | Esta sesión, con decisión de Miguel | Semana 2 (29 sep) | B18 y B19; aporta además el dato de WebRTC que B13 necesita para declarar navegadores | Si el experimento no concluye, se elige la opción con más evidencia publicada y se declara como no verificada en el ADR; nunca se empieza B18 sin decisión |
| **Instalar `mise`** en la máquina | Miguel | Antes del Bolt 1 | B1 y, por tanto, todo lo demás | Instalar Python, uv, Node y pnpm a mano con las versiones del ADR, y anotarlo como deuda |
| **Proyectos y claves de Gemini, separados por uso** (primero evaluaciones y generación) | Miguel | Antes del Bolt 5 | B5, y con él B6 en adelante | El generador puede correr con datos de muestra escritos a mano hasta que existan las claves, pero la medición de costo no arranca |
| **Etiquetas humanas de DS-7** para calibrar el juez | Miguel | Semana 4 | B12 no se cierra sin ellas | Los criterios que dependen del juez se reportan como "no medida" y no bloquean; las compuertas juzgadas por código siguen bloqueando |
| **Revisión de una muestra de textos fuente por idioma** | Miguel | Semana 3 | B6 no se cierra sin ella | Se genera el corpus y se marca como no revisado; ninguna superficie pública lo usa hasta la revisión |

## Con fecha: retrasan una medición, no la construcción

| Dependencia | Quién la tiene | Para cuándo | Afecta | Plan B |
| --- | --- | --- | --- | --- |
| **Decisión del tope de gasto de la voz** (Cartesia gratuito o plan de pago) | Miguel | Semana 6 (29 oct) | La voz principal de B19 y B20 | Cartesia gratuito por defecto; la voz de respaldo atiende cuando se agota |
| **Voluntarios para grabar DS-5 en inglés** | Miguel consigue | Semana 6 | La medición de latencia de B19 por hito | Miguel graba y se declara no nativo; se añaden variantes con ruido |
| **Tres personas de Medellín para la escucha a ciegas** | Miguel consigue | Semana 6 o 9 | Confirma la voz principal de B21 | Miguel decide escuchando, y queda escrito que la elección es de una sola persona |
| **Grabaciones de DS-5 en español** con consentimiento | Miguel consigue | Semana 9 | La medición por hito de B21 | Se reduce a cinco grabaciones, como dice la compuerta del día 60 |
| **Dos o tres revisores del perfil** para la validación externa | Miguel consigue | Cuando el chat y la bandeja estén en vivo | La primera compuerta de contenido | Se hace asíncrona con el video v1 |
| **Tres a cinco personas del perfil** para el piloto cerrado | Miguel consigue | Semana 8 | Las objeciones que entran al README | Se publica sin piloto y se recogen objeciones después, asumiendo el costo de la primera impresión |
| **Una persona del sector asegurador** que lea una póliza sintética | Miguel consigue | 30 oct | La credibilidad del corpus | Se declara en el README como suposición no validada |
| **Decisión de publicar el repositorio** | Miguel | Semana 12 | La compuerta del día 90 | Sigue privado y se comparte por invitación |

## Otro intent

| Dependencia | Dónde vive | Para cuándo | Afecta | Plan B |
| --- | --- | --- | --- | --- |
| **Hospedaje del aplicativo y de los estáticos**, incluida la página de espera con la instancia dormida (OQ4) | Intent `infra` | Antes de publicar el chat | B13 y el despliegue de B14, B15 y B17 | El chat y la bandeja corren en local para la validación externa, y el despliegue espera |
| **Origen del chequeo periódico, disparador nocturno y canal de alertas** (PA-10) | Intent `infra` | Antes de publicar el chat | B13 deja los endpoints; B16 deja el comando | El reinicio se dispara a mano hasta que exista el programador, y queda anotado como riesgo abierto |
| **Tubería de despliegue y observabilidad de plataforma** | Intent `infra` | Antes de publicar | El despliegue de todo lo público | Despliegue manual con el mismo `verify.sh`, como hoy con la landing |

## Proveedores externos en ejecución

No son dependencias de planificación, pero un fallo suyo detiene una medición o
una demostración. Están aquí para que el plan no los dé por sentados.

| Proveedor | Para qué | Qué pasa si falla |
| --- | --- | --- |
| Gemini | Modelo de lenguaje y embeddings | La corrida se marca **no comparable** con su causa y se repite; el umbral no se toca nunca |
| Deepgram | Transcripción en streaming | La llamada no puede empezar y la consola lo dice; el chat sigue vivo |
| Cartesia | Síntesis de la voz principal | Se atiende con la voz de respaldo, avisando en la consola |
| Langfuse | Backend de trazas | Nada del caso ni del gasto se detiene; se registra la pérdida de trazas |
| GitHub Actions | La compuerta | Un `main` en rojo por causa ajena se marca no comparable y se repite; la entrega se detiene hasta que la compuerta pueda correr |

## Cómo se usa esta tabla

Antes de empezar un Bolt se mira si tiene una fila bloqueante sin resolver. Si la
tiene, no se empieza: se avisa a Miguel con la fila y su plan B, y se construye
el siguiente Bolt que sí esté libre, siempre que el mapa de dependencias lo
permita. Ningún Bolt se empieza "a medias esperando" algo externo, porque eso es
exactamente lo que la práctica del equipo prohíbe.
