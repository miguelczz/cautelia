"""Las sondas de la comprension de un mensaje (fase 0, 2026-10-07).

Cada caso `DS-2/<idioma>/understand-*` trae el contexto que la agente tiene en ese
turno --tipo de conversacion, datos ya anotados, lo ultimo que dijo-- y un mensaje,
y dice que tiene que entender: la intencion, los datos ya interpretados, el si o el
no y si la persona pregunto algo. La sonda llama al mismo puerto que usa el chat
(`orchestration.nodes.intake.understanding.Understander`) y pasa los datos por la misma
validacion y normalizacion que la captura, asi que compara **lo que llegaria al
caso**, no lo que el modelo escribio.

**El puerto lo instala quien corre la sonda**, no este modulo: construir el
cliente de Claude es de la raiz de composicion, y el corredor no la importa
(contrato `produccion-sin-evals` y su reciproco). Lo instala
`untangle.server.understanding_cli`, con la clave de evaluaciones. Sin puerto
instalado el caso queda **no medido** con su causa, nunca en verde.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Awaitable, Callable
from pathlib import Path

from untangle.base import Locale
from untangle.case_record import fields
from untangle.case_record.models import FieldStatus, RecordType
from untangle.evals import loading
from untangle.evals.models import Dataset, UnderstandingExpectation
from untangle.evals.runner.api import (
    CheckOutcome,
    EvalTarget,
    register_async_check,
    register_targets,
)
from untangle.evals.runner.failures import TargetUnavailableError
from untangle.orchestration import outcome_claim, triage_inputs
from untangle.orchestration.nodes.intake import extraction, understanding
from untangle.orchestration.nodes.intake.understanding import (
    CaseStatus,
    HistoryLine,
    NotedDetail,
    UnderstandingRequest,
    UnderstandingResponse,
)
from untangle.tenancy.models import TenantId

UNIT = "fase-0-entender"

_CASES_DIR = Path("app/evals/cases/ds2")

#: Quien construye el puerto real; lo instala el comando que corre la sonda.
_fabrica: Callable[[], understanding.Understander] | None = None


def install(factory: Callable[[], understanding.Understander] | None) -> None:
    """Instala (o quita, con `None`) quien construye el puerto real."""
    global _fabrica
    _fabrica = factory


def _plegar(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto.casefold()) if not unicodedata.combining(c)
    )


def _tipo_del_caso(
    esperado: UnderstandingExpectation, respuesta: UnderstandingResponse
) -> RecordType | None:
    if esperado.record_type is not None:
        return RecordType(esperado.record_type)
    return understanding.opening_record_type(respuesta, quote_enabled=esperado.quote_enabled)


def _terceros(se_espera_negacion: bool | None, valor: str | None) -> list[str]:
    """Lo que `other_parties` quedo siendo, contra lo que el mensaje decia de los demas.

    Lo lee **la misma funcion que decide el cierre directo**: una negacion clara es la unica
    forma de `other_parties` con la que un caso sin terceros capturados se cierra sin ajustador.
    Un campo que no quedo anotado no es ninguna de las dos cosas, y se dice aparte. Sin
    expectativa (`None`) el caso no mide esto.
    """
    if se_espera_negacion is None:
        return []
    if valor is None:
        return ["falta el campo 'other_parties' (el mensaje hablaba de los demas involucrados)"]
    niega = (
        triage_inputs.other_parties_data_pending((), block_status=FieldStatus.STATED, value=valor)
        is False
    )
    if niega == se_espera_negacion:
        return []
    if niega:
        return [f"'other_parties' = {valor!r} es una negacion clara, y el mensaje nombra a alguien"]
    return [
        f"'other_parties' = {valor!r} no es una negacion clara, y el mensaje decia que no habia"
    ]


#: Lo que `unlisted_driver` devuelve, dicho con las palabras de la expectativa: `True` es que
#: quien conducia no figura en la poliza, `False` que figura, `None` que no se sabe.
_LECTURA_DEL_CONDUCTOR: dict[bool | None, str] = {
    True: "unlisted",
    False: "listed",
    None: "unknown",
}


def _conductor(esperado: UnderstandingExpectation, valor: str | None) -> list[str]:
    """Lo que la derivacion del conductor lee del campo anotado, contra lo que se espera.

    Lo lee **la misma funcion que la derivacion** (`triage_inputs.unlisted_driver`), con los
    conductores que la poliza del caso declara: el nombre completo que dijo la persona tiene que
    llegar al campo de una forma que esa funcion pueda leer --junto a un verbo de conducir--, y
    sin nombre no se puede haber inventado uno. Sin expectativa (`None`) el caso no mide esto.
    """
    if esperado.driver_reading is None:
        return []
    if valor is None:
        return [
            f"falta el campo '{triage_inputs.DRIVER_FIELD}' (el mensaje hablaba de quien conducia)"
        ]
    figura = triage_inputs.unlisted_driver(
        valor, status=FieldStatus.STATED, declared_drivers=esperado.declared_drivers
    )
    leido = _LECTURA_DEL_CONDUCTOR[figura]
    if leido == esperado.driver_reading:
        return []
    return [
        f"'{triage_inputs.DRIVER_FIELD}' = {valor!r} se lee como '{leido}', "
        f"se esperaba '{esperado.driver_reading}'"
    ]


def _pregunta_por(palabras: tuple[str, ...], respuesta: str | None) -> list[str]:
    """Si lo que la agente contesto es una pregunta que nombra alguna de las palabras.

    Es lo unico que un juez por codigo puede afirmar de un texto libre: que **pregunta por** el
    nombre, no que lo pregunte bien. Una respuesta sin «?» o sin ninguna de las palabras no lo
    hace. Sin palabras el caso no mide la respuesta.
    """
    if not palabras:
        return []
    texto = _plegar(respuesta or "")
    if "?" in texto and any(_plegar(palabra) in texto for palabra in palabras):
        return []
    return [f"la respuesta no pregunta por {list(palabras)}: {respuesta!r}"]


def _nombra(palabras: tuple[str, ...], respuesta: str | None) -> list[str]:
    """Si lo que la agente contesto nombra alguna de las palabras, sea pregunta o no."""
    if not palabras:
        return []
    texto = _plegar(respuesta or "")
    if any(_plegar(palabra) in texto for palabra in palabras):
        return []
    return [f"la respuesta no nombra ninguna de {list(palabras)}: {respuesta!r}"]


def _sin_promesa_de_desenlace(vigilar: bool, respuesta: str | None) -> list[str]:
    """Si la respuesta afirma un desenlace del reporte que solo el codigo puede dar.

    Lo mide la misma funcion que descarta esa respuesta en el chat, y dice **que oracion** lo
    afirmo. Una respuesta vacia no afirma nada. Sin `vigilar` el caso no mide esto.
    """
    if not vigilar:
        return []
    afirmacion = outcome_claim.find_claim(respuesta)
    if afirmacion is None:
        return []
    return [
        f"la respuesta da el reporte por hecho o dice que lo revisa un ajustador: {afirmacion!r}"
    ]


def evaluate(
    esperado: UnderstandingExpectation,
    respuesta: UnderstandingResponse,
    *,
    language: Locale,
) -> list[str]:
    """Las diferencias entre lo entendido y lo esperado; vacia si coincide."""
    fallos: list[str] = []
    if respuesta.wants.value not in esperado.wants:
        fallos.append(f"intencion '{respuesta.wants.value}', se esperaba {list(esperado.wants)}")
    if esperado.answer is not None and respuesta.answer.value != esperado.answer:
        fallos.append(f"respuesta '{respuesta.answer.value}', se esperaba '{esperado.answer}'")
    if (
        esperado.asks_question is not None
        and (respuesta.person_question is not None) != esperado.asks_question
    ):
        fallos.append(f"pregunta de la persona: {respuesta.person_question!r}")
    if (
        esperado.asks_about_coverage is not None
        and respuesta.asks_about_coverage != esperado.asks_about_coverage
    ):
        fallos.append(f"pregunta de cobertura: {respuesta.asks_about_coverage}")

    tipo = _tipo_del_caso(esperado, respuesta)
    permitidos = (
        frozenset(d.key for d in fields.definitions_for(tipo)) if tipo is not None else frozenset()
    )
    campos = extraction.extract_fields(
        respuesta.as_extraction(),
        turn_id="sonda",
        turn_text=esperado.message,
        language=language,
        now=esperado.today,
        allowed_keys=permitidos,
    )
    valores = {campo.field_key: campo.value for campo in campos}
    for clave, valor in esperado.items.items():
        obtenido = valores.get(clave)
        if obtenido is None:
            fallos.append(f"falta el campo '{clave}' (se entendio {valores})")
        elif clave in extraction.QUOTE_TYPED_FIELDS:
            if obtenido != valor:
                fallos.append(f"'{clave}' = {obtenido!r}, se esperaba {valor!r}")
        elif _plegar(valor) not in _plegar(obtenido):
            fallos.append(f"'{clave}' = {obtenido!r}, no contiene {valor!r}")
    fallos.extend(
        f"aparecio '{clave}' = {valores[clave]!r}, que el mensaje no dijo"
        for clave in esperado.absent_items
        if clave in valores
    )
    fallos.extend(
        _terceros(esperado.other_parties_denied, valores.get(triage_inputs.OTHER_PARTIES_FIELD))
    )
    fallos.extend(_conductor(esperado, valores.get(triage_inputs.DRIVER_FIELD)))
    fallos.extend(_pregunta_por(esperado.reply_asks_for_any, respuesta.reply))
    fallos.extend(_nombra(esperado.reply_mentions_any, respuesta.reply))
    fallos.extend(_sin_promesa_de_desenlace(esperado.reply_claims_no_outcome, respuesta.reply))
    return fallos


def _peticion(
    esperado: UnderstandingExpectation, *, tenant: TenantId, language: Locale
) -> UnderstandingRequest:
    """La peticion del caso: el contexto que la agente tiene en ese turno.

    El caso trae las claves de lo ya anotado y lo ultimo que dijo la agente, no la conversacion
    entera: lo ultimo que dijo es toda la historia. Los datos van «ya los dio», salvo los que el
    caso trae con su valor (`captured_values`), que van como los ve el modelo en el chat: un dato
    que se reemplaza al volver a anotarlo no se puede medir sin verlo. Es lo que hay para medir
    que se entiende, no que se contesta."""
    tipo = RecordType(esperado.record_type) if esperado.record_type is not None else None
    faltan = (
        tuple(d.key for d in fields.definitions_for(tipo) if d.key not in esperado.captured)
        if tipo is not None
        else ()
    )
    return UnderstandingRequest(
        tenant_id=tenant,
        language=language,
        today=esperado.today,
        record_type=tipo,
        quote_enabled=esperado.quote_enabled,
        noted=tuple(
            NotedDetail(clave, esperado.captured_values.get(clave)) for clave in esperado.captured
        ),
        missing=faltan,
        person_text=esperado.message,
        case_status=CaseStatus.RECEIVING if tipo is not None else CaseStatus.NONE,
        history=(
            (HistoryLine(speaker="agent", text=esperado.last_agent_text),)
            if esperado.last_agent_text
            else ()
        ),
    )


def _sonda(nombre: str) -> Callable[..., Awaitable[CheckOutcome]]:
    async def sonda(*, language: Locale, root: Path) -> CheckOutcome:
        caso = loading.load_case(root / _CASES_DIR / nombre / f"{language}.yaml")
        esperado = caso.understanding
        if esperado is None or caso.tenant is None:
            return CheckOutcome(passed=False, detail=f"el caso '{nombre}' no trae su comprension")
        fabrica = _fabrica
        if fabrica is None:
            msg = (
                "no hay quien entienda instalado: la comprension se mide con "
                "`mise run evals:entender`, que construye el puerto con la clave de evaluaciones"
            )
            raise TargetUnavailableError(msg)
        peticion = _peticion(esperado, tenant=caso.tenant, language=language)
        # La misma regla que aplica el chat: se mide lo que el turno recibe.
        respuesta = understanding.canonical_reading(await fabrica()(peticion), peticion.record_type)
        fallos = evaluate(esperado, respuesta, language=language)
        return CheckOutcome(passed=not fallos, detail="; ".join(fallos))

    return sonda


def _casos(root: Path | None = None) -> tuple[str, ...]:
    base = (root or Path.cwd()) / _CASES_DIR
    if not base.is_dir():
        return ()
    return tuple(sorted(d.name for d in base.iterdir() if d.name.startswith("understand-")))


def criterion_of(case_name: str) -> str:
    return "understanding_" + case_name.removeprefix("understand-").replace("-", "_")


def register_understanding_probes(root: Path | None = None) -> None:
    """Registra una sonda por caso `understand-*` y sus objetivos."""
    nombres = _casos(root)
    for nombre in nombres:
        register_async_check(criterion_of(nombre), _sonda(nombre))
    register_targets(
        UNIT,
        tuple(
            EvalTarget(criterion_of(nombre), Dataset.DS_2, f"La agente entiende: {nombre}")
            for nombre in nombres
        ),
    )


__all__ = [
    "UNIT",
    "criterion_of",
    "evaluate",
    "install",
    "register_understanding_probes",
]
