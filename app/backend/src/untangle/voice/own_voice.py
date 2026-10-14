"""La propia voz de la agente, cuando vuelve por el microfono (2026-10-13).

Hasta hoy la unica defensa contra el eco era la cancelacion de eco del navegador (BR4.2).
Cuando no alcanza --altavoz de portatil, volumen alto, un navegador que no cancela lo que
suena por Web Audio-- el reconocedor transcribe a la agente como a cualquiera, y la llamada
tomaba esas palabras por las de la persona: la agente se cortaba a si misma y despues se
contestaba. La pantalla pedia audifonos; Miguel pidio que no pudiera pasar.

Esta es la segunda barrera, de **otro mecanismo**: no mira el audio, mira lo que se sabe.
El servidor sabe que frase mando a sintetizar y cuando suena en el navegador (`CallRunner.
_sonando_hasta`), y el reconocedor dice cuando se pronuncio cada palabra. Una palabra oida
mientras la agente suena, que ademas es lo que la agente esta diciendo, es su eco: se quita
del transcrito antes de que nadie decida nada con el.

**Se quita lo que es eco y nada mas.** El reconocedor entrega a veces en un solo transcrito
el eco de la pregunta y, pegada, la respuesta de la persona. Quitarlo entero le haria
repetirse; quitarle de mas es peor: «no, nadie salio herido» sin el «no» ya dice otra cosa.
Por eso hay tres zonas:

- **mientras la agente suena** (hasta el final estimado): si lo oido es su frase, todo lo
  de esa zona es eco, tambien la palabra que el altavoz deformo;
- **el margen del final** (`TAIL`): el final es una estimacion, asi que aqui solo es eco lo
  que casa con la frase --un tramo que sigue el orden, o sus ultimas palabras--;
- **despues**: es la persona, diga lo que diga.

**Lo que no hace.** No calla el microfono: quien interrumpe con otras palabras sigue
interrumpiendo. Y no reconoce un eco tan deformado que ya no se parece a la frase; ese
caso sigue dependiendo del navegador.
"""

from __future__ import annotations

import re
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from untangle.providers.ports import ExternalText, Transcript

#: Cuanto antes del inicio estimado puede caer una palabra del eco: los tiempos del
#: reconocedor y el reloj del servidor no son el mismo reloj.
LEAD = timedelta(seconds=0.3)
#: El margen del final. El final es una estimacion por bytes enviados: el navegador
#: empieza a sonar algo despues de que el servidor envia.
TAIL = timedelta(seconds=0.8)
#: Lo mismo cuando el transcrito no trae tiempos por palabra y solo se sabe cuando llego:
#: el reconocedor entrega un final hasta un par de segundos despues de lo que oyo.
TAIL_WITHOUT_TIMES = timedelta(seconds=2.0)
#: Que parte de lo oido tiene que ser un tramo seguido de la frase para que sea eco.
MIN_SHARE = 0.6
#: Un tramo cuenta desde dos palabras seguidas: una suelta («no», «es») coincide por azar.
MIN_RUN = 2
#: Hasta cuantas palabras un trozo es demasiado corto para pedirle un tramo: un parcial de
#: una o dos palabras mientras la agente suena es eco si la mitad esta en su frase.
SHORT = 3
#: Cuantas de las ultimas palabras de la frase pueden caer solas en el margen del final.
LAST_WORDS = 3
#: Cuantas frases recientes se recuerdan.
KEPT = 8
#: Desde que parecido una palabra oida es la misma que una dicha («erido» por «herido»).
_SIMILAR = 0.8
_MIN_FUZZY_LEN = 4

_NO_PALABRA = re.compile(r"[^a-z0-9ñ]+")


def _tokens(text: str) -> list[str]:
    plano = "".join(
        c
        for c in unicodedata.normalize("NFD", text.casefold().replace("ñ", "\0"))
        if not unicodedata.combining(c)
    ).replace("\0", "ñ")
    return [t for t in _NO_PALABRA.split(plano) if t]


