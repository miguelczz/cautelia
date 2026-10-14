"""La carpeta versionada `app/config/providers/`: quien cobra, cuanto y con que tope.

Dos archivos y no uno, porque cambian con cadencias distintas y porque uno de
los dos lleva su propia version: `providers.yaml` dice **con que** se habla --los
modelos anclados, el plan de cada uso, los numeros del cortacircuitos y los
limites de la voz-- y `prices.yaml` dice **cuanto cuesta** y **que lo detiene**
del lado del proveedor. Mezclarlos obligaria a versionar la tabla de precios
cada vez que se toca un tiempo de espera.

Es la pieza mas baja del modulo: **no depende de ninguna otra**. Si dependiera de
la fabrica de clientes, validar la configuracion exigiria una clave de proveedor,
y arrancar sin clave dejaria de poder decir que archivo esta roto.

Lo que este modulo no hace, a proposito:

- **No lee variables de entorno.** Las claves se leen en `settings.py`, que es el
  unico punto que lo hace (SEC-U1.2). Aqui no hay ni un nombre de variable: un
  archivo versionado que nombrara claves seria el primer paso para que alguna
  acabe dentro.
- **No comprueba la vigencia de los topes.** Esa medicion es contra la fecha de
  hoy, ningun esquema la expresa y una configuracion no puede caducar sola
  mientras esta en disco: vive en `workspace/schema_check.py`, que es lo que
  corre el guion de verificacion.
"""

from __future__ import annotations

from datetime import date, tzinfo
from enum import StrEnum
from pathlib import Path
from typing import Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import Field, ValidationError, model_validator

from untangle import paths
from untangle.base import Frozen, Locale, ProviderName, UnitKind, Use
from untangle.telemetry.spend.models import PriceEntry, UsdAmount

#: Los dos archivos de la carpeta.
PROVIDERS_FILE = "providers.yaml"
PRICES_FILE = "prices.yaml"

#: Los segmentos que delatan un alias **movil**: un identificador que el
#: proveedor puede reapuntar a otro modelo sin avisar (BR1.4). Anclamos por
#: identificador exacto porque un alias movido convierte dos corridas del mismo
#: commit en dos corridas de modelos distintos, y con ello la linea base de
#: evaluaciones deja de comparar nada.
#:
#: La lista esta versionada aqui y crece cuando aparezca una forma nueva. Es
#: deliberadamente una lista de segmentos y no una expresion regular: lo que se
#: prohibe se lee en un diff.
MOVING_ALIAS_SEGMENTS: frozenset[str] = frozenset(
    {"latest", "stable", "preview", "experimental", "exp"}
)


class ProviderConfigError(ValueError):
    """Un archivo de la carpeta de proveedores no vale.

    El mensaje nombra el archivo y la clave rota. Falla al arrancar y no cuando
    se hace la primera llamada: descubrir a mitad de una corrida que el modelo
    estaba mal declarado cuesta la cuota que ya se gasto.
    """


# --- Lo que declara `providers.yaml` ------------------------------------------


class ModelKind(StrEnum):
    """Que sabe hacer un modelo declarado.

    Los dos ultimos los llena U15 `speech-providers`. Estan aqui porque el
    esquema del archivo es de esta unidad y U15 lo hereda sin cambiarlo.
    """

    GENERATION = "generation"
    EMBEDDING = "embedding"
    TRANSCRIPTION = "transcription"
    SYNTHESIS = "synthesis"


class ModelRef(Frozen):
    """Un modelo o una voz, anclado por identificador exacto (BR1.4)."""

    id: str = Field(min_length=1)
    kind: ModelKind
    #: Solo para embeddings: el vector se trunca a esta dimension y se normaliza.
    #: Va en configuracion y no en el codigo porque cambiarla invalida el indice
    #: entero, y eso tiene que verse en un diff.
    dimensions: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _el_identificador_no_es_un_alias_movil(self) -> Self:
        _rechazar_alias_movil(self.id)
        return self

    @model_validator(mode="after")
    def _solo_los_embeddings_tienen_dimension(self) -> Self:
        if self.kind is ModelKind.EMBEDDING and self.dimensions is None:
            msg = f"el modelo de embeddings '{self.id}' tiene que declarar su dimension"
            raise ValueError(msg)
        if self.kind is not ModelKind.EMBEDDING and self.dimensions is not None:
            msg = f"'{self.id}' no es de embeddings y no lleva dimension de vector"
            raise ValueError(msg)
        return self


