# Entidades — U19 `quote`

Esta unidad **no crea ninguna tabla**. Añade un tipo de registro que ya está declarado,
sus campos, un conjunto de reglas, un valor de enum y una fila de permisos. Todo lo
demás lo reusa.

## Lo que ya existe y solo se llena

| Qué | Dónde | Estado hoy |
| --- | --- | --- |
| `RecordType.QUOTE_REQUEST` | `case_record/models.py` | Declarado, **sin campos a propósito**: el comentario de `case_record/fields.py` dice que está esperando a esta unidad |
| `quote_enabled` | `tenancy/models.py` y la configuración de las tres aseguradoras | Existe, en `false` en las tres. Sunmeadow pasa a `true` (AC6.1.2) |
| El vocabulario de campos del motor | `rules/fields.py` | Cerrado, con seis campos de triage. Entran cinco de elegibilidad |
| La guardia de salida con sus patrones de importe | `app/config/compliance/{es,en}/guard.yaml` | Cuatro patrones por idioma. **No se añade ninguno** |
| El puerto de reanudación | `inbox/decision.py` | Enchufado por la raíz de composición |

## `QuoteRequest` — los cuatro bloques de captura

Los campos están en `docs/reference/estructura-solicitud-cotizacion.md`, con su tipo y
su bloque. Aquí solo lo que el diseño decide sobre ellos:

- **Cuatro bloques**, y cada uno se confirma antes de pasar al siguiente (BR1.2).
- Los datos personales de la solicitud —nombre, fecha de nacimiento, VIN— usan los
  reconocedores de redacción que **ya existen**. La solicitud no añade ninguno.
- `vehicle_age_years` es **derivado** y se calcula en un solo sitio (BR1.4).
- Los conjuntos cerrados (`use_type`, `annual_mileage_band`) se escriben como enum en
  inglés, y la etiqueta que ve una persona sale del catálogo.

## `EligibilityOutcome` — lo que sale de las reglas

| Campo | Qué es |
| --- | --- |
| `outcome` | `eligible`, `not_eligible` o `referred`. Conjunto cerrado de tres (BR2.1) |
| `band` | `standard_risk`, `elevated_risk`, `pending_review` o `outside_appetite` (BR2.2) |
| `deciding_rules` | Los identificadores de las reglas que la decidieron, **para la traza y la bandeja**, nunca para el prospecto |
| `explanation_key` | La clave del catálogo con la razón en lenguaje llano (BR2.3) |

**`band` y `outcome` no son el mismo dato en dos formas.** `outcome` dice qué pasa con
la solicitud; `band` dice dónde queda el riesgo. Una derivación tiene `outcome =
referred` y `band = pending_review`, y esa combinación es la única en la que la banda
dice "no se sabe": el tipo la exige y rechaza una derivación con banda afirmada.

**`deciding_rules` no sale hacia el prospecto.** Va a la traza y a la vista del caso en
la bandeja, donde el suscriptor necesita ver qué decidió. Quien pregunta lee la
explicación (BR2.3).

## El rol de suscriptor

- `Role.UNDERWRITER`, un valor más del enum de dos que ya existe.
- Una acción nueva en la tabla de permisos: decidir una solicitud de cotización. Nada
  de esto es una rama en el código, que es lo que `tenancy/models.py` ya pide.
- **Ninguna credencial de suscriptor se publica**, igual que las otras dos: son para
  Miguel, el despliegue local y las pruebas.

## Lo que esta unidad no añade

- **Ninguna tabla.** La solicitud es un caso con su tipo de registro, en las tablas que
  ya existen y con la misma política de fila por aseguradora.
- **Ningún reconocedor de datos personales.**
- **Ningún patrón nuevo de la guardia de salida.**
- **Ningún nodo del grafo** (BR1.1).

## Sources

- `rules.md` — BR1.1 a BR4.3
- `docs/reference/estructura-solicitud-cotizacion.md` — los cuatro bloques y sus campos
- El código: `case_record/models.py`, `case_record/fields.py`, `rules/fields.py`,
  `tenancy/models.py`, `inbox/decision.py`, `app/config/compliance/{es,en}/guard.yaml`

## Assumptions & Open Questions

None.
