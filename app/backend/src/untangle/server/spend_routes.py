"""El tablero de gasto: `GET /api/spend`, publico y sin credencial (U22, 2026-10-09).

Era un panel del operador, con su clave. Miguel decidio publicarlo: la telemetria
es uno de los tres atractivos del proyecto --con el chat y las llamadas-- y la
gracia es que cualquiera vea cuanto ha costado. Se publica con la regla que el
proyecto ya tenia para toda superficie publica (Refined Mockups, Q7): **recuentos,
totales y distribuciones, nunca el numero ni el identificador de un caso de
visitante**. Por eso la lista de casos nombra cada uno por lo que fue --tipo,
canal, aseguradora y hora--, su clave es solo su posicion en la lista, y el caso
del propio navegador sale marcado como suyo (decision de Miguel del 2026-10-09).

## Lo que el tablero no hace

**No decide cortar** (BR3.3). El estado --`ok`, `alerted`, `exhausted`, `unknown`--
lo calcula `budget.state`, la misma funcion que consulta el corte; aqui se muestra
lo que ya esta decidido.

**No descarta lo no medido.** Cada total viaja como `SpendTotal`, con su conteo de
llamadas sin valorar dentro del tipo: publicar el total sin decir cuantas no se
midieron exige desarmar el tipo a proposito.

**No gasta.** Lee el registro de gasto y los casos; no llama a ningun proveedor.
Lo comun a todos los visitantes se guarda unos segundos, para que recargar la
pagina no sea una consulta nueva cada vez.

## Lo que se muestra cuando no hay precio (2026-10-11)

"Sin precio" no es "sin dato": el proveedor reporta cuantos tokens conto aunque la
tabla no tenga la linea de ese modelo. Cada total lleva al lado `unpriced`, con esos
tokens, para que la pantalla diga cuanto se consumio en vez de callar. Sigue sin
sumarse a ningun importe: el dinero y los tokens no se mezclan.

## Una comparacion es una sola cosa (2026-10-11)

Un clic en "Comparar" abre un caso en cada aseguradora, y desde fuera parecen tres
consultas sueltas. Se agrupan por dos datos que ya estan guardados, no por
coincidencia de hora: que el caso nacio de la vista de comparacion (la divulgacion
que quedo registrada al abrirlo) y que lo abrio el mismo navegador. Un navegador
tiene una conversacion por aseguradora a la vez, asi que sus casos de comparacion
son, a lo sumo, uno por aseguradora en cada ronda. El resumen del navegador nunca
sale de aqui: la comparacion se identifica por su posicion en la respuesta.

## El enlace a Langfuse (2026-10-14)

Las trazas de cada turno salen a Langfuse y cada una es publica por su direccion, pero el
proyecto entero pide iniciar sesion y los visitantes no tienen cuenta: solo se puede abrir
**una traza por su direccion**. Por eso el tablero ofrece, a quien llega, **las de su propio
navegador** y a nadie mas: `SpendPanel.langfuse_url` es la traza `ready` mas reciente entre
los casos de este navegador, y `CaseSpendItem.trace_url` la de ese caso, solo si es suyo.

La regla de "hay enlace" es la de la bandeja (`links.summary_url`: solo con el resumen
`ready`, y nada si Langfuse no esta configurado o no se supo el proyecto). El dueno se
comprueba **dos veces**: el caso sale de las consultas por la clave del navegador y el resumen
tambien se compara contra su resumen (`trace_summaries_for_visitor`), asi que una URL no sale
por un solo descuido. Se lee **una vez por aseguradora** y no una por fila. Y como el cuerpo
va con `Cache-Control: private, no-store`, ningun intermediario se la puede servir a otro.
"""

from __future__ import annotations

import asyncio
import time
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, NamedTuple, Self

from fastapi import APIRouter, Cookie, Response
from pydantic import Field, model_validator

from untangle.base import Frozen, ProviderName
from untangle.case_record import api as casos
from untangle.chat import opening
from untangle.chat import session as chat
from untangle.server.problems import problem_responses
from untangle.surface_spec import SurfaceId, SurfaceProbe, SurfaceSpec
from untangle.telemetry.spend import api as spend
from untangle.telemetry.spend import budget, repository
from untangle.telemetry.spend.models import BudgetState, SpendActivity, SpendTotal, UnpricedUsage
from untangle.telemetry.traces import api as trazas
from untangle.telemetry.traces import links as trace_links
from untangle.tenancy import api as tenancy
from untangle.voice import api as voz