def _rechazar_alias_movil(identificador: str) -> None:
    """Falla si el identificador delata un alias movil (BR1.4). Lo comparten
    modelos y voces: una voz reapuntable moveria lo que se oye igual que un
    modelo reapuntable mueve lo que se responde."""
    segmentos = set(identificador.replace(".", "-").split("-"))
    movil = sorted(segmentos & MOVING_ALIAS_SEGMENTS)
    if movil:
        msg = (
            f"'{identificador}' parece un alias movil por el segmento '{movil[0]}': el "
            "proveedor puede reapuntarlo a otro modelo sin avisar. Declare el "
            "identificador exacto de la version que se quiere anclar"
        )
        raise ValueError(msg)


class VoiceEntry(Frozen):
    """Una voz del proveedor que el proyecto **comprobo que existe** (U15, BR2.2).

    Es la lista contra la que se valida la configuracion de voz de cada
    aseguradora al arrancar: una voz que no esta aqui apaga la voz de esa
    aseguradora con su motivo. Se comprueba contra el proveedor de verdad con
    `mise run voice:contract-live`, que pregunta a su lista de voces --una
    llamada que no cuesta--; arrancar no pregunta a nadie, porque el proceso y
    el chat no pueden depender de que un proveedor de voz conteste.
    """

    id: str = Field(min_length=1)
    #: El modelo con el que se sintetiza esta voz. Tiene que estar declarado en
    #: `models` del mismo proveedor, con tipo `synthesis`.
    model: str = Field(min_length=1)
    #: Los idiomas en los que el proyecto la usa. Catalina habla los dos con la
    #: misma identidad (experimento 4); una voz de Aura-2 habla uno solo.
    languages: tuple[Locale, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _la_voz_no_es_un_alias_movil(self) -> Self:
        _rechazar_alias_movil(self.id)
        return self


class ProviderEntry(Frozen):
    """Un proveedor, los modelos suyos que el proyecto ancla y las voces que usa."""

    name: ProviderName
    models: tuple[ModelRef, ...] = Field(min_length=1)
    #: Solo los proveedores de sintesis declaran voces (U15). Vacio por omision:
    #: Gemini no tiene ninguna, y la clave llega opcional como toda clave nueva.
    voices: tuple[VoiceEntry, ...] = ()

    @model_validator(mode="after")
    def _ningun_identificador_repetido(self) -> Self:
        vistos = [modelo.id for modelo in self.models]
        if len(set(vistos)) != len(vistos):
            msg = f"'{self.name}' declara dos veces el mismo identificador de modelo"
            raise ValueError(msg)
        voces = [voz.id for voz in self.voices]
        if len(set(voces)) != len(voces):
            msg = f"'{self.name}' declara dos veces la misma voz"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _cada_voz_usa_un_modelo_de_sintesis_declarado(self) -> Self:
        for voz in self.voices:
            if not self.has_model(voz.model, kind=ModelKind.SYNTHESIS):
                msg = (
                    f"la voz '{voz.id}' de '{self.name}' usa el modelo '{voz.model}', que "
                    "este proveedor no declara como modelo de sintesis"
                )
                raise ValueError(msg)
        return self

    def has_model(self, model_id: str, *, kind: ModelKind | None = None) -> bool:
        return any(
            modelo.id == model_id and (kind is None or modelo.kind is kind)
            for modelo in self.models
        )

    def voice(self, voice_id: str) -> VoiceEntry | None:
        for voz in self.voices:
            if voz.id == voice_id:
                return voz
        return None


class Plan(StrEnum):
    """El plan contratado para un uso.

    Decide si la llamada se factura de verdad, y con eso si suma contra el techo
    (BR3.6, BR4.2). El precio de lista se registra en los dos casos.
    """

    FREE = "free"
    PAID = "paid"


class UseConfig(Frozen):
    """Para que se llama, a quien, con que modelo y bajo que plan (BR1.3, BR3.6)."""

    use: Use
    provider: ProviderName
    model: str = Field(min_length=1)
    plan: Plan
    #: Se escribe aparte en vez de derivarse del plan **y se comprueba contra
    #: el**: es la columna de la que depende el techo, y que el archivo la diga
    #: en voz alta es lo que permite leer en un diff el dia que un uso pasa a
    #: pagarse.
    billable: bool
    #: Los dos tiempos maximos hacia el proveedor, **por uso** y no globales: los
    #: usos tienen paciencias distintas y el turno de voz no puede esperar lo que
    #: una corrida de evaluaciones si (`nfr-design/performance-design.md`). No
    #: llevan valor por defecto a proposito: un tiempo maximo que el archivo no
    #: escribe es un tiempo maximo que nadie decidio, y este es el archivo que se
    #: lee cuando hay que explicar por que se corto una llamada.
    connect_timeout_ms: int = Field(ge=1)
    read_timeout_ms: int = Field(ge=1)

    @model_validator(mode="after")
    def _la_marca_concuerda_con_el_plan(self) -> Self:
        esperado = self.plan is Plan.PAID
        if self.billable is not esperado:
            msg = (
                f"el uso '{self.use}' declara plan '{self.plan}' y billable="
                f"{self.billable}: un plan gratuito no factura y uno de pago si "
                "(BR3.6). Corrija el que este mal, no los dos"
            )
            raise ValueError(msg)
        return self


class CircuitBreakerConfig(Frozen):
    """Los numeros del cortacircuitos, uno por pareja (proveedor, uso).

    Viven en configuracion y no en el codigo para poder cambiarlos sin un
    despliegue de logica. Lo que **no** vive aqui es que tipos de error cuentan:
    `invalid_response` no abre el circuito porque es un problema del contenido y
    no de la salud del proveedor, y contarlo abriria el circuito por un prompt
    mal hecho. Eso es una decision de diseno, no un ajuste.
    """

    failure_threshold: int = Field(ge=1)
    open_seconds: int = Field(ge=1)
    half_open_probes: int = Field(ge=1)


class VoiceLimits(Frozen):
    """Los limites del enlace publico de voz (FR3.9).

    Ninguno lleva valor por defecto a proposito: un limite que el archivo no
    escribe es un limite que nadie decidio, y este es el archivo que se revisa
    cuando hay que explicar por que se rechazo una llamada.
    """

    max_call_seconds: int = Field(ge=1)
    calls_per_visitor_per_day: int = Field(ge=0)
    #: El tope del cupo diario del sitio. El cupo real se **deriva** cada dia del
    #: presupuesto que queda y los dias que faltan (BR5.6); esto es solo el techo
    #: que ese calculo no puede pasar.
    site_daily_cap: int = Field(ge=0)

    @model_validator(mode="after")
    def _el_tope_del_sitio_no_es_menor_que_el_de_una_conexion(self) -> Self:
        """Un tope del sitio por debajo del de una conexion es un error de archivo.

        Quedaria alcanzado antes que el de la conexion y la frase que ve la persona
        nombraria el carril equivocado: le diria que el sitio esta ocupado cuando lo
        que se acabo es su propia llamada del dia.

        **Vive aqui y no en la decision** (U17, tanda 2): lo que la decision compara
        es el **cupo de hoy**, que se deriva del presupuesto y puede bajar hasta cero
        con todo el archivo bien escrito. Un cupo de cero no es una configuracion
        rota: es que hoy no caben mas llamadas, y eso se responde como carril
        agotado, no como archivo invalido.
        """
        if self.site_daily_cap < self.calls_per_visitor_per_day:
            msg = (
                f"'site_daily_cap' ({self.site_daily_cap}) no puede ser menor que "
                f"'calls_per_visitor_per_day' ({self.calls_per_visitor_per_day}): el "
                "carril del sitio quedaria alcanzado antes y la frase nombraria el "
                "carril equivocado"
            )
            raise ValueError(msg)
        return self


class ChatLimits(Frozen):
    """Los limites del chat publico (FR4.6, RT-13).

    No protegen el presupuesto --el chat corre en plan gratuito y no suma contra
    el techo (BR3.6, BR4.2)-- sino contra el **abuso** y contra la cuota del
    propio plan gratuito, que es compartida y se agota para todos los visitantes
    a la vez.

    Son un **valor de arranque**: U13 `chat` los confirma con sus propios
    criterios cuando construya la superficie que los aplica. Dejarlos sin
    declarar hasta entonces significaria publicar el chat sin limite, que es lo
    que la regla del proyecto prohibe.
    """

    #: Treinta. Una captura completa de los siete campos son diez a veinte
    #: turnos, asi que treinta dejan explorar sin obligar a abrir otra sesion.
    messages_per_session: int = Field(ge=1)
    #: Sesenta, que son dos conversaciones completas en un dia.
    messages_per_day: int = Field(ge=1)


class RecordingReserve(Frozen):
    """La reserva de grabacion, declarada en **minutos** y no en dolares.

    En dolares envejeceria mal: el precio por minuto de la voz lo fija el
    experimento 1, y el dia que se mida la reserva cubriria otra cantidad de
    minutos sin que nadie lo hubiera decidido. En minutos, la pregunta que
    importa --"alcanza para grabar el video?"-- se responde sin calculadora, y la
    conversion a dolares sale de la misma tabla de precios que todo lo demas.
    """

    minutes: int = Field(ge=0)


class ProviderModelRef(Frozen):
    """Un proveedor y un modelo, nombrados para pedirle su precio a la tabla."""

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)


