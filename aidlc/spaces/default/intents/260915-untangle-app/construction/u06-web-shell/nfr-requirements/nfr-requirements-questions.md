# Preguntas — Requisitos de calidad de U6 `web-shell`

El diseño funcional dejó dos cosas encargadas a esta etapa con nombre propio: la
lista de navegadores declarados (PA-4) y el presupuesto de tiempo del arnés de
accesibilidad. Al escribirla apareció una tercera que el diseño no resolvió: qué
cuenta como "menos de 3 segundos" para la página de espera. Las tres tienen dos
respuestas legítimas y las tres cambian lo que se promete a quien abre la demo.

Miguel delegó estas respuestas en la recomendación el 2026-09-21 ("la gracia es
de que hagas una verificacion de cual es la mejor opcion, la mas logica y por esa
misma te vayas"). Cada una lleva su razón escrita antes de la respuesta.

---

## Q1 — Qué navegadores se declaran, y con qué dato (PA-4)

`unit-of-work.md` dice que la lista se fija aquí **con el dato de WebRTC del
experimento 1**. Ese dato no existe: el experimento 1 midió los servicios de voz
desde un guion, no desde un navegador, y ADR-009 sigue esperando justo esa
medición. La pregunta es si U6 puede declarar su lista sin él.

- A. **(Recomendada)** U6 declara hoy la lista de **su** alcance —las dos últimas
  versiones mayores de Chrome, Edge, Firefox y Safari en escritorio, y de Safari
  en iOS y Chrome en Android—, porque nada de U6 usa WebRTC: el marco, el inicio
  y las páginas de estado son HTML, CSS y peticiones HTTP. La condición de WebRTC
  pasa, con su nombre, a `nfr-requirements` de U16, que es la unidad que abre el
  micrófono y la que puede medirlo. El arnés corre accesibilidad completa en el
  motor de Chromium y una prueba de dibujo de cada pantalla en los motores de
  Firefox y de WebKit.
- B. No declarar la lista hasta tener el dato de WebRTC. Deja a U6 sin objetivo de
  compilación ni de pruebas y ata una unidad sin voz a una medición de voz.
- C. La misma lista de A, pero con accesibilidad completa en los tres motores.
  Triplica el tiempo del paso más caro del arnés para un resultado que casi no
  cambia: el analizador revisa el documento, y el documento es el mismo en los
  tres motores.
- X. Other (please specify)

**Por qué la A.** Ata cada condición a la unidad que la puede medir. Y las
diferencias reales entre motores —fuentes, tamaños, una propiedad de CSS sin
soporte— se ven en la prueba de dibujo, que es barata; lo que el analizador
encuentra depende del documento, no del motor.

[Answer]: A

---

## Q2 — Qué cuenta como "menos de 3 segundos" para la página de espera

AC5.16.4 dice que con la instancia dormida, quien abre el chat o la consola ve en
menos de 3 segundos una página que dice que la demo está despertando. El mismo
número puede significar dos cosas muy distintas según dónde se mida.

- A. **(Recomendada)** Se mide en un **teléfono de gama media con red móvil
  lenta**, emulados en el arnés (red "4G lenta" y CPU cuatro veces más lenta, los
  perfiles de referencia de las herramientas de Chrome), con el proceso
  respondiendo 503: desde que empieza la navegación hasta que el título de la
  página de espera está pintado. El peso de lo que se carga antes de esa página
  queda con presupuesto propio.
- B. Se mide en escritorio, sin limitar red ni CPU. Pasa casi siempre y no dice
  nada de quien entra desde el enlace de LinkedIn en el teléfono.
- X. Other (please specify)

**Por qué la A.** US1.33 ya pide que todo funcione desde el teléfono, y quien
llega a una demo de portafolio desde una red social llega casi siempre así. Un
número medido en escritorio pasaría hoy y fallaría justo ante la persona que
importa. La otra mitad de la condición —que los archivos vivan en un hospedaje
que no se duerme— sigue siendo del intent `infra` (OQ4).

[Answer]: A

---

## Q3 — Cuánto tiempo puede tomar el arnés de accesibilidad en cada entrega

El arnés recorre cada pantalla en dos idiomas y dos modos (FD-U6-7). Hoy son
ocho pantallas de U6 y crecerá con cada unidad que agregue las suyas. Corre
dentro del guion de verificación, que es la única compuerta, y un paso lento es
un paso que alguien termina saltándose.

- A. **(Recomendada)** Un presupuesto de **4 minutos** para el paso completo en
  el flujo de integración continua, medido y publicado en cada corrida. Si el
  crecimiento lo pasa, el arnés **no se recorta en silencio**: se paraleliza por
  pantalla o se sube el presupuesto con una decisión escrita, y hasta entonces el
  exceso se reporta como fallo del presupuesto, no de accesibilidad.
- B. Sin presupuesto propio; que tome lo que tome. Nadie nota cuándo se volvió el
  paso que hace la compuerta de veinte minutos.
- X. Other (please specify)

**Por qué la A.** Cuatro minutos caben con holgura en lo que hoy tarda el flujo
y dan margen para las pantallas de U13, U14, U16 y U22. Y la regla de qué hacer
al pasarlo evita la salida fácil, que sería quitar idiomas o modos: eso es bajar
una compuerta.

[Answer]: A
