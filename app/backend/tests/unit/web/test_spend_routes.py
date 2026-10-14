"""El tablero de gasto sin base: el montaje, la forma y lo que no decide (2026-10-09).

Desde el 2026-10-09 es publico, por decision de Miguel. Lo que **no** necesita base
y por eso se prueba aqui, en cada corrida: que se monta sin credencial como una
superficie publica, que entrega lo que las consultas devuelven sin recalcularlo,
que los casos salen descritos y **sin identificador**, que el caso del navegador
sale como suyo, y que el codigo no contiene ningun umbral. Lo que necesita el
registro de verdad --las agregaciones en SQL, los casos que existen-- esta en
`tests/integration/u22`.
"""

from __future__ import annotations

import ast
import inspect
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from untangle import paths
from untangle.base import ProviderName
from untangle.case_record import api as casos
from untangle.case_record.models import Case, CaseNumber, Channel, Origin, RecordType
from untangle.chat import opening
from untangle.chat import session as chat
from untangle.copy_catalog import api as copy_api
from untangle.server import composition, spend_routes
from untangle.settings import Settings
from untangle.telemetry.spend import api as spend
from untangle.telemetry.spend import repository
from untangle.telemetry.spend.models import (
    BudgetWindow,
    SpendActivity,
    SpendTotal,
    UnpricedUsage,
)
from untangle.tenancy import api as tenancy
from untangle.voice import api as voz

MODULO = composition.ModuleSpec(
    module="untangle.server.spend_routes",
    provides=frozenset({"router", "surfaces"}),
)

#: Marcas reconocibles: el identificador y el numero de un caso. Si alguno aparece
#: en la respuesta, el tablero publico identifico a un visitante.
CASO_ID = "case-secreto-7f3c91"
CASO_NUMERO = "STO-482913"


@pytest.fixture(autouse=True)
def proceso_limpio() -> Iterator[None]:
    spend_routes.reset_cache()
    yield
    copy_api.reset()
    spend.reset()
    spend_routes.reset_cache()


def _cliente(**cookies: str) -> TestClient:
    app = composition.build_app(
        Settings(env="local", database_url=None),
        modules=(MODULO,),
        dist_dir=paths.frontend_dist_dir(),
    )
    return TestClient(app, raise_server_exceptions=False, cookies=cookies)


def _total(medido: str, sin_medir: int = 0) -> SpendTotal:
    return SpendTotal(measured_usd=Decimal(medido), unmeasured_count=sin_medir)


def _ventana(**cambios: Any) -> BudgetWindow:
    base: dict[str, Any] = {
        "window_start": date(2026, 9, 16),
        "window_end": date(2026, 12, 15),
        "billable_spent_usd": Decimal("3.20"),
        "recording_reserve_usd": Decimal("0.225"),
        "recording_reserve_status": "measured",
        "updated_at": datetime(2026, 10, 1, tzinfo=UTC),
    }
    return BudgetWindow(**(base | cambios))


