"""u5_platform_0001_spend_tables: la factura del proyecto y el rastro.

Revision: u5_platform_0001_spend_tables
Revision anterior: u4_case_0001_case_tables

Cuatro tablas, y **tres de ellas no llevan aseguradora**. No es un olvido: el
techo es uno solo para el proyecto y las cifras por proveedor y por mes cruzan
las tres aseguradoras, asi que el dinero y las cuotas son dato del proyecto
(BR7.1). Las tres entran en `[tool.untangle.rls] excluded` del manifiesto, cada
una con su razon escrita, y a cambio aceptan una prohibicion mas fuerte que la
que pierden y que una herramienta comprueba: ahi dentro no hay nada personal que
aislar (BR7.2). La cuarta, el resumen de traza, si es dato de un visitante y
lleva su aseguradora, su politica y su marca como cualquier otra.

Igual que en las revisiones de U2 y U4, **las lineas de aislamiento estan
escritas literales** y los conjuntos cerrados se escriben a mano en vez de
generarse desde los enums de Python: una migracion es el registro historico de
lo que se le hizo a la base, y leer el enum vivo haria que anadir un valor
manana cambiara el significado de lo que esta revision dice haber hecho ayer.

Cuatro decisiones cargan el peso de esta revision:

**1. El texto de las tres tablas excluidas va acotado, nunca `TEXT`.** Es lo que
paga la exclusion. La asercion de columnas falla ante una columna de texto sin
longitud acotada en una tabla excluida (BR7.2), asi que cada columna declara
cuanto cabe en ella. No es una molestia burocratica: una columna sin tope es
donde un dia cabe una frase del asegurado, y esa frase estaria en la unica tabla
del aplicativo que nadie filtra por aseguradora.

**2. El caso se nombra, no se cuelga.** `spend_entry.case_ref` referencia el
caso con `ON DELETE SET NULL`: el reinicio nocturno borra el caso de visitante y
la fila de gasto **sobrevive** con su proveedor, su uso, su costo y su fecha
(BR7.5). Con borrado en cascada, el reinicio vaciaria el registro de lo que el
proyecto ya pago, contra AC5.14.4. `trace_summary.case_id` si va en cascada,
porque el resumen es del visitante y se va con el (BR7.4).

**3. El dinero va en tipo numerico exacto**, `NUMERIC(20, 12)`, nunca en coma
flotante. La escala sale de los dos extremos reales: el precio por token del
modelo de chat es 0,00000025 USD --siete decimales-- y la lista publica precios
por millon que al dividirse pueden bajar mas, asi que doce decimales dejan
margen sin inventarlo; los ocho digitos enteros restantes sobran para un techo
de 5 USD. Con coma flotante, sumar veinte fracciones de centavo da un total que
depende del orden de las sumas, y entonces el techo cortaria en un punto
distinto segun el orden de las llamadas.

**4. La reserva de grabacion admite nulo y viaja con su estado.** Es una
desviacion consciente de `entities.md`, que la declara decimal obligatoria con
default 0. La reserva se declara en **minutos** en configuracion versionada y se
convierte a dolares con la tabla de precios, que hoy no publica el precio por
minuto de la voz: esa conversion puede quedar **no medida**. Un default 0 diria
"no hay reserva" cuando lo cierto es "no se pudo calcular", y con reserva 0 el
carril publico se llevaria tambien lo apartado para grabar el video de la semana
doce. Es el mismo par que ya usa `CallReserve` para el mismo dato, y el mismo
que usa el costo en todo esta unidad (BR3.9, BR4.9).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "u5_platform_0001_spend_tables"
down_revision: str | None = "u4_case_0001_case_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: La marca de dato de visitante, igual que en U2 y U4. Una prueba le pregunta
#: al catalogo que tablas la llevan y exige que cada una tenga purgador.
MARCA = "visitor-data"

#: Dinero y precios. Doce decimales por el precio por token, ocho digitos
#: enteros por un techo que es de 5 USD.
DINERO = sa.Numeric(precision=20, scale=12)

#: Unidades cobrables: tokens, segundos de audio, caracteres. Mismo tipo exacto
#: que el dinero porque es el otro factor de la multiplicacion, y basta con que
#: uno sea inexacto para que el producto lo sea.
UNIDADES = sa.Numeric(precision=24, scale=6)


def upgrade() -> None:
    # --- El libro mayor -------------------------------------------------------
    # Una fila por llamada, sin excepcion, incluida la que fallo y la que no se
    # pudo valorar (BR3.1). Sin las que fallan, el costo por caso quedaria por
    # debajo del real y nadie lo notaria.
    op.create_table(
        "spend_entry",
        sa.Column("entry_id", sa.String(64), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        # El identificador exacto del modelo o de la voz, nunca un alias movil
        # (BR1.4): un alias se mueve del lado del proveedor y la cifra publicada
        # deja de poder reproducirse.
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("use", sa.String(16), nullable=False),
        # Atribucion, no aislamiento (BR7.1). Nula cuando el uso no tiene
        # aseguradora: evaluaciones, generacion, operacion. **No** lleva clave
        # foranea hacia la aseguradora porque las aseguradoras no son una tabla:
        # viven en configuracion versionada (U2).
        sa.Column("tenant_ref", sa.String(32), nullable=True),
        sa.Column("case_ref", sa.String(64), nullable=True),
        sa.Column("units", UNIDADES, nullable=False),
        sa.Column("unit_kind", sa.String(32), nullable=False),
        # Las cuatro columnas de precio. Todas presentes o todas ausentes, y eso
        # lo dice `cost_status` (BR3.4).
        sa.Column("unit_price_usd", DINERO, nullable=True),
        sa.Column("price_list_version", sa.String(32), nullable=True),
        sa.Column("price_list_effective_date", sa.Date(), nullable=True),
        sa.Column("cost_usd", DINERO, nullable=True),
        sa.Column("cost_status", sa.String(16), nullable=False),
        sa.Column("billable", sa.Boolean(), nullable=False),
        sa.Column("lane", sa.String(16), nullable=False, server_default="public"),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        # El caso se **nombra** y no se cuelga: el reinicio nocturno lo borra y
        # esta columna queda vacia mientras la fila sobrevive con su costo
        # (BR7.5, AC5.14.4).
        sa.ForeignKeyConstraint(
            ["case_ref"],
            ["case_record.case_id"],
            name="spend_entry_nombra_el_caso",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "provider IN ('gemini', 'deepgram', 'cartesia', 'fallback_tts')",
            name="spend_entry_proveedor_valido",
        ),
        sa.CheckConstraint(
            "use IN ('voice', 'chat', 'evals', 'operations')", name="spend_entry_uso_valido"
        ),
        sa.CheckConstraint(
            "unit_kind IN ('input_tokens', 'output_tokens', 'embedding_tokens', "
            "'audio_seconds', 'characters')",
            name="spend_entry_unidad_valida",
        ),
        sa.CheckConstraint(
            "cost_status IN ('measured', 'not_measured')", name="spend_entry_estado_valido"
        ),
        sa.CheckConstraint("lane IN ('public', 'recording')", name="spend_entry_carril_valido"),
        sa.CheckConstraint(
            "source IN ('provider_reported', 'counted_locally')", name="spend_entry_origen_valido"
        ),
        sa.CheckConstraint("units >= 0", name="spend_entry_unidades_no_negativas"),
        sa.CheckConstraint(
            "unit_price_usd IS NULL OR unit_price_usd >= 0", name="spend_entry_precio_no_negativo"
        ),
        sa.CheckConstraint(
            "cost_usd IS NULL OR cost_usd >= 0", name="spend_entry_costo_no_negativo"
        ),
        # Las cuatro columnas de precio van juntas o no va ninguna, y cual de
        # las dos lo dice `cost_status`. Es la invariante de BR3.4 impuesta por
        # la base y no solo por el modelo: sin ella, una fila escrita por una
        # via que nadie previo podria decir "measured" y no traer con que.
        sa.CheckConstraint(
            "num_nonnulls(unit_price_usd, price_list_version, price_list_effective_date, "
            "cost_usd) = CASE WHEN cost_status = 'measured' THEN 4 ELSE 0 END",
            name="spend_entry_precio_completo_o_ausente",
        ),
    )
    # Los dos indices del reporte. No participan en el camino del turno: ese
    # camino lee la ventana y el contador por su clave y no recorre el historial
    # (diseno de rendimiento).
    op.create_index("spend_entry_por_fecha", "spend_entry", ["occurred_at"])
    op.create_index("spend_entry_por_proveedor", "spend_entry", ["provider", "occurred_at"])
    op.create_index("spend_entry_por_caso", "spend_entry", ["case_ref"])
    op.execute(
        "COMMENT ON TABLE spend_entry IS "
        "'dato del proyecto: una fila por llamada a un proveedor, sin aseguradora "
        "que aislar (BR7.1, BR7.2)'"
    )

    # --- Los contadores de cuota ----------------------------------------------
    op.create_table(
        "quota_counter",
        # Se **deriva** de alcance, sujeto y comienzo del periodo. Dos contadores
        # del mismo alcance y sujeto en el mismo periodo tienen que ser uno: si
        # la clave se eligiera al crearlos, abrir dos llamadas a la vez crearia
        # dos filas y cada una dejaria pasar la suya (RT-13).
        sa.Column("counter_key", sa.String(192), primary_key=True),
        sa.Column("scope", sa.String(32), nullable=False),
        # El resumen de la clave del navegador, nunca la clave (BR7.3). Para el
        # alcance del sitio, el literal `site`: el cupo del sitio no es de nadie.
        sa.Column("subject_key", sa.String(64), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        # El limite vigente cuando se abrio el periodo. El cupo del sitio se
        # recalcula cada dia (BR5.6); esto deja escrito con cual se decidio, de
        # modo que un rechazo se pueda explicar meses despues.
        sa.Column("limit_at_period_start", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # La unicidad logica, impuesta por la base ademas de por la derivacion de
        # la clave: si un dia alguien derivara mal la clave, dos filas del mismo
        # alcance, sujeto y periodo dejarian pasar el doble de lo permitido.
        sa.UniqueConstraint(
            "scope", "subject_key", "period_start", name="quota_counter_uno_por_periodo"
        ),
        sa.CheckConstraint(
            "scope IN ('chat_messages_session', 'chat_messages_day', "
            "'voice_calls_visitor_day', 'voice_calls_site_day')",
            name="quota_counter_alcance_valido",
        ),
        sa.CheckConstraint("count >= 0", name="quota_counter_conteo_no_negativo"),
        sa.CheckConstraint("limit_at_period_start >= 0", name="quota_counter_limite_no_negativo"),
        # El cupo del sitio no es de ningun visitante, y ningun visitante puede
        # llamarse `site`: las dos mitades, porque cada una sola deja pasar la
        # confusion en una direccion (BR5.1).
        sa.CheckConstraint(
            "(scope = 'voice_calls_site_day') = (subject_key = 'site')",
            name="quota_counter_sitio_sin_dueno",
        ),
    )
    op.execute(
        "COMMENT ON TABLE quota_counter IS "
        "'dato del proyecto: cuanto lleva consumido un sujeto en un periodo, con el "
        "resumen de la clave del navegador y nunca la clave (BR7.1, BR7.3)'"
    )

    # --- El acumulado de la ventana -------------------------------------------
    # Una sola fila por ventana. Existe por dos razones que sumar el historial no
    # cubre: el corte tiene que poder decidirse sin recorrerlo (BR3.8) y dos
    # llamadas simultaneas tienen que competir por **la misma fila** para que
    # ninguna pase el techo creyendo que la otra no existe (BR4.6). Una fila
    # unica se bloquea; una suma no.
    op.create_table(
        "budget_window",
        sa.Column("window_start", sa.Date(), primary_key=True),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("billable_spent_usd", DINERO, nullable=False, server_default="0"),
        sa.Column("cap_usd", DINERO, nullable=False, server_default="5.00"),
        sa.Column("alert_usd", DINERO, nullable=False, server_default="3.00"),
        # Se escribe una sola vez. Que exista es lo que impide una segunda alerta
        # (BR4.3): una alerta por llamada convierte el aviso en ruido.
        sa.Column("alert_sent_at", sa.DateTime(timezone=True), nullable=True),
        # Admite nulo y viaja con su estado, igual que el costo. Ver la cuarta
        # decision del encabezado: la reserva se declara en minutos y su
        # conversion a dolares puede quedar no medida, y un cero diria "no hay
        # reserva" en vez de "no se pudo calcular".
        sa.Column("recording_reserve_usd", DINERO, nullable=True),
        sa.Column(
            "recording_reserve_status",
            sa.String(16),
            nullable=False,
            server_default="not_measured",
        ),
        sa.Column("recording_spent_usd", DINERO, nullable=False, server_default="0"),
        # Cuantas llamadas facturables no se pudieron valorar. Viaja con el
        # acumulado para que ninguna pantalla pueda mostrar el total sin decir
        # cuanto no se midio (BR3.5).
        sa.Column("unmeasured_billable_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # La ventana es acumulada de noventa dias y nunca mensual (BR4.1): con un
        # contador que se reinicia cada mes, el techo no protege nada.
        sa.CheckConstraint(
            "window_end = window_start + INTERVAL '90 days'", name="budget_window_noventa_dias"
        ),
        sa.CheckConstraint(
            "recording_reserve_status IN ('measured', 'not_measured')",
            name="budget_window_estado_de_reserva_valido",
        ),
        sa.CheckConstraint(
            "(recording_reserve_status = 'measured') = (recording_reserve_usd IS NOT NULL)",
            name="budget_window_reserva_con_su_estado",
        ),
        sa.CheckConstraint("billable_spent_usd >= 0", name="budget_window_acumulado_no_negativo"),
        sa.CheckConstraint("cap_usd >= 0", name="budget_window_techo_no_negativo"),
        sa.CheckConstraint("recording_spent_usd >= 0", name="budget_window_grabacion_no_negativa"),
        sa.CheckConstraint(
            "unmeasured_billable_calls >= 0", name="budget_window_no_medidas_no_negativas"
        ),
        # La alerta avisa **antes** del techo, no despues.
        sa.CheckConstraint("alert_usd <= cap_usd", name="budget_window_alerta_antes_del_techo"),
        # Apartar mas de lo que hay dejaria el carril publico cerrado desde el
        # primer dia.
        sa.CheckConstraint(
            "recording_reserve_usd IS NULL OR recording_reserve_usd <= cap_usd",
            name="budget_window_reserva_cabe_en_el_techo",
        ),
        # Con la reserva sin medir, `COALESCE` la deja en cero y esto exige que
        # el carril de grabacion no haya gastado nada: no se puede gastar de una
        # reserva cuyo tamano no se sabe.
        sa.CheckConstraint(
            "recording_spent_usd <= COALESCE(recording_reserve_usd, 0)",
            name="budget_window_grabacion_dentro_de_su_reserva",
        ),
        # Lo gastado en grabacion esta **incluido** en el acumulado facturable.
        sa.CheckConstraint(
            "recording_spent_usd <= billable_spent_usd",
            name="budget_window_grabacion_dentro_del_acumulado",
        ),
    )
    op.execute(
        "COMMENT ON TABLE budget_window IS "
        "'dato del proyecto: el acumulado de la ventana de 90 dias, su techo y su "
        "alerta; no se borra nunca (BR7.1, AC5.14.4)'"
    )

    # --- El resumen de traza --------------------------------------------------
    # La unica de las cuatro que es dato de un visitante: lleva su aseguradora,
    # su politica y su marca, y cuelga del caso en cascada (BR7.4).
    op.create_table(
        "trace_summary",
        sa.Column("trace_id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        # El resumen de la clave del navegador, nunca la clave (BR7.3). Decide a
        # quien se le muestra (BR6.6).
        sa.Column("visitor_key_hash", sa.Text(), nullable=False),
        # El turno cuya respuesta resume. Nulo en el resumen de un caso entero.
        sa.Column("turn_ref", sa.Text(), nullable=True),
        # La lista de nodos con su tiempo y su costo. Va junta porque se escribe
        # en un solo acto --al completarse el rastro-- y se lee entera; ninguna
        # consulta pregunta por un nodo suelto.
        sa.Column("nodes", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("clauses_retrieved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("clauses_verified", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("cost_usd", DINERO, nullable=True),
        sa.Column("cost_status", sa.Text(), nullable=False, server_default="not_measured"),
        sa.Column("status", sa.Text(), nullable=False, server_default="recording"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["case_record.case_id"],
            name="trace_summary_del_caso",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('recording', 'ready', 'lost')", name="trace_summary_estado_valido"
        ),
        sa.CheckConstraint(
            "cost_status IN ('measured', 'not_measured')", name="trace_summary_costo_valido"
        ),
        sa.CheckConstraint(
            "(cost_status = 'measured') = (cost_usd IS NOT NULL)",
            name="trace_summary_costo_con_su_estado",
        ),
        sa.CheckConstraint("clauses_retrieved >= 0", name="trace_summary_recuperadas_no_negativas"),
        # Verificar lo que no se recupero no significa nada.
        sa.CheckConstraint(
            "clauses_verified >= 0 AND clauses_verified <= clauses_retrieved",
            name="trace_summary_verificadas_no_superan_recuperadas",
        ),
        sa.CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0", name="trace_summary_latencia_no_negativa"
        ),
        # Un resumen `ready` sin nodos o sin latencia **miente**: mientras el
        # rastro no haya llegado, el estado es `recording` y `lost` es un valor,
        # no un fallo (BR6.7).
        sa.CheckConstraint(
            "status <> 'ready' OR (latency_ms IS NOT NULL AND jsonb_array_length(nodes) > 0)",
            name="trace_summary_listo_esta_completo",
        ),
    )
    op.create_index(
        "trace_summary_por_aseguradora", "trace_summary", ["tenant_id", "case_id", "created_at"]
    )
    # Por quien lo produjo: es la consulta de BR6.6, y responder "no existe" a
    # otro navegador tiene que costar una lectura por indice, no un recorrido.
    op.create_index(
        "trace_summary_por_navegador", "trace_summary", ["tenant_id", "visitor_key_hash"]
    )
    op.execute("ALTER TABLE trace_summary ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE trace_summary FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON trace_summary
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
        """
    )
    op.execute(
        f"COMMENT ON TABLE trace_summary IS "
        f"'{MARCA}: lo que una respuesta ensena de si misma, del navegador que la "
        f"produjo y de nadie mas (C-11, BR6.6)'"
    )


def downgrade() -> None:
    """Deshace la revision entera. Se prueba en cada corrida, no se supone.

    `mise run migrate:check` sube, baja y vuelve a subir contra una base virgen:
    un `downgrade()` que no funciona se descubre el dia que se escribe y no el
    dia que hace falta.

    El orden es el inverso del de arriba. El resumen de traza va primero porque
    apunta al caso; las tres del dinero no apuntan a nada que esta revision haya
    creado, y `spend_entry` pierde su clave foranea al borrarse la tabla.
    """
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON trace_summary")
    op.drop_index("trace_summary_por_navegador", table_name="trace_summary")
    op.drop_index("trace_summary_por_aseguradora", table_name="trace_summary")
    op.drop_table("trace_summary")

    op.drop_table("budget_window")

    op.drop_table("quota_counter")

    op.drop_index("spend_entry_por_caso", table_name="spend_entry")
    op.drop_index("spend_entry_por_proveedor", table_name="spend_entry")
    op.drop_index("spend_entry_por_fecha", table_name="spend_entry")
    op.drop_table("spend_entry")
