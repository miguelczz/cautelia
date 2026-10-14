# Reglas — U22 `public-evidence`

Trece reglas en cuatro familias: de dónde salen las cifras, qué no puede decir una
superficie pública, el gasto, y las dos secciones generadas del README.

Dos llevan `[bloquea]`, y las dos protegen principios y no conducta: que el panel
público nunca muestre un identificador de caso de un visitante, y que una cifra
sin medir nunca aparezca como cero. La segunda parece menor y no lo es: un cero
es una afirmación —"se midió y dio cero"— y esa afirmación sería falsa.

```yaml
rules:
  # --- De dónde salen las cifras (US4.16) -------------------------------------
  - id: BR1.1
    statement: Las cifras salen de la línea base vigente versionada, nunca de un reporte suelto.
    category: policy
    applies_to: "El panel de cifras y las secciones generadas del README"
    trigger: "Al abrir el panel y al regenerar el README."
    logic: >
      El reporte de una corrida vive en `tmp/` y no se versiona: una cifra sacada
      de ahí no tiene commit que citar y cambia sin que nadie lo decida. La línea
      base sí es un archivo del repositorio, y por eso es la única que puede
      llevar fecha, commit y enlace a su corrida.
    violation: "Una cifra del panel no coincide con la línea base vigente."
    source: AC4.16.2, FD-U22-1

  - id: BR1.2
    statement: "[bloquea] Una cifra sin medir se muestra como «no medida» con su causa, nunca vacía ni en cero."
    category: constraint
    applies_to: "Cada una de las cinco cifras y cada sección generada"
    trigger: "Siempre que falte el dato que la produce."
    logic: >
      Un cero afirma que se midió y dio cero. Tres de las cinco cifras nacen sin
      medir --las dos de la línea base porque todavía no hay ninguna, y las
      latencias porque se miden por hito contra proveedores de verdad--, así que
      este es el estado normal del panel el día que nace y no una excepción.
    violation: "El panel muestra 0 % donde no hay medición, o una celda vacía."
    source: AC4.16.4, P5, P7

  - id: BR1.3
    statement: Cada cifra lleva su fecha, su commit y el enlace a la corrida que la produjo.
    category: policy
    applies_to: "Cada cifra del panel"
    trigger: "Al dibujar el panel."
    logic: >
      Es lo que separa el panel de una diapositiva: sin los tres, la cifra es una
      afirmación de alguien, y con los tres es una que se puede ir a comprobar.
    violation: "Una cifra sin commit o sin enlace a su corrida."
    source: AC4.16.2

  - id: BR1.4
    statement: Las cifras por idioma se muestran lado a lado y nunca como promedio combinado.
    category: constraint
    applies_to: "Completitud, precisión de citación y latencias"
    trigger: "Al dibujar el panel y al generar el README."
    logic: >
      Un promedio de los dos idiomas esconde exactamente lo que la paridad existe
      para vigilar: que el español no sea un servicio de segunda. Un idioma bueno
      tapa a uno malo y el número sale presentable.
    violation: "Aparece una sola cifra donde hay dos idiomas."
    source: P12, AC4.16.1

  - id: BR1.5
    statement: Las latencias dicen entre qué eventos se miden, sobre qué conjunto, y con p50 y p95.
    category: policy
    applies_to: "Las latencias del panel"
    trigger: "Al dibujar el panel."
    logic: >
      Una latencia sin sus extremos no se puede reproducir ni discutir. Los
      extremos son los eventos de traza que ya emiten la voz y el chat: fin del
      habla a primer audio, y envío a primera palabra.
    violation: "Una latencia sin sus dos extremos, sin conjunto o con un solo percentil."
    source: AC4.16.3

  # --- Lo que una superficie pública no puede decir ---------------------------
  - id: BR2.1
    statement: "[bloquea] El panel público muestra recuentos y distribuciones, nunca identificadores ni datos de casos de visitantes."
    category: constraint
    applies_to: "El panel de cifras"
    trigger: "En cada cifra que se agregue al panel."
    logic: >
      El panel no pide credencial y los casos son de personas que usaron la demo.
      Los casos por aseguradora son cuántos, no cuáles. Es la regla que el
      proyecto aprendió en Refined Mockups y vale para toda superficie pública.
    violation: "Aparece un número de caso, un identificador o cualquier dato de un visitante."
    source: AC4.16.5, regla del proyecto sobre superficies públicas

  - id: BR2.2
    statement: Ninguna capacidad sin construir aparece como disponible.
    category: constraint
    applies_to: "El panel y las secciones generadas"
    trigger: "En cada fila que enumere una capacidad."
    logic: >
      Es P7 aplicado a la evidencia: prometer en el panel lo que no existe es
      peor que en cualquier otra pantalla, porque el panel existe precisamente
      para que se le crea.
    violation: "Una fila enlaza a algo que no existe, o describe algo no construido."
    source: AC4.1.4, P7

  # --- El gasto (AC5.14.1) ----------------------------------------------------
  - id: BR3.1
    statement: El panel de gasto pide una clave de operador, que no es una credencial de aseguradora.
    category: policy
    applies_to: "Las dos pantallas"
    trigger: "Al entrar."
    logic: >
      "Costo por caso" es una fila por caso, y eso es información de operación de
      Miguel, no evidencia para quien evalúa. Lo que sí es evidencia --el costo
      por caso promedio-- está entre las cinco cifras públicas.

      **Y no vale la credencial de la bandeja** (FD-U22-8). El gasto es del
      proyecto entero, no de una aseguradora, y los dos roles que existen
      --`adjuster` y `account_agent`-- son de una aseguradora. Darle a uno de ellos
      el gasto del proyecto dejaría que la credencial de una aseguradora alcance
      datos de las otras. Así que el panel lleva su propia clave de operador,
      declarada en el despliegue, y **sin ella no se monta**: una superficie que
      existe sin poder autenticar a nadie es una superficie que invita a probar.
    violation: "El gasto se sirve con una credencial de aseguradora, o la pantalla se monta sin clave."
    source: Respuesta 1A, AC4.16.5, FD-U22-8

  - id: BR3.2
    statement: El gasto se muestra por caso, por proveedor, por mes y como acumulado de la ventana de 90 días.
    category: policy
    applies_to: "El panel de gasto"
    trigger: "Al abrirlo."
    logic: >
      Las cuatro vistas ya existen como consultas del registro de gasto; esta
      unidad las muestra y no las calcula otra vez. La ventana empieza el
      2026-09-16 y es acumulada, nunca mensual.
    violation: "Falta una de las cuatro vistas, o el acumulado se calcula por mes."
    source: AC5.14.1, D11 de User Stories

  - id: BR3.3
    statement: El panel de gasto no reimplementa la alerta ni el corte.
    category: constraint
    applies_to: "El panel de gasto"
    trigger: "Siempre."
    logic: >
      La alerta de los 3 USD y el corte de los 5 los construyeron U15 y U16, con
      sus pruebas. Un segundo sitio que decida cuándo cortar es un segundo umbral
      que un día discrepa del primero.
    violation: "El panel decide si se corta, en vez de mostrar lo que ya está decidido."
    source: AC5.14.2, AC5.14.3

  # --- Las dos secciones generadas del README (US4.1) -------------------------
  - id: BR4.1
    statement: "«Cómo falla» sale del resumen de la última corrida completa, agrupa por la taxonomía de causa raíz, nombra los casos y cita su commit."
    category: policy
    applies_to: "La sección generada"
    trigger: "Al regenerarla."
    logic: >
      Los identificadores de caso son la moneda de todo el sistema: el reporte, el
      diff contra la línea base y esta sección los usan sin traducir. Una sección
      que dijera "algunos casos de citación fallan" no serviría para ir a mirar.

      La fuente es el resumen de la última corrida completa y **no la línea base**,
      porque una línea base publicada no puede traer fallos: BR2.1 rechaza
      publicarla con un solo caso en rojo, y hace bien. Leyéndola, la sección diría
      siempre "No case failed" y el criterio se cumpliría de forma y no de fondo.
      AC4.1.3 dice "el último reporte de evaluación", y esto es lo más cerca que se
      puede estar de eso con un archivo versionado: el reporte entero vive en `tmp/`
      y no se versiona a propósito (la huella del árbol de código no salta
      `app/evals/`, pero sí `tmp/`).

      Las cifras siguen saliendo de la línea base: son dos fuentes para dos
      secciones distintas, no dos lectores de lo mismo. Y el estado en el que la
      sección vive cuando no hay resumen es "no medida" con su causa, igual que las
      cifras.
    violation: "La sección no nombra ningún identificador, no cita commit, o lee la línea base."
    source: AC4.1.3, FD-U22-10

  - id: BR4.2
    statement: El chequeo del README falla si lo publicado no coincide con lo que producen la línea base vigente y el resumen de la última corrida completa, y corre en cada entrega.
    category: constraint
    applies_to: "Las dos secciones generadas"
    trigger: "En cada corrida del guion de verificación."
    logic: >
      Sin el chequeo, la sección envejece en silencio y el README vuelve a ser una
      diapositiva. Corre en cada entrega y no por hito porque entre hitos es
      justo cuando envejece. El arreglo es un comando, igual que los contratos
      generados; y sin línea base ni resumen las dos secciones dicen «no medida» y el
      chequeo compara contra eso, así que no se pone rojo por no haber medido.
    violation: "El README publicado y el generado difieren y la entrega pasa igual."
    source: AC4.1.3, respuesta 2A

  - id: BR4.3
    statement: El resumen de la última corrida completa se escribe siempre, en verde y en rojo, y nunca desde un subconjunto.
    category: constraint
    applies_to: "El resumen de la última corrida completa"
    trigger: "Al correr la corrida completa."
    logic: >
      Escribirlo solo cuando la corrida está en verde lo dejaría vacío justo cuando
      hay algo que contar, que es el defecto que esta familia de reglas existe para
      no repetir. Y escribirlo desde un subconjunto haría falsa toda proporción que
      la sección publique: "42 de 100" sobre un subconjunto de 74 no es 42 de 100.
      Por eso lo escribe el mismo comando que publica la línea base --que ya corre
      siempre la corrida completa y no acepta subconjunto-- antes de decidir si
      publica, y el tipo rechaza un resumen que declare subconjunto.
    violation: "La corrida completa termina en rojo y el resumen no se escribió, o se escribió desde un subconjunto."
    source: AC4.1.3, FD-U22-10
```

## Trazabilidad

| Familia | Reglas | `[bloquea]` |
| --- | --- | --- |
| De dónde salen las cifras | BR1.1 – BR1.5 | BR1.2 |
| Lo que no puede decir | BR2.1 – BR2.2 | BR2.1 |
| El gasto | BR3.1 – BR3.3 | — |
| El README generado | BR4.1 – BR4.3 | — |

## Sources

- `functional-design-questions.md` — las tres respuestas y las siete decisiones
- `../../../inception/user-stories/stories.md` — US4.16, US4.1, AC5.14.1

## Assumptions & Open Questions

None.
