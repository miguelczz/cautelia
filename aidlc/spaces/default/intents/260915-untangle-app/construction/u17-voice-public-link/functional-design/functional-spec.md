# Diseño funcional — U17 `voice-public-link`

Lo que hace publicable la voz: dos carriles diarios, una ventana de retoma, la voz
elegida antes de cada llamada, y una consola que dice todo eso **antes** de pedir el
micrófono.

## Sources

- `../../../inception/user-stories/stories.md` — US5.12, US5.11, US4.17, D12
- `functional-design-questions.md` — las diez decisiones y los tres hallazgos del código
- El código: `voice/availability.py`, `voice/loop.py`, `tenancy/models.py`,
  `telemetry/spend/quota.py`, `server/voice_routes.py`

## Assumptions & Open Questions

None.

---

## Flujo 1 — Antes del micrófono (AC4.17.1, AC4.17.2, AC5.12.3)

1. La consola pregunta la disponibilidad y **antes de pedir el micrófono** dice: que es
   una demostración con pólizas de ejemplo, si la voz está disponible, y los dos
   límites —tres minutos por llamada y una llamada al día **desde esta conexión**—.
2. Muestra la póliza de ejemplo de la aseguradora elegida y sugiere qué probar:
   reportar un choque, preguntar por la cobertura, interrumpir a la agente y cambiar de
   idioma.
3. Si no hay voz, dice **por qué** —uno de los cuatro códigos cerrados, con la frase de
   su catálogo— y ofrece el chat, **sin pedir el micrófono**.
4. Si el carril del visitante o el del sitio están agotados, el rechazo es honesto, con
   su causa y la oferta del chat, también antes del micrófono.

**"Desde esta conexión" y no "por persona"** (AC5.12.6): un visitante cambia de
navegador o de red, así que este carril no es un control de gasto y la consola no
insinúa que lo sea.

---

## Flujo 2 — Los dos carriles y la ventana de retoma (AC5.12.2, AC5.12.4)

1. La decisión es **pura**: recibe la configuración de la aseguradora, lo que los
   contadores ya dicen y el reloj, y devuelve admitir o **cuál** carril rechazó.
2. Una llamada que terminó en el límite deja el caso retomable durante la ventana
   (`resume_window_seconds`, 900 por omisión).
3. Volver a llamar **dentro** de la ventana retoma el mismo caso y **no consume la
   llamada del día**; sí cuenta contra las llamadas del sitio y contra el techo de
   gasto. Fuera de la ventana es una llamada nueva.
4. Los dos valores son configuración: cambiarlos y desplegar no cambia código
   (AC5.12.4).

**La asimetría de la retoma es el punto del diseño.** El carril del visitante protege
la experiencia —que quien prueba pueda terminar lo que empezó— y el del sitio y el
techo protegen el dinero. Tratarlos igual sacrificaría uno de los dos.

---

## Flujo 3 — La voz, decidida antes de cada llamada (US5.11)

1. Antes de abrir, se compara lo que queda del presupuesto público con la reserva de
   una llamada completa a la voz principal. La decisión **ya existe y es pura**
   (`quota.voice_mode`): lo que esta unidad hace es **cablearla**.
2. Si no cubre la reserva, la llamada entera se atiende con la voz de respaldo y la
   consola lo avisa **antes de la primera frase**, diciendo que puede sonar distinta en
   cada idioma.
3. **Nunca se cambia de voz por presupuesto a mitad de llamada.** La que empezó con la
   principal termina con la principal; la siguiente empieza con la de respaldo si lo
   que queda ya no cubre otra reserva.
4. Al empezar un periodo nuevo de cuota, vuelve la principal, y la telemetría registra
   la hora de cada cambio.

**Con cualquiera de los dos datos sin medir, la respuesta es la voz de respaldo.**
Afirmar que cabe lo que no se sabe cuánto cuesta es la forma de pasarse del techo sin
haberlo decidido.

---

## Flujo 4 — Durante y después de la llamada (AC4.17.3 a AC4.17.6)

1. El estado de la llamada, el tiempo restante y el botón de colgar están **siempre
   visibles**, también a 360 px.
2. La transcripción etiqueta con texto quién habla, y la consola muestra el estado de
   la agente: escuchando, pensando, hablando o revisando la póliza.
3. Al terminar un turno, la consola muestra la latencia del fin del habla al primer
   audio, con esa etiqueta, y su valor **coincide con los eventos de la traza** de ese
   turno.
4. Al terminar la llamada —por colgar, por corte o por límite— la consola muestra el
   número de caso, su estado y el enlace firmado si quedó derivado o cerrado.
5. Si el caso quedó "esperando al asegurado", la consola dice que hay quince minutos
   para volver a llamar sin gastar la llamada del día, y ofrece un botón que lo pasa ya
   a un ajustador, lo deriva como solicitud de persona y muestra su enlace firmado.

---

## Flujo 5 — Los topes en el proveedor (AC5.12.5)

1. Una **tabla versionada** con una fila por proveedor de pago: qué tope, dónde se
   configuró y **la fecha de su última comprobación**.
2. El simulacro del checklist del segundo día corre con una clave de prueba de tope
   mínimo y la aplicación detenida, comprueba que el proveedor rechaza la llamada que
   se pasa, y **registra el resultado con su fecha**.

**Un límite que vive solo en la aplicación falla abierto cuando lo que falla es la
aplicación.** Y un tope configurado hace tres meses y no comprobado no es un tope: es
un recuerdo. Por eso la fecha es una columna y no una nota.

---

## Lo que esta unidad no construye

- **La llamada y su consola base**: U16.
- **El corte y el aviso de los treinta segundos**: ya existen en U16.
- **La decisión de la voz**: ya existe y es pura; aquí se cablea.
- **El techo de gasto y su alerta**: U5 y U15.
- **Configurar los topes en cada proveedor**: lo hace Miguel; aquí queda escrito y
  comprobado.

## Resumen de reglas (vista derivada)

Las reglas están en `rules.md`. Dos llevan `[bloquea]`: que ninguna llamada pública se
abra sin pasar los dos carriles, y que la voz no cambie por presupuesto a mitad de
llamada.

## Metas medibles

| Meta | Valor | De dónde |
| --- | --- | --- |
| Llamadas abiertas sin pasar los dos carriles | **cero** | AC5.12.3, en cada entrega |
| Cambios de voz por presupuesto a mitad de llamada | **cero** | AC5.11.2, en cada entrega |
| La decisión de los dos carriles | p95 ≤ 1 ms sumados | PERF-U17.1, como los cinco del chat |
| Topes del proveedor con su fecha de comprobación | todos | AC5.12.5, por hito |
