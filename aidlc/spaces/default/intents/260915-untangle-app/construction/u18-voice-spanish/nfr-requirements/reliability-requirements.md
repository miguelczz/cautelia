# Fiabilidad — U18 `voice-spanish`

| Identificador | Qué exige | Cómo se comprueba |
| --- | --- | --- |
| REL-U18.1 | Un cambio de idioma no pierde ningún bloque confirmado (BR2.3, `[bloquea]`) | Prueba con dos bloques confirmados antes del cambio |
| REL-U18.2 | Una llamada cortada se retoma en el idioma en que se estaba hablando | Prueba de corte y retoma después de un cambio |
| REL-U18.3 | El detector que falla no tumba el turno: se conserva el idioma actual | Prueba con el detector levantando |

## REL-U18.2 es la razón de que el idioma se escriba

Con el idioma solo en memoria, retomar una llamada que había pasado al inglés la
devolvería al español: un cambio de idioma que nadie pidió, justo cuando la persona
vuelve de un corte y menos ganas tiene de repetir nada.

## REL-U18.3 falla del lado que conserva

El detector carga modelos y puede fallar. Cuando falla, la llamada **sigue en el
idioma que tenía**: es el mismo lado del que ya falla el detector cuando no hay
señal suficiente, y el que no sorprende a nadie. Lo contrario --tumbar el turno--
convertiría un fallo del detector en una llamada rota.

## Sources

- `../functional-design/rules.md` — BR2.3, BR3.3
- `../functional-design/entities.md` — por qué el idioma se escribe

## Assumptions & Open Questions

None.
