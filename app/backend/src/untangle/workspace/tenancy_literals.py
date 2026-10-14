"""Ningun identificador de aseguradora literal fuera de su sitio (BR4.2, SEC-U2.14).

Una rama por aseguradora dentro del codigo de decision es la forma en que una
diferencia de **configuracion** se convierte en una diferencia de
**comportamiento** que nadie puede auditar. Toda diferencia entre aseguradoras
--idioma, voz, reglas, politicas, corpus, poliza de ejemplo, la derivacion
siempre de la agencia-- vive en su carpeta versionada.

Los identificadores no salen de una lista escrita a mano: salen de **las carpetas
que hay**. Asi, anadir una cuarta aseguradora la deja vigilada sin tocar este
archivo, que es la misma propiedad que pide FR9.3.

Dos sitios donde un literal si es correcto, y ninguno mas:

- el cargador de configuracion y las propias carpetas, que es donde el
  identificador **se declara**;
- las fixtures y los casos de prueba, que existen precisamente para nombrar una
  aseguradora concreta, y los datos que produce el generador sintetico en
  `app/data/`, que son fixtures a escala de corpus.

Cada entrada de la lista de exclusion lleva su razon escrita al lado. Una lista
de exclusiones sin razones crece hasta que el chequeo deja de comprobar nada.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from untangle import paths

#: Donde un identificador literal es correcto, con su razon. Son prefijos de ruta
#: relativos a la raiz del repositorio.
PERMITIDOS: tuple[tuple[str, str], ...] = (
    ("app/config/tenants", "Las carpetas donde el identificador se declara (C-25)"),
    ("app/backend/src/untangle/tenancy/config.py", "El cargador de configuracion"),
    (
        "app/data",
        "Datos, no codigo: la salida del generador (corpus, polizas, casos sembrados, DS-8) y "
        "sus textos fuente nombran la aseguradora a la que pertenecen, igual que una fixture. "
        "Ahi el identificador es un dato; lo que prohibe BR4.2 es una rama en el codigo (U7)",
    ),
    ("app/backend/tests", "Pruebas y sus datos sembrados"),
    (
        "app/frontend/e2e",
        "El arnes de pantallas y su registro de rutas: datos de prueba, por la "
        "misma razon que `app/backend/tests`. Una pantalla por aseguradora se "
        "abre en una direccion concreta, y con un identificador inventado la "
        "pagina llama a rutas que no existen y el propio arnes falla por los "
        "errores de consola, que es como se descubrio (U13)",
    ),
    ("app/evals/cases", "Casos de golden set: datos, no codigo"),
    ("app/evals/subsets", "Listas de casos de golden set: datos, no codigo"),
    (
        "app/evals/last-run.json",
        "El resumen de la ultima corrida completa: nombra casos y criterios del golden "
        "set, y algunos llevan a su aseguradora en el nombre. Datos generados, no codigo",
    ),
    (
        "app/evals/fixtures",
        "Escenarios de prueba: datos, no codigo. La mayoria arma sus frases con "
        "marcadores desde la configuracion cargada (U10), pero un escenario que "
        "prueba una conducta propia de una aseguradora concreta -- como el "
        "perfil de reglas de U9 -- nombra la suya por la misma razon que un "
        "caso de golden set nombra la suya",
    ),
)

#: Donde se busca. El prefijo del aplicativo entero, menos lo generado.
EXTENSIONES = (".py", ".ts", ".tsx", ".js", ".yaml", ".yml", ".json", ".sql", ".sh")

#: Lo que nunca se recorre: dependencias, artefactos y salidas.
IGNORADOS = (
    "node_modules",
    ".venv",
    "__pycache__",
    "dist",
    "coverage",
    "tmp",
    "app/contracts",
)


@dataclass(frozen=True)
class Hallazgo:
    """Un literal donde no debia estar. Nombra el archivo y la linea."""

    path: Path
    line: int
    tenant_id: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: identificador de aseguradora literal '{self.tenant_id}'"


def tenant_ids(root: Path) -> tuple[str, ...]:
    """Los identificadores que hay, leidos de las carpetas que existen."""
    directorio = root / "app" / "config" / "tenants"
    if not directorio.is_dir():
        return ()
    return tuple(sorted(p.name for p in directorio.iterdir() if p.is_dir()))


def _permitido(relativa: Path) -> bool:
    texto = relativa.as_posix()
    return any(texto.startswith(prefijo) for prefijo, _ in PERMITIDOS)


def _archivos(root: Path) -> Iterable[Path]:
    prefijo = root / "app"
    if not prefijo.is_dir():
        return
    for archivo in sorted(prefijo.rglob("*"), key=lambda p: p.as_posix()):
        if not archivo.is_file() or archivo.suffix not in EXTENSIONES:
            continue
        relativa = archivo.relative_to(root)
        if any(parte in relativa.as_posix() for parte in IGNORADOS):
            continue
        if _permitido(relativa):
            continue
        yield archivo


def run_all(root: Path | None = None) -> list[Hallazgo]:
    """Los literales encontrados fuera de sitio, en orden estable."""
    base = root if root is not None else paths.repo_root()
    identificadores = tenant_ids(base)
    if not identificadores:
        return []

    # Palabra completa: un identificador coincide cuando aparece como palabra, no
    # cuando aparece dentro de otra. Buscar subcadenas sueltas daria falsos
    # positivos que acaban convirtiendose en exclusiones, y una lista de
    # exclusiones que crece es un chequeo que deja de comprobar.
    #
    # Este comentario no nombra a ninguna aseguradora a proposito: el chequeo se
    # encontro a si mismo cuando lo hacia, que es justo lo que tiene que hacer.
    patron = re.compile(r"\b(" + "|".join(re.escape(i) for i in identificadores) + r")\b")

    hallazgos: list[Hallazgo] = []
    for archivo in _archivos(base):
        try:
            contenido = archivo.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for numero, linea in enumerate(contenido.splitlines(), start=1):
            for coincidencia in patron.finditer(linea):
                hallazgos.append(
                    Hallazgo(
                        path=archivo.relative_to(base),
                        line=numero,
                        tenant_id=coincidencia.group(1),
                    )
                )
    return hallazgos


def main() -> int:
    hallazgos = run_all()
    for hallazgo in hallazgos:
        print(str(hallazgo), file=sys.stderr)
    if hallazgos:
        print(
            f"\n{len(hallazgos)} identificador(es) de aseguradora literal(es) fuera "
            "del cargador y de las fixtures. Las diferencias entre aseguradoras "
            "viven en su carpeta versionada, no en una rama del codigo (BR4.2).",
            file=sys.stderr,
        )
        return 1
    print("identificadores de aseguradora: ninguno literal fuera de sitio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
