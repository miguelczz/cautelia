# Instrucciones de prueba — U14 `inbox`

U14 es de la **rama evaluada**: realiza M9, M6 y M5, y sus casos previos son
RT-4 de DS-6 con las colisiones de DS-8, un caso derivado de DS-2 con su
explicación esperada, y los casos de clientes de Knotwell de DS-2.

La diferencia con las unidades anteriores es que aquí **todo lo que se prueba es
una frontera de acceso**. No hay una sola conducta interesante de esta unidad que
no se pueda resumir como "quién puede ver o hacer qué": la cola, la vista, la
corrección, la decisión y el enlace. Por eso las tres compuertas duras se
comprueban **por el punto de entrada**, nunca por la función interna: lo que hay
que demostrar es que nadie entra por la puerta, no que una función devuelva lo
correcto cuando se la llama bien.

## El caso previo, antes del código

RT-4 con las colisiones de DS-8 se escribe primero, se corre y se comprueba que
falla nombrando su razón. Es el que ata BR1.4 y BR5.1 a una compuerta de
seguridad medida sobre datos sembrados que colisionan a propósito —mismas
pólizas y mismos nombres en dos aseguradoras— y no sobre un caso cómodo.

## Lo que cada tanda deja probado

| Tanda | Pruebas | Dónde corren |
| --- | --- | --- |
| 1. La cola | Aserción de esquema sobre las dos tablas; **la compuerta dura de la credencial**, por la interfaz y por la API, con el control positivo delante; el orden por prioridad y espera; los filtros sin resultados; los casos que esperan al asegurado | Integración con base |
| 2. La vista y la corrección | Los seis bloques reunidos sin copia; "sin cláusula" frente a "no pude verificar"; el conteo de consultas; la corrección con su rastro y su recibo; el caso cerrado inmutable; la reanudación del flujo por `Last-Event-ID` | Integración con base |
| 3. La decisión y el enlace | El comentario obligatorio; el orden registrar-antes-de-reanudar; la clave reciclada como conflicto; dos personas un caso; las acciones por configuración; **las dos compuertas duras del enlace**, comparando las respuestas enteras | Integración con base |
| 4. Pantallas y cierre | Las tres pantallas; el encabezado pegajoso; los bloques plegados con su resultado a la vista; la pantalla del visitante en la línea base de accesibilidad; los casos de evaluación | Pruebas de pantalla y arnés |

## Las pruebas que aíslan una regla, escritas antes del código

Cada una rompe **una** regla y nada más, y se comprueba en rojo antes de escribir
lo que la satisface:

- **BR1.4** `[bloquea]` — una credencial de una aseguradora pidiendo la cola de
  otra, por la interfaz y por una petición directa.
- **BR1.1** — dos casos de la misma prioridad con esperas distintas, y dos
  prioridades con esperas invertidas: el orden no se puede satisfacer por
  casualidad con un solo caso.
- **BR1.3** — un filtro que no deja ninguna fila.
- **BR2.2** — un bloque plegado cuyo titular no dice su resultado.
- **BR2.5** — un caso con "sin cláusula" y otro con "no pude verificar".
- **BR3.3** — una fecha imposible: se rechaza y el valor anterior sigue ahí.
- **BR3.4** — una corrección sobre un caso cerrado, por la API.
- **BR4.1** — una decisión sin comentario.
- **BR4.3** — un caso derivado con completitud 3/7 (se decide) y uno esperando al
  asegurado (no se decide, ni por la API).
- **BR4.4** — dos decisiones sobre el mismo caso, y dos con la misma clave de
  idempotencia.
- **BR4.5** — una credencial de agencia aprobando por la API.
- **BR5.1** `[bloquea]` — una sesión de enlace pidiendo la cola.
- **BR5.2** `[bloquea]` — un enlace con la firma alterada y un caso inexistente,
  comparados campo por campo.
- **BR5.3** — los dos bordes de la hora, con el reloj por argumento.
- **BR5.4** — el enlace que vence mientras se escribe el comentario.
- **BR5.5** — una decisión con enlace atribuida a quien no es.
- **BR5.6** — el token en la dirección, en `Referer` o en un registro.
- **BR6.2** — una reconexión que se salta eventos.
- **BR6.3** — un dato personal en la tabla de avisos.

## Cómo se comprueban las tres compuertas duras

Las tres se miden **comparando dos respuestas enteras** —código y cuerpo— y no
comprobando que un dato ajeno no aparezca. La razón la dejó escrita U12 y la
aplicó U13: la filtración no es el dato, es la distinción.

En las tres, **el control positivo va delante**: la credencial legítima recibe su
cola real y el enlace legítimo su caso real antes de comprobar que el ajeno no
recibe nada. Sin él, las dos aserciones pasan igual con una implementación que no
entregue nunca nada, que es exactamente el defecto que U13 encontró en su propia
prueba del resumen de traza.

## Lo que se rompe para comprobar que la prueba prueba

Al cerrar cada tanda, cada regla nueva se rompe y se comprueba que **alguna
prueba se cae, por conducta rota y no por un `ImportError`**. El catálogo de
formas que no prueban está en `docs/reference/como-se-revisa-el-codigo.md` y la
skill `revisar-tanda` lo recorre.

Las que más probablemente acechen en esta unidad, por su forma:

- **La aserción que no puede distinguir**: comprobar que la cola de Stonecroft no
  trae casos de Sunmeadow con datos donde las dos aseguradoras no comparten nada.
  Por eso el caso previo son las colisiones de DS-8.
- **La que comprueba ausencia en vez de identidad**: las tres compuertas duras.
- **La que mide dentro de una sola ventana**: los dos bordes de la hora del
  enlace.
- **El módulo que miente sobre sí mismo**: la vista de caso dice reunir seis
  bloques; hay que comprobar que los seis llegan, no que la función existe.

## Cobertura

El piso del 80 % agregado sigue en pie, y esta unidad no añade ningún módulo
crítico nuevo: el aislamiento por tenant que sí lo es pertenece a U2 y aquí se
consume. La interfaz puede quedar por debajo mientras el agregado se cumpla.