class _Registro:
    """Las consultas, sustituidas. Anota cuales se pidieron."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        ventana: BudgetWindow | None,
        suyos: frozenset[str] = frozenset(),
    ) -> None:
        self.llamadas: list[str] = []
        self._ventana = ventana
        self._suyos = suyos
        self.hoy = datetime.now(UTC).date()
        monkeypatch.setattr(repository, "load_window", self._load_window)
        monkeypatch.setattr(repository, "spend_by_provider", self._por_proveedor)
        monkeypatch.setattr(repository, "spend_by_model", self._por_modelo)
        monkeypatch.setattr(repository, "spend_by_day_and_activity", self._por_dia)
        monkeypatch.setattr(repository, "spend_per_call", self._llamadas)
        monkeypatch.setattr(repository, "spend_per_chat", self._chats)
        monkeypatch.setattr(repository, "recent_case_spend", self._casos)
        monkeypatch.setattr(repository, "unpriced_by_provider", self._sin_precio_por_proveedor)
        monkeypatch.setattr(repository, "unpriced_by_activity", self._sin_precio_por_actividad)
        monkeypatch.setattr(chat, "comparison_browsers", self._de_comparacion)
        monkeypatch.setattr(casos, "cases_by_id", self._leer_casos)
        monkeypatch.setattr(chat, "case_ids_of_visitor", self._del_navegador)
        monkeypatch.setattr(voz, "case_ids_of_visitor", self._del_navegador)

    async def _load_window(self, inicio: date, **_: Any) -> BudgetWindow | None:
        self.llamadas.append("load_window")
        return self._ventana

    async def _por_proveedor(self, **_: Any) -> Any:
        self.llamadas.append("spend_by_provider")
        return ((ProviderName.GEMINI, _total("1.25", 4)),)

    async def _por_modelo(self, **_: Any) -> Any:
        self.llamadas.append("spend_by_model")
        return (
            (ProviderName.GEMINI, "gemini-3.5-flash-lite", _total("1.25")),
            (ProviderName.GEMINI, "gemini-embedding-001", _total("0", 4)),
            (ProviderName.ANTHROPIC, "claude-haiku-5-5", _total("9.00")),
        )

    async def _por_dia(self, desde: date, **_: Any) -> Any:
        self.llamadas.append("spend_by_day_and_activity")
        return (
            (self.hoy - timedelta(days=40), SpendActivity.QUALITY_TESTS, _total("1.00")),
            (self.hoy - timedelta(days=1), SpendActivity.CALLS, _total("0.30")),
            (self.hoy, SpendActivity.CALLS, _total("0.20")),
            (self.hoy, SpendActivity.CHAT, _total("0.05", 2)),
        )

    async def _sin_precio_por_proveedor(self, **_: Any) -> Any:
        self.llamadas.append("unpriced_by_provider")
        return {ProviderName.GEMINI: UnpricedUsage(tokens=12345, uncounted=1, free_plan=True)}

    async def _sin_precio_por_actividad(self, desde: date, **_: Any) -> Any:
        self.llamadas.append("unpriced_by_activity")
        return {SpendActivity.CHAT: UnpricedUsage(tokens=800, free_plan=False)}

    async def _de_comparacion(self, **_: Any) -> dict[str, str]:
        self.llamadas.append("comparison_browsers")
        return {}

    async def _llamadas(self, **_: Any) -> Any:
        self.llamadas.append("spend_per_call")
        return repository.CountedSpend(count=5, total=_total("0.50"))

    async def _chats(self, **_: Any) -> Any:
        self.llamadas.append("spend_per_chat")
        return repository.CountedSpend(count=0, total=_total("0"))

    async def _casos(self, **_: Any) -> Any:
        self.llamadas.append("recent_case_spend")
        tenant = tenancy.available_ids()[0]
        ahora = datetime.now(UTC)
        return (
            repository.CaseProviderSpend(
                case_ref=CASO_ID,
                tenant_ref=tenant,
                last_at=ahora,
                provider=ProviderName.CARTESIA,
                total=_total("0.02"),
            ),
            repository.CaseProviderSpend(
                case_ref=CASO_ID,
                tenant_ref=tenant,
                last_at=ahora,
                provider=ProviderName.DEEPGRAM,
                total=_total("0.01", 1),
            ),
            # Un caso que ya no existe: lo borro el reinicio nocturno.
            repository.CaseProviderSpend(
                case_ref="case-borrado",
                tenant_ref=tenant,
                last_at=ahora,
                provider=ProviderName.ANTHROPIC,
                total=_total("0.09"),
            ),
        )

    async def _leer_casos(self, tenant_id: str, ids: Any) -> tuple[Case, ...]:
        ahora = datetime.now(UTC)
        return tuple(
            Case(
                case_id=CASO_ID,
                tenant_id=tenant_id,
                case_number=CaseNumber(prefix="STO", serial="482913"),
                record_type=RecordType.CLAIM,
                channel=Channel.VOICE,
                origin=Origin.PUBLIC_VOICE_CONSOLE,
                language="es",
                created_at=ahora,
                updated_at=ahora,
            )
            for caso in ids
            if caso == CASO_ID
        )

    async def _del_navegador(self, **_: Any) -> frozenset[str]:
        return self._suyos


def test_se_monta_como_superficie_publica_y_responde_sin_credencial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _Registro(monkeypatch, ventana=_ventana())
    (superficie,) = spend_routes.surfaces()
    with _cliente() as cliente:
        respuesta = cliente.get("/api/spend")

    assert superficie.public is True
    assert respuesta.status_code == 200
    # Lleva "tu caso", que es de este navegador: ningun intermediario lo guarda.
    assert respuesta.headers["cache-control"] == "private, no-store"


def test_la_raiz_de_composicion_lo_monta_sin_condicion() -> None:
    declarado = {modulo.module: modulo for modulo in composition.MODULOS}
    assert declarado["untangle.server.spend_routes"].requires_setting is None


def test_las_actividades_suman_todos_los_dias_y_la_grafica_solo_los_ultimos_30(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registro = _Registro(monkeypatch, ventana=_ventana())
    with _cliente() as cliente:
        cuerpo = cliente.get("/api/spend").json()

    actividades = {a["activity"]: a["total"] for a in cuerpo["by_activity"]}
    # Las llamadas de dos dias se suman; las pruebas de hace 40 dias cuentan en el
    # total aunque ya no salgan en la grafica.
    assert actividades["calls"] == {"measured_usd": "0.50", "unmeasured_count": 0}
    assert actividades["quality_tests"] == {"measured_usd": "1.00", "unmeasured_count": 0}
    assert cuerpo["total"] == {"measured_usd": "1.55", "unmeasured_count": 2}

    dias = cuerpo["by_day"]
    assert len(dias) == spend_routes.DAYS
    assert dias[-1]["day"] == registro.hoy.isoformat()
    assert {a["activity"] for a in dias[-1]["activities"]} == {"calls", "chat"}
    # Un dia sin gasto esta en la lista, vacio: la grafica no salta dias.
    assert dias[0]["activities"] == []
    assert all("quality_tests" not in str(d) for d in dias)


def test_cada_proveedor_dice_con_que_modelos_trabaja_y_solo_los_suyos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _Registro(monkeypatch, ventana=_ventana())
    with _cliente() as cliente:
        cuerpo = cliente.get("/api/spend").json()

    (gemini,) = cuerpo["by_provider"]
    # El de Anthropic no se le cuelga a Gemini, y el que no tiene precio viaja con
    # su conteo y no como cero a secas.
    assert [m["model"] for m in gemini["models"]] == [
        "gemini-3.5-flash-lite",
        "gemini-embedding-001",
    ]
    assert gemini["models"][1]["total"] == {"measured_usd": "0", "unmeasured_count": 4}


def test_los_promedios_viajan_como_total_y_cuantos(monkeypatch: pytest.MonkeyPatch) -> None:
    _Registro(monkeypatch, ventana=_ventana())
    with _cliente() as cliente:
        cuerpo = cliente.get("/api/spend").json()

    assert cuerpo["calls"] == {"count": 5, "total": {"measured_usd": "0.50", "unmeasured_count": 0}}
    assert cuerpo["chats"]["count"] == 0


def test_los_casos_se_describen_y_no_se_identifican(monkeypatch: pytest.MonkeyPatch) -> None:
    _Registro(monkeypatch, ventana=_ventana())
    with _cliente() as cliente:
        respuesta = cliente.get("/api/spend")
    cuerpo = respuesta.json()

    # El borrado no sale; el que existe sale con lo que fue y lo que costo.
    (caso,) = cuerpo["cases"]
    assert caso["record_type"] == "claim"
    assert caso["channel"] == "voice"
    assert caso["total"] == {"measured_usd": "0.03", "unmeasured_count": 1}
    assert [p["provider"] for p in caso["by_provider"]] == ["cartesia", "deepgram"]
    # Ni su identificador ni su numero, en ninguna parte de la respuesta.
    assert CASO_ID not in respuesta.text
    assert CASO_NUMERO not in respuesta.text
    assert caso["key"] == "0"


def test_el_caso_de_este_navegador_sale_como_suyo_y_sin_galleta_ninguno(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _Registro(monkeypatch, ventana=_ventana(), suyos=frozenset({CASO_ID}))
    with _cliente(untangle_visitor="clave-del-navegador") as cliente:
        con = cliente.get("/api/spend").json()
    with _cliente() as cliente:
        sin = cliente.get("/api/spend").json()

    assert con["cases"][0]["yours"] is True
    assert sin["cases"][0]["yours"] is False


def test_sin_ventana_el_tablero_dice_nulo_y_no_inventa_una_en_cero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _Registro(monkeypatch, ventana=None)
    with _cliente() as cliente:
        cuerpo = cliente.get("/api/spend").json()

    assert cuerpo["window"] is None
    assert cuerpo["alert_sent_at"] is None


def test_recargar_no_repite_las_consultas_mientras_dura_lo_guardado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registro = _Registro(monkeypatch, ventana=_ventana())
    with _cliente() as cliente:
        cliente.get("/api/spend")
        cliente.get("/api/spend")

    assert registro.llamadas.count("load_window") == 1


# --- Lo que no tiene precio se muestra en tokens (2026-10-11) ----------------------


def test_los_tokens_sin_precio_viajan_por_proveedor_y_por_actividad_y_el_resto_sin_ellos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _Registro(monkeypatch, ventana=_ventana())
    with _cliente() as cliente:
        cuerpo = cliente.get("/api/spend").json()

    (gemini,) = cuerpo["by_provider"]
    assert gemini["unpriced"] == {"tokens": 12345, "uncounted": 1, "free_plan": True}
    por_actividad = {a["activity"]: a["unpriced"] for a in cuerpo["by_activity"]}
    # Sin plan gratuito donde el dato no lo respalda, y en cero donde no hay nada.
    assert por_actividad["chat"] == {"tokens": 800, "uncounted": 0, "free_plan": False}
    assert por_actividad["calls"] == {"tokens": 0, "uncounted": 0, "free_plan": False}
    # El dinero no se mezcla con los tokens: el total sigue siendo el de siempre.
    assert cuerpo["total"] == {"measured_usd": "1.55", "unmeasured_count": 2}


def test_los_tokens_sin_precio_de_un_caso_son_la_suma_de_sus_proveedores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registro = _Registro(monkeypatch, ventana=_ventana())
    original = registro._casos

    async def con_tokens(**kw: Any) -> Any:
        filas = await original(**kw)
        return tuple(
            fila.model_copy(
                update={"unpriced": UnpricedUsage(tokens=100, uncounted=0, free_plan=True)}
            )
            if fila.case_ref == CASO_ID
            else fila
            for fila in filas
        )

    monkeypatch.setattr(repository, "recent_case_spend", con_tokens)
    with _cliente() as cliente:
        (caso,) = cliente.get("/api/spend").json()["cases"]

    assert [p["unpriced"]["tokens"] for p in caso["by_provider"]] == [100, 100]
    assert caso["unpriced"] == {"tokens": 200, "uncounted": 0, "free_plan": True}


# --- Una comparacion es una sola cosa (2026-10-11) ---------------------------------

#: Lo que solo vale para firmar en la prueba: el resumen de un navegador no sale.
NAVEGADOR_A = "resumen-secreto-del-navegador-a-91ce"
NAVEGADOR_B = "resumen-secreto-del-navegador-b-27fd"


class _RegistroDeComparaciones(_Registro):
    """Casos sembrados a mano: quien los abrio y desde que vista nacieron."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        casos_: dict[str, tuple[str, datetime]],
        navegadores: dict[str, str],
        suyos: frozenset[str] = frozenset(),
    ) -> None:
        self.casos_ = casos_
        self.navegadores = navegadores
        self.clave_pedida: str | None = None
        super().__init__(monkeypatch, ventana=_ventana(), suyos=suyos)

    async def _casos(self, **_: Any) -> Any:
        return tuple(
            repository.CaseProviderSpend(
                case_ref=case_id,
                tenant_ref=tenant,
                last_at=cuando,
                provider=ProviderName.GEMINI,
                total=_total("0", 3),
                unpriced=UnpricedUsage(tokens=1000, uncounted=0, free_plan=True),
            )
            for case_id, (tenant, cuando) in self.casos_.items()
        )

    async def _leer_casos(self, tenant_id: str, ids: Any) -> tuple[Case, ...]:
        return tuple(
            Case(
                case_id=case_id,
                tenant_id=tenant_id,
                case_number=CaseNumber(prefix="STO", serial="482913"),
                record_type=RecordType.COVERAGE_INQUIRY,
                channel=Channel.CHAT,
                origin=Origin.PUBLIC_CHAT,
                language="es",
                created_at=self.casos_[case_id][1],
                updated_at=self.casos_[case_id][1],
            )
            for case_id in ids
            if case_id in self.casos_
        )

    async def _de_comparacion(self, **pedido: Any) -> dict[str, str]:
        self.clave_pedida = pedido["catalog_key"]
        return {c: self.navegadores[c] for c in pedido["case_ids"] if c in self.navegadores}


