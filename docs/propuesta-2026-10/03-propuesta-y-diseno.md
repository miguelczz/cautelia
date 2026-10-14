# Propuesta: una agente que entiende, guía y responde de verdad

Para Miguel, 2026-10-07. Parte de `01-como-funciona-hoy.md` y `02-hallazgos.md`. Las
decisiones que te tocan están al final, cada una con mi recomendación.

## El principio: que nadie se pierda

La persona que entra no sabe qué hacer ni qué es una póliza de ejemplo. Cada mensaje de
la agente tiene que dejarle claro qué hacer después y ponérselo fácil. Cinco reglas
concretas:

1. **Contesta lo que le preguntan, antes de seguir.** Si la persona pregunta «¿cuántos
   años es eso?», la agente responde «serían unos 4 años, lo anoto así» y luego
   continúa.
2. **Una pregunta a la vez, con un ejemplo de respuesta.** «¿Cuándo nació el
   conductor? Por ejemplo: 3 de mayo de 1990.»
3. **Botones de respuesta rápida** bajo cada pregunta: «Reportar un accidente»,
   «Preguntar por mi póliza», «Cotizar», «Usar la póliza de ejemplo», «Hoy», «Ayer»,
   «Sí», «No». Escribir nunca es obligatorio.
4. **Siempre sabe dónde va.** «Llevamos 3 de 5 datos; ahora, ¿dónde fue?»
5. **Nunca se equivoca de tema.** Si la conversación es una cotización, no habla de un
   accidente.

## Fase 0. Que la agente entienda la conversación

Es el cambio de fondo, y lo que piden tus capturas. Hoy nadie entiende la conversación
entera:

- el tipo de conversación sale de palabras clave;
- un modelo gratuito y lento saca los datos sin razonar;
- una lista fija decide la siguiente pregunta;
- otro modelo la dice bonita sin saber de qué trata la conversación.

**Cómo quedaría cada turno.** Dos llamadas a Claude Haiku, de alrededor de un segundo
cada una:

1. **Entender.** El modelo recibe:
   - la aseguradora;
   - el tipo de conversación;
   - lo que ya se sabe y lo que falta;
   - los últimos mensajes y el mensaje nuevo.

   Devuelve una respuesta estructurada, no texto libre:
   - qué quiere la persona: reportar, preguntar por su póliza, cotizar, una duda
     general, hablar con alguien o solo saludar;
   - los datos que dio, ya interpretados: «desde 2022» se convierte en 4 años de
     licencia, y «hoy a las 7» en la fecha y la hora;
   - si hizo una pregunta, cuál fue.
2. **Decidir.** Lo decide el código, como siempre:
   - valida cada dato contra el esquema del caso;
   - guarda los datos;
   - elige qué falta, cuándo se cierra y cuándo se deriva al ajustador.
3. **Decir.** El modelo redacta la respuesta sabiendo de qué trata la conversación:
   contesta la pregunta de la persona, reconoce lo que dijo y hace la siguiente
   pregunta que eligió el código, con su ejemplo y sus botones.

**Lo que no cambia:**

- el código decide qué falta, cuándo se cierra y quién decide;
- la guardia de salida revisa todo texto;
- la comprobación de cifras y códigos sigue activa;
- si el modelo falla o tarda, sale la frase fija;
- la agente nunca afirma cobertura, montos ni culpa.

**Sobre el tiempo.** Hoy un turno tarda de 2,5 a 4,5 segundos por el modelo gratuito
lento. Con este diseño serían unos 2 a 2,5 segundos.

**Sobre el costo.** Unos 3.000 tokens por turno con Claude Haiku.

| Medida | Valor |
| --- | --- |
| Costo por turno | 0,0005 USD |
| Costo por conversación de 15 turnos | 0,008 USD |
| Conversaciones con tus 5 USD | unas 600 |

**Lo que corrige de una vez:**

- toda la sección E de los hallazgos;
- la clasificación del primer mensaje (C1, C2);
- el «¿es usted y conducía?» (C3);
- el «meses sin seguro» a quien tiene seguro vigente (C7).

**Cómo se prueba.**

- Antes de construir, escribo como casos de evaluación las conversaciones de tus
  capturas, y otras del mismo tipo en español e inglés. Deben fallar hoy.
- Después de construir, deben pasar.
- Las compuertas de siempre siguen igual.

### La apertura, tal como la pediste

> Hola, soy Catalina, la asistente de inteligencia artificial de Autos Poblado. Esto es
> una demostración con pólizas de ejemplo, así que no escriba datos personales reales.
> Puedo ayudarle a reportar un siniestro, a resolver dudas sobre su póliza o darle una
> cotización.

En las aseguradoras que no cotizan termina en «…a reportar un siniestro o a resolver
dudas sobre su póliza.».

