# Preguntas — Diseño funcional de U7 `synthetic-data`

U7 es el generador de datos sintéticos, y de sus datos depende el resto del
proyecto: corpus de pólizas, pólizas emitidas, casos sembrados, las colisiones de
DS-8 y los valores personales ficticios. Varias cosas ya están fijadas:
- **ADR-016:** el modelo redacta una sola vez, alguien revisa y un generador
  determinista compone.
- **C-26:** la forma de la salida.
- **ADR-010:** los idiomas de cada corpus.
- **`docs/reference/estructura-poliza-iso-pap.md`:** la estructura de la póliza.

Quedan cuatro huecos.

**Cómo se respondieron.** El 2026-09-21 Miguel delegó en la recomendación las
decisiones de construcción. Cada respuesta es la opción recomendada, con su
razón.

---

## Q1 — Quién redacta los textos fuente

- A. **(Recomendada)** Un comando aparte, `mise run synthetic:draft` (tarea nueva), redacta
  una sola vez con Gemini en plan gratuito. Usa la clave del uso `operations`,
  hace una llamada por parte de la póliza, aseguradora e idioma, y pasa por el
  techo y el registro de gasto de U5.
  - Los borradores caen en `tmp/synthetic-drafts/`, que git ignora, y el
    generador nunca lee de ahí.
  - El agente de código revisa cada borrador contra la estructura de referencia
    y contra P8, y lo promueve a `app/data/sources/` (carpeta nueva), con su marca de revisión y
    un commit.
  - Miguel revisa una muestra de diez cláusulas por aseguradora emisora.
- B. El agente de código escribe los textos directamente, sin comando de
  redacción. Es más rápido, pero contradice ADR-016 y deja AC5.3.4 sin
  construir.
- X. Other (please specify)

**Por qué la A.** Es lo que aprobó ADR-016 y lo que pide AC5.3.4. El plan
gratuito no cuesta, y el texto es sintético, así que el uso de datos que Miguel
aceptó en ADR-006 no expone nada real.

[Answer]: A

---

## Q2 — Cuánto corpus

- A. **(Recomendada)** Para Stonecroft Mutual (en español) y para Sunmeadow Auto
  (en inglés):
  - un formulario base completo, con todas las partes de la referencia (acuerdo,
    definiciones y las partes A a F) y sus numerales, unas 50 a 70 cláusulas;
  - cinco endosos; el de Sunmeadow incluye el que amplía la cobertura de
    transporte, y Stonecroft no lo tiene, a propósito (AC5.4.3);
  - ocho distractores declarados: versiones anteriores de una cláusula y
    cláusulas casi idénticas a otra;
  - un documento de jurisdicción del Estado de Corvane, referenciado desde cada
    formulario.

  Knotwell guarda copias exactas de los dos, generadas desde el original.
- B. El mínimo de los criterios: cuatro endosos y solo los encabezados de cada
  parte. Alcanza para validar, pero no para las 20 preguntas de citación por
  idioma de DS-3, que necesitan cláusulas vecinas con qué confundirse.
- X. Other (please specify)

**Por qué la A.** DS-3 mide si la agente cita la cláusula correcta entre otras
parecidas. Sin numerales ni distractores, ese golden set sería fácil, y el
proyecto prohíbe construir un set donde los casos fáciles sean mayoría (P5).

[Answer]: A

---

## Q3 — De dónde salen las huellas de los formularios de terceros (AC5.4.4 y AC5.5.5, `[bloquea]`)

- A. **(Recomendada)** Un comando, `mise run synthetic:fingerprints` (tarea nueva), lee los
  specimens públicos del formulario PP 00 01: el de 1994 que publica el
  regulador de Maine y el de 2018 que publica el de Virginia, los mismos que cita
  la referencia.
  - Los lee desde `tmp/specimens/`, que git ignora, y guarda en el repositorio
    solo el hash de cada secuencia de ocho palabras, ya normalizadas y sin los
    encabezados estructurales. El texto de los specimens nunca se versiona.
  - `content:check` falla si una cláusula comparte **una sola** de esas
    secuencias.
- B. Quedarse con los marcadores de texto que ya tiene `content:check`. No
  cumple el criterio, que pide huellas y un umbral.
- X. Other (please specify)

**Por qué la A.** Es la única forma de comprobar "no hay texto ajeno" sin tener
ese texto en el repositorio.

**Límite, dicho de frente.** Las secuencias en inglés no detectan una traducción
al español. El corpus de Stonecroft depende de la revisión de la muestra por
Miguel (AC5.4.5) para ese caso.

[Answer]: A

---

## Q4 — Cómo llegan los casos sembrados a la base

- A. **(Recomendada)** El generador escribe cada caso como archivo en
  `app/data/tenants/<aseguradora>/cases/` (C-26).
  - Un comando, `mise run synthetic:seed` (tarea nueva), los carga por la API pública de U4
    con origen `generator`, el valor que U4 ya reserva para que el borrado de
    datos de visitantes no los toque.
  - Las pruebas que parten de un caso sembrado lo cargan dentro de su propia
    transacción, así ninguna ve los cambios de otra (AC5.6.3).
- B. Solo los archivos, y que cada prueba arme su caso. Repite en cada prueba lo
  que el generador ya sabe hacer.
- X. Other (please specify)

**Por qué la A.** U4 ya dejó el origen `generator` para esto. Restaurar los
sembrados cada noche es del reinicio de U20, que va a la pasada de publicación
(DP-14).

[Answer]: A
