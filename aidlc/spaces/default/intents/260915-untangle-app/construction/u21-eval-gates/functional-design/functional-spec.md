# Especificación funcional — U21 `eval-gates`

Fuente de verdad de los flujos de U21. Los datos están en `entities.md` y las
decisiones en `rules.md`. Respuestas aplicadas:
- **Q1:** las etiquetas de DS-7 se ponen con un comando local, en tandas.
- **Q2:** el juez cuenta cuando el límite inferior del intervalo llega a 0,80.
- **Q3:** sin línea base, la compuerta corre y no compara.

## 1. Qué hace esta unidad

U1 dejó el corredor y el reporte de una corrida. U21 agrega **la memoria entre
corridas**, que es lo que convierte ese reporte en una compuerta:

- **Compara** la corrida contra la línea base versionada y decide si hay
  regresión, con la regla que corresponde al tamaño del conjunto.
- **Calibra al juez** contra las etiquetas humanas de DS-7 y apaga sus veredictos
  donde no alcanza el umbral, sin tocar las compuertas de código.
- **Revisa con un segundo detector** de mecanismo distinto lo que ya se redactó.
- **Cierra la compuerta** en el guion de verificación: un cambio de reglas corre
  las evaluaciones, y el audio se queda para el comando por hito.

**Lo que U21 no hace, y quién lo hace:**
- El corredor, el formato de los casos y el veredicto por caso: **U1**.
- El panel de cifras y las secciones del README: **U22**.
- La redacción de datos personales en sí: **U3**. U21 solo la audita.
- Las etiquetas humanas de DS-7: las pone **Miguel**.

## 2. Flujos

### F1 — Cerrar una corrida contra la línea base

1. Termina la corrida y U1 entrega su reporte.
2. Se lee la línea base vigente (`current.json`) y el archivo de inestables.
3. Por cada caso: si pasaba y ahora falla, es regresión, salvo que sea inestable
   o que `regressions.yaml` lo nombre con su causa y su commit (BR2.2, BR2.4).
4. Por cada métrica de denominador grande: si cae más de 2 pp sin explicación, es
   regresión (BR2.3).
5. El reporte gana su sección de diferencia: qué pasó a fallar, qué pasó a pasar,
   qué cambió cada métrica, y los inestables aparte.
6. Si hay regresión o fallo de compuerta dura, el comando termina con código
   distinto de cero (AC4.5.3).

### F2 — Calibrar al juez

1. Se leen las etiquetas humanas de DS-7 con sus tres particiones fijas.
2. El juez juzga la partición de prueba con su rúbrica versionada.
3. Se calculan TPR y TNR **por criterio y por idioma**, con su n y su intervalo,
   y se guardan con el identificador exacto del modelo y la versión de la
   rúbrica.
4. En cada corrida posterior: donde el límite inferior de los dos intervalos
   llega al umbral, los veredictos del juez cuentan; donde no, ese criterio y
   ese idioma salen como "no medida" y no bloquean (BR3.1).
5. Sin calibración para esa combinación de modelo y rúbrica, todos sus criterios
   salen como "no medida" y la recalibración queda abierta con fecha (BR3.2).

### F3 — El segundo detector

1. Al cerrar la corrida, se recogen las salidas ya redactadas: trazas
   exportadas, logs, exportaciones y el propio reporte.
2. El segundo detector las revisa con su mecanismo propio, declarado y distinto
   del de U3 (BR4.1).
3. Un solo hallazgo, en cualquier idioma, deja la compuerta en rojo, con el
   archivo, el idioma y el tipo de entidad (BR4.2).
4. Una prueba siembra un teléfono sin redactar y comprueba que el detector lo
   encuentra: un detector que nunca encuentra nada no prueba nada (AC4.14.4).

### F4 — La compuerta en la entrega

1. El guion único de verificación corre el subconjunto declarado de DS-2, DS-3 y
   DS-6, incluido cuando el cambio toca un archivo de reglas (BR5.1).
2. DS-5 no se invoca ahí: va en el comando por hito.
3. Una corrida roja por causa externa se marca "no comparable" con su causa y su
   identificador, y se repite; si sigue roja, bloquea, y el umbral no se toca
   (BR1.3, AC5.9.5).

### F5 — Publicar una línea base

1. Solo por hito y solo con las compuertas duras en verde y la corrida completa,
   no un subconjunto (BR2.1).
2. Se escribe el archivo con su fecha y su commit, y `current.json` pasa a
   apuntarlo. Queda en el repositorio: la línea base se lee en un diff.

## 3. Reglas (resumen derivado de `rules.md`)

| Familia | Reglas |
| --- | --- |
| Reporte | BR1.1 a BR1.3 |
| Regresión y línea base | BR2.1 a BR2.4 |
| Juez | BR3.1 a BR3.4 |
| Segundo detector | BR4.1 y BR4.2 |
| Compuerta | BR5.1 |

## 4. Decisiones de esta etapa

| # | Decisión | Por qué |
| --- | --- | --- |
| FD-U21-1 | Línea base, calibraciones e inestables viven como archivos versionados en `app/evals/`, no en tablas (Q3) | La compuerta corre en GitHub Actions, sin base de datos, y lo que decide una entrega tiene que leerse en un diff |
| FD-U21-2 | El segundo detector es determinista: patrones propios y validadores de formato, sin modelo de lenguaje | Mecanismo distinto del reconocimiento estadístico de U3 (ADR-013), corre sin clave de proveedor y no puede fallar por cuota |
| FD-U21-3 | Las etiquetas de DS-7 se ponen con un comando local que muestra turno y criterio, y guarda un archivo versionado por idioma (Q1) | Langfuse es para la anotación de la demo en vivo; para 40 transcripciones propias, un comando sin servicio es menos que montar y mantener uno |
| FD-U21-4 | El juez cuenta cuando el **límite inferior** del intervalo de TPR y el de TNR llegan a 0,80 (Q2) | Exigir el límite inferior y no la media impide que una muestra pequeña y afortunada habilite al juez; el valor se registra en `nfr-requirements` |
| FD-U21-5 | Sin línea base vigente, la compuerta corre, publica y no compara, diciéndolo en la cabecera (Q3) | La primera corrida de un hito no puede bloquearse por falta de pasado, y callarlo haría leer "sin regresiones" donde no hubo comparación |

## Sources

- `../../../inception/units-generation/unit-of-work.md` — sección U21.
- `../../../inception/user-stories/stories.md` — US4.5, US4.6, US4.14 y US5.9.
- `../../../inception/requirements-analysis/requirements.md` — FR11.3 a FR11.7 y
  FR6.5.
- `../../../inception/domain-design/components.md` — Evaluation.
- `../../../inception/contract-design/contract-summary.md` — C-27.
- `app/backend/src/untangle/evals/report.py` — el reporte que dejó U1.

## Assumptions & Open Questions

- **La taxonomía de causa raíz** es la del PRD 11.3; U21 la fija como enum en el
  código y no inventa categorías nuevas.
- **Cuántos casos entran al 20 % de la muestra humana** sale del tamaño de la
  corrida; no hay mínimo declarado más allá de incluir todos los fallos del juez.