Saca la mención a que la conversación se guarda y se borra cada noche. Eso modifica
un criterio aprobado, el AC1.1.1, que pedía decirlo. Lo registro como tu decisión.

Debajo de la apertura aparecen los tres botones: «Reportar un accidente», «Preguntar
por mi póliza» y «Cotizar». El saludo deja de repetir la apertura y contesta corto:
«¡Hola! ¿Quiere reportar un accidente, resolver una duda de su póliza o pedir una
cotización?», con los mismos botones.

### Tus datos en tu propia burbuja

La persona verá lo que escribió tal cual, también al recargar la página. Su navegador
guarda su propia copia mientras dure la conversación. La base de datos sigue
guardándolo tapado, porque esa es una regla de seguridad del proyecto: el chat es
público y alguien puede escribir datos reales aunque se le pida que no.

## Fase 1. Que preguntar por una póliza funcione de punta a punta

La promesa central del producto, y hoy rota (hallazgos A y B).

> Tú: ¿Mi póliza cubre el granizo?
> Catalina: Para revisarlo necesito el número de su póliza. Si no tiene una, use la de
> ejemplo. *[botón: Usar la póliza de ejemplo POL-100042]*
> Tú: POL-100042
> Catalina: Encontré la póliza POL-100042 a nombre de Natalia Henao Rendón. ¿Es usted?
> *[Sí] [No]*
> Tú: Sí
> Catalina: Su póliza habla del granizo en «Parte D — Daños a su vehículo», dentro de
> otros daños distintos al choque, con un deducible propio. Abajo le dejo la cláusula
> exacta. Que aplique a su caso lo decide un ajustador. *[Que lo revise un ajustador]
> [Tengo otra pregunta]*

**Lo que cambia por dentro:**

1. **En la consulta solo se pide la póliza**, y la confirmación es «¿Es usted?» (A2,
   A5).
2. **El paso que falta: proponer las citas.**
   - El código busca las 8 cláusulas más cercanas de esa póliza.
   - Claude Haiku lee solo esas 8 y propone cuáles responden la pregunta.
   - El verificador de cuatro comprobaciones decide qué citas salen.
   - Si no sale ninguna, la agente dice que no encuentra una cláusula y no adivina
     (A3).
3. **La respuesta llega en el mismo turno.** Pasa igual si la pregunta llega en medio
   de un reporte: la agente responde y retoma el dato que faltaba. Desaparece el «un
   momento» que bloqueaba la pantalla (A6, A7).
4. **La consulta termina.** «Que lo revise un ajustador» la deriva a la bandeja (A4).
5. **La decisión vuelve al chat**, con el aviso que ya existe, y la página del caso deja
   de prometer lo que no pasa (B1 a B3).
6. **«Comparar aseguradoras»** funciona por este mismo camino y se enlaza desde el
   inicio (A8, D3).

**Costo:** unos 0,0004 USD por respuesta con citas, alrededor de 0,40 USD por cada mil.

## Fase 2. Pestaña «Pólizas» y panel «Documentos que consulta Catalina»

### Pestaña «Pólizas»

Va en la barra superior, junto a «Resultados».

```
┌──────────────────────────────────────────────────────────────────────┐
│ Pólizas                                                              │
│ Las pólizas de ejemplo de cada aseguradora. Elija una y pregunte     │
│ por ella en el chat o en la llamada.                                 │
│                                                                      │
│ [ Seguros Aburrá ]  [ Autos Poblado ]  [ Agencia Castilla ]          │
│                                                                      │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                   │
│ │ POL-100042 ★ │ │ POL-100118   │ │ POL-100205   │   (6 por          │
│ │ Natalia H.   │ │ ...          │ │ ...          │    aseguradora)   │
│ │ Renault Logan│ │              │ │              │                   │
│ └──────────────┘ └──────────────┘ └──────────────┘                   │
│                                                                      │
│ ── POL-100042 · vigente del 2 ene 2026 al 2 ene 2027 ──────────────  │
│ Qué cubre                                                            │
│   Responsabilidad civil   lesiones: 100.000 por persona,             │
│                           200.000 por accidente; daños: 20.000       │
│   Gastos médicos          5.000 por persona                          │
│   Conductor sin seguro    100.000 / 200.000                          │
│   Daños a su vehículo     deducible choque 250; otros daños 100      │
│ Endosos vigentes (5)      «Familiar que estudia en otra ciudad», …   │
│                                                                      │
│ Preguntas para probar                                                │
│   [¿Me cubre el granizo?]  [¿Me pagan un carro de alquiler?]         │
│                                                                      │
│ [ Preguntar en el chat con esta póliza ]  [ Ver sus documentos ]     │
└──────────────────────────────────────────────────────────────────────┘
```