def _sembrar_dos_comparaciones(
    monkeypatch: pytest.MonkeyPatch, *, suyos: frozenset[str] = frozenset()
) -> _RegistroDeComparaciones:
    """El navegador A comparo con las tres; el B, con dos; y hay un chat suelto."""
    uno, dos, tres = sorted(tenancy.available_ids())[:3]
    base = datetime.now(UTC) - timedelta(hours=2)
    minuto = timedelta(minutes=1)
    return _RegistroDeComparaciones(
        monkeypatch,
        casos_={
            "a-uno": (uno, base),
            "a-dos": (dos, base + minuto),
            "a-tres": (tres, base + 2 * minuto),
            "b-uno": (uno, base + 10 * minuto),
            "b-dos": (dos, base + 11 * minuto),
            "suelto": (uno, base + 20 * minuto),
        },
        navegadores={
            "a-uno": NAVEGADOR_A,
            "a-dos": NAVEGADOR_A,
            "a-tres": NAVEGADOR_A,
            "b-uno": NAVEGADOR_B,
            "b-dos": NAVEGADOR_B,
        },
        suyos=suyos,
    )


def test_las_consultas_de_un_mismo_clic_en_comparar_salen_como_una_sola_entrada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registro = _sembrar_dos_comparaciones(monkeypatch)
    with _cliente() as cliente:
        respuesta = cliente.get("/api/spend")
    cuerpo = respuesta.json()

    # Dos comparaciones --una por navegador-- y el chat que no salio de ninguna.
    assert [len(c["parts"]) for c in cuerpo["comparisons"]] == [3, 2]
    assert [c["record_type"] for c in cuerpo["cases"]] == ["coverage_inquiry"]
    assert len(cuerpo["cases"]) == 1
    # El dato que las ata es la divulgacion de la comparacion, no la hora.
    assert registro.clave_pedida == opening.COMPARISON_DISCLOSURE_BLOCK

    primera = cuerpo["comparisons"][0]
    assert primera["total"] == {"measured_usd": "0", "unmeasured_count": 9}
    assert primera["unpriced"] == {"tokens": 3000, "uncounted": 0, "free_plan": True}
    assert sorted(p["tenant_id"] for p in primera["parts"]) == sorted(tenancy.available_ids()[:3])
    # Ni el resumen del navegador ni ningun identificador de caso.
    for marca in (NAVEGADOR_A, NAVEGADOR_B, "a-uno", "b-dos", "suelto"):
        assert marca not in respuesta.text, marca
    assert [c["key"] for c in cuerpo["comparisons"]] == ["c0", "c1"]


