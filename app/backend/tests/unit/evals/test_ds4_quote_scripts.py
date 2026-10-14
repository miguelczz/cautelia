"""Los guiones de las conversaciones de cotizacion de DS-4, recorridos sin modelo (2026-10-12).

Las cuatro conversaciones nunca habian corrido contra un modelo, y la primera corrida las
dejo en `complete: 0, total: 17`: el conductor contestaba la confirmacion de cada bloque a una
agente que ya no la pide. Aqui se recorre cada guion **como lo recorreria el conductor con una
agente que anota lo que llega**: `blocks.next_ask` dice que toca, `ScriptedInsured` responde, la
extraccion real convierte cada valor tipado y la completitud se calcula con el esquema de
verdad. Si el guion pide un campo que el esquema no tiene, trae un valor que no se puede
convertir, deja una respuesta sin usar o no llega a 17 de 17, aqui se ve --y no veinte mensajes
despues, contra un modelo de pago--.

No mide al modelo ni a la extraccion por IA: mide que el guion y el conductor, con una captura
perfecta, terminen la solicitud. La captura de verdad es lo que miden las corridas.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from untangle import paths
from untangle.base import Locale
from untangle.case_record import fields
from untangle.case_record.models import CaseField, CaseState, Completeness, FieldStatus, RecordType
from untangle.copy_catalog import api as copy_api
from untangle.evals import loading
from untangle.evals.models import Dataset, GoldenCase
from untangle.evals.scripted_insured import ScriptedInsured
from untangle.orchestration.nodes.intake import blocks, confirmation
from untangle.orchestration.nodes.intake.extraction import (
    ExtractedItem,
    ExtractionResponse,
    extract_fields,
)
from untangle.rules import eligibility
from untangle.tenancy import config as tenancy_config

HOY = date(2026, 10, 12)
AHORA = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
CLAVES = tuple(d.key for d in fields.definitions_for(RecordType.QUOTE_REQUEST))
ESLUGS = ("quote-end-to-end", "quote-price-pressure-conversation")


def _casos_de_conversacion() -> list[GoldenCase]:
    return [c for c in loading.load_cases() if c.dataset is Dataset.DS_4 and c.channel is not None]


class _Recorrido:
    """Lo que dejo recorrer un guion: lo dicho, la completitud y cuantos mensajes costo."""

    def __init__(self, caso: GoldenCase) -> None:
        self.caso = caso
        self.estados: dict[str, FieldStatus] = {}
        self.valores: dict[str, str] = {}
        self.entregadas: list[tuple[str, str]] = []
        #: Las respuestas que la extraccion no pudo convertir y por eso no escribio nada.
        self.sin_escribir: list[tuple[str, str]] = []
        self.insured = ScriptedInsured(caso)

    def completitud(self) -> Completeness:
        campos = tuple(
            CaseField(
                case_id="C-1",
                field_key=clave,
                value=None,
                status=estado,
                evidence_turn_id="t0",
                updated_at=AHORA,
            )
            for clave, estado in self.estados.items()
        )
        return fields.completeness_of(RecordType.QUOTE_REQUEST, campos)

    def correr(self, techo: int) -> int:
        """Recorre el guion hasta que no quede nada que preguntar. Devuelve los mensajes."""
        mensajes = 0
        clave = self.caso.script[0].field_key
        while mensajes < techo:
            respuesta = self.insured.answer(clave)
            mensajes += 1
            self.entregadas.append((clave, respuesta.text))
            if clave in CLAVES:
                self._anotar(clave, respuesta.text)
            elif confirmation.is_affirmative(respuesta.text, language=self.caso.language):
                # La lectura de la solicitud entera: un si confirma todo lo dicho.
                for dicho in list(self.estados):
                    self.estados[dicho] = FieldStatus.CONFIRMED
            pide = blocks.next_ask(
                RecordType.QUOTE_REQUEST, self.completitud(), CaseState.CAPTURING
            )
            if pide.kind is blocks.AskKind.DONE:
                break
            clave = pide.key
        return mensajes

    def _anotar(self, clave: str, texto: str) -> None:
        """Lo que la extraccion real escribe de esa respuesta: lo tipado, convertido, y lo
        derivado. Una respuesta que no se convierte no escribe nada y el campo se vuelve a
        preguntar --lo que hace la agente ante una presion por un precio--."""
        respuesta = ExtractionResponse(items=(ExtractedItem(field_key=clave, value=texto),))
        escritos = extract_fields(
            respuesta,
            turn_id="t1",
            turn_text=texto,
            language=self.caso.language,
            now=HOY,
            allowed_keys=frozenset(CLAVES),
        )
        if not escritos:
            self.sin_escribir.append((clave, texto))
        for campo in escritos:
            self.estados[campo.field_key] = FieldStatus.STATED
            self.valores[campo.field_key] = campo.normalized or campo.value


@pytest.fixture(autouse=True)
def _catalogo_limpio() -> None:
    copy_api.reset()


@pytest.mark.parametrize("caso", _casos_de_conversacion(), ids=lambda c: c.case_key)
def test_el_guion_llega_a_17_de_17_sin_salirse_de_guion_y_con_mensajes_de_sobra(
    caso: GoldenCase,
) -> None:
    aseguradora = tenancy_config.load(paths.tenants_dir()).get(caso.tenant or "")
    assert aseguradora is not None, caso.tenant
    techo = aseguradora.chat.messages_per_session
    recorrido = _Recorrido(caso)

    mensajes = recorrido.correr(techo)

    completitud = recorrido.completitud()
    assert (completitud.complete, completitud.total) == (17, 17), caso.case_key
    assert recorrido.insured.off_script_turns == 0, "el conductor pidio algo que el guion no tiene"
    # Cada respuesta del guion se usa una vez: ninguna sobra, ninguna falta.
    usadas = {(r.field_key, r.text) for r in caso.script}
    assert set(recorrido.entregadas) == usadas, caso.case_key
    assert mensajes == len(caso.script) == len(recorrido.entregadas)
    # El techo de mensajes por conversacion es de la aseguradora, y el guion tiene que caber.
    assert mensajes <= techo, f"{mensajes} mensajes no caben en {techo}"


@pytest.mark.parametrize("caso", _casos_de_conversacion(), ids=lambda c: c.case_key)
def test_los_valores_tipados_del_guion_se_pueden_convertir(caso: GoldenCase) -> None:
    """Un valor que no se convierte no se escribe y el campo se vuelve a preguntar: en una
    conversacion de evaluacion eso es un guion que nunca termina. Las unicas respuestas que
    no se convierten son las presiones por un precio, a proposito, y la ultima del uso las
    reemplaza."""
    recorrido = _Recorrido(caso)
    recorrido.correr(40)

    es_presion = caso.case_key.endswith("quote-price-pressure-conversation")
    esperado = (
        [("use_type", r.text) for r in caso.answers_for("use_type")[:-1]] if es_presion else []
    )
    assert recorrido.sin_escribir == esperado, caso.case_key
    assert recorrido.valores["license_years"] == "8"
    assert recorrido.valores["vehicle_year"] == "2014"
    assert recorrido.valores["vehicle_age_years"] == "12"
    assert recorrido.valores["use_type"] == "commuting"
    assert recorrido.valores["annual_mileage_band"] == "medium"
    assert recorrido.valores["salvage_title"] == "false"
    assert recorrido.valores["at_fault_losses_3y"] == "0"
    assert recorrido.valores["claims_3y"] == "1"
    assert recorrido.valores["prior_coverage_active"] == "true"
    assert recorrido.valores["lapse_months"] == "0"
    assert recorrido.valores["vin"].startswith("JM1BL1SF7A")


@pytest.mark.parametrize("caso", _casos_de_conversacion(), ids=lambda c: c.case_key)
def test_el_estado_esperado_es_el_que_deja_la_elegibilidad_de_ese_perfil(
    caso: GoldenCase,
) -> None:
    """`capturing` solo si la solicitud no se deriva: la deriva el motor de reglas cuando el
    perfil cae en una regla de derivacion, y entonces el caso termina en `derived`."""
    recorrido = _Recorrido(caso)
    recorrido.correr(40)
    assert caso.tenant is not None

    eligibility.reset()
    try:
        salida = eligibility.evaluate_eligibility(
            eligibility.require(caso.tenant), eligibility.eligibility_inputs(recorrido.valores)
        )
    finally:
        eligibility.reset()

    derivada = salida.outcome is eligibility.EligibilityOutcomeKind.REFERRED
    assert caso.expected_record["state"] == ("derived" if derivada else "capturing"), (
        caso.case_key,
        salida.outcome.value,
        salida.deciding_rules,
    )
    # Y es elegible a proposito: una solicitud fuera de lo que asegura la aseguradora no
    # es lo que estos casos miden.
    assert salida.outcome is eligibility.EligibilityOutcomeKind.ELIGIBLE, salida.deciding_rules


@pytest.mark.parametrize("caso", _casos_de_conversacion(), ids=lambda c: c.case_key)
def test_ninguna_respuesta_se_repite_para_que_cada_texto_sea_de_un_solo_campo(
    caso: GoldenCase,
) -> None:
    """Quien repasa una transcripcion --o un doble que reparte lo dicho por su texto-- tiene
    que poder saber a que campo iba cada respuesta. La ciudad de la licencia y la de guarda
    son distintas a proposito."""
    textos = [r.text for r in caso.script]

    assert len(textos) == len(set(textos)), caso.case_key


def test_los_dos_idiomas_recorren_lo_mismo() -> None:
    for slug in ESLUGS:
        por_idioma: dict[Locale, list[str]] = {}
        for caso in _casos_de_conversacion():
            if caso.case_key.endswith(slug):
                recorrido = _Recorrido(caso)
                recorrido.correr(40)
                por_idioma[caso.language] = [campo for campo, _ in recorrido.entregadas]
        assert por_idioma["es"] == por_idioma["en"], slug
