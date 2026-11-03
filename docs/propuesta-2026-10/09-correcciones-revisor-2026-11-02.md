# Correcciones de un revisor externo (2026-11-02)

Una persona revisó el proyecto y Miguel aceptó sus correcciones. Este documento
lleva cada una con su decisión, su plan y su estado.

## Lo pedido

1. Que el RAG use pólizas de aseguradoras colombianas reales (por ejemplo, SURA
   para Agencia Castilla) y que se actualicen solas.
2. Que la agente pida los datos del accidente en un solo mensaje.
3. Que el ajustador sea un subagente que consulte internet, la póliza y lo
   demás, trabaje como un ajustador con experiencia y le muestre al usuario el
   porqué de sus decisiones.
4. Que el mensaje de la agente se vea en stream, no de golpe.
5. Guardrails para preguntas fuera de contexto, con un mensaje preestablecido
   que no gaste tokens y proteja la información.
6. Un MCP propio para las consultas rígidas, para ahorrar consumo.
7. Quitar el enlace a Langfuse que abre la última conversación.

## Decisiones de Miguel (2026-11-02)

| # | Decisión |
| --- | --- |
| 1 | Investigar si es legal; si no es viable, se queda lo que hay. Ver «Pólizas reales: lo que se encontró» |
| 2 | Sin pregunta: en el chat la agente pide en un mensaje todo lo que falta; en la llamada sigue de a una pregunta, porque por voz una lista larga no se retiene |
| 3 | **El ajustador de IA decide solo y explica**, con fuentes reales y un proceso detallado y visible. Enmienda la regla de que una persona firma toda decisión de cobertura y dinero |
| 4 | Respuesta progresiva **después** de la guardia de salida: se revisa completa y luego aparece palabra por palabra |
| 5 | Sin pregunta: intención «fuera de contexto» con frase fija del catálogo, sin llamar al modelo que redacta |
| 6 | Herramientas del agente para consultas rígidas, sin RAG ni modelo, publicadas además como servidor MCP propio |
| 7 | Sin pregunta: se quita el enlace |
| 3a | El ajustador usa **Claude Haiku**, lee la póliza y sus cláusulas, las reglas y el relato, consulta el valor del vehículo en la guía pública de Fasecolda y hace **como mucho 3 búsquedas web por caso**, con tope diario de casos en la demo pública. Todo lo que se pueda resolver con código (límites, deducibles, vigencia, valor de referencia) sale de las herramientas del punto 6, no del modelo |
| 3b | El visitante **solo ve** la decisión y su explicación: se quita la parte de la demo en la que juega a ser ajustador |
| 8 | Las pólizas ficticias se reescriben con la **estructura del mercado colombiano**, sin copiar texto ni nombrar aseguradoras reales |

## Pólizas reales: lo que se encontró

No es asesoría legal; es lo que muestran las fuentes.

- **Los clausulados son públicos.** Las aseguradoras radican los modelos de sus
  pólizas ante la Superintendencia Financiera, que los publica para consulta, y
  el régimen de protección al consumidor les pide publicar sus contratos
  estandarizados. Leerlos y citarlos con su fuente es de bajo riesgo.
- **Copiarlos no está claro.** La Ley 23 de 1982 protege toda obra original y
  no excluye expresamente los modelos de contrato privados. Copiar el texto
  entero en un repositorio público y en el corpus de la demo queda en zona gris.
- **El mayor riesgo es la marca.** La Decisión 486 protege las marcas notorias
  incluso frente a usos no comerciales que se aprovechen de su prestigio o la
  diluyan, y SURA es notoria. Una demo en la que «Agencia Castilla» vende
  pólizas SURA y un ajustador de IA decide coberturas con su nombre puede leerse
  como si SURA respaldara esas decisiones. Ese es el escenario que más podría
  perjudicar a Miguel.

**Conclusión:** usar aseguradoras reales por su nombre no es viable sin su
autorización. Se queda lo que hay, como pidió Miguel. Queda abierta una mejora
opcional que no tiene ese riesgo: reescribir las pólizas ficticias con la
estructura del mercado colombiano (hoy siguen la estructura de la póliza
estadounidense de ISO), sin copiar texto ni nombrar aseguradoras.

## Fases

| Fase | Contenido | Estado |
| --- | --- | --- |
| 1 | Quitar el enlace a Langfuse; guardrail fuera de contexto; respuesta progresiva tras la guardia | Hecho y en `main` |
| 2 | Datos del accidente en un solo mensaje (chat) | Revertido (`173baac4`): la lista armada por el código reemplazaba la respuesta del modelo y tumbó unas 20 pruebas de la u12. Se rehace para que el modelo pida todo lo que falta y el código solo compruebe que no omitió nada |
| 3 | Herramientas para consultas rígidas y servidor MCP | Hecho y en `main` (`06478984`). Pendiente de decisión: la guardia de salida bloquea los montos, así que deducible y límites salen hoy con la frase genérica |
| 4 | Pólizas con estructura colombiana (va antes del ajustador, que razona sobre ellas) | Pendiente |
| 5 | Ajustador de IA que decide y explica | Pendiente |

Cada fase se sube a GitHub cuando su revisión queda en verde. Nada se publica a
producción hasta que Miguel lo pruebe.

## Lo que cambia la fase 4 en lo publicado

El README, la landing y la guardia de salida dicen hoy que la IA nunca decide
cobertura ni montos. Cuando el ajustador de IA decida, esos textos se cambian en
la misma tanda. La guardia de salida sigue aplicándose a la agente que conversa;
la decisión del ajustador sale por su propia superficie y con su explicación.
