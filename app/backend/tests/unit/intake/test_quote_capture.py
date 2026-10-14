"""La captura de una solicitud de cotizacion (U19, BR1.1 a BR1.4): cuatro bloques sobre el nodo que ya existe.

Lo que estas pruebas protegen:

- que **el grafo no gane nodos** (BR1.1): la solicitud es un tipo de registro, no una rama;
- que la captura sea **una idea a la vez y con confirmacion por bloque** (BR1.2): nunca dos
  preguntas en un turno, y un bloque no se cierra hasta que se confirma;
- que lo que las reglas leen llegue **convertido** y que lo que no se puede convertir no se
  escriba (BR1.3): un "a veces" no es un uso del vehiculo;
- que la **antiguedad del vehiculo se derive en un solo sitio** desde el reloj inyectado (BR1.4).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from untangle import paths
from untangle.base import Locale, ProviderName, SpendSource, Use
from untangle.case_record import fields, schema_loading
from untangle.case_record.models import (
    CaseField,
    CaseState,
    Completeness,
    FieldStatus,
    RecordType,
)
from untangle.copy_catalog import api as copy_api
from untangle.orchestration.graph import GRAPH_NODE_SPECS
from untangle.orchestration.nodes.intake import (
    blocks,
    composition,
    extraction,
    normalization,
)
from untangle.orchestration.nodes.intake.blocks import Block
from untangle.orchestration.nodes.intake.extraction import ExtractedItem, ExtractionResponse
from untangle.orchestration.nodes.intake.node import IntakeNode, IntakeNodeInput, IntakeNodeOutput
from untangle.providers.ports import (
    GenerationResult,
    InstructionText,
    PromptRef,
    SystemInstruction,
    UsageReport,
)
from untangle.telemetry.traces.models import NodeName

HOY = date(2026, 9, 30)
CLAVES = tuple(d.key for d in schema_loading.fields_by_record_type()[RecordType.QUOTE_REQUEST])
BLOQUES_DE_LA_SOLICITUD = (
    Block.QUOTE_DRIVER,
    Block.QUOTE_VEHICLE,
    Block.QUOTE_USAGE,
    Block.QUOTE_HISTORY,
)


@pytest.fixture(autouse=True)
def _catalogo_limpio() -> Iterator[None]:
    copy_api.reset()
    yield
    copy_api.reset()


# --- BR1.1: el grafo no gana nodos ---------------------------------------------------


def test_el_grafo_sigue_teniendo_cuatro_nodos() -> None:
    """La solicitud es un tipo de registro sobre los mismos cuatro nodos, no una rama (BR1.1)."""
    esperados = {"intake", "policy_verification", "decision", "compliance"}

    assert {nodo.value for nodo in NodeName} == esperados
    assert {nodo.name.value for nodo in GRAPH_NODE_SPECS} == esperados
    assert len(GRAPH_NODE_SPECS) == 4


def test_los_cuatro_bloques_de_la_solicitud_no_son_nodos_del_grafo() -> None:
    """`Block` es el vocabulario de la captura; un bloque nuevo no puede colarse como nodo."""
    nodos = {nodo.value for nodo in NodeName}

    assert not nodos & {bloque.value for bloque in BLOQUES_DE_LA_SOLICITUD}


def test_el_orden_de_bloques_es_un_dato_del_tipo_de_registro() -> None:
    assert blocks.order_for(RecordType.QUOTE_REQUEST) == BLOQUES_DE_LA_SOLICITUD
    assert blocks.order_for(RecordType.CLAIM) == blocks.BLOCK_ORDER
    assert blocks.order_for(RecordType.COVERAGE_INQUIRY) == blocks.BLOCK_ORDER
    assert not set(BLOQUES_DE_LA_SOLICITUD) & set(blocks.BLOCK_ORDER)


# --- Un estado de caso simulado, para recorrer el nodo turno a turno ---------------------


class _Extractor:
    def __init__(self, *items: ExtractedItem) -> None:
        self.items = items

    async def __call__(self, _prompt: object) -> GenerationResult:
        return GenerationResult(
            text=None,
            parsed=ExtractionResponse(items=self.items),
            usage=UsageReport(
                provider=ProviderName.GEMINI,
                model="gemini-2.5-flash",
                use=Use.CHAT,
                source=SpendSource.PROVIDER_REPORTED,
            ),
            prompt=PromptRef(prompt_id="intake", locale="es", sha256="a" * 64),
        )


def _instruccion(_language: str) -> SystemInstruction:
    return SystemInstruction(
        ref=PromptRef(prompt_id="intake", locale="es", sha256="a" * 64),
        text=InstructionText("Eres la agente de captura."),
    )


class _Caso:
    """Lo que el ejecutor guardaria: valor y estado de cada campo, y la lectura en espera."""

    def __init__(self, language: Locale, *, hoy: date = HOY) -> None:
        self.language = language
        self.hoy = hoy
        self.valores: dict[str, str] = {}
        self.estados: dict[str, FieldStatus] = {}
        self.en_espera: Block | None = None
        self.turno = 0

    def completitud(self) -> Completeness:
        campos = tuple(
            CaseField(
                case_id="C-1",
                field_key=clave,
                value=None,
                status=estado,
                evidence_turn_id="t0",
                updated_at=_AHORA,
            )
            for clave, estado in self.estados.items()
            if estado is not FieldStatus.NOT_STATED
        )
        return fields.completeness_of(RecordType.QUOTE_REQUEST, campos)

    def _valores_del_bloque_a_leer(self, completitud: Completeness) -> dict[str, str]:
        """Lo mismo que `case_context.stated_values_for_readback`: en la solicitud, todo lo
        dicho, porque se confirma de una vez (2026-10-08)."""
        if not any(
            blocks.readback_fields_in_block(RecordType.QUOTE_REQUEST, bloque, completitud)
            for bloque in BLOQUES_DE_LA_SOLICITUD
        ):
            return {}
        return dict(self.valores)

    async def decir(self, texto: str, *items: ExtractedItem) -> IntakeNodeOutput:
        self.turno += 1
        completitud = self.completitud()
        nodo = IntakeNode(
            extract=_Extractor(*items), instruction=_instruccion, clock=lambda: self.hoy
        )
        salida = await nodo.run(
            IntakeNodeInput(
                tenant_id="sunmeadow",
                case_id="C-1",
                record_type=RecordType.QUOTE_REQUEST,
                case_state=CaseState.CAPTURING,
                completeness=completitud,
                language=self.language,
                turn_text=texto,
                turn_id=f"t{self.turno}",
                awaiting_confirmation=self.en_espera,
                stated_values=self._valores_del_bloque_a_leer(completitud),
            )
        )
        for campo in salida.intake_extracted:
            self.valores[campo.field_key] = campo.value
            self.estados[campo.field_key] = FieldStatus.STATED
        resolucion = salida.intake_readback_resolved
        if resolucion is not None:
            for clave in resolucion.fields:
                if resolucion.accepted:
                    self.estados[clave] = FieldStatus.CONFIRMED
                else:
                    self.estados.pop(clave, None)
                    self.valores.pop(clave, None)
        self.en_espera = salida.intake_awaiting_confirmation
        return salida


from datetime import (  # noqa: E402 -- junto a quien lo usa, para que la clase se lea de arriba abajo
    UTC,
    datetime,
)

_AHORA = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _item(clave: str, valor: str) -> ExtractedItem:
    return ExtractedItem(field_key=clave, value=valor)


# Lo que dice una persona, por idioma, en el orden de los bloques. Cada respuesta es
# **lo que se dijo** ("hace ocho anios"), no el valor canonico: la conversion es del codigo.
GUION: dict[Locale, list[tuple[str, str]]] = {
    "es": [
        ("driver_name", "Marta Diaz Lopez"),
        ("driver_birth_date", "12 de abril de 1990"),
        ("license_years", "hace ocho años"),
        ("license_jurisdiction", "Corvane"),
        ("vehicle_year", "es un 2014"),
        ("vehicle_make", "Mazda"),
        ("vehicle_model", "Tres"),
        ("vin", "JM1BL1SF7A1234567"),
        ("salvage_title", "no, está limpio"),
        ("use_type", "para ir al trabajo"),
        ("annual_mileage_band", "moderado"),
        ("garaging_jurisdiction", "Corvane"),
        ("at_fault_losses_3y", "ninguno"),
        ("claims_3y", "uno"),
        ("prior_coverage_active", "sí, tengo"),
    ],
    "en": [
        ("driver_name", "Marta Diaz Lopez"),
        ("driver_birth_date", "April 12, 1990"),
        ("license_years", "about eight years"),
        ("license_jurisdiction", "Corvane"),
        ("vehicle_year", "it's a 2014"),
        ("vehicle_make", "Mazda"),
        ("vehicle_model", "Three"),
        ("vin", "JM1BL1SF7A1234567"),
        ("salvage_title", "no, it's clean"),
        ("use_type", "commuting to work"),
        ("annual_mileage_band", "moderate"),
        ("garaging_jurisdiction", "Corvane"),
        ("at_fault_losses_3y", "none"),
        ("claims_3y", "one"),
        ("prior_coverage_active", "yes, I do"),
    ],
}
SI: dict[Locale, str] = {"es": "sí, es correcto", "en": "yes, that's correct"}
NO: dict[Locale, str] = {"es": "no, es incorrecto", "en": "no, that's incorrect"}


async def _decir_todo(caso: _Caso) -> list[IntakeNodeOutput]:
    """Responde de a un campo, sin confirmar nada. Devuelve la salida de cada turno."""
    salidas: list[IntakeNodeOutput] = []
    guion = dict(GUION[caso.language])
    for claves in schema_loading.QUOTE_FIELDS_BY_BLOCK.values():
        for clave in claves:
            if clave in guion:
                salidas.append(await caso.decir(guion[clave], _item(clave, guion[clave])))
    return salidas


async def _recorrer(caso: _Caso) -> list[IntakeNodeOutput]:
    """Responde de a un campo y confirma la solicitud entera al final (2026-10-08)."""
    salidas = await _decir_todo(caso)
    salidas.append(await caso.decir(SI[caso.language]))
    return salidas


# --- BR1.2: cuatro bloques, una idea a la vez, confirmacion por bloque ---------------------


@pytest.mark.parametrize("language", ["es", "en"])
async def test_el_recorrido_completo_pregunta_agrupado_y_lee_todo_una_vez(
    language: Locale,
) -> None:
    """Decision de Miguel del 2026-10-08: una sola confirmacion al final, y lo que falta se
    pregunta agrupado, hasta tres datos por mensaje."""
    caso = _Caso(language)
    salidas = await _recorrer(caso)

    claves = [s.intake_response_key for s in salidas]
    lecturas = [k for k in claves if k.startswith("intake.readback.quote_")]
    assert lecturas == ["intake.readback.quote_all"]
    assert claves[-1] == "intake.closing.summary_quote"
    for salida in salidas:
        if salida.intake_response_key.startswith("intake.question.quote_"):
            assert salida.intake_response_text.count("?") <= composition.QUOTE_QUESTIONS_PER_TURN


@pytest.mark.parametrize("language", ["es", "en"])
async def test_al_terminar_los_cuatro_bloques_la_solicitud_esta_completa_17_de_17(
    language: Locale,
) -> None:
    caso = _Caso(language)
    await _recorrer(caso)

    completitud = caso.completitud()
    assert (completitud.complete, completitud.total) == (17, 17)
    assert (
        blocks.next_block(RecordType.QUOTE_REQUEST, completitud, CaseState.CAPTURING)
        is Block.FINAL_CONFIRMATION
    )


async def test_las_preguntas_salen_en_el_orden_del_esquema() -> None:
    caso = _Caso("es")
    salidas = await _recorrer(caso)

    preguntas = [
        s.intake_response_key.removeprefix("intake.question.quote_")
        for s in salidas
        if s.intake_response_key.startswith("intake.question.quote_")
    ]
    # Cada respuesta del guion provoca la pregunta del campo SIGUIENTE (la clave del turno
    # es la del primer dato que se pregunta); la primera la hizo la apertura.
    esperadas = [
        "driver_birth_date", "license_years", "license_jurisdiction",
        "vehicle_year", "vehicle_make", "vehicle_model", "vin", "salvage_title",
        "use_type", "annual_mileage_band", "garaging_jurisdiction",
        "at_fault_losses_3y", "claims_3y", "prior_coverage_active",
    ]  # fmt: skip
    assert preguntas == esperadas


async def _hasta_el_vehiculo(caso: _Caso) -> None:
    """El conductor completo, dicho de una vez: lo que sigue es el bloque del vehiculo."""
    guion = dict(GUION[caso.language])
    await caso.decir(
        "soy yo",
        *(_item(c, guion[c]) for c in schema_loading.QUOTE_FIELDS_BY_BLOCK["quote_driver"]),
    )


@pytest.mark.parametrize("language", ["es", "en"])
async def test_un_turno_sin_nada_anotado_pide_un_solo_dato_el_primero_que_falta(
    language: Locale,
) -> None:
    """Visto el 2026-10-11: «Three.» contestando a modelo, VIN y perdida total no se anotaba y
    la agente repetia los tres datos hasta el tope de mensajes. Sin nada anotado, se pide
    uno solo, con la frase de un dato que el catalogo ya tiene."""
    caso = _Caso(language)
    await _hasta_el_vehiculo(caso)
    guion = dict(GUION[language])
    await caso.decir(guion["vehicle_year"], _item("vehicle_year", guion["vehicle_year"]))
    agrupada = await caso.decir(guion["vehicle_make"], _item("vehicle_make", guion["vehicle_make"]))
    assert agrupada.intake_response_text.count("?") == composition.QUOTE_QUESTIONS_PER_TURN

    for _ in range(3):
        salida = await caso.decir("Three." if language == "en" else "Tres.")

        assert salida.intake_extracted == ()
        assert salida.intake_response_key == "intake.question.quote_vehicle_model"
        assert salida.intake_response_text == copy_api.t(
            composition.QUESTION_QUOTE_VEHICLE_MODEL, locale=language
        )
        assert salida.intake_response_text.count("?") == 1


@pytest.mark.parametrize("language", ["es", "en"])
async def test_un_turno_que_si_anota_sigue_preguntando_agrupado(language: Locale) -> None:
    """El control que distingue de la prueba de arriba: lo anotado no angosta la pregunta."""
    caso = _Caso(language)
    await _hasta_el_vehiculo(caso)
    guion = dict(GUION[language])

    salida = await caso.decir(guion["vehicle_year"], _item("vehicle_year", guion["vehicle_year"]))

    assert (
        salida.intake_response_text
        == composition.question_of(
            Block.QUOTE_VEHICLE,
            ("vehicle_make", "vehicle_model", "vin", "salvage_title"),
            language=language,
        )[1]
    )
    assert salida.intake_response_text.count("?") == composition.QUOTE_QUESTIONS_PER_TURN


async def test_el_primer_mensaje_de_un_bloque_nuevo_sale_agrupado() -> None:
    """Con el conductor completo el bloque del vehiculo se abre agrupado: angostar es cosa de
    la repeticion, no de abrir el bloque (lo abre el turno que si anoto)."""
    caso = _Caso("es")
    guion = dict(GUION["es"])
    salida = await caso.decir(
        "soy yo",
        *(_item(c, guion[c]) for c in schema_loading.QUOTE_FIELDS_BY_BLOCK["quote_driver"]),
    )

    assert salida.intake_response_text.count("?") == composition.QUOTE_QUESTIONS_PER_TURN
    assert salida.intake_response_key == "intake.question.quote_vehicle_year"


async def test_la_apertura_de_la_solicitud_sigue_pidiendo_todo_de_una_vez() -> None:
    caso = _Caso("es")

    salida = await caso.decir("Quiero una cotización")

    assert salida.intake_response_key == "intake.question.quote_all"


async def test_la_solicitud_no_se_cierra_sin_confirmarla() -> None:
    """BR1.2: con todo dicho, nada cuenta como completo hasta el si de la lectura."""
    caso = _Caso("es")
    salidas = await _decir_todo(caso)

    assert salidas[-1].intake_response_key == "intake.readback.quote_all"
    completitud = caso.completitud()
    assert completitud.complete == 0, "dichos y sin confirmar no cuentan"
    assert {"driver_name", "vin", "prior_coverage_active"} <= set(completitud.awaiting_readback)


async def test_un_si_confirma_toda_la_solicitud() -> None:
    caso = _Caso("es")
    await _decir_todo(caso)

    salida = await caso.decir(SI["es"])

    assert salida.intake_readback_resolved is not None
    assert salida.intake_readback_resolved.accepted is True
    assert caso.completitud().complete == caso.completitud().total


async def test_un_no_devuelve_a_nadie_lo_dijo_lo_que_no_se_volvio_a_decir() -> None:
    """Corregir en la misma frase conserva la correccion y borra el resto del bloque."""
    caso = _Caso("es")
    await _decir_todo(caso)

    salida = await caso.decir(
        "no, la licencia es de doce años", _item("license_years", "doce años")
    )

    assert salida.intake_readback_resolved is not None
    assert salida.intake_readback_resolved.accepted is False
    assert caso.valores["license_years"] == "12"
    # Lo que no se repitio vuelve a preguntarse, empezando por el conductor.
    assert "license_years" in caso.estados
    assert "driver_name" not in caso.estados
    assert salida.intake_response_key == "intake.question.quote_driver_name"


async def test_callar_no_confirma() -> None:
    """Un turno que no es un si explicito no confirma la solicitud (BR3.1)."""
    caso = _Caso("es")
    await _decir_todo(caso)

    salida = await caso.decir("mmm, no estoy seguro")

    assert salida.intake_readback_resolved is not None
    assert salida.intake_readback_resolved.accepted is False


async def test_un_dato_adelantado_no_se_vuelve_a_preguntar() -> None:
    """BR3.3: si el nombre y la fecha llegan juntos, la siguiente pregunta es la licencia."""
    caso = _Caso("es")

    salida = await caso.decir(
        "soy Marta Diaz, nací el 12 de abril de 1990",
        _item("driver_name", "Marta Diaz"),
        _item("driver_birth_date", "12 de abril de 1990"),
    )

    assert salida.intake_response_key == "intake.question.quote_license_years"


async def test_un_bloque_entero_adelantado_sigue_con_lo_que_falta() -> None:
    """Se confirma todo al final: con el conductor completo, se pregunta por el carro."""
    caso = _Caso("en")

    salida = await caso.decir(
        "I'm Marta Diaz, born April 12 1990, licensed for eight years in Corvane",
        _item("driver_name", "Marta Diaz"),
        _item("driver_birth_date", "April 12, 1990"),
        _item("license_years", "eight years"),
        _item("license_jurisdiction", "Corvane"),
    )

    assert salida.intake_response_key == "intake.question.quote_vehicle_year"
    assert salida.intake_awaiting_confirmation is None


async def test_una_clave_de_otro_tipo_de_caso_no_tumba_el_turno() -> None:
    """El prompt es uno para todos los tipos: el modelo puede devolver `injuries` en una solicitud."""
    caso = _Caso("es")

    salida = await caso.decir(
        "no hubo heridos, soy Marta",
        _item("injuries", "no hubo heridos"),
        _item("driver_name", "Marta"),
    )

    assert [c.field_key for c in salida.intake_extracted] == ["driver_name"]


# --- La lectura nombra lo dicho y nunca imprime el enum -----------------------------------------


@pytest.mark.parametrize("language", ["es", "en"])
async def test_las_lecturas_nombran_todo_lo_dicho_y_con_etiqueta_no_con_enum(
    language: Locale,
) -> None:
    caso = _Caso(language)
    salidas = await _recorrer(caso)
    lecturas = {
        s.intake_response_key: s.intake_response_text
        for s in salidas
        if s.intake_response_key.startswith("intake.readback.quote_")
    }

    # Una sola lectura con todo lo dicho (2026-10-08).
    todo = lecturas["intake.readback.quote_all"]
    for dicho in ("Marta Diaz Lopez", "Corvane", "8", "2014", "Mazda", "JM1BL1SF7A1234567"):
        assert dicho in todo
    vehiculo = uso = historial = todo
    # Los valores cerrados salen por su etiqueta, nunca por el valor del enum.
    for texto in lecturas.values():
        for enum in ("commuting", "commercial", "medium", "standard_risk", "true", "false"):
            # En ingles la etiqueta de dos valores coincide con su enum, y se dice asi.
            assert enum not in texto.lower() or (
                language == "en" and enum in {"commuting", "medium"}
            )
    assert ("para ir al trabajo" if language == "es" else "commuting") in uso
    assert ("normal" if language == "es" else "medium") in uso
    assert ("con seguro vigente" if language == "es" else "with active insurance") in historial
    assert (
        "nunca declarado pérdida total" if language == "es" else "never declared a total loss"
    ) in vehiculo


def test_cada_pregunta_cabe_en_la_regla_de_una_idea_en_los_dos_idiomas() -> None:
    """BR3.4: veinticinco palabras y una sola pregunta, para cada campo, en español y en ingles."""
    preguntables = [k for k in CLAVES if k not in extraction.DERIVED_FIELDS]
    for idioma in ("es", "en"):
        for clave in preguntables:
            _, frase = composition._quote_question((clave,), language=idioma)
            assert composition.assert_question_shape(frase) == (), (idioma, clave, frase)


def test_un_campo_derivado_nunca_se_pregunta_se_pregunta_el_dato_del_que_sale() -> None:
    clave, _ = composition._quote_question(("vehicle_age_years",), language="es")

    assert str(clave) == "intake.question.quote_vehicle_year"


# --- BR1.3: lo que las reglas leen llega convertido, y lo que no se convierte no se escribe ----------


def _extraer(clave: str, valor: str, language: Locale = "es", hoy: date = HOY) -> list[str]:
    campos = extraction.extract_fields(
        ExtractionResponse(items=(_item(clave, valor),)),
        turn_id="t1",
        turn_text=valor,
        language=language,
        now=hoy,
    )
    return [f"{c.field_key}={c.value}" for c in campos]


@pytest.mark.parametrize(
    ("clave", "dicho", "idioma", "escrito"),
    [
        ("license_years", "hace como ocho años", "es", ["license_years=8"]),
        ("license_years", "menos de un año", "es", ["license_years=0"]),
        ("license_years", "less than a year", "en", ["license_years=0"]),
        ("license_years", "twenty five", "en", ["license_years=25"]),
        ("at_fault_losses_3y", "ninguno", "es", ["at_fault_losses_3y=0"]),
        ("at_fault_losses_3y", "no, ninguno", "es", ["at_fault_losses_3y=0"]),
        ("at_fault_losses_3y", "twice", "en", ["at_fault_losses_3y=2"]),
        ("at_fault_losses_3y", "dos", "es", ["at_fault_losses_3y=2"]),
        ("salvage_title", "no, está limpio", "es", ["salvage_title=false"]),
        ("salvage_title", "sí, tiene", "es", ["salvage_title=true"]),
        ("salvage_title", "yes it does", "en", ["salvage_title=true"]),
        ("salvage_title", "no, it's clean", "en", ["salvage_title=false"]),
        ("use_type", "uso personal", "es", ["use_type=personal"]),
        ("use_type", "para ir al trabajo", "es", ["use_type=commuting"]),
        ("use_type", "hago entregas de domicilios", "es", ["use_type=commercial"]),
        ("use_type", "personal, y a veces entregas", "es", ["use_type=commercial"]),
        ("use_type", "commuting to work", "en", ["use_type=commuting"]),
        ("use_type", "I drive for Uber", "en", ["use_type=commercial"]),
        ("annual_mileage_band", "poco", "es", ["annual_mileage_band=low"]),
        ("annual_mileage_band", "no mucho", "es", ["annual_mileage_band=low"]),
        ("annual_mileage_band", "a lot", "en", ["annual_mileage_band=high"]),
        ("vehicle_year", "es un 2014", "es", ["vehicle_year=2014", "vehicle_age_years=12"]),
    ],
)
def test_lo_que_las_reglas_leen_se_escribe_convertido(
    clave: str, dicho: str, idioma: Locale, escrito: list[str]
) -> None:
    assert _extraer(clave, dicho, idioma) == escrito


@pytest.mark.parametrize(
    ("clave", "dicho", "idioma"),
    [
        ("use_type", "a veces", "es"),
        ("use_type", "it depends", "en"),
        ("salvage_title", "está limpio", "es"),
        ("salvage_title", "no idea", "en"),
        ("license_years", "muchos", "es"),
        ("at_fault_losses_3y", "algunos", "es"),
        ("annual_mileage_band", "depende", "es"),
        ("vehicle_year", "98", "es"),
        ("vehicle_year", "1850", "es"),
        ("vehicle_year", "2040", "es"),
    ],
)
def test_un_valor_que_no_se_puede_convertir_no_se_escribe(
    clave: str, dicho: str, idioma: Locale
) -> None:
    """El campo queda sin decir y se vuelve a preguntar: guardarlo dejaria la regla muda."""
    assert _extraer(clave, dicho, idioma) == []


def test_los_campos_sin_regla_se_escriben_como_se_dijeron() -> None:
    assert _extraer("driver_name", "Marta Diaz Lopez") == ["driver_name=Marta Diaz Lopez"]
    assert _extraer("garaging_jurisdiction", "Corvane") == ["garaging_jurisdiction=Corvane"]


def test_el_modelo_no_puede_escribir_un_campo_derivado() -> None:
    """Dos sitios que calculan la antiguedad son dos sitios que un dia discrepan (BR1.4)."""
    assert _extraer("vehicle_age_years", "99") == []


def test_los_meses_sin_cobertura_de_quien_tiene_cobertura_se_derivan_en_cero() -> None:
    assert _extraer("prior_coverage_active", "sí, tengo") == [
        "prior_coverage_active=true",
        "lapse_months=0",
    ]


def test_a_quien_no_tiene_cobertura_los_meses_se_le_preguntan() -> None:
    assert _extraer("prior_coverage_active", "no tengo") == ["prior_coverage_active=false"]
    assert _extraer("lapse_months", "seis meses") == ["lapse_months=6"]
    assert _extraer("lapse_months", "un año") == ["lapse_months=12"]


def test_lo_que_dijo_el_modelo_sobre_los_meses_manda_sobre_la_derivacion() -> None:
    respuesta = ExtractionResponse(
        items=(_item("prior_coverage_active", "sí"), _item("lapse_months", "tres meses"))
    )

    campos = extraction.extract_fields(
        respuesta, turn_id="t1", turn_text="sí, pero estuve tres meses sin", language="es", now=HOY
    )

    assert {c.field_key: c.value for c in campos} == {
        "prior_coverage_active": "true",
        "lapse_months": "3",
    }


def test_lo_derivado_comparte_la_evidencia_del_dato_de_origen() -> None:
    campos = extraction.extract_fields(
        ExtractionResponse(items=(_item("vehicle_year", "2014"),)),
        turn_id="t7",
        turn_text="es un 2014",
        language="es",
        now=HOY,
    )

    derivado = next(c for c in campos if c.field_key == "vehicle_age_years")
    assert derivado.evidence_turn_id == "t7"


# --- BR1.4: la antiguedad se calcula en un solo sitio, desde el reloj inyectado -----------------


@pytest.mark.parametrize(
    ("anio", "hoy", "edad"),
    [
        ("2014", date(2026, 9, 30), "12"),
        ("2014", date(2027, 1, 2), "13"),
        ("2000", date(2026, 9, 30), "26"),
        ("2027", date(2026, 9, 30), "0"),
    ],
)
def test_la_antiguedad_sale_del_anio_y_del_reloj_inyectado(anio: str, hoy: date, edad: str) -> None:
    """Dos corridas con el mismo reloj dan lo mismo; con otro reloj, otra antiguedad (y un modelo
    del anio que viene no tiene antiguedad negativa)."""
    assert normalization.derive_vehicle_age(anio, now=hoy) == edad
    assert _extraer("vehicle_year", anio, hoy=hoy)[1] == f"vehicle_age_years={edad}"


def test_la_antiguedad_no_lee_el_reloj_del_proceso() -> None:
    """El mismo caso, dos relojes inyectados: nada depende de la fecha de hoy de verdad."""
    una = _extraer("vehicle_year", "2014", hoy=date(2030, 6, 1))
    otra = _extraer("vehicle_year", "2014", hoy=date(2026, 6, 1))

    assert una[1] == "vehicle_age_years=16"
    assert otra[1] == "vehicle_age_years=12"


def test_la_antiguedad_se_calcula_en_un_solo_sitio_del_codigo() -> None:
    """BR1.4: ninguna otra resta de un anio contra el calendario aparece en el aplicativo.

    Se cuentan las restas `<algo>.year - ...` en todo `src`: solo `derive_vehicle_age` las hace.
    Una segunda, en una regla, en la bandeja o en una pantalla, es un segundo sitio que un dia
    discrepa del primero y que ninguna prueba de comportamiento vera.
    """
    raiz = paths.repo_root() / "app" / "backend" / "src" / "untangle"
    patron = re.compile(r"\.year\s*-")
    hallazgos = {
        str(archivo.relative_to(raiz)): len(patron.findall(archivo.read_text(encoding="utf-8")))
        for archivo in raiz.rglob("*.py")
        if patron.search(archivo.read_text(encoding="utf-8"))
    }

    assert hallazgos == {"orchestration/nodes/intake/normalization.py": 1}


def test_el_nombre_del_campo_derivado_solo_aparece_donde_debe() -> None:
    """Quien escribe `vehicle_age_years` es la captura; quien lo lee es el motor de reglas."""
    raiz = paths.repo_root() / "app" / "backend" / "src" / "untangle"
    permitidos = {
        "rules/fields.py",
        "rules/eligibility.py",
        "case_record/schema_loading.py",
        "case_record/labels.py",
        "case_record/schema/fields.yaml",
        "orchestration/nodes/intake/composition.py",
        "orchestration/nodes/intake/extraction.py",
        "orchestration/nodes/intake/normalization.py",
    }
    donde = {
        str(archivo.relative_to(raiz))
        for archivo in raiz.rglob("*")
        if archivo.suffix in {".py", ".yaml"}
        and "vehicle_age_years" in archivo.read_text(encoding="utf-8")
    }

    assert donde <= permitidos, sorted(donde - permitidos)
    assert "rules/eligibility.py" in donde
    assert "orchestration/nodes/intake/extraction.py" in donde


# --- Las tablas del normalizador, una a una -----------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "idioma", "esperado"),
    [
        ("8", "es", 8),
        ("tengo 12 años", "es", 12),
        ("treinta y cinco", "es", 35),
        ("veinticinco", "es", 25),
        ("thirty five", "en", 35),
        ("twenty-five", "en", 25),
        ("none", "en", 0),
        ("never", "en", 0),
        ("nunca", "es", 0),
        ("no", "es", 0),
        ("no", "en", 0),
        ("many", "en", None),
        ("", "es", None),
    ],
)
def test_parse_count(texto: str, idioma: Locale, esperado: int | None) -> None:
    assert normalization.parse_count(texto, language=idioma) == esperado


def test_ningun_valor_canonico_es_un_valor_que_el_modelo_pueda_escribir_distinto() -> None:
    """Las conversiones son funciones puras: mismo texto, mismo idioma, mismo resultado."""
    for _ in range(3):
        assert normalization.normalize_use_type("personal", language="es") == "personal"
        assert normalization.normalize_yes_no("no, está limpio", language="es") == "false"


def test_el_vin_se_normaliza_cuando_tiene_forma_de_vin_y_se_conserva_cuando_no() -> None:
    assert normalization.normalize_vin("jm1bl1sf7a1234567", language="es") == "JM1BL1SF7A1234567"
    assert normalization.normalize_vin("1234", language="es") is None
    assert _extraer("vin", "1234") == ["vin=1234"]


def test_cada_campo_tipado_tiene_su_conversion_y_es_de_la_solicitud() -> None:
    assert set(extraction._QUOTE_TYPED) <= set(CLAVES)
    assert extraction.DERIVED_FIELDS <= set(CLAVES)


def test_las_claves_del_prompt_de_extraccion_cubren_los_campos_que_se_preguntan() -> None:
    """Si el prompt no nombra un campo, el modelo no lo extrae y el bloque no termina nunca."""
    raiz = Path(paths.repo_root() / "app" / "config" / "prompts")
    preguntables = [k for k in CLAVES if k not in extraction.DERIVED_FIELDS]
    for idioma in ("es", "en"):
        texto = (raiz / f"intake_extraction.{idioma}.md").read_text(encoding="utf-8")
        faltan = [k for k in preguntables if f"`{k}`" not in texto]
        assert faltan == [], (idioma, faltan)
        assert "`vehicle_age_years`" not in texto, "lo deriva el codigo; el modelo no lo escribe"


# --- PERF-U19.2: soportar cotizacion no agranda el turno -------------------------------------------


def _p95(muestras: list[float]) -> float:
    muestras = sorted(muestras)
    return muestras[max(0, int(len(muestras) * 0.95) - 1)]


async def test_perf_u19_2_el_turno_de_un_bloque_de_la_solicitud_cabe_en_el_presupuesto_del_nodo() -> (
    None
):
    """El mismo techo que PERF-U12.3 (p95 de 50 ms, sin proveedor) para un turno de la solicitud.

    La elegibilidad corre en el ritmo de fondo y no se espera aqui: lo unico que se mide es la
    captura de un campo tipado, su derivacion y la pregunta siguiente.
    """
    import time

    muestras: list[float] = []
    for _ in range(100):
        caso = _Caso("es")
        empezo = time.perf_counter()
        await caso.decir("es un 2014", _item("vehicle_year", "es un 2014"))
        muestras.append((time.perf_counter() - empezo) * 1000)

    assert _p95(muestras) <= 50.0, f"p95 = {_p95(muestras):.3f} ms"


def test_perf_u19_2_las_frases_fijas_de_la_cotizacion_caben_en_el_presupuesto_de_los_controles() -> (
    None
):
    """`reply_before_capture` corre en el camino del turno: dos expresiones regulares, p95 de 1 ms."""
    import time

    from untangle.orchestration import quote_reply

    muestras: list[float] = []
    for n in range(500):
        empezo = time.perf_counter()
        quote_reply.reply_before_capture(
            record_type=RecordType.QUOTE_REQUEST,
            anything_captured=True,
            quote_enabled=True,
            text=f"vivo en Corvane, mi auto es un Mazda {2000 + n % 20}",
            language="es",
        )
        muestras.append((time.perf_counter() - empezo) * 1000)

    assert _p95(muestras) <= 1.0, f"p95 = {_p95(muestras):.4f} ms"


async def test_seguir_contando_no_deja_una_lectura_a_medias() -> None:
    """Visto en produccion el 2026-10-08: a "¿Es correcto?" sobre el conductor la persona
    contesto con su vehiculo y la agente borraba al conductor. Desde que la solicitud se
    lee una sola vez al final, a mitad de camino no hay lectura que borrar: el vehiculo
    se anota y el conductor sigue dicho."""
    caso = _Caso("es")
    for clave, texto in GUION["es"][:4]:
        await caso.decir(texto, _item(clave, texto))

    salida = await caso.decir("Es un Mazda 3 2021", _item("vehicle_year", "2021"))

    assert salida.intake_readback_resolved is None
    assert "driver_name" in caso.completitud().awaiting_readback
    assert caso.valores["vehicle_year"] == "2021"


async def test_un_no_a_la_lectura_sigue_borrando_lo_leido() -> None:
    """El control: un no explicito sigue siendo un no (BR3.1)."""
    caso = _Caso("es")
    await _decir_todo(caso)

    salida = await caso.decir("No")

    assert salida.intake_readback_resolved is not None
    assert not salida.intake_readback_resolved.accepted


async def test_no_tener_el_vin_a_la_mano_se_anota_y_no_se_repite_la_pregunta() -> None:
    """Visto el 2026-10-08: "no lo tengo a la mano" volvia a pedir el VIN y un "no" seco
    si se anotaba. Una respuesta corta a un dato de texto libre se guarda tal cual."""
    caso = _Caso("es")
    for clave, texto in GUION["es"][:7]:
        await caso.decir(texto, _item(clave, texto))

    salida = await caso.decir("No lo tengo a la mano")

    assert caso.valores["vin"] == "No lo tengo a la mano"
    assert salida.intake_response_key != "intake.question.quote_vin"


async def test_un_dato_con_tipo_que_no_se_entiende_no_se_guarda_a_ciegas() -> None:
    """El control: los anos de licencia tienen tipo; un texto que no los dice no se
    escribe en el campo, y se vuelve a preguntar."""
    caso = _Caso("es")
    for clave, texto in GUION["es"][:2]:
        await caso.decir(texto, _item(clave, texto))

    await caso.decir("depende")

    assert "license_years" not in caso.valores
