"""La redaccion de U3 encuentra cada valor personal sembrado, por tipo e idioma (NFR11.10, BR7.2).

Cada valor de `app/data/personal_values.json` se pone en una frase como la que
diria la persona que lo tiene, en su idioma, y se pasa por `redact()`. El valor
no puede sobrevivir entero a la redaccion. Una prueba por tipo y por idioma, para
que el reporte diga cual de las catorce combinaciones fallo y nunca un promedio
(P12).

Dos afirmaciones, y las dos hacen falta:

- **El valor no sobrevive entero** a `redact()`, que es lo que ve quien lee la
  transcripcion.
- **Un hallazgo de su tipo lo cubre entero**, que es el "por tipo" de NFR11.10.
  La primera sola no basta: tapar "Megan" deja "Megan Hughes" fuera del texto y
  "Hughes" a la vista, y tapar la cola de digitos de un VIN deja fuera el VIN
  entero con el fabricante, el modelo y el ano a la vista. Asi salian las dos
  cosas antes de la correccion de U3 del 2026-09-21 (la regla de
  autoidentificacion y el reconocedor de VIN).

Usa los modelos de U3 (`mise run models:install`), como `test:u3`: lo que se
prueba es que el detector detecta, y un doble no detecta nada.
"""

from __future__ import annotations

import json
from collections import defaultdict

import pytest

from untangle.base import Locale
from untangle.compliance.redaction import detector as deteccion
from untangle.compliance.redaction.api import redact
from untangle.compliance.redaction.recognizers.models import EntityType
from untangle.synthetic_data.models import PersonalValueKind

from .apoyo import RAIZ_REAL

#: Como dice cada dato la persona que lo tiene. Frases corrientes, las de un
#: reporte por chat: el contexto que traen es el que trae una conversacion real.
FRASES: dict[str, dict[PersonalValueKind, str]] = {
    "es": {
        PersonalValueKind.NAME: "Me llamo {}.",
        PersonalValueKind.PHONE: "Mi celular es {}.",
        PersonalValueKind.NATIONAL_ID: "Mi cédula es {}.",
        PersonalValueKind.EMAIL: "Mi correo es {}.",
        PersonalValueKind.PLATE: "La placa de mi carro es {}.",
        PersonalValueKind.VIN: "El número de VIN de mi carro es {}.",
        PersonalValueKind.POLICY_NUMBER: "Mi póliza es la {}.",
    },
    "en": {
        PersonalValueKind.NAME: "My name is {}.",
        PersonalValueKind.PHONE: "My cell number is {}.",
        PersonalValueKind.NATIONAL_ID: "My ID number is {}.",
        PersonalValueKind.EMAIL: "My email is {}.",
        PersonalValueKind.PLATE: "My car's plate is {}.",
        PersonalValueKind.VIN: "The VIN number is {}.",
        PersonalValueKind.POLICY_NUMBER: "My policy is {}.",
    },
}


#: El tipo de entidad de U3 que tiene que cubrir cada clase de valor sembrado.
TIPO_DE_U3: dict[PersonalValueKind, EntityType] = {
    PersonalValueKind.NAME: EntityType.PERSON,
    PersonalValueKind.PHONE: EntityType.PHONE,
    PersonalValueKind.NATIONAL_ID: EntityType.NATIONAL_ID,
    PersonalValueKind.EMAIL: EntityType.EMAIL,
    PersonalValueKind.PLATE: EntityType.LICENSE_PLATE,
    PersonalValueKind.VIN: EntityType.VIN,
    PersonalValueKind.POLICY_NUMBER: EntityType.POLICY_NUMBER,
}


def _por_tipo_e_idioma() -> dict[tuple[str, str], list[str]]:
    archivo = RAIZ_REAL / "app" / "data" / "personal_values.json"
    grupos: dict[tuple[str, str], list[str]] = defaultdict(list)
    for valor in json.loads(archivo.read_text(encoding="utf-8"))["values"]:
        grupos[(valor["kind"], valor["language"])].append(valor["value"])
    return grupos


GRUPOS = _por_tipo_e_idioma()


def test_hay_valores_de_cada_tipo_en_los_dos_idiomas() -> None:
    """Sin esto, una combinacion sin valores pasaria la prueba de abajo sin probar nada."""
    esperadas = {(k.value, idioma) for k in PersonalValueKind for idioma in ("es", "en")}
    assert esperadas <= set(GRUPOS)


@pytest.mark.parametrize(
    ("kind", "language"),
    [(k.value, idioma) for k in PersonalValueKind for idioma in ("es", "en")],
    ids=lambda v: str(v),
)
def test_la_redaccion_encuentra_cada_valor_sembrado(kind: str, language: str) -> None:
    frase = FRASES[language][PersonalValueKind(kind)]
    escapados = [
        valor
        for valor in GRUPOS.get((kind, language), [])
        if valor in redact(frase.format(valor), language="es" if language == "es" else "en")
    ]
    assert escapados == [], (
        f"{len(escapados)} valor(es) de tipo {kind} en '{language}' salen sin redactar: {escapados}"
    )


def test_cada_clase_de_valor_tiene_su_tipo_en_u3() -> None:
    """Una clase nueva sin tipo haria pasar la prueba de abajo sin medir nada."""
    assert set(TIPO_DE_U3) == set(PersonalValueKind)


@pytest.mark.parametrize(
    ("kind", "language"),
    [(k.value, idioma) for k in PersonalValueKind for idioma in ("es", "en")],
    ids=lambda v: str(v),
)
def test_un_hallazgo_de_su_tipo_cubre_cada_valor_entero(kind: str, language: str) -> None:
    clase = PersonalValueKind(kind)
    tipo = TIPO_DE_U3[clase]
    idioma: Locale = "es" if language == "es" else "en"
    detector = deteccion.get_detector()

    sin_cubrir = []
    for valor in GRUPOS.get((kind, language), []):
        frase = FRASES[language][clase].format(valor)
        inicio = frase.index(valor)
        fin = inicio + len(valor)
        hallazgos = detector.detect(frase, language=idioma)
        if not any(h.entity_type is tipo and h.start <= inicio and fin <= h.end for h in hallazgos):
            sin_cubrir.append(valor)

    assert sin_cubrir == [], (
        f"{len(sin_cubrir)} valor(es) de tipo {kind} en '{language}' sin un hallazgo "
        f"de tipo {tipo.value} que los cubra enteros: {sin_cubrir}"
    )
