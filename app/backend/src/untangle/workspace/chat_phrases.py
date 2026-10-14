"""Cada frase que el grafo puede mandar por el chat, el chat sabe decirla.

**El chequeo que faltaba, y lo que costó no tenerlo.** El nodo de captura declara
`intake.tone.calm` como su frase de degradación (`INTAKE_SPEC.degraded_copy_key`).
La tabla de frases del chat no la tenía, y su respaldo --razonable por sí solo--
convierte una clave desconocida en la frase de error. Resultado: cada turno que se
degradaba le decía a la persona *"Tuve un problema para responder eso"* en vez de
*"Quiero ayudarle con calma"*, y en pantalla no había forma de distinguir un fallo
de una degradación. Lo vio Miguel usando el chat; ninguna de las 2.375 pruebas.

**Por qué no está con los otros chequeos del catálogo.** Necesita leer lo que los
nodos declaran, y `untangle.copy_catalog` está **por debajo** de
`untangle.orchestration` en el contrato de capas: no puede importarlo. Este módulo
vive en `workspace`, que está por encima de todo y es donde ya viven los demás
chequeos del árbol.

**Qué dirección comprueba.** El chequeo de consumidores del catálogo mira una --que
toda clave escrita se use en algún sitio-- y este mira la contraria: que toda clave
que el servidor **puede mandar por este canal** el canal sepa decirla. Ninguna de
las dos implica la otra, y la que faltaba era esta.

**Qué claves son esas** (ampliado el 2026-10-12, cuando el servidor estrenó
`compliance.handoff.adjuster_review_inquiry` y la tabla no la tenía: quien pidió un
ajustador en una consulta leyó "tuve un problema para responder eso" con el caso
ya derivado). Son tres fuentes: la frase de degradación de cada nodo, toda clave
que `orchestration/turn.py` declara como constante --la espera, el error y las
derivaciones salen de ahí-- y la frase de cierre por insultos, que sale del nodo de
captura. Las dos propias de la voz no cuentan: la consola de la llamada tiene su
propio chequeo (`voice_phrases`).
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

from untangle import paths
from untangle.orchestration import turn
from untangle.orchestration.graph import GRAPH_NODE_SPECS
from untangle.orchestration.nodes.intake.composition import TONE_CLOSING_ABUSE

#: Donde el chat declara las frases que sabe decir. Tabla de literales, por la
#: misma razón que el resto del catálogo: una clave armada en ejecución no se
#: puede comprobar con un grep.
TABLA_DEL_CHAT = Path("app") / "frontend" / "src" / "pages" / "chat" / "chat-copy.ts"


#: Las dos frases que `turn.py` declara y solo dice una llamada. No pasan por el chat.
SOLO_DE_LA_VOZ = frozenset({"orchestration.turn.waiting", "orchestration.turn.error"})

#: Una entrada de la tabla del chat: `"clave": (t) => ...`. Se lee la entrada y no
#: cualquier aparicion de la clave: una clave nombrada en un comentario no es una frase
#: que el chat sepa decir.
_ENTRADA_DE_LA_TABLA = re.compile(r'^\s*"([a-z0-9_.]+)":\s*\(t\)', re.MULTILINE)


def _claves_de_turn() -> frozenset[str]:
    """Toda clave que `turn.py` declara como constante a nivel de modulo.

    Se lee el codigo y no el modulo en memoria, porque `CopyKey` es un tipo con nombre
    sobre `str` y en ejecucion una clave no se distingue de cualquier cadena."""
    arbol = ast.parse(Path(str(turn.__file__)).read_text(encoding="utf-8"))
    claves: set[str] = set()
    for nodo in arbol.body:
        if not isinstance(nodo, ast.Assign) or not isinstance(nodo.value, ast.Call):
            continue
        llamada = nodo.value
        if (
            isinstance(llamada.func, ast.Name)
            and llamada.func.id == "CopyKey"
            and len(llamada.args) == 1
            and isinstance(llamada.args[0], ast.Constant)
            and isinstance(llamada.args[0].value, str)
        ):
            claves.add(llamada.args[0].value)
    return frozenset(claves)


def claves_que_el_servidor_manda() -> list[str]:
    """Las claves que el servidor puede mandar al chat como espera, derivacion o error."""
    degradacion = {spec.degraded_copy_key for spec in GRAPH_NODE_SPECS}
    del_turno = _claves_de_turn() - SOLO_DE_LA_VOZ
    return sorted({*degradacion, *del_turno, str(TONE_CLOSING_ABUSE)})


def faltantes(root: Path | None = None) -> list[str]:
    """Las claves que el servidor puede mandar y el chat no sabe decir."""
    base = root if root is not None else paths.repo_root()
    tabla = base / TABLA_DEL_CHAT
    if not tabla.is_file():
        # Sin la tabla este chequeo no comprueba nada y pasaría en verde, que es
        # peor que no tenerlo: se nombra el archivo y se falla.
        msg = f"no existe la tabla de frases del chat en '{TABLA_DEL_CHAT.as_posix()}'"
        raise FileNotFoundError(msg)
    conocidas = set(_ENTRADA_DE_LA_TABLA.findall(tabla.read_text(encoding="utf-8")))
    return [clave for clave in claves_que_el_servidor_manda() if clave not in conocidas]


def main() -> int:
    ausentes = faltantes()
    for clave in ausentes:
        print(
            f"'{clave}' la puede mandar el servidor al chat y no esta en "
            f"{TABLA_DEL_CHAT.as_posix()}: la persona leeria la frase de error en su lugar",
            file=sys.stderr,
        )
    if ausentes:
        print(f"\n{len(ausentes)} frase(s) del servidor sin decir en el chat", file=sys.stderr)
        return 1
    print(f"frases del servidor: las {len(claves_que_el_servidor_manda())} llegan al chat")
    return 0


if __name__ == "__main__":
    sys.exit(main())
