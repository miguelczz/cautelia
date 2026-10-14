# Preguntas de diseño funcional — U20 `demo-operations`

Una pregunta para Miguel, **ya contestada**, y nueve decisiones que tomé yo. La
pregunta era de operación y afecta lo que un visitante ve una noche que algo falle.

## Sources

- `../../../inception/user-stories/stories.md` — US5.1, US5.15
- `../../../inception/units-generation/unit-of-work.md` — U20 y la decisión UG-3
- `../../../inception/delivery-planning/pasada-de-publicacion.md` — AC5.6.4, diferido aquí
- El código: `tenancy/models.py` (`VisitorDataPurger` y su `Protocol` con `dry_run`),
  `server/composition.py` (**los nueve purgadores registrados a mano, con la razón de
  cada uno escrita al lado**), `mise.toml` (`corpus:ingest`, cuyo comentario dice que
  **U20 la invocará igual al aprovisionar, en vez de escribir la suya**)

## Assumptions & Open Questions

None. La pregunta está contestada abajo.

---

## Q1 — Cuando el reinicio no se completa en 24 horas, ¿qué ve quien llega?

**Por qué hay pregunta.** AC5.15.5 dice que si no se completa antes de 24 horas desde
el último reinicio exitoso, "el chat y la voz públicos dejan de aceptar casos nuevos con
el mensaje del catálogo". Eso está claro. Lo que el criterio no dice es **qué pasa con
lo que ya está abierto**, y hay dos lecturas honestas.

**Respuesta de Miguel (2026-09-30): opción A.** Se dejan de aceptar **casos nuevos**, y
una conversación o una llamada ya abierta **termina normalmente**. Quien está a mitad de
reportar un siniestro lo termina; quien llega después lee el mensaje del catálogo.

Es la lectura literal de "casos nuevos", y nadie pierde trabajo a mitad por un fallo de
operación que no es suyo.

**Lo que cuesta, y queda escrito porque es un compromiso y no un detalle:** los datos de
quien terminó esa conversación se quedan una noche más, que es exactamente lo que el
reinicio existe para evitar. La ventana se alarga; lo que la mantiene acotada es que la
alerta ya salió y que el reintento sigue corriendo. **La degradación es a propósito: la
demo se estrecha en vez de caerse.**

La opción descartada era cortar todo, incluido lo abierto: devolvía la retención a su
ventana de inmediato, al precio de que alguien perdiera un reporte a mitad.

---

## Las nueve decisiones que tomé yo

| # | Qué | Por qué no es pregunta |
| --- | --- | --- |
| FD-U20-1 | **El reinicio no borra ninguna tabla: llama a los nueve purgadores que ya existen**, en el orden del registro escrito a mano de la raíz de composición | UG-3, y el propio registro lo dice: escrito a mano y nunca descubierto solo, porque un descubrimiento deja de encontrar lo que alguien nombró distinto. Una décima consulta de borrado aquí sería el sitio donde la retención deja de estar acotada sin que nadie lo note |
| FD-U20-2 | **La orquestación del reinicio es pura sobre el `Protocol`**: recibe los purgadores, el reloj y el corte, y devuelve qué se borró y qué falló. No abre sesión | Es lo que la deja probable entera con dobles, sin base, y lo que permite que la tanda 1 vaya a la nube. El `Protocol` ya existe y ya trae `dry_run` |
| FD-U20-3 | **El aprovisionamiento valida la carpeta completa antes de crear nada**, y falla nombrando el archivo y el campo que faltan | AC5.1.3, literal. Validar a mitad deja una aseguradora existiendo a medias, que es peor que no existir: nada la borra y nada la completa |
| FD-U20-4 | **El aprovisionamiento invoca `corpus:ingest`, no escribe su propia ingesta** | El comentario de esa tarea ya lo dejó escrito. Una segunda ingesta sería un segundo sitio donde el corpus se indexa distinto |
| FD-U20-5 | **El aprovisionamiento es idempotente**: correrlo otra vez con la misma configuración deja el mismo estado y no duplica nada | AC5.1.5. Y es lo que hace que el comando se pueda correr sin miedo, que es la mitad de su valor |
| FD-U20-6 | **El registro de gasto sobrevive al reinicio**, y eso ya está decidido purgador por purgador: U5 borra los contadores de visitante y de sesión y conserva el del sitio, la ventana y el libro mayor | Está escrito al lado de cada purgador en la raíz de composición. Esta unidad no decide qué se conserva: lo decide el dueño de cada tabla, y aquí solo se llama |
| FD-U20-7 | **Cada corrida del reinicio deja un `ResetRun`**, con qué purgadores corrieron, qué borró cada uno, cuánto tardó y si falló alguno | AC5.15.5 pide alerta y reintento, y sin registro no hay nada que alertar ni con qué comparar. Y es el dato que dice si la demo estuvo limpia anoche |
| FD-U20-8 | **Una conversación abierta a la hora del reinicio recibe el aviso del catálogo**, y su mensaje siguiente abre un caso nuevo sin error | AC5.15.3. El chat ya sabe abrir un caso en el primer mensaje: lo que falta es que el aviso llegue y que la conversación no quede apuntando a un caso que ya no existe |
| FD-U20-9 | **La unidad se parte en dos tandas por dónde puede correr cada una**: la validación de la carpeta, la orquestación con dobles y el `ResetRun` a la nube; los nueve purgadores de verdad, la ingesta y el backend de trazas aquí | La nube no tiene base ni motor de contenedores, y el reinicio de verdad se comprueba contra una base con datos sembrados |

## Lo que esta unidad no construye

- **El borrado de cada tabla**: lo implementa su dueño, y los nueve ya existen.
- **El disparador nocturno**: lo fija el intent `infra`.
- **La ingesta del corpus**: existe como tarea y aquí se invoca.
- **Que el reinicio devuelva los casos sembrados a su estado sembrado** (AC5.6.4): está
  diferido a la pasada de publicación y es conducta de esta unidad cuando se cierre.
