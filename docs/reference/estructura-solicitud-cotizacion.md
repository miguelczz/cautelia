# Estructura de la solicitud de cotización de auto personal — referencia para el esquema sintético

Hermano de `estructura-poliza-iso-pap.md`, y con la misma frontera: aquí se registra
**la estructura** de una solicitud de cotización, con nombres de campo propios. No hay
texto de terceros, y **no se consultó ni se guardó ningún specimen**.

## De dónde sale la estructura

AC6.1.2 de US6.1 pide que los campos estén "inspirados en la estructura del formulario
ACORD 90, sin su texto", y nombra los cuatro bloques: **conductor, vehículo, uso e
historial**. Esos cuatro bloques son el reparto que usa cualquier solicitud de auto
personal, y son lo único que se imita: el orden de las preguntas y qué va en cada
bloque. Los nombres de campo, los valores de los conjuntos cerrados y todo el texto que
lee una persona son propios y viven en el catálogo de textos por idioma.

**Por qué esto y no una copia de la estructura del formulario.** Los formularios de
ACORD son material con derechos, igual que los de ISO. La regla del proyecto prohíbe
que su texto, sus formularios o sus specímenes entren al repositorio o al corpus; y la
parte que sí se puede imitar —cómo se reparte una solicitud en bloques— no hace falta
sacarla de un specimen, porque la historia ya la nombra. Así que no se consultó
ninguno. Si algún día hace falta más detalle, se aplica lo mismo que con la póliza ISO:
el specimen se lee en el scratchpad de la sesión y no se versiona nada de él.

## Los cuatro bloques

Cada campo lleva el nombre con el que vive en el esquema del caso, bajo el tipo de
registro `quote_request`.

### 1. Conductor

| Campo | Tipo | Notas |
| --- | --- | --- |
| `driver_name` | texto | Dato personal: se redacta en cada punto de salida como cualquier nombre |
| `driver_birth_date` | fecha | Dato personal |
| `license_years` | entero | Años con licencia vigente. **Lo leen las reglas de elegibilidad** |
| `license_jurisdiction` | texto corto | El estado ficticio de Corvane, o los de las aseguradoras sembradas |

### 2. Vehículo

| Campo | Tipo | Notas |
| --- | --- | --- |
| `vehicle_year` | entero | El año del modelo, tal como lo dice quien pregunta |
| `vehicle_make` | texto corto | Marca |
| `vehicle_model` | texto corto | Modelo |
| `vin` | texto | Dato personal: ya tiene su reconocedor propio en la redacción |
| `salvage_title` | booleano | Título de salvamento. **Lo leen las reglas de elegibilidad** |
| `vehicle_age_years` | entero | **Derivado**, no preguntado: lo calcula la captura desde `vehicle_year` y el reloj. **Lo leen las reglas de elegibilidad** |

**Por qué la antigüedad es un campo y no una comparación contra el año.** Una regla que
dijera `vehicle_year <= 2001` envejece sola: el año que viene significa otra cosa y
nadie se entera. El campo derivado se calcula en **un solo sitio**, con el reloj que ya
inyecta la captura, y la regla compara contra una antigüedad, que no envejece.

### 3. Uso

| Campo | Tipo | Notas |
| --- | --- | --- |
| `use_type` | conjunto cerrado | `personal`, `commuting`, `commercial`. **Lo leen las reglas de elegibilidad** |
| `annual_mileage_band` | conjunto cerrado | Tramos, no un número: nadie sabe su kilometraje exacto |
| `garaging_jurisdiction` | texto corto | Dónde duerme el vehículo |

### 4. Historial

| Campo | Tipo | Notas |
| --- | --- | --- |
| `at_fault_losses_3y` | entero | Siniestros con culpa en tres años. **Lo leen las reglas de elegibilidad** |
| `claims_3y` | entero | Siniestros reportados en tres años, con o sin culpa |
| `prior_coverage_active` | booleano | Si tiene cobertura vigente hoy |
| `lapse_months` | entero | Meses sin cobertura, cuando no tiene |

## Cómo se usa en Untangle

- Los cuatro bloques son **bloques de captura** del nodo `intake`, con su confirmación
  por bloque, igual que los siete que ya existen para un siniestro. El grafo **no gana
  nodos** (FR13.1).
- Los cinco campos marcados son los que entran al vocabulario cerrado del motor de
  reglas. **Ninguno existe sin el bloque de captura que lo escribe**: es la regla que
  evita el hueco que hoy tienen seis campos del triage de siniestros, declarados en el
  vocabulario y que nadie escribe.
- Los datos personales de la solicitud —nombre, fecha de nacimiento, VIN— se redactan
  en cada punto de salida por los reconocedores que ya existen. La solicitud no añade
  ninguno.
- Los valores de los conjuntos cerrados se escriben como enum en inglés, y la etiqueta
  que ve una persona se resuelve por el catálogo de textos, nunca imprimiendo el enum.