@dataclass
class Said:
    """Una frase de la agente: lo que dice y cuando suena."""

    tokens: tuple[str, ...]
    starts_at: datetime
    #: Nulo mientras se sigue enviando: todavia no se sabe cuando termina de sonar.
    ends_at: datetime | None = None

    def sounding(self, at: datetime, *, tail: timedelta = timedelta(0)) -> bool:
        if at < self.starts_at - LEAD:
            return False
        return self.ends_at is None or at <= self.ends_at + tail


def _como_lo_dicho(oido: str, dichos: frozenset[str]) -> str:
    """La palabra dicha a la que suena esta, o ella misma si no suena a ninguna."""
    if oido in dichos or len(oido) < _MIN_FUZZY_LEN:
        return oido
    mejor, parecido = oido, _SIMILAR
    for dicho in dichos:
        actual = SequenceMatcher(None, oido, dicho, autojunk=False).ratio()
        if actual >= parecido:
            mejor, parecido = dicho, actual
    return mejor


@dataclass(frozen=True)
class _Oida:
    """Una palabra del transcrito, situada respecto a lo que suena."""

    tokens: tuple[str, ...]
    #: Cae mientras la agente suena, sin margen.
    sounding: bool
    #: Cae mientras suena o en el margen del final.
    near: bool


def _en_tramos(oidas: list[_Oida], dichos: list[str]) -> set[int]:
    """Las palabras oidas que forman, en orden, un tramo de la frase de la agente.

    Un tramo vale si tiene `MIN_RUN` palabras y **empieza** mientras la agente suena o en
    su margen; desde ahi puede seguir: la ultima palabra del eco cae a veces justo fuera.
    """
    vocabulario = frozenset(dichos)
    plano = [
        (_como_lo_dicho(token, vocabulario), i)
        for i, oida in enumerate(oidas)
        for token in oida.tokens
    ]
    bloques = SequenceMatcher(
        None, [token for token, _ in plano], dichos, autojunk=False
    ).get_matching_blocks()
    dentro: set[int] = set()
    for bloque in bloques:
        if bloque.size >= MIN_RUN and oidas[plano[bloque.a][1]].near:
            dentro.update(indice for _, indice in plano[bloque.a : bloque.a + bloque.size])
    return dentro


def echo_words(oidas: list[_Oida], dichos: list[str], ultimas: frozenset[str]) -> set[int]:
    """Los indices de las palabras oidas que son la voz de la agente. Vacio si ninguna.

    `dichos` es lo que la agente dijo hace poco, en orden; `ultimas`, las ultimas palabras
    de su frase mas reciente.
    """
    cerca = [i for i, oida in enumerate(oidas) if oida.near and oida.tokens]
    if not cerca:
        return set()
    vocabulario = frozenset(dichos)
    sonando = [i for i in cerca if oidas[i].sounding]
    tramos = _en_tramos(oidas, dichos)

    if len(cerca) > SHORT:
        # Una frase entera encima de la agente: o es mayormente la suya, o es la persona.
        if len(tramos.intersection(cerca)) / len(cerca) < MIN_SHARE:
            return set()
        es_eco = bool(tramos)
    else:
        en_la_frase = sum(
            1
            for i in sonando
            if any(_como_lo_dicho(token, vocabulario) in vocabulario for token in oidas[i].tokens)
        )
        es_eco = bool(tramos) or (bool(sonando) and en_la_frase * 2 >= len(sonando))

    quitar = set(tramos)
    if es_eco:
        # Mientras suena y lo oido es su frase, todo es suyo: tambien la palabra deformada.
        quitar.update(sonando)
    # En el margen del final solo cae el final de la frase.
    quitar.update(
        i
        for i in cerca
        if not oidas[i].sounding
        and all(_como_lo_dicho(token, ultimas) in ultimas for token in oidas[i].tokens)
    )
    return quitar