#: Lo que la sonda tiene de plazo. Es una lectura de fila unica.
PROBE_TIMEOUT_MS = 200

#: Cuantos dias muestra la grafica.
DAYS = 30
#: Cuantos casos ofrece la lista.
CASES = 30
#: Cuanto se guarda lo comun a todos los visitantes. Corto: quien acaba de
#: terminar una llamada quiere verla en el tablero.
CACHE_SECONDS = 15.0

_CERO = SpendTotal(measured_usd=Decimal(0), unmeasured_count=0)


# --- Lo que se devuelve ---------------------------------------------------------


class ActivitySpend(Frozen):
    """Lo que costo una actividad: llamadas, chat, pruebas, lectura de polizas."""

    activity: SpendActivity
    total: SpendTotal
    #: Los tokens de lo que no tiene precio publicado. Aditivo.
    unpriced: UnpricedUsage = Field(default_factory=UnpricedUsage)


class DaySpend(Frozen):
    """Un dia de la grafica, en UTC, con lo que costo cada actividad ese dia."""

    day: date
    activities: tuple[ActivitySpend, ...]


class ModelSpend(Frozen):
    """Lo que costo un modelo, con su identificador exacto: el que se cobro."""

    model: str
    total: SpendTotal


class ProviderSpend(Frozen):
    """Lo que costo un proveedor, con lo que no se pudo medir."""

    provider: ProviderName
    total: SpendTotal
    #: Con que modelos trabaja ese proveedor aqui, de mayor a menor gasto. Vacio en
    #: el desglose de un caso, donde lo que importa es quien cobro.
    models: tuple[ModelSpend, ...] = ()
    #: Los tokens de lo que no tiene precio publicado. Aditivo.
    unpriced: UnpricedUsage = Field(default_factory=UnpricedUsage)


class CountedSpend(Frozen):
    """Lo que costaron todas las llamadas (o todos los chats) y cuantos fueron.

    El promedio lo saca la pantalla: asi puede decir sobre cuantos se calculo, y
    con cero no inventa un promedio.
    """

    count: int
    total: SpendTotal


class CaseSpendItem(Frozen):
    """Un caso de la lista, **descrito y no identificado**.

    No lleva el identificador ni el numero del caso, y no puede: es una superficie
    publica y los casos son de personas que usaron la demostracion. `key` es su
    posicion en esta respuesta y no sirve para nada fuera de ella.
    """

    key: str
    tenant_id: str
    record_type: str
    channel: str
    started_at: datetime
    yours: bool
    total: SpendTotal
    by_provider: tuple[ProviderSpend, ...]
    #: Los tokens de lo que no tiene precio publicado. Aditivo.
    unpriced: UnpricedUsage = Field(default_factory=UnpricedUsage)
    #: Donde abrir la traza de este caso en Langfuse. **Solo en el caso de este navegador**
    #: y solo con la traza lista: en el de cualquier otro, siempre `None`. Aditivo.
    trace_url: str | None = None

    @model_validator(mode="after")
    def _la_traza_es_de_quien_la_pide(self) -> Self:
        if self.trace_url is not None and not self.yours:
            msg = (
                "un caso que no es de este navegador no lleva el enlace a su traza: las "
                "trazas de Langfuse son publicas por su direccion y quien llega no puede "
                "recibir la de otro visitante"
            )
            raise ValueError(msg)
        return self


class ComparisonPart(Frozen):
    """Lo que cobro una aseguradora dentro de una comparacion."""

    tenant_id: str
    total: SpendTotal
    unpriced: UnpricedUsage = Field(default_factory=UnpricedUsage)


class ComparisonSpendItem(Frozen):
    """Las consultas de un mismo clic en "Comparar", **como una sola entrada**.

    Como el caso, se describe y no se identifica: `key` es su posicion entre las
    comparaciones de esta respuesta. `started_at` es el del primer caso del grupo.
    """

    key: str
    started_at: datetime
    yours: bool
    total: SpendTotal
    unpriced: UnpricedUsage = Field(default_factory=UnpricedUsage)
    parts: tuple[ComparisonPart, ...]


