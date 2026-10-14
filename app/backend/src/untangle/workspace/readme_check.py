"""`mise run readme:gen` y `mise run readme:check`: las dos secciones generadas del README (U22).

    python -m untangle.workspace.readme_check gen     reescribe las dos secciones
    python -m untangle.workspace.readme_check check   falla si lo publicado difiere

Un solo comando con dos modos, como los contratos generados: el arreglo de un
README desactualizado es correr `gen` y commitear, nunca editar a mano lo que hay
entre las marcas (BR4.2).

Dos fuentes para dos secciones (FD-U22-10): las cifras salen de la linea base
vigente y "Como falla" del resumen de la ultima corrida completa. Sin ninguna de
las dos, su seccion dice "no medida" con su causa y el chequeo compara contra eso:
no se pone rojo por no haber medido todavia.
"""

from __future__ import annotations

import sys
from pathlib import Path

from untangle import paths
from untangle.evals.evidence import api as evidence
from untangle.evals.gates.loading import load_current_baseline, load_last_run_digest
from untangle.evals.loading import LoadError

__all__ = ["check", "generate", "main"]


def check(readme: Path | None = None) -> list[str]:
    """Los desacuerdos entre el README y sus dos fuentes. Vacio si coinciden."""
    archivo = readme if readme is not None else paths.readme_path()
    if not archivo.is_file():
        return [f"{archivo.name}: no existe; `readme:gen` reescribe secciones, no crea el archivo"]
    baseline = load_current_baseline()
    problemas = evidence.check(
        archivo.read_text(encoding="utf-8"), baseline, load_last_run_digest()
    )
    return [str(problema) for problema in problemas]


def generate(readme: Path | None = None) -> bool:
    """Reescribe las dos secciones. Devuelve si el archivo cambio."""
    archivo = readme if readme is not None else paths.readme_path()
    anterior = archivo.read_text(encoding="utf-8")
    nuevo = evidence.regenerate(anterior, load_current_baseline(), load_last_run_digest())
    if nuevo == anterior:
        return False
    archivo.write_text(nuevo, encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    argumentos = sys.argv[1:] if argv is None else argv
    if len(argumentos) != 1 or argumentos[0] not in ("gen", "check"):
        print("uso: python -m untangle.workspace.readme_check gen|check", file=sys.stderr)
        return 64

    try:
        if argumentos[0] == "gen":
            cambio = generate()
            print("README.md: dos secciones regeneradas" if cambio else "README.md: sin cambios")
            return 0

        problemas = check()
    except (LoadError, evidence.MarkersError, OSError) as error:
        print(f"readme: {error}", file=sys.stderr)
        return 1

    if problemas:
        for problema in problemas:
            print(problema, file=sys.stderr)
        print(
            "\nLas dos secciones generadas salen de la linea base vigente. "
            "Corra `mise run readme:gen` y commitee el resultado; editar a mano lo que hay "
            "entre las marcas no sirve, porque el chequeo lo volveria a encontrar distinto.",
            file=sys.stderr,
        )
        return 1
    print("README.md: las dos secciones generadas coinciden con sus fuentes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
