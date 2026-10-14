# Preguntas — Diseño funcional de U9 `rules-decision`

U9 es el motor de reglas y el nodo `decision`. Lo que ya está fijado:
- **C-19:** la firma de `evaluate` y `required_inputs`, y las tres categorías.
- **C-25:** la forma del archivo de reglas de cada aseguradora y que cada regla
  trae su prueba.
- **FR6.4:** la agencia deriva siempre por regla, sin rama de código.

Quedan tres huecos.

**Cómo se respondieron.** Miguel delegó en la recomendación las decisiones de
construcción el 2026-09-21. Cada respuesta es la opción recomendada, con su
razón.

---

## Q1 — Con qué se escriben las condiciones de una regla

- A. **(Recomendada)** Un conjunto cerrado de operadores que evalúa el código:
  `equals`, `in`, `present`, `absent`, `gte` y `lte`, combinados con `all`,
  `any` y `not`. Nada de cadenas de expresión ni `eval`.
- B. Un lenguaje de expresiones, como JSONLogic o CEL. Da más potencia, pero
  agrega una dependencia y una superficie de inyección para diez a veinte reglas
  que no la necesitan.
- X. Other (please specify)

**Por qué la A.** Es lo mínimo que expresan las reglas del PRD. Además, un
operador desconocido falla al cargar, no al evaluar.

[Answer]: A

---

## Q2 — Qué categoría sale cuando disparan varias reglas, o ninguna

- A. **(Recomendada)** Gana la más prudente: `referral`, luego
  `standard_review` y luego `direct_close`.
  - Una regla marcada como de cobertura o dinero fuerza `referral` (AC1.15.4).
  - Cada conjunto de reglas trae exactamente una regla por defecto, que siempre
    dispara con `standard_review`. Así ninguna categoría sale sin una regla que
    la justifique (FR6.2).
- B. Que el orden del archivo decida. Una regla movida de lugar cambiaría
  decisiones sin que nadie lo note.
- X. Other (please specify)

**Por qué la A.** Ante la duda, una persona revisa. Y la regla por defecto hace
visible el caso que ninguna regla previó.

[Answer]: A

---

## Q3 — Cómo se prueban las reglas antes de que exista el chat (rama evaluada)

- A. **(Recomendada)** Casos de DS-2 con los campos que el asegurado daría y la
  categoría esperada, por aseguradora e idioma, corridos por una sonda que
  aplica las reglas a esos campos.
  - Es el mismo camino que usó U10 con sus sondas.
  - Cuando existan la captura (U11) y el chat (U13), los mismos casos correrán
    de punta a punta.
- B. Esperar al chat para escribir los casos. La práctica del proyecto pide el
  caso antes de la conducta.
- X. Other (please specify)

**Por qué la A.** Cumple "primero el caso, después la conducta", y los casos
sirven igual cuando llegue el chat.

[Answer]: A
