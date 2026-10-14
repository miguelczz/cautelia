# Preguntas — Infraestructura de U1 `workspace`

U1 **no se despliega**. Su infraestructura son tres cosas: el entorno local que
alguien levanta en su máquina, el flujo de integración continua que corre la
compuerta, y lo que deja escrito para que el intent `infra` no tenga que
inventarlo.

**Fuentes consumidas.** `../nfr-design/performance-design.md` (el camino de los
15 minutos y el trabajo semanal), `../nfr-design/security-design.md` (los ocho
controles y los dos trabajos del flujo), `../nfr-design/scalability-design.md`
(las tres válvulas), `../nfr-design/reliability-design.md` (los nueve pasos del
guion y la política de fallo), `../nfr-design/observability-design.md` (qué
registra una corrida y dónde sobrevive), `../nfr-design/logical-components.md`
(el inventario y los dominios de fallo),
`../../../inception/domain-design/components.md` y `.../decisions.md` (ADR-002
lenguajes y herramientas, ADR-010 PostgreSQL con pgvector, ADR-015 Langfuse en
local con docker compose), `../functional-design/functional-spec.md` (los tres
flujos) y `../../../inception/contract-design/contract-summary.md` (C-24, C-27,
C-28).

## Lo que se aplica sin preguntar

- **Los dos trabajos del flujo**: el primero invoca el guion acotado al escaneo
  de secretos, el segundo corre el resto. Ya decidido en el diseño no funcional.
- **Permisos vacíos por defecto y acciones fijadas por identificador de commit.**
  Práctica afirmada.
- **PostgreSQL con pgvector y Langfuse en local con docker compose.** ADR-010 y
  ADR-015.
- **Langfuse no se levanta en el camino de los 15 minutos.** Ya decidido.
- **Nada de despliegue, entornos ni hospedaje.** Son del intent `infra` y de la
  pregunta abierta de hospedaje; U1 no los toca.

**Un dato corregido de paso.** Los requisitos de seguridad decían que había que
añadir la negación `!.env.example` al `.gitignore`. Ya está: hoy el archivo
ignora `.env` y `.env.*`, y en la línea siguiente exceptúa `.env.example`. No hay
nada que hacer ahí.

Quedan **cuatro decisiones**.

## Q1 — Cómo se anclan las imágenes de los servicios locales

Los requisitos piden anclar las imágenes "por versión exacta, no por etiqueta
móvil". Hay dos formas de leer eso y no dan lo mismo.

A. **Por huella digital (el identificador del contenido)** (recomendada): la
   imagen queda congelada byte a byte, así que dos máquinas y la tubería corren
   exactamente lo mismo, hoy y en seis meses. Es además el único anclaje que una
   etiqueta reescrita no puede cambiar por debajo. El costo es que subir de
   versión exige buscar la huella nueva, y el archivo se lee peor
B. **Por etiqueta de versión precisa**: legible y suficiente casi siempre; una
   etiqueta puede reescribirse en el registro, y entonces el tiempo de arranque
   —que es lo que mide la meta de los 15 minutos— cambia sin que nadie lo haya
   tocado
C. **Por etiqueta mayor**: lo más cómodo de mantener y lo que los requisitos ya
   descartaron; una versión que cambia sola mueve la medición
X. Other (please specify)

[Answer]: A

**Nota.** Miguel delegó primero esta decisión ("si estás teniendo en cuenta que
usaremos Docker... entonces la que me recomiendas"). Se le confirmó que Docker
está contemplado y ya instalado en su máquina, se explicó por qué la huella
digital es la recomendada —la meta de los 15 minutos depende de cuánto tardan
las imágenes en bajar y arrancar, y una etiqueta reescrita movería esa medición
sin que nadie tocara el proyecto— y se le volvió a presentar la pregunta, que
respondió `A`.

## Q2 — De dónde salen la base de datos y las trazas en la tubería

Las pruebas y la corrida de evaluaciones necesitan una base de datos. GitHub
Actions ofrece la suya, y nosotros ya tenemos una definida para la máquina de
quien desarrolla.

A. **La misma definición de docker compose que se usa en local** (recomendada):
   una sola descripción de la base de datos en todo el proyecto. Lo que corre la
   tubería es literalmente lo que corre en tu máquina, así que un fallo que solo
   aparece en la tubería deja de ser un misterio. El costo es medio minuto más de
   arranque y que hay que cuidar que no choquen los puertos
B. **Los contenedores de servicio de GitHub Actions**: es la forma idiomática y
   arranca algo más rápido, con comprobación de salud incluida. El costo es
   real: la base de datos queda descrita en dos sitios, y el día que se separen
   la tubería y tu máquina dejan de probar lo mismo
C. **Sin base de datos en la tubería**, saltando las pruebas que la necesitan:
   la corrida más rápida y una compuerta que deja de medir justo lo que más
   importa
X. Other (please specify)

[Answer]: A

## Q3 — Cuándo se revierte un `main` en rojo

La compuerta corre **después** de que el cambio ya aterrizó, así que un `main`
en rojo es un incidente. La práctica dice que arreglar hacia adelante tiene
prioridad, pero no dice hasta cuándo.

A. **Hacia adelante, y si no está verde en 30 minutos se revierte**
   (recomendada): el arreglo directo sigue siendo lo primero, y hay un punto de
   corte escrito. Sin ese punto, "hacia adelante" se convierte en dos horas de
   `main` roto en el que no puede entrar nada más, que es peor que revertir
B. **Siempre hacia adelante, sin límite**: lo más simple de recordar; un fallo
   difícil puede dejar el tronco bloqueado toda una tarde
C. **Revertir siempre, de inmediato**: el tronco vuelve a verde en un minuto
   siempre; para un error de una línea es más ceremonia que arreglo, y cada
   reversión es un viaje de ida y vuelta
X. Other (please specify)

[Answer]: A

## Q4 — Cómo te enteras de que `main` se puso rojo

Si un `main` en rojo es un incidente, hace falta decir por dónde llega el aviso.
Hoy no llega por ningún lado.

A. **Las notificaciones del propio GitHub, configuradas para fallos**
   (recomendada): correo y aviso en la aplicación móvil cuando una corrida falla
   sobre `main`, sin instalar ni pagar nada y sin un servicio más que mantener.
   Es lo que hace que la palabra "incidente" signifique algo
B. **Un canal aparte** (mensajería o similar) con un aviso automático: más
   visible si ya vives en esa aplicación; es un servicio más, una credencial más
   y algo más que se puede romper en silencio
C. **Mirarlo a mano**: cero configuración, y un `main` roto que nadie mira deja
   de ser un incidente y pasa a ser el estado normal
X. Other (please specify)

[Answer]: A