class SpendPanel(Frozen):
    """El tablero entero.

    **`window` admite nulo y eso es un estado, no un hueco**: sin fila de la
    ventana no hay acumulado que mostrar, y escribir un cero diria "se midio y dio
    cero".
    """

    window: BudgetState | None
    alert_sent_at: datetime | None
    #: Todo lo gastado desde que empezo el proyecto, facturable o no.
    total: SpendTotal
    by_activity: tuple[ActivitySpend, ...]
    by_provider: tuple[ProviderSpend, ...]
    #: Los ultimos `DAYS` dias, todos, incluidos los que no gastaron nada.
    by_day: tuple[DaySpend, ...]
    calls: CountedSpend
    chats: CountedSpend
    #: Los casos que **no** salieron de una comparacion; los que si, van en
    #: `comparisons`, cada grupo como una sola entrada.
    cases: tuple[CaseSpendItem, ...]
    comparisons: tuple[ComparisonSpendItem, ...] = ()
    #: La traza lista mas reciente entre los casos **de este navegador**, para abrirla en
    #: Langfuse; `None` si no tiene ninguna, si Langfuse no esta configurado o si no se
    #: sabe el proyecto. Nunca la de otro visitante. Aditivo.
    langfuse_url: str | None = None


# --- El armado ----------------------------------------------------------------


class _Caso(Frozen):
    """Un caso de la lista antes de saber si es del visitante."""

    case_id: str
    tenant_id: str
    record_type: str
    channel: str
    started_at: datetime
    total: SpendTotal
    by_provider: tuple[ProviderSpend, ...]
    unpriced: UnpricedUsage


class _Comparacion(Frozen):
    """Los casos de un mismo clic en "Comparar", de la primera a la ultima aseguradora."""

    members: tuple[_Caso, ...]


class _Enlaces(NamedTuple):
    """Las trazas de Langfuse que este navegador puede abrir."""

    #: Del caso a la direccion de su traza, solo los casos de este navegador.
    por_caso: Mapping[str, str]
    #: La de la traza lista mas reciente de todas, o `None`.
    ultimo: str | None


_SIN_ENLACES = _Enlaces(por_caso={}, ultimo=None)


class _Comun(Frozen):
    """Lo que ven todos los visitantes igual."""

    panel: SpendPanel
    entradas: tuple[_Caso | _Comparacion, ...]


_guardado: tuple[float, _Comun] | None = None


def _sumar(totales: list[SpendTotal]) -> SpendTotal:
    resultado = _CERO
    for total in totales:
        resultado = resultado + total
    return resultado


def _sumar_sin_precio(partes: Sequence[UnpricedUsage]) -> UnpricedUsage:
    resultado = UnpricedUsage()
    for parte in partes:
        resultado = resultado + parte
    return resultado


def _dias(
    filas: tuple[tuple[date, SpendActivity, SpendTotal], ...], hoy: date
) -> tuple[DaySpend, ...]:
    por_dia: dict[date, list[ActivitySpend]] = defaultdict(list)
    for dia, actividad, total in filas:
        por_dia[dia].append(ActivitySpend(activity=actividad, total=total))
    primero = hoy - timedelta(days=DAYS - 1)
    return tuple(
        DaySpend(day=dia, activities=tuple(por_dia.get(dia, ())))
        for dia in (primero + timedelta(days=n) for n in range(DAYS))
    )


