# Preguntas de diseño funcional — U17 `voice-public-link`

**Ninguna pregunta para Miguel**, y eso es el resultado de leer el código: casi todo
lo que esta unidad parecía tener que decidir ya está decidido en un criterio aprobado
o construido y sin cablear. Diez decisiones, todas mías.

## Sources

- `../../../inception/user-stories/stories.md` — US5.12, US5.11, US4.17 y la decisión D12
- `../../../inception/units-generation/unit-of-work.md` — U17 y su orden de entrega
- `../../../inception/delivery-planning/pasada-de-publicacion.md` — los carriles diarios,
  diferidos aquí a propósito
- El código: `voice/availability.py` (**`VoiceOffCode` ya declara los dos carriles y
  dice "quien los devolverá es U17"**), `tenancy/models.py` (`CallConfig`, con tres
  campos y la razón escrita de por qué no son cinco), `telemetry/spend/quota.py`
  (**`voice_mode()` ya existe y es pura**), `server/voice_routes.py` (`VoiceMode.PRIMARY`
  escrito a mano en cuatro sitios), `voice/loop.py` (el corte y el aviso, ya
  construidos)

## Assumptions & Open Questions

None.

---

## Lo que el código ya tenía hecho, y cambia el tamaño de la unidad

Tres hallazgos de leer antes de diseñar:

1. **El corte a los tres minutos y el aviso a los treinta segundos ya existen.**
   `CallConfig` trae `max_call_seconds`, `warn_at_seconds` y
   `resume_window_seconds`, con un validador que exige que el aviso quepa dentro de la
   llamada; `voice/loop.py` los aplica y emite `voice.notice.time_running_out`. U16 los
   construyó y el propio `CallConfig` explica por qué son tres y no cinco: **los dos
   carriles diarios son de U17**.
2. **La elección de la voz ya está escrita y es pura.** `quota.voice_mode(remaining,
   reserve)` decide principal o respaldo antes de abrir, y `covers_primary_voice`
   responde "no" cuando cualquiera de los dos datos está sin medir. Lo que falta es que
   producción la llame: `server/voice_routes.py` tiene `VoiceMode.PRIMARY` escrito a
   mano en cuatro sitios, y `voice/models.py` dice, con esas palabras, que "quien elige
   el modo es U17".
3. **Los dos códigos de rechazo ya están en la lista cerrada.**
   `VoiceOffCode.RATE_LIMITED_DAILY` y `RATE_LIMITED_SITE` existen con su frase del
   catálogo, y su comentario dice que hoy nadie los emite porque "servirlos sería
   prometer un límite que nada hace cumplir".

**Consecuencia:** US5.11 es cableado, no lógica nueva. Lo nuevo de esta unidad son los
dos carriles diarios, sus contadores, la ventana de retoma como regla, los avisos
públicos de la consola y la tabla de topes del proveedor.

---

## Las diez decisiones que tomé yo

| # | Qué | Por qué no es pregunta |
| --- | --- | --- |
| FD-U17-1 | **La decisión de los dos carriles es pura**, como los cinco controles del chat: recibe la configuración, lo que los contadores ya dicen y el reloj como argumentos, y devuelve admitir o **cuál** carril rechazó | Es la forma que `chat/limits.py` ya probó: deja medir el presupuesto sin depender de la máquina y cubrir los bordes de cada límite sin base de datos. Y devuelve el código, no la frase: la frase sale del catálogo en el punto único de salida |
| FD-U17-2 | ~~Los dos campos nuevos van a `CallConfig`~~ → **corregida el 2026-09-30**: los dos carriles son **del sitio** y ya vivían en `VoiceLimits` (`providers.yaml`). `CallConfig` se queda con tres campos | Me equivoqué leyendo el docstring de `CallConfig`, que dice que los carriles son de U17 pero no que sean de una aseguradora. «Quince llamadas del sitio» escrito en tres carpetas son cuarenta y cinco, y el cupo real se deriva cada día del presupuesto que queda. Lo encontró la tanda 1 |
| FD-U17-3 | **La ventana de retoma no crea un contador nuevo**: usa `resume_window_seconds`, que ya existe, y su regla es que una retoma dentro de la ventana **no** consume la llamada del día, pero **sí** cuenta contra las del sitio y contra el techo de gasto | AC5.12.2, literal. Y la asimetría es el punto: el carril del visitante protege la experiencia y el del sitio y el techo protegen el dinero, que es lo que AC5.12.6 dice con otras palabras |
| FD-U17-4 | **El techo de gasto no depende del carril por visitante**, y la consola dice "desde esta conexión" y no "por persona" | AC5.12.6, literal: un visitante cambia de navegador o de red, así que el carril por visitante no es un control de gasto y la consola no puede insinuar que lo sea |
| FD-U17-5 | **La elección de la voz se cablea, no se reescribe**: la raíz de composición pasa a llamar a `quota.voice_mode` y desaparecen los cuatro `VoiceMode.PRIMARY` escritos a mano | Reescribir una decisión que ya existe y es pura crearía un segundo sitio donde decidir lo mismo. Lo que falta es el cable, y el cable es de esta unidad |
| FD-U17-6 | **La voz no cambia por presupuesto a mitad de llamada**, nunca. Se decide una vez, antes de la primera frase, y la llamada entera se atiende con esa voz | AC5.11.2, y el propio `VoiceMode` lo dice: cambiar de voz a mitad suena a fallo aunque sea un ahorro. Un cambio a mitad solo ocurre cuando el proveedor falla, y eso es de U16 |
| FD-U17-7 | **La consola dice la disponibilidad antes de pedir el micrófono**, y cuando no hay voz dice por qué y ofrece el chat sin pedirlo | AC4.17.1. Pedir el micrófono para después decir que no hay voz es la peor pantalla posible, y `VoiceOffCode` existe justamente para no tener que hacerlo |
| FD-U17-8 | ~~La tabla de topes es un archivo versionado nuevo~~ → **corregida el 2026-09-30**: `ProviderCapConfig` en `prices.yaml` **ya era esa tabla**, con su fecha obligatoria. Esta unidad solo mejora el mensaje de una fila sin fecha | AC5.12.5 sigue en pie y la razón de la fecha también; lo que estaba mal era creer que no existía. Lo encontró la tanda 1, que no creó una segunda |
| FD-U17-9 | **La unidad no toca el corte ni el aviso**: los aplica U16 y ya están probados. Lo que añade es que el final por límite **derive** el caso con el motivo de la demostración y que la consola dé su enlace | AC5.12.1, y la frontera que `CallConfig` ya declara |
| FD-U17-10 | **La unidad se parte en dos tandas por dónde puede correr cada una**: las dos decisiones puras y los avisos de la consola a la nube; los contadores, el cableado y la tabla de topes aquí | Los contadores necesitan base; el cableado necesita la raíz de composición y sus pruebas de integración; la tabla de topes necesita que Miguel la llene |

## Lo que esta unidad no construye

- **La llamada, su transporte y su consola base**: son de U16.
- **El corte a los tres minutos y el aviso a los treinta segundos**: ya existen.
- **La decisión de la voz**: ya existe y es pura; aquí se cablea.
- **El techo de gasto y la alerta**: son de U5 y U15.
- **Configurar de verdad los topes en cada proveedor**: eso lo hace Miguel en la consola
  de cada proveedor, y la unidad aporta la tabla donde queda escrito y el simulacro que
  lo comprueba.
