# Diseño funcional — U19 `quote`

El flujo delgado de cotización sobre los mismos cuatro nodos: elegible, no elegible o
derivación al suscriptor, con una banda de riesgo y **sin un solo importe**.

La unidad no tiene directorio propio: sus piezas viven en los módulos dueños, cada una
como la parte que faltaba de un componente que ya existe (UG-7).

## Sources

- `../../../inception/user-stories/stories.md` — US6.1, US6.2, US6.3
- `../../../inception/requirements-analysis/requirements.md` — FR13.1, FR13.2, NFR13
- `functional-design-questions.md` — las tres respuestas y las ocho decisiones
- `docs/reference/estructura-solicitud-cotizacion.md` — los cuatro bloques

## Assumptions & Open Questions

None.

---

## Flujo 1 — Pedir una cotización en la misma conversación (US6.1)

1. La apertura ofrece cotizar **solo si la aseguradora lo tiene activo** en su
   configuración (`quote_enabled`, que ya existe). Hoy solo Sunmeadow Auto.
2. Quien pregunta pide cotizar. El caso nace con el tipo de registro `quote_request`.
3. El nodo `intake` pregunta **una idea a la vez** los cuatro bloques —conductor,
   vehículo, uso, historial— y **confirma cada bloque** antes de pasar al siguiente,
   con el mismo mecanismo de los siete bloques que ya captura para un siniestro.
4. Cuando los cuatro están confirmados, el caso queda completo para su tipo.

**El grafo no gana nodos** (FR13.1). Lo que cambia es qué bloques pide la captura
según el tipo de registro, que es un dato, no una rama.

**Donde está apagada** (AC6.1.3), la agente dice que esta demostración no cotiza y
ofrece lo que sí puede hacer. Es la decisión D4 de User Stories: no se ofrece lo que no
está construido, ni lo que esta aseguradora no tiene activo.

---

## Flujo 2 — Saber si soy elegible, sin recibir un precio (US6.2)

1. Con los cuatro bloques capturados, el motor de reglas aplica el **conjunto de
   elegibilidad** de esa aseguradora: las mismas reglas versionadas con `when`/`then` y
   sus casos de prueba dentro del YAML que ya usa el triage de siniestros. Corre en el
   **ritmo de fondo**, no dentro del turno: el turno emite una frase de espera del
   catálogo y lee lo que el fondo dejó en el estado.
2. La salida es una de tres: **elegible**, **no elegible** o **derivación al
   suscriptor**, con las reglas que la deciden y una **banda de riesgo** de cuatro
   valores (Q1).
3. La razón se dice en **lenguaje llano**, sin identificadores de regla: sale de la
   clave `explanation_key` de la regla que decidió, que vive en el catálogo de textos
   por idioma (AC6.2.3).
4. Si quien pregunta insiste en un precio, la respuesta no da ninguna cifra, explica
   que esta demostración no calcula precios y ofrece la banda (AC6.2.4). Es una frase
   fija del catálogo, no una improvisación del modelo.

**Ningún importe, y eso ya está construido** (AC6.2.2, `[bloquea]`). La guardia de
salida —el punto único por el que pasa todo texto que llega a una persona— tiene cuatro
patrones de importe y de porcentaje por idioma. Esta unidad **no construye un segundo
detector** (FD-U19-1): construye los casos de DS-4 que lo ejercitan por idioma.

---

## Flujo 3 — Decidir en la bandeja las solicitudes derivadas (US6.3)

1. El rol **`underwriter`** entra al enum de roles, con su fila en la tabla de
   permisos y la acción de decidir una solicitud de cotización.
2. Su bandeja muestra **solo solicitudes de cotización derivadas**: ni siniestros, ni
   solicitudes que las reglas ya resolvieron. El filtro es del servidor.
3. Declararla elegible, con comentario obligatorio, **reanuda el grafo** por el puerto
   de reanudación que ya existe, cierra la solicitud con resolución aprobado, y quien
   preguntó ve la decisión en su conversación. Declararla no elegible la cierra con
   resolución rechazado.
4. Una credencial de ajustador o de agente de cuenta **no puede decidirla**, ni por la
   pantalla ni por una petición directa a la API, y la solicitud no cambia (AC6.3.3).

**La decisión se registra antes de reanudar**, como la de un siniestro: al revés, un
caso puede quedar reanudado sin decisión escrita, y eso no se ve.

---

## Flujo 4 — Lo que la cotización no puede decir

Es la mitad que protege el principio, y por eso tiene flujo propio.

- **Ninguna respuesta con un importe, un símbolo o un código de moneda**, en ningún
  idioma. Compuerta dura.
- **Ningún porcentaje**: la guardia también los caza, y una banda expresada en
  porcentaje sería un precio disfrazado.
- **Ninguna razón con identificador de regla**: quien pregunta lee la condición, no
  `SUN-Q-03`.
- **Ninguna banda afirmada cuando la decide una persona**: la derivación dice
  `pending_review`, que es "todavía no se sabe".
- **Ninguna oferta de cotizar donde está apagada.**

---

## Lo que esta unidad no construye

- **Tarifas o precios actuariales**: fuera de alcance.
- **Nodos nuevos del grafo**: FR13.1.
- **Un detector de importes propio**: ya existe la guardia de salida.
- **El cableado del grafo de fondo**: es trabajo aparte, y toca los mismos archivos, así
  que no corre al mismo tiempo.

## Resumen de reglas (vista derivada)

Las reglas están en `rules.md`. Dos llevan `[bloquea]`: que ninguna respuesta de la
cotización contenga un importe, y que ninguna credencial sin el rol de suscriptor
decida una solicitud.

## Metas medibles

| Meta | Valor | De dónde |
| --- | --- | --- |
| Exactitud por campo de la solicitud | 95 % o más, por idioma | AC6.1.4, por hito sobre DS-4 |
| Derivaciones correctas | 100 %, por idioma | AC6.2.5, por hito sobre DS-4 |
| Derivaciones innecesarias | 10 % o menos | NFR13 |
| Respuestas con importe | **cero**, por idioma | AC6.2.2, en cada entrega |