@dataclass
class OwnVoice:
    """Lo que la agente dijo hace poco, para quitarlo de lo que el reconocedor oye."""

    _said: deque[Said] = field(default_factory=lambda: deque(maxlen=KEPT), init=False)

    def begin(self, text: str, *, starts_at: datetime) -> Said:
        """Empieza a sonar una frase. Se cierra con `Said.ends_at` cuando se sabe."""
        dicho = Said(tokens=tuple(_tokens(text)), starts_at=starts_at)
        self._said.append(dicho)
        return dicho

    def cut(self, at: datetime) -> None:
        """El navegador vacio su cola: nada suena mas alla de `at`."""
        for dicho in self._said:
            if dicho.ends_at is None or dicho.ends_at > at:
                dicho.ends_at = at

    def sounding(self, at: datetime) -> bool:
        """Si a esa hora suena la agente (con el margen del final)."""
        return any(dicho.sounding(at, tail=TAIL) for dicho in self._said)

    def strip(
        self,
        transcript: Transcript,
        *,
        heard_at: datetime,
        stream_started_at: datetime | None,
    ) -> Transcript | None:
        """El transcrito sin la voz de la agente; `None` si no queda nada de la persona.

        Devuelve el mismo objeto cuando no hay nada que quitar.
        """
        if not self._said:
            return transcript
        con_tiempos = bool(transcript.words) and stream_started_at is not None
        if con_tiempos:
            assert stream_started_at is not None  # noqa: S101 -- lo dice `con_tiempos`
            textos = [str(palabra.text) for palabra in transcript.words]
            momentos = [
                stream_started_at + timedelta(seconds=palabra.start_s)
                for palabra in transcript.words
            ]
            cola = TAIL
        else:
            # Sin tiempos por palabra solo se sabe cuando llego el transcrito entero.
            textos = str(transcript.text).split()
            momentos = [heard_at] * len(textos)
            cola = TAIL_WITHOUT_TIMES
        oidas = [
            _Oida(
                tokens=tuple(_tokens(texto)),
                sounding=any(dicho.sounding(momento) for dicho in self._said),
                near=any(dicho.sounding(momento, tail=cola) for dicho in self._said),
            )
            for texto, momento in zip(textos, momentos, strict=True)
        ]
        cerca = [momento for momento, oida in zip(momentos, oidas, strict=True) if oida.near]
        if not cerca:
            return transcript
        recientes = [
            dicho
            for dicho in self._said
            if dicho.ends_at is None or min(cerca) <= dicho.ends_at + cola
        ]
        dichos = [token for dicho in recientes for token in dicho.tokens]
        ultimas = frozenset(recientes[-1].tokens[-LAST_WORDS:]) if recientes else frozenset()
        quitar = echo_words(oidas, dichos, ultimas)
        if not quitar:
            return transcript
        quedan = [i for i in range(len(oidas)) if i not in quitar]
        if not any(oidas[i].tokens for i in quedan):
            # Lo que queda es, como mucho, puntuacion suelta.
            return None
        return _solo(transcript, quedan, textos, con_tiempos=con_tiempos)


def _solo(
    transcript: Transcript, quedan: list[int], textos: list[str], *, con_tiempos: bool
) -> Transcript:
    """El transcrito con solo esas palabras, en su orden."""
    escritas = str(transcript.text).split()
    # El texto del reconocedor trae puntuacion que las palabras sueltas no: se conserva
    # cuando las dos listas casan una a una.
    fuente = escritas if len(escritas) == len(textos) else textos
    return Transcript(
        text=ExternalText(" ".join(fuente[i] for i in quedan)),
        is_final=transcript.is_final,
        words=tuple(transcript.words[i] for i in quedan) if con_tiempos else (),
        language=transcript.language,
    )


__all__ = [
    "KEPT",
    "LAST_WORDS",
    "LEAD",
    "MIN_RUN",
    "MIN_SHARE",
    "SHORT",
    "TAIL",
    "TAIL_WITHOUT_TIMES",
    "OwnVoice",
    "Said",
    "echo_words",
]
