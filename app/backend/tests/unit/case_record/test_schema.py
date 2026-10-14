"""El esquema versionado: que declara y que no deja cargar (BR1.3 a BR1.6, BR3.2).

Lo que estas pruebas protegen es que **un esquema a medias no arranque**. Es el
fallo que no se manifiesta: un campo que falta de la lista no rompe ninguna
pantalla, solo hace que la completitud publique una cifra sobre un denominador
equivocado. Sigue saliendo un numero, solo que el equivocado.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from untangle.case_record import schema_loading as carga
from untangle.case_record.models import CaseSchemaError, CaseState, RecordType


def _crudo(nombre: str) -> dict[str, Any]:
    """El archivo real, sin validar, para poder romperlo a proposito."""
    cargado: Any = yaml.safe_load((carga.schema_dir() / nombre).read_text(encoding="utf-8"))
    assert isinstance(cargado, dict)
    return cargado


def _escribir(directorio: Path, nombre: str, datos: dict[str, Any]) -> None:
    (directorio / nombre).write_text(
        yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


# --- Lo que hay, que tiene que estar -----------------------------------------


def test_el_siniestro_declara_sus_siete_campos_centrales() -> None:
    """FR1.1 los fija, y el orden importa porque es el de la guia de la conversacion."""
    campos = carga.load_fields()[RecordType.CLAIM]

    assert tuple(c.key for c in campos) == carga.CLAIM_FIELDS


def test_solo_tres_campos_del_siniestro_exigen_lectura_en_voz_alta() -> None:
    """Lesiones, lugar, y vehiculo y conductor (BR2.2, ADR-005).

    Si fueran mas, la completitud exigiria confirmar campos que la decision de
    arquitectura no obliga a confirmar, y un caso completo dejaria de serlo.
    """
    campos = carga.load_fields()[RecordType.CLAIM]

    assert {c.key for c in campos if c.requires_readback} == carga.READBACK_FIELDS


def test_la_consulta_de_cobertura_declara_dos_campos_y_ninguno_del_accidente() -> None:
    """AC1.3.6 la abre sin la pregunta de seguridad; AC2.4.3 exige contar por tipo."""
    campos = carga.load_fields()[RecordType.COVERAGE_INQUIRY]

    assert tuple(c.key for c in campos) == ("identity_and_policy", "question_asked")
    assert not {c.key for c in campos} & set(carga.CLAIM_FIELDS[1:])


def test_la_solicitud_de_cotizacion_declara_sus_cuatro_bloques() -> None:
    """U19, BR1.2: conductor, vehiculo, uso e historial, en ese orden y con esos campos.

    Los nombres son los de `docs/reference/estructura-solicitud-cotizacion.md`. Si el
    archivo declara dieciseis, la completitud publica una cifra sobre dieciseis y nadie lo
    nota: por eso el cargador lo compara con la lista versionada y esta prueba con el documento.
    """
    campos = carga.load_fields()[RecordType.QUOTE_REQUEST]

    assert tuple(c.key for c in campos) == carga.QUOTE_FIELDS
    assert len(campos) == 17
    por_bloque: dict[str, tuple[str, ...]] = {}
    for campo in campos:
        por_bloque[campo.source_block] = (*por_bloque.get(campo.source_block, ()), campo.key)
    assert por_bloque == carga.QUOTE_FIELDS_BY_BLOCK
    assert tuple(por_bloque) == ("quote_driver", "quote_vehicle", "quote_usage", "quote_history")


def test_todo_campo_de_la_solicitud_exige_lectura_porque_el_bloque_se_confirma() -> None:
    """AC6.1.2: la confirmacion es por bloque, y un bloque sin campos con lectura no se confirmaria."""
    campos = carga.load_fields()[RecordType.QUOTE_REQUEST]

    assert all(c.requires_readback for c in campos)


def test_una_solicitud_con_un_campo_menos_no_carga(tmp_path: Path) -> None:
    datos = copy.deepcopy(_crudo("fields.yaml"))
    datos["record_types"]["quote_request"]["fields"].pop()
    _escribir(tmp_path, "fields.yaml", datos)

    with pytest.raises(CaseSchemaError) as error:
        carga.load_fields(tmp_path)

    assert "cotizacion" in str(error.value)


def test_una_solicitud_cuyo_campo_no_exige_lectura_no_carga(tmp_path: Path) -> None:
    datos = copy.deepcopy(_crudo("fields.yaml"))
    datos["record_types"]["quote_request"]["fields"][0]["requires_readback"] = False
    _escribir(tmp_path, "fields.yaml", datos)

    with pytest.raises(CaseSchemaError) as error:
        carga.load_fields(tmp_path)

    assert "driver_name" in str(error.value)


def test_la_tabla_declara_doce_transiciones_y_ninguna_mas() -> None:
    """BR3.2: lo que no esta en la tabla se rechaza, asi que la tabla es el modelo."""
    filas = carga.load_transitions()

    assert len(filas) == 12
    assert [f.id for f in filas] == [f"T{n}" for n in range(1, 13)]


def test_ningun_estado_queda_sin_salida_salvo_el_terminal() -> None:
    """Un estado sin salida es un caso atrapado, y AC1.14.4 quiere esa cifra en cero."""
    filas = carga.load_transitions()
    con_salida = {f.from_state for f in filas}

    sin_salida = set(CaseState) - con_salida
    assert sin_salida == {CaseState.CLOSED}


def test_todos_los_estados_son_alcanzables_desde_el_inicial() -> None:
    """Un estado inalcanzable es una fila de la tabla que no describe nada."""
    filas = carga.load_transitions()
    alcanzados = {CaseState.OPEN}
    while True:
        nuevos = {f.to_state for f in filas if f.from_state in alcanzados} - alcanzados
        if not nuevos:
            break
        alcanzados |= nuevos

    assert alcanzados == set(CaseState)


def test_la_unica_vuelta_a_la_captura_es_la_del_limite_de_la_demostracion() -> None:
    """BR3.3, ADR-005. Y lleva sus cuatro condiciones, no una ni tres."""
    filas = carga.load_transitions()
    hacia_captura = [f for f in filas if f.to_state is CaseState.CAPTURING]

    vuelta = [f for f in hacia_captura if f.from_state is not CaseState.OPEN]
    assert len(vuelta) == 1
    assert vuelta[0].from_state is CaseState.DERIVED
    assert len(vuelta[0].conditions) == 4


# --- Lo que no puede cargar ---------------------------------------------------


def test_un_siniestro_con_seis_campos_no_carga(tmp_path: Path) -> None:
    """Es el fallo silencioso que motiva este archivo: la cifra saldria sobre seis."""
    datos = copy.deepcopy(_crudo("fields.yaml"))
    datos["record_types"]["claim"]["fields"].pop()
    _escribir(tmp_path, "fields.yaml", datos)

    with pytest.raises(CaseSchemaError) as error:
        carga.load_fields(tmp_path)

    assert "siniestro" in str(error.value)


def test_un_tipo_de_registro_que_falta_no_carga(tmp_path: Path) -> None:
    """Los tres tipos del enum tienen que estar declarados, o crear uno fallaria tarde."""
    datos = copy.deepcopy(_crudo("fields.yaml"))
    del datos["record_types"]["coverage_inquiry"]
    _escribir(tmp_path, "fields.yaml", datos)

    with pytest.raises(CaseSchemaError) as error:
        carga.load_fields(tmp_path)

    assert "coverage_inquiry" in str(error.value)


def test_cambiar_que_campo_exige_lectura_no_carga(tmp_path: Path) -> None:
    """Moverlo aqui cambiaria en silencio lo que cuenta como caso completo."""
    datos = copy.deepcopy(_crudo("fields.yaml"))
    datos["record_types"]["claim"]["fields"][3]["requires_readback"] = True
    _escribir(tmp_path, "fields.yaml", datos)

    with pytest.raises(CaseSchemaError):
        carga.load_fields(tmp_path)


def test_una_transicion_con_un_estado_inventado_no_carga(tmp_path: Path) -> None:
    """El modelo es cerrado: un estado fuera de los siete no existe (BR3.1)."""
    datos = copy.deepcopy(_crudo("transitions.yaml"))
    datos["transitions"][0]["to"] = "en_revision"
    _escribir(tmp_path, "transitions.yaml", datos)

    with pytest.raises(CaseSchemaError):
        carga.load_transitions(tmp_path)


def test_dos_transiciones_con_el_mismo_identificador_no_cargan(tmp_path: Path) -> None:
    """El identificador es como el diagrama y las pruebas nombran cada arista."""
    datos = copy.deepcopy(_crudo("transitions.yaml"))
    datos["transitions"][1]["id"] = datos["transitions"][0]["id"]
    _escribir(tmp_path, "transitions.yaml", datos)

    with pytest.raises(CaseSchemaError):
        carga.load_transitions(tmp_path)


def test_una_transicion_que_sale_de_cerrado_no_carga(tmp_path: Path) -> None:
    """`closed` es terminal. Una salida de ahi es exactamente el camino que
    AC4.10.1 quiere imposible: un caso cerrado que vuelve a moverse."""
    datos = copy.deepcopy(_crudo("transitions.yaml"))
    datos["transitions"].append(
        {"id": "T13", "from": "closed", "to": "capturing", "when": "inventada", "conditions": []}
    )
    _escribir(tmp_path, "transitions.yaml", datos)

    with pytest.raises(CaseSchemaError) as error:
        carga.load_transitions(tmp_path)

    assert "terminal" in str(error.value)


def test_un_archivo_que_falta_falla_nombrandolo(tmp_path: Path) -> None:
    """Fallar cerrado: sin su esquema, el caso no se puede validar."""
    with pytest.raises(CaseSchemaError) as error:
        carga.load_fields(tmp_path)

    assert "fields.yaml" in str(error.value)
