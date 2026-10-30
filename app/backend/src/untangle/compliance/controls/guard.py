"""La guardia de salida sobre cada frase hacia el asegurado (BR1.1 a BR1.8).

Cada frase que va a salir --del modelo, del catalogo o de degradacion-- pasa por
aqui **antes** de ir a la sintesis o al chat, una por una y sin esperar el turno
completo (BR1.1). Lo que hace con ella:

1. La normaliza y le aplica los patrones de las siete categorias **de los dos
   idiomas** (BR1.2, BR1.3), mas la revelacion de configuracion que depende de
   la configuracion cargada: el identificador y el nombre de las **otras**
   aseguradoras y un numero de caso que no es el del caso en curso (BR1.7).
2. Sin coincidencia, la frase sale igual.
3. Con coincidencia, por cada categoria: si es la primera de esa categoria en el
   turno sale la frase permitida del catalogo; si no, la frase se descarta y el
   resto del turno sigue (BR1.4). La frase original nunca sale y nunca se
   guarda (BR1.6).
4. Si algo falla al evaluar, **falla cerrado**: la frase no sale, sale la de
   degradacion y queda una intervencion `not_evaluable` (BR1.5).

**Pura, salvo por el catalogo.** No abre ninguna conexion, no escribe en la base
y no emite eventos: devuelve un `GuardResult` con las intervenciones **sin
persistir**. Emitir el evento de traza y guardar la intervencion es del punto
unico de salida (U12), que sabe en que turno quedo la frase; la superficie de
`api.py` hace lo primero. Asi el corredor de evaluaciones la puede medir sin base
de datos, que es lo que mantiene vivo el camino del clon al reporte.

**Ningun modelo en la cadena.** La guardia es de reglas (FD-U10-1): un contrato
de importacion falla si este paquete llega a importar un proveedor.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from functools import lru_cache

from untangle.base import Frozen, Locale
from untangle.compliance.controls import phrases
from untangle.compliance.controls.models import (
    GuardCategory,
    InterventionAction,
    InterventionDraft,
)
from untangle.compliance.controls.normalization import normalize
from untangle.compliance.controls.patterns import PatternLibrary
from untangle.tenancy.models import TenantConfig

#: Los identificadores de los patrones que la guardia compone con la
#: configuracion cargada. No viven en ningun archivo porque su expresion depende
#: de que aseguradoras hay y de que caso esta en curso (BR1.7); el identificador
#: si es fijo, y es lo que se guarda en la intervencion.
OTHER_TENANT_ID_PATTERN = "guard.config.config_disclosure.other_tenant_id"
OTHER_TENANT_NAME_PATTERN = "guard.config.config_disclosure.other_tenant_name"
OTHER_CASE_NUMBER_PATTERN = "guard.config.config_disclosure.other_case_number"

#: La forma de un numero de caso tal como se dicta: las dos letras de la aseguradora,
#: guion y el contador (`ap-29`, FR1.5), ya normalizado. Cualquier numero con esta
#: forma que no sea el del caso en curso es de otro caso.
#:
#: **Con dos letras la forma sola atrapa de mas**: `cx-5` es un Mazda, y la guardia
#: taparia toda frase que nombrara el vehiculo. Por eso, cuando el contexto trae los
#: prefijos de las aseguradoras cargadas (`GuardContext.case_prefixes`), solo cuentan
#: esos; sin ellos --un contexto armado a mano-- se usa la forma general.
#:
#: **`POL-` no cae aqui por construccion**: la forma del numero de poliza (BR1.6 de U11)
#: lleva tres letras, y `\b` no deja que `ol-23` se lea dentro de `pol-23`. Hasta el
#: 2026-10-06 la guardia tomaba la poliza por un caso ajeno y tapaba toda frase en la
#: que la agente la nombrara --la lectura de la identidad, y la frase que confirma al
#: titular (P3)-- con "no puedo compartir esa informacion".
_GENERAL_CASE_NUMBER_SHAPE = re.compile(r"\b[a-z]{2}-[1-9]\d{0,5}\b")


@lru_cache(maxsize=8)
def case_number_shape(prefixes: tuple[str, ...]) -> re.Pattern[str]:
    """La forma de un numero de caso para esos prefijos, o la general si no hay ninguno."""
    if not prefixes:
        return _GENERAL_CASE_NUMBER_SHAPE
    alternativas = "|".join(re.escape(p.lower()) for p in prefixes)
    return re.compile(rf"\b(?:{alternativas})-[1-9]\d{{0,5}}\b")


@dataclass
class GuardTurn:
    """Lo que la guardia recuerda dentro de **un** turno (BR1.4).

    Las categorias que ya reemplazo: la segunda frase de la misma categoria en el
    mismo turno se descarta en vez de repetir la frase permitida. Quien emite el
    turno crea uno nuevo por turno; se comparte entre las frases de ese turno y
    solo entre ellas.
    """

    substituted: set[GuardCategory] = field(default_factory=set)


@dataclass(frozen=True)
class TenantIdentity:
    """Como se nombra una aseguradora: su identificador y su nombre visible."""

    tenant_id: str
    display_name: str


@dataclass(frozen=True)
class GuardContext:
    """Todo lo que la guardia necesita saber de la frase, salvo la frase."""

    #: El idioma del turno: el de la frase permitida que sale. Los patrones se
    #: aplican de los dos idiomas sea cual sea (BR1.3).
    language: Locale
    #: Las aseguradoras que **no** son la del turno, leidas de su configuracion
    #: (BR1.7). La propia no esta: la agente dice su nombre en la apertura.
    other_tenants: tuple[TenantIdentity, ...] = ()
    #: El numero legible del caso en curso, si ya hay caso. Cualquier otro numero
    #: con forma de numero de caso es de otro caso.
    case_number: str | None = None
    #: Los prefijos de numero de caso de **todas** las aseguradoras cargadas, la propia
    #: incluida. Vacio solo en un contexto armado a mano.
    case_prefixes: tuple[str, ...] = ()
    #: La clave del catalogo de la que salio la frase, cuando el aplicativo la
    #: compuso desde el catalogo. El modelo no puede traerla: es lo que hace
    #: segura la exencion de las plantillas aprobadas (BR1.8).
    source_key: str | None = None

    @classmethod
    def for_tenant(
        cls,
        tenant_id: str,
        *,
        language: Locale,
        tenants: Sequence[TenantConfig],
        case_number: str | None = None,
        source_key: str | None = None,
    ) -> GuardContext:
        """El contexto de una aseguradora, con las demas leidas de la configuracion."""
        otras = tuple(
            TenantIdentity(t.tenant_id, t.display_name) for t in tenants if t.tenant_id != tenant_id
        )
        return cls(
            language=language,
            other_tenants=otras,
            case_number=case_number,
            case_prefixes=tuple(sorted({t.case_number_prefix for t in tenants})),
            source_key=source_key,
        )


class GuardResult(Frozen):
    """Lo que devuelve la guardia por cada frase (`entities.md`, GuardResult)."""

    #: La frase original, las permitidas del catalogo, la de degradacion, o nada
    #: si la frase se descarto.
    text_out: str | None
    #: Las claves del catalogo de lo que salio en lugar de la frase, en orden.
    #: Vacia cuando la frase sale igual o se descarto.
    copy_keys: tuple[str, ...] = ()
    interventions: tuple[InterventionDraft, ...] = ()
    #: Falso solo cuando fallo la evaluacion (BR1.5).
    evaluated: bool = True

    @property
    def unchanged(self) -> bool:
        """La frase salio tal cual: evaluada y sin ninguna intervencion."""
        return self.evaluated and not self.interventions


def _palabra(texto: str) -> re.Pattern[str]:
    """Una expresion que encuentra `texto` normalizado como palabra entera."""
    partes = [re.escape(parte) for parte in normalize(texto).split(" ") if parte]
    return re.compile(r"\b" + r"\s+".join(partes) + r"\b")


def _revelacion_por_configuracion(texto: str, context: GuardContext) -> str | None:
    """El patron de revelacion que depende de la configuracion, o nada (BR1.7)."""
    for otra in context.other_tenants:
        if _palabra(otra.tenant_id).search(texto):
            return OTHER_TENANT_ID_PATTERN
        if _palabra(otra.display_name).search(texto):
            return OTHER_TENANT_NAME_PATTERN
    actual = normalize(context.case_number) if context.case_number else None
    for numero in case_number_shape(context.case_prefixes).findall(texto):
        if numero != actual:
            return OTHER_CASE_NUMBER_PATTERN
    return None


def detect_categories(
    text: str, *, library: PatternLibrary, context: GuardContext
) -> dict[GuardCategory, str]:
    """Las categorias que caen en la frase, con el primer patron de cada una.

    En el orden de `GuardCategory`, que es el de BR1.2, para que dos corridas
    nombren lo mismo en el mismo orden.
    """
    normalizado = normalize(text)
    eximida = context.source_key is not None and context.source_key in library.exempt_catalog_keys
    halladas: dict[GuardCategory, str] = {}
    for patron in library.guard:
        if patron.category is None or patron.category in halladas:
            continue
        if eximida and patron.category is GuardCategory.COVERAGE_PROMISE:
            continue
        if patron.regex.search(normalizado):
            halladas[patron.category] = patron.id
    if GuardCategory.CONFIG_DISCLOSURE not in halladas:
        dinamico = _revelacion_por_configuracion(normalizado, context)
        if dinamico is not None:
            halladas[GuardCategory.CONFIG_DISCLOSURE] = dinamico
    return {c: halladas[c] for c in GuardCategory if c in halladas}


def evaluate(
    text: str, *, library: PatternLibrary, context: GuardContext, turn: GuardTurn
) -> GuardResult:
    """Evalua una frase y decide que sale en su lugar (BR1.4). Actualiza el turno."""
    halladas = detect_categories(text, library=library, context=context)
    if not halladas:
        return GuardResult(text_out=text)

    frases: list[str] = []
    claves: list[str] = []
    intervenciones: list[InterventionDraft] = []
    for categoria, patron in halladas.items():
        if categoria in turn.substituted:
            intervenciones.append(
                InterventionDraft(
                    category=categoria,
                    pattern_id=patron,
                    action=InterventionAction.DROPPED,
                    catalog_key=None,
                )
            )
            continue
        clave = phrases.ALLOWED_KEYS[categoria]
        frases.append(phrases.allowed_text(categoria, locale=context.language))
        claves.append(clave)
        intervenciones.append(
            InterventionDraft(
                category=categoria,
                pattern_id=patron,
                action=InterventionAction.SUBSTITUTED,
                catalog_key=clave,
            )
        )
    # El turno se actualiza solo cuando ya se decidio todo: una frase que no se
    # pudo evaluar no deja una categoria marcada como usada.
    turn.substituted.update(halladas)
    return GuardResult(
        text_out=" ".join(frases) if frases else None,
        copy_keys=tuple(claves),
        interventions=tuple(intervenciones),
    )


def not_evaluable(*, language: Locale) -> GuardResult:
    """Lo que sale cuando la guardia no pudo evaluar: la degradacion (BR1.5)."""
    return GuardResult(
        text_out=phrases.degraded_text(locale=language),
        copy_keys=(phrases.GUARD_DEGRADED,),
        interventions=(
            InterventionDraft(
                category=None,
                pattern_id=None,
                action=InterventionAction.NOT_EVALUABLE,
                catalog_key=phrases.GUARD_DEGRADED,
            ),
        ),
        evaluated=False,
    )


def guard_sentence(
    text: str,
    *,
    context: GuardContext,
    turn: GuardTurn,
    library: PatternLibrary | Callable[[], PatternLibrary],
) -> tuple[GuardResult, Exception | None]:
    """La guardia entera, con su falla cerrada (BR1.5).

    Devuelve el resultado y, si fallo, **el error**: la frase no sale, sale la
    de degradacion, y quien llama decide como dejar rastro del fallo --la
    superficie de `api.py` lo emite como evento con su tipo--. Devolverlo en vez
    de tragarlo es lo que impide que un fallo cerrado sea tambien un fallo
    silencioso.

    `library` puede ser la biblioteca o quien la da: asi un fallo **al cargarla**
    tambien cae dentro de la falla cerrada, y no solo uno al aplicarla.
    """
    try:
        biblioteca = library() if callable(library) else library
        return evaluate(text, library=biblioteca, context=context, turn=turn), None
    except Exception as error:  # noqa: BLE001 -- falla cerrado por contrato (C-20, BR1.5): cualquier fallo al evaluar deja la frase dentro, y el error se devuelve para dejar rastro
        return not_evaluable(language=context.language), error