def _agrupar(
    casos_: Sequence[_Caso], navegadores: Mapping[str, str]
) -> tuple[_Caso | _Comparacion, ...]:
    """Une en una comparacion los casos que abrio un mismo navegador desde esa vista.

    `navegadores` solo trae los casos que nacieron de la comparacion. Dentro de un
    navegador, el primer caso de cada aseguradora es la ronda 0, el segundo la 1, y
    asi: una ronda tiene a lo sumo un caso por aseguradora. Conserva el orden de la
    lista: cada comparacion ocupa el lugar de su primer caso.
    """
    rondas: dict[tuple[str, int], list[_Caso]] = defaultdict(list)
    de_cada_caso: dict[str, tuple[str, int]] = {}
    contados: Counter[tuple[str, str]] = Counter()
    de_comparacion = (caso for caso in casos_ if caso.case_id in navegadores)
    for caso in sorted(de_comparacion, key=lambda c: c.started_at):
        navegador = navegadores[caso.case_id]
        ronda = contados[(navegador, caso.tenant_id)]
        contados[(navegador, caso.tenant_id)] += 1
        rondas[(navegador, ronda)].append(caso)
        de_cada_caso[caso.case_id] = (navegador, ronda)

    resultado: list[_Caso | _Comparacion] = []
    puestas: set[tuple[str, int]] = set()
    for caso in casos_:
        clave = de_cada_caso.get(caso.case_id)
        if clave is None:
            resultado.append(caso)
        elif clave not in puestas:
            puestas.add(clave)
            resultado.append(_Comparacion(members=tuple(rondas[clave])))
    return tuple(resultado)


async def _de_comparacion(lista: Sequence[_Caso]) -> dict[str, str]:
    """Del caso al resumen de su navegador, solo para los que nacieron de la comparacion."""
    clave = opening.disclosure_key_of(opening.Surface.COMPARISON)
    por_aseguradora: dict[str, list[str]] = defaultdict(list)
    for caso in lista:
        por_aseguradora[caso.tenant_id].append(caso.case_id)
    grupos = await asyncio.gather(
        *(
            chat.comparison_browsers(
                tenant_id=tenancy.require(tenant).tenant_id, case_ids=ids, catalog_key=clave
            )
            for tenant, ids in por_aseguradora.items()
        )
    )
    return {caso: navegador for grupo in grupos for caso, navegador in grupo.items()}


async def _casos() -> tuple[_Caso | _Comparacion, ...]:
    """Los casos recientes que todavia existen, descritos por lo que fueron."""
    filas = await repository.recent_case_spend()
    por_caso: dict[str, list[repository.CaseProviderSpend]] = defaultdict(list)
    for fila in filas:
        por_caso[fila.case_ref].append(fila)

    conocidas = set(tenancy.available_ids())
    por_aseguradora: dict[str, list[str]] = defaultdict(list)
    for case_ref, partes in por_caso.items():
        if partes[0].tenant_ref in conocidas:
            por_aseguradora[partes[0].tenant_ref].append(case_ref)
    leidos = await asyncio.gather(
        *(
            casos.cases_by_id(tenancy.require(tenant).tenant_id, ids)
            for tenant, ids in por_aseguradora.items()
        )
    )
    existentes = {caso.case_id: caso for grupo in leidos for caso in grupo}

    resultado: list[_Caso] = []
    for case_ref, partes in por_caso.items():
        caso = existentes.get(case_ref)
        if caso is None:
            # Lo borro el reinicio nocturno, o no era un caso de nadie.
            continue
        proveedores = tuple(
            ProviderSpend(provider=parte.provider, total=parte.total, unpriced=parte.unpriced)
            for parte in partes
        )
        resultado.append(
            _Caso(
                case_id=case_ref,
                tenant_id=caso.tenant_id,
                record_type=caso.record_type.value,
                channel=caso.channel.value,
                started_at=caso.created_at,
                total=_sumar([p.total for p in proveedores]),
                by_provider=proveedores,
                unpriced=_sumar_sin_precio([p.unpriced for p in proveedores]),
            )
        )
    entradas = _agrupar(resultado, await _de_comparacion(resultado))
    return entradas[:CASES]


