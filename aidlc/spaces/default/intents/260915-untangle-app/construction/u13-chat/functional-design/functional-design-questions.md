# Preguntas — Diseño funcional de U13 `chat`

Lo que ya está fijado y no se vuelve a discutir:

- **C-14:** la interfaz del turno ya existe y está construida en U12. Esta unidad
  la consume; no la cambia.
- **ADR-006:** el chat público corre en el plan gratuito de Gemini, con el aviso
  de no escribir datos reales antes de cualquier texto del visitante. Riesgo
  aceptado, no se vuelve a preguntar.
- **D-017:** el repositorio es privado y candidato a público en la semana 12.
- **UG-3:** una unidad que guarda datos de visitante implementa el contrato de
  borrado de U2 con su prueba.
- **Las compuertas duras** de esta unidad son pasa o falla por caso y no se negocian.
  Las nombra `rules.md`; ninguna decisión de esta etapa las toca.

Queda **una** decisión que ningún documento resuelve, y es de las tuyas: cambia lo
que ve quien evalúa el producto.

---

## Q1 — La vista de comparación: ¿entra en U13 o espera?

U13 tiene cuatro superficies. Tres son la conversación en sí: la página de chat, el
resumen de traza y el aviso de lo que decidió el ajustador. La cuarta es **la vista
de comparación**: la misma pregunta respondida por las tres aseguradoras, lado a
lado.

Esa cuarta es la que demuestra en un minuto lo que el proyecto afirma —que el mismo
sistema responde distinto según la póliza sin mezclar datos— y es la más cara de las
cuatro. Trae su propia compuerta dura (que cada columna recupere solo de su corpus),
su propia carga por columna con fallo aislado, y su propia pantalla.

En el PRD es **S5**, y el orden de corte escrito es S2, S1, C1, S5, S4. O sea que ya
está marcada para caer si el tiempo aprieta, y acabas de decirme que el tiempo
aprieta.

**Opción A — Entra en U13, como está planificada.** La demostración queda completa
en una sola unidad: quien abra el repositorio en la semana 12 encuentra la pantalla
que explica el proyecto sin leer nada. Cuesta más tanda y más tiempo en la unidad
más grande del plan.

**Opción B — Las tres superficies de conversación en U13, la vista de comparación en
una unidad propia después de U14.** U13 cierra antes y más pequeña, la vista de
comparación llega con la bandeja ya construida —que es cuando hay más casos reales
que comparar— y si el tiempo se acaba, lo que se cae es una pantalla de demostración
y no el canal de texto.

**Mi recomendación es la B**, y por una razón que no es el tiempo: la vista de
comparación es más convincente cuando hay casos de verdad detrás, y hoy no los hay.
Construirla ahora significa demostrarla con las tres pólizas de ejemplo y nada más.

Lo que no cambia en ninguna de las dos: las tres compuertas duras de aislamiento del
canal de texto (BR1.1, BR6.2, BR6.3) entran en U13 sí o sí.

**[Answer]:** Opción B — las tres superficies de conversación en U13, y la vista de
comparación en una unidad propia después de U14 (decisión de Miguel, 2026-09-28).

Consecuencia registrada: US2.9 sale del alcance de U13 y pasa a **U23
`comparison-view`**, declarada después de U14. La familia de reglas que este
diseño había escrito para ella (la divulgación de la vista, las tres respuestas
en el idioma, el aislamiento por columna como compuerta dura, la carga por
columna con fallo aislado y la diferencia explicada por una cláusula) se conserva
como semilla de esa unidad y se retira de aquí: un documento que declare reglas
que su unidad no construye es la deuda que TD-03 dejó en la landing, y no se
reproduce.
