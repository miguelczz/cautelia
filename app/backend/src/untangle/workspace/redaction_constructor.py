"""Quien produce el tipo redactado, y quien guarda un valor junto a su etiqueta.

Dos reglas sobre el arbol sintactico, un solo comando, porque son la misma
busqueda: **de que cosas no puede haber ni una sola en este arbol** (BR1.6,
BR1.8, SEC-U3.2, SEC-U3.7, SEC-U3.8).

**Regla 1: solo `compliance/redaction/api.py` produce `Redacted`.** Hace falta
porque el tipo **no garantiza nada por si solo**: `NewType` se borra en tiempo de
ejecucion, asi que `Redacted(texto_sin_tapar)` es una llamada legal que el
comprobador de tipos acepta. Sin este chequeo, "imposible por construccion" seria
"improbable por costumbre".

Y producir el tipo son **tres formas, no una**. Buscar solo la llamada dejaba
abierta la puerta de al lado, y eso lo encontro la revision del diseno:

| Forma | Que hace |
| --- | --- |
| `Redacted(texto)` | Invocar el constructor |
| `cast(Redacted, texto)` | Afirmar el tipo sin construirlo |
| Una anotacion `: Redacted` con `# type: ignore` al lado | Silenciar al comprobador para lo mismo |

Un control que solo cubre la forma obvia de saltarselo es un control que atrapa
los descuidos y no los atajos.

**Regla 2: dentro del modulo de redaccion no existe ninguna boveda.** Ninguna
estructura relaciona un hallazgo con su valor original: ni un diccionario con el
texto detectado de clave, ni un contenedor donde se guarde, ni una clase con un
campo de hallazgo y un campo de valor a la vez. Si existiera una, existiria un
unico sitio con todos los datos personales juntos, que es peor que no tapar. La
irreversibilidad deja asi de ser una promesa y pasa a ser algo que una
herramienta comprueba.

Comparar dos trozos del texto **sin guardarlos** si esta permitido, y es lo que
hace la numeracion de etiquetas: lo que la regla persigue es que un valor quede
**guardado** en algun sitio, no que se mire.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from untangle import paths

#: El tipo que solo un archivo puede producir.
TIPO = "Redacted"

#: El unico archivo que lo produce. Relativo a la raiz del repositorio.
ARCHIVO_QUE_LO_PRODUCE = "app/backend/src/untangle/compliance/redaction/api.py"

#: Donde vive el modulo de redaccion. La regla 2 se aplica aqui dentro: es el
#: unico sitio del aplicativo que ve a la vez el texto en claro y sus hallazgos,
#: y por lo tanto el unico donde una boveda se podria construir sin querer.
MODULO_DE_REDACCION = "app/backend/src/untangle/compliance/redaction"

#: Donde se busca la regla 1: todo el codigo del aplicativo, pruebas incluidas.
#: Las pruebas entran a proposito: una prueba que fabricara un `Redacted` falso
#: estaria comprobando la garantia contra si misma.
PREFIJOS = (
    "app/backend/src",
    "app/backend/tests",
)

#: Lo que nunca se recorre.
IGNORADOS = ("__pycache__", ".venv", "node_modules")

#: Nombres de campo que **llevan un valor**. La lista es corta a proposito: son
#: los que alguien escribiria sin pensarlo al querer guardar "lo que se
#: detecto".
NOMBRES_DE_VALOR = frozenset(
    {"value", "text", "original", "raw", "plain", "matched", "detected", "valor", "texto"}
)

#: Nombres de campo que **identifican un hallazgo o su etiqueta**. Una clase con
#: uno de estos y uno de los de arriba es la correspondencia que BR1.6 prohibe.
NOMBRES_DE_HALLAZGO = frozenset(
    {"entity_type", "label", "ordinal", "recognizer_id", "etiqueta", "tipo", "numero"}
)

#: Metodos que **guardan** lo que reciben.
METODOS_QUE_GUARDAN = frozenset({"add", "append", "appendleft", "insert", "setdefault", "update"})


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


def _es_rebanada(nodo: ast.expr) -> bool:
    """Si la expresion es `algo[a:b]`, es decir un trozo de un texto."""
    return isinstance(nodo, ast.Subscript) and isinstance(nodo.slice, ast.Slice)


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
    """Recorre un archivo y apunta lo que no puede estar en el."""

    def __init__(
        self,
        donde: str,
        lineas: list[str],
        nombres: frozenset[str],
        *,
        dentro_del_modulo: bool,
    ) -> None:
        self.donde = donde
        self.lineas = lineas
        #: Con que nombres se conoce el tipo en este archivo, alias incluidos.
        self.nombres = nombres
        self.dentro_del_modulo = dentro_del_modulo
        self.hallazgos: list[Hallazgo] = []

    # --- Regla 1: quien produce el tipo --------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        objetivo = node.func
        if (isinstance(objetivo, ast.Name) and objetivo.id in self.nombres) or (
            isinstance(objetivo, ast.Attribute) and objetivo.attr == TIPO
        ):
            self._apuntar(
                "BR1.8",
                node.lineno,
                f"invoca el constructor de `{TIPO}`. Solo lo hace "
                f"`{ARCHIVO_QUE_LO_PRODUCE}`: `NewType` se borra en tiempo de "
                "ejecucion, asi que esta llamada fabrica un texto que el resto "
                "del sistema tratara como redactado sin que lo este",
            )

        es_cast = (isinstance(objetivo, ast.Name) and objetivo.id == "cast") or (
            isinstance(objetivo, ast.Attribute) and objetivo.attr == "cast"
        )
        if es_cast and node.args and _nombra_el_tipo(node.args[0]):
            self._apuntar(
                "BR1.8",
                node.lineno,
                f"afirma el tipo `{TIPO}` con `cast` sin construirlo. Es la puerta "
                "de al lado de la anterior y entrega exactamente lo mismo: un "
                "texto sin tapar que los puntos de salida aceptaran",
            )

        if self.dentro_del_modulo:
            self._boveda_en_llamada(node)

        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if _nombra_el_tipo(node.annotation) and _silenciado(self.lineas, node):
            self._apuntar(
                "BR1.8",
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
                "BR1.8",
                node.lineno,
                f"declara `{TIPO}` en su firma con un `type: ignore` al lado",
            )

    # --- Regla 2: ninguna boveda ---------------------------------------------

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if self.dentro_del_modulo:
            campos = {
                hijo.target.id
                for hijo in node.body
                if isinstance(hijo, ast.AnnAssign) and isinstance(hijo.target, ast.Name)
            }
            de_valor = sorted(campos & NOMBRES_DE_VALOR)
            de_hallazgo = sorted(campos & NOMBRES_DE_HALLAZGO)
            if de_valor and de_hallazgo:
                self._apuntar(
                    "BR1.6",
                    node.lineno,
                    f"la clase `{node.name}` guarda {de_hallazgo} y {de_valor} a la "
                    "vez: es la correspondencia entre un hallazgo y su valor "
                    "original, y un solo sitio con todos los datos personales "
                    "juntos es peor que no taparlos",
                )
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        if self.dentro_del_modulo:
            for clave in node.keys:
                if clave is not None and _es_rebanada(clave):
                    self._apuntar(
                        "BR1.6",
                        clave.lineno,
                        "usa un trozo del texto de entrada como clave de un "
                        "diccionario: eso es guardar el valor detectado, que es "
                        "justo la boveda que no puede existir",
                    )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if self.dentro_del_modulo:
            for objetivo in node.targets:
                if isinstance(objetivo, ast.Subscript) and _es_rebanada(objetivo.slice):
                    self._apuntar(
                        "BR1.6",
                        node.lineno,
                        "indexa por un trozo del texto de entrada para guardar algo "
                        "debajo: es la correspondencia entre el valor y su etiqueta",
                    )
        self.generic_visit(node)

    def _boveda_en_llamada(self, node: ast.Call) -> None:
        objetivo = node.func
        if isinstance(objetivo, ast.Attribute) and objetivo.attr in METODOS_QUE_GUARDAN:
            if any(_es_rebanada(arg) for arg in node.args):
                self._apuntar(
                    "BR1.6",
                    node.lineno,
                    f"guarda un trozo del texto de entrada con `.{objetivo.attr}()`: "
                    "un hallazgo que cargue su valor convierte cualquier volcado de "
                    "diagnostico en una fuga",
                )
        for palabra in node.keywords:
            if _es_rebanada(palabra.value):
                self._apuntar(
                    "BR1.6",
                    node.lineno,
                    f"pasa un trozo del texto de entrada como `{palabra.arg}=`: si "
                    "lo que se construye lo conserva, la correspondencia existe",
                )

    def _apuntar(self, regla: str, linea: int, detalle: str) -> None:
        self.hallazgos.append(Hallazgo(regla, f"{self.donde}:{linea}", detalle))


def check_file(path: Path, *, relative: str) -> list[Hallazgo]:
    """Los hallazgos de un archivo. El que produce el tipo queda fuera de la regla 1."""
    fuente = path.read_text(encoding="utf-8")
    try:
        arbol = ast.parse(fuente, filename=str(path))
    except SyntaxError as error:
        return [Hallazgo("BR1.8", f"{relative}:{error.lineno or 0}", f"no se pudo leer: {error}")]

    revisor = _Revisor(
        relative,
        fuente.splitlines(),
        _nombres_locales_del_tipo(arbol),
        dentro_del_modulo=relative.startswith(MODULO_DE_REDACCION),
    )
    revisor.visit(arbol)

    if relative == ARCHIVO_QUE_LO_PRODUCE:
        # El unico archivo que puede producir el tipo. La regla 2 le sigue
        # aplicando: es tambien el que mas cerca esta de poder construir una
        # boveda sin querer.
        return [h for h in revisor.hallazgos if h.rule != "BR1.8"]
    return revisor.hallazgos


def run_all(root: Path | None = None) -> list[Hallazgo]:
    """Las dos reglas sobre todo el codigo del aplicativo."""
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
            f"\n{len(hallazgos)} hallazgo(s). El tipo redactado solo lo produce "
            f"`{ARCHIVO_QUE_LO_PRODUCE}`, y dentro del modulo de redaccion no puede "
            "existir ninguna estructura que relacione un hallazgo con su valor "
            "original.",
            file=sys.stderr,
        )
        return 1
    print("redaccion: un solo productor del tipo y ninguna boveda")
    return 0


if __name__ == "__main__":
    sys.exit(main())
