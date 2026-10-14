# Entidades — U18 `voice-spanish`

**Esta unidad no añade ninguna entidad ni ninguna tabla.** No hay migración.

Lo que cambia es el significado de un campo que ya existe, y un campo nuevo en
configuración versionada. Los dos se escriben aquí porque un cambio de
significado sin decirlo es peor que una tabla nueva: la tabla se ve en el diff del
esquema y el significado no.

---

## `CallSession.language` deja de ser un dato de apertura

**Antes** (U16): el idioma con el que se abrió la llamada. Se escribía una vez y
no cambiaba nunca.

**Ahora**: el idioma **en el que se está hablando**. Cambia cuando la persona lo
pide (BR2.4) o cuando la detección automática lo decide (BR3.2).

| | |
| --- | --- |
| Quién lo escribe | El ciclo de la llamada, al resolver un cambio |
| Cuántas veces | Las que haga falta, mientras la llamada viva |
| Qué no toca | El caso, sus campos y su completitud (BR2.3) |

**Lo que se gana escribiéndolo y no llevándolo en memoria:** una llamada que se
corta y se retoma vuelve en el idioma en que se estaba hablando, no en el que
empezó. Con el idioma solo en memoria, retomar en español una llamada que había
pasado al inglés sería un cambio de idioma que nadie pidió.

---

## `CaseRecord.language` **no** cambia

Es el idioma en que el caso se abrió, y así se queda (BR5.1, `[bloquea]`).

Se escribe aquí porque la tentación es real y el argumento en contra no es obvio:
parece más "correcto" que el caso refleje el idioma actual. No lo es. Si el caso
cambiara de idioma con el último turno, quien quisiera mover su caso de cola solo
tendría que decir dos palabras en el otro idioma, y eso es RT-10 con otra ropa.

Lo que sí queda en los dos idiomas es la **transcripción**, turno por turno, que
es donde la ajustadora ve lo que de verdad pasó.

---

## `VoiceConfig` gana un campo, apagado por omisión

```
auto_language_detection: bool = False
```

Aditivo a C-25, con la misma forma que los demás campos que U15 y U16 añadieron:
llega con su valor por omisión y **sin subir `config_version`**, para que una
aseguradora que todavía no lo declara siga cargando igual.

**Apagado por omisión, y la razón es de alcance**: US1.32 es la única historia
Should de esta unidad y la última en la regla de corte del PRD. Si se corta, lo
que queda es la conducta con la detección apagada, que AC1.31.5 ya describe y que
esta unidad construye de todos modos.

---

## Lo que no hay, y por qué

- **Ninguna tabla de idioma por turno.** La transcripción ya guarda el idioma de
  cada turno (U4): una segunda copia se desincroniza y la que alguien olvida
  borrar es siempre la segunda.
- **Ningún contador de turnos en el otro idioma.** Los dos turnos seguidos que
  BR3.2 pide se leen del estado del turno anterior, como todo lo demás en esta
  llamada: un contador propio se desincroniza al reanudar tras un corte, y el
  punto de control no.
- **Ninguna entidad de "petición de cambio".** Una petición no es un hecho que
  guardar: es una frase que se reconoce y se aplica en el acto.

## Sources

- `functional-design-questions.md` — D4, D7
- `rules.md` — BR2.3, BR3.1, BR3.2, BR5.1
- `../../u16-voice-call/functional-design/entities.md` — `CallSession`, que aquí no crece

## Assumptions & Open Questions

None.