async def _comun(hoy: date) -> _Comun:
    inicio = spend.current_runtime().window_start
    desde = min(inicio, hoy - timedelta(days=DAYS - 1))
    # En tres grupos: `gather` solo conserva el tipo de cada resultado hasta seis.
    (
        (ventana, filas, proveedores, modelos),
        (llamadas, chats, lista),
        (sin_precio_de_proveedor, sin_precio_de_actividad),
    ) = await asyncio.gather(
        asyncio.gather(
            repository.load_window(inicio),
            repository.spend_by_day_and_activity(desde),
            repository.spend_by_provider(),
            repository.spend_by_model(),
        ),
        asyncio.gather(repository.spend_per_call(), repository.spend_per_chat(), _casos()),
        asyncio.gather(repository.unpriced_by_provider(), repository.unpriced_by_activity(desde)),
    )
    por_actividad: dict[SpendActivity, list[SpendTotal]] = defaultdict(list)
    for _dia, actividad, total in filas:
        por_actividad[actividad].append(total)
    actividades = tuple(
        ActivitySpend(
            activity=actividad,
            total=_sumar(por_actividad[actividad]),
            unpriced=sin_precio_de_actividad.get(actividad, UnpricedUsage()),
        )
        for actividad in SpendActivity
        if actividad in por_actividad
    )
    panel = SpendPanel(
        window=budget.state(ventana) if ventana is not None else None,
        alert_sent_at=ventana.alert_sent_at if ventana is not None else None,
        total=_sumar([a.total for a in actividades]),
        by_activity=actividades,
        by_provider=tuple(
            ProviderSpend(
                provider=proveedor,
                total=total,
                models=tuple(
                    ModelSpend(model=modelo, total=del_modelo)
                    for de, modelo, del_modelo in modelos
                    if de is proveedor
                ),
                unpriced=sin_precio_de_proveedor.get(proveedor, UnpricedUsage()),
            )
            for proveedor, total in proveedores
        ),
        by_day=_dias(filas, hoy),
        calls=CountedSpend(count=llamadas.count, total=llamadas.total),
        chats=CountedSpend(count=chats.count, total=chats.total),
        cases=(),
    )
    return _Comun(panel=panel, entradas=lista)


async def _lo_comun() -> _Comun:
    global _guardado
    ahora = time.monotonic()
    if _guardado is not None and ahora - _guardado[0] < CACHE_SECONDS:
        return _guardado[1]
    comun = await _comun(datetime.now(UTC).date())
    _guardado = (ahora, comun)
    return comun


def reset_cache() -> None:
    """Las pruebas lo vacian para no ver el tablero de la anterior."""
    global _guardado
    _guardado = None


def _planos(entradas: Sequence[_Caso | _Comparacion]) -> tuple[_Caso, ...]:
    """Todos los casos, tambien los que van dentro de una comparacion."""
    return tuple(
        caso
        for entrada in entradas
        for caso in (entrada.members if isinstance(entrada, _Comparacion) else (entrada,))
    )


async def _de_este_navegador(lista: Sequence[_Caso], visitor_key: str | None) -> dict[str, str]:
    """Los casos que abrio este navegador, por chat o por llamada, con su aseguradora.

    Mira todas las aseguradoras de la lista y trae **todos** los casos del navegador en
    ellas, salgan o no en la lista: el enlace a "tu ultima conversacion" no tiene por que
    depender de que esa conversacion siga entre las treinta mas recientes del tablero.
    """
    if not visitor_key:
        return {}
    resumen = tenancy.visitor_key_digest(visitor_key)
    consultas = [
        (tenant, consulta)
        for tenant in {caso.tenant_id for caso in lista}
        for consulta in (chat.case_ids_of_visitor, voz.case_ids_of_visitor)
    ]
    grupos = await asyncio.gather(
        *(
            consulta(tenant_id=tenancy.require(tenant).tenant_id, visitor_key_digest=resumen)
            for tenant, consulta in consultas
        )
    )
    return {
        caso: tenant
        for (tenant, _consulta), grupo in zip(consultas, grupos, strict=True)
        for caso in grupo
    }


async def _enlaces_de(suyos: Mapping[str, str], visitor_key: str | None) -> _Enlaces:
    """Las trazas de Langfuse de los casos de este navegador, con una lectura por aseguradora.

    Solo pregunta por los casos que ya son suyos, y el almacen compara ademas el dueno de
    cada resumen: una traza que no sea de esta clave no llega a este punto. Sin Langfuse
    configurado no hace ni una lectura. La mas reciente se decide por la fecha del resumen,
    con el identificador de la traza para desempatar.
    """
    if not suyos or not visitor_key or not trace_links.available():
        return _SIN_ENLACES
    resumen = tenancy.visitor_key_digest(visitor_key)
    por_aseguradora: dict[str, list[str]] = defaultdict(list)
    for caso, tenant in suyos.items():
        por_aseguradora[tenant].append(caso)
    grupos = await asyncio.gather(
        *(
            trazas.trace_summaries_for_visitor(
                ids, tenant_id=tenancy.require(tenant).tenant_id, visitor_key_hash=resumen
            )
            for tenant, ids in por_aseguradora.items()
        )
    )
    listas = [
        (traza, direccion)
        for grupo in grupos
        for traza in grupo.values()
        if (direccion := trace_links.summary_url(traza)) is not None
    ]
    if not listas:
        return _SIN_ENLACES
    _traza, ultimo = max(listas, key=lambda par: (par[0].created_at, par[0].trace_id))
    return _Enlaces(
        por_caso={traza.case_id: direccion for traza, direccion in listas}, ultimo=ultimo
    )