class SynthesisReserve(Frozen):
    """La sintesis de una llamada, en los dos modos, y cuanto habla la agente.

    Los dos modos se declaran juntos porque **la diferencia entre ellos es la
    razon por la que el modo existe**: la voz de respaldo cuesta menos por
    caracter, asi que con el presupuesto justo el enlace publico sigue vivo con
    ella en vez de cerrarse.
    """

    primary: ProviderModelRef
    fallback: ProviderModelRef
    characters: int = Field(ge=0)


class ModelReserve(Frozen):
    """Los tokens que una llamada le pide al modelo, de ida y de vuelta."""

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class CallReserveSpec(Frozen):
    """Lo que **se supone** que consume una llamada publica de duracion maxima.

    No es un precio: es el consumo. Los precios salen de `prices.yaml` y esto dice
    cuantas unidades de cada uno se gastan, que es una suposicion del proyecto y
    por eso vive en configuracion versionada con su razon escrita al lado.

    Los segundos de audio no estan aqui: son `voice_limits.max_call_seconds`.
    Declararlos otra vez seria la misma duracion en dos sitios, y el dia que
    cambiara uno el otro seguiria diciendo lo de antes.
    """

    transcription: ProviderModelRef
    synthesis: SynthesisReserve
    model: ModelReserve


