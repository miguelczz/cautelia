# Reglas de negocio — U21 `eval-gates`

Son 14 reglas en cinco familias: el reporte, la regresión, el juez, el segundo
detector y la compuerta.

## Reglas

El bloque siguiente es la fuente de verdad; la tabla resumen se deriva de él.

```yaml
rules:

  - id: BR1.1
    statement: Cada caso del reporte trae su identificador, su veredicto por criterio con el tipo de juicio, su causa raíz y el enlace a su traza.
    category: validation
    applies_to: "CaseRow del reporte"
    trigger: "Al generar el reporte."
    logic: "Cada criterio de cada caso declara si lo juzgó código, el juez o una persona; un caso fallido trae su causa raíz de la taxonomía del PRD 11.3; la traza va con su estado cuando no está disponible, nunca vacía ni inventada."
    violation: "La prueba del reporte falla."
    source: AC4.5.1, FR11.3

  - id: BR1.2
    statement: Ninguna cifra mezcla idiomas.
    category: constraint
    applies_to: "Todo el reporte y la línea base"
    trigger: "Siempre."
    logic: "Las métricas se guardan y se publican por idioma. No existe campo donde escribir un promedio combinado, ni en el reporte (U1) ni en la línea base."
    violation: "La prueba de paridad falla."
    source: AC4.5.2, P12

  - id: BR1.3
    statement: Lo que no se pudo medir se declara, nunca se omite.
    category: policy
    applies_to: "EvalReport"
    trigger: "Cuota agotada, proveedor caído, juez fuera de calibración."
    logic: "La métrica afectada sale como 'no medida' con su causa; la corrida se marca 'no comparable' con su identificador; ninguna métrica desaparece del reporte."
    violation: "La prueba de causas falla."
    source: AC4.5.5, AC5.9.5

  - id: BR2.1
    statement: La línea base se publica solo con las compuertas duras en verde, y se versiona con su commit.
    category: validation
    applies_to: "Baseline"
    trigger: "Al publicar una línea base por hito."
    logic: "SI la corrida tiene un fallo de compuerta dura, o no es comparable, ENTONCES no se puede publicar como línea base."
    violation: "El comando de publicación falla nombrando el caso."
    source: AC4.5.4, P5

  - id: BR2.2
    statement: En los conjuntos pequeños, cualquier caso que pase a fallar detiene la entrega hasta que una explicación lo nombre.
    category: policy
    applies_to: "DS-2, DS-3 y DS-6"
    trigger: "En cada corrida con línea base vigente."
    logic: "SI un caso que pasaba en la línea base falla ENTONCES la compuerta queda en rojo, salvo que `regressions.yaml` nombre ese identificador con su causa raíz y un commit desde el que vale. Una explicación sin identificadores no cuenta."
    violation: "Compuerta dura: la entrega se detiene."
    source: AC5.9.2, FR11.4

  - id: BR2.3
    statement: En las métricas de denominador grande, una caída de más de 2 puntos porcentuales detiene la entrega.
    category: calculation
    applies_to: "Extracción por campo, fidelidad de la lectura, latencias"
    trigger: "En cada corrida con línea base vigente."
    logic: "SI la métrica cae más de 2 pp frente a la línea base y no hay explicación que nombre los casos afectados ENTONCES la compuerta queda en rojo. El umbral porcentual no se aplica a los conjuntos pequeños, donde manda BR2.2."
    violation: "Compuerta dura."
    source: AC5.9.3, FR11.4

  - id: BR2.4
    statement: Un caso inestable se reporta aparte, no cuenta para la compuerta y sigue en el set.
    category: policy
    applies_to: "UnstableCase"
    trigger: "En cada corrida."
    logic: "Los casos de `unstable-cases.yaml` salen en su propia sección, con su etiqueta, y no suman ni restan a los recuentos de la compuerta. Marcar uno exige dos corridas del mismo commit con veredictos distintos y un trabajo abierto. Nunca se borra del set."
    violation: "La prueba de inestables falla; retirarlo del set es P5."
    source: AC4.5.4, P5

  - id: BR3.1
    statement: Los veredictos del juez cuentan solo donde su calibración alcanza el umbral, por criterio y por idioma.
    category: policy
    applies_to: "JudgeCalibration"
    trigger: "En cada corrida que usa el juez."
    logic: "Para cada criterio e idioma, cuentan solo si el límite inferior del intervalo de TPR y el de TNR alcanzan el umbral de nfr-requirements, medidos sobre la partición de prueba. Donde no, el criterio se publica como 'no medida' con esa causa y no bloquea."
    violation: "La prueba de calibración falla."
    source: AC4.6.1, AC4.6.2, ADR-014

  - id: BR3.2
    statement: Cambiar el modelo del juez o la rúbrica obliga a recalibrar.
    category: validation
    applies_to: "JudgeCalibration"
    trigger: "Al arrancar la corrida."
    logic: "SI no existe una calibración registrada para la combinación exacta de modelo y versión de rúbrica ENTONCES los criterios del juez se publican como 'no medida' con la causa 'juez sin calibrar', y la recalibración queda como trabajo abierto con fecha."
    violation: "La prueba de recalibración falla."
    source: AC4.6.3

  - id: BR3.3
    statement: Las compuertas juzgadas por código siguen bloqueando aunque el juez esté descalibrado.
    category: constraint
    applies_to: "Citas inexistentes, aislamiento, datos personales en trazas, esquema"
    trigger: "Siempre."
    logic: "La descalibración del juez apaga solo los criterios que él juzga. Ninguna compuerta dura de código depende de él."
    violation: "Compuerta dura."
    source: AC4.6.2, PRD 11.2

  - id: BR3.4
    statement: La muestra para revisión humana es reproducible y siempre incluye todos los fallos del juez.
    category: calculation
    applies_to: "Cola de anotación"
    trigger: "Al preparar la revisión humana."
    logic: "El 20 % de los casos, elegidos con una semilla registrada, más todos los que el juez marcó como fallo. Los desacuerdos se registran junto a la versión de la rúbrica."
    violation: "La prueba de muestreo falla."
    source: AC4.6.4, PRD 11.3

  - id: BR4.1
    statement: El segundo detector no comparte mecanismo, reconocedores ni biblioteca con el primero.
    category: constraint
    applies_to: "Segundo detector"
    trigger: "Siempre."
    logic: "Cada detector declara su mecanismo. El segundo no importa el módulo de redacción de U3: lee su configuración de reconocedores como archivo, solo para comprobar que no coinciden. Un contrato de importación lo verifica."
    violation: "El contrato de importación falla; la prueba de mecanismos falla."
    source: AC4.14.1, ADR-013

  - id: BR4.2
    statement: Un solo dato personal en trazas, logs, exportaciones o en el propio reporte detiene la entrega.
    category: policy
    applies_to: "Salidas de la corrida de DS-2 y DS-6"
    trigger: "Al cerrar la corrida."
    logic: "El segundo detector revisa lo ya redactado. Un hallazgo, en cualquiera de los dos idiomas, deja la compuerta en rojo. Se mide por idioma y por tipo de entidad, nunca como promedio."
    violation: "Compuerta dura (NFR11)."
    source: AC4.14.2, AC4.14.3

  - id: BR5.1
    statement: Un cambio en los archivos de reglas corre las evaluaciones, y el audio no corre en cada entrega.
    category: policy
    applies_to: "Guion de verificación y flujo de GitHub Actions"
    trigger: "En cada entrega a main."
    logic: "El guion único corre DS-2, DS-3 y DS-6 —el subconjunto declarado si la corrida completa no cabe en el presupuesto—. DS-5 solo se invoca en el comando por hito. Un commit con la compuerta en rojo no se despliega."
    violation: "La prueba del flujo falla."
    source: AC5.9.1, AC5.9.4, FR6.5, FR11.7
```

## Resumen

| ID | Regla |
| --- | --- |
| BR1.1 | Cada caso con su veredicto, su tipo de juicio, su causa y su traza |
| BR1.2 | Ninguna cifra mezcla idiomas |
| BR1.3 | Lo que no se pudo medir se declara |
| BR2.1 | La línea base se publica solo en verde y con su commit |
| BR2.2 | Un caso que pasa a fallar detiene la entrega |
| BR2.3 | Una caída de más de 2 pp detiene la entrega |
| BR2.4 | Los inestables se reportan aparte y siguen en el set |
| BR3.1 | El juez cuenta solo donde está calibrado |
| BR3.2 | Cambiar juez o rúbrica obliga a recalibrar |
| BR3.3 | Las compuertas de código no dependen del juez |
| BR3.4 | Muestra humana reproducible, con todos los fallos del juez |
| BR4.1 | Segundo detector de mecanismo distinto |
| BR4.2 | Un solo dato personal detiene la entrega |
| BR5.1 | Cambiar reglas corre las evaluaciones; el audio va por hito |
