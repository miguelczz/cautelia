"""u10_compliance_0002_tenant_fks: las referencias al caso y al turno llevan la aseguradora.

Revision: u10_compliance_0002_tenant_fks
Revision anterior: u10_compliance_0001_tables

## El hueco que cierra (compuerta dura, decision 4 del conductor)

Las comprobaciones de llave foranea de PostgreSQL **no pasan por las politicas de
fila**: el motor las ejecuta por encima de ellas. Con la llave de una sola
columna --`case_id` apunta a `case_record.case_id`--, una fila de la aseguradora B
podia apuntar a un caso de la aseguradora A: la politica de B le deja escribir su
propia fila, y la llave encontraba el caso de A sin preguntar de quien era. El
aislamiento por fila seguia intacto --B no ve el caso de A-- pero la base aceptaba
una referencia cruzada entre aseguradoras, y el borrado en cascada de A se
llevaba la fila de B.

## Como lo cierra

Cada referencia de una tabla aislada hacia otra tabla aislada lleva **tambien la
aseguradora**: `(tenant_id, case_id)` apunta a `(tenant_id, case_id)` del caso, y
`(tenant_id, turn_id)` a `(tenant_id, turn_id)` del turno. Una fila de B que
nombre un caso de A ya no encuentra a quien apuntar, porque el par no existe, y
la base la rechaza nombrando la llave.

Para poder apuntar a un par, el par tiene que ser unico: el caso gana
`case_record_aseguradora_y_caso` y el turno `case_transcript_turn_aseguradora_y_turno`.
No cambia nada de lo que ya era unico --`case_id` y `turn_id` siguen siendo llave
primaria--; solo dice en la base que el par tambien lo es.

Diez llaves, en tres unidades, **con el mismo nombre que tenian**:

- U4: las cuatro hijas del caso (campos, partes, turnos e historial).
- U5: el resumen de traza.
- U10: las tres tablas de cumplimiento, y las dos que ademas apuntan a un turno.

Mismo nombre y mismo borrado en cascada: quien lea el catalogo ve la misma llave,
ahora con una columna mas. Que ninguna vuelva a quedarse sin la aseguradora lo
comprueba `rls:check`, que falla ante cualquier llave foranea entre dos tablas
aisladas que no la lleve.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "u10_compliance_0002_tenant_fks"
down_revision: str | None = "u10_compliance_0001_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Las llaves que apuntan al caso: nombre y tabla. Todas borran en cascada.
LLAVES_AL_CASO: tuple[tuple[str, str], ...] = (
    ("case_field_del_caso", "case_field"),
    ("case_party_del_caso", "case_party"),
    ("case_transcript_turn_del_caso", "case_transcript_turn"),
    ("case_change_del_caso", "case_change"),
    ("trace_summary_del_caso", "trace_summary"),
    ("disclosure_record_del_caso", "disclosure_record"),
    ("guard_intervention_del_caso", "guard_intervention"),
    ("compliance_review_del_caso", "compliance_review"),
)

#: Las llaves que apuntan a un turno: nombre, tabla y columna del turno.
LLAVES_AL_TURNO: tuple[tuple[str, str, str], ...] = (
    ("guard_intervention_de_su_turno", "guard_intervention", "turn_id"),
    ("compliance_review_hasta_su_turno", "compliance_review", "reviewed_through_turn"),
)

CASO_UNICO = "case_record_aseguradora_y_caso"
TURNO_UNICO = "case_transcript_turn_aseguradora_y_turno"


def upgrade() -> None:
    # Primero los pares unicos: una llave solo puede apuntar a columnas unicas.
    op.create_unique_constraint(CASO_UNICO, "case_record", ["tenant_id", "case_id"])
    op.create_unique_constraint(TURNO_UNICO, "case_transcript_turn", ["tenant_id", "turn_id"])

    for nombre, tabla in LLAVES_AL_CASO:
        op.drop_constraint(nombre, tabla, type_="foreignkey")
        op.create_foreign_key(
            nombre,
            tabla,
            "case_record",
            ["tenant_id", "case_id"],
            ["tenant_id", "case_id"],
            ondelete="CASCADE",
        )

    for nombre, tabla, columna in LLAVES_AL_TURNO:
        op.drop_constraint(nombre, tabla, type_="foreignkey")
        op.create_foreign_key(
            nombre,
            tabla,
            "case_transcript_turn",
            ["tenant_id", columna],
            ["tenant_id", "turn_id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    """Vuelve a las llaves de una columna. Se prueba en cada corrida, no se supone.

    `mise run migrate:check` sube, baja y vuelve a subir contra una base virgen.
    Bajar reabre el hueco que esta revision cierra: es lo que la revision anterior
    decia, y deshacerla tiene que dejar la base exactamente asi.
    """
    for nombre, tabla, columna in LLAVES_AL_TURNO:
        op.drop_constraint(nombre, tabla, type_="foreignkey")
        op.create_foreign_key(
            nombre,
            tabla,
            "case_transcript_turn",
            [columna],
            ["turn_id"],
            ondelete="CASCADE",
        )

    for nombre, tabla in LLAVES_AL_CASO:
        op.drop_constraint(nombre, tabla, type_="foreignkey")
        op.create_foreign_key(
            nombre,
            tabla,
            "case_record",
            ["case_id"],
            ["case_id"],
            ondelete="CASCADE",
        )

    op.drop_constraint(TURNO_UNICO, "case_transcript_turn", type_="unique")
    op.drop_constraint(CASO_UNICO, "case_record", type_="unique")
