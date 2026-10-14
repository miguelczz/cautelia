"""El vocabulario cerrado de campos que el motor de reglas puede leer (BR1.2).

`rules` esta por debajo de `case_record` en el contrato de capas (`.importlinter`)
y no puede importar su esquema de siete bloques de captura (`fields.yaml`): son
demasiado grandes para condicionar sobre ellos directamente -- "hay heridos" no
es lo mismo que "el bloque de heridos se capturo". El motor declara su propio
vocabulario, mas fino, y `required_inputs()` es lo que le dice a la captura
(U11) que tiene que escribir (C-19).

Cerrado y versionado aqui, en un solo lugar: una regla que nombre un campo fuera
de esta lista no carga (BR1.2). Anadir un campo es anadir una entrada aqui.
"""

from __future__ import annotations

from typing import Final

#: El monto estimado del siniestro, en la cifra interna del motor (miles de pesos). Es el
#: unico campo cuyos umbrales la bandeja le muestra a quien anota (`amount_steps`).
CLAIM_AMOUNT: Final = "claim_amount"

#: Los seis campos de los perfiles de triage de las tres aseguradoras (CG-U9-1):
#: heridos, terceros con datos pendientes, monto, cobertura, sospecha de fraude y
#: conductor no listado. La regla de la agencia (BR2.6) no lee ninguno.
TRIAGE_FIELDS: frozenset[str] = frozenset(
    {
        "injuries_present",
        "other_parties_data_pending",
        "claim_amount",
        "coverage_disputed",
        "fraud_suspected",
        "unlisted_driver",
    }
)

#: Los cinco campos que leen las reglas de elegibilidad de una cotizacion (U19,
#: FD-U19-3). **Cada uno tiene un bloque de captura que lo escribe**, y una
#: prueba lo comprueba contra el esquema del caso: un campo declarado aqui que
#: nadie escribe no falla, simplemente no dispara, y la regla que lo nombra queda
#: muerta sin que nada se ponga rojo (BR1.3). Es el hueco que tienen hoy los seis
#: de arriba, y por eso este conjunto se declara aparte.
#:
#: `vehicle_age_years` es el unico derivado: lo calcula la captura desde el anio
#: del modelo y el reloj, en un solo sitio (BR1.4).
ELIGIBILITY_FIELDS: frozenset[str] = frozenset(
    {
        "use_type",
        "salvage_title",
        "at_fault_losses_3y",
        "license_years",
        "vehicle_age_years",
    }
)

#: El vocabulario cerrado entero. Un conjunto de reglas solo puede leer los campos
#: de su propia familia: el de triage los de triage y el de elegibilidad los de
#: elegibilidad, y cada cargador lo comprueba.
KNOWN_FIELDS: frozenset[str] = TRIAGE_FIELDS | ELIGIBILITY_FIELDS

#: Lo que puede valer un campo. Sin tipos abiertos: una regla que comparara
#: contra un objeto arbitrario no se podria versionar ni probar con `tests`.
type RuleValue = bool | int | float | str
