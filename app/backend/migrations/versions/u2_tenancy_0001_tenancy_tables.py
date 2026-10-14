"""u2_tenancy_0001_tenancy_tables: las dos tablas de U2, con su aislamiento.

Revision: u2_tenancy_0001_tenancy_tables
Revision anterior: ninguna. Es la primera del proyecto: U1 decidio a proposito no
crear ninguna tabla (CG-1), asi que U2 instala tambien la historia de
migraciones.

Las dos tablas que U2 crea son las unicas del modulo que llegan a la base. La
aseguradora, la persona de bandeja y la tabla de permisos viven en configuracion
versionada; el enlace de caso y la clave del navegador estan aqui porque
necesitan poder **revocarse y borrarse cada noche**.

**Las tres lineas de aislamiento estan escritas literales, una por tabla**
(decision Q1 del diseno de calidad). No hay funcion compartida que las emita. La
razon es de lectura: una revision tiene que decir por si sola que aislamiento
dejo. Con una funcion compartida hay que ir a otro archivo para saberlo, y
cambiarla alteraria en silencio el aislamiento de tablas escritas meses antes.
La duplicacion es deliberada: son tres lineas que cualquiera revisa de un
vistazo, y quien se las salte lo descubre en `mise run rls:check`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u2_tenancy_0001_tenancy_tables"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "case_access_link",
        sa.Column("link_id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        # Del token se guarda su resumen, nunca el token: quien lea la tabla no
        # puede reconstruir ningun enlace (FD-U2-8).
        sa.Column("token_digest", sa.Text(), nullable=False, unique=True),
        sa.Column("access", sa.Text(), nullable=False, server_default="view_and_decide"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        # Vacio mientras el enlace vale. Una vez puesto, no se quita.
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        # No limita nada: existe para que un canje repetido sea un hecho
        # observable y no una conjetura (BR3.2).
        sa.Column("redeemed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("access IN ('view_and_decide')", name="case_access_link_access_valido"),
        sa.CheckConstraint("expires_at > created_at", name="case_access_link_vida_positiva"),
    )
    op.create_index(
        "case_access_link_por_aseguradora_y_caso",
        "case_access_link",
        ["tenant_id", "case_id"],
    )
    op.execute("ALTER TABLE case_access_link ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE case_access_link FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON case_access_link
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
        """
    )
    # La marca de dato de visitante, en la misma revision que crea la tabla y por
    # la misma razon que el aislamiento: una prueba le pregunta al catalogo que
    # tablas la llevan y exige que cada una tenga purgador. Comparar dos listas
    # escritas a mano no comprueba nada (BR3.6, C-11).
    op.execute(
        "COMMENT ON TABLE case_access_link IS "
        "'visitor-data: enlace firmado hacia el caso de un visitante (C-11)'"
    )

    op.create_table(
        "visitor_key",
        sa.Column("tenant_id", sa.Text(), nullable=False),
        # El resumen de la clave que viaja en la cookie; la clave en claro no se
        # guarda. Nada aqui identifica a una persona: ni nombre, ni correo, ni
        # direccion de red.
        sa.Column("visitor_key_hash", sa.Text(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        # La identidad es la pareja: el mismo navegador que visita dos
        # aseguradoras tiene una fila por cada una, y ninguna ve la otra (BR3.5).
        sa.PrimaryKeyConstraint("tenant_id", "visitor_key_hash", name="visitor_key_pk"),
    )
    op.execute("ALTER TABLE visitor_key ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE visitor_key FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON visitor_key
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
        """
    )
    op.execute(
        "COMMENT ON TABLE visitor_key IS "
        "'visitor-data: clave del navegador de un visitante, sin identidad (C-11)'"
    )


def downgrade() -> None:
    """Deshace la revision entera. Se prueba en cada corrida, no se supone.

    `mise run migrate:check` sube, baja y vuelve a subir contra una base virgen:
    un `downgrade()` que no funciona se descubre el dia que se escribe y no el
    dia que hace falta.
    """
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON visitor_key")
    op.drop_table("visitor_key")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON case_access_link")
    op.drop_index("case_access_link_por_aseguradora_y_caso", table_name="case_access_link")
    op.drop_table("case_access_link")
