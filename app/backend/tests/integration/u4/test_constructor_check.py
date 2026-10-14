"""El chequeo del tipo sellado, con las violaciones plantadas una a una.

Una regla que nunca se ha visto fallar no es una regla comprobada: es una regla
que se supone que funciona. Cada prueba de aqui planta **una** de las tres
formas de saltarse el punto unico de cifrado y exige que el chequeo la
encuentre y la nombre.

La primera prueba es la que les da valor a las demas: comprueba que el arbol
correcto **pasa**. Sin ella, un error del andamiaje --una ruta mal escrita, un
directorio que no existe-- se leeria como un chequeo que funciona, porque el
sintoma seria exactamente el que se esperaba ver.

Las violaciones se plantan como **texto**, no como codigo de este archivo: asi
el chequeo, que tambien recorre las pruebas, no encuentra aqui lo que las
pruebas plantan a proposito en otro sitio.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from untangle.workspace import case_constructor as chequeo

#: El arbol minimo correcto: el punto unico de cifrado fabrica el tipo por las
#: dos puertas que tiene --sellar y declarar lo que vino de la columna--, el
#: modulo que lo declara solo lo nombra, y el repositorio lo transporta sin
#: fabricarlo nunca.
ARBOL: dict[str, str] = {
    "app/backend/src/untangle/case_record/models.py": (
        "from typing import NewType\n"
        "\n"
        'Sealed = NewType("Sealed", bytes)\n'
        'KeyId = NewType("KeyId", str)\n'
    ),
    "app/backend/src/untangle/case_record/crypto.py": (
        "from untangle.case_record.models import Sealed\n"
        "\n"
        "\n"
        "def from_storage(raw: bytes) -> Sealed:\n"
        "    return Sealed(raw)\n"
        "\n"
        "\n"
        "def seal(value: str) -> Sealed:\n"
        "    return Sealed(value.encode())\n"
    ),
    "app/backend/src/untangle/case_record/repository.py": (
        "from untangle.case_record.models import Sealed\n"
        "\n"
        "\n"
        "def guardar(nombre: Sealed) -> None:\n"
        "    print(nombre)\n"
    ),
    "app/backend/tests/unit/case_record/test_algo.py": (
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


def test_el_punto_unico_de_cifrado_puede_fabricar_el_tipo(tmp_path: Path) -> None:
    """`crypto.py` invoca el constructor dos veces y eso **no** es un hallazgo.

    Si lo fuera, el chequeo seria inutilizable: no habria forma de fabricar un
    sellado en ningun sitio, ni siquiera donde debe fabricarse.
    """
    _sembrar(tmp_path)

    assert not [h for h in chequeo.run_all(tmp_path) if "crypto.py" in h.where]


def test_usar_el_tipo_en_una_firma_no_es_producirlo(tmp_path: Path) -> None:
    """El repositorio **exige** un sellado; exigirlo es lo que se quiere.

    Si anotar el tipo contara como producirlo, la regla prohibiria justo la
    conducta que existe para imponer: que lo que llega al almacen venga ya
    sellado.
    """
    _sembrar(tmp_path)

    assert not [h for h in chequeo.run_all(tmp_path) if "repository.py" in h.where]


def test_declarar_el_tipo_no_es_fabricarlo(tmp_path: Path) -> None:
    """`models.py` escribe `NewType("Sealed", bytes)` y eso no cuenta.

    Declarar el tipo y fabricar un valor suyo son cosas distintas, y el chequeo
    tiene que distinguirlas o el archivo que define el tipo no podria definirlo.
    """
    _sembrar(tmp_path)

    assert not [h for h in chequeo.run_all(tmp_path) if "models.py" in h.where]


# --- Las tres formas de producir el tipo (PA-8, capa 2) -----------------------


def test_atrapa_la_llamada_al_constructor_fuera_de_su_archivo(tmp_path: Path) -> None:
    """La forma obvia: `Sealed(dato_en_claro)`.

    Es una llamada legal que el comprobador de tipos acepta, porque `NewType` se
    borra en tiempo de ejecucion. Lo que escribe en la columna cifrada es el
    nombre del testigo tal cual lo dijo.
    """
    _sembrar(
        tmp_path,
        {
            "app/backend/src/untangle/case_record/parties.py": (
                "from untangle.case_record.models import Sealed\n"
                "\n"
                "\n"
                "def registrar(nombre: str) -> Sealed:\n"
                "    return Sealed(nombre.encode())\n"
            )
        },
    )

    assert [h for h in chequeo.run_all(tmp_path) if "parties.py" in h.where and h.rule == "PA-8"]


def test_atrapa_el_cast_que_afirma_el_tipo_sin_construirlo(tmp_path: Path) -> None:
    """La puerta de al lado: `cast(Sealed, datos)`.

    Entrega exactamente lo mismo que la llamada, sin invocar nunca el
    constructor. Un control que solo cubre la forma obvia atrapa descuidos y no
    atajos.
    """
    _sembrar(
        tmp_path,
        {
            "app/backend/src/untangle/case_record/parties.py": (
                "from typing import cast\n"
                "\n"
                "from untangle.case_record.models import Sealed\n"
                "\n"
                "\n"
                "def registrar(nombre: bytes) -> Sealed:\n"
                "    return cast(Sealed, nombre)\n"
            )
        },
    )

    assert [h for h in chequeo.run_all(tmp_path) if "parties.py" in h.where and h.rule == "PA-8"]


def test_atrapa_la_anotacion_que_silencia_al_comprobador(tmp_path: Path) -> None:
    """La tercera: anotar el tipo y callar al comprobador con `type: ignore`."""
    _sembrar(
        tmp_path,
        {
            "app/backend/src/untangle/case_record/parties.py": (
                "from untangle.case_record.models import Sealed\n"
                "\n"
                "\n"
                "def registrar(nombre: bytes) -> None:\n"
                "    cifrado: Sealed = nombre  # type: ignore[assignment]\n"
                "    print(cifrado)\n"
            )
        },
    )

    assert [h for h in chequeo.run_all(tmp_path) if "parties.py" in h.where and h.rule == "PA-8"]


def test_atrapa_la_firma_silenciada(tmp_path: Path) -> None:
    """La misma tercera forma, movida a la firma en vez del cuerpo."""
    _sembrar(
        tmp_path,
        {
            "app/backend/src/untangle/case_record/parties.py": (
                "from untangle.case_record.models import Sealed\n"
                "\n"
                "\n"
                "def registrar(\n"
                "    nombre: Sealed,  # type: ignore[assignment]\n"
                ") -> None:\n"
                "    print(nombre)\n"
            )
        },
    )

    assert [h for h in chequeo.run_all(tmp_path) if "parties.py" in h.where and h.rule == "PA-8"]


def test_atrapa_las_tres_formas_a_la_vez(tmp_path: Path) -> None:
    """Las tres juntas dan tres hallazgos, no uno.

    Importa: quien arregla la primera y vuelve a correr tiene que seguir viendo
    las otras dos, en vez de descubrirlas de una en una.
    """
    _sembrar(
        tmp_path,
        {
            "app/backend/src/untangle/case_record/parties.py": (
                "from typing import cast\n"
                "\n"
                "from untangle.case_record.models import Sealed\n"
                "\n"
                "\n"
                "def registrar(nombre: bytes) -> None:\n"
                "    uno = Sealed(nombre)\n"
                "    dos = cast(Sealed, nombre)\n"
                "    tres: Sealed = nombre  # type: ignore[assignment]\n"
                "    print(uno, dos, tres)\n"
            )
        },
    )

    hallazgos = [h for h in chequeo.run_all(tmp_path) if "parties.py" in h.where]

    assert len(hallazgos) == 3


# --- Que el chequeo nombre lo que encontro ------------------------------------


def test_el_hallazgo_nombra_el_archivo_y_la_linea(tmp_path: Path) -> None:
    """Un chequeo que solo dice "fallo" obliga a buscar a mano lo que ya sabia."""
    _sembrar(
        tmp_path,
        {
            "app/backend/src/untangle/case_record/parties.py": (
                "from untangle.case_record.models import Sealed\n"
                "\n"
                "\n"
                "def registrar(nombre: bytes) -> Sealed:\n"
                "    return Sealed(nombre)\n"
            )
        },
    )

    (hallazgo,) = [h for h in chequeo.run_all(tmp_path) if "parties.py" in h.where]

    assert hallazgo.where.endswith(":5")
    assert "Sealed" in hallazgo.detail


def test_una_prueba_tampoco_puede_fabricar_el_tipo(tmp_path: Path) -> None:
    """Las pruebas entran en el alcance a proposito.

    Una prueba que fabricara un sellado falso estaria comprobando la garantia
    contra si misma: pasaria siempre, y con el cifrado roto tambien.
    """
    _sembrar(
        tmp_path,
        {
            "app/backend/tests/unit/case_record/test_algo.py": (
                "from untangle.case_record.models import Sealed\n"
                "\n"
                "\n"
                "def test_algo() -> None:\n"
                '    assert Sealed(b"sin cifrar")\n'
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


# --- Las tres vias que la revision encontro abiertas --------------------------


@pytest.mark.parametrize(
    ("nombre", "fuente"),
    [
        (
            "solo por palabra clave",
            "from untangle.case_record.models import Sealed\n"
            "\n"
            "\n"
            "def f(*, v: Sealed) -> None:  # type: ignore[assignment]\n"
            "    print(v)\n",
        ),
        (
            "solo posicional",
            "from untangle.case_record.models import Sealed\n"
            "\n"
            "\n"
            "def g(v: Sealed, /) -> None:  # type: ignore[assignment]\n"
            "    print(v)\n",
        ),
        (
            "resto variable",
            "from untangle.case_record.models import Sealed\n"
            "\n"
            "\n"
            "def i(*vs: Sealed) -> None:  # type: ignore[assignment]\n"
            "    print(vs)\n",
        ),
        (
            "alias de importacion",
            "from untangle.case_record.models import Sealed as S\n"
            "\n"
            "\n"
            "def h() -> None:\n"
            '    print(S(b"en claro"))\n',
        ),
    ],
)
def test_atrapa_las_vias_que_no_son_un_argumento_normal(
    nombre: str, fuente: str, tmp_path: Path
) -> None:
    """Un control que solo cubre la forma obvia atrapa descuidos y no atajos.

    Las cuatro las encontro la revision asesora de esta etapa. La del alias es
    la grave: `from ... import Sealed as S` y despues `S(b"en claro")` fabrica un
    sellado de verdad que el repositorio escribiria en la columna cifrada.
    """
    _sembrar(tmp_path, {"app/backend/src/untangle/case_record/parties.py": fuente})

    assert [h for h in chequeo.run_all(tmp_path) if "parties.py" in h.where], nombre
