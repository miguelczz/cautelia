"""`mise run synthetic:fingerprints`: las huellas de los specimens de `tmp/specimens/` (U7, F4).

    mise run synthetic:fingerprints -- \\
        --specimen tmp/specimens/<archivo> "<formulario>" "<edicion>" "<publicador>" <AAAA-MM-DD> \\
        [--specimen ...]

Sin `--specimen`, vuelve a sacar las huellas de los specimens que ya declara el
archivo de huellas, buscandolos en `tmp/specimens/` por el hash de cada archivo:
es la forma de regenerarlas cuando cambia la normalizacion sin volver a escribir
de memoria el publicador y la fecha.

**Por que este comando vive aqui y no en `untangle.synthetic_data`.** Es el unico
que sabe llegar a `tmp/specimens/`, y ningun modulo de la composicion puede
conocer `tmp/` (BR2.1, BR2.3; lo comprueba `test_fronteras.py`). La logica --leer,
normalizar, cortar y guardar hashes-- si vive en `synthetic_data.fingerprints` y
recibe las rutas; aqui solo se resuelven.

Lo que imprime son recuentos y nombres de archivo. **Nunca texto de un specimen**:
un specimen en un log es un specimen en el repositorio el dia que alguien pega
ese log (SEC-U7.2).
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from untangle import paths
from untangle.synthetic_data import canonical, fingerprints
from untangle.text_fingerprints import SettingsError, load_settings

__all__ = ["main", "run"]


class _UsoError(ValueError):
    """Un argumento que no sirve. El mensaje dice cual y por que."""


def _dentro_de_specimens(ruta: Path, raiz: Path, carpeta: Path) -> Path:
    absoluta = ruta if ruta.is_absolute() else raiz / ruta
    absoluta = absoluta.resolve()
    if not absoluta.is_relative_to(carpeta.resolve()):
        msg = (
            f"'{ruta}' no esta en '{carpeta}': los specimens viven ahi porque git ignora esa "
            "carpeta, y un specimen fuera de ella puede acabar en un commit (SEC-U7.2)"
        )
        raise _UsoError(msg)
    return absoluta


def _declarados(
    argumentos: list[list[str]], raiz: Path, carpeta: Path
) -> list[fingerprints.SpecimenFile]:
    specimens = []
    for ruta, formulario, edicion, publicador, fecha in argumentos:
        try:
            recuperado = date.fromisoformat(fecha)
        except ValueError as error:
            msg = f"'{fecha}' no es una fecha AAAA-MM-DD"
            raise _UsoError(msg) from error
        specimens.append(
            fingerprints.SpecimenFile(
                path=_dentro_de_specimens(Path(ruta), raiz, carpeta),
                form=formulario,
                edition=edicion,
                publisher=publicador,
                retrieved_at=recuperado,
            )
        )
    return specimens


def _los_del_archivo(destino: Path, carpeta: Path) -> list[fingerprints.SpecimenFile]:
    """Los specimens que ya declara el archivo, encontrados en disco por su hash."""
    if not destino.is_file():
        msg = (
            f"no hay archivo de huellas en '{destino}' del que tomar los specimens: la primera "
            "vez hay que declararlos con --specimen"
        )
        raise _UsoError(msg)
    anterior = fingerprints.load_fingerprint_set(destino)
    en_disco = {
        canonical.sha256_hex(archivo.read_bytes()): archivo
        for archivo in sorted(carpeta.glob("*"))
        if archivo.suffix.lower() in fingerprints.FORMATOS and archivo.is_file()
    }
    faltan = [
        f"{f.form} {f.edition} ({f.publisher})"
        for f in anterior.sources
        if f.file_sha256 not in en_disco
    ]
    if faltan:
        msg = (
            f"no estan en '{carpeta}' los specimens de: {', '.join(faltan)}. Sin todos, las "
            "huellas nuevas cubririan menos que las viejas"
        )
        raise _UsoError(msg)
    return [
        fingerprints.SpecimenFile(
            path=en_disco[fuente.file_sha256],
            form=fuente.form,
            edition=fuente.edition,
            publisher=fuente.publisher,
            retrieved_at=fuente.retrieved_at,
        )
        for fuente in anterior.sources
    ]


def run(raiz: Path, carpeta: Path, argumentos: list[list[str]] | None) -> int:
    """Saca las huellas y escribe el archivo. Devuelve el codigo de salida."""
    try:
        ajustes = load_settings(raiz)
        destino = raiz / ajustes.shingles_file
        specimens = (
            _declarados(argumentos, raiz, carpeta)
            if argumentos
            else _los_del_archivo(destino, carpeta)
        )
        conjunto, por_specimen = fingerprints.build_fingerprint_set(specimens, ajustes)
    except (_UsoError, SettingsError, fingerprints.FingerprintError) as error:
        print(f"synthetic:fingerprints: {error}", file=sys.stderr)
        return 1

    fingerprints.write_fingerprint_set(conjunto, destino)
    for specimen in specimens:
        print(
            f"synthetic:fingerprints: {specimen.path.name} ({specimen.form} {specimen.edition}, "
            f"{specimen.publisher}): {por_specimen[specimen.path.name]} secuencias de "
            f"{ajustes.shingle_size} palabras"
        )
    print(
        f"synthetic:fingerprints: {len(conjunto.hashes)} huellas distintas en "
        f"{destino.relative_to(raiz).as_posix()}, solo como SHA-256"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    analizador.add_argument(
        "--specimen",
        nargs=5,
        action="append",
        metavar=("RUTA", "FORMULARIO", "EDICION", "PUBLICADOR", "FECHA"),
        help="un specimen de tmp/specimens/ con lo que se sabe de el; se repite por specimen",
    )
    argumentos = analizador.parse_args(argv)
    return run(paths.repo_root(), paths.specimens_dir(), argumentos.specimen)


if __name__ == "__main__":
    raise SystemExit(main())
