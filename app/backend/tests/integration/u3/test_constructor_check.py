"""El chequeo del tipo y de la boveda, con las violaciones plantadas una a una.

Una regla que nunca se ha visto fallar no es una regla comprobada: es una regla
que se supone que funciona. Cada prueba de aqui planta **una** de las formas de
saltarse el control y exige que el chequeo la encuentre y la nombre.

La primera prueba es la que les da valor a las demas: comprueba que el arbol
correcto **pasa**. Sin ella, un error del andamiaje que hiciera fallar todo se
leeria como un chequeo que funciona, y es un error facil de cometer --una ruta
mal escrita, un directorio que no existe-- y dificil de notar, porque el sintoma
es exactamente el que se esperaba ver.

Las violaciones se plantan como **texto**, no como codigo de este archivo: asi el
chequeo, que tambien recorre las pruebas, no encuentra en este archivo lo que las
pruebas plantan a proposito en otro sitio.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from untangle.workspace import redaction_constructor as chequeo

#: El arbol minimo correcto: el unico archivo que produce el tipo lo produce, y
#: ningun otro lo toca.
ARBOL: dict[str, str] = {
    "app/backend/src/untangle/compliance/redaction/api.py": (
        "from typing import NewType\n"
        "\n"
        'Redacted = NewType("Redacted", str)\n'
        "\n"
        "\n"
        "def redact(text: str) -> Redacted:\n"
        "    return Redacted(text.upper())\n"
    ),
    "app/backend/src/untangle/compliance/redaction/labels.py": (
        'def etiqueta(numero: int) -> str:\n    return f"[DATO {numero}]"\n'
    ),
    "app/backend/src/untangle/case_record/api.py": (
        "from untangle.compliance.redaction.api import Redacted\n"
        "\n"
        "\n"
        "def guardar(turno: Redacted) -> None:\n"
        "    print(turno)\n"
    ),
    "app/backend/tests/unit/redaction/test_algo.py": (
        "def test_algo() -> None:\n    assert True\n"
    ),
}


def _sembrar(raiz: Path, extra: dict[str, str] | None = None) -> Path:
    contenido = dict(ARBOL)
    contenido.update(extra or {})
    for ruta, texto in contenido.items():
        archivo = raiz / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(texto, encoding="utf-8")
    return raiz


# --- La linea base ------------------------------------------------------------


def test_el_arbol_correcto_pasa(tmp_path: Path) -> None:
    """Sin violacion plantada, el chequeo no encuentra nada.

    Es la prueba que impide que un fallo del andamiaje se lea como exito.
    """
    _sembrar(tmp_path)

    assert chequeo.run_all(tmp_path) == []


def test_el_archivo_que_produce_el_tipo_puede_producirlo(tmp_path: Path) -> None:
    """`api.py` invoca el constructor y eso **no** es un hallazgo.

    Si lo fuera, el chequeo seria inutilizable: no habria forma de fabricar un
    `Redacted` en ningun sitio, ni siquiera donde debe fabricarse.
    """
    _sembrar(tmp_path)

    hallazgos = chequeo.run_all(tmp_path)

    assert not [h for h in hallazgos if "redaction/api.py" in h.where]


def test_usar_el_tipo_en_una_firma_no_es_producirlo(tmp_path: Path) -> None:
    """Un punto de salida **exige** `Redacted`; exigirlo es lo que se quiere.

    Si anotar el tipo contara como producirlo, la regla prohibiria justo la
    conducta que existe para imponer.
    """
    _sembrar(tmp_path)

    hallazgos = chequeo.run_all(tmp_path)

    assert not [h for h in hallazgos if "case_record" in h.where]


# --- Las tres formas de producir el tipo (BR1.8, NFRD-U3-7) -------------------


def test_atrapa_la_llamada_al_constructor_fuera_de_su_archivo(tmp_path: Path) -> None:
    """La forma obvia: `Redacted(texto_sin_tapar)`.

    Es una llamada legal que el comprobador de tipos acepta, porque `NewType` se
    borra en tiempo de ejecucion. Sin este chequeo, la garantia se apoyaria en
    que a nadie se le ocurra escribirla.
    """
    _sembrar(
        tmp_path,
        {
            "app/backend/src/untangle/inbox/export.py": (
                "from untangle.compliance.redaction.api import Redacted\n"
                "\n"
                "\n"
                "def exportar(texto: str) -> Redacted:\n"
                "    return Redacted(texto)\n"
            )
        },
    )

    hallazgos = chequeo.run_all(tmp_path)

    assert [h for h in hallazgos if "inbox/export.py" in h.where and h.rule == "BR1.8"]


def test_atrapa_el_cast_que_afirma_el_tipo_sin_construirlo(tmp_path: Path) -> None:
    """La puerta de al lado: `cast(Redacted, texto)`.

    Entrega exactamente lo mismo que la llamada, sin invocar nunca el
    constructor. Un control que solo cubre la forma obvia atrapa descuidos y no
    atajos.
    """
    _sembrar(
        tmp_path,
        {
            "app/backend/src/untangle/inbox/export.py": (
                "from typing import cast\n"
                "\n"
                "from untangle.compliance.redaction.api import Redacted\n"
                "\n"
                "\n"
                "def exportar(texto: str) -> Redacted:\n"
                "    return cast(Redacted, texto)\n"
            )
        },
    )

    hallazgos = chequeo.run_all(tmp_path)

    assert [h for h in hallazgos if "inbox/export.py" in h.where and h.rule == "BR1.8"]


def test_atrapa_la_anotacion_que_silencia_al_comprobador(tmp_path: Path) -> None:
    """La tercera: anotar el tipo y callar al comprobador con `type: ignore`."""
    _sembrar(
        tmp_path,
        {
            "app/backend/src/untangle/inbox/export.py": (
                "from untangle.compliance.redaction.api import Redacted\n"
                "\n"
                "\n"
                "def exportar(texto: str) -> None:\n"
                "    seguro: Redacted = texto  # type: ignore[assignment]\n"
                "    print(seguro)\n"
            )
        },
    )

    hallazgos = chequeo.run_all(tmp_path)

    assert [h for h in hallazgos if "inbox/export.py" in h.where and h.rule == "BR1.8"]


def test_atrapa_la_firma_silenciada(tmp_path: Path) -> None:
    """La misma tercera forma, movida a la firma en vez del cuerpo.

    Faltaba, y por eso el chequeo de la firma vivio roto: preguntaba por el
    numero de linea a un nodo que no lo lleva, asi que miraba un tramo vacio y
    no disparaba nunca.
    """
    _sembrar(
        tmp_path,
        {
            "app/backend/src/untangle/inbox/export.py": (
                "from untangle.compliance.redaction.api import Redacted\n"
                "\n"
                "\n"
                "def exportar(\n"
                "    texto: Redacted,  # type: ignore[assignment]\n"
                ") -> None:\n"
                "    print(texto)\n"
            )
        },
    )

    hallazgos = chequeo.run_all(tmp_path)

    assert [h for h in hallazgos if "inbox/export.py" in h.where and h.rule == "BR1.8"]


def test_atrapa_las_tres_formas_a_la_vez(tmp_path: Path) -> None:
    """Las tres juntas dan tres hallazgos, no uno.

    Importa: quien arregla la primera y vuelve a correr tiene que seguir viendo
    las otras dos, en vez de descubrirlas de una en una.
    """
    _sembrar(
        tmp_path,
        {
            "app/backend/src/untangle/inbox/export.py": (
                "from typing import cast\n"
                "\n"
                "from untangle.compliance.redaction.api import Redacted\n"
                "\n"
                "\n"
                "def exportar(texto: str) -> None:\n"
                "    uno = Redacted(texto)\n"
                "    dos = cast(Redacted, texto)\n"
                "    tres: Redacted = texto  # type: ignore[assignment]\n"
                "    print(uno, dos, tres)\n"
            )
        },
    )

    hallazgos = [
        h for h in chequeo.run_all(tmp_path) if "inbox/export.py" in h.where and h.rule == "BR1.8"
    ]

    assert len(hallazgos) == 3


# --- Ninguna boveda (BR1.6, SEC-U3.7, SEC-U3.8) -------------------------------


def test_atrapa_el_diccionario_indexado_por_el_valor_detectado(tmp_path: Path) -> None:
    """La forma mas comun de construir una boveda sin querer.

    Quien quiere que el mismo telefono conserve su numero entre turnos escribe
    exactamente esto, y con ello crea el unico sitio del sistema donde estan
    todos los datos personales juntos.
    """
    _sembrar(
        tmp_path,
        {
            "app/backend/src/untangle/compliance/redaction/labels.py": (
                "_MEMORIA: dict[str, str] = {}\n"
                "\n"
                "\n"
                "def etiquetar(texto: str, inicio: int, fin: int, etiqueta: str) -> None:\n"
                "    _MEMORIA[texto[inicio:fin]] = etiqueta\n"
            )
        },
    )

    hallazgos = chequeo.run_all(tmp_path)

    assert [h for h in hallazgos if h.rule == "BR1.6" and "labels.py" in h.where]


def test_atrapa_el_contenedor_donde_se_guarda_el_valor(tmp_path: Path) -> None:
    """Guardar el trozo "solo para depurar" es guardar el dato personal."""
    _sembrar(
        tmp_path,
        {
            "app/backend/src/untangle/compliance/redaction/detector.py": (
                "def depurar(texto: str, inicio: int, fin: int, vistos: list[str]) -> None:\n"
                "    vistos.append(texto[inicio:fin])\n"
            )
        },
    )

    hallazgos = chequeo.run_all(tmp_path)

    assert [h for h in hallazgos if h.rule == "BR1.6" and "detector.py" in h.where]


def test_atrapa_la_clase_que_lleva_el_hallazgo_y_su_valor(tmp_path: Path) -> None:
    """Un hallazgo que cargue su valor convierte cualquier volcado en una fuga."""
    _sembrar(
        tmp_path,
        {
            "app/backend/src/untangle/compliance/redaction/detector.py": (
                "from dataclasses import dataclass\n"
                "\n"
                "\n"
                "@dataclass\n"
                "class Hallazgo:\n"
                "    entity_type: str\n"
                "    value: str\n"
            )
        },
    )

    hallazgos = chequeo.run_all(tmp_path)

    assert [h for h in hallazgos if h.rule == "BR1.6" and "detector.py" in h.where]


def test_comparar_dos_trozos_sin_guardarlos_no_es_una_boveda(tmp_path: Path) -> None:
    """Es exactamente lo que hace la numeracion de etiquetas (BR3.3).

    Si mirarlos contara como guardarlos, la unica forma de que el mismo valor
    repetido conservara su numero seria la boveda que la regla prohibe: el
    chequeo estaria empujando hacia lo que existe para impedir.
    """
    _sembrar(
        tmp_path,
        {
            "app/backend/src/untangle/compliance/redaction/labels.py": (
                "def es_el_mismo(texto: str, a: tuple[int, int], b: tuple[int, int]) -> bool:\n"
                "    return texto[a[0]:a[1]] == texto[b[0]:b[1]]\n"
            )
        },
    )

    assert chequeo.run_all(tmp_path) == []


def test_la_boveda_solo_se_busca_dentro_del_modulo_de_redaccion(tmp_path: Path) -> None:
    """Fuera del modulo, un trozo de texto en una lista es texto cualquiera.

    Es el unico sitio del aplicativo que ve a la vez el texto en claro y sus
    hallazgos; aplicar la regla en todas partes la llenaria de hallazgos que no
    son datos personales y acabaria con alguien apagandola.
    """
    _sembrar(
        tmp_path,
        {
            "app/backend/src/untangle/policy_rag/corpus.py": (
                "def trocear(texto: str, cortes: list[int], salida: list[str]) -> None:\n"
                "    for inicio in cortes:\n"
                "        salida.append(texto[inicio:inicio + 40])\n"
            )
        },
    )

    assert chequeo.run_all(tmp_path) == []


# --- Que el chequeo nombre lo que encontro ------------------------------------


def test_el_hallazgo_nombra_el_archivo_y_la_linea(tmp_path: Path) -> None:
    """Un chequeo que solo dice "fallo" obliga a buscar a mano lo que ya sabia."""
    _sembrar(
        tmp_path,
        {
            "app/backend/src/untangle/inbox/export.py": (
                "from untangle.compliance.redaction.api import Redacted\n"
                "\n"
                "\n"
                "def exportar(texto: str) -> Redacted:\n"
                "    return Redacted(texto)\n"
            )
        },
    )

    (hallazgo,) = [h for h in chequeo.run_all(tmp_path) if "inbox/export.py" in h.where]

    assert hallazgo.where.endswith(":5")
    assert "Redacted" in hallazgo.detail


def test_una_prueba_tampoco_puede_fabricar_el_tipo(tmp_path: Path) -> None:
    """Las pruebas entran en el alcance a proposito.

    Una prueba que fabricara un `Redacted` falso estaria comprobando la garantia
    contra si misma: pasaria siempre, y con la redaccion rota tambien.
    """
    _sembrar(
        tmp_path,
        {
            "app/backend/tests/unit/redaction/test_algo.py": (
                "from untangle.compliance.redaction.api import Redacted\n"
                "\n"
                "\n"
                "def test_algo() -> None:\n"
                '    assert Redacted("sin tapar")\n'
            )
        },
    )

    assert [h for h in chequeo.run_all(tmp_path) if "test_algo.py" in h.where]


@pytest.mark.parametrize("ruta", sorted(ARBOL))
def test_el_arbol_de_la_linea_base_es_codigo_valido(ruta: str, tmp_path: Path) -> None:
    """El andamiaje se compila. Un arbol con un error de sintaxis produciria un
    hallazgo por archivo y la linea base pasaria a ser una mentira."""
    import ast

    ast.parse(ARBOL[ruta])