- **Las preguntas para probar son botones.** Abren el chat de esa aseguradora con la
  póliza y la pregunta ya enviadas. Salen de las diferencias declaradas entre
  aseguradoras, que ya existen en los datos.
- **Se muestran:** número, titular, vehículos, vigencia, límites, deducibles y endosos.

### Panel «Documentos que consulta Catalina»

Una ventana que se abre desde la pestaña de pólizas, desde la cabecera del chat y desde
cada cláusula citada («verla en su documento»).

```
┌──────────────────────────────────────────────────────────────────────┐
│ Documentos que consulta Catalina · Seguros Aburrá               [×]  │
│ Cuando usted pregunta por su póliza, Catalina busca aquí las 8        │
│ cláusulas más cercanas, solo de su póliza, y un verificador revisa   │
│ cada cita. Si no hay una cláusula sobre el tema, no adivina.         │
│                                                                      │
│ Documentos                 │ Parte D — Daños a su vehículo  [buscar] │
│ ▸ Póliza de autos 2026 (86)│ STO-PAP-2026-D.1  ...texto...           │
│   Jurisdicción (5)         │   La modifica el endoso 3               │
│   Endoso 1 … Endoso 5      │ STO-PAP-2026-D.2  ...texto...           │
│   Versión 2025 (no vigente)│                                         │
│                            │ Citada 12 veces esta semana             │
└──────────────────────────────────────────────────────────────────────┘
```

- Muestra los documentos por aseguradora, las cláusulas agrupadas por parte, un
  buscador y las relaciones entre cláusulas.
- La versión 2025 aparece marcada como no vigente. Se explica que está para comprobar
  que la agente no cita documentos viejos.
- **Sobre «cómo se retroalimenta».** Los documentos no cambian con las conversaciones,
  y el panel lo dice. Lo que sí cambia, y se muestra, es cuántas veces se citó cada
  cláusula. Es un dato agregado que no identifica a nadie.

**Por dentro:**

- cuatro rutas públicas de solo lectura, con aislamiento por aseguradora y límite por
  origen;
- un componente de ventana modal accesible, de la misma familia que ya usa la
  interfaz, con licencia MIT;
- los textos en el catálogo, en español e inglés.

## Fase 3. Lo que queda

- **Insultos (C4):** al tercero se cierra de verdad y se deriva.
- **La llamada (C5, C6):**
  - la pregunta inicial es «¿Hubo alguien herido?», como en el chat;
  - no cuelga después de hacer una pregunta;
  - usa la misma comprensión de la fase 0 si cabe en su segundo y medio por turno.
- **Cotización (C8, E5):**
  - las solicitudes que van a suscriptor llegan a la bandeja;
  - las preguntas se adaptan a Colombia.
- **Pantallas (B5, D2, D4 a D8):**
  - el inicio dice para qué es la póliza de ejemplo;
  - la guía muestra el enlace del caso;
  - «Resultados» explica cada cifra;
  - la traza tiene botón para volver;
  - hay un enlace para elegir otra aseguradora;
  - las páginas de personal lo dicen;
  - «grafo» se cambia por palabras llanas.

## Decisiones

**Decididas por Miguel el 2026-10-07: todas como se recomienda abajo.**

1. **Que la agente entienda con Claude Haiku (fase 0).** Esto cambia una regla
   aprobada del proyecto: hoy el tipo de conversación lo deciden reglas de palabras.
   Con el cambio, lo propone el modelo como una opción cerrada, y el código lo valida y
   decide. Cuesta 0,008 USD por conversación. Recomiendo hacerlo.
2. **Cuántas pólizas mostrar.** Recomiendo las 6 de cada aseguradora.
3. **En qué unidad mostrar los límites.** Los datos no traen moneda. Recomiendo pesos
   colombianos multiplicando por mil, para que «100.000» se lea como cien millones; si
   no, dólares. Las cifras se ven muy chicas como pesos sin escalar.
4. **Tú o usted en las pantallas.** La agente habla de usted y la pantalla de tú.
   Recomiendo usted en todo.
5. **El «decídalo usted mismo» de la demo.** Recomiendo dejarlo, explicado en la guía
   y en la página del caso como «en esta demo usted puede hacer de ajustador». La
   agente dejaría de decir «decidirlo».
6. **Preguntas de cotización para Colombia.** Ejemplo: «¿En qué ciudad sacó la
   licencia?» en lugar de «¿en qué estado?». Recomiendo adaptarlas.
7. **Orden.** Recomiendo fase 0, luego fase 1, fase 2 y fase 3. La pestaña de pólizas
   invita a preguntar, y eso solo tiene sentido cuando la pregunta se responde bien.
