"""El punto unico de cifrado de los campos personales del caso (PA-8).

Esta unidad es el unico sitio del aplicativo donde un dato personal se guarda
**en claro**, y no es un descuido: el PRD lo decidio asi --"el caso guarda los
datos personales que la operacion necesita, cifrados en reposo y bajo RLS; lo
que sale a trazas, logs y evals va redactado"-- y U3 dejo escrito como regla que
los campos estructurados del caso no se redactan. La redaccion protege las
salidas; el almacen lo protege este archivo.

**Una sola puerta.** Solo este modulo fabrica y abre el tipo sellado. El
repositorio recibe valores ya sellados y los escribe; no conoce la clave ni el
algoritmo. Con dos puertas, la afirmacion "todo lo personal se cifra antes de
persistir" habria que revisarla cada vez que alguien anade una.

**Contra que protege, y contra que no.** Protege contra quien alcance el almacen
sin alcanzar el proceso: un volcado, una copia de seguridad, la consola del
proveedor de base. **No** protege contra quien tenga el proceso y su variable de
entorno, porque entonces tiene la clave. Decirlo importa: un control que se cree
mas fuerte de lo que es acaba sustituyendo a los que si harian falta.

**Cerrado al arrancar, visible al leer** (NFRD-U4-2 y NFRD-U4-4). Sin clave, el
proceso no arranca: un modo degradado que guardara en claro "mientras tanto" es
exactamente como un dato personal acaba sin cifrar sin que nadie lo decida. Pero
una fila que no se puede descifrar **no impide abrir el caso**: el campo aparece
como no disponible y deja su evento. Al arrancar, el fallo afecta a lo que
todavia no ha pasado y cerrarse no cuesta nada; al leer, el caso ya existe y
alguien tiene que decidirlo.
"""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken

from untangle import observability
from untangle.case_record.models import KeyId, Sealed
from untangle.settings import CASE_FIELD_ENCRYPTION_KEY_VAR, Settings

#: La variable de entorno de la clave. El nombre vive en `settings.py`, con las
#: otras, para que el chequeo de entorno lo vea en un solo sitio y la plantilla
#: y el codigo no puedan decir cosas distintas.
KEY_ENV_VAR = CASE_FIELD_ENCRYPTION_KEY_VAR

#: Cuantos caracteres del resumen de la clave forman su identificador. Ocho
#: bastan para distinguir las claves que un proyecto como este va a tener, y no
#: revelan nada util sobre la clave: es un resumen, no un prefijo.
KEY_ID_LENGTH = 8


class EncryptionKeyMissingError(RuntimeError):
    """No hay clave de cifrado, o no tiene la forma esperada.

    Es condicion de arranque. El mensaje dice como generar una y **nunca
    incluye** el valor de lo que encontro: un error que imprimiera una clave mal
    formada la pondria en un log.
    """


@dataclass(frozen=True)
class Unavailable:
    """Lo que devuelve abrir una fila que no se puede descifrar.

    Es un **valor**, no una excepcion, y esa diferencia es el diseno: el caso se
    abre igual y ese campo aparece marcado. Un caso que no abre solo dice que
    algo paso; uno con un hueco senalado se puede seguir trabajando y el hueco
    se ve.

    Lo que ve una persona no es esto: es la etiqueta del catalogo de textos en
    su idioma. Esto es lo que el repositorio devuelve para que la pantalla sepa
    que hay que resolverla.
    """

    key_id: KeyId
    reason: str


def _leer_clave(settings: Settings | None = None) -> bytes:
    opciones = settings if settings is not None else Settings()
    crudo = (opciones.case_field_encryption_key or "").strip()
    if not crudo:
        msg = (
            f"falta la clave de cifrado de los campos del caso en '{KEY_ENV_VAR}'. "
            "Sin ella no se guarda ni se lee ningun campo del caso, porque guardar "
            "en claro 'mientras tanto' es como un dato personal acaba sin cifrar sin "
            "que nadie lo decida. Genere una con: mise run claves:cifrado"
        )
        raise EncryptionKeyMissingError(msg)
    return crudo.encode("ascii")


def _validar(clave: bytes) -> None:
    try:
        Fernet(clave)
    except Exception as error:
        # El mensaje no lleva la clave ni un fragmento suyo: un error que la
        # imprimiera la dejaria en el log del arranque.
        msg = (
            f"la clave de '{KEY_ENV_VAR}' no tiene la forma esperada "
            f"({type(error).__name__}): son 32 bytes en base64 seguro para URL"
        )
        raise EncryptionKeyMissingError(msg) from error