class ProvidersConfig(Frozen):
    """El archivo `providers.yaml` entero, ya validado."""

    config_version: int = Field(ge=1)
    providers: tuple[ProviderEntry, ...] = Field(min_length=1)
    uses: tuple[UseConfig, ...] = Field(min_length=1)
    circuit_breaker: CircuitBreakerConfig
    voice_limits: VoiceLimits
    chat_limits: ChatLimits
    recording_reserve: RecordingReserve
    #: Lo que consume una llamada publica, por componente (U17, tanda 2).
    call_reserve: CallReserveSpec
    #: La zona en la que se cierra el dia de una cuota diaria (BR5.2). Se declara
    #: y no se deduce del servidor: la del servidor movería la medianoche al
    #: cambiar de maquina y regalaria o quitaria una llamada. Es un nombre de la
    #: base de datos IANA y se comprueba que exista al cargar, porque un nombre
    #: mal escrito no se nota hasta que alguien mira el corte del dia.
    quota_timezone: str = Field(min_length=1)

    @model_validator(mode="after")
    def _la_zona_horaria_existe(self) -> Self:
        try:
            ZoneInfo(self.quota_timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            msg = (
                f"'{self.quota_timezone}' no es una zona horaria conocida: el dia de "
                "una cuota se cierra en la zona configurada (BR5.2), y un nombre mal "
                "escrito no se nota hasta que alguien mira el corte del dia"
            )
            raise ValueError(msg) from error
        return self

    @property
    def zone(self) -> tzinfo:
        """La zona ya resuelta. El validador garantizo que existe."""
        return ZoneInfo(self.quota_timezone)

    @model_validator(mode="after")
    def _cada_uso_se_declara_una_vez(self) -> Self:
        declarados = [uso.use for uso in self.uses]
        repetidos = sorted({u.value for u in declarados if declarados.count(u) > 1})
        if repetidos:
            msg = f"estos usos se declaran mas de una vez: {', '.join(repetidos)}"
            raise ValueError(msg)

        faltan = sorted(u.value for u in Use if u not in set(declarados))
        if faltan:
            msg = (
                f"estos usos no declaran plan: {', '.join(faltan)}. Un uso sin plan no "
                "puede saber si factura, y de esa marca depende el techo (BR3.6, BR4.2)"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _cada_uso_apunta_a_un_modelo_declarado(self) -> Self:
        por_nombre = {entrada.name: entrada for entrada in self.providers}
        for uso in self.uses:
            proveedor = por_nombre.get(uso.provider)
            if proveedor is None:
                msg = (
                    f"el uso '{uso.use}' apunta al proveedor '{uso.provider}', que este "
                    "archivo no declara"
                )
                raise ValueError(msg)
            if not proveedor.has_model(uso.model):
                msg = (
                    f"el uso '{uso.use}' apunta al modelo '{uso.model}', que "
                    f"'{uso.provider}' no declara; solo se llama a modelos anclados"
                )
                raise ValueError(msg)
        return self

    def speech_providers(self) -> tuple[ProviderName, ...]:
        """Los proveedores que declaran un modelo de transcripcion o de sintesis (U15).

        Son los que hablan con la voz, y solo tienen clave del uso `voice`: es la
        lista contra la que `schema:check` exige una fila de tope de ese uso
        (PA-9.2). Se deriva de lo declarado y no se escribe aparte, para que un
        proveedor de voz nuevo no pueda llegar sin su tope por olvido.
        """
        de_voz = (ModelKind.TRANSCRIPTION, ModelKind.SYNTHESIS)
        return tuple(
            entrada.name
            for entrada in self.providers
            if any(modelo.kind in de_voz for modelo in entrada.models)
        )

    def provider(self, name: ProviderName) -> ProviderEntry | None:
        """La entrada de un proveedor, o ninguna si este archivo no lo declara."""
        for entrada in self.providers:
            if entrada.name is name:
                return entrada
        return None

    def for_use(self, use: Use) -> UseConfig:
        """El plan de un uso. El validador ya garantizo que los cuatro estan."""
        for uso in self.uses:
            if uso.use is use:
                return uso
        msg = f"el uso '{use}' no esta declarado"  # pragma: no cover - lo impide el validador
        raise ProviderConfigError(msg)  # pragma: no cover


# --- Lo que declara `prices.yaml` ---------------------------------------------


class PriceLine(Frozen):
    """Una linea de precio de lista, sin la version ni la fecha.

    Las dos son de la tabla entera y no de la linea: una tabla donde cada linea
    pudiera declarar su propia fecha permitiria mezclar precios de dos momentos y
    publicar una cifra que no corresponde a ninguno.
    """

    provider: ProviderName
    model: str = Field(min_length=1)
    unit_kind: UnitKind
    unit_price_usd: UsdAmount


class CapKind(StrEnum):
    """Que figura detiene el gasto **del lado del proveedor** (BR5.8, PA-9).

    Una alerta de presupuesto **no** es ninguna de estas cuatro y no se anota:
    avisa mientras el gasto sigue, que es exactamente fallar abierto. Donde el
    proveedor no ofrece tope duro, lo que lo sustituye es un saldo prepagado con
    la recarga automatica desactivada, porque el saldo si se agota con la
    aplicacion detenida.
    """

    PREPAID_BALANCE = "prepaid_balance"
    MONTHLY_CAP = "monthly_cap"
    RATE_LIMIT = "rate_limit"
    NONE_AVAILABLE = "none_available"


class ProviderCapConfig(Frozen):
    """El tope de un uso en su proveedor, con cuando se comprobo por ultima vez.

    La fecha no es burocracia: un tope que nadie miro en meses es una creencia,
    no un control, y `schema:check` la compara contra hoy.
    """

    provider: ProviderName
    use: Use
    cap_kind: CapKind
    #: Lo que el proveedor tiene configurado, tal como se lee en su consola. Es
    #: texto porque cada figura se expresa distinto --un saldo, un tope mensual,
    #: un limite por minuto-- y forzarlo a un numero perderia la unidad.
    cap_value: str | None = None
    #: Que lo sustituye cuando no hay tope disponible. Obligatorio en ese caso: un
    #: hueco declarado sin sustituto es un hueco escondido con otro nombre.
    substitute: str | None = None
    last_checked_at: date

    @model_validator(mode="after")
    def _un_hueco_declarado_dice_que_lo_tapa(self) -> Self:
        if self.cap_kind is CapKind.NONE_AVAILABLE and not self.substitute:
            msg = (
                f"'{self.provider}' para el uso '{self.use}' declara que no hay tope "
                "disponible y no escribe 'substitute': un hueco declarado sin decir que "
                "lo tapa se lee igual de bien que un control (BR5.8, PA-9)"
            )
            raise ValueError(msg)
        if self.cap_kind is not CapKind.NONE_AVAILABLE and self.substitute:
            msg = (
                f"'{self.provider}' para el uso '{self.use}' declara el tope "
                f"'{self.cap_kind}' y ademas un sustituto: el sustituto es solo para "
                "cuando no hay tope"
            )
            raise ValueError(msg)
        return self


class PricesConfig(Frozen):
    """El archivo `prices.yaml` entero: la tabla de precios y los topes."""

    config_version: int = Field(ge=1)
    #: La version de la tabla. Sin ella, una cifra publicada no se podria
    #: reproducir meses despues, cuando el precio del proveedor ya cambio
    #: (AC4.8.4).
    list_version: str = Field(min_length=1)
    #: De cuando es esa tabla.
    effective_date: date
    entries: tuple[PriceLine, ...] = ()
    caps: tuple[ProviderCapConfig, ...] = ()

    @model_validator(mode="after")
    def _ninguna_linea_de_precio_repetida(self) -> Self:
        claves = [(linea.provider, linea.model, linea.unit_kind) for linea in self.entries]
        if len(set(claves)) != len(claves):
            msg = (
                "la tabla declara dos precios para la misma terna (proveedor, modelo, "
                "unidad): el calculo tendria que elegir uno y no hay criterio para ello"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _ningun_tope_repetido(self) -> Self:
        claves = [(tope.provider, tope.use) for tope in self.caps]
        if len(set(claves)) != len(claves):
            msg = "la tabla declara dos topes para la misma pareja (proveedor, uso)"
            raise ValueError(msg)
        return self

    def price_entries(self) -> tuple[PriceEntry, ...]:
        """Las lineas con la version y la fecha de la tabla ya puestas.

        Es lo que guarda cada fila de gasto: el precio que uso, de que lista y de
        que fecha (BR3.2).
        """
        return tuple(
            PriceEntry(
                provider=linea.provider,
                model=linea.model,
                unit_kind=linea.unit_kind,
                unit_price_usd=linea.unit_price_usd,
                list_version=self.list_version,
                effective_date=self.effective_date,
            )
            for linea in self.entries
        )


class ProviderPlatformConfig(Frozen):
    """Los dos archivos juntos, que es como los consume la raiz de composicion."""

    providers: ProvidersConfig
    prices: PricesConfig


# --- La carga -----------------------------------------------------------------


def _read_yaml(path: Path) -> dict[str, object]:
    try:
        crudo = path.read_text(encoding="utf-8")
    except OSError as error:
        msg = f"no se pudo leer '{path}': {error}"
        raise ProviderConfigError(msg) from error

    try:
        cargado = yaml.safe_load(crudo)
    except yaml.YAMLError as error:
        msg = f"'{path}' no es YAML valido: {error}"
        raise ProviderConfigError(msg) from error

    if not isinstance(cargado, dict):
        encontrado = type(cargado).__name__
        msg = f"'{path}' no contiene un mapa en su raiz, sino {encontrado}"
        raise ProviderConfigError(msg)
    return cargado


def _fila_de_tope(datos: dict[str, object], loc: tuple[int | str, ...]) -> str:
    """El proveedor y el uso de la fila `caps.N` a la que apunta un error, o vacio.

    `caps.3.last_checked_at` obliga a contar filas en el archivo; con el
    proveedor y el uso delante, quien lo lee va directo a la linea que falla.
    """
    if len(loc) < 2 or loc[0] != "caps" or not isinstance(loc[1], int):
        return ""
    filas = datos.get("caps")
    if not isinstance(filas, list) or loc[1] >= len(filas):
        return ""
    fila = filas[loc[1]]
    if not isinstance(fila, dict):
        return ""
    return f" (fila '{fila.get('provider', '?')}' del uso '{fila.get('use', '?')}')"


def _problemas_del_error(error: ValidationError, datos: dict[str, object] | None = None) -> str:
    """Cada problema con su clave **y su razon**.

    U2 reporta solo las claves, y ahi alcanza: sus fallos son campos que faltan.
    Aqui casi todos vienen de un validador que ya escribio por que --por que ese
    identificador parece un alias, por que ese tope no cuenta como control-- y
    tirar esa frase para dejar `caps.0` convertiria un mensaje util en un acertijo.
    Un problema de una fila de topes **nombra la fila** (BR4.1).
    """
    partes: list[str] = []
    for problema in error.errors():
        clave = ".".join(str(parte) for parte in problema["loc"]) or "(raiz)"
        fila = _fila_de_tope(datos, problema["loc"]) if datos is not None else ""
        razon = problema["msg"].removeprefix("Value error, ")
        partes.append(f"{clave}{fila}: {razon}")
    return "; ".join(partes)


def _load_into[T: Frozen](model: type[T], path: Path) -> T:
    datos = _read_yaml(path)
    try:
        return model.model_validate(datos)
    except ValidationError as error:
        msg = f"'{path}' no valida su esquema; {_problemas_del_error(error, datos)}"
        raise ProviderConfigError(msg) from error


def load_providers(path: Path) -> ProvidersConfig:
    """`providers.yaml`, validado. El fallo nombra el archivo y la clave rota."""
    return _load_into(ProvidersConfig, path)


def load_prices(path: Path) -> PricesConfig:
    """`prices.yaml`, validado."""
    return _load_into(PricesConfig, path)


def load(folder: Path | None = None) -> ProviderPlatformConfig:
    """La carpeta entera. Se carga una vez al arrancar y no se recarga en caliente.

    No recargar es una decision, no una simplificacion: cambiar un precio mueve
    una cifra publicada, y tiene que quedar en el historial y disparar la
    compuerta de evaluaciones. Una recarga en caliente permitiria moverla sin
    que nadie lo viera en un diff.
    """
    base = folder if folder is not None else paths.providers_dir()
    return ProviderPlatformConfig(
        providers=load_providers(base / PROVIDERS_FILE),
        prices=load_prices(base / PRICES_FILE),
    )
