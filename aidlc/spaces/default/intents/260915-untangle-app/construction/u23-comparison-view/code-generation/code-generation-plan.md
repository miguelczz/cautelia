# Plan de generación de código — U23 `comparison-view`

Dos tandas, repartidas por **dónde puede correr cada una**.

| Tanda | Qué | Dónde | Por qué ahí |
| --- | --- | --- | --- |
| 1 | La pantalla completa: tres columnas con su estado propio, la divulgación, las preguntas de ejemplo, el texto de fuera de propósito, el apilado a 360 px, y su registro en el arnés | **Nube** | Es interfaz con respuestas declaradas: `vitest` corre allá y la pantalla se prueba con las tres respuestas servidas como datos, sin base |
| 2 | La costura real: las tres conversaciones de verdad, el idioma de la pregunta, la divulgación registrada en los tres casos, el emisor de la agencia en el contrato, el reconocedor de fuera de propósito y **la prueba de aislamiento sobre las trazas** | Aquí | Necesita base, corpus ingerido y trazas: la compuerta dura se lee en las trazas de una pregunta real |

**En serie.** La tanda 2 conecta lo que la 1 dibuja.

---

## Tanda 1 — La pantalla *(nube)*

1. La pantalla en `pages/comparison/`, con sus tres columnas y el estado cerrado por
   columna (`idle`, `loading`, `answered`, `failed`, `rejected`).
2. La divulgación de AC2.9.1, con la póliza de ejemplo de cada columna y el emisor de
   la de la agencia.
3. Las preguntas de ejemplo y el texto de fuera de propósito, del catálogo en los dos
   idiomas, con su paridad.
4. El apilado a 360 px con el nombre de la aseguradora visible en cada columna.
5. Su entrada en el registro de pantallas del arnés, como pantalla de visitante, con
   sus respuestas declaradas.

**Pruebas.** Una columna que responde no espera a las otras dos; una que falla no borra
las otras; un rechazo por límite dice cuál fue con la frase de su catálogo; `failed` y
`rejected` no se dibujan igual; la divulgación aparece antes de que exista el campo de
pregunta; y ninguna cadena visible está escrita en el componente.

**Reglas que cierra:** BR1.1, BR1.2, BR1.3, BR2.2, BR2.4.

---

## Tanda 2 — La costura y el aislamiento *(aquí)*

1. Las tres conversaciones reales por las rutas del chat, con el idioma de la pregunta.
2. **La divulgación de la vista registrada en los tres casos** (respuesta A de Q1): el
   chat recibe de qué superficie viene la conversación y marca la apertura como
   entregada con la clave de esa superficie. Es un parámetro aditivo, no una ruta nueva.
3. **`example_policy_issuer`** en la configuración, obligatorio para una agencia, en
   `TenantPresentation`, y el chequeo que lo compara con `issuer_tenant` del archivo
   versionado de la póliza (Q2). Con eso la respuesta declarada del arnés puede traerlo y
   la línea base de accesibilidad pasa a medir la pantalla llena.
4. **«Fuera de propósito» decidido en el servidor** por `coverage_detour.is_coverage_question`,
   sobre la superficie de la comparación: un mensaje que no es pregunta de cobertura no se
   admite ahí y no abre caso (Q3).
5. La prueba de aislamiento **sobre las trazas** de las tres columnas.
6. La prueba de que una pregunta descuenta tres mensajes de los límites.

**Reglas que cierra:** BR1.4, BR2.1, BR2.3, BR3.1, BR3.2.

---

## Tareas nuevas

| Tarea | Qué hace |
| --- | --- |
| `test:u23` | Solo las pruebas de esta unidad |

## Lo que no se toca

- **La respuesta de cobertura, la recuperación y el verificador de citas**: U13 y U8.
- **Los cinco controles del chat**: se usan, no se tocan.
- **El contrato de borrado**: esta vista no añade tabla ni purgador.
