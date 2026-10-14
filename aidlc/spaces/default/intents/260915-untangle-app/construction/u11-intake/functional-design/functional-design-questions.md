# Preguntas — Diseño funcional de U11 `intake`

Lo que ya está fijado y no se vuelve a discutir:

- **D22:** dentro del turno corren solo tres controles baratos, y son de U10. La
  captura no detecta la emergencia: la respeta.
- **ADR-006:** unos 3.900 tokens de entrada por turno de voz, prompts
  versionados.
- **La corrección del 2026-09-19:** U11 no depende de U9. La derivación la
  produce el nodo de decisión después, en el ritmo de fondo.
- **`entities: []`:** U11 no crea ninguna entidad; escribe en las del caso de U4.

Quedan dos huecos, y los dos cambian lo que ve quien abre la bandeja.

---

## Q1 — Cuando alguien da dos versiones de un dato ya confirmado, ¿cuál es el valor del caso?

El criterio dice que el caso **guarda las dos versiones, cada una con su turno y
su hora** (AC1.12.1), y que la agente no acusa ni aconseja. Eso está claro. Lo
que no dice ningún documento es cuál de las dos es *el* valor: el que cuenta
para la completitud, el que lee la regla de la aseguradora y el que ve el
ajustador arriba en la ficha.

El caso típico es el que nombra el escenario RT-7: la persona confirma una
fecha, y más adelante dice otra anterior al inicio de la póliza.

- A. **(Recomendada)** El valor del caso sigue siendo **el primero confirmado**,
  y el segundo queda anotado como versión alternativa con su turno y su hora. La
  regla de la aseguradora no mira la fecha sola: mira que **haya** una versión
  que contradice, y por eso deriva.
- B. Gana el último: el valor del caso pasa a ser el nuevo y el anterior queda
  como histórico.
- C. El campo queda marcado en conflicto, **sin valor**, hasta que una persona
  elija.

**Por qué A.** Porque deja el caso legible sin decidir nada que no corresponda.
Con B, una persona que se corrige de buena fe —que es la mayoría— acaba con el
dato bueno reemplazado por el malo si se equivoca al final. Con C, el campo
queda vacío y la completitud de AC1.7.3 lo cuenta como faltante, así que un caso
perfectamente reportado se vería incompleto por haberse corregido.

A tiene una consecuencia que conviene ver antes de elegirla: obliga a que la
regla de U9 que deriva lea **la existencia de una versión que contradice** y no
el valor del campo. Es una línea más en el conjunto de reglas de cada
aseguradora, y hay que escribirla al construir U9's reglas de elegibilidad o
antes.

---

## Q2 — "Lesiones, conductor y lugar se confirman antes de anotarse": ¿lectura aparte, o basta la del bloque?

El catálogo de unidades le pone a U11 esa responsabilidad con esas palabras.
Pero cada bloque ya se lee de vuelta entero antes de contarse como confirmado
(AC1.7.1), y esos tres campos viven dentro de bloques que ya se leen. Leerlos
otra vez por separado son turnos extra, y la meta del hito es **14 turnos o
menos** por caso (AC1.5.6).

- A. **(Recomendada)** Basta la lectura del bloque, con una condición: la
  lectura tiene que **nombrar esos tres explícitamente** cuando aparecen, y no
  resumirlos. "Anotado: usted conducía, en la autopista salida 12, sin heridos.
  ¿Correcto?" cumple; "Anotado: los datos del accidente. ¿Correcto?" no.
- B. Lectura propia por campo para esos tres, aunque cueste turnos.

**Por qué A.** Porque lo que la responsabilidad protege es que nadie quede
anotado como conductor, herido o en un lugar sin haberlo dicho y confirmado — y
una lectura de bloque que los nombra uno por uno consigue exactamente eso. B
compra lo mismo pagando tres turnos por caso, que sobre una meta de catorce es
más de un quinto del presupuesto.

Si eliges B, la meta de 14 turnos hay que revisarla con ella, porque las dos
juntas no caben.

[Answer Q1]: A
[Answer Q2]: A

**Respondidas por Miguel el 2026-09-27**, las dos con la opcion recomendada.
