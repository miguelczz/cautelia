# Preguntas — Diseño funcional de U6 `web-shell`

U6 es lo común a todas las pantallas y lo que el proceso servido hace por ellas:
el sistema de diseño con sus dos modos, el idioma, el cliente de la API, el
inicio, las páginas de estado, el arnés de accesibilidad que usarán las unidades
con pantallas, las cabeceras de seguridad y la salud del proceso. Es la primera
unidad con interfaz visible, y se construye **antes** que cualquier canal: el
chat llega con U13 y la voz con U16.

Casi todo está decidido. Los tokens, los modos y los componentes los fijan las
maquetas aprobadas (`design-system-mapping.md`, `interaction-spec.md`); el
framework y las herramientas, ADR-002; las convenciones HTTP y la salud, los
contratos C-01, C-02 y C-28; y la regla que más pesa aquí la fija `project.md`:
*nunca prometer en la interfaz una capacidad que no está construida*. Quedan tres
huecos con dos respuestas legítimas, y los tres cambian algo que se ve.

**Cómo se respondieron.** Miguel delegó las decisiones de construcción en la
recomendación el 2026-09-21 ("avances tanto como sea posible [...] la gracia es
de que hagas una verificacion de cual es la mejor opcion, la mas logica y por esa
misma te vayas"). Cada respuesta es la opción marcada como recomendada, con su
razón escrita antes para que se pueda discutir y revertir.

---

## Q1 — Qué muestra el inicio mientras no existen el chat ni la voz

La maqueta M1 es el inicio de la demo **terminada**: un título que promete
reportar un accidente y decidir el caso, "Cómo funciona" en tres pasos, y dos
botones por aseguradora, "Abrir chat" y "Llamar". Cuando U6 termine no existirá
ninguno de los dos canales, ni la comparación, ni los paneles. Y el inicio no se
puede dejar para después: está en el alcance de U6.

- A. **(Recomendada)** El servidor declara qué superficies están construidas y
  montadas, y el inicio muestra solo las acciones de esas superficies. El título,
  "Cómo funciona" y "Qué puedes probar" aparecen cuando existe el primer canal.
  Mientras no hay ninguno, el inicio muestra el nombre, el aviso de
  demostración, las tres aseguradoras con su carácter y su póliza de ejemplo, y
  una sola línea honesta: "Esta demostración todavía no tiene canales abiertos."
  Cada unidad que monta una superficie hace aparecer su acción sin tocar el
  inicio.
- B. El inicio completo desde hoy, con los botones hacia páginas de "próximamente".
  Rompe la regla de `project.md`: es exactamente prometer lo que no está.
- C. Aplazar el inicio hasta U13. Cambia el reparto aprobado de unidades y deja a
  U6 sin ninguna pantalla que el arnés de accesibilidad pueda recorrer, que es
  como construir el arnés sin probarlo.
- X. Other (please specify)

**Por qué la A.** La regla no se cumple por disciplina sino por construcción: si
la acción solo aparece cuando la superficie está montada, ningún despliegue puede
mostrar un botón roto aunque alguien olvide actualizar el inicio. Y el mismo
registro sirve al chequeo periódico (AC5.16.1), que tiene que saber qué
superficies comprobar.

[Answer]: A

---

## Q2 — En qué idioma se abre por primera vez una página sin aseguradora

El chat tiene su idioma: el de la aseguradora (C-25, `default_language`). Pero el
inicio y las páginas de estado no pertenecen a ninguna, y nada aprobado dice en
qué idioma se abren la primera vez. Quien llega puede venir de LinkedIn en
Colombia o de un reclutador en Estados Unidos.

- A. **(Recomendada)** El idioma del dispositivo si empieza por español; en
  cualquier otro caso, inglés. El selector con "Español" y "English" queda
  visible en la barra superior desde el primer momento.
- B. Siempre inglés, y el visitante cambia si quiere.
- C. Siempre español, y el visitante cambia si quiere.
- X. Other (please specify)

**Por qué la A.** Es la única que no obliga a nadie a buscar el selector antes de
entender la página, y trata igual a los dos idiomas (P12): ninguno es "el
original" del que el otro es traducción. Inglés como respaldo porque es el que
lee cualquiera que no hable ninguno de los dos.

[Answer]: A

---

## Q3 — Qué es "una sesión" para la telemetría de activación

AC5.16.6 pide contar sesiones con un mensaje, con tres turnos o más, y las que
cierran el ciclo en la bandeja, **sin guardar datos personales ni identificadores
del navegador que duren más que la sesión**. Para contar "una vez por sesión"
hay que reconocer la sesión, y hay dos formas de hacerlo.

- A. **(Recomendada)** La sesión es la **clave del navegador que ya existe**
  (`ut_visitor`, U2), que es por aseguradora y se borra en el reinicio nocturno.
  El avance de cada sesión se guarda como dato de visitante con su borrado, y lo
  único que sobrevive a la noche es el conteo por día, aseguradora e hito, sin
  ninguna columna que apunte a una persona.
- B. Un identificador nuevo por pestaña, guardado solo en la pestaña. Cuenta una
  sesión nueva cada vez que alguien abre otra pestaña o recarga, así que infla la
  cifra publicada, y agrega un segundo identificador del navegador que el
  proyecto no tiene hoy.
- X. Other (please specify)

**Por qué la A.** No crea ningún identificador nuevo: reutiliza uno cuya vida ya
está acotada y cuyo borrado ya está probado. Y la cifra que sale es la que un
lector espera de "sesión": la misma persona en la misma aseguradora ese día.

[Answer]: A
