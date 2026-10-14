"""Los comandos del generador que invoca el archivo de tareas (U7).

    mise run synthetic:generate   compone y escribe app/data/ (BR1.3)
    mise run synthetic:check      regenera en un directorio temporal y compara (TECH-U7.1)
    mise run synthetic:sample     elige la muestra de diez clausulas por emisora (BR5.4)

Tres comandos de U7 no viven aqui, y cada uno por su razon:

- `synthetic:draft` necesita el adaptador del modelo, y solo la raiz de
  composicion puede construirlo (`untangle.server.synthetic_draft`);
- `synthetic:fingerprints` es el unico que sabe llegar a `tmp/specimens/`, y
  ningun modulo de la composicion puede conocer `tmp/`
  (`untangle.workspace.synthetic_fingerprints`);
- `synthetic:seed` usa la API de U4, que esta por encima del generador en el
  contrato de capas (`untangle.server.synthetic_seed`, FD-U7-9).

Este modulo no importa nada de `untangle.providers`, igual que el resto de la
composicion.

Las lineas que imprime son para quien opera el comando, como las de los demas
comandos del proyecto: no llegan a ninguna persona a traves del aplicativo.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from untangle import paths
from untangle.synthetic_data import canonical, composition, generator, review_sample
from untangle.synthetic_data.manifest import SEED
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.models import TenantConfigError, TenantKind

__all__ = ["CORPUS_COMPOSERS", "main", "run_check", "run_generate", "run_sample"]

#: Los compositores del corpus. Es uno solo, que recorre F3.2 en orden: cada paso
#: usa lo que dejo el anterior (ver `composition`).
CORPUS_COMPOSERS: tuple[generator.Composer, ...] = (composition.compose_corpus,)


def _sin_compositores(composers: Sequence[generator.Composer]) -> bool:
    if composers:
        return False
    print(
        "no hay ningun compositor del corpus registrado (cli.CORPUS_COMPOSERS): no se "
        "escribe ni se compara nada",
        file=sys.stderr,
    )
    return True


def _informar(error: generator.GenerationError) -> int:
    for problema in error.problems:
        print(problema, file=sys.stderr)
    print(f"\n{len(error.problems)} problema(s): no se escribio nada", file=sys.stderr)
    return 1


def run_generate(repo_root: Path, data_dir: Path, composers: Sequence[generator.Composer]) -> int:
    """Compone, valida y escribe `data_dir`. Sale con 1 y sin escribir si algo falla."""
    if _sin_compositores(composers):
        return 2
    solicitud = generator.GenerationRequest(
        repo_root=repo_root, data_dir=data_dir, composers=tuple(composers)
    )
    try:
        informe = generator.generate(solicitud)
    except generator.GenerationError as error:
        return _informar(error)
    print(
        f"synthetic:generate: {len(informe.written)} escrito(s), {len(informe.unchanged)} sin "
        f"cambios, {len(informe.deleted)} borrado(s)"
    )
    return 0


def run_check(repo_root: Path, data_dir: Path, composers: Sequence[generator.Composer]) -> int:
    """Regenera en un directorio temporal y compara byte a byte con `data_dir` (CG-U7-4).

    Publica su duracion (TECH-U7.4). La mide con un reloj monotono, que solo cuenta
    segundos transcurridos: no entra en ninguna salida.
    """
    if _sin_compositores(composers):
        return 2
    inicio = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="synthetic-check-") as temporal:
        solicitud = generator.GenerationRequest(
            repo_root=repo_root, data_dir=Path(temporal), composers=tuple(composers)
        )
        try:
            generator.generate(solicitud)
        except generator.GenerationError as error:
            return _informar(error)
        diferencias = generator.compare(Path(temporal), data_dir)
    duracion = time.perf_counter() - inicio
    for diferencia in diferencias:
        print(diferencia, file=sys.stderr)
    print(f"synthetic:check: duracion {duracion:.2f} s")
    if diferencias:
        print(
            f"\n{len(diferencias)} archivo(s) de app/data/ no son lo que produce el generador; "
            "regenere con `mise run synthetic:generate` y revise el diff",
            file=sys.stderr,
        )
        return 1
    print("synthetic:check: app/data/ es exactamente lo que produce el generador")
    return 0


def _emisoras(repo_root: Path) -> tuple[str, ...]:
    """Las emisoras, leidas de la configuracion: ninguna se nombra en el codigo."""
    cargadas = tenancy_config.load(repo_root / "app" / "config" / "tenants")
    if cargadas.unavailable:
        raise TenantConfigError("; ".join(caida.detail for caida in cargadas.unavailable))
    return tuple(t.tenant_id for t in cargadas.available if t.kind is TenantKind.CARRIER)


def run_sample(repo_root: Path, data_dir: Path, drawn_on: date, *, seed: int = SEED) -> int:
    """Escribe la muestra de cada emisora, sin veredicto (BR5.4).

    **Nunca sobrescribe una muestra que ya existe**: puede llevar el veredicto de
    Miguel, y reemplazarla borraria su revision sin que nadie lo decida. Si el
    archivo ya tiene exactamente lo que se sacaria, no hay nada que hacer.
    """
    try:
        emisoras = _emisoras(repo_root)
        muestras = []
        for emisora in emisoras:
            elegibles = review_sample.candidates(data_dir, emisora)
            muestra = review_sample.draw(emisora, drawn_on, elegibles, seed=seed)
            destino = data_dir / "sources" / review_sample.review_path(emisora, drawn_on)
            texto = review_sample.render(muestra, elegibles, drawn_on)
            if destino.exists() and destino.read_text(encoding="utf-8") != texto:
                msg = (
                    f"'{destino}' ya existe y es distinta: una muestra no se sobrescribe, "
                    "porque puede llevar el veredicto de Miguel"
                )
                raise review_sample.ReviewSampleError(msg)
            muestras.append((destino, texto))
    except (review_sample.ReviewSampleError, TenantConfigError) as error:
        print(f"synthetic:sample: {error}", file=sys.stderr)
        return 1
    for destino, texto in muestras:
        canonical.write_atomic(destino, texto.encode("utf-8"))
        print(f"synthetic:sample: {destino.relative_to(repo_root).as_posix()} (semilla {seed})")
    print(
        "synthetic:sample: sin veredicto; corra `mise run synthetic:generate` para copiarlas "
        "al manifiesto"
    )
    return 0


def _analizador() -> argparse.ArgumentParser:
    analizador = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    sub = analizador.add_subparsers(dest="comando", required=True)
    sub.add_parser("generate", help="compone y escribe app/data/")
    sub.add_parser("check", help="regenera en un directorio temporal y compara byte a byte")
    muestra = sub.add_parser("sample", help="la muestra de diez clausulas por emisora (BR5.4)")
    muestra.add_argument(
        "--date",
        required=True,
        type=date.fromisoformat,
        help="AAAA-MM-DD: el dia en que se saca la muestra, que va en el nombre del archivo",
    )
    return analizador


def main(argv: list[str] | None = None) -> int:
    argumentos = _analizador().parse_args(argv)
    raiz = paths.repo_root()
    if argumentos.comando == "generate":
        return run_generate(raiz, paths.data_dir(), CORPUS_COMPOSERS)
    if argumentos.comando == "sample":
        return run_sample(raiz, paths.data_dir(), argumentos.date)
    return run_check(raiz, paths.data_dir(), CORPUS_COMPOSERS)


if __name__ == "__main__":
    raise SystemExit(main())
