"""Las tres variables de Langfuse: opcionales, juntas o ninguna, y con la direccion cerrada.

Sin red y sin entorno: cada prueba fija lo que lee, y el `conftest` de la suite
quita las tres variables del entorno de quien la corre, porque si estuvieran puestas
estas pruebas cambiarian de rama sin que nadie lo pidiera.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from untangle.settings import Settings, variable_names

CLAVE_PUBLICA = "pk-lf-x"
CLAVE_SECRETA = "sk-lf-x"
NOMBRES = (
    "UNTANGLE_LANGFUSE_PUBLIC_KEY",
    "UNTANGLE_LANGFUSE_SECRET_KEY",
    "UNTANGLE_LANGFUSE_HOST",
)


def test_las_tres_se_leen_con_el_prefijo_del_aplicativo() -> None:
    assert set(NOMBRES) <= set(variable_names())


def test_sin_ninguna_no_hay_langfuse() -> None:
    ajustes = Settings(env="ci")

    assert ajustes.langfuse_public_key is None
    assert ajustes.langfuse_secret_key is None
    assert ajustes.langfuse_host is None
    assert not ajustes.langfuse_configured


def test_con_las_tres_hay_langfuse() -> None:
    ajustes = Settings(
        env="ci",
        langfuse_public_key=CLAVE_PUBLICA,
        langfuse_secret_key=CLAVE_SECRETA,
        langfuse_host="https://us.cloud.langfuse.com",
    )

    assert ajustes.langfuse_configured


@pytest.mark.parametrize("falta", ["langfuse_public_key", "langfuse_secret_key", "langfuse_host"])
def test_con_dos_de_tres_no_hay_langfuse(falta: str) -> None:
    """Dos de tres no es medio configurado: es no configurado, y nada sale."""
    completas = {
        "langfuse_public_key": CLAVE_PUBLICA,
        "langfuse_secret_key": CLAVE_SECRETA,
        "langfuse_host": "https://us.cloud.langfuse.com",
    }
    del completas[falta]

    assert not Settings.model_validate({"env": "ci", **completas}).langfuse_configured


def test_una_plantilla_copiada_tal_cual_deja_las_variables_vacias_y_eso_es_ausente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`.env.example` trae los tres nombres sin valor: vacia no es una clave de cero caracteres."""
    for nombre in NOMBRES:
        monkeypatch.setenv(nombre, "")

    ajustes = Settings(env="ci")

    assert (ajustes.langfuse_public_key, ajustes.langfuse_secret_key, ajustes.langfuse_host) == (
        None,
        None,
        None,
    )
    assert not ajustes.langfuse_configured


def test_la_barra_final_de_la_direccion_se_quita() -> None:
    ajustes = Settings(env="ci", langfuse_host="https://us.cloud.langfuse.com/")

    assert ajustes.langfuse_host == "https://us.cloud.langfuse.com"


@pytest.mark.parametrize(
    "direccion",
    [
        "http://us.cloud.langfuse.com",  # las claves viajarian a la vista de la red
        "us.cloud.langfuse.com",  # sin esquema
        "https://",  # sin servidor
        "https://us.cloud.langfuse.com/api/public",  # con ruta: la raiz de la API es la del servidor
        "https://us.cloud.langfuse.com?x=1",
    ],
)
def test_una_direccion_que_no_es_https_con_servidor_sin_ruta_no_arranca(direccion: str) -> None:
    with pytest.raises(ValidationError) as error:
        Settings(env="ci", langfuse_host=direccion)

    # El mensaje nombra la variable y no repite lo que llego (`hide_input_in_errors`).
    assert "UNTANGLE_LANGFUSE_HOST" in str(error.value)
    assert "input_value" not in str(error.value)