def test_un_navegador_que_compara_otra_vez_con_casos_nuevos_abre_otra_comparacion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uno, dos, _ = sorted(tenancy.available_ids())[:3]
    base = datetime.now(UTC) - timedelta(hours=2)
    _RegistroDeComparaciones(
        monkeypatch,
        casos_={
            "ronda-1-uno": (uno, base),
            "ronda-1-dos": (dos, base),
            "ronda-2-uno": (uno, base + timedelta(hours=1)),
        },
        navegadores={
            "ronda-1-uno": NAVEGADOR_A,
            "ronda-1-dos": NAVEGADOR_A,
            "ronda-2-uno": NAVEGADOR_A,
        },
    )
    with _cliente() as cliente:
        cuerpo = cliente.get("/api/spend").json()

    # Dos casos de la misma aseguradora no pueden ser del mismo clic.
    assert sorted(len(c["parts"]) for c in cuerpo["comparisons"]) == [1, 2]
    assert cuerpo["cases"] == []


def test_la_comparacion_es_suya_si_alguno_de_sus_casos_lo_es_y_sale_marcada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _sembrar_dos_comparaciones(monkeypatch, suyos=frozenset({"a-dos"}))
    with _cliente(untangle_visitor="clave-del-navegador") as cliente:
        con = cliente.get("/api/spend").json()
    spend_routes.reset_cache()
    with _cliente() as cliente:
        sin = cliente.get("/api/spend").json()

    assert [c["yours"] for c in con["comparisons"]] == [True, False]
    assert not any(c["yours"] for c in sin["comparisons"])
    # El caso suelto no es de nadie: la marca no se pega a lo que no es suyo.
    assert con["cases"][0]["yours"] is False


