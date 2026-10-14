# Preguntas — Infraestructura de U5 `provider-platform`

Esta unidad no despliega nada nuevo: corre embebida en el proceso único y el
backend de trazas ya está en `docker-compose.yml` con su perfil y su imagen
anclada. Lo que sí toca son **archivos compartidos** —los contratos de
importación, la plantilla de variables, el manifiesto— y eso es lo que estas
cuatro preguntas deciden.

Miguel delegó las respuestas en la recomendación, igual que las de las tres
etapas anteriores.

---

## Q1 — El contrato del SDK del proveedor está más suelto de lo que pide ADR-018

El contrato que ya existe, `sdk-solo-en-su-adaptador`, prohíbe importar `google`
desde quince módulos. Pero `untangle.providers` **no está en esa lista**, así que
hoy el SDK se puede importar desde cualquier sitio de ese paquete: también desde
`ports.py` y desde `factory.py`.

ADR-018 dice otra cosa: "el SDK de un proveedor solo se importa **dentro de su
adaptador**". La diferencia importa porque `ports.py` es lo que ven las seis
unidades que consumen este contrato: un tipo del proveedor filtrándose ahí lo
heredarían todas.

- A. **(Recomendada)** Se aprieta. Un contrato nuevo prohíbe los SDK de
  proveedor en `untangle.providers.ports` y `untangle.providers.factory`,
  dejándolos solo en `untangle.providers.adapters`. El contrato viejo no se
  toca: los dos se complementan, uno vigila fuera del paquete y el otro dentro.
- B. Se deja como está. Nadie va a importar el SDK en los puertos a propósito, y
  el día que pase se verá en la revisión.
- X. Other (please specify)

**Por qué la A.** Es la misma forma que U2 y U3 usaron para sus propios módulos:
un contrato general para las fronteras **entre** paquetes y uno acotado para las
que hay **dentro**. Y la razón de fondo es la del proyecto entero: una convención
que solo vive en la memoria del autor no está a la semana seis.

[Answer]: A

---

## Q2 — El chequeo de "nadie emite un tramo por su cuenta": ¿contrato o análisis propio?

El diseño exige que la única forma de emitir un tramo sea el ayudante de esta
unidad. U3 y U4 resolvieron un problema parecido con un análisis estático propio
—`redaction:constructor` y `case:constructor`—, así que la pregunta es si este
es un tercer hermano o algo más barato.

- A. **(Recomendada)** Un **contrato de importación**: `opentelemetry` prohibido
  en todo salvo `untangle.telemetry.traces`. Es exactamente lo que
  `import-linter` hace, ya corre en el paso 3 del guion, y no añade ni una tarea
  ni un paso.
- B. Un análisis estático propio, hermano de los otros dos.
- X. Other (please specify)

**Por qué la A, y por qué los otros dos sí hicieron falta.** Los análisis de U3 y
U4 existen porque su tipo **se borra en tiempo de ejecución**: `NewType`
desaparece, así que fabricarlo con un `cast` o con una anotación más un
`type: ignore` no deja rastro que un contrato de importación pueda ver. Aquí no
hay tipo que se borre: hay un import, y los imports son justo lo que
`import-linter` mira. Un tercer hermano sería un mecanismo nuevo para un problema
que el mecanismo viejo ya resuelve.

**Dos contratos más, de la misma familia.** Con el mismo cambio entran el que
prohíbe que la contabilidad importe las trazas —que es lo que hace verdadera la
frase "el corte funciona aunque la observación falle"— y el de capas internas del
módulo, igual que `tenancy` y `redaction` tienen el suyo.

[Answer]: A

---

## Q3 — Las tres claves nuevas de proveedor, ¿entran al entorno de la tubería?

U5 añade tres variables: la clave del chat, la de la voz y la de operación. La
pregunta es si la compuerta las necesita.

- A. **(Recomendada)** **No.** La compuerta no llama a ningún proveedor: las
  pruebas de contrato de los adaptadores corren contra respuestas grabadas, y el
  subconjunto `smoke` de evaluaciones no necesita clave —es lo que sostiene la
  cifra publicada de "del clon al reporte sin cuenta en ningún proveedor"—. En la
  plantilla va el **nombre**, nunca el valor; `mise run env:check` comprueba las
  dos direcciones.
- B. Sí, para poder correr las pruebas de contrato contra el proveedor real en
  cada corrida. Gasta cuota en cada empujón, contradice el presupuesto, y pone
  tres claves más donde pueden filtrarse.
- X. Other (please specify)

**Por qué la A.** Mismo precedente que U4 con la clave de cifrado, y la misma
razón: una clave en el entorno de la tubería es una clave más donde puede
filtrarse y no compra nada. La prueba contra el proveedor real corre **por
hito**, a mano, con la clave de quien la corre.

[Answer]: A

---

## Q4 — El archivo de trazas que sube la tubería, ¿va redactado?

En la tubería no hay backend de trazas —no cabe en su máquina—, así que las
trazas de cada corrida se exportan a un archivo que se sube como artefacto de la
corrida. El repositorio es candidato a publicarse en la semana doce.

- A. **(Recomendada)** **Sí, por el mismo punto único que todo lo demás.** No hay
  una vía "interna" de exportación: el archivo sale por la misma función que el
  envío al backend, y esa función pasa por la redacción. Además el artefacto
  lleva retención corta, porque un artefacto de corrida no es un archivo
  histórico.
- B. Sin redactar, porque es un artefacto interno de la tubería. Un artefacto de
  una corrida de un repositorio que puede volverse público no es interno, y
  "interno" es exactamente la palabra que precede a las fugas de este tipo.
- X. Other (please specify)

**Por qué la A.** La regla del proyecto dice que un punto de salida nuevo sin
redacción tiene que ser **imposible por construcción**, no detectable por
disciplina. Una segunda vía de exportación sin redacción sería justo ese punto de
salida nuevo, con la agravante de que nadie lo llamaría así.

[Answer]: A
