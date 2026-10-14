"""Quien fabrica un valor sellado.

Una regla sobre el arbol sintactico: **solo `case_record/crypto.py` produce
`Sealed`** (PA-8, capa 2 del diseno de seguridad de U4). Es hermano del que U3
instalo para el tipo redactado, y existe por la misma razon tecnica: `NewType`
se borra en tiempo de ejecucion, asi que `Sealed(b"Nayibe Quintero")` es una
llamada legal que el comprobador de tipos acepta sin protestar.

Sin este chequeo, "todo lo personal se cifra antes de persistir" seria una
afirmacion que habria que volver a revisar cada vez que alguien toca el modulo.
Con el, es algo que una herramienta comprueba en cada corrida.

**Lo que se persigue no es un descuido, es un atajo.** Producir el tipo son
**tres formas**, no una:

| Forma | Que hace |
| --- | --- |
| `Sealed(datos)` | Invocar el constructor |
| `cast(Sealed, datos)` | Afirmar el tipo sin construirlo |
| Una anotacion `: Sealed` con `# type: ignore` al lado | Silenciar al comprobador para lo mismo |

Buscar solo la llamada dejaria abierta la puerta de al lado. Es la leccion que
la revision del diseno de U3 dejo escrita, y aqui se aplica de entrada.

**Contra que NO protege.** El archivo exento puede fabricar un sellado con lo
que quiera: `from_storage` acepta cualquier cadena de bytes. Lo que esta regla
compra no es imposibilidad, es **un solo sitio que auditar**. Decirlo importa:
un control que se cree mas fuerte de lo que es acaba sustituyendo a los que si
harian falta.

La direccion de las importaciones --que nadie fuera de `crypto.py` importe la
biblioteca de criptografia-- es la otra mitad de la capa 2, y no vive aqui: la
comprueba el contrato de importacion del linter, donde viven las demas.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from untangle import paths

#: El tipo que solo un archivo puede producir.
TIPO = "Sealed"

#: El unico archivo que lo produce. Relativo a la raiz del repositorio. No es
#: donde el tipo se **declara** --eso es `models.py`, que solo lo nombra-- sino
#: donde se **fabrica**: el punto unico de cifrado.
ARCHIVO_QUE_LO_PRODUCE = "app/backend/src/untangle/case_record/crypto.py"

#: Donde se busca: todo el codigo del aplicativo, pruebas incluidas. Las pruebas
#: entran a proposito, igual que en el chequeo hermano: una prueba que fabricara
#: un sellado falso estaria comprobando la garantia contra si misma.
PREFIJOS = (
    "app/backend/src",
    "app/backend/tests",
)

#: Lo que nunca se recorre.
IGNORADOS = ("__pycache__", ".venv", "node_modules")


@dataclass(frozen=True)
class Hallazgo:
    """Un hallazgo del chequeo: su regla, donde esta y que hay que arreglar."""

    rule: str
    where: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.rule}] {self.where}: {self.detail}"


def _archivos(root: Path) -> tuple[Path, ...]:
    encontrados: list[Path] = []
    for prefijo in PREFIJOS:
        base = root / prefijo
        if not base.is_dir():
            continue
        encontrados.extend(
            archivo
            for archivo in base.rglob("*.py")
            if archivo.is_file() and not any(parte in IGNORADOS for parte in archivo.parts)
        )
    return tuple(sorted(encontrados, key=lambda p: p.as_posix()))


def _nombra_el_tipo(nodo: ast.expr | None) -> bool:
    """Si una expresion menciona el tipo, tal cual o con su modulo delante."""
    if nodo is None:
        return False
    return any(
        (isinstance(hijo, ast.Name) and hijo.id == TIPO)
        or (isinstance(hijo, ast.Attribute) and hijo.attr == TIPO)
        for hijo in ast.walk(nodo)
    )


def _silenciado_entre(lineas: list[str], primera: int, ultima: int) -> bool:
    """Si alguna linea del tramo lleva un `type: ignore`."""
    return any("type: ignore" in linea for linea in lineas[primera - 1 : ultima])


def _silenciado(lineas: list[str], nodo: ast.AST) -> bool:
    """Si el enunciado lleva un `type: ignore` en alguna de sus lineas."""
    primera = getattr(nodo, "lineno", None)
    if primera is None:
        return False
    ultima = getattr(nodo, "end_lineno", None) or primera
    return _silenciado_entre(lineas, primera, ultima)


def _tramo_de_la_firma(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[int, int]:
    """Las lineas que ocupa la firma: del `def` hasta antes del cuerpo.

    No se calcula desde `node.args` porque `ast.arguments` **no lleva numero de
    linea**: preguntarselo devuelve nada, el tramo sale vacio y el chequeo no
    dispara nunca. Es un fallo silencioso --el control existe, se lee bien y no
    mira nada-- y solo aparece si una prueba planta la violacion en la firma.
    """
    primera = node.lineno
    ultima = node.body[0].lineno - 1 if node.body else primera
    return primera, max(primera, ultima)


def _nombres_locales_del_tipo(arbol: ast.AST) -> frozenset[str]:
    """Con que nombres se conoce el tipo **en este archivo**.

    Hace falta porque importar con otro nombre es gratis: `from ... import
    Sealed as S` y despues `S(b"en claro")` fabrica un sellado de verdad que el
    repositorio escribiria en la columna cifrada. Comparar solo contra el nombre
    literal dejaba esa puerta abierta, y era la mas facil de las tres.
    """
    nombres = {TIPO}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom):
            nombres.update(a.asname or a.name for a in nodo.names if a.name == TIPO)
        elif isinstance(nodo, ast.Import):
            nombres.update(a.asname for a in nodo.names if a.asname and a.name.endswith(f".{TIPO}"))
    return frozenset(nombres)


class _Revisor(ast.NodeVisitor):
    """Recorre un archivo y apunta las tres formas de producir el tipo."""

    def __init__(self, donde: str, lineas: list[str], nombres: frozenset[str]) -> None:
        self.donde = donde
        self.lineas = lineas
        #: Con que nombres se conoce el tipo en este archivo, alias incluidos.
        self.nombres = nombres
        self.hallazgos: list[Hallazgo] = []

    def visit_Call(self, node: ast.Call) -> None:
        objetivo = node.func
        if (isinstance(objetivo, ast.Name) and objetivo.id in self.nombres) or (
            isinstance(objetivo, ast.Attribute) and objetivo.attr == TIPO
        ):
            self._apuntar(
                node.lineno,
                f"invoca el constructor de `{TIPO}`. Solo lo hace "
                f"`{ARCHIVO_QUE_LO_PRODUCE}`: `NewType` se borra en tiempo de "
                "ejecucion, asi que esta llamada fabrica unos bytes que el "
                "repositorio escribira en la columna cifrada sin que lo esten",
            )

        es_cast = (isinstance(objetivo, ast.Name) and objetivo.id == "cast") or (
            isinstance(objetivo, ast.Attribute) and objetivo.attr == "cast"
        )
        if es_cast and node.args and _nombra_el_tipo(node.args[0]):
            self._apuntar(
                node.lineno,
                f"afirma el tipo `{TIPO}` con `cast` sin construirlo. Es la puerta "
                "de al lado de la anterior y entrega exactamente lo mismo: un "
                "dato personal en claro que el almacen aceptara",
            )

        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if _nombra_el_tipo(node.annotation) and _silenciado(self.lineas, node):
            self._apuntar(
                node.lineno,
                f"anota `{TIPO}` y silencia al comprobador con `type: ignore`. "
                "Es la tercera forma de producir el tipo, y un control que solo "
                "cubre la forma obvia atrapa descuidos, no atajos",
            )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._firma_silenciada(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._firma_silenciada(node)
        self.generic_visit(node)

    def _firma_silenciada(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        argumentos = [
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
            node.args.vararg,
            node.args.kwarg,
        ]
        anotaciones = [node.returns, *(a.annotation for a in argumentos if a is not None)]
        primera, ultima = _tramo_de_la_firma(node)
        if any(_nombra_el_tipo(a) for a in anotaciones) and _silenciado_entre(
            self.lineas, primera, ultima
        ):
            self._apuntar(
                node.lineno,
                f"declara `{TIPO}` en su firma con un `type: ignore` al lado",
            )

    def _apuntar(self, linea: int, detalle: str) -> None:
        self.hallazgos.append(Hallazgo("PA-8", f"{self.donde}:{linea}", detalle))


def check_file(path: Path, *, relative: str) -> list[Hallazgo]:
    """Los hallazgos de un archivo. El punto unico de cifrado queda exento."""
    if relative == ARCHIVO_QUE_LO_PRODUCE:
        return []

    fuente = path.read_text(encoding="utf-8")
    try:
        arbol = ast.parse(fuente, filename=str(path))
    except SyntaxError as error:
        return [Hallazgo("PA-8", f"{relative}:{error.lineno or 0}", f"no se pudo leer: {error}")]

    revisor = _Revisor(relative, fuente.splitlines(), _nombres_locales_del_tipo(arbol))
    revisor.visit(arbol)
    return revisor.hallazgos


def run_all(root: Path | None = None) -> list[Hallazgo]:
    """La regla sobre todo el codigo del aplicativo."""
    base = root if root is not None else paths.repo_root()
    hallazgos: list[Hallazgo] = []
    for archivo in _archivos(base):
        hallazgos.extend(check_file(archivo, relative=archivo.relative_to(base).as_posix()))
    return hallazgos


def _imprimir(hallazgos: Iterable[Hallazgo]) -> None:
    for hallazgo in hallazgos:
        print(str(hallazgo), file=sys.stderr)


def main() -> int:
    hallazgos = run_all()
    if hallazgos:
        _imprimir(hallazgos)
        print(
            f"\n{len(hallazgos)} hallazgo(s). El valor sellado solo lo fabrica "
            f"`{ARCHIVO_QUE_LO_PRODUCE}`: es la unica puerta por la que un dato "
            "personal llega al almacen, y con dos habria que revisar en cada "
            "cambio si sigue siendo cierto que todo lo personal se cifra.",
            file=sys.stderr,
        )
        return 1
    print("cifrado del caso: un solo productor del tipo sellado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
