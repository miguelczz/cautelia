"""u14_inbox_0002_triage_note: lo que el ajustador anota para las reglas de triage.

Revision: u14_inbox_0002_triage_note
Revision anterior: u4_case_0003_continues_case

## Por que existe

De los seis campos que leen las reglas de triage, tres no los produce la conversacion
ni un modelo: el monto estimado, la cobertura disputada y la sospecha de fraude los
anota un ajustador desde la bandeja (decision del 2026-10-03). Hasta hoy no tenian
donde quedarse, asi que las reglas que mandan un caso a un ajustador por dinero, por
cobertura o por fraude nunca disparaban.

## Una tabla propia y no filas de `case_field`

`case_field` es el esquema del caso -- lo que la persona cuenta--, cuenta para la
completitud y va sellado con el cifrador. Estas tres anotaciones no son nada de eso:
las pone quien revisa, no cuentan como dato pendiente del asegurado, y meterlas
alli habria movido el "3 de 7" de la cola cada vez que un ajustador anotara algo.

## Tres columnas que admiten nulo, y el nulo significa algo

`claim_amount`, `coverage_disputed` y `fraud_suspected` llevan los nombres del
vocabulario cerrado del motor de reglas (`rules/fields.py`), para que la
correspondencia sea un grep y no una tabla. **Nulo es "sin anotar"**, que no es lo
mismo que "no": una regla que lee un campo ausente no dispara (BR2.1 de U9), y una
que lee `false` afirma que alguien lo comprobo. La pantalla tiene que poder dejar un
dato sin anotar y volver a dejarlo sin anotar, y una columna `NOT NULL DEFAULT false`
lo habria vuelto imposible.

Una fila por caso, no un historial: lo que vale es lo ultimo. El historial de quien
cambio que y cuando vive en `case_change`, que ya es de solo anexar.

## Llave compuesta desde el primer commit y borrado con el caso

La llave hacia el caso es `(tenant_id, case_id)` y cae en cascada, igual que
`rule_evaluation` y `quote_eligibility` (UG-3, la leccion de
`u10_compliance_0002_tenant_fks`): las llaves foraneas de PostgreSQL no pasan por las
politicas de fila, asi que una llave de una sola columna dejaria a una aseguradora
anotar el caso de otra. Lleva la marca de dato de visitante porque cuelga del caso de
una persona que uso la demostracion y el reinicio nocturno tiene que declararla.

## Dos restricciones que se amplian

1. **`case_change_clase_valida`** y **`case_change_campo_con_su_clave`**: una sexta
   clase de entrada, `triage_noted`, que nombra el dato anotado. Anotarla como
   `field_set` diria "este campo del esquema se fijo a este valor", que no es lo que
   paso (mismo argumento que `u11_intake_0002_alt_version`).
2. **`decision_receipt_operacion_valida`**: una tercera escritura idempotente,
   `triage_note`. La clave de idempotencia es por operacion, asi que no choca con las
   de decidir ni con las de corregir un campo.

## Reversible

`downgrade` vuelve a poner las tres restricciones con el texto exacto de las
revisiones anteriores y borra la tabla. Baja **solo si no queda ninguna entrada
`triage_noted` en el historial**: el historial es de solo anexar (SEC-U4.11) y no se
borra para poder bajar. Los recibos `triage_note` si se borran: son huellas de
peticiones, no historial.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u14_inbox_0002_triage_note"
down_revision: str | None = "u4_case_0003_continues_case"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: La marca de dato de visitante (C-11), igual que en U4, U9 y U19.
MARCA = "visitor-data"

ASEGURADORA = sa.String(31)
IDENTIFICADOR = sa.String(64)

TABLA = "case_triage_note"

#: Las restricciones que se amplian, con su texto de antes y de ahora escrito una
#: vez para que `upgrade` y `downgrade` no puedan divergir. Las "de antes" son,
#: caracter a caracter, las que dejo `u11_intake_0002_alt_version` y
#: `u14_inbox_0001_tables`.
CLASE = "case_change_clase_valida"
CLASE_ANTES = (
    "change_kind IN ('field_set', 'field_version_alternate', 'transition_applied', "
    "'transition_rejected', 'close_rejected')"
)
CLASE_AHORA = (
    "change_kind IN ('field_set', 'field_version_alternate', 'triage_noted', "
    "'transition_applied', 'transition_rejected', 'close_rejected')"
)
CAMPO = "case_change_campo_con_su_clave"
CAMPO_ANTES = "change_kind NOT IN ('field_set', 'field_version_alternate') OR field_key IS NOT NULL"
CAMPO_AHORA = (
    "change_kind NOT IN ('field_set', 'field_version_alternate', 'triage_noted') "
    "OR field_key IS NOT NULL"
)
OPERACION = "decision_receipt_operacion_valida"
OPERACION_ANTES = "operation IN ('decision', 'field_correction')"
OPERACION_AHORA = "operation IN ('decision', 'field_correction', 'triage_note')"

_POLITICA = """
    CREATE POLICY tenant_isolation ON {tabla}
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
"""


def _aislar(tabla: str, descripcion: str) -> None:
    op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY")
    op.execute(_POLITICA.format(tabla=tabla))
    op.execute(f"COMMENT ON TABLE {tabla} IS '{MARCA}: {descripcion} (C-11)'")


def _cambiar_restriccion(tabla: str, nombre: str, condicion: str) -> None:
    op.drop_constraint(nombre, tabla, type_="check")
    op.create_check_constraint(nombre, tabla, condicion)


def upgrade() -> None:
    op.create_table(
        TABLA,
        sa.Column("tenant_id", ASEGURADORA, primary_key=True),
        sa.Column("case_id", IDENTIFICADOR, primary_key=True),
        # La cifra interna del motor, que el proyecto muestra en pesos multiplicandola
        # por mil. Nulo es "sin anotar".
        sa.Column("claim_amount", sa.BigInteger(), nullable=True),
        sa.Column("coverage_disputed", sa.Boolean(), nullable=True),
        sa.Column("fraud_suspected", sa.Boolean(), nullable=True),
        # El identificador de la persona de la tabla versionada, no el nombre de nadie.
        sa.Column("noted_by", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["case_record.tenant_id", "case_record.case_id"],
            name="case_triage_note_del_caso",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "claim_amount IS NULL OR claim_amount >= 0",
            name="case_triage_note_monto_no_negativo",
        ),
        sa.CheckConstraint("noted_by <> ''", name="case_triage_note_dice_quien"),
    )
    _aislar(TABLA, "lo que el ajustador anota para las reglas de triage del caso de un visitante")

    _cambiar_restriccion("case_change", CLASE, CLASE_AHORA)
    _cambiar_restriccion("case_change", CAMPO, CAMPO_AHORA)
    _cambiar_restriccion("decision_receipt", OPERACION, OPERACION_AHORA)


def downgrade() -> None:
    """El orden inverso, y se niega a borrar historial para poder bajar.

    `mise run migrate:check` sube, baja y vuelve a subir contra una base virgen.
    """
    conexion = op.get_bind()
    quedan = conexion.execute(
        sa.text("SELECT count(*) FROM case_change WHERE change_kind = 'triage_noted'")
    ).scalar_one()
    if quedan:
        msg = (
            f"quedan {quedan} entrada(s) 'triage_noted' en el historial. Bajar esta revision "
            "las dejaria fuera de la restriccion, y el historial es de solo anexar "
            "(SEC-U4.11): no se borran para poder bajar"
        )
        raise RuntimeError(msg)
    # Los recibos de esta operacion no son historial: son la huella de una peticion, y
    # la restriccion de vuelta los rechazaria a mitad de la migracion.
    op.execute("DELETE FROM decision_receipt WHERE operation = 'triage_note'")

    _cambiar_restriccion("decision_receipt", OPERACION, OPERACION_ANTES)
    _cambiar_restriccion("case_change", CAMPO, CAMPO_ANTES)
    _cambiar_restriccion("case_change", CLASE, CLASE_ANTES)

    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {TABLA}")
    op.drop_table(TABLA)
