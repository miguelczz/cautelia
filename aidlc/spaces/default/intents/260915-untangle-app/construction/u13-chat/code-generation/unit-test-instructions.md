# Instrucciones de prueba — U13 `chat`

U13 es de la **rama evaluada**: realiza M6 y la adherencia de idioma de PRD 11.2, y su
caso previo son las conversaciones de DS-2 **por el canal chat** más el escenario RT-10
de DS-6.

La diferencia con las unidades anteriores es que aquí las pruebas tienen que cubrir dos
lados que hasta ahora estaban separados: la conducta del servidor y lo que de verdad
llega a una pantalla. Las dos compuertas duras de aislamiento se comprueban **por el
punto de entrada del canal**, no por la función interna: lo que hay que demostrar es que
una persona con un navegador no obtiene el caso de otra.

## El caso previo, antes del código

Los ejes de DS-2 por el canal chat, en los dos idiomas, y el escenario **RT-10**
(cambio de idioma para esquivar los controles) de DS-6. RT-10 se escribe primero, se
corre y se comprueba que falla nombrando su razón: es el que ata BR2.1 y BR2.3 a una
compuerta de seguridad y no solo a una preferencia de idioma.

## Lo que cada tanda deja probado

| Tanda | Pruebas | Dónde corren |
| --- | --- | --- |
| 1. La conversación y sus límites | Aserción de esquema; una conversación de otra aseguradora no se encuentra; el purgador se la lleva; los cinco controles rechazan antes del proveedor; la divulgación va primero y sin su registro el caso no cierra | Integración con base, y unitarias cronometradas |
| 2. El turno por el canal | Los tres casos de idioma; ninguna ruta termina sin uno de los tres eventos finales; el texto parcial no esquiva la guardia; la conexión huérfana se cierra | Unitarias e integración |
| 3. La retoma | **Las dos compuertas duras**, comparando contra la respuesta ante lo inexistente con su control positivo; un caso con los dos canales en orden | Integración con base |
| 4. Pantallas y cierre | La cita expandible y la cláusula en otro idioma; el resumen de traza redactado y ajeno; "se está registrando"; el aviso por la guardia y bloqueado sin decisión; los dos casos de DS-2 | Integración y pruebas de pantalla |

## Las pruebas que aíslan una regla, escritas antes del código

Cada una rompe **una** regla y nada más, y se comprueba en rojo antes de escribir lo
que la satisface:

- **BR1.1** [bloquea] — un turno procesado antes de que la divulgación se haya emitido.
- **BR1.2** — un caso sin el registro de la divulgación no se cierra.
- **BR2.1** — un primer mensaje en español sobre una página que abrió en inglés.
- **BR2.2** — un "ok", una placa y un nombre propio no cambian el idioma.
- **BR3.1** — el mensaje que supera el límite recibe la frase del catálogo y el caso
  queda guardado.
- **BR3.2** — la ráfaga se rechaza **sin llamar al proveedor**.
- **BR4.2** — la cláusula en otro idioma nunca se muestra traducida como si fuera
  literal.
- **BR4.3** — el resumen de traza de otra conversación responde como uno inexistente.
- **BR4.4** — una traza en curso dice que se está registrando.
- **BR5.2** — el mismo texto sin una decisión registrada se bloquea.
- **BR6.2** [bloquea] — caso de otro navegador, idéntico a inexistente.
- **BR6.3** [bloquea] — caso de otra aseguradora, idéntico a inexistente.

## Cómo se comprueba una compuerta de aislamiento

No comprobando que el dato ajeno no aparezca. **Comparando**, campo por campo y
carácter por carácter, contra la respuesta a un caso que no existe. La razón la dejó
escrita U12 y esta unidad la hereda: la filtración no es el dato, es la distinción.

Y el **control positivo va delante**: la sesión legítima tiene que recibir una respuesta
real con la que comparar. Sin él, las dos aserciones pasan igual con una implementación
que no entregue nunca nada — que es la forma exacta en que una prueba de aislamiento
puede estar verde y no proteger nada.

## Las cinco formas de prueba floja que este proyecto ya encontró

Ninguna se repite. Las cinco salieron de las revisiones de U12 y están en su resumen de
código:

1. **Una prueba que no pasa por la pieza.** Comprobar aislamiento con una consulta SQL
   directa prueba la política de fila, que ya está probada, no el código nuevo.
2. **Una aserción que no puede distinguir.** Si se afirma que un valor sale de la
   configuración, se usa un valor **distinto** del que la fábrica de pruebas pone por
   omisión.
3. **Una decisión tomada sobre el conjunto entero** en vez de sobre cada elemento, en
   una rama que ningún caso recorre.
4. **Una defensa que solo mira el salto directo.** Un contrato de importación que
   permitía los saltos se burlaba con un módulo puente de una línea.
5. **Una prueba que afirma más de lo que comprueba.** Si cubre una parte de un
   criterio, lo dice en su docstring.

## Lo que corre en cada tanda y lo que corre una vez

Mientras se trabaja: las pruebas de la unidad (`mise run test:u13`, que **esta unidad
crea**). Al cerrar cada tanda: sus compuertas. Al cerrar la unidad: la suite completa,
`scripts/verify.sh` entero y la corrida completa del corredor de evaluaciones.
