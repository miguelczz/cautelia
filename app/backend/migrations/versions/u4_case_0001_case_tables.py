"""u4_case_0001_case_tables: las cinco tablas del caso, con su aislamiento.

Revision: u4_case_0001_case_tables
Revision anterior: u2_tenancy_0001_tenancy_tables

Cinco tablas: el caso, sus campos, sus partes, su transcripcion y su historial.
Las cinco nacen con **las tres lineas de aislamiento escritas literales** --una
por tabla, sin funcion compartida-- por la misma razon que las de U2: una
revision tiene que decir por si sola que aislamiento dejo, y cambiar una funcion
compartida alteraria en silencio el aislamiento de tablas escritas meses antes.

Tres decisiones cargan el peso de esta revision:

**1. Las cuatro tablas hijas cuelgan del caso con borrado en cascada.** "El
purgador borra el caso completo, sin dejar huerfanos" (SEC-U4.5) deja asi de
depender de que el purgador recuerde el orden: lo impone la forma de la base. Un
purgador que se olvidara de los turnos no dejaria turnos huerfanos, porque la
base no se lo permitiria.

**2. Los datos personales van en columnas de bytes, y cada fila lleva el
identificador de la clave que la cifro** (NFRD-U4-1, decision de Miguel). Una
columna de texto seria una columna sin cifrar. El identificador por fila es lo
que hace posible rotar la clave sin una migracion que reescriba el almacen
entero ni una ventana en la que los casos no se puedan abrir: las filas viejas
se siguen leyendo con la clave vieja y las nuevas nacen con la nueva.

La transcripcion **no** lleva columna cifrada, y no es un olvido: el texto del
turno ya va redactado por U3 antes de llegar aqui, y lo que protege el cifrado
--un volcado, una copia de seguridad-- ya no encuentra nada que leer en el.

**3. El historial rechaza el UPDATE en la base, no solo en el codigo.** Es de
solo anexar (SEC-U4.11) y el disparador lo impone. El DELETE si se permite, y
esa asimetria es deliberada: el reinicio nocturno tiene que poder borrar un caso
de visitante entero. Lo que la regla prohibe es que una entrada **cambie**, no
que la retencion acotada se cumpla.

Los conjuntos cerrados se escriben **literales** en sus restricciones y no se
generan desde los enums de Python. Una migracion es un registro historico de lo
que se le hizo a la base: si leyera el enum vivo, anadir un valor manana
cambiaria el significado de lo que esta revision dice haber hecho ayer.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "u4_case_0001_case_tables"
down_revision: str | None = "u2_tenancy_0001_tenancy_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: La marca de dato de visitante que cada tabla lleva en su comentario. Una
#: prueba de U2 le pregunta al catalogo que tablas la llevan y exige que cada
#: una tenga purgador: comparar dos listas escritas a mano no comprobaria nada.
MARCA = "visitor-data"

_POLITICA = """
    CREATE POLICY tenant_isolation ON {tabla}
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
"""


def _aislar(tabla: str, descripcion: str) -> None:
    """Habilita, fuerza y politiza el aislamiento, y escribe la marca.

    Esto **no** es la funcion compartida que la revision de U2 evito: aquella
    habria ocultado el texto del aislamiento. Aqui el texto esta a la vista en
    `_POLITICA`, tres lineas arriba, y lo que se evita repetir cinco veces es
    solo la llamada. Quien lea esta revision ve el aislamiento completo sin
    salir del archivo, que es lo que aquella decision buscaba.
    """
    op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY")
    op.execute(_POLITICA.format(tabla=tabla))
    op.execute(f"COMMENT ON TABLE {tabla} IS '{MARCA}: {descripcion} (C-11)'")


def upgrade() -> None:
    # --- El caso --------------------------------------------------------------
    op.create_table(
        "case_record",
        sa.Column("case_id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        # El numero legible completo, tal como se dicta: tres letras, guion,
        # seis digitos. Es lo que una persona anota y lo que teclea despues.
        sa.Column("case_number", sa.Text(), nullable=False),
        sa.Column("record_type", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default="open"),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("policy_ref", sa.Text(), nullable=True),
        sa.Column("derivation_reason", sa.Text(), nullable=True),
        sa.Column("priority", sa.Text(), nullable=False, server_default="normal"),
        # Los cinco adjuntos del cierre, con el estado de cada uno. Van juntos
        # en un solo valor porque se escriben en un solo acto --el cierre-- y se
        # leen enteros; ninguna consulta pregunta por uno suelto.
        sa.Column("closing_evidence", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        # El numero es unico **dentro de** la aseguradora, no en toda la base:
        # los prefijos distintos ya lo separan, y una unicidad global acoplaria
        # tres aseguradoras que no se conocen entre si.
        sa.UniqueConstraint("tenant_id", "case_number", name="case_record_numero_unico"),
        sa.CheckConstraint(
            "case_number ~ '^[A-Z]{3}-[0-9]{6}$'", name="case_record_numero_con_forma"
        ),
        sa.CheckConstraint(
            "record_type IN ('claim', 'coverage_inquiry', 'quote_request')",
            name="case_record_tipo_valido",
        ),
        sa.CheckConstraint(
            "state IN ('open', 'capturing', 'verifying', 'deciding', "
            "'derived', 'awaiting_insured', 'closed')",
            name="case_record_estado_valido",
        ),
        sa.CheckConstraint(
            "resolution IS NULL OR resolution IN "
            "('registered', 'approved', 'rejected', 'sent_to_insurer')",
            name="case_record_resolucion_valida",
        ),
        sa.CheckConstraint("channel IN ('voice', 'chat')", name="case_record_canal_valido"),
        sa.CheckConstraint(
            "origin IN ('public_chat', 'public_voice_console', 'local_deployment', 'generator')",
            name="case_record_origen_valido",
        ),
        sa.CheckConstraint("language IN ('es', 'en')", name="case_record_idioma_valido"),
        sa.CheckConstraint(
            "derivation_reason IS NULL OR derivation_reason IN "
            "('demo_limit', 'person_requested', 'rule')",
            name="case_record_motivo_valido",
        ),
        sa.CheckConstraint("priority IN ('normal', 'high')", name="case_record_prioridad_valida"),
        # Un caso cerrado trae su resolucion, su fecha y sus cinco adjuntos. Sin
        # esto, "cerrado" seria un estado que se puede alcanzar sin haber
        # comprobado nada, que es exactamente lo que SEC-U4.13 impide arriba.
        sa.CheckConstraint(
            "state <> 'closed' OR (resolution IS NOT NULL AND closed_at IS NOT NULL "
            "AND closing_evidence IS NOT NULL)",
            name="case_record_cierre_completo",
        ),
        # Y al reves: lo que no esta cerrado no lleva nada del cierre. Sin esta
        # mitad, una fila con resolucion y sin cerrar se leeria como decidida en
        # cualquier consulta que mire la columna y no el estado (BR3.5).
        sa.CheckConstraint(
            "state = 'closed' OR (resolution IS NULL AND closed_at IS NULL "
            "AND closing_evidence IS NULL)",
            name="case_record_sin_cierre_a_medias",
        ),
        # Quien pidio hablar con una persona ya pidio ayuda una vez; que su caso
        # quede detras de otros en la bandeja es el fallo que se siente como que
        # no lo escucharon (BR3.8).
        sa.CheckConstraint(
            "derivation_reason IS DISTINCT FROM 'person_requested' OR priority = 'high'",
            name="case_record_prioridad_de_quien_pidio_persona",
        ),
    )
    op.create_index("case_record_por_aseguradora", "case_record", ["tenant_id", "state"])
    _aislar("case_record", "el caso de un visitante y todo lo que cuelga de el")

    # --- Los campos -----------------------------------------------------------
    op.create_table(
        "case_field",
        sa.Column("case_id", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("field_key", sa.Text(), nullable=False),
        # Sellado. Lo que el asegurado dijo es dato personal igual que el nombre
        # del testigo, y SEC-U4.8 los cifra a los dos antes de persistir.
        sa.Column("value", sa.LargeBinary(), nullable=True),
        sa.Column("sealed_key_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="not_stated"),
        sa.Column("evidence_turn_id", sa.Text(), nullable=True),
        sa.Column("evidence_change_id", sa.Text(), nullable=True),
        sa.Column("confirmed_aloud_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("case_id", "field_key", name="case_field_pk"),
        sa.ForeignKeyConstraint(
            ["case_id"], ["case_record.case_id"], name="case_field_del_caso", ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "status IN ('not_stated', 'stated', 'confirmed')", name="case_field_estado_valido"
        ),
        # Un campo no dicho no lleva valor ni evidencia: no hay nada que
        # respaldar. Es la distincion que separa "la persona dijo que no hubo
        # lesionados" de "nadie pregunto" (BR2.3).
        sa.CheckConstraint(
            "status <> 'not_stated' OR (value IS NULL AND evidence_turn_id IS NULL "
            "AND evidence_change_id IS NULL)",
            name="case_field_no_dicho_sin_nada",
        ),
        # Y uno dicho lleva **exactamente una** evidencia: el turno en que se
        # dijo, o la entrada del historial si lo escribio un ajustador (BR2.4).
        sa.CheckConstraint(
            "status = 'not_stated' OR ((evidence_turn_id IS NOT NULL)::int "
            "+ (evidence_change_id IS NOT NULL)::int = 1)",
            name="case_field_una_sola_evidencia",
        ),
        # Un valor sin su identificador de clave no se podria abrir el dia de la
        # rotacion, y un identificador sin valor no significa nada.
        sa.CheckConstraint(
            "(value IS NULL) = (sealed_key_id IS NULL)", name="case_field_clave_con_valor"
        ),
        # Un campo corregido desde la bandeja no lleva marca de lectura en voz
        # alta: no hubo conversacion (BR2.5).
        sa.CheckConstraint(
            "confirmed_aloud_at IS NULL OR evidence_change_id IS NULL",
            name="case_field_lectura_solo_con_turno",
        ),
    )
    op.create_index("case_field_por_aseguradora", "case_field", ["tenant_id", "case_id"])
    _aislar("case_field", "los campos del caso de un visitante, cifrados en reposo")

    # --- Las partes -----------------------------------------------------------
    op.create_table(
        "case_party",
        sa.Column("party_id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        # Las tres columnas personales de la otra parte. Van selladas y sin
        # valor supuesto: una parte de la que solo se sabe el rol tiene las tres
        # vacias, y eso es un dato, no un hueco que rellenar.
        sa.Column("name", sa.LargeBinary(), nullable=True),
        sa.Column("contact", sa.LargeBinary(), nullable=True),
        sa.Column("plate", sa.LargeBinary(), nullable=True),
        sa.Column("sealed_key_id", sa.Text(), nullable=True),
        sa.Column("injury_status", sa.Text(), nullable=True),
        sa.Column("vehicle_description", sa.Text(), nullable=True),
        # La placa del otro vehiculo lleva su propio estado y su evidencia: una
        # placa que se oyo mal y no se confirmo no cuenta como completa.
        sa.Column("plate_status", sa.Text(), nullable=False, server_default="not_stated"),
        sa.Column("plate_evidence_turn_id", sa.Text(), nullable=True),
        sa.Column("statement_version", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["case_id"], ["case_record.case_id"], name="case_party_del_caso", ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "role IN ('injured', 'witness', 'other_driver', 'other_vehicle')",
            name="case_party_rol_valido",
        ),
        sa.CheckConstraint(
            "plate_status IN ('not_stated', 'stated', 'confirmed')",
            name="case_party_estado_placa_valido",
        ),
        sa.CheckConstraint(
            "plate_status = 'not_stated' OR plate IS NOT NULL",
            name="case_party_placa_dicha_con_valor",
        ),
        sa.CheckConstraint(
            "num_nonnulls(name, contact, plate) = 0 OR sealed_key_id IS NOT NULL",
            name="case_party_clave_con_valor",
        ),
    )
    op.create_index("case_party_por_aseguradora", "case_party", ["tenant_id", "case_id"])
    _aislar("case_party", "las otras partes del accidente de un visitante, cifradas en reposo")

    # --- La transcripcion -----------------------------------------------------
    op.create_table(
        "case_transcript_turn",
        sa.Column("turn_id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        sa.Column("speaker", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        # Texto, no bytes: llega ya redactado por U3 y el tipo lo exige en la
        # firma antes de ejecutar. Cifrarlo ademas protegeria un texto del que
        # los datos personales ya se quitaron.
        sa.Column("text_redacted", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("interrupted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["case_record.case_id"],
            name="case_transcript_turn_del_caso",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "speaker IN ('insured', 'agent', 'staff')", name="case_transcript_turn_hablante_valido"
        ),
        sa.CheckConstraint(
            "channel IN ('voice', 'chat')", name="case_transcript_turn_canal_valido"
        ),
        sa.CheckConstraint("language IN ('es', 'en')", name="case_transcript_turn_idioma_valido"),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="case_transcript_turn_orden_del_reloj",
        ),
    )
    op.create_index(
        "case_transcript_turn_por_aseguradora",
        "case_transcript_turn",
        ["tenant_id", "case_id", "started_at"],
    )
    _aislar("case_transcript_turn", "la transcripcion del caso de un visitante, ya redactada")

    # --- El historial ---------------------------------------------------------
    op.create_table(
        "case_change",
        sa.Column("change_id", sa.Text(), primary_key=True),
        # El orden en que pasaron las cosas, y no el de sus relojes. El
        # identificador es al azar --uno correlativo dejaria ver cuantos cambios
        # lleva el caso a quien solo vio uno-- y dos entradas del mismo instante
        # quedarian en orden arbitrario ordenando por fecha. Un historial que se
        # audita tiene que poder leerse en el orden en que ocurrio.
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        sa.Column("change_kind", sa.Text(), nullable=False),
        sa.Column("field_key", sa.Text(), nullable=True),
        # Selladas por la misma razon que el campo: **son copias suyas**.
        # Dejarlas en claro desharia el cifrado para todo lo que alguna vez se
        # corrigio, y el historial seria la fuga por la puerta de atras.
        sa.Column("previous_value", sa.LargeBinary(), nullable=True),
        sa.Column("new_value", sa.LargeBinary(), nullable=True),
        sa.Column("sealed_key_id", sa.Text(), nullable=True),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("channel", sa.Text(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"], ["case_record.case_id"], name="case_change_del_caso", ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "change_kind IN ('field_set', 'transition_applied', "
            "'transition_rejected', 'close_rejected')",
            name="case_change_clase_valida",
        ),
        sa.CheckConstraint(
            "actor_type IN ('insured', 'agent', 'staff', 'system')",
            name="case_change_actor_valido",
        ),
        sa.CheckConstraint(
            "channel IS NULL OR channel IN ('voice', 'chat')", name="case_change_canal_valido"
        ),
        sa.CheckConstraint(
            "num_nonnulls(previous_value, new_value) = 0 OR sealed_key_id IS NOT NULL",
            name="case_change_clave_con_valor",
        ),
        # Un cambio de campo dice cual. Un rechazo de transicion no tiene campo
        # que nombrar, y exigirselo obligaria a inventar uno.
        sa.CheckConstraint(
            "change_kind <> 'field_set' OR field_key IS NOT NULL",
            name="case_change_campo_con_su_clave",
        ),
    )
    op.create_index("case_change_por_aseguradora", "case_change", ["tenant_id", "case_id", "seq"])
    _aislar("case_change", "el historial del caso de un visitante, con los valores cifrados")

    # El historial es de solo anexar, y lo impone la base (SEC-U4.11). El DELETE
    # se permite a proposito: el reinicio nocturno tiene que poder borrar un caso
    # de visitante entero, y lo que la regla prohibe es que una entrada cambie,
    # no que la retencion acotada se cumpla.
    op.execute(
        """
        CREATE FUNCTION case_change_solo_anexa() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'el historial del caso es de solo anexar: una entrada '
                'no se edita (SEC-U4.11). Para corregir un campo se anexa otra '
                'entrada, que es lo que deja el rastro de quien lo cambio';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER case_change_sin_edicion
            BEFORE UPDATE ON case_change
            FOR EACH ROW EXECUTE FUNCTION case_change_solo_anexa()
        """
    )


def downgrade() -> None:
    """Deshace la revision entera. Se prueba en cada corrida, no se supone.

    `mise run migrate:check` sube, baja y vuelve a subir contra una base virgen:
    un `downgrade()` que no funciona se descubre el dia que se escribe y no el
    dia que hace falta.

    El orden es el inverso del de arriba porque las cuatro hijas apuntan al
    caso: borrarlo primero dejaria cuatro claves foraneas colgando.
    """
    op.execute("DROP TRIGGER IF EXISTS case_change_sin_edicion ON case_change")
    op.execute("DROP FUNCTION IF EXISTS case_change_solo_anexa()")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON case_change")
    op.drop_index("case_change_por_aseguradora", table_name="case_change")
    op.drop_table("case_change")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON case_transcript_turn")
    op.drop_index("case_transcript_turn_por_aseguradora", table_name="case_transcript_turn")
    op.drop_table("case_transcript_turn")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON case_party")
    op.drop_index("case_party_por_aseguradora", table_name="case_party")
    op.drop_table("case_party")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON case_field")
    op.drop_index("case_field_por_aseguradora", table_name="case_field")
    op.drop_table("case_field")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON case_record")
    op.drop_index("case_record_por_aseguradora", table_name="case_record")
    op.drop_table("case_record")
