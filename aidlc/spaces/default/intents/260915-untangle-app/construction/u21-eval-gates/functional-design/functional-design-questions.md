# Preguntas — Diseño funcional de U21 `eval-gates`

U21 convierte las corridas de evaluación en una compuerta. Lo que ya está
fijado:
- **C-27:** el reporte por caso, criterio e idioma que dejó U1, con sus causas de
  "no medida" y "no comparable".
- **ADR-014:** el juez se calibra con TPR y TNR por criterio e idioma, con
  intervalo, y no con el 85 % de acuerdo.
- **ADR-013:** el segundo detector no comparte mecanismo con el primero.
- **La definición de regresión** de `team.md`: por caso en los conjuntos
  pequeños, por 2 puntos porcentuales en los grandes.

Quedan tres huecos.

**Cómo se respondieron.** Miguel delegó en la recomendación las decisiones de
construcción el 2026-09-21. Cada respuesta es la opción recomendada, con su
razón. La única que necesita algo suyo —las etiquetas de DS-7— va aparte, como
dependencia humana, no como pregunta bloqueante.

---

## Q1 — Cómo se ponen las etiquetas humanas de DS-7

Son 40 transcripciones, 20 por idioma, etiquetadas turno a turno y criterio a
criterio. Sin ellas el juez no se puede calibrar, y sin calibración sus
veredictos no cuentan.

- A. **(Recomendada)** Un comando local que muestra un turno con su criterio y
  espera el veredicto, guarda el avance y se puede dejar a medias. Las etiquetas
  quedan en un archivo versionado por idioma, con las tres particiones fijas.
- B. Montar Langfuse para anotar ahí. Es la herramienta que el PRD reserva para
  la anotación de la demo en vivo, pero para 40 transcripciones propias
  significa levantar y mantener un servicio antes de poder empezar.
- X. Other (please specify)

**[Answer]: A**

**Por qué.** Etiquetar es trabajo de Miguel y va a hacerse en ratos sueltos: lo
que importa es poder parar y seguir sin perder nada. Un archivo versionado
además deja la calibración auditable en el repositorio, que es donde vive todo
lo demás que decide una entrega.

---

## Q2 — Qué tan bueno tiene que ser el juez para que sus veredictos cuenten

- A. **(Recomendada)** Cuentan cuando el **límite inferior** del intervalo de
  confianza de TPR y el de TNR llegan a **0,80**, medidos por criterio y por
  idioma sobre la partición de prueba.
- B. Exigir 0,80 a la media, sin mirar el intervalo. Con 20 casos por idioma, una
  muestra afortunada habilitaría al juez con facilidad.
- C. Exigir 0,90 al límite inferior. Con este tamaño de muestra, casi ningún
  criterio llegaría, y casi todo se publicaría como "no medida".
- X. Other (please specify)

**[Answer]: A**

**Por qué.** El límite inferior es lo que protege de la muestra pequeña, que es
justo el riesgo de DS-7. El valor exacto se registra en `nfr-requirements` con
su comando, y no se baja para que un criterio pase; si un criterio no llega, se
publica como "no medida" y se recalibra.

---

## Q3 — Dónde vive la línea base y qué pasa cuando todavía no hay

- A. **(Recomendada)** Archivos versionados en `app/evals/baselines/`, uno por
  publicación y un puntero a la vigente. Sin línea base, la compuerta corre,
  publica y **dice en la cabecera que no comparó**.
- B. Una tabla en la base de datos. La compuerta corre en GitHub Actions, donde
  no hay base de datos, y lo que decide una entrega dejaría de verse en un diff.
- C. Sin línea base, la compuerta falla. Bloquearía la primera corrida de cada
  hito por no tener pasado.
- X. Other (please specify)

**[Answer]: A**

**Por qué.** Misma razón que los casos de golden set: son datos que deciden una
entrega y tienen que leerse en el repositorio. Y callar que no hubo comparación
haría leer "sin regresiones" donde no se comparó nada, que es exactamente el
fallo silencioso que esta unidad existe para evitar.
