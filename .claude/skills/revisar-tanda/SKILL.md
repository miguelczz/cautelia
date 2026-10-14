---
name: revisar-tanda
description: >
  Revisar una tanda de código de Untangle antes de commitearla: romper cada regla
  nueva para comprobar que alguna prueba se cae, contrastar el cambio contra el
  catálogo de formas de prueba que no prueban, y declarar el resultado. Se usa al
  terminar de escribir código del aplicativo (app/), al cerrar una tanda o un paso
  del plan de generación de código, y antes de cualquier commit que toque pruebas,
  umbrales, compuertas duras o configuración de calidad.
argument-hint: "[tanda o rutas a revisar]"
user-invocable: true
---

# Revisar una tanda

Las compuertas automáticas en verde **no son evidencia de nada**. En las siete tandas
de U12 había un defecto real en cada una con las nueve compuertas pasando, y cinco de
los ocho estaban en la prueba. Este procedimiento es lo que los encontró.

El catálogo de formas —catorce de prueba que no prueba, catorce de hallazgo que no está en
ninguna prueba, cinco reglas sobre quien revisa, y las cuatro respuestas a una rotura
que no tumba nada— está en `docs/reference/como-se-revisa-el-codigo.md`. **Léelo en el
paso 4**, no antes: cada forma lleva el defecto real que la enseñó, y es lo que hace que
se reconozca.

## El procedimiento

1. **Correr las pruebas de lo que se tocó, y nada más.** El archivo de prueba del
   archivo que se cambió: segundos. Si se tocó el catálogo de textos o un esquema,
   `mise run contracts:gen`, que genera archivos y no verifica nada.

   **En la máquina de Miguel no se corre la verificación en ninguna de sus formas**: ni
   `scripts/verify.sh`, ni `mise run verify:rapido`, ni la suite completa, ni el arnés de
   navegadores. Decisión suya, repetida varias veces y escrita el 2026-10-13: la
   verificación es GitHub Actions sobre `main`. No se anota como paso pendiente ni se le
   pide tiempo de máquina para ella. Si GitHub sale en rojo, es un incidente y se arregla
   hacia adelante.

2. **Leer el diff entero.** No el informe de entrega, no el resumen: el diff. Incluidos
   los archivos de prueba, de configuración y de datos.

3. **Romper y correr, regla por regla.** Por cada regla de negocio, criterio de
   aceptación o compuerta dura que la tanda dice cumplir: cambiar el valor, invertir la
   comparación o saltarse el paso, correr, y anotar **qué se rompió y qué prueba se
   cayó**. Dos condiciones para que cuente:
   - Si no se cae ninguna, la prueba está escrita a la medida del código: se corrige la
     prueba, no se justifica.
   - El rojo tiene que ser **conducta rota**. Un `ImportError` o un símbolo que todavía
     no existe no prueba nada.

4. **Pasar el cambio por el catálogo.** Leer `docs/reference/como-se-revisa-el-codigo.md`
   y recorrer sus formas contra este diff. **Empezar por los dobles**: la forma 12 --un
   doble más permisivo que la pieza real-- es la que dejó el chat sin atender a nadie con
   2.363 pruebas en verde, y se reconoce con un grep (`del ` o `_` en la firma de un
   doble). Después, las que más veces han acertado aquí: la
   aserción que no puede distinguir, la que comprueba ausencia en vez de identidad, la
   que se escribió desde la lectura equivocada del criterio, y el módulo que miente
   sobre sí mismo.

5. **Si se regeneró algo, correr las compuertas otra vez.** `contracts:gen`,
   `synthetic:generate` y `copy` reescriben archivos versionados, y lo que reescriben
   entra en lo que las compuertas miran: un cliente generado con un modelo nuevo puede
   romper el comprobador de tipos que pasó cinco minutos antes. El 2026-10-02 eso puso
   `main` en rojo: `types` pasó, `contracts:check` regeneró el cliente del chat con una
   respuesta nueva, y nadie volvió a correr `types`. **La regeneración va antes de las
   compuertas, nunca después.**

6. **Comprobar que nada se debilitó para pasar.** En el diff: ninguna prueba existente
   relajada o borrada, ningún umbral ni piso de cobertura bajado, ninguna compuerta dura
   saltada, ninguna supresión del linter sin su razón escrita al lado. Esto no se negocia
   y ninguna explicación lo levanta.

7. **Declarar el resultado, explícitamente.** Qué se rompió, qué se cayó, qué no se
   cayó y qué se corrigió. "Se ve bien" no es un resultado; el resultado es la lista de
   roturas con su efecto.

8. **Escribir lo aprendido en el mismo commit.** Si la revisión encontró una forma nueva
   —de defecto o de buena práctica—, se escribe cuando aparece y no al final, porque lo
   que se pierde esperando es siempre el caso concreto. Dónde va lo decide una sola
   pregunta, *¿qué pasa si me la salto?*:
   - pasa algo que no debía pasar nunca → un hook
   - se saltan pasos de un procedimiento que se repite → esta skill
   - queda una regla que aplica siempre → `project.md`, por el ritual de aprendizajes
   - hace falta el caso y el razonamiento → el documento de referencia

## Para artefactos del flujo, no para código

`scripts/check-artifacts.py <dir de la unidad>` (o `--todas`) comprueba lo que se puede
comprobar de un artefacto de AI-DLC: que cada `mise run X` citado exista o esté
declarado como creado por esa unidad, que cada ruta citada exista, que cada
identificador `BR`/`FD`/`NFRD`/`INF` esté definido, y que las cifras escritas en prosa
coincidan con el recuento real. Se corre antes de cerrar una etapa. No forma parte de
`scripts/verify.sh`, que es la compuerta del aplicativo.
