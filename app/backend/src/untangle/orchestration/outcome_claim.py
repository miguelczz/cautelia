"""Lo que solo el codigo puede decir de un reporte: que quedo hecho, o que un ajustador lo revisa.

Visto en una llamada simulada (2026-10-13): con el lugar del choque todavia sin decir, la
persona dijo «No, asi esta bien, eso es todo, gracias» y el modelo contesto «Ya quedo anotado tu
reporte; un ajustador lo revisara con tu poliza». Es falso --el caso seguia tomando datos y no
llega a ningun ajustador-- y la persona se iba creyendo que su reporte estaba hecho. Lo que le pasa
a un reporte al terminar (queda registrado, o lo revisa un ajustador) lo dice **solo el codigo**,
con frases fijas, cuando de verdad paso (`closing_outcome`); el modelo no lo sabe ni puede
prometerlo.

Este modulo es esa comprobacion: una funcion pura sobre el texto, sin modelo ni base. Quien decide
**cuando** aplicarla es el turno (`turn._texto_del_turno`: solo mientras la captura sigue abierta);
el juez por codigo de las evaluaciones (`evals.understanding_probes`) usa esta misma funcion, para
que el aplicativo y la medicion lean lo mismo.

## Que se considera una afirmacion

Una oracion que **afirma**, como hecho o como promesa, una de dos cosas:

1. que el reporte --o el caso, la solicitud, la consulta-- *quedo* registrado, anotado, guardado,
   enviado, completo, listo o cerrado («ya quedo anotado tu reporte», «tu caso esta completo», «ya
   registre tu solicitud», «todo quedo guardado», «ya terminamos»);
2. que un ajustador lo *revisa, revisara o tiene* («un ajustador lo revisara», «lo tiene un
   ajustador», «sera revisado por un ajustador», «ya pase tu caso a un ajustador»).

## Lo que deja pasar, con su razon

- **Una pregunta.** «¿Quieres que un ajustador lo revise?» no afirma nada.
- **Una oferta o una condicion que va antes**: «si prefieres, paso tu caso a un ajustador»,
  «cuando me digas el lugar, tu reporte quedara registrado». Ofrecer pasar el caso es una frase
  legitima del producto; lo que no puede hacer la agente es darlo por hecho.
- **Una negacion pegada**: «tu reporte aun no esta completo», «todavia no queda registrado».
- **Un dato anotado**: «anote el lugar», «quedo anotado el lugar del accidente», «ya lo anote».
  La afirmacion necesita **el reporte** (o el caso, la solicitud...) como sujeto o complemento, o un
  «todo» que lo abarque; un dato suelto no lo es.
- **Lo que solo se acerca**: «queda casi completo», «va muy bien», «falta el lugar».
- **Lo que explica sin prometer**: «un ajustador confirma si aplica y por cuanto».

## Lo que marca de mas, y se acepta

Una oracion con la afirmacion y una pregunta pegada con coma en ingles («Your report is saved,
anything else?») queda exenta por la pregunta. Y «el ajustador revisa cada caso con la poliza»,
dicho en general, se marca igual que dicho de este caso. En los dos casos lo que sale es la frase
del catalogo, que es correcta, y el costo es una respuesta mas seca; el otro error --dejar salir la
promesa falsa-- es el que se paga con la confianza de quien se va creyendo que su reporte esta
hecho.

## El vocabulario

Es una tabla cerrada por idioma, abajo, y se busca en **los dos idiomas** sea cual sea el de la
conversacion: una afirmacion falsa lo es en el idioma que sea, y un idioma equivocado se descarta
aparte (`turn._en_el_otro_idioma`). Se compara plegado --minusculas y sin tildes--, salvo el «si»
condicional contra el «si» afirmativo, que sin tilde son la misma palabra y se separan antes de
plegar. Se amplia con su prueba delante, nunca adivinando: una entrada demasiado ancha convierte
una respuesta natural en una frase de contestadora.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from untangle.compliance.controls.normalization import fold

# --- El vocabulario: una tabla por idioma --------------------------------------------------


@dataclass(frozen=True)
class _Vocabulary:
    """Lo que se busca en un idioma. Todo plegado: minusculas y sin tildes."""

    #: Las afirmaciones: cada una es una expresion que, completa, dice que el reporte quedo hecho o
    #: que un ajustador lo revisa.
    claims: tuple[re.Pattern[str], ...]
    #: Lo que, dicho **antes** de la afirmacion en la misma oracion, la vuelve oferta o condicion.
    frames: re.Pattern[str]
    #: Lo que, pegado a la afirmacion, la niega.
    negators: re.Pattern[str]


def _compile(*patrones: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(patron) for patron in patrones)


# Espanol. «caso», «consulta» y «solicitud» son cosas que se registran; «el caso» (con articulo)
# no es «en ese caso» ni «en caso de»: sin «ese» y sin coma entre el sustantivo y el verbo.
_ES_COSA = r"(?:reporte|caso|solicitud|consulta|siniestro|reclamo|reclamacion|denuncia|informe)"
_ES_DET = r"(?:tu|su|el|la|mi|nuestro)"
_ES_ESTADO = (
    r"(?:registrad|anotad|guardad|enviad|completad|terminad|radicad|cerrad|hech|complet|list)[oa]s?"
)
_ES_AJUSTADOR = r"ajustador(?:es|a|as)?"
_ES_VERBO_ANOTAR = (
    r"(?:anote|anotamos|registre|registramos|guarde|guardamos|envie|enviamos|radique|radicamos"
    r"|cerre|cerramos|complete|completamos|termine|terminamos)"
)

_ES = _Vocabulary(
    claims=_compile(
        # «tu reporte quedo registrado», «el caso ya esta completo»
        rf"\b{_ES_DET}\s+{_ES_COSA}\b[^.!?;:,]{{0,25}}?\b(?:quedo|queda|quedara|ha\s+quedado|esta|fue|sera)"
        rf"\s+(?:ya\s+|todo\s+)?{_ES_ESTADO}\b",
        # «ya quedo anotado tu reporte»
        rf"\b(?:quedo|queda|quedara|ha\s+quedado|esta)\s+(?:ya\s+|todo\s+)?{_ES_ESTADO}"
        rf"\s+{_ES_DET}\s+{_ES_COSA}\b",
        # «ya registre tu solicitud», «anotamos tu caso» (no «el numero de caso»)
        rf"\b{_ES_VERBO_ANOTAR}\s+(?:ya\s+)?(?:todo\s+)?{_ES_DET}\s+{_ES_COSA}\b",
        rf"\bhe\s+(?:anotado|registrado|guardado|enviado|completado|terminado|radicado|cerrado)"
        rf"\s+(?:todo\s+)?{_ES_DET}\s+{_ES_COSA}\b",
        # «todo quedo guardado», «ya quedo todo», «ya terminamos», «ya tengo todo lo que necesito»
        rf"\btodo\s+(?:ya\s+)?(?:quedo|queda|esta)\s+{_ES_ESTADO}\b",
        rf"\b(?:quedo|queda|esta)\s+(?:ya\s+)?todo\s+{_ES_ESTADO}\b",
        r"\bya\s+(?:esta|quedo)\s+todo\b",
        r"\bya\s+(?:terminamos|acabamos)\b(?!\s+con\b)",
        r"\bya\s+tengo\s+todo\s+(?:lo\s+que\s+)?(?:necesito|hace\s+falta)\b",
        # «un ajustador lo revisara», «el ajustador te contactara»
        rf"\b(?:un|el|nuestro|tu)\s+{_ES_AJUSTADOR}\s+(?:(?:lo|la|los|las|le|les|te|nos|se)\s+)?"
        r"(?:revisara|revisa|vera|tomara|atendera|evaluara|analizara|contactara|llamara|escribira"
        r"|se\s+encargara|se\s+pondra\s+en\s+contacto|podra\s+revisar\w*|esta\s+revisando"
        r"|estara\s+revisando|va\s+a\s+(?:revisar|ver|tomar|atender|evaluar|analizar|contactar"
        r"|llamar|encargarse))\b",
        # «lo revisara un ajustador», «ya lo tiene un ajustador»
        rf"\b(?:lo|la|los|las)\s+(?:va\s+a\s+)?(?:revisar|revisara|revisa|tomara|atendera|vera"
        rf"|tiene|evaluara|analizara)\s+(?:un|el|nuestro)\s+{_ES_AJUSTADOR}\b",
        # «sera revisado por un ajustador»
        rf"\b(?:sera|va\s+a\s+ser|esta\s+siendo|fue)\s+(?:revisad|atendid|evaluad|analizad|tomad)"
        rf"[oa]s?\s+por\s+(?:un|el)\s+{_ES_AJUSTADOR}\b",
        # «queda con un ajustador», «esta en manos de un ajustador»
        rf"\b(?:esta|queda|quedo|sigue|estara)\s+(?:ya\s+)?(?:con|en\s+manos\s+de|a\s+cargo\s+de"
        rf"|en\s+revision\s+(?:de|por|con))\s+(?:un|el)\s+{_ES_AJUSTADOR}\b",
        # «pase tu caso a un ajustador», «ya lo derive con un ajustador»
        rf"\b(?:pase|derive|envie|mande|transferi|traslade|escale|reenvie|remiti)\b[^.!?;:,]{{0,30}}?"
        rf"\b(?:a|con)\s+(?:un|el)\s+{_ES_AJUSTADOR}\b",
    ),
    frames=re.compile(
        r"\b(?:si|cuando|una\s+vez|en\s+cuanto|apenas|luego\s+de|despues\s+de|para\s+que|antes\s+de"
        r"|hasta\s+que|mientras|por\s+si|en\s+caso\s+de|puedo|podria|podriamos|podemos|quieres"
        r"|quiere|prefieres|prefiere|te\s+gustaria|le\s+gustaria|deseas|desea)\b"
    ),
    negators=re.compile(r"\b(?:no|ni|nunca|tampoco|jamas)\b"),
)

# Ingles.
_EN_THING = r"(?:report|case|claim|request|inquiry|submission)"
_EN_DET = r"(?:your|the|this)"
_EN_STATE = (
    r"(?:saved|recorded|logged|submitted|filed|registered|sent|noted|complete|completed|finished"
    r"|done|ready|closed)"
)
_EN_ADJUSTER = r"adjusters?"

_EN = _Vocabulary(
    claims=_compile(
        # «your report is saved», «the case has been submitted», «your report's complete»
        rf"\b{_EN_DET}\s+{_EN_THING}\b[^.!?;:,]{{0,25}}?(?:'s|\s+(?:is|was|has\s+been|will\s+be|got|gets))"
        rf"\s+(?:now\s+|all\s+|already\s+)?{_EN_STATE}\b",
        # «I've recorded your report» (not «the case number»)
        r"\b(?:i|we)(?:'ve|\s+have)?\s+(?:already\s+)?(?:saved|recorded|logged|submitted|filed"
        rf"|registered|sent|completed|finished|noted(?:\s+down)?)\s+(?:all\s+of\s+)?{_EN_DET}\s+"
        rf"{_EN_THING}\b(?!\s+(?:number|id|details?|information|info|data))",
        # «everything is saved», «you're all set», «that completes your report»
        r"\b(?:everything|all)\s+(?:is|has\s+been|was|got)\s+(?:now\s+)?(?:saved|recorded|logged"
        r"|noted|registered|submitted|done|complete|completed|set)\b",
        r"\b(?:you(?:'re|\s+are)|we(?:'re|\s+are))\s+(?:all\s+)?(?:set|done|finished)\b(?!\s+with)",
        rf"\bthat\s+(?:completes|finishes|wraps\s+up)\s+(?:your|the)\s+{_EN_THING}\b",
        r"\b(?:i|we)\s+(?:now\s+)?have\s+(?:everything|all)\s+(?:i|we)\s+need\b",
        # «an adjuster will review it», «the adjuster is reviewing it»
        rf"\b(?:an?|the|our|your)\s+{_EN_ADJUSTER}(?:\s+will|\s+is\s+going\s+to|'ll)\s+"
        r"(?:be\s+in\s+touch|be\s+reviewing|review|look|take|contact|reach|handle|follow|go\s+over"
        r"|check|evaluate|assess|call|get\s+in\s+touch|get\s+back)\b",
        rf"\b(?:an?|the|our)\s+{_EN_ADJUSTER}\s+(?:is|has|was)\s+(?:now\s+)?(?:reviewing|reviewed"
        r"|looking|taken|taking|handling)\b",
        rf"\b(?:reviewed|handled|evaluated|looked\s+at|taken\s+over)\s+by\s+(?:an?|the|our)\s+{_EN_ADJUSTER}\b",
        rf"\b(?:is|are|remains?|now)\s+(?:now\s+)?(?:with|in\s+the\s+hands\s+of|under\s+review\s+by)"
        rf"\s+(?:an?|the|our)\s+{_EN_ADJUSTER}\b",
        # «I've passed your case to an adjuster»
        r"\b(?:passed|sent|forwarded|handed|referred|escalated|routed|transferred)\b[^.!?;:,]{0,30}?"
        rf"\bto\s+(?:an?|the|our)\s+{_EN_ADJUSTER}\b",
    ),
    frames=re.compile(
        r"\b(?:if|when|once|after|before|until|unless|so\s+that|in\s+case|would\s+you|do\s+you"
        r"|shall\s+i|can\s+i|could\s+i|i\s+can|i\s+could|we\s+can|want\s+me|happy\s+to)\b"
    ),
    negators=re.compile(r"\b(?:not|never|no|neither)\b|n't\b"),
)

_VOCABULARIOS: tuple[_Vocabulary, ...] = (_ES, _EN)

# --- Lo que se hace con el texto -----------------------------------------------------------

#: Donde acaba una oracion: un punto, un cierre de pregunta o admiracion, un punto y coma, un
#: salto de linea, o el «¿» que abre otra --«Ya quedo anotado, ¿algo mas?» son dos oraciones, y la
#: pregunta no cubre a la afirmacion--.
_FIN_DE_ORACION = re.compile(r"(?<=[.!?…])\s+|[;\n]+|(?=¿)")

#: Donde acaba una clausula dentro de la oracion: la negacion solo cuenta si esta en la misma
#: clausula que la afirmacion («No te preocupes, ya quedo anotado» no la niega).
_FIN_DE_CLAUSULA = re.compile(r"[,:;()\-—]")

#: El «si» afirmativo lleva tilde y el condicional no; plegar las tildes los vuelve una palabra. Se
#: separa antes de plegar.
_SI_AFIRMATIVO = re.compile(r"\bsí\b", re.IGNORECASE)


def _plegar(oracion: str) -> str:
    return fold(_SI_AFIRMATIVO.sub("sii", oracion))


def _afirma(oracion: str, vocabulario: _Vocabulary) -> bool:
    plegada = _plegar(oracion)
    for patron in vocabulario.claims:
        for coincidencia in patron.finditer(plegada):
            antes = plegada[: coincidencia.start()]
            if vocabulario.frames.search(antes):
                continue
            inicio_de_clausula = max((m.end() for m in _FIN_DE_CLAUSULA.finditer(antes)), default=0)
            pegado = plegada[inicio_de_clausula : coincidencia.end()]
            if vocabulario.negators.search(pegado):
                continue
            return True
    return False


def find_claim(text: str | None) -> str | None:
    """La primera oracion de `text` que afirma que el reporte quedo hecho o que lo revisa un
    ajustador (ver el docstring del modulo), tal como se escribio; `None` si ninguna lo afirma.

    Es lo que usa el juez por codigo de las evaluaciones para decir **que** afirmo la respuesta.
    """
    for oracion in _FIN_DE_ORACION.split(text or ""):
        if "?" in oracion:
            continue
        if any(_afirma(oracion, vocabulario) for vocabulario in _VOCABULARIOS):
            return oracion.strip()
    return None


def claims_outcome(text: str | None) -> bool:
    """Si `text` afirma que el reporte quedo hecho o que un ajustador lo revisa."""
    return find_claim(text) is not None


__all__ = ["claims_outcome", "find_claim"]
