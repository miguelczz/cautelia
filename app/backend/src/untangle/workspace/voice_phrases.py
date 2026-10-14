"""Cada aviso que el servidor puede mandar por el socket, la consola sabe decirlo.

Es el hermano de `chat_phrases.py`, en la misma dirección y por la misma razón: el
chequeo de consumidores del catálogo mira que toda clave escrita se use en algún
sitio, y **este mira la contraria**, que toda clave que el servidor puede mandar
por este canal el canal sepa decirla. Ninguna de las dos implica la otra.

**Por qué es un módulo aparte y no una rama de aquel.** Las fuentes son otras. En
el chat lo que puede llegar son las frases de degradación que declaran los nodos;
aquí lo que puede llegar es el cuadro `notice` del protocolo, cuyo vocabulario son
los motivos de cuota de U5 y los de voz apagada de U15. Un solo módulo llamado
"frases del chat" que comprobara las dos cosas sería un módulo que miente sobre sí
mismo, y el mensaje de su fallo nombraría el archivo equivocado.

**Qué pasa si falta una.** La consola devuelve nulo y no dice nada: el aviso se
pierde en silencio. Es deliberado del otro lado --una clave desconocida es un
contrato roto, no un caso de ejecución, y poner la frase de error en su lugar
diría que la llamada se rompió-- y por eso hace falta este chequeo, que es lo que
convierte "contrato roto" en una compuerta en vez de un hueco en pantalla.
"""

from __future__ import annotations

import sys
from pathlib import Path

from untangle import paths
from untangle.voice.availability import all_copy_keys

#: Donde la consola declara los avisos que sabe decir. Tabla de literales, por la
#: misma razón que el resto del catálogo: una clave armada en ejecución no se
#: puede comprobar con un grep.
TABLA_DE_LA_VOZ = Path("app") / "frontend" / "src" / "pages" / "voice" / "voice-copy.ts"


def claves_que_el_servidor_manda() -> tuple[str, ...]:
    """El vocabulario completo del cuadro `notice` y del motivo de no haber voz.

    Sale de las tablas de cada dueño y no de una lista escrita aquí: una lista
    propia se quedaría atrás el día que U17 añada su carril, que es justo el día
    en que este chequeo tendría que avisar.
    """
    return tuple(str(clave) for clave in all_copy_keys())


def faltantes(root: Path | None = None) -> list[str]:
    """Las claves que el servidor puede mandar y la consola no sabe decir."""
    base = root if root is not None else paths.repo_root()
    tabla = base / TABLA_DE_LA_VOZ
    if not tabla.is_file():
        # Sin la tabla este chequeo no comprueba nada y pasaría en verde, que es
        # peor que no tenerlo: se nombra el archivo y se falla.
        msg = f"no existe la tabla de avisos de la voz en '{TABLA_DE_LA_VOZ.as_posix()}'"
        raise FileNotFoundError(msg)
    contenido = tabla.read_text(encoding="utf-8")
    return [clave for clave in claves_que_el_servidor_manda() if f'"{clave}"' not in contenido]


def main() -> int:
    ausentes = faltantes()
    for clave in ausentes:
        print(
            f"'{clave}' la puede mandar el servidor por el socket y no esta en "
            f"{TABLA_DE_LA_VOZ.as_posix()}: el aviso se perderia en silencio",
            file=sys.stderr,
        )
    if ausentes:
        print(f"\n{len(ausentes)} aviso(s) que la consola no sabe decir", file=sys.stderr)
        return 1
    total = len(claves_que_el_servidor_manda())
    print(f"avisos de la voz: los {total} que el servidor manda llegan a la consola")
    return 0


if __name__ == "__main__":
    sys.exit(main())
