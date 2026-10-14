# Diseño funcional — U20 `demo-operations`

Dos operaciones: **dar de alta una aseguradora con una carpeta y un comando**, y
**borrar cada noche lo que dejaron los visitantes** llamando al contrato de borrado de
cada dueño, conservando el registro de gasto y dejando escrito qué pasó.

## Sources

- `../../../inception/user-stories/stories.md` — US5.1, US5.15
- `functional-design-questions.md` — la pregunta y las nueve decisiones
- El código: `server/composition.py` (los nueve purgadores), `tenancy/models.py`
  (`VisitorDataPurger`), `mise.toml` (`corpus:ingest`)

## Assumptions & Open Questions

None.

---

## Flujo 1 — Aprovisionar una aseguradora (US5.1)

1. **Primero se valida la carpeta entera**: nombre, idioma, voz, reglas, políticas,
   corpus, póliza de ejemplo y personas. Si falta algo, el comando **falla antes de
   crear nada** y nombra el archivo y el campo.
2. Con la carpeta completa: se crea la aseguradora, se invoca `corpus:ingest` —la tarea
   que ya existe— y se siembra un caso en cada estado.
3. Correrlo otra vez con la misma configuración **no duplica nada** y deja el mismo
   estado.
4. La aseguradora nueva pasa la batería de humo: chat, pregunta de cobertura, bandeja y
   aislamiento.

**El commit que agrega una aseguradora no cambia ningún archivo de código** (AC5.1.1), y
eso se comprueba: ningún identificador de aseguradora aparece fuera del cargador de
configuración y de las fixtures, que es el chequeo que ya corre en cada entrega.

**Validar antes de crear no es cortesía.** Una aseguradora a medias no la borra nada y
no la completa nada: se queda existiendo mal, y la siguiente persona que mire creerá que
el aprovisionamiento funciona.

---

## Flujo 2 — El reinicio nocturno (US5.15)

1. A la hora configurada, el reinicio llama a **los nueve purgadores registrados**, en
   el orden del registro escrito a mano de la raíz de composición. **No borra ninguna
   tabla por su cuenta.**
2. Se borra lo que cada dueño declara como dato de visitante: casos con sus puntos de
   control, transcripciones, conversaciones, enlaces, llamadas y trazas, **también en el
   backend de trazas**.
3. **El registro de gasto sobrevive**, y no porque esta unidad lo exceptúe: cada
   purgador ya declara qué conserva. El de U5 borra los contadores de visitante y de
   sesión y conserva el del sitio, la ventana de presupuesto y el libro mayor entero.
4. La bandeja pública queda sin casos de visitantes.
5. **Ningún número de caso y ningún enlace firmado emitido antes se repite después.**
6. Cada corrida deja un `ResetRun`: qué purgadores corrieron, qué borró cada uno, cuánto
   tardó, y si falló alguno.

**El audio no se borra porque nunca se guardó** (AC5.15.2). Comprobarlo antes y después
del reinicio es la forma de demostrar que no hay un archivo esperando a que alguien lo
encuentre.

---

## Flujo 3 — Una conversación abierta a la hora del reinicio (AC5.15.3)

1. La conversación recibe **el aviso del catálogo** de que la demostración se reinició.
2. Su mensaje siguiente **abre un caso nuevo, sin error**: la conversación no queda
   apuntando a un caso que ya no existe.

---

## Flujo 4 — Cuando el reinicio falla (AC5.15.5)

1. Sale una **alerta** y se **reintenta**.
2. Si no se completa antes de **24 horas** desde el último reinicio exitoso, el chat y la
   voz públicos **dejan de aceptar casos nuevos** con el mensaje del catálogo.
3. **Lo que ya está abierto termina normalmente** (respuesta Q1): se dejan de aceptar
   casos nuevos, y quien está a mitad de un reporte lo termina. El compromiso que eso
   acepta —los datos de esa conversación se quedan una noche más— es el precio de que
   nadie pierda trabajo por un fallo de operación que no es suyo, y lo que mantiene la
   ventana acotada es que la alerta ya salió y el reintento sigue corriendo.

**El reloj que cuenta es el del último reinicio exitoso, no el del último intento.** Tres
intentos fallidos seguidos no reinician el contador: es justo el caso en el que la
retención dejó de estar acotada.

---

## Flujo 5 — Lo que esta operación no puede hacer

- **No borra ninguna tabla directamente**: llama al contrato de su dueño.
- **No conserva nada por su cuenta**: lo que sobrevive lo declara cada purgador.
- **No crea una aseguradora a medias.**
- **No reutiliza un número de caso ni un enlace firmado.**
- **No deja una corrida sin registro**, ni un fallo sin alerta.

---

## Lo que esta unidad no construye

- **El borrado de cada tabla**: los nueve purgadores ya existen, uno por dueño.
- **El disparador nocturno**: es del intent `infra`.
- **La ingesta del corpus**: existe como tarea y aquí se invoca.

## Resumen de reglas (vista derivada)

Las reglas están en `rules.md`. Dos llevan `[bloquea]`: que tras el reinicio no quede
ningún dato de visitante —tampoco en el backend de trazas— y que el registro de gasto
sobreviva.

## Metas medibles

| Meta | Valor | De dónde |
| --- | --- | --- |
| Datos de visitante después del reinicio | **cero**, tampoco en trazas | AC5.15.1, por hito y en el checklist |
| Filas del registro de gasto perdidas | **cero** | AC5.15.1 |
| Corridas del reinicio sin su registro | **cero** | AC5.15.5 |
| Horas sin reinicio exitoso antes de cerrar casos nuevos | 24 | AC5.15.5 |