def key_id(clave: bytes) -> KeyId:
    """El identificador de una clave: los primeros caracteres de su resumen.

    Cada fila guarda **cual** clave la cifro (NFRD-U4-1, decision de Miguel).
    Hoy hay una sola y no cambia nada; el dia que haya que rotar, las filas
    viejas se siguen leyendo con la clave vieja y las nuevas nacen con la nueva,
    sin una migracion que reescriba el almacen entero ni una ventana en la que
    los casos no se puedan abrir.

    Es un resumen y no un prefijo de la clave: publicar un prefijo seria
    publicar parte del secreto.
    """
    return hashlib.sha256(clave).hexdigest()[:KEY_ID_LENGTH]


def from_storage(raw: bytes) -> Sealed:
    """Declara que unos bytes que vienen de la columna son un valor sellado.

    Es la **segunda** forma de producir el tipo, y vive en este archivo a
    proposito: el analisis estatico exige que las dos esten en el mismo sitio,
    para que auditar "quien fabrica un sellado" siga siendo leer un archivo.

    Hace falta porque leer es la otra mitad del viaje: el repositorio recibe
    `bytes` de la base --la base no sabe de tipos de Python-- y alguien tiene
    que decir que esos bytes son un sellado. Sin esta funcion ese `alguien`
    seria un `cast` en el repositorio, que es justo lo que el chequeo prohibe.

    No valida nada, y no puede: unos bytes cifrados y unos bytes en claro son
    indistinguibles sin la clave. Quien intente abrir un valor que no lo era
    recibe el marcador de no disponible, que es la conducta correcta.
    """
    return Sealed(raw)


@dataclass(frozen=True)
class Cipher:
    """La clave activa y su identificador, resueltos una vez.

    Se construye en el arranque y se pasa a quien lo necesite, en vez de leerse
    del entorno en cada llamada: leerlo en cada llamada haria que quitar la
    variable con el proceso vivo cambiara la conducta a mitad de una peticion.
    """

    _fernet: Fernet
    id: KeyId

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> Cipher:
        """Resuelve la clave de la configuracion. Falla cerrado si no esta o no vale.

        La raiz de composicion le pasa la suya, que leyo del entorno una vez.
        Sin argumento la lee ahora, que es lo que hace una prueba.
        """
        clave = _leer_clave(settings)
        _validar(clave)
        return cls(_fernet=Fernet(clave), id=key_id(clave))

    def seal(self, value: str) -> Sealed:
        """Cifra un valor personal. Es la **unica** forma de fabricar el tipo."""
        return Sealed(self._fernet.encrypt(value.encode("utf-8")))

    def unseal(self, value: Sealed, *, stored_key_id: KeyId) -> str | Unavailable:
        """Abre un valor, o devuelve el marcador de no disponible.

        Devuelve el marcador --y no levanta-- cuando la fila la cifro otra clave
        o el dato esta corrupto. El caso se abre igual (NFRD-U4-2).
        """
        if stored_key_id != self.id:
            observability.emit(
                "case_record.unseal_other_key",
                stored_key_id=stored_key_id,
                active_key_id=self.id,
            )
            return Unavailable(
                key_id=stored_key_id,
                reason="la fila la cifro otra clave, que este proceso no tiene",
            )
        try:
            return self._fernet.decrypt(bytes(value)).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as error:
            # El evento lleva la causa y la clave, **nunca el valor**: un rastro
            # de fallo que imprimiera lo que iba a descifrar seria el punto de
            # fuga que este archivo existe para evitar.
            observability.emit(
                "case_record.unseal_failed",
                key_id=stored_key_id,
                error=type(error).__name__,
            )
            return Unavailable(key_id=stored_key_id, reason=type(error).__name__)


_cifrador: Cipher | None = None


def install(cipher: Cipher) -> None:
    """Fija el cifrador del proceso. Lo llama la raiz de composicion."""
    global _cifrador
    _cifrador = cipher


def reset() -> None:
    """Lo olvida. Existe para que una prueba no herede el de otra."""
    global _cifrador
    _cifrador = None


def active() -> Cipher:
    """El cifrador del proceso, o falla diciendo que nadie lo instalo."""
    if _cifrador is None:
        msg = (
            "no hay cifrador instalado: la raiz de composicion tiene que llamar "
            "a `install(Cipher.from_settings(opciones))` antes de la primera lectura "
            "o escritura de un campo del caso"
        )
        raise EncryptionKeyMissingError(msg)
    return _cifrador


def generate_key() -> str:
    """Una clave nueva, para el arranque local y para las pruebas.

    Vive aqui y no en un guion suelto para que el mensaje del error de arranque
    pueda nombrar una forma de generarla que existe de verdad.
    """
    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
