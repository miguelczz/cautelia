#!/usr/bin/env python3
"""Comprueba las afirmaciones de los artefactos del flujo contra la realidad.

No es parte de `scripts/verify.sh`: ese guion es la compuerta del **aplicativo**,
y esto revisa los documentos del flujo de trabajo, que son otra cosa. Se corre a
mano antes de cerrar una etapa.

Existe por un motivo medido. En la unidad U3, el revisor encontro diecisiete
defectos en cuatro etapas, y trece eran de dos clases que una maquina detecta:
afirmar que existe un comando, un archivo o un mecanismo que no existe, y
contradecirse dentro del mismo documento. Escribir lo que *deberia* ser cierto
como si *fuera* cierto es comodo de leer y deja a quien implementa teniendo que
volver a preguntar.

Uso:
    python3 scripts/check-artifacts.py <directorio de la unidad>
    python3 scripts/check-artifacts.py --todas
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REGISTRO = RAIZ / "aidlc/spaces/default/intents/260915-untangle-app"
CONSTRUCCION = REGISTRO / "construction"

# Prefijos de ruta que nombran codigo real del repositorio. Una ruta con uno de
# estos prefijos o existe, o esta declarada como algo que la unidad va a crear.
PREFIJOS_DE_CODIGO = ("app/", "scripts/", ".github/", "mise.toml", "docker-compose.yml")

# Un documento puede prometer algo que todavia no existe. Lo declara con una de
# estas palabras cerca; sin ellas, la afirmacion se lee como un hecho.
MARCAS_DE_FUTURO = (
    "entra", "entran", "nuevo", "nueva", "nuevos", "nuevas", "se crea", "se crean",
    "se anade", "se añade", "se anaden", "se añaden", "tarea nueva", "tareas nuevas",
    "no existe", "todavia", "todavía", "cuando exista", "la generacion de codigo",
    "la generación de código", "propuest",
)


def tareas_declaradas() -> set[str]:
    """Las tareas que hoy existen en el archivo de tareas."""
    datos = tomllib.loads((RAIZ / "mise.toml").read_text())
    return set(datos.get("tasks", {}))


def contexto(texto: str, pos: int, radio: int = 260) -> str:
    return texto[max(0, pos - radio) : pos + radio].lower()


#: Donde una unidad puede declarar las tareas que crea, en orden de antiguedad.
#:
#: La primera es la de las unidades que tuvieron etapa de infraestructura. La
#: segunda se anadio el 2026-09-29 con U18: desde la decision de modo ligero del
#: 2026-09-21 (DP-12) esa etapa **no corre**, asi que las unidades nuevas no
#: tienen donde declararlas y este chequeo daba por no declarada cualquier tarea
#: suya. U16 paso por casualidad --su tarea ya existia en `mise.toml` cuando se
#: corrio el chequeo-- y eso es justo lo que hace peligroso un hueco: no falla,
#: pasa.
DOCS_DE_TAREAS_NUEVAS = (
    "infrastructure-design/cicd-pipeline.md",
    "code-generation/code-generation-plan.md",
)


def tareas_que_la_unidad_crea(unidad: Path) -> set[str]:
    """Las tareas que la unidad declara como nuevas, en su tabla.

    Declararlas una vez en un sitio vale para toda la unidad: exigir la palabra
    "nueva" al lado de cada mencion llenaria los documentos de ruido.
    """
    declaradas: set[str] = set()
    for nombre in DOCS_DE_TAREAS_NUEVAS:
        doc = unidad / nombre
        if not doc.exists():
            continue
        bloque = re.split(r"^#+ .*tareas nuevas.*$", doc.read_text(), flags=re.M | re.I)
        if len(bloque) < 2:
            continue
        declaradas |= set(re.findall(r"^\| `([a-z0-9:_-]+)` \|", bloque[1], re.M))
    return declaradas


def revisar_comandos(doc: Path, texto: str, tareas: set[str], creadas: set[str]) -> list[str]:
    """Todo `mise run X` citado: o X existe, o la unidad declara que lo crea."""
    fallos = []
    vistas: set[str] = set()
    for m in re.finditer(r"mise run ([a-z0-9:_-]+)", texto):
        tarea = m.group(1)
        if tarea in tareas or tarea in creadas or tarea in vistas:
            continue
        if any(marca in contexto(texto, m.start()) for marca in MARCAS_DE_FUTURO):
            continue
        vistas.add(tarea)
        fallos.append(f"{doc.name}: cita `mise run {tarea}`, que no existe en mise.toml y la unidad no declara que lo cree")
    return fallos


def revisar_rutas(doc: Path, texto: str) -> list[str]:
    """Toda ruta de codigo citada: o existe, o el documento dice que se va a crear."""
    fallos = []
    patron = r"`((?:app|scripts|\.github)/[A-Za-z0-9_./<>-]+|mise\.toml|docker-compose\.yml)`"
    for m in re.finditer(patron, texto):
        ruta = m.group(1)
        if "<" in ruta or ">" in ruta:  # plantilla, no ruta literal
            continue
        if (RAIZ / ruta).exists():
            continue
        if any(marca in contexto(texto, m.start()) for marca in MARCAS_DE_FUTURO):
            continue
        fallos.append(f"{doc.name}: cita `{ruta}`, que no existe y no se declara como algo a crear")
    return fallos


def _regla_de(unidad: str, br: str) -> bool:
    """Si esa unidad declara esa regla. Falso tambien si la unidad no existe."""
    carpetas = sorted(CONSTRUCCION.glob(f"{unidad.lower()}-*/functional-design/rules.md"))
    for reglas in carpetas:
        if br in set(re.findall(r"^  - id: (BR[0-9]+\.[0-9]+)$", reglas.read_text(), re.M)):
            return True
    return False


def revisar_identificadores(unidad: Path, docs: dict[Path, str]) -> list[str]:
    """Todo identificador citado tiene que estar definido en algun sitio."""
    fallos = []
    definidos: set[str] = set()
    for texto in docs.values():
        definidos |= set(re.findall(r"^  - id: ([A-Z]+[0-9]+\.[0-9]+)$", texto, re.M))
        definidos |= set(re.findall(r"^\| ((?:SEC|NFR|BR|AC)-?[A-Z0-9]*[0-9]+\.[0-9]+) \|", texto, re.M))
        definidos |= set(re.findall(r"^\| ((?:FD|NFRD|INF|CG)-U[0-9]+-[0-9]+) \|", texto, re.M))
    for doc, texto in docs.items():
        for idn in set(re.findall(r"\b(?:FD|NFRD|INF|CG)-U[0-9]+-[0-9]+\b", texto)):
            if idn not in definidos:
                fallos.append(f"{doc.name}: cita {idn}, que no esta declarado en ninguna tabla de decisiones de la unidad")
        # Una regla citada **con su unidad al lado** --"BR4.5 de U16"-- se busca en
        # esa unidad y no en esta. Las referencias entre unidades son legitimas y
        # frecuentes: U18 habla la llamada que construyo U16 y cita sus reglas. Sin
        # esta rama, el chequeo empujaba a escribir prosa mas vaga para esquivarlo,
        # que es lo contrario de lo que existe para hacer.
        ajenas = {
            (br, u) for br, u in re.findall(r"\b(BR[0-9]+\.[0-9]+) de (U[0-9]+)\b", texto)
        }
        for br, unidad_ajena in ajenas:
            if not _regla_de(unidad_ajena, br):
                fallos.append(
                    f"{doc.name}: cita {br} de {unidad_ajena}, que no existe en las reglas de esa unidad"
                )
        propios = set(re.findall(r"\bBR[0-9]+\.[0-9]+\b", texto)) - {br for br, _ in ajenas}
        if propios and (unidad / "functional-design/rules.md").exists():
            reglas = (unidad / "functional-design/rules.md").read_text()
            reales = set(re.findall(r"^  - id: (BR[0-9]+\.[0-9]+)$", reglas, re.M))
            for br in propios - reales:
                fallos.append(f"{doc.name}: cita {br}, que no existe en rules.md")
    return fallos


#: Los numerales en palabras del 1 al 40, generados y no escritos a mano.
#:
#: **Escritos a mano le faltaban justo los del rango que se usa.** "Diecisiete
#: reglas" pasaba en verde sobre un documento con veinte, porque la lista saltaba
#: de "quince" a "veinte". Un chequeo de cifras con agujeros es peor que no
#: tenerlo: entrena a confiar en el verde.
_UNIDADES = (
    "cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece "
    "catorce quince dieciseis diecisiete dieciocho diecinueve veinte veintiuno "
    "veintidos veintitres veinticuatro veinticinco veintiseis veintisiete "
    "veintiocho veintinueve treinta"
).split()

#: Las formas con tilde y el femenino, que es como se escriben de verdad en prosa.
_VARIANTES = {
    "dieciseis": ("dieciséis",),
    "veintiuno": ("veintiún", "veintiuna"),
    "veintidos": ("veintidós",),
    "veintitres": ("veintitrés",),
    "veintiseis": ("veintiséis",),
    "uno": ("una", "un"),
}


def _numerales() -> dict[str, int]:
    """Cada numeral con su valor, del cero al cuarenta."""
    mapa: dict[str, int] = {}
    for valor, palabra in enumerate(_UNIDADES):
        mapa[palabra] = valor
        for variante in _VARIANTES.get(palabra, ()):
            mapa[variante] = valor
    for decena, nombre in ((30, "treinta"), (40, "cuarenta")):
        mapa[nombre] = decena
        for valor, palabra in enumerate(_UNIDADES[1:10], start=1):
            mapa[f"{nombre} y {palabra}"] = decena + valor
    return mapa


def revisar_cifras(doc: Path, texto: str) -> list[str]:
    """La cifra del **total**, escrita en prosa, tiene que coincidir con lo que hay.

    Tres cosas que parecen detalles y cada una era un modo de fallo:

    **Solo la entrada del documento**, antes de su primer encabezado de seccion.
    Mas abajo una cifra casi siempre cuenta una familia --"tres llevan
    `[bloquea]`"-- y compararla con el total la marcaria mal.

    **Solo la frase del total**, la que la convencion usa: "N reglas, repartidas en
    M familias" o "N reglas en M familias". Sin eso, "tres reglas de esta unidad
    son compuertas duras" --una cuenta parcial perfectamente correcta-- salia como
    hallazgo.

    **El numeral mas largo primero.** "Tres reglas" casa dentro de "Treinta y tres
    reglas", asi que sin ordenar por longitud un documento que dice bien su total
    de 33 se marcaba como si dijera 3. Es la misma trampa que hizo pasar por buena
    la cabecera de U16 cuando decia "treinta y ocho" y habia treinta y una.

    Los tres se descubrieron el 2026-09-29 al completar la lista de numerales, que
    saltaba de "quince" a "veinte" y dejaba pasar "diecisiete reglas" sobre un
    documento con veinte.
    """
    entrada = re.split(r"^## ", texto, maxsplit=1, flags=re.M)[0]
    palabras = _numerales()
    reales = {
        "reglas": len(re.findall(r"^  - id: BR[0-9]+\.[0-9]+$", texto, re.M)),
        "controles": len(re.findall(r"^\| SEC-U[0-9]+\.[0-9]+ \|", texto, re.M)),
    }
    # Los mas largos primero: si no, el final de un compuesto gana al compuesto.
    alternativa = "|".join(
        re.escape(palabra) for palabra in sorted(palabras, key=len, reverse=True)
    )
    sustantivos = "|".join(reales)
    #: La frase con la que este proyecto enuncia un total, y solo esa.
    patron = re.compile(
        rf"\b({alternativa})\s+({sustantivos})\b\s*,?\s*"
        rf"(?:repartidas|en\s+[\wáéíóúñ]+\s+familias)",
        re.I,
    )
    fallos = []
    for numeral, sustantivo in patron.findall(entrada):
        real = reales[sustantivo.lower()]
        valor = palabras[numeral.lower()]
        if real and valor != real:
            fallos.append(f"{doc.name}: dice '{numeral} {sustantivo}' y hay {real}")
    return fallos


def revisar_trazabilidad(unidad: Path) -> list[str]:
    """Todo objetivo de una fila de cobertura tiene que existir de verdad."""
    fallos = []
    for tj in unidad.glob("*/traceability.json"):
        datos = json.loads(tj.read_text())
        for fila in datos.get("coverage", []) + datos.get("reverse", []):
            objetivo = fila.get("target", "")
            for m in re.finditer(r"\b((?:app|scripts|\.github)/[A-Za-z0-9_./-]+)\b", objetivo):
                if not (RAIZ / m.group(1)).exists():
                    fallos.append(f"{tj.parent.name}/traceability.json: {fila['id']} apunta a {m.group(1)}, que no existe")
    return fallos


def revisar_unidad(unidad: Path) -> list[str]:
    tareas = tareas_declaradas()
    creadas = tareas_que_la_unidad_crea(unidad)
    docs = {p: p.read_text() for p in sorted(unidad.glob("*/*.md")) if "/reviews/" not in str(p)}
    fallos: list[str] = []
    for doc, texto in docs.items():
        fallos += revisar_comandos(doc, texto, tareas, creadas)
        fallos += revisar_rutas(doc, texto)
        fallos += revisar_cifras(doc, texto)
    fallos += revisar_identificadores(unidad, docs)
    fallos += revisar_trazabilidad(unidad)
    return fallos


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    unidades = (
        sorted(CONSTRUCCION.glob("u*/"))
        if sys.argv[1] == "--todas"
        else [Path(sys.argv[1]).resolve()]
    )
    total = 0
    for unidad in unidades:
        fallos = revisar_unidad(unidad)
        total += len(fallos)
        estado = f"{len(fallos)} hallazgo(s)" if fallos else "sin hallazgos"
        print(f"\n{unidad.name}: {estado}")
        for f in fallos:
            print(f"  {f}")
    print(f"\nTotal: {total}")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
