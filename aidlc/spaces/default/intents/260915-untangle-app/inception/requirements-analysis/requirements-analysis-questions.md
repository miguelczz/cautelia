# Preguntas de Requirements Analysis

Siete preguntas. El PRD v1.1 (`docs/specs/prd.md`) ya resuelve casi todo el
alcance: los quince módulos, los veintiún Must, los doce principios y las
métricas con sus umbrales. Lo que sigue son los huecos que impiden escribir un
requisito con criterio de aprobado o fallido, casi todos abiertos por la
decisión de ayer de publicar el enlace en vivo de la voz (D-018).

Cada pregunta lleva su recomendación con la razón. Responde escribiendo la letra
en el `[Answer]:` correspondiente.

---

## Q1 — Los números del enlace de voz en vivo

D-018 hizo obligatorio el enlace público de voz, con límites duros como
condición para publicarlo. Un requisito no es verificable sin cifras: hace falta
decir cuántos minutos dura una llamada, cuántas puede hacer un visitante y
cuántas caben en un día.

Para dimensionar: el modelo cuesta alrededor de un centavo por llamada de cuatro
minutos, y la transcripción sale del crédito gratuito de Deepgram. La voz paisa
en el tier gratuito de Cartesia alcanza para unas once llamadas al mes.

- `A.` Conservador: 3 minutos por llamada, 1 llamada por visitante al día, 15 llamadas al día en todo el sitio.
- `B.` Medio: 4 minutos por llamada, 2 llamadas por visitante al día, 30 llamadas al día en todo el sitio.
- `C.` Amplio: 5 minutos por llamada, 3 llamadas por visitante al día, 60 llamadas al día en todo el sitio.
- `X. Other (please specify)`

**Recomendación: A.** Una llamada de tres minutos ya recorre el camino completo
(saludo, siete campos, cláusula citada, derivación) y es lo que muestra el
guion del video. Quince al día son unas 450 al mes, muy por encima del tráfico
realista de un enlace de portafolio, y aun así acotan el peor caso. Son valores
de configuración: subirlos después no toca código.

[Answer]: A

---

## Q2 — Qué pasa cuando se agota el presupuesto de la voz paisa

La voz paisa es el renglón caro y su presupuesto mensual es pequeño. La pregunta
es qué debe hacer el sistema el día que se acabe, con el enlace ya publicado.

- `A.` Degradar sin caerse: cambia solo a una voz genérica gratuita y sigue atendiendo llamadas; el visitante ve un aviso honesto de que está oyendo la voz de respaldo.
- `B.` Rechazar llamadas nuevas con un mensaje honesto hasta el mes siguiente; el chat sigue vivo.
- `C.` Rechazar y ofrecer al visitante agendar una demostración contigo por LinkedIn.
- `X. Other (please specify)`

**Recomendación: A.** Es la opción que convierte la restricción en evidencia: un
evaluador que ve el sistema cambiar de proveedor solo, bajo presión de
presupuesto, sin romperse y diciendo la verdad, está viendo degradación elegante
funcionando. Es un componente más que mostrar, no un parche. Encaja además con
la arquitectura desacoplada que pediste: el proveedor de respaldo es otra entrada
en la configuración, no otra rama de código.

[Answer]: A

---

## Q3 — El tope de gasto, ahora que la voz se publica

El tope vigente son 5 USD en 90 días con alerta en 3 USD (D-015, M20). Cubre
unas 400 llamadas de cuatro minutos del modelo, así que alcanza; el renglón que
no alcanza es la voz paisa, que en tier gratuito da unas once llamadas al mes y
en el plan pago de Cartesia unas 66 al mes por 5 USD mensuales.

- `A.` Mantener 5 USD en 90 días. La voz paisa vive en su tier gratuito y, agotado, se degrada según Q2.
- `B.` Subir a 20 USD en 90 días, para pagar el plan de voz durante los dos meses en que la voz importa y tener la voz paisa viva casi todo el tiempo.
- `C.` Mantener 5 USD ahora y decidir en el día 30, con el gasto y el tráfico reales a la vista.
- `X. Other (please specify)`

**Recomendación: C.** Es exactamente lo que planteaste: dejar que el tiempo dé
la respuesta. Escribir 5 USD hoy como techo vigente, instrumentar el costo por
llamada y por proveedor, y revisar en el día 30 con datos. B se puede adoptar en
cualquier momento cambiando una cifra de configuración.

[Answer]: C

---

## Q4 — Cuánto se guardan las grabaciones y transcripciones de la demo pública

Desde el día en que el enlace es público, entra voz y texto de personas reales
aunque las pólizas sean inventadas. Hay que fijar cuánto tiempo se guarda, y eso
es un requisito verificable.

- `A.` Nada de audio: la grabación se descarta al terminar la llamada y solo queda la transcripción redactada, borrada en el reinicio nocturno junto con los datos de demostración.
- `B.` Audio y transcripción redactados, ambos borrados en el reinicio nocturno.
- `C.` Audio y transcripción redactados, conservados 7 días para poder depurar, y borrados después.
- `X. Other (please specify)`

**Recomendación: A.** El audio es el dato más sensible y el que menos falta hace:
las métricas de latencia salen de los eventos, no de la grabación, y el conjunto
de audio para evaluaciones son grabaciones tuyas y de voluntarios, no de
visitantes. Guardar menos también es más fácil de defender en el README.

