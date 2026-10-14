# Preguntas — Diseño funcional de U8 `policy-rag`

U8 es la unidad que sostiene la promesa central del producto: que ninguna
cláusula citada sea inventada, ajena o vencida. Lo que ya está fijado y no se
vuelve a discutir:

- **ADR-010:** índice híbrido dentro de PostgreSQL con pgvector, fusión por
  rango recíproco, búsqueda vectorial exacta, cierre por relaciones entre
  cláusulas.
- **ADR-011:** un endoso vigente que modifica la cláusula citada rechaza la
  cita si la respuesta no lo considera.
- **ADR-003:** la escritura la hace el verificador, no el nodo, con clave
  idempotente, porque el grafo reejecuta el nodo al reanudar.
- **C-18 y C-26:** la forma de la API de U8 y la del corpus que le entrega U7.
- **D22:** la verificación de póliza corre en el ritmo de fondo, no dentro del
  turno.

Queda un hueco, y lo abrió el corpus real al existir.

---

## Q1 — Qué pasa cuando la póliza está en un idioma y la pregunta en el otro

Al leer el corpus que generó U7 aparece algo que ningún documento anterior
decidió: **cada aseguradora tiene su corpus en un solo idioma.** Stonecroft
Mutual son 104 cláusulas, todas en español. Sunmeadow Auto son 103, todas en
inglés. Knotwell, como agencia, guarda copias de las dos.

Y al mismo tiempo, el archivo de configuración de cada aseguradora dice, en su
propio comentario, que `default_language` es "el idioma con el que se abre, no
una restricción". O sea que Ana puede escribirle en inglés al chat de
Stonecroft y preguntar si le cubren el carro de alquiler — y la cláusula que
responde esa pregunta está redactada en español.

Esto no es un borde raro: es la mitad de las combinaciones posibles, y es
exactamente lo que va a probar quien abra la demo para ver si el bilingüismo es
de verdad.

- A. **(Recomendada)** La cláusula se muestra **en el idioma en que está
  escrita**; la respuesta, el resumen y el nombre de la parte van en el idioma
  de la conversación; y cuando los dos difieren, la respuesta lo dice con una
  frase del catálogo ("su póliza está redactada en español; se la resumo en
  inglés y le dejo la cláusula completa en el caso").
- B. El modelo traduce el texto de la cláusula y se muestra la traducción,
  marcada como no oficial, con el original al lado.
- C. La agente responde en el idioma de la póliza cuando el corpus está en otro
  idioma, y lo avisa.

**Por qué A.** La cláusula es el contrato. Una traducción hecha por el modelo
(opción B) es texto que nadie verificó ocupando el lugar del texto verificado:
sería la única cosa en toda la pantalla que el verificador exacto no puede
comprobar, justo en la unidad cuyo trabajo es que eso no pase. Y la opción C
rompe la promesa más visible del producto, que es responderle a cada persona en
su idioma.

A tiene además una consecuencia que ya estaba prevista sin que nadie la
nombrara: el catálogo de entidades aprobado en `domain-design` le puso a
`CoverageAnswer` dos campos separados, `answer_language` y `clause_language`.
Esos dos campos solo tienen sentido si pueden diferir.

Lo que cuesta: una clave nueva en el catálogo de copy, en los dos idiomas, y un
par de casos de DS-3 que prueben la combinación cruzada.

**Esta fue a Miguel y no se auto-respondió**, aunque la delegación del
2026-09-21 cubra las decisiones de construcción: cambia lo que ve quien abre la
demo para probar el bilingüismo, que es el criterio que separa lo que se decide
solo de lo que se le lleva. **Respondida por Miguel el 2026-09-26: opción A.**

[Answer]: A
