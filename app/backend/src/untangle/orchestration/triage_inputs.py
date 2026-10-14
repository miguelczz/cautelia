"""Los insumos del motor de reglas que se **derivan** de lo capturado (PENDIENTES 1.8).

El vocabulario cerrado de `rules/fields.py` declara seis campos de triage y hasta
el 2026-10-03 no los producia nadie: cada caso caia en la regla por defecto
--revision estandar, la salida segura-- y la traza lo decia con un evento por
decision. De los seis, tres se derivan de lo que el caso ya tiene --los terceros con
datos pendientes, los heridos y el conductor que no figura en la poliza--, y los otros
tres no se derivan: el monto, la cobertura disputada y la sospecha de fraude los decide
un ajustador en la bandeja y los anota ahi (`inbox/triage_notes.py`).

Este modulo tiene los que se derivan. Son **funciones puras**: reciben lo que el
caso guarda --sus filas de partes, el estado de un bloque y, para los bloques
que se dicen con palabras, el texto que la persona dijo-- y devuelven el valor del
campo, sin leer la base y sin reloj. Esa es
la misma razon que la normalizacion de la captura escribe para estar en codigo y
no en el modelo (FD-U11-2): dos corridas del mismo commit tienen que decidir lo
mismo, y una decision que dependiera de un modelo dejaria de ser reproducible.

**Un campo que no se puede derivar no se inventa: no se escribe.** Un campo
ausente no dispara (BR2.1 de U9), que es exactamente lo correcto; un campo escrito
en `False` por no saber afirma que se comprobo y no se cumple, y eso es una regla
que no dispara **diciendo** que miro.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from untangle.case_record.models import CaseParty, FieldStatus, PartyRole
from untangle.compliance.controls.normalization import fold

__all__ = [
    "DRIVER_FIELD",
    "INJURIES_FIELD",
    "OTHER_PARTIES_FIELD",
    "injuries_present",
    "other_parties_data_pending",
    "unlisted_driver",
]

#: La clave del bloque de terceros en el esquema del caso (`schema/fields.yaml`).
#: Vive aqui, junto a la unica funcion que la necesita, y no en la raiz de
#: composicion: una clave de esquema suelta en el cableado es una que nadie
#: relaciona con su razon el dia que el esquema cambie.
OTHER_PARTIES_FIELD = "other_parties"


def _a_una_persona(parte: CaseParty) -> bool:
    """Un tercero del que no se sabe como se llama o como ubicarlo.

    `CaseParty` ya dice que un atributo que no se sabe queda vacio y **es un dato
    pendiente, nunca un valor supuesto** (BR1.8, AC1.8.2). Lo que este modulo
    anade es cual de esos atributos cuenta segun lo que la parte es.
    """
    return parte.name is None or parte.contact is None


def _a_un_vehiculo(parte: CaseParty) -> bool:
    # La placa se mira por su **estado** y no por si el valor esta: `NOT_STATED`
    # es "nadie la dijo", que es justo el dato pendiente, y distinguirlo de un
    # valor ausente es la razon de que `FieldStatus` tenga tres estados.
    return parte.plate_status is FieldStatus.NOT_STATED or not parte.vehicle_description


#: Quien cuenta como tercero **y** que dato le falta, en una sola tabla. Las dos
#: cosas juntas a proposito: separar "quien es un tercero" de "que se le mira"
#: deja dos guardias para la misma regla, y entonces meter un rol en la primera no
#: cambia nada mientras no este en la segunda --que es exactamente como una prueba
#: deja de poder distinguir--. Un rol que no esta aqui no cuenta, y quitarlo o
#: ponerlo tiene efecto inmediato.
#:
#: `REPORTER` no esta: el texto que ve el ajustador habla de "los terceros
#: involucrados", y quien llama **por** alguien no esta involucrado en el
#: accidente. Un familiar que reporta sin dejar su telefono no manda el caso a
#: revision.
#:
#: Y no hay una sola lista de atributos para todos: un vehiculo no tiene telefono
#: y una persona no tiene placa, asi que "le falta algun atributo" seria cierto
#: para cualquiera y la regla disparia siempre.
_DATOS_PENDIENTES: dict[PartyRole, Callable[[CaseParty], bool]] = {
    PartyRole.OTHER_DRIVER: _a_una_persona,
    PartyRole.WITNESS: _a_una_persona,
    PartyRole.INJURED: _a_una_persona,
    PartyRole.OTHER_VEHICLE: _a_un_vehiculo,
}


def other_parties_data_pending(
    parties: tuple[CaseParty, ...], *, block_status: FieldStatus, value: str | None = None
) -> bool | None:
    """Si algun tercero tiene datos pendientes, o `None` si **no se puede afirmar nada**.

    `block_status` es el estado del campo `other_parties` del caso y `value`, lo que la
    persona dijo en el. Son tres situaciones y no dos, que es la misma distincion que el
    proyecto ya hace entre "no hay clausula que lo cubra" y "no pude verificar", y entre
    `EMPTY` y `NOT_EVALUATED` en la evidencia de cierre:

    - **nadie pregunto** (`NOT_STATED`): `None`. No hay nada que afirmar. El campo
      queda ausente y su regla no dispara, que es lo correcto: una regla ausente
      manda a revision estandar, la salida segura.
    - **hay filas de terceros** (otro conductor, otro vehiculo, testigo, lesionado):
      cierto si a alguno le falta algo.
    - **se pregunto y no hay filas**: `False` **solo si lo dicho es una negacion clara**
      --«ninguno», «nadie mas», «no hubo otros vehiculos», "none"-- de una lista
      cerrada; es lo que deja cerrar directo un choque de un solo vehiculo, que es lo que
      la primera regla de Sunmeadow exige. Cualquier otra cosa --«me choco un taxi y se
      fue», «no se», un texto que no se puede leer, ningun texto-- es `None`: el insumo
      queda ausente y el caso va a revision estandar. Que el bloque se haya dicho no
      prueba que no hubiera terceros: la persona puede haberlos nombrado sin que nadie
      llegara a registrarles una fila, y cerrar ese caso sin ajustador es el error caro.

    Colapsar "nadie pregunto" con "no habia" en `False` cerraria directo un caso cuyos
    terceros nadie llego a capturar, afirmando que se comprobo algo que nunca se
    pregunto. Colapsar "no habia" en `None` dejaria sin cierre directo a todo caso sin
    terceros, que es el camino que esa regla existe para abrir.

    El valor dicho es dato personal: aqui solo se lee, y no se emite ni se guarda.
    """
    if block_status is FieldStatus.NOT_STATED:
        return None
    terceros = [parte for parte in parties if parte.role in _DATOS_PENDIENTES]
    if terceros:
        return any(_DATOS_PENDIENTES[parte.role](parte) for parte in terceros)
    if value is not None and _niega_a_los_terceros(value):
        return False
    return None


# --- Heridos ---------------------------------------------------------------------------

#: La clave del campo de heridos en el esquema del caso (`schema/fields.yaml`).
INJURIES_FIELD = "injuries"

_DICHO = frozenset({FieldStatus.STATED, FieldStatus.CONFIRMED})

# El vocabulario de abajo esta plegado (minusculas, sin tildes) y es **cerrado**: ver
# `injuries_present` para saber por que una palabra que no esta aqui nunca produce un falso.

#: Palabras que niegan. «ni» y «sin» tambien: «sin heridos», «ni un rasguno».
_NEGADORES = frozenset(
    {"no", "nadie", "ninguno", "ninguna", "ningun", "ningunos", "ningunas", "sin", "ni", "nada"}
    | {"cero", "0", "zero", "nobody", "none", "nope", "nothing", "without"}
)

#: Las que niegan **a todos**, no solo a quien escribe: anclan una negacion que no nombra heridos.
_NEGADORES_DE_TODOS = frozenset(
    {"nadie", "ninguno", "ninguna", "ningun", "ningunos", "ningunas", "nobody", "none"}
)

#: Negaciones que no se pueden leer sin mas («not hurt» niega al reves de lo que parece).
#: Solo sirven para impedir que la frase cuente como una afirmacion de dano.
_NEGACIONES_OPACAS = frozenset(
    {"tampoco", "nunca", "jamas", "not", "never", "nor", "neither", "cannot", "cant", "wont"}
    | {"dont", "didnt", "doesnt", "wasnt", "werent", "isnt", "arent", "hasnt", "havent"}
)

#: Lesion o muerte de una persona. Negadas («no hubo heridos») son parte de la negacion;
#: sin negar («hubo heridos») son la afirmacion.
_HERIDOS = frozenset(
    {"herido", "heridos", "herida", "heridas", "lesion", "lesiones", "lesionado", "lesionados"}
    | {"lesionada", "lesionadas", "lastimado", "lastimados", "lastimada", "lastimadas"}
    | {"lastimo", "lastimaron", "lastime", "lastimamos", "lesiono", "lesionaron", "hirio"}
    | {"hirieron", "golpeo", "golpearon", "rasguno", "rasgunos", "muerto", "muertos", "muerta"}
    | {"muertas", "muerte", "muertes", "fallecido", "fallecidos", "fallecida", "fallecidas"}
    | {"victima", "victimas", "injured", "injury", "injuries", "hurt", "harmed", "wounded"}
    | {"dead", "killed", "died", "death", "deaths", "casualty", "casualties", "victim"}
    | {"victims", "fatality", "fatalities", "scratch", "scratches"}
)

#: Palabras de enlace que no dicen nada del estado de las personas.
_APOYO = frozenset(
    {"el", "la", "los", "las", "un", "una", "uno", "unos", "unas", "de", "del", "en", "a"}
    | {"al", "que", "hubo", "hay", "haya", "habia", "hubiera", "hubieron", "salio", "salieron"}
    | {"resulto", "resultaron", "quedo", "quedaron", "fue", "fueron", "esta", "estan"}
    | {"estaba", "estaban", "estuvo", "estuvieron", "tuvo", "tuvieron", "ocurrio", "persona"}
    | {"personas", "gente", "alguien", "ocupante", "ocupantes", "pasajero", "pasajeros"}
    | {"conductor", "conductores", "the", "an", "of", "in", "to", "was", "were", "is", "are"}
    | {"got", "get", "gets", "had", "has", "have", "there", "theres", "any", "anyone"}
    | {"anybody", "one", "person", "people", "passenger", "passengers", "occupant"}
    | {"occupants", "driver", "drivers"}
)

#: Agradecimientos y matices que no afirman ni niegan nada.
_RELLENO = frozenset(
    {"gracias", "dios", "afortunadamente", "felizmente", "suerte", "por", "solo", "solamente"}
    | {"unicamente", "apenas", "bendito", "thank", "thanks", "god", "thankfully", "luckily"}
    | {"fortunately", "lucky", "just", "only"}
)

#: Cosas de las que se habla en vez de las personas. Valen en una frase suelta («solo danos
#: materiales») pero **no dentro de una negacion**: «sin danos materiales» niega el carro.
_OBJETOS = frozenset(
    {"dano", "danos", "material", "materiales", "carro", "carros", "auto", "autos", "vehiculo"}
    | {"vehiculos", "choque", "accidente", "susto", "damage", "property", "car", "cars"}
    | {"vehicle", "vehicles", "accident", "crash", "scare"}
)

_AFIRMACIONES = frozenset({"si", "sii", "yes", "yeah", "yep", "yup", "afirmativo"})

#: Dano a una persona dicho con otras palabras: dolor, sangre, huesos, atencion medica o una
#: parte del cuerpo. Ancho a proposito: equivocarse hacia «verdadero» manda el caso a un
#: ajustador, que es el lado seguro.
_DANO = re.compile(
    r"\b(?:dolor\w*|duel\w+|adolorid\w+|sangr\w+|fractur\w+|hueso\w*|esguince\w*|latigazo|"
    r"conmocion\w*|contusion\w*|trauma\w*|desmay\w+|inconscien\w+|quemadur\w+|ambulancia\w*|"
    r"hospital\w*|clinica|urgencias|paramedic\w+|medic[oa]s?|enfermer[oa]s?|cirugia|cabeza|"
    r"cuello|brazos?|piernas?|pecho|espalda|rodillas?|costillas?|cadera|hombros?|tobillos?|"
    r"munecas?|dedos?|abdomen|nuca|dientes?|nariz|ojos?|columna|cervical\w*|pain\w*|"
    r"ach(?:e|es|ing)|bleed\w*|blood|bled|broke\w*|bones?|sprain\w*|whiplash|concussion\w*|"
    r"bruis\w+|unconscious\w*|faint\w*|burn(?:s|ed|t)?|clinic|doctors?|nurses?|surgery|"
    r"emergency room|head|neck|arms?|legs?|chest|knees?|ribs?|hips?|shoulders?|ankles?|"
    r"wrists?|fingers?|nose|teeth|tooth|eyes?|spine|stomach)\b"
)

#: Donde se parte la respuesta en clausulas: la puntuacion y las conjunciones que contraponen.
#: «y» no parte: «no hubo heridos y todo bien» es una sola negacion.
_SEPARADORES = re.compile(
    r"[,;.:!?¡¿()\[\]\"/\\\n-]+|\b(?:pero|aunque|sino|excepto|salvo|menos|but|however|although"
    r"|though|except|yet)\b"
)


class _Clausula(StrEnum):
    VACIA = "vacia"
    AFIRMA = "afirma"
    DANO = "dano"
    NIEGA = "niega"
    NEUTRA = "neutra"
    DESCONOCIDA = "desconocida"


def _normalizar(valor: str) -> str:
    texto = fold(valor).replace("'", "")
    texto = re.sub(r"\bno one\b", "nobody", texto)
    texto = re.sub(r"\bdanos? personal(?:es)?\b", "lesionados", texto)
    texto = re.sub(r"\bse (?:hizo|hicieron) dano\b", "lastimo", texto)
    # «nadie se lastimo»: el «se» es el reflexivo de la lesion, no una palabra suelta.
    return re.sub(r"\bse (?=(?:lastim|lesion|hiri)\w*|golpeo\b|golpearon\b)", "", texto)


def _clasificar(tokens: list[str]) -> _Clausula:
    if not tokens:
        return _Clausula.VACIA
    palabras = set(tokens)
    negada = bool(palabras & (_NEGADORES | _NEGACIONES_OPACAS))
    if not negada and palabras <= _AFIRMACIONES:
        return _Clausula.AFIRMA
    if not negada and (_DANO.search(" ".join(tokens)) or palabras & _HERIDOS):
        return _Clausula.DANO
    if negada:
        # Una palabra de dano dentro de una negacion («no me duele nada») no esta en
        # `permitidas`, asi que la clausula queda desconocida sin una rama aparte.
        # Ancla: la negacion es de heridos, de todos, o no tiene objeto («no», «no, gracias»).
        ancla = bool(
            palabras & _HERIDOS
            or palabras & _NEGADORES_DE_TODOS
            or palabras <= (_NEGADORES | _RELLENO)
        )
        permitidas = _NEGADORES | _HERIDOS | _APOYO | _RELLENO
        return _Clausula.NIEGA if palabras <= permitidas and ancla else _Clausula.DESCONOCIDA
    if palabras <= (_APOYO | _RELLENO | _OBJETOS):
        return _Clausula.NEUTRA
    return _Clausula.DESCONOCIDA


def injuries_present(
    value: str | None, *, status: FieldStatus, parties: tuple[CaseParty, ...] = ()
) -> bool | None:
    """Si el caso dice que hubo alguien herido: `True`, `False`, o `None` si no se sabe.

    Lee el campo `injuries` del caso, que lo anota el modelo que lleva la conversacion
    («no» si nadie se lastimo; «si» y lo que dijo si alguien) o, cuando el modelo falla, la
    extraccion por reglas con las palabras de la persona. El valor puede ser cualquiera de las
    dos formas, y por eso esta funcion lee **texto** y no un si/no.

    El error caro es devolver `False` cuando hubo heridos: el caso cerraria directo sin
    ajustador. Por eso las dos salidas no son simetricas:

    - **`False` solo sale de una lista cerrada.** Cada palabra de la respuesta tiene que ser
      una que niega o una de enlace («no», «nadie se lastimo», «sin heridos», «gracias a
      Dios»), y al menos una niega. Una palabra que no esta en la lista --«creo», «grave»,
      «mi hijo», «estoy»-- impide el `False` sin que haga falta prever la frase. Lo que se
      pueda decir de mas formas de las que alguien escribio queda `None`, que es seguro:
      sin el insumo ninguna regla de cierre dispara y el caso va a revision estandar.
    - **`True` sale de cualquier mencion de dano a una persona** fuera de una negacion limpia
      --herido, lesion, dolor, una parte del cuerpo, atencion medica-- o de un «si» a secas.
      Equivocarse hacia `True` deriva el caso a un ajustador.

    La respuesta se parte en clausulas (puntuacion y «pero»), porque «no, pero mi hijo se
    golpeo la cabeza» niega en una y afirma en otra, y gana la afirmacion. «Nada grave», «no
    creo», «creo que no», «no se» y «estamos bien» son `None`: no dicen que nadie se lastimo.
    Un «si» seguido de una negacion se contradice y tambien es `None`.

    `parties` es la otra fuente: un tercero registrado como lesionado dice que hubo heridos
    aunque el campo diga que no.

    Un campo que nadie dijo (`NOT_STATED`) no tiene nada que leer: `None`. La funcion no emite
    ni guarda nada: el valor es dato personal y aqui solo se lee.
    """
    if any(parte.role is PartyRole.INJURED for parte in parties):
        return True
    if status not in _DICHO or value is None:
        return None
    clausulas = [
        _clasificar(clausula.split()) for clausula in _SEPARADORES.split(_normalizar(value))
    ]
    clausulas = [c for c in clausulas if c is not _Clausula.VACIA]
    if _Clausula.DANO in clausulas:
        return True
    if clausulas and clausulas[0] is _Clausula.AFIRMA:
        return None if _Clausula.NIEGA in clausulas else True
    if _Clausula.NIEGA in clausulas and all(
        c in (_Clausula.NIEGA, _Clausula.NEUTRA) for c in clausulas
    ):
        return False
    return None


# --- Terceros: quien dice que no hubo otros ---------------------------------------------
#
# Misma tecnica que los heridos y mismo vocabulario de negaciones: `False` solo sale de una
# lista cerrada, y una palabra que no esta en ella impide el `False` sin que haga falta
# prever la frase. Lo que cambia es el apoyo: aqui se niega a **otros vehiculos y otras
# personas**, asi que los nombres de cosas (vehiculo, carro, persona, tercero) valen, pero
# solo dentro de una clausula que niega. Sin articulos a proposito: «no, el otro conductor»
# es una frase que nombra a un tercero, y «el» no esta en la lista para que no pase por una
# negacion.

#: Palabras de enlace que no dicen nada de los terceros por si solas.
_CONECTORES_DE_TERCEROS = frozenset(
    {"hubo", "hay", "haya", "habia", "hubieron", "habian", "mas", "de", "en", "que", "habido"}
    | {"there", "were", "was", "is", "are", "any", "at", "all", "else", "involved", "been"}
    | {"anyone", "anybody", "one"}
)

#: Las cosas que se niegan: otros vehiculos, otras personas. Solo cuentan en una clausula que
#: niega; «no, otros vehiculos» no es una negacion, es una frase que se contradice.
_NOMBRES_DE_TERCEROS = frozenset(
    {"otro", "otros", "otra", "otras", "vehiculo", "vehiculos", "carro", "carros", "auto"}
    | {"autos", "coche", "coches", "persona", "personas", "gente", "tercero", "terceros"}
    | {"tercera", "terceras", "involucrado", "involucrados", "involucrada", "involucradas"}
    | {"conductor", "conductores", "parte", "partes", "moto", "motos", "peaton", "peatones"}
    | {"other", "others", "another", "vehicle", "vehicles", "car", "cars", "person", "people"}
    | {"party", "parties", "third", "driver", "drivers", "motorcycle", "pedestrian"}
    | {"pedestrians"}
)

#: «Solo yo» / "just me": nadie mas, dicho sin ninguna palabra que niegue. Se reescribe a la
#: forma que si niega antes de clasificar. «Solo yo choque» queda con «choque» fuera de la
#: lista y no pasa: la reescritura no relaja nada, solo nombra una forma corriente.
_SOLO_YO = re.compile(
    r"\b(?:solo|solamente|unicamente)\s+(?:yo|nosotros|mi\s+(?:carro|auto|coche|vehiculo)"
    r"|el\s+mio|el\s+nuestro)\b"
)
_JUST_ME = re.compile(r"\b(?:just|only)\s+(?:me|us|my\s+(?:car|vehicle)|ours|mine)\b")


def _niega_a_los_terceros(valor: str) -> bool:
    """Si lo dicho niega, con claridad y de una lista cerrada, que hubiera otros involucrados.

    Cada clausula (la respuesta se parte por puntuacion y por «pero») tiene que ser una de
    dos: o niega --todas sus palabras son de negacion, de enlace, de relleno o nombres de
    terceros, y al menos una niega-- o es neutra --solo enlace y relleno («gracias»)--. Y al
    menos una niega. Una palabra fuera de la lista (un verbo, un articulo, «taxi», «se fue»)
    deja el texto sin leer: no es un `False`.
    """
    texto = _JUST_ME.sub("nobody else", _SOLO_YO.sub("nadie mas", _normalizar(valor)))
    clausulas = [set(clausula.split()) for clausula in _SEPARADORES.split(texto)]
    niega_alguna = False
    neutra = _CONECTORES_DE_TERCEROS | _RELLENO
    for palabras in clausulas:
        if not palabras or palabras <= neutra:
            continue
        if not palabras & _NEGADORES or not palabras <= (
            _NEGADORES | _CONECTORES_DE_TERCEROS | _NOMBRES_DE_TERCEROS | _RELLENO
        ):
            return False
        niega_alguna = True
    return niega_alguna


# --- Conductor que no figura en la poliza -----------------------------------------------
#
# Quien conducia lo guarda el caso como **texto libre** en `vehicle_and_driver` ("el carro y
# quien manejaba"): no hay un campo con el nombre del conductor, y la derivacion lo lee de las
# palabras. Eso fija el criterio entero. Comparar un nombre sacado de una frase con los
# conductores de la poliza es lo mas fragil de este modulo, y el error caro es decir que el
# conductor **figura** cuando no figura (la regla no dispara y nadie lo mira). Por eso, igual
# que en heridos y terceros, cada salida tiene su vocabulario cerrado y lo que no entra en el
# queda ausente, que es la salida segura.

#: La clave del campo del vehiculo y el conductor en el esquema del caso (`schema/fields.yaml`).
DRIVER_FIELD = "vehicle_and_driver"

#: Verbos de conducir, plegados (sin tildes ni mayusculas). Los activos admiten al conductor
#: antes o despues ("Carlos conducia", "conducia Carlos"); los pasivos solo despues, con "por" o
#: "by" ("conducido por Carlos", "driven by Carlos").
_VERBOS_ACTIVOS = frozenset(
    {"conducia", "conducian", "conducio", "condujo", "conduciendo", "conduce", "manejaba"}
    | {"manejaban", "manejando", "maneja", "manejo", "driving", "drove", "drives"}
)
_VERBOS_PASIVOS = frozenset({"conducido", "conducida", "manejado", "manejada", "driven"})
_VERBOS = _VERBOS_ACTIVOS | _VERBOS_PASIVOS

#: Parentescos y tratamientos: lo unico que puede ir entre el verbo y el nombre ("manejaba mi
#: hijo Carlos Ruiz") y lo que presenta a un nombre dicho antes del verbo ("mi hermano Carlos
#: Ruiz iba manejando").
_PARENTESCOS = frozenset(
    {"hijo", "hija", "esposo", "esposa", "marido", "mujer", "hermano", "hermana", "papa", "mama"}
    | {"padre", "madre", "primo", "prima", "tio", "tia", "sobrino", "sobrina", "yerno", "nuera"}
    | {"cunado", "cunada", "suegro", "suegra", "novio", "novia", "amigo", "amiga", "vecino"}
    | {"vecina", "companero", "companera", "empleado", "empleada", "chofer", "senor", "senora"}
    | {"don", "dona", "son", "daughter", "husband", "wife", "brother", "sister", "father"}
    | {"mother", "dad", "mom", "cousin", "uncle", "aunt", "nephew", "niece", "friend", "neighbor"}
    | {"neighbour", "coworker", "boyfriend", "girlfriend", "employee", "mr", "mrs", "ms", "dr"}
)
#: Las palabras que presentan a un nombre: un parentesco, o "por" / "by" / "llamado" / "named".
_PRESENTADORES = _PARENTESCOS | frozenset({"por", "by", "llamado", "llamada", "named", "called"})
#: Lo que puede ir entre el verbo y el presentador sin decir nada del conductor.
_RELLENO_DESPUES = frozenset(
    {"mi", "mis", "su", "sus", "nuestro", "nuestra", "my", "his", "her", "our", "el", "la", "un"}
    | {"una", "a", "an", "the", "era", "fue", "es", "was", "is", "quien", "que", "who", "lo"}
)
#: Lo que puede ir entre el nombre y el verbo ("Carlos Ruiz iba manejando"). Sin «lo» ni «la»:
#: «Chevrolet Spark lo manejaba mi hijo» no dice que Chevrolet Spark sea una persona.
_RELLENO_ANTES = frozenset(
    {"iba", "estaba", "era", "fue", "was", "were", "had", "been", "quien", "who"}
)
#: Palabras que abren una frase o enlazan, y que nunca son parte de un nombre aunque lleven
#: mayuscula: "Lo manejaba Carlos" no tiene un nombre que empiece en "Lo".
_NO_SON_NOMBRE = (
    _VERBOS
    | _PRESENTADORES
    | _RELLENO_DESPUES
    | _RELLENO_ANTES
    | frozenset({"yo", "tu", "usted", "ella", "ellos", "ellas", "nosotros", "i", "he", "she"})
    | frozenset({"they", "we", "you", "it", "si", "sii", "yes", "hola", "hello", "gracias"})
    | frozenset({"thanks", "se", "no"})
)
#: Particulas que van dentro de un nombre ("Maria de los Angeles Perez").
_PARTICULAS = frozenset({"de", "del", "la", "las", "los"})

#: Dudas que quitan la certeza: con cualquiera, el conductor no se afirma ni se niega.
_DUDAS = frozenset(
    {"creo", "pienso", "supongo", "parece", "parecia", "quiza", "quizas", "posiblemente"}
    | {"probablemente", "maybe", "perhaps", "probably", "possibly", "guess", "think", "believe"}
    | {"seems", "apparently", "dudo"}
)
#: Lo que quita la certeza de lo que se dijo: una negacion (la de heridos, que ya es cerrada) o
#: una duda. «No manejaba Carlos Ruiz» no dice que Carlos Ruiz conducia.
_QUITAN_LA_CERTEZA = _NEGADORES | _NEGACIONES_OPACAS | _DUDAS

#: Lo que el sistema escribe cuando la persona confirma que conducia el titular: la frase del
#: catalogo (`intake.policy.confirmed_vehicle`), plegada. Una prueba compara esta forma con el
#: catalogo en los dos idiomas, para que cambiar la frase sin cambiar esta linea no deje la
#: derivacion ciega sin que nada se ponga rojo.
_CONDUJO_EL_TITULAR = re.compile(
    r"(?:^|[,.;:]\s*)(?:conducia el titular|driven by the policyholder)\s*\.?\s*$"
)
_MENCIONA_AL_TITULAR = re.compile(r"conducia el titular|driven by the policyholder")

#: Una pieza del texto: una palabra (con sus guiones y apostrofos), un numero o un signo.
_APOSTROFOS = "'" + chr(0x2019)
_PIEZA = re.compile(rf"[^\W\d_]+(?:[{_APOSTROFOS}\-][^\W\d_]+)*|\d+|[^\w\s]")

#: Cuantas palabras puede tener un nombre completo: mas de eso es una frase, no un nombre.
_MAXIMO_DE_PALABRAS = 5


class _Clase(StrEnum):
    PALABRA = "palabra"
    NUMERO = "numero"
    SIGNO = "signo"


@dataclass(frozen=True, slots=True)
class _Pieza:
    """Una pieza del texto: lo que dijo la persona y su forma plegada, para comparar."""

    raw: str
    clase: _Clase
    plain: str

    def es_de(self, vocabulario: frozenset[str]) -> bool:
        return self.clase is _Clase.PALABRA and self.plain in vocabulario

    def es_de_un_nombre(self) -> bool:
        """Una palabra con mayuscula que no es de las que abren frase ni de enlace."""
        return (
            self.clase is _Clase.PALABRA
            and self.raw[0].isupper()
            and len(self.plain) >= 2
            and self.plain not in _NO_SON_NOMBRE
        )


def _pieza(raw: str) -> _Pieza:
    if raw[0].isalpha():
        return _Pieza(raw, _Clase.PALABRA, fold(raw).replace("'", "").replace("-", ""))
    return _Pieza(raw, _Clase.NUMERO if raw[0].isdigit() else _Clase.SIGNO, raw)


def _piezas(texto: str) -> list[_Pieza]:
    return [_pieza(m.group(0)) for m in _PIEZA.finditer(texto)]


def _palabras_del_nombre(texto: str) -> tuple[str, ...]:
    """Las palabras plegadas de un nombre, sin las particulas ("de", "del", "la"...)."""
    return tuple(
        p.plain for p in _piezas(texto) if p.clase is _Clase.PALABRA and p.plain not in _PARTICULAS
    )


def _corrida_hacia_adelante(piezas: list[_Pieza], inicio: int) -> tuple[str, ...]:
    """Las palabras con mayuscula seguidas desde `inicio`.

    Las une solo si estan separadas por espacios: una coma, un punto o un numero la cortan. Una
    particula cuenta solo entre dos palabras del nombre ("Maria de los Angeles Perez").
    """
    palabras: list[str] = []
    i = inicio
    while i < len(piezas):
        if piezas[i].es_de_un_nombre():
            palabras.append(piezas[i].plain)
            i += 1
            continue
        j = i
        while j < len(piezas) and piezas[j].es_de(_PARTICULAS):
            j += 1
        if j > i and palabras and j < len(piezas) and piezas[j].es_de_un_nombre():
            i = j
            continue
        break
    return tuple(palabras)


def _corrida_hacia_atras(piezas: list[_Pieza], fin: int) -> tuple[tuple[str, ...], int]:
    """Las palabras con mayuscula seguidas que terminan en `fin`, y donde empieza la corrida."""
    palabras: list[str] = []
    i = fin
    while i >= 0:
        if piezas[i].es_de_un_nombre():
            palabras.append(piezas[i].plain)
            i -= 1
            continue
        j = i
        while j >= 0 and piezas[j].es_de(_PARTICULAS):
            j -= 1
        if j < i and palabras and j >= 0 and piezas[j].es_de_un_nombre():
            i = j
            continue
        break
    return tuple(reversed(palabras)), i + 1


def _nombre_despues_del_verbo(piezas: list[_Pieza], verbo: int) -> tuple[str, ...] | None:
    """«manejaba Carlos Ruiz», «iba manejando mi hermano Carlos Ruiz», «driven by Carlos Ruiz».

    Entre el verbo y el nombre solo cabe relleno que termine en un presentador, o nada.
    """
    j, presentado = verbo + 1, True
    while j < len(piezas) and piezas[j].es_de(_RELLENO_DESPUES | _PRESENTADORES):
        presentado = piezas[j].plain in _PRESENTADORES
        j += 1
    if presentado and j < len(piezas) and piezas[j].es_de_un_nombre():
        return _corrida_hacia_adelante(piezas, j)
    return None


def _nombre_antes_del_verbo(piezas: list[_Pieza], verbo: int) -> tuple[str, ...] | None:
    """«Carlos Ruiz iba manejando», «my husband Carlos Ruiz was driving».

    El nombre va pegado al verbo salvo un «iba» o un «was», y empieza despues de un presentador,
    de un signo o del inicio del texto. «Mi Renault Logan manejaba...» no entra: «mi» no
    presenta a una persona.
    """
    k = verbo - 1
    while k >= 0 and piezas[k].es_de(_RELLENO_ANTES):
        k -= 1
    if k < 0 or not piezas[k].es_de_un_nombre():
        return None
    palabras, inicio = _corrida_hacia_atras(piezas, k)
    if inicio == 0 or piezas[inicio - 1].clase is _Clase.SIGNO:
        return palabras
    return palabras if piezas[inicio - 1].es_de(_PARENTESCOS) else None


def _nombres_dichos(piezas: list[_Pieza]) -> set[tuple[str, ...]]:
    """Los nombres que el texto pone junto a un verbo de conducir, cada uno con sus palabras.

    Un nombre cuenta solo si esta **pegado** al verbo; una palabra con mayuscula suelta es el
    carro mas veces que una persona.
    """
    hallados: set[tuple[str, ...]] = set()
    for i, pieza in enumerate(piezas):
        if not pieza.es_de(_VERBOS):
            continue
        despues = _nombre_despues_del_verbo(piezas, i)
        if despues is not None:
            hallados.add(despues)
        if pieza.plain in _VERBOS_ACTIVOS:
            antes = _nombre_antes_del_verbo(piezas, i)
            if antes is not None:
                hallados.add(antes)
    return hallados


def _a_una_letra(a: str, b: str) -> bool:
    """Si dos palabras son la misma o difieren en una sola letra (cambiada, puesta o quitada).

    Solo para palabras de cuatro letras o mas: «Ana» y «Ani» pueden ser dos personas, y «Mario» y
    «Maria» tambien lo son, pero la duda entre ellas es justo la que se deja ausente.
    """
    if a == b:
        return True
    if min(len(a), len(b)) < 4 or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b, strict=True)) == 1
    corta, larga = sorted((a, b), key=len)
    return any(larga[:i] + larga[i + 1 :] == corta for i in range(len(larga)))


def _comparar_con_la_poliza(
    nombre: tuple[str, ...], declarados: list[tuple[str, ...]]
) -> bool | None:
    """`False` si el nombre es el de un conductor declarado, `True` si con claridad no lo es.

    **El mismo nombre** son las mismas palabras plegadas --minusculas, sin tildes, sin
    particulas-- en cualquier orden, y al menos dos. Nada mas: ni un apellido de menos, ni solo
    el nombre de pila, ni una letra distinta. Cuanto mas se afloja, mas cerca se esta de decir
    que figura cuando no figura.

    **Distinto con claridad** es un nombre completo --dos palabras o mas-- cuya primera palabra
    (el nombre de pila, en los dos idiomas) no es ninguna palabra de ningun conductor declarado
    ni difiere de una en una sola letra. Compartir los apellidos del titular no hace parecido a
    un hijo: lo que lo distingue es su nombre de pila. El orden apellido-nombre cae del lado
    seguro, porque su primera palabra es un apellido que casi siempre esta en la poliza.

    Todo lo demas --un nombre incompleto, un nombre de pila que se repite, una letra de
    diferencia-- es ausente.
    """
    if len(nombre) < 2 or len(nombre) > _MAXIMO_DE_PALABRAS:
        return None
    if any(len(d) >= 2 and frozenset(d) == frozenset(nombre) for d in declarados):
        return False
    conocidas = {palabra for d in declarados for palabra in d}
    if any(_a_una_letra(nombre[0], palabra) for palabra in conocidas):
        return None
    return True


def _frase_del_titular(plegado: str) -> tuple[bool, bool | None]:
    """Si el texto trae la frase del sistema para el titular, y que dice de quien conducia.

    `(False, None)` si no la trae. `(True, False)` si es lo ultimo del texto y nada la
    contradice: conducia el titular, que la poliza siempre declara. `(True, None)` si la trae
    pero el texto cuenta otra version --otro verbo de conducir antes, o algo dicho despues--: era
    lo que se guardaba antes de que el conductor dicho reemplazara a la frase del sistema, y un
    texto que dice las dos cosas no se lee a favor de ninguna.
    """
    final = _CONDUJO_EL_TITULAR.search(plegado)
    if final is not None:
        antes = _piezas(plegado[: final.start()])
        return True, (None if any(p.es_de(_VERBOS) for p in antes) else False)
    return _MENCIONA_AL_TITULAR.search(plegado) is not None, None


def unlisted_driver(
    value: str | None, *, status: FieldStatus, declared_drivers: tuple[str, ...]
) -> bool | None:
    """Si quien conducia no figura en la poliza: `True`, `False`, o `None` si no se sabe.

    `value` es el campo `vehicle_and_driver` del caso, abierto solo para leerlo, y
    `declared_drivers` los nombres que la poliza del caso declara (el titular primero). Vacio es
    «el caso no tiene poliza identificada» o «la poliza no declara conductores»: en los dos, no
    hay contra que comparar y el resultado es `None`.

    Tres salidas, y la tercera es la que vale:

    - **`False` (figura)** cuando el caso dice que conducia el titular con las palabras que el
      sistema escribe al confirmarlo (`intake.policy.confirmed_vehicle`), o cuando la persona
      nombra con nombre completo a un conductor que la poliza declara. El titular siempre esta
      declarado.
    - **`True` (no figura)** cuando la persona nombra a quien conducia con nombre y apellido y
      ese nombre es distinto con claridad de todos los declarados (ver `_comparar_con_la_poliza`).
    - **`None` en todo lo demas**: «manejaba mi hijo» sin nombre, un solo nombre de pila, un
      nombre incompleto, una negacion («no manejaba Carlos»), una duda («creo que...»), dos
      nombres distintos, o un texto que no se puede leer. El insumo queda ausente y la regla
      del conductor no dispara, igual que antes de este campo.

    El error caro es devolver `False` cuando no figura: la regla no dispara y nadie lo mira. Por
    eso `False` es la salida mas estrecha, y por eso un nombre solo cuenta si esta **pegado a un
    verbo de conducir**. Equivocarse hacia `True` manda el caso a un ajustador, que es el lado
    seguro.

    El valor es dato personal: aqui solo se lee, y no se emite ni se guarda.
    """
    declarados = [d for d in (_palabras_del_nombre(n) for n in declared_drivers) if d]
    piezas = _piezas(value or "")
    if (
        status not in _DICHO
        or value is None
        or not value.strip()
        or not declarados
        or any(p.es_de(_QUITAN_LA_CERTEZA) for p in piezas)
    ):
        return None

    mencionada, del_titular = _frase_del_titular(fold(value))
    if mencionada:
        return del_titular

    nombres = _nombres_dichos(piezas)
    if len(nombres) != 1:
        return None
    return _comparar_con_la_poliza(next(iter(nombres)), declarados)
