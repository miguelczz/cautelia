# Escalabilidad — U21 `eval-gates`

U21 no sirve tráfico: corre en la máquina de quien construye y en GitHub
Actions. Lo único que crece es **el número de casos**, y ahí sí hay un límite
que importa, porque la corrida tiene un presupuesto de diez minutos.

| Qué crece | Hasta dónde | Cómo se sostiene |
| --- | --- | --- |
| Casos de los golden sets | DS-2 60, DS-3 40, DS-6 v0 10 por idioma | Cuando la corrida completa no cabe en el presupuesto o en el plan gratuito, la compuerta corre el **subconjunto declarado** y la corrida completa pasa a ser obligatoria por hito y antes de publicar cualquier línea base |
| Líneas base acumuladas | Una por hito | Archivos versionados; la vigente se nombra con un puntero, las demás quedan como historia |
| Etiquetas de DS-7 | 40 transcripciones, 20 por idioma | Tamaño fijo por historia; si creciera, el intervalo de confianza se estrecha y la calibración mejora sola |

**Lo que no se hace nunca:** apagar la compuerta porque la corrida no cabe. Se
corre el subconjunto declarado, que es reproducible y está versionado.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| SCA-U21.1 | Corridas de la compuerta que se saltan por no caber en el presupuesto | **Exactamente 0** | Tarea nueva `mise run test:u21` |

## Sources

- `../functional-design/rules.md` — BR5.1.
- `aidlc/spaces/default/memory/team.md` — presupuesto de la corrida.

## Assumptions & Open Questions

- **[assumption]** El subconjunto declarado hoy es `smoke`; cuál se usa cuando la
  corrida completa deje de caber lo fija esta unidad en su plan de código.
