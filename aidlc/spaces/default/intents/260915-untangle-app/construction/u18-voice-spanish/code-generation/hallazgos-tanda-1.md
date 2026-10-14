# Revisión de la tanda 1 — U18 `voice-spanish`

"El detector sube a módulo hoja". Un movimiento y ninguna conducta nueva: 2.082
pruebas en verde sin tocar una sola aserción de U13, que es exactamente lo que se
quería demostrar.

## 1. Lo que se rompió, y qué se cayó

Una rotura, y tumbó una prueba de conducta. Deshecha.

| Regla | Qué se rompió | Qué se cayó |
| --- | --- | --- |
| BR3.4 | El detector importa un canal | `test_el_detector_no_puede_mirar_hacia_arriba` |

Las demás reglas de la unidad no tienen código todavía: son de la tanda 2.

## 2. Los 36 contratos pasaban y el módulo nuevo no estaba en ninguno

Al mover `language.py` a la raíz, `lint-imports` siguió en verde. **Y eso no
significaba que estuviera bien**: un módulo que no aparece en ninguna regla no
está limpio, está **sin mirar**. Nada le habría impedido importar la raíz de
composición al día siguiente, que es justo el estado del que se le sacó.

Es una forma de la aserción que no puede distinguir, aplicada a una herramienta:
"pasa" y "no se comprueba" salen iguales por la salida, y el número de contratos
subiendo de 35 a 36 es lo único que lo delata.

Ahora hay un contrato propio —lo único que el detector puede ver del aplicativo es
`untangle.base`— y tres pruebas: la línea base, la violación plantada, y la que
comprueba que el contrato **sigue nombrando los dos canales**. La tercera es la
que se pierde en silencio: quitar uno de los dos de la lista no rompe nada
visible, y desde ese día el detector podría volver a colgarse de un canal.

## 3. Una cuarta prueba que mira el repositorio de verdad

Las tres de arriba corren sobre un árbol de mentira, que es lo que permite plantar
una violación sin romper el proyecto. Pero un árbol de mentira no puede decir si
**aquí** hay un segundo detector.

La cuarta busca `LanguageDetectorBuilder` en todo el código fuente y exige que
aparezca en un solo archivo. Es lo que no se puede escribir sin crear un detector,
y es la diferencia entre comprobar la regla y comprobar la configuración.

## 4. Decisiones tomadas al mover

1. **No queda reexportador.** `chat/language.py` desaparece y los dos
   consumidores de U13 apuntan al nuevo. Dos caminos al mismo sitio es como uno de
   los dos se queda atrás.
2. **No se tocó un número.** Los dos umbrales --0,75 y 0,5-- y el piso de cuatro
   palabras son medidas de U13, no elecciones, y la tanda es un movimiento. Si
   alguna prueba de U13 hubiera habido que tocarla, sería señal de que el
   movimiento cambió algo; no hubo ninguna.
3. **La prueba se mudó con el módulo**, de `tests/unit/chat/` a `tests/unit/`.
   Una prueba que se queda en la carpeta del canal del que la pieza salió es la
   siguiente en quedarse atrás.
4. **`lingua` no entra en la lista de SDK de proveedor.** Es una biblioteca local
   que no habla con la red, y el contrato que prohíbe los SDK existe contra
   llamadas a terceros, no contra dependencias.

## 5. Mover un archivo deja ocho registros apuntando al aire

El chequeo de artefactos lo dijo en el acto: la trazabilidad de U13 citaba
`chat/language.py` en cuatro criterios --AC1.2.1 a AC1.2.4-- y dos documentos de
diseño de esta misma unidad citaban la ruta vieja. Ocho citas a un archivo que ya
no estaba.

Ninguna rompe nada al correr. Es exactamente por eso que hace falta una
herramienta que las mire: un registro que apunta al aire se lee igual de bien que
uno correcto, y solo se nota cuando alguien va a buscar el archivo y no está.

Las ocho repuntadas en el mismo cambio que el movimiento, que es donde tenían que
ir.

## 6. Lo que no se debilitó

Ninguna prueba existente relajada ni borrada --ninguna se tocó siquiera--. Ningún
umbral ni piso de cobertura bajado. Ninguna compuerta saltada. **Un contrato de
importación más**, no uno menos.

## Sources

- `code-generation-plan.md` — tanda 1
- `../functional-design/rules.md` — BR3.4
- `../functional-design/functional-design-questions.md` — D1

## Assumptions & Open Questions

None.