[Answer]: A

---

## Q5 — Qué pasa con el caso que crea un visitante

Un evaluador que entra al chat o llama puede llenar un caso completo. La
pregunta es si ese caso vive de verdad (aparece en la bandeja, se puede aprobar)
o es de usar y tirar.

- `A.` Vive: el caso se guarda, aparece en la bandeja de demostración y el propio visitante puede entrar a la bandeja y aprobarlo, cerrando el ciclo completo. Todo se borra en el reinicio nocturno.
- `B.` Vive pero aislado: el caso se guarda y tú lo ves en la bandeja, pero el visitante no tiene acceso a ella.
- `C.` Efímero: el caso existe durante la sesión, muestra la cláusula citada y la derivación, y desaparece al cerrar.
- `X. Other (please specify)`

**Recomendación: A.** Es la demostración más fuerte que tiene el proyecto: la
persona en el bucle deja de ser una afirmación del README y pasa a ser algo que
el evaluador hace con sus manos. El riesgo de que alguien ensucie los datos lo
resuelve el reinicio nocturno, que ya está en las prácticas.

[Answer]: A

---

## Q6 — Cómo se entra a la bandeja del ajustador desde internet

Si el visitante va a cerrar el ciclo, necesita entrar a la bandeja. Eso implica
publicar unas credenciales, lo que choca de frente con la regla de no exponer
secretos; la excepción ya está nombrada en las prácticas, falta decidir su forma.

- `A.` Credenciales de demostración por aseguradora, publicadas en el README y en la propia página, sin ningún alcance fuera de su aseguradora, rotadas en el reinicio nocturno.
- `B.` Un enlace firmado que el propio chat entrega al visitante al cerrar su caso, válido una hora y solo para ese caso.
- `C.` Sin acceso público: la bandeja solo se muestra en el video y en local.
- `X. Other (please specify)`

**Recomendación: B.** Da el mismo ciclo completo que A pero sin publicar una
credencial reutilizable: el enlace nace del caso que la persona acaba de crear,
muere en una hora y no sirve para ver casos ajenos. Además demuestra la frontera
de aislamiento funcionando, que es justo lo que la regla de multi-tenant
promete. Si prefieres A, funciona, pero deja una credencial viva en internet
todo el tiempo.

[Answer]: B

---

## Q7 — Los nombres ficticios que quedaron pendientes

El PRD fija los tres inquilinos y deja tres nombres sin decidir. Hacen falta
para el corpus, para la bandeja y para los conjuntos de evaluación.

- `A.` Ajustador de Sunmeadow Auto: **Marcus Webb**. Agente de cuenta de Knotwell: **Priya Raman**. Jurisdicción: **Estado de Corvane** (la que ya está por defecto).
- `B.` Los mismos dos nombres, pero cambiar la jurisdicción a **Estado de Vantera**.
- `C.` Los mismos dos nombres, pero cambiar la jurisdicción a **Estado de Ellery**.
- `X. Other (please specify)`

**Recomendación: A.** Sunmeadow atiende en inglés y Knotwell también, así que los
dos nombres encajan con su idioma por defecto y contrastan con Diana, la
ajustadora de Stonecroft que atiende en español. Corvane ya está escrito en el
PRD y en el mapa del código; cambiarlo ahora obliga a editar varios documentos
sin ganar nada.

[Answer]: A

---

## Q8 — Seguimiento: el límite diario no cabe en el techo de gasto

Detectado al cruzar las respuestas de Q1 y Q3, como exige el análisis de
contradicciones de esta etapa.

Una llamada de tres minutos cuesta alrededor de 0,005 USD de modelo (unos quince
turnos, con caché de prompt). Quince llamadas al día son 0,075 USD diarios. En
noventa días eso suma unos **6,75 USD**, por encima del techo de **5 USD** que
elegiste mantener en Q3.

No es un error de ninguna de las dos respuestas: es que el límite diario reparte
el consumo pero no lo garantiza, y el techo es el que corta. Saturado todos los
días, el techo se alcanzaría cerca del **día 67**; a partir de ahí la voz
rechazaría llamadas nuevas y el chat seguiría vivo, que es el comportamiento
definido y no una falla. La pregunta es si eso te sirve o prefieres que ni
siquiera en el peor caso se llegue al techo.

- `A.` Dejar 15 al día y aceptar el corte hacia el día 67 en el peor caso. El techo es el control autoritativo; el límite diario solo reparte el consumo.
- `B.` Bajar a 10 llamadas al día, para que incluso saturado los noventa días quepan dentro de los 5 USD.
- `C.` Dejar 15 al día y subir el techo a 10 USD.
- `X. Other (please specify)`

**Recomendación: A.** El tráfico real de un enlace de portafolio está muy lejos
de la saturación: quince llamadas diarias sostenidas durante dos meses serían un
éxito enorme, y si eso pasa, subir el techo es la decisión fácil de tomar. El
corte ya está diseñado, es honesto y deja el chat vivo. Además es exactamente lo
que elegiste en Q3: revisar en el día 30 con datos reales, no adivinar hoy.

[Answer]: A

---

## Registro de modo de interacción

[Answer]: Guide me
