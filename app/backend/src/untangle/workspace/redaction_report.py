"""El informe de la redaccion: por idioma, por tipo y **por reconocedor**.

Es el comando que produce el valor real de NFR11.2, y la columna por reconocedor
es la razon de que exista (NFR-U3-5): sin ella, un reconocedor roto se esconde
detras del respaldo, que tapa el mismo dato y suma al mismo tipo. Con ella, la
fila que se queda en cero dice cual dejo de funcionar.

**Nunca un promedio combinado de los dos idiomas** (P12, BR4.1). Los dos lados se
publican lado a lado, y un idioma roto no se puede esconder detras del otro.

**La cifra del respaldo va aparte** (BR4.2). Un respaldo que dispara mucho
significa una de dos cosas, y las dos son trabajo concreto: un reconocedor se
rompio, o hay un formato frecuente sin reconocedor propio. Sumarla a su tipo
borraria justo esa senal. Su techo es 1 de cada 10 por idioma y **no detiene la
entrega**: tapar de mas es el lado seguro del error.

Se mide sobre las **fixtures sembradas y versionadas** de RT-14 y RT-15, no
sobre texto de corrida: dos corridas del mismo commit tienen que dar el mismo
numero. La regla de autoidentificacion tiene su propia fila (`*-person-cue`),
aparte de la del modelo: sin ella, lo que tapa la regla se sumaria a la fila del
modelo y un modelo que dejara de reconocer nombres no se notaria.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from untangle import paths
from untangle.base import Locale
from untangle.compliance.redaction import api
from untangle.compliance.redaction.recognizers.models import (
    FORMAT_TYPES,
    EntityType,
    RedactionReport,
)
from untangle.evals.redaction_fixtures import load_fixtures

#: El techo de NFR11.2: uno de cada diez tapados, por idioma. No bloquea; abre
#: trabajo.
TECHO_DEL_RESPALDO = 0.10


@dataclass(frozen=True)
class PorIdioma:
    """Lo medido en un idioma. Nunca se combina con el otro."""

    language: Locale
    counts_by_type: dict[EntityType, int]
    counts_by_recognizer: dict[str, int]
    fallback_count: int
    total: int

    @property
    def fallback_share(self) -> float:
        return self.fallback_count / self.total if self.total else 0.0

    @property
    def over_budget(self) -> bool:
        return self.fallback_share > TECHO_DEL_RESPALDO


def _sumar(destino: dict[str, int], origen: dict[str, int]) -> None:
    for clave, valor in origen.items():
        destino[clave] = destino.get(clave, 0) + valor


def measure(language: Locale, root: Path) -> PorIdioma:
    """Corre la redaccion sobre las fixtures sembradas de un idioma."""
    fixtures = load_fixtures(language, root)
    por_tipo: dict[EntityType, int] = dict.fromkeys(EntityType, 0)
    por_reconocedor: dict[str, int] = {}
    respaldo = 0

    for seed in (*fixtures.seeds, *fixtures.cross_language):
        informe: RedactionReport = api.redaction_report(seed.text, language=language)
        for tipo, cuantos in informe.counts_by_type.items():
            por_tipo[tipo] = por_tipo.get(tipo, 0) + cuantos
        _sumar(por_reconocedor, informe.counts_by_recognizer)
        respaldo += informe.fallback_count

    return PorIdioma(
        language=language,
        counts_by_type=por_tipo,
        counts_by_recognizer=por_reconocedor,
        fallback_count=respaldo,
        total=sum(por_tipo.values()),
    )


def measure_all(root: Path | None = None) -> tuple[PorIdioma, ...]:
    """Los dos idiomas, cada uno por su lado."""
    base = root if root is not None else paths.repo_root()
    return tuple(measure(idioma, base) for idioma in ("es", "en"))


def _imprimir(medidos: tuple[PorIdioma, ...]) -> None:
    """Los dos idiomas lado a lado, y ninguna cifra combinada."""
    idiomas = [m.language for m in medidos]

    print("redaccion: hallazgos sobre las fixtures sembradas (RT-14 y RT-15)")
    print()
    print(f"{'tipo de entidad':<18}" + "".join(f"{i:>8}" for i in idiomas))
    for tipo in EntityType:
        fila = "".join(f"{m.counts_by_type.get(tipo, 0):>8}" for m in medidos)
        print(f"{tipo.value:<18}{fila}")

    # **Todos** los reconocedores en las dos columnas, incluidos los del otro
    # idioma. Filtrarlos por el idioma del turno esconderia justo la senal que
    # esta tabla existe para dar: en un turno espanol, un dato dictado en ingles
    # lo encuentra el juego ingles, y esa fila es la prueba de que los dos juegos
    # corren (BR2.9). Una fila que se queda en cero dice que reconocedor dejo de
    # funcionar.
    print()
    print(f"{'reconocedor':<24}" + "".join(f"{m.language:>8}" for m in medidos))
    identificadores = sorted({i for m in medidos for i in m.counts_by_recognizer})
    for identificador in identificadores:
        fila = "".join(f"{m.counts_by_recognizer.get(identificador, 0):>8}" for m in medidos)
        print(f"{identificador:<24}{fila}")

    print()
    print(f"{'respaldo (NFR11.2)':<18}" + "".join(f"{m.fallback_count:>8}" for m in medidos))
    print(f"{'total tapado':<18}" + "".join(f"{m.total:>8}" for m in medidos))
    print(
        f"{'proporcion':<18}"
        + "".join(f"{m.fallback_share * 100:>7.1f}%" for m in medidos)
        + f"   (techo {TECHO_DEL_RESPALDO * 100:.0f} %)"
    )


def main() -> int:
    medidos = measure_all()
    _imprimir(medidos)

    # Un tipo por formato con cero hallazgos sobre sus propias semillas es un
    # reconocedor roto, no una medicion baja: eso si detiene la entrega. Son los
    # cuatro propios del dominio y el VIN, todos sembrados en RT-14.
    rotos = [
        f"{m.language}/{tipo.value}"
        for m in medidos
        for tipo in sorted(FORMAT_TYPES)
        if m.counts_by_type.get(tipo, 0) == 0
    ]
    if rotos:
        print(
            f"\nsin un solo hallazgo en sus casos sembrados: {', '.join(rotos)}. "
            "Un reconocedor que falla en su propio caso sembrado esta roto, no "
            "es imperfecto (NFR11.1)",
            file=sys.stderr,
        )
        return 1

    pasados = [m.language for m in medidos if m.over_budget]
    if pasados:
        # No bloquea (NFR-U3-3): tapar de mas es el lado seguro. Pero pasarse
        # senala un reconocedor roto o un formato frecuente sin reconocedor
        # propio, y las dos cosas son trabajo concreto.
        print(
            f"\nel respaldo tapa mas de 1 de cada 10 en: {', '.join(pasados)}. "
            "No detiene la entrega; abre trabajo (NFR11.2)"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
