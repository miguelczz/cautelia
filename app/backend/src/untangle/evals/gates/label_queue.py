"""Elige los turnos que Miguel va a etiquetar para DS-7 (F2, FD-U21-3).

Puro: recibe las transcripciones de una corrida (ya redactadas) y lo que la cola y las
etiquetas ya tienen, y devuelve las entradas nuevas con las cifras de como se eligieron.
No lee ni escribe archivos y no llama a ningun modelo; eso es de `label_queue_cli`.

**Reproducible, sin `random`.** Todo desempate sale de SHA-256 sobre la semilla y el
identificador (el mismo mecanismo de `sampling`): la misma corrida, la misma semilla y el
mismo estado de la cola dan siempre la misma cola, en cualquier maquina.

**Paridad.** La misma cantidad por idioma (20 por omision), contada por el idioma del
texto del turno y no por el del caso: una conversacion que cambia de idioma a mitad
(RT-10) tiene turnos en los dos. Si un idioma no alcanza, se dice con la cifra; no se
rellena con otro idioma ni con texto de ejemplo.

**Lo facil no es mayoria.** Si la cola se llenara al azar con los turnos de una corrida en
verde, casi todos serian limpios, la calibracion no tendria un solo "falla" que medir y
no diria nada del juez. Por eso, para cada criterio, la mitad de lo que se elige sale de
los turnos que el codigo ya marco como dudosos para ese criterio (`judged_criteria`) y
la otra mitad de los limpios. Si no hay suficientes marcados, se toman todos y se dice; si
no hay ninguno, se dice tambien, en vez de inventar una dificultad que el codigo no vio.
Tambien se reparte entre conversaciones: ninguna aporta un segundo turno mientras otra no
haya aportado uno.

**Particiones fijas.** Cada entrada nueva lleva su particion (`fit`, `dev` o `test`), que
no se cambia despues: solo `test` cuenta para encender al juez, asi que la mitad va a
`test`, y el resto se reparte entre ajuste y desarrollo. La asignacion se hace dentro de
cada criterio y cada estrato, para que `test` reciba su parte de marcados y de limpios.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from itertools import zip_longest

from untangle.base import Locale
from untangle.evals.gates import judged_criteria
from untangle.evals.gates.calibration import CALIBRATION_THRESHOLD
from untangle.evals.gates.models import HumanLabel, LabelingQueueEntry, Split
from untangle.evals.gates.wilson import wilson_lower_bound
from untangle.evals.transcripts import TranscriptsFile

LANGUAGES: tuple[Locale, ...] = ("es", "en")

#: Veinte turnos por idioma: la cifra de DS-7 (PRD 11.1).
DEFAULT_PER_LANGUAGE = 20

#: Cambiarla cambia la cola; por eso es explicita y se imprime.
DEFAULT_SEED = "ds7-v1"

#: Que parte de lo que se elige de cada criterio sale de turnos marcados por el codigo.
FLAGGED_SHARE = 0.5

#: Como se reparten las particiones dentro de un grupo, en orden: la mitad a `test`.
SPLIT_CYCLE: tuple[Split, ...] = (Split.TEST, Split.FIT, Split.TEST, Split.DEV)

Key = tuple[str, int, str]
TurnKey = tuple[str, int]


@dataclass(frozen=True)
class Candidate:
    """Un turno de la agente que se puede etiquetar."""

    transcript_id: str
    turn_index: int
    language: Locale
    text: str
    context: str | None
    signals: tuple[str, ...]

    @property
    def turn_key(self) -> TurnKey:
        return (self.transcript_id, self.turn_index)


@dataclass(frozen=True)
class Existing:
    """Lo que la cola y las etiquetas ya tienen. El plan solo agrega a esto."""

    queue: tuple[LabelingQueueEntry, ...] = ()
    labels: tuple[HumanLabel, ...] = ()

    def by_key(self) -> dict[Key, tuple[Locale, Split]]:
        """Cada (transcripcion, turno, criterio) ya presente, sin repetir lo que esta en las dos."""
        presentes: dict[Key, tuple[Locale, Split]] = {}
        for entrada in self.queue:
            clave = (entrada.transcript_id, entrada.turn_index, entrada.criterion)
            presentes[clave] = (entrada.language, entrada.split)
        for etiqueta in self.labels:
            clave = (etiqueta.transcript_id, etiqueta.turn_index, etiqueta.criterion)
            presentes.setdefault(clave, (etiqueta.language, etiqueta.split))
        return presentes


@dataclass(frozen=True)
class CellStat:
    """Como quedo un criterio en un idioma."""

    language: Locale
    criterion: str
    #: Ya en la cola o etiquetadas antes de esta corrida del comando.
    already: int
    added_flagged: int
    added_clean: int
    #: Turnos de la corrida que el codigo marco como dudosos para este criterio.
    flagged_in_run: int
    #: Cuantas entradas de este criterio e idioma estan en `test` (las ya puestas y las nuevas).
    test_total: int


@dataclass(frozen=True)
class QueuePlan:
    new_entries: tuple[LabelingQueueEntry, ...]
    stats: tuple[CellStat, ...]
    #: Cuantas entradas faltan para llegar a `per_language`, por idioma. Cero si llega.
    shortfall: dict[Locale, int] = field(default_factory=dict)
    #: Conversaciones que se descartaron por no traer las senales del codigo.
    unsignaled_conversations: int = 0
    #: Turnos elegibles por idioma en la corrida, para decir con la cifra cuando no alcanza.
    eligible: dict[Locale, int] = field(default_factory=dict)


def transcript_id(case_key: str, run_id: str) -> str:
    """El identificador de una transcripcion en las etiquetas: el caso y la corrida.

    Lleva la corrida porque el mismo caso, en otra corrida, dice otras cosas: una etiqueta
    atada solo al caso quedaria pegada al texto equivocado.
    """
    return f"{case_key}@{run_id}"


def candidates(file: TranscriptsFile) -> tuple[tuple[Candidate, ...], int]:
    """Los turnos de la agente que se pueden etiquetar, y cuantas conversaciones se descartan.

    Se excluye la apertura (la frase fija del catalogo, que juzga el codigo) y las
    conversaciones sin senales del codigo, que no se pueden estratificar.
    """
    encontrados: list[Candidate] = []
    sin_senales = 0
    for conversacion in file.conversations:
        if not conversacion.signals_read:
            sin_senales += 1
            continue
        identificador = transcript_id(conversacion.case_key, file.run_id)
        ultimo_de_la_persona: str | None = None
        for turno in conversacion.turns:
            if turno.speaker == "insured":
                ultimo_de_la_persona = turno.text
                continue
            if turno.opening:
                continue
            encontrados.append(
                Candidate(
                    transcript_id=identificador,
                    turn_index=turno.index,
                    language=turno.language,
                    text=turno.text,
                    context=ultimo_de_la_persona,
                    signals=turno.signals,
                )
            )
    return tuple(encontrados), sin_senales


def min_labels_per_class(threshold: float = CALIBRATION_THRESHOLD) -> int:
    """Cuantas etiquetas de cada clase necesita la particion de prueba de un criterio.

    El limite inferior de Wilson de un acierto perfecto con `n` observaciones es el mejor
    que un juez puede sacar: con menos de este `n` ni uno perfecto llega al umbral. Es
    aritmetica sobre el umbral vigente; no lo cambia ni lo discute.
    """
    n = 1
    while wilson_lower_bound(n, n) < threshold:
        n += 1
    return n


def _score(seed: str, *partes: object) -> int:
    resumen = hashlib.sha256(":".join([seed, *map(str, partes)]).encode()).hexdigest()
    return int(resumen, 16)


@dataclass
class _Cursor:
    """El estado de la eleccion de un idioma: que turnos se usaron y de que conversaciones."""

    seed: str
    used: set[TurnKey]
    per_conversation: Counter[str]

    def pick(self, pool: Iterable[Candidate], n: int, *, criterion: str) -> list[Candidate]:
        """Hasta `n` turnos del grupo, de las conversaciones menos usadas y por semilla."""
        restantes = sorted(
            (c for c in pool if c.turn_key not in self.used),
            key=lambda c: _score(self.seed, "pick", criterion, c.transcript_id, c.turn_index),
        )
        elegidos: list[Candidate] = []
        while restantes and len(elegidos) < n:
            # `min` devuelve el primero de los empatados: el de menor puntaje.
            mejor = min(restantes, key=lambda c: self.per_conversation[c.transcript_id])
            restantes.remove(mejor)
            elegidos.append(mejor)
            self.used.add(mejor.turn_key)
            self.per_conversation[mejor.transcript_id] += 1
        return elegidos


def _allocate(criteria: Sequence[str], already: Counter[str], total: int) -> dict[str, int]:
    """Reparte `total` entradas nuevas llenando primero el criterio que menos tiene."""
    reparto = dict.fromkeys(criteria, 0)
    for _ in range(total):
        siguiente = min(criteria, key=lambda c: (already[c] + reparto[c], criteria.index(c)))
        reparto[siguiente] += 1
    return reparto


@dataclass(frozen=True)
class _Chosen:
    candidate: Candidate
    criterion: str
    flagged: bool
    split: Split = Split.TEST


def _choose(
    pool: Sequence[Candidate], criteria: Sequence[str], reparto: dict[str, int], cursor: _Cursor
) -> list[_Chosen]:
    """Para cada criterio, la mitad de marcados y el resto de limpios (o lo que haya)."""
    elegidas: dict[str, list[_Chosen]] = {c: [] for c in criteria}

    # Primero los turnos que el codigo marco, criterio por criterio.
    for criterio in criteria:
        marcados = [c for c in pool if judged_criteria.is_flagged(criterio, c.signals)]
        quiero = math.ceil(reparto[criterio] * FLAGGED_SHARE)
        elegidas[criterio] += [
            _Chosen(c, criterio, flagged=True)
            for c in cursor.pick(marcados, quiero, criterion=criterio)
        ]

    # Despues los limpios; si se acaban, lo que quede de marcados.
    for criterio in criteria:
        limpios = [c for c in pool if not judged_criteria.is_flagged(criterio, c.signals)]
        faltan = reparto[criterio] - len(elegidas[criterio])
        elegidas[criterio] += [
            _Chosen(c, criterio, flagged=False)
            for c in cursor.pick(limpios, faltan, criterion=criterio)
        ]
        faltan = reparto[criterio] - len(elegidas[criterio])
        if faltan > 0:
            restantes = [c for c in pool if judged_criteria.is_flagged(criterio, c.signals)]
            elegidas[criterio] += [
                _Chosen(c, criterio, flagged=True)
                for c in cursor.pick(restantes, faltan, criterion=criterio)
            ]

    return [elegida for criterio in criteria for elegida in elegidas[criterio]]


def _assign_splits(chosen: list[_Chosen], seed: str) -> list[_Chosen]:
    """La particion de cada entrada nueva, dentro de su criterio y su estrato."""
    grupos: dict[tuple[str, bool], list[_Chosen]] = {}
    for elegida in chosen:
        grupos.setdefault((elegida.criterion, elegida.flagged), []).append(elegida)
    particionadas: list[_Chosen] = []
    for (criterio, _), items in sorted(grupos.items()):
        ordenados = sorted(
            items,
            key=lambda i: _score(
                seed, "split", criterio, i.candidate.transcript_id, i.candidate.turn_index
            ),
        )
        particionadas += [
            _Chosen(i.candidate, i.criterion, i.flagged, SPLIT_CYCLE[posicion % len(SPLIT_CYCLE)])
            for posicion, i in enumerate(ordenados)
        ]
    return particionadas


def _stats_for(
    idioma: Locale,
    criterios: Sequence[str],
    chosen: Sequence[_Chosen],
    pool: Sequence[Candidate],
    presentes: dict[Key, tuple[Locale, Split]],
) -> list[CellStat]:
    estadisticas: list[CellStat] = []
    for criterio in criterios:
        propias = [c for c in chosen if c.criterion == criterio]
        ya = [
            (lang, split) for (_, _, crit), (lang, split) in presentes.items() if crit == criterio
        ]
        ya_del_idioma = [split for lang, split in ya if lang == idioma]
        estadisticas.append(
            CellStat(
                language=idioma,
                criterion=criterio,
                already=len(ya_del_idioma),
                added_flagged=sum(1 for c in propias if c.flagged),
                added_clean=sum(1 for c in propias if not c.flagged),
                flagged_in_run=sum(
                    1 for c in pool if judged_criteria.is_flagged(criterio, c.signals)
                ),
                test_total=sum(1 for s in ya_del_idioma if s is Split.TEST)
                + sum(1 for c in propias if c.split is Split.TEST),
            )
        )
    return estadisticas


def plan_queue(
    file: TranscriptsFile,
    *,
    existing: Existing = Existing(),  # noqa: B008 -- inmutable
    per_language: int = DEFAULT_PER_LANGUAGE,
    criteria: Sequence[str] = judged_criteria.DEFAULT_NAMES,
    seed: str = DEFAULT_SEED,
) -> QueuePlan:
    """Las entradas que faltan para que cada idioma llegue a `per_language`.

    Lo que ya esta en la cola o ya esta etiquetado cuenta y no se toca: el plan solo
    agrega. Con la cola ya completa devuelve un plan sin entradas nuevas.
    """
    elegibles, sin_senales = candidates(file)
    criterios = tuple(criteria)
    presentes = existing.by_key()
    usados: set[TurnKey] = {(t, i) for (t, i, _) in presentes}

    elegidas: dict[Locale, list[_Chosen]] = {}
    estadisticas: list[CellStat] = []
    faltan: dict[Locale, int] = {}
    cuantos_elegibles: dict[Locale, int] = {}

    for idioma in LANGUAGES:
        piscina = [c for c in elegibles if c.language == idioma]
        cuantos_elegibles[idioma] = sum(1 for c in piscina if c.turn_key not in usados)

        ya_por_criterio: Counter[str] = Counter(
            crit for (_, _, crit), (lang, _) in presentes.items() if lang == idioma
        )
        a_agregar = max(0, per_language - sum(ya_por_criterio[c] for c in criterios))
        cursor = _Cursor(
            seed=seed,
            used=usados,
            per_conversation=Counter(
                tid for (tid, _, _), (lang, _) in presentes.items() if lang == idioma
            ),
        )
        nuevas = _choose(
            piscina, criterios, _allocate(criterios, ya_por_criterio, a_agregar), cursor
        )
        nuevas = _assign_splits(nuevas, seed)

        elegidas[idioma] = nuevas
        faltan[idioma] = max(0, a_agregar - len(nuevas))
        estadisticas += _stats_for(idioma, criterios, nuevas, piscina, presentes)

    return QueuePlan(
        new_entries=_in_labeling_order(elegidas, criterios, seed),
        stats=tuple(estadisticas),
        shortfall=faltan,
        unsignaled_conversations=sin_senales,
        eligible=cuantos_elegibles,
    )


def _entry(elegida: _Chosen) -> LabelingQueueEntry:
    cand = elegida.candidate
    return LabelingQueueEntry(
        transcript_id=cand.transcript_id,
        turn_index=cand.turn_index,
        criterion=elegida.criterion,
        language=cand.language,
        split=elegida.split,
        agent_text=cand.text,
        context=cand.context,
    )


def _in_labeling_order(
    elegidas: dict[Locale, list[_Chosen]], criterios: Sequence[str], seed: str
) -> tuple[LabelingQueueEntry, ...]:
    """El orden en que Miguel las ve: alternando idioma y criterio.

    Se puede dejar a medias, y una cola ordenada por idioma dejaria el segundo sin
    etiquetas si se corta a la mitad; alternando, cualquier prefijo tiene los dos.
    """
    por_idioma: list[list[LabelingQueueEntry]] = []
    for idioma in LANGUAGES:
        por_criterio = [
            [
                _entry(c)
                for c in sorted(
                    (c for c in elegidas[idioma] if c.criterion == criterio),
                    key=lambda c: _score(
                        seed, "order", criterio, c.candidate.transcript_id, c.candidate.turn_index
                    ),
                )
            ]
            for criterio in criterios
        ]
        por_idioma.append(
            [e for ronda in zip_longest(*por_criterio) for e in ronda if e is not None]
        )
    return tuple(e for ronda in zip_longest(*por_idioma) for e in ronda if e is not None)


def merge(
    existing: Sequence[LabelingQueueEntry], new: Sequence[LabelingQueueEntry]
) -> tuple[LabelingQueueEntry, ...]:
    """La cola que se escribe: lo que ya habia, intacto y en su orden, y despues lo nuevo."""
    return (*existing, *new)
