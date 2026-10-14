# Preguntas — Diseño de calidad de U4 `case-record`

Esta etapa traduce en arquitectura lo que la anterior decidió: cómo se monta el
cifrado dentro del módulo, qué pieza lo posee y qué pasa cuando falla.

La mayoría se deduce de decisiones ya tomadas y no se pregunta: el cifrado va del
lado del aplicativo, sobre los atributos de las otras partes y los valores de los
campos del caso, con la clave en una variable de entorno separada por uso. La
pieza que lo hace será un punto único, igual que la redacción de U3 tiene un solo
punto de salida, porque una segunda vía de escritura sin cifrar volvería el
control una cuestión de disciplina en vez de construcción.

Quedan dos huecos que ningún documento aprobado resuelve y que tienen dos
respuestas legítimas cada uno.

---

## Q1 — Qué pasa con las filas ya guardadas si la clave cambia

Ningún artefacto trata la rotación de la clave de cifrado. La regla del proyecto
sobre rotación habla de claves de proveedor filtradas, que es otra cosa: allí
rotar invalida lo viejo a propósito. Aquí rotar **no debe** volver ilegible un
caso que un ajustador tiene que poder abrir.

- A. **Cada fila guarda qué clave la cifró**, en una columna pequeña al lado del
  dato. Hoy hay una sola clave y nada cambia; el día que haya que rotar, las
  filas viejas se siguen leyendo con la clave vieja y las nuevas nacen con la
  nueva. El camino de rotación existe sin construirlo.
- B. **Una sola clave, sin identificador y sin camino de rotación**, y se escribe
  por qué: los casos de visitante mueren esa misma noche y el resto de datos son
  sintéticos. Si hubiera que rotar, se regeneran los datos sembrados.
- X. Other (please specify)

[Answer]: A

---

## Q2 — Qué se ve cuando un campo cifrado no se puede descifrar

Puede pasar: una clave equivocada en el entorno, una fila que viajó de una
máquina a otra, un dato corrupto. El caso sigue existiendo y el ajustador sigue
teniendo que decidirlo.

- A. **El caso se abre y el campo aparece como no disponible**, con su marca en
  la pantalla y un evento en la traza. El ajustador ve el resto del caso y sabe
  que ahí falta algo, en vez de encontrarse con una pantalla vacía.
- B. **El caso no se abre**: el fallo de descifrado es fallo de lectura del caso
  entero. Es la postura de fallar cerrado, y evita que alguien decida sobre un
  caso al que le falta justo el campo que importaba.
- X. Other (please specify)

[Answer]: A