def test_la_comparacion_empieza_cuando_empezo_su_primer_caso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registro = _sembrar_dos_comparaciones(monkeypatch)
    with _cliente() as cliente:
        cuerpo = cliente.get("/api/spend").json()

    primera = cuerpo["comparisons"][0]
    esperado = registro.casos_["a-uno"][1].isoformat().replace("+00:00", "Z")
    assert primera["started_at"] == esperado


# --- BR3.3: el tablero no contiene ningun umbral ------------------------------------

#: Lo que solo puede aparecer en un sitio que **decide** cortar o avisar. Si alguno
#: aparece en el tablero, hay un segundo umbral que un dia discrepa del primero.
NOMBRES_DE_DECISION = (
    "cap_usd",
    "alert_usd",
    "crosses_alert",
    "check_quota",
    "consume_quota",
    "release_call_quota",
    "reserve_primary_voice",
    "public_remaining",
    "recording_remaining",
)


def test_el_tablero_no_nombra_ninguna_de_las_piezas_que_deciden_el_corte() -> None:
    arbol = ast.parse(inspect.getsource(spend_routes))
    # Se miran los **nombres del codigo**, no la documentacion.
    usados = {nodo.id for nodo in ast.walk(arbol) if isinstance(nodo, ast.Name)} | {
        nodo.attr for nodo in ast.walk(arbol) if isinstance(nodo, ast.Attribute)
    }

    assert sorted(usados & set(NOMBRES_DE_DECISION)) == []


