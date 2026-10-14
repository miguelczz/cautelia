"""El cifrado de los campos personales del caso (PA-8, SEC-U4.8 a SEC-U4.10).

Lo que estas pruebas protegen es el unico sitio del aplicativo donde un dato
personal se guarda en claro a proposito. Su fallo es silencioso: un campo que se
escribe sin cifrar no rompe ninguna pantalla, no levanta ninguna excepcion y no
hace fallar ninguna prueba de funcionamiento. Sigue habiendo un caso; solo que
el nombre del testigo quedo legible para quien alcance el almacen.

Dos posturas distintas se prueban aparte, porque la asimetria es deliberada:
**cerrado al arrancar** --sin clave el proceso no arranca-- y **visible al
leer** --una fila que no se descifra no impide abrir el caso--.
"""

from __future__ import annotations

import pytest

from untangle.case_record import crypto

DATO = "Nayibe Quintero Ospina"


@pytest.fixture
def cifrador(monkeypatch: pytest.MonkeyPatch) -> crypto.Cipher:
    """Un cifrador con clave propia, generada en el montaje.

    Nunca una clave real y nunca una fija escrita aqui: una clave fija en el
    codigo de prueba es una clave en el repositorio.
    """
    monkeypatch.setenv(crypto.KEY_ENV_VAR, crypto.generate_key())
    return crypto.Cipher.from_settings()


# --- Lo que se guarda no se puede leer ----------------------------------------


def test_el_valor_sellado_no_contiene_el_original(cifrador: crypto.Cipher) -> None:
    """Ni entero, ni por fragmentos, ni con otra codificacion.

    Se comprueban las tres formas porque tapar el valor y dejar un pedazo es el
    error que no se nota: el nombre completo no aparece, pero el apellido si.
    """
    sellado = bytes(cifrador.seal(DATO))

    assert DATO.encode("utf-8") not in sellado
    for fragmento in DATO.split():
        assert fragmento.encode("utf-8") not in sellado
    assert DATO.encode("utf-16") not in sellado


def test_sellar_dos_veces_el_mismo_valor_da_dos_resultados_distintos(
    cifrador: crypto.Cipher,
) -> None:
    """Si diera el mismo, dos filas iguales se reconocerian sin abrirlas, y quien
    lea el almacen sabria que dos partes distintas se llaman igual."""
    assert cifrador.seal(DATO) != cifrador.seal(DATO)


def test_abrir_devuelve_el_original(cifrador: crypto.Cipher) -> None:
    """La operacion tiene que ser reversible: el ajustador lee el dato."""
    sellado = cifrador.seal(DATO)

    assert cifrador.unseal(sellado, stored_key_id=cifrador.id) == DATO


def test_un_valor_alterado_no_se_abre(cifrador: crypto.Cipher) -> None:
    """El cifrado es autenticado: un byte cambiado en la base no se descifra a
    otra cosa, se rechaza. Descifrar basura a un texto plausible seria peor que
    no descifrar."""
    sellado = bytearray(cifrador.seal(DATO))
    sellado[-1] ^= 0x01

    resultado = cifrador.unseal(crypto.from_storage(bytes(sellado)), stored_key_id=cifrador.id)

    assert isinstance(resultado, crypto.Unavailable)


# --- La clave -----------------------------------------------------------------


def test_sin_clave_en_el_entorno_no_se_puede_construir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cerrado al arrancar (NFRD-U4-4). Un modo degradado que guardara en claro
    "mientras tanto" es exactamente como un dato personal acaba sin cifrar sin
    que nadie lo decida."""
    monkeypatch.delenv(crypto.KEY_ENV_VAR, raising=False)

    with pytest.raises(crypto.EncryptionKeyMissingError) as error:
        crypto.Cipher.from_settings()

    assert crypto.KEY_ENV_VAR in str(error.value)


def test_una_clave_mal_formada_no_se_puede_construir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Y el mensaje no la imprime: un error que la imprimiera la dejaria en el
    log del arranque, que es justo de donde se quiere sacar."""
    basura = "esto-no-es-una-clave"
    monkeypatch.setenv(crypto.KEY_ENV_VAR, basura)

    with pytest.raises(crypto.EncryptionKeyMissingError) as error:
        crypto.Cipher.from_settings()

    assert basura not in str(error.value)


def test_el_identificador_de_clave_no_es_un_pedazo_de_la_clave() -> None:
    """Publicar un prefijo de la clave seria publicar parte del secreto.

    El identificador viaja con cada fila, asi que esta a la vista de cualquiera
    que lea el almacen.
    """
    clave = crypto.generate_key()
    identificador = crypto.key_id(clave.encode("ascii"))

    assert identificador not in clave
    assert len(identificador) == crypto.KEY_ID_LENGTH


def test_dos_claves_distintas_tienen_identificadores_distintos() -> None:
    """Es lo que hace util la columna: si colisionaran, el dia de la rotacion no
    se sabria con cual abrir cada fila."""
    a = crypto.key_id(crypto.generate_key().encode("ascii"))
    b = crypto.key_id(crypto.generate_key().encode("ascii"))

    assert a != b


# --- Visible al leer ----------------------------------------------------------


def test_una_fila_cifrada_con_otra_clave_no_tumba_la_lectura(cifrador: crypto.Cipher) -> None:
    """Visible al leer (NFRD-U4-2, decision de Miguel).

    Es la mitad que hace util la rotacion: el dia que la clave cambie, las filas
    viejas devuelven el marcador en vez de romper el caso entero.
    """
    sellado = cifrador.seal(DATO)

    resultado = cifrador.unseal(sellado, stored_key_id="00000000")

    assert isinstance(resultado, crypto.Unavailable)
    assert resultado.key_id == "00000000"


def test_el_marcador_de_no_disponible_no_lleva_el_dato(cifrador: crypto.Cipher) -> None:
    """Ni en su razon ni en su representacion. Un camino de fallo que imprimiera
    lo que iba a descifrar seria el punto de fuga que este modulo evita."""
    sellado = bytearray(cifrador.seal(DATO))
    sellado[-1] ^= 0x01

    resultado = cifrador.unseal(crypto.from_storage(bytes(sellado)), stored_key_id=cifrador.id)

    assert isinstance(resultado, crypto.Unavailable)
    assert DATO not in repr(resultado)
    for fragmento in DATO.split():
        assert fragmento not in repr(resultado)


# --- El cifrador del proceso --------------------------------------------------


def test_pedir_el_cifrador_sin_instalarlo_falla_diciendo_como(
    cifrador: crypto.Cipher,
) -> None:
    """Falla en el acto y nombra a quien tiene que instalarlo, en vez de cifrar
    con una clave adivinada."""
    crypto.reset()

    with pytest.raises(crypto.EncryptionKeyMissingError) as error:
        crypto.active()

    assert "raiz de composicion" in str(error.value)


def test_el_cifrador_instalado_es_el_que_se_devuelve(cifrador: crypto.Cipher) -> None:
    """Se resuelve una vez en el arranque y no en cada llamada: leer el entorno
    en cada llamada haria que quitar la variable con el proceso vivo cambiara la
    conducta a mitad de una peticion."""
    crypto.install(cifrador)
    try:
        assert crypto.active() is cifrador
    finally:
        crypto.reset()
