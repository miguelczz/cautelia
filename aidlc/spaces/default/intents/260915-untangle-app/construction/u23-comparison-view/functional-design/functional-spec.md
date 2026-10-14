# Diseño funcional — U23 `comparison-view`

La misma pregunta de cobertura respondida por las tres aseguradoras lado a lado, cada
columna con sus cláusulas citadas, su propio estado de carga y su propio fallo.

**Lo que hace valiosa esta vista no es que junte tres respuestas: es que demuestra en
un minuto que el aislamiento existe.** Tres columnas que citan cláusulas distintas de
corpus distintos es la prueba visible de lo que M9 promete.

## Sources

- `../../../inception/user-stories/stories.md` — US2.9
- `functional-design-questions.md` — la pregunta y las siete decisiones
- El código: `chat/api.py`, `chat/limits.py`, `chat/case_opening.py`, `tenancy/purge.py`

## Assumptions & Open Questions

None.

---

## Flujo 1 — Antes de la primera pregunta (AC2.9.1, AC2.9.6)

1. La vista dice que responde una asistente de inteligencia artificial, que es una
   demostración con pólizas de ejemplo, y **qué póliza de ejemplo usa cada columna**.
   La columna de Knotwell nombra además la aseguradora que emitió su póliza, porque
   Knotwell es una agencia y no emite.
2. Sugiere dos o tres preguntas de ejemplo, del catálogo por idioma.
3. No pide nada más: no hay credencial ni formulario.
4. Cuando llega la primera pregunta, **esta divulgación queda registrada en los tres
   casos** que la vista abre, con su hora, su idioma y su superficie. Las columnas no
   muestran la apertura de cada aseguradora: serían cuatro divulgaciones seguidas y tres
   ofertas de reportar un siniestro en una pantalla que compara coberturas (respuesta
   Q1).

---

## Flujo 2 — Una pregunta, tres respuestas (AC2.9.2 a AC2.9.5)

1. La vista detecta el idioma de la pregunta con el detector determinista que ya
   existe, y abre —o reusa— **una conversación por aseguradora** en ese idioma.
2. Manda la misma pregunta por las tres rutas del chat que ya existen, una por
   aseguradora, y escucha tres flujos.
3. Cada columna muestra **su propio estado de carga** y aparece en cuanto está lista.
   La que falla dice que no pudo revisar la póliza, y las otras dos siguen.
4. Cada respuesta llega con sus cláusulas citadas o con "no encuentro una cláusula",
   que son **dos valores distintos** y nunca el mismo (es la regla del proyecto, no
   una decisión de esta vista).
5. A 360 px las tres se apilan, con el nombre de la aseguradora visible en cada una.

**Cada pregunta cuenta como tres respuestas contra los límites del chat público**
(AC2.9.6), y no porque esta vista lo cuente: porque son tres mensajes por tres rutas
que ya llevan sus cinco controles. Cuando uno de los tres se rechaza, esa columna dice
cuál límite fue, con la frase de su catálogo, y las otras siguen.

---

## Flujo 3 — Una pregunta que no es de cobertura (AC2.9.6)

1. La vista explica que compara respuestas de cobertura y enlaza el chat de cada
   aseguradora, donde sí se puede reportar un siniestro.
2. No responde la pregunta fuera de propósito y no la manda a las tres columnas.

---

## Flujo 4 — Lo que esta vista no puede hacer

- **Ninguna columna recupera del corpus de otra aseguradora** (AC2.9.3, `[bloquea]`).
- **Ninguna columna afirma cobertura**: dice lo que su póliza dice, con la cláusula, y
  todo pasa por la guardia de salida como cualquier texto del chat.
- **La vista no redacta la diferencia** entre columnas: la diferencia se lee en las
  cláusulas citadas.
- **La vista no guarda nada propio**: sus conversaciones y sus casos son de visitante y
  los borra el contrato que ya existe.

---

## Lo que esta unidad no construye

- **La respuesta de cobertura, su recuperación y su verificación**: U13 y U8.
- **Ninguna ruta nueva del servidor** (FD-U23-1), con la excepción que Q1 decida.
- **Ninguna tabla.**
- **Publicar la vista**: pasada de publicación.

## Resumen de reglas (vista derivada)

Las reglas están en `rules.md`. Una lleva `[bloquea]`: que cada columna recupere solo
del corpus de su aseguradora, comprobado en las trazas.

## Metas medibles

| Meta | Valor | De dónde |
| --- | --- | --- |
| Columnas que recuperan de otro corpus | **cero**, comprobado en las trazas | AC2.9.3, en cada entrega |
| Hallazgos serios o críticos de accesibilidad | cero: es pantalla de visitante | D25 |
| Una columna caída deja de responder a las otras | nunca | AC2.9.5 |