def test_el_tablero_no_compara_ningun_importe() -> None:
    """Ninguna comparacion de orden fuera del reloj de lo guardado."""
    arbol = ast.parse(inspect.getsource(spend_routes))
    comparaciones = [
        ast.unparse(nodo)
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Compare)
        and any(isinstance(operador, (ast.Gt, ast.GtE, ast.Lt, ast.LtE)) for operador in nodo.ops)
        and "CACHE_SECONDS" not in ast.unparse(nodo)
    ]
    assert comparaciones == []


def test_el_tablero_solo_lee_el_registro() -> None:
    arbol = ast.parse(inspect.getsource(spend_routes))
    usadas = {
        nodo.attr
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Attribute)
        and isinstance(nodo.value, ast.Name)
        and nodo.value.id == "repository"
    }

    assert usadas == {
        "CaseProviderSpend",
        "load_window",
        "recent_case_spend",
        "spend_by_day_and_activity",
        "spend_by_model",
        "spend_by_provider",
        "spend_per_call",
        "spend_per_chat",
        "unpriced_by_activity",
        "unpriced_by_provider",
    }


def test_el_estado_sale_de_la_funcion_de_la_contabilidad() -> None:
    """El estado del techo lo calcula `budget.state`, la misma que consulta el corte."""
    arbol = ast.parse(inspect.getsource(spend_routes))
    llamadas = {
        f"{nodo.func.value.id}.{nodo.func.attr}"
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Call)
        and isinstance(nodo.func, ast.Attribute)
        and isinstance(nodo.func.value, ast.Name)
    }
    assert "budget.state" in llamadas
