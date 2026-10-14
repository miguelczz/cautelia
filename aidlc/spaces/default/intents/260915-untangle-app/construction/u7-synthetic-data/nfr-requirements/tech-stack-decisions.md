# Decisiones de herramientas — U7 `synthetic-data`

**Una dependencia nueva, solo de desarrollo:** `pypdf`, para extraer el texto
de los specimens en PDF al sacar las huellas.
- **Qué hace:** lee el texto de un PDF.
- **Por qué no la biblioteca estándar:** Python no trae lector de PDF.
- **Licencia:** BSD-3-Clause.
- **Alcance:** va en el grupo de desarrollo porque solo la usa un comando a
  mano, nunca el aplicativo servido.

Todo lo demás ya está en el manifiesto: PyYAML para los textos fuente, Pydantic
para los esquemas y la fábrica de proveedores de U5 para la redacción.

| Pieza | Con qué | Por qué |
| --- | --- | --- |
| Azar sembrado | Elecciones derivadas de SHA-256 sobre semilla, ruta de salida y contador, sin el generador aleatorio de la biblioteca estándar | Un hash no cambia entre versiones de Python. La documentación de `random` solo garantiza la secuencia de `random()`; el resto de sus métodos puede cambiar de algoritmo entre versiones, y eso rompería los bytes idénticos (BR1.1, BR1.2) |
| Forma canónica | JSON con claves ordenadas, UTF-8 sin escapar, sangría de 2, salto final LF | Dos corridas iguales escriben los mismos bytes en cualquier máquina |
| Textos fuente | YAML en `app/data/sources/`, carpeta nueva que se crea con la generación de código | Legible para revisar a mano; PyYAML ya está en el proyecto |
| Esquemas de la salida | Modelos Pydantic, con JSON Schema generado a `app/contracts/schemas/` (C-28) | Mismo camino que los demás esquemas; `contracts:check` detecta la deriva |
| Redacción | Fábrica de U5, uso `operations`, modelo anclado en `app/config/providers/providers.yaml` | ADR-016 y Q1; una sola forma de llamar al modelo |
| Huellas | SHA-256 de secuencias de ocho palabras normalizadas | Q3; umbral cero |

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| TECH-U7.1 | Archivos de `app/data/` que difieren de una regeneración limpia con la misma semilla (AC5.3.1) | **Exactamente 0**, en cada entrega | Tarea nueva `mise run synthetic:check`, invocada por `scripts/verify.sh` |
| TECH-U7.2 | Archivos de `app/data/` fuera del manifiesto o con hash distinto | **Exactamente 0** | `mise run schema:check` |
| TECH-U7.3 | Combinaciones de estado, aseguradora e idioma sin caso sembrado, y resoluciones sin caso cerrado (AC5.6.1) | **Exactamente 0** | Tarea nueva `mise run test:u7` |
| TECH-U7.4 | Duración de `synthetic:check` | **Publicada, sin umbral propio**: la corrida entera tiene el suyo (NFR17, dueña U21) | Tarea nueva `mise run synthetic:check` |

## Sources

- `../functional-design/functional-spec.md` — FD-U7-1 a FD-U7-6.
- `../functional-design/rules.md` — BR1.1, BR1.2, BR2.1 y BR5.1.
- `../../../inception/domain-design/decisions.md` — ADR-016.
- `../../../inception/contract-design/contract-summary.md` — C-26 y C-28.
- `aidlc/spaces/default/codekb/untangle/technology-stack.md` — stack del
  aplicativo.

## Assumptions & Open Questions

- Ninguna.
