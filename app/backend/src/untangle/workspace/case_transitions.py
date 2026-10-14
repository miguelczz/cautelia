"""El diagrama del ciclo de vida se genera desde la tabla, no se dibuja.

Un diagrama editado a mano describe un ciclo de vida que el codigo no aplica, y
ese desacuerdo no lo nota nadie: el dibujo se ve bien, las pruebas pasan, y lo
que esta mal es la frase que alguien leyo para entender el sistema. Esto es la
enmienda de ADR-005 hecha herramienta.

**Que compara.** Genera el diagrama desde `transitions.yaml` y lo busca en cada
documento declarado abajo. Si alguno tiene uno distinto, falla y ensena las dos
versiones.

**Por que una lista y no un archivo.** El mismo ciclo de vida acabara dibujado
en mas de un sitio --la especificacion hoy, el README cuando U22 lo escriba-- y
el segundo dibujo es justo el que se queda atras. Anadirlo aqui es una linea.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from untangle import paths
from untangle.case_record import schema_loading

#: Los documentos que dibujan el ciclo de vida. Relativos a la raiz.
DOCUMENTOS = (
    "aidlc/spaces/default/intents/260915-untangle-app/construction/"
    "u4-case-record/functional-design/functional-spec.md",
)

#: El estado en que nace un caso y el que lo termina. Van en el diagrama como
#: los dos extremos y no salen de la tabla: la tabla dice como se pasa de un
#: estado a otro, no por donde se entra y se sale del ciclo.
INICIAL = "open"
TERMINAL = "closed"

_BLOQUE = re.compile(r"```mermaid\n(stateDiagram-v2\n.*?)```", re.S)


def render() -> str:
    """El diagrama que dice la tabla, en el orden en que la tabla lo dice."""
    lineas = ["stateDiagram-v2", f"    [*] --> {INICIAL}"]
    lineas.extend(
        f"    {fila.from_state.value} --> {fila.to_state.value}: {fila.id}"
        for fila in schema_loading.transitions()
    )
    lineas.append(f"    {TERMINAL} --> [*]")
    return "\n".join(lineas) + "\n"


def written_in(texto: str) -> tuple[str, ...]:
    """Los diagramas de ciclo de vida que ese documento trae escritos."""
    return tuple(coincidencia.group(1) for coincidencia in _BLOQUE.finditer(texto))


def check(root: Path | None = None) -> list[str]:
    """Los desacuerdos. Vacio cuando todos los documentos dicen lo mismo."""
    base = root if root is not None else paths.repo_root()
    esperado = render()
    problemas: list[str] = []

    for relativo in DOCUMENTOS:
        archivo = base / relativo
        if not archivo.is_file():
            problemas.append(f"{relativo}: no existe, y esta declarado como documento del ciclo")
            continue

        escritos = written_in(archivo.read_text(encoding="utf-8"))
        if not escritos:
            problemas.append(
                f"{relativo}: no trae ningun diagrama de estados, y esta declarado "
                "como documento del ciclo. O se borro, o la lista de arriba sobra"
            )
            continue

        problemas.extend(
            f"{relativo}: el diagrama escrito no coincide con la tabla.\n"
            f"--- la tabla dice ---\n{esperado}"
            f"--- el documento dice ---\n{escrito}"
            for escrito in escritos
            if escrito != esperado
        )

    return problemas


def main() -> int:
    problemas = check()
    if problemas:
        for problema in problemas:
            print(problema, file=sys.stderr)
        print(
            "\nEl diagrama se genera desde `transitions.yaml`. Uno editado a mano "
            "describe un ciclo de vida que el codigo no aplica, y ese desacuerdo "
            "no lo nota nadie: el dibujo se ve bien y las pruebas pasan.",
            file=sys.stderr,
        )
        return 1
    print(
        f"ciclo de vida: {len(schema_loading.transitions())} transiciones, y el diagrama coincide"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
