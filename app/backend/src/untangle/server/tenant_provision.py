"""`mise run tenant:provision`: dar de alta una aseguradora con una carpeta (US5.1).

    mise run tenant:provision -- <id> [--dry-run]

Tres pasos y en este orden, que es el unico que cumple BR1.1:

1. **Valida la carpeta entera y no crea nada todavia.** Si falta algo, el comando
   falla nombrando el archivo y el campo de **cada** falta, no de la primera: una
   aseguradora a medias no la borra nada y no la completa nada --se queda
   existiendo mal-- y descubrir un campo por corrida convierte dar de alta una
   aseguradora en cinco intentos.
2. **Invoca la ingesta que ya existe** (`corpus:ingest`), no escribe la suya
   (BR1.3). Y la invoca como funcion y no como proceso: el comentario de esa
   tarea ya lo dejo escrito para esta unidad, y una segunda ingesta seria un
   segundo sitio donde el corpus se indexa distinto --la diferencia apareceria
   como una cita que no se encuentra--.
3. **Siembra los casos de esa aseguradora** por la siembra que ya existe, que
   crea cada caso por la API de U4 con origen `generator`, el que el reinicio
   nocturno conserva.

**Es idempotente de verdad y no solo de nombre** (BR1.2). La ingesta compara el
resumen del contenido y pide al proveedor solo lo que falta, asi que repetirla no
vuelve a gastar; la siembra deja como esta el caso que ya existe en su estado y
se detiene nombrando el que existe en otro. Correrlo dos veces deja el mismo
estado y no cuesta una segunda vez.

**Exige al menos un caso sembrado, y lo comprueba antes de ingerir.** Una
aseguradora dada de alta con la bandeja vacia parece una aseguradora rota: quien
abre la demostracion no distingue "no ha pasado nada" de "el aprovisionamiento no
termino". Se comprueba antes del paso 2 y no despues, porque ingerir **ya es
crear**: dejar el corpus indexado y la bandeja vacia es exactamente la mitad de
aseguradora que BR1.1 prohibe.

**No publica ninguna credencial.** Dice que personas declara la carpeta y con que
comando se emite la de cada una; ninguna sale por aqui (D23).

**Lo que este comando no hace, y es la mitad de AC5.1.1.** No toca ningun archivo
de codigo, porque no hay ninguno que tocar: lo que distingue a una aseguradora
vive en su carpeta. Que siga siendo cierto no se confia a la memoria --lo
comprueba `tenancy:literals` en cada entrega-- y lo comprueba tambien la bateria
de humo de esta unidad, que da de alta una cuarta aseguradora que no se publica y
la hace pasar por el chat, la bandeja y el aislamiento.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from untangle import paths
from untangle.case_record.crypto import Cipher, EncryptionKeyMissingError
from untangle.demo_operations.api import TenantFolderReport, validate_tenant_folder
from untangle.server import corpus_ingest, synthetic_seed
from untangle.settings import Settings
from untangle.synthetic_data.cases import SeededCaseLoadError, load_seeded_cases
from untangle.tenancy import config as tenancy_config
from untangle.tenancy import session

__all__ = [
    "FolderIncompleteError",
    "IngestFailedError",
    "NoSeededCasesError",
    "ProvisionError",
    "ProvisionOutcome",
    "main",
    "provision",
]

#: Como se invoca la ingesta. Es un argumento y no una llamada directa para que
#: una prueba pueda comprobar **que se invoca** --que es lo que BR1.3 pide-- sin
#: llamar al proveedor de embeddings, que cuesta dinero. Su valor por omision es
#: la tarea que ya existe, asi que no hay una segunda ingesta ni por descuido.
#:
#: **Asincrono, y no por simetria**: `provision` corre dentro de un bucle de
#: eventos, y la ingesta de verdad tambien es asincrona. Cuando este tipo decia
#: `Callable[[str], int]`, el unico valor que lo cumplia era la cascara de linea
#: de comandos, que arranca su propio bucle --y eso levanta `RuntimeError` desde
#: dentro de otro. El tipo describia una frontera que no se podia cruzar.
type IngestStep = Callable[[str], Awaitable[int]]


class ProvisionError(RuntimeError):
    """El aprovisionamiento no se pudo completar. El mensaje dice que falto."""


class FolderIncompleteError(ProvisionError):
    """La carpeta no esta completa. Lleva **todas** las faltas, con archivo y campo."""

    def __init__(self, report: TenantFolderReport) -> None:
        detalle = "\n".join(
            f"  {falta.file}: {falta.field}: {falta.detail}" for falta in report.missing
        )
        super().__init__(
            f"la carpeta de '{report.tenant_id}' tiene {len(report.missing)} falta(s) y no se "
            f"creo nada:\n{detalle}"
        )
        self.report = report


class IngestFailedError(ProvisionError):
    """La ingesta del corpus devolvio un codigo distinto de cero."""


class NoSeededCasesError(ProvisionError):
    """El corpus de esa aseguradora no trae ningun caso sembrado."""


@dataclass(frozen=True)
class ProvisionOutcome:
    """Lo que dejo el aprovisionamiento."""

    tenant_id: str
    seeded: tuple[synthetic_seed.SeedOutcome, ...]
    #: Las personas de bandeja que declara la carpeta. **Solo sus
    #: identificadores**: la credencial se emite aparte y no se publica (D23).
    staff: tuple[str, ...]

    @property
    def created(self) -> int:
        return sum(1 for caso in self.seeded if caso.created)


async def _ingesta_de_la_tarea(tenant_id: str) -> int:
    """La tarea `corpus:ingest`, con esta aseguradora y el registro del proyecto.

    Llama al nucleo asincrono y **nunca** a `corpus_ingest.main`: `main` arranca
    un bucle de eventos, y aqui ya hay uno corriendo.
    """
    return await corpus_ingest.run(["--tenant", tenant_id])


@dataclass(frozen=True)
class ProvisionRoots:
    """Las tres raices que el aprovisionamiento lee.

    Son un argumento y no tres constantes porque la bateria de humo da de alta
    una **cuarta aseguradora que no se publica**: su carpeta vive en las
    fixtures, y si estas rutas no entraran por aqui habria que ponerla en
    `app/config/tenants/`, donde el inicio del sitio la anunciaria.
    """

    #: Donde viven las carpetas de aseguradora (`.../tenants`).
    tenants: Path
    #: Donde vive el corpus por aseguradora (`.../data/tenants`).
    corpus: Path
    #: La raiz de los datos generados, de donde salen los casos sembrados.
    data: Path

    @classmethod
    def versionadas(cls) -> ProvisionRoots:
        """Las del repositorio, que son las que usa el comando."""
        return cls(
            tenants=paths.tenants_dir(),
            corpus=paths.corpus_tenants_dir(),
            data=paths.data_dir(),
        )


async def provision(
    tenant_id: str,
    *,
    cipher: Cipher,
    now: datetime,
    ingest: IngestStep = _ingesta_de_la_tarea,
    roots: ProvisionRoots | None = None,
) -> ProvisionOutcome:
    """Valida, ingiere y siembra, en ese orden. Falla antes de crear nada (BR1.1)."""
    raices = roots if roots is not None else ProvisionRoots.versionadas()
    carpeta = raices.tenants / tenant_id
    informe = validate_tenant_folder(carpeta, corpus_root=raices.corpus)
    if not informe.complete:
        raise FolderIncompleteError(informe)

    casos = tuple(
        registro for registro in load_seeded_cases(raices.data) if registro.tenant_id == tenant_id
    )
    if not casos:
        msg = (
            f"el corpus de '{tenant_id}' no trae ningun caso sembrado, asi que su bandeja "
            "amaneceria vacia y no se distinguiria de un aprovisionamiento a medias"
        )
        raise NoSeededCasesError(msg)

    codigo = await ingest(tenant_id)
    if codigo != 0:
        msg = (
            f"la ingesta del corpus de '{tenant_id}' devolvio {codigo}: no se sembro ningun "
            "caso. La ingesta se retoma sola --pide al proveedor solo lo que falta-- asi que "
            "volver a correr este comando continua donde quedo"
        )
        raise IngestFailedError(msg)

    sembrados = await synthetic_seed.seed_all(casos, cipher=cipher, now=now)
    return ProvisionOutcome(
        tenant_id=tenant_id,
        seeded=sembrados,
        staff=tuple(persona.principal_id for persona in tenancy_config.load_tenant(carpeta).staff),
    )


def _imprimir(resultado: ProvisionOutcome) -> None:
    for caso in resultado.seeded:
        como = "sembrado" if caso.created else "ya estaba"
        print(f"tenant:provision: {caso.case_key} -> {caso.state.value} ({como})")
    print(
        f"tenant:provision: '{resultado.tenant_id}' lista con {len(resultado.seeded)} caso(s), "
        f"{resultado.created} sembrado(s) ahora"
    )
    for principal in resultado.staff:
        print(
            f"tenant:provision: la bandeja de '{principal}' necesita su credencial: "
            f"mise run tenancy:credential -- --tenant {resultado.tenant_id} "
            f"--principal {principal}"
        )


async def _correr(tenant_id: str, cipher: Cipher, now: datetime) -> ProvisionOutcome:
    try:
        return await provision(tenant_id, cipher=cipher, now=now)
    finally:
        await session.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    analizador.add_argument(
        "tenant_id", help="el identificador de la aseguradora, que es su carpeta"
    )
    argumentos = analizador.parse_args(argv)

    opciones = Settings()
    if not opciones.database_url:
        print(
            "tenant:provision: falta UNTANGLE_DATABASE_URL: sin base no hay donde aprovisionar. "
            "Levante la local con `mise run services:up`",
            file=sys.stderr,
        )
        return 1
    try:
        cipher = Cipher.from_settings(opciones)
    except EncryptionKeyMissingError as error:
        print(f"tenant:provision: {error}", file=sys.stderr)
        return 1

    session.configure(opciones.database_url)
    try:
        resultado = asyncio.run(_correr(argumentos.tenant_id, cipher, datetime.now(UTC)))
    except (ProvisionError, SeededCaseLoadError, synthetic_seed.SeedError) as error:
        print(f"tenant:provision: {error}", file=sys.stderr)
        return 1
    _imprimir(resultado)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