def _item_de_comparacion(
    comparacion: _Comparacion, *, key: str, suyos: Mapping[str, str]
) -> ComparisonSpendItem:
    miembros = comparacion.members
    return ComparisonSpendItem(
        key=key,
        started_at=min(caso.started_at for caso in miembros),
        yours=any(caso.case_id in suyos for caso in miembros),
        total=_sumar([caso.total for caso in miembros]),
        unpriced=_sumar_sin_precio([caso.unpriced for caso in miembros]),
        parts=tuple(
            ComparisonPart(tenant_id=caso.tenant_id, total=caso.total, unpriced=caso.unpriced)
            for caso in miembros
        ),
    )


async def build_panel(visitor_key: str | None = None) -> SpendPanel:
    """El tablero, con los casos de este navegador marcados como suyos y con sus trazas."""
    comun = await _lo_comun()
    suyos = await _de_este_navegador(_planos(comun.entradas), visitor_key)
    enlaces = await _enlaces_de(suyos, visitor_key)
    sueltos: list[CaseSpendItem] = []
    comparaciones: list[ComparisonSpendItem] = []
    for entrada in comun.entradas:
        if isinstance(entrada, _Comparacion):
            comparaciones.append(
                _item_de_comparacion(entrada, key=f"c{len(comparaciones)}", suyos=suyos)
            )
        else:
            suyo = entrada.case_id in suyos
            sueltos.append(
                CaseSpendItem(
                    key=str(len(sueltos)),
                    tenant_id=entrada.tenant_id,
                    record_type=entrada.record_type,
                    channel=entrada.channel,
                    started_at=entrada.started_at,
                    yours=suyo,
                    total=entrada.total,
                    by_provider=entrada.by_provider,
                    unpriced=entrada.unpriced,
                    trace_url=enlaces.por_caso.get(entrada.case_id) if suyo else None,
                )
            )
    return comun.panel.model_copy(
        update={
            "cases": tuple(sueltos),
            "comparisons": tuple(comparaciones),
            "langfuse_url": enlaces.ultimo,
        }
    )


# --- La ruta ------------------------------------------------------------------


def router() -> APIRouter:
    enrutador = APIRouter(prefix="/api", tags=["spend"])

    @enrutador.get(
        "/spend",
        response_model=SpendPanel,
        operation_id="getSpend",
        responses=problem_responses(),
    )
    async def panel(
        response: Response,
        untangle_visitor: Annotated[str | None, Cookie()] = None,
    ) -> SpendPanel:
        # Lleva la marca de "tu caso", que es de este navegador: ningun
        # intermediario puede servirsela a otro.
        response.headers["Cache-Control"] = "private, no-store"
        return await build_panel(untangle_visitor)

    return enrutador


async def _sonda() -> None:
    """Que el tablero se puede armar: una lectura de fila unica, sin gastar."""
    await repository.load_window(spend.current_runtime().window_start)


def surfaces() -> tuple[SurfaceSpec, ...]:
    """El tablero de gasto: publico y unico (no hay uno por aseguradora)."""
    return (
        SurfaceSpec(
            surface_id=SurfaceId.SPEND_PANEL,
            owning_unit="u22-public-evidence",
            public=True,
            per_tenant=False,
            probe=SurfaceProbe(check=_sonda, timeout_ms=PROBE_TIMEOUT_MS),
        ),
    )


__all__ = [
    "ActivitySpend",
    "CaseSpendItem",
    "ComparisonPart",
    "ComparisonSpendItem",
    "CountedSpend",
    "DaySpend",
    "ModelSpend",
    "ProviderSpend",
    "SpendPanel",
    "build_panel",
    "reset_cache",
    "router",
    "surfaces",
]
