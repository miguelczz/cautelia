# Preguntas — Diseño funcional de U3 `pii-redaction`

Tres decisiones que los documentos aprobados no resolvían. Las tres cambian lo
que ve quien llega a mirar el aplicativo, y por eso se decidieron bajo la norma
que Miguel fijó el 2026-09-20: **si quien llega tiene que descifrar algo, está
mal**.

## Q1 — Qué se ve en lugar de un dato tapado

`AC4.12.3` dice que el teléfono aparece "como una etiqueta de su tipo y nunca
con sus dígitos", pero no dice qué etiqueta.

- A. Etiqueta traducida y numerada
- B. Etiqueta traducida, sin numerar
- C. Etiqueta técnica fija en inglés

[Answer]: A

**Decidida por Claude bajo la norma de legibilidad, con una precisión sobre la
opción tal como estaba escrita.** La opción A planteaba resolver el idioma al
mostrar, de modo que el mismo dato guardado se viera `[TELÉFONO 1]` o
`[PHONE 1]` según quién leyera. Rige en cambio esto: **la etiqueta se escribe en
el idioma de la conversación**, desde el catálogo de textos, y se guarda ya
escrita.

Dos razones:

1. Una conversación sostenida en español es un artefacto en español. Un
   `[PHONE]` incrustado en prosa española se lee peor que un `[TELÉFONO]`, y el
   que revisa la bandeja está leyendo la conversación del asegurado, no la suya.
2. Un renglón de log o una traza exportada se leen **fuera** del aplicativo, sin
   catálogo que resolver. Guardar la etiqueta ya escrita hace que se entiendan
   solas; guardar un token haría que ahí se viera un símbolo interno.

**El número se mantiene, y es la mitad que importa.** Sin él, el teléfono del
asegurado y el del testigo se ven idénticos y quien lee el caso no puede saber
si eran dos personas o una repetida:

> Mi teléfono es `[TELÉFONO 1]` y el del testigo es `[TELÉFONO 2]`

**Alcance de la numeración, acotado tras la revisión.** Vale dentro del texto
que se redacta en una llamada y empieza de nuevo en la siguiente. Mantener el
mismo número para el mismo teléfono a lo largo de la conversación exigiría
guardar la correspondencia entre el valor real y su número, que es justo la
bóveda que BR1.6 prohíbe; el hallazgo R-01 de la revisión encontró esa
contradicción. Donde la numeración de verdad sirve —distinguir el teléfono del
asegurado del del testigo— es dentro del mismo turno.

La opción C queda descartada porque rompe la paridad de idiomas que el proyecto
sostiene en todo lo demás.

## Q2 — A qué formatos apuntan los reconocedores

El mundo del producto es una jurisdicción ficticia, Corvane, pero el chat es
público y entra gente real.

- A. Formatos reales de Colombia y EE. UU.
- B. Solo los formatos de Corvane

[Answer]: A

Decisión de Miguel. Desde el día en que el chat público existe entran datos de
personas reales aunque el corpus sea sintético, y un reconocedor que solo
conozca un formato inventado los deja pasar en claro. Es exactamente lo que este
componente existe para impedir.

## Q3 — Qué pasa con lo que ningún reconocedor declara

- A. Regla de respaldo por contexto
- B. Solo lo que un reconocedor declara

[Answer]: A

Decisión de Miguel. Además de los cuatro reconocedores, se tapan secuencias
largas de dígitos cuando el texto alrededor habla de un dato personal. Cubre el
formato que nadie previó, que es por donde se escapan las cosas. El costo
aceptado es que alguna vez tapará un número que no hacía falta tapar, y que eso
se verá en la transcripción.

**Consecuencia que esta decisión obliga a declarar:** la medición de `AC4.13.3`
es por idioma y por tipo de entidad. El respaldo no es un tipo de entidad, así
que se reporta como su propia fila y nunca se suma a la de un reconocedor: un
respaldo que dispara mucho escondería que un reconocedor dejó de funcionar.
