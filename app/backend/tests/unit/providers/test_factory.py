"""La fabrica de clientes por uso y los puertos (BR1.3, capas 2 y 7 de seguridad).

Lo que estas pruebas defienden tiene un fallo silencioso: si el chat usara la
clave de la voz, **todo seguiria funcionando** --la llamada sale, el modelo
contesta-- hasta el dia en que una cuota agotada en el chat apaga la voz, que es
exactamente lo que las claves separadas existen para impedir. No rompe ninguna
pantalla, no levanta ningun error, y solo se nota cuando ya paso.

Ninguna clave de estas pruebas es real ni fija: cada caso genera la suya en su
montaje. Una clave fija en el codigo de prueba es una clave en el repositorio.
"""

from __future__ import annotations

import secrets
from pathlib import Path

import pytest

from untangle.base import Use
from untangle.providers import config, factory, prompts
from untangle.providers.ports import (
    ExternalText,
    InstructionText,
    PromptPart,
    PromptRef,
    SystemInstruction,
)
from untangle.providers.transport import (
    ProviderRequest,
    ProviderResponse,
    Transport,
)
from untangle.settings import Settings

PROVIDERS_YAML = """
config_version: 1
providers:
  - name: gemini
    models:
      - id: gemini-3.1-flash-lite
        kind: generation
  - name: anthropic
    models:
      - id: claude-haiku-5-5
        kind: generation
uses:
  - use: voice
    provider: gemini
    model: gemini-3.1-flash-lite
    plan: paid
    billable: true
    connect_timeout_ms: 2000
    read_timeout_ms: 2000
  - use: chat
    provider: gemini
    model: gemini-3.1-flash-lite
    plan: free
    billable: false
    connect_timeout_ms: 2000
    read_timeout_ms: 2000
  - use: evals
    provider: gemini
    model: gemini-3.1-flash-lite
    plan: free
    billable: false
    connect_timeout_ms: 2000
    read_timeout_ms: 2000
  - use: operations
    provider: gemini
    model: gemini-3.1-flash-lite
    plan: free
    billable: false
    connect_timeout_ms: 2000
    read_timeout_ms: 2000
  - use: corpus
    provider: gemini
    model: gemini-3.1-flash-lite
    plan: free
    billable: false
    connect_timeout_ms: 2000
    read_timeout_ms: 60000
  - use: chat_reply
    provider: anthropic
    model: claude-haiku-5-5
    plan: paid
    billable: true
    connect_timeout_ms: 2000
    read_timeout_ms: 3000
  - use: evals_chat
    provider: anthropic
    model: claude-haiku-5-5
    plan: paid
    billable: true
    connect_timeout_ms: 2000
    read_timeout_ms: 3000
circuit_breaker:
  failure_threshold: 5
  open_seconds: 30
  half_open_probes: 1
voice_limits:
  max_call_seconds: 180
  calls_per_visitor_per_day: 1
  site_daily_cap: 15
chat_limits:
  messages_per_session: 30
  messages_per_day: 60
quota_timezone: America/Bogota
recording_reserve:
  minutes: 45
call_reserve:
  transcription:
    provider: deepgram
    model: nova-3
  synthesis:
    primary:
      provider: cartesia
      model: sonic-3.6
    fallback:
      provider: deepgram
      model: aura-2
    characters: 1300
  model:
    provider: gemini
    model: gemini-3.1-flash-lite
    input_tokens: 15000
    output_tokens: 1000
"""


class _TransporteFalso:
    """Un transporte que solo se acuerda de con que clave lo construyeron."""

    def __init__(self, api_key: str, use: Use) -> None:
        self.api_key = api_key
        self.use = use
        self.enviadas: list[ProviderRequest] = []

    async def send(self, request: ProviderRequest) -> ProviderResponse:
        self.enviadas.append(request)
        return ProviderResponse(status_code=200, body={})


class _FabricaDeTransportes:
    """La que registra que clave recibio cada uso. Es el unico observador posible.

    No hay forma de preguntarle a la fabrica por la clave de un uso, que es la
    propiedad que se esta comprobando: lo unico que se puede mirar es lo que
    llego hasta aqui.
    """

    def __init__(self) -> None:
        self.creados: dict[Use, _TransporteFalso] = {}

    def create(self, *, api_key: str, use: Use) -> Transport:
        transporte = _TransporteFalso(api_key, use)
        self.creados[use] = transporte
        return transporte


def _configuracion(tmp_path: Path) -> config.ProvidersConfig:
    ruta = tmp_path / config.PROVIDERS_FILE
    ruta.write_text(PROVIDERS_YAML, encoding="utf-8")
    return config.load_providers(ruta)


def _clave() -> str:
    """Una clave distinta en cada caso, generada aqui y nunca escrita a mano."""
    return f"test-{secrets.token_urlsafe(16)}"


# --- Un cliente por uso, con su clave -----------------------------------------


def test_cada_uso_recibe_su_propia_clave(tmp_path: Path) -> None:
    """Una clave distinta por uso, un cliente por uso, ninguno compartido (BR1.3).

    Este registro arma los transportes de Gemini. `chat_reply` y `evals_chat` son
    de Anthropic y su cliente lo arma su propio adaptador (2026-10-07): aqui no
    reciben transporte, y sus claves no aparecen en ningun cliente de Gemini.
    """
    claves = {uso: _clave() for uso in Use}
    transportes = _FabricaDeTransportes()

    factory.ProviderClients(
        settings=Settings(
            voice_model_api_key=claves[Use.VOICE],
            chat_model_api_key=claves[Use.CHAT],
            evals_model_api_key=claves[Use.EVALS],
            operations_model_api_key=claves[Use.OPERATIONS],
            corpus_model_api_key=claves[Use.CORPUS],
            anthropic_api_key_chat=claves[Use.CHAT_REPLY],
            anthropic_api_key_evals=claves[Use.EVALS_CHAT],
        ),
        config=_configuracion(tmp_path),
        transports=transportes,
    )

    recibidas = {uso: transporte.api_key for uso, transporte in transportes.creados.items()}
    de_anthropic = {Use.CHAT_REPLY, Use.EVALS_CHAT}
    de_gemini = {uso: clave for uso, clave in claves.items() if uso not in de_anthropic}
    assert recibidas == de_gemini
    assert not {claves[uso] for uso in de_anthropic} & set(recibidas.values())
    assert len(set(recibidas.values())) == len(de_gemini), "dos usos comparten clave"


def test_la_fabrica_no_acepta_una_clave_por_argumento(tmp_path: Path) -> None:
    """Construir un cliente con la clave que uno tenga a mano no esta disponible.

    Si lo estuviera, la separacion por uso seria una costumbre y no una
    propiedad: bastaria con que alguien pasara la que tenia cerca.
    """
    clientes = factory.ProviderClients(
        settings=Settings(chat_model_api_key=_clave()),
        config=_configuracion(tmp_path),
        transports=_FabricaDeTransportes(),
    )

    publicos = {nombre for nombre in dir(clientes) if not nombre.startswith("_")}
    assert "api_key" not in publicos
    for nombre in publicos:
        atributo = getattr(type(clientes), nombre, None)
        anotaciones = getattr(atributo, "__annotations__", {}) if atributo else {}
        assert "api_key" not in anotaciones, f"'{nombre}' acepta una clave por argumento"


def test_el_objeto_del_cliente_no_sale_de_la_fabrica(tmp_path: Path) -> None:
    """Ningun metodo publico devuelve el cliente, asi que no hay donde imprimirlo.

    La comprobacion se hace sobre lo que devuelven los metodos publicos y no
    sobre la lista de nombres: un metodo nuevo que lo devolviera pasaria una
    prueba de nombres sin enterarse.
    """
    clientes = factory.ProviderClients(
        settings=Settings(chat_model_api_key=_clave()),
        config=_configuracion(tmp_path),
        transports=_FabricaDeTransportes(),
    )

    for nombre in ("available", "require"):
        devuelto = getattr(clientes, nombre)()
        assert not isinstance(devuelto, factory._Client)
        assert not any(isinstance(elemento, factory._Client) for elemento in devuelto or ())

    # Y el objeto interno **no guarda la clave**: la entrego al construirse y
    # vive dentro del transporte, asi que aqui no hay atributo que imprimir.
    interno = clientes._clientes[Use.CHAT]
    assert not hasattr(interno, "api_key")
    assert "key" not in repr(interno)
    assert interno.use.value in repr(interno)


# --- Lo que pasa cuando falta una clave ---------------------------------------


def test_un_uso_sin_clave_no_cae_al_cliente_de_otro(tmp_path: Path) -> None:
    """Falla nombrando su variable en vez de usar la clave del vecino."""
    clientes = factory.ProviderClients(
        settings=Settings(chat_model_api_key=_clave()),
        config=_configuracion(tmp_path),
        transports=_FabricaDeTransportes(),
    )

    assert clientes.available() == (Use.CHAT,)
    with pytest.raises(factory.MissingProviderKeyError, match="UNTANGLE_VOICE_MODEL_API_KEY"):
        clientes.require(Use.VOICE)


def test_el_cliente_de_embeddings_usa_la_clave_de_su_propio_uso(tmp_path: Path) -> None:
    """PASO 0 de `u8-tanda-3`: `corpus` construye su cliente con su propia clave,
    nunca con la de `operations` ni con ninguna otra (BR1.3, BR1.6)."""
    transportes = _FabricaDeTransportes()
    clave_de_corpus = _clave()

    clientes = factory.ProviderClients(
        settings=Settings(
            chat_model_api_key=_clave(),
            operations_model_api_key=_clave(),
            corpus_model_api_key=clave_de_corpus,
        ),
        config=_configuracion(tmp_path),
        transports=transportes,
    )

    assert clientes.available() == (Use.CHAT, Use.CORPUS, Use.OPERATIONS)
    assert transportes.creados[Use.CORPUS].api_key == clave_de_corpus


def test_el_uso_corpus_sin_clave_falla_al_arrancar_con_su_motivo(tmp_path: Path) -> None:
    """Sin `UNTANGLE_CORPUS_MODEL_API_KEY`, pedirlo falla nombrando esa variable
    y no la de `operations`, como ya pasa con los otros cuatro usos."""
    clientes = factory.ProviderClients(
        settings=Settings(operations_model_api_key=_clave()),
        config=_configuracion(tmp_path),
        transports=_FabricaDeTransportes(),
    )

    with pytest.raises(factory.MissingProviderKeyError, match="UNTANGLE_CORPUS_MODEL_API_KEY"):
        clientes.require(Use.CORPUS)


def test_require_falla_al_arrancar_y_no_en_la_primera_llamada(tmp_path: Path) -> None:
    """Nombra **todas** las que faltan, no la primera.

    Descubrirlas de una en una obliga a arrancar cuatro veces, y cada arranque
    fallido es tiempo en el que ya se estaba llamando al proveedor.
    """
    clientes = factory.ProviderClients(
        settings=Settings(evals_model_api_key=_clave()),
        config=_configuracion(tmp_path),
        transports=_FabricaDeTransportes(),
    )

    with pytest.raises(factory.MissingProviderKeyError) as fallo:
        clientes.require(Use.VOICE, Use.CHAT, Use.EVALS, Use.OPERATIONS)

    mensaje = str(fallo.value)
    assert "UNTANGLE_VOICE_MODEL_API_KEY" in mensaje
    assert "UNTANGLE_CHAT_MODEL_API_KEY" in mensaje
    assert "UNTANGLE_OPERATIONS_MODEL_API_KEY" in mensaje
    assert "UNTANGLE_EVALS_MODEL_API_KEY" not in mensaje


async def test_la_peticion_sale_por_el_cliente_de_su_uso(tmp_path: Path) -> None:
    """Mandar por un uso usa **ese** transporte y ningun otro."""
    transportes = _FabricaDeTransportes()
    clientes = factory.ProviderClients(
        settings=Settings(chat_model_api_key=_clave(), voice_model_api_key=_clave()),
        config=_configuracion(tmp_path),
        transports=transportes,
    )

    await clientes.send(
        ProviderRequest(
            path="models/x:generateContent", body={}, connect_timeout_ms=1, read_timeout_ms=1
        ),
        use=Use.CHAT,
    )

    assert len(transportes.creados[Use.CHAT].enviadas) == 1
    assert transportes.creados[Use.VOICE].enviadas == []


# --- La posicion del texto externo, en el tipo --------------------------------


def test_el_cargador_de_prompts_no_recibe_texto(tmp_path: Path) -> None:
    """La instruccion sale de su archivo versionado, con su hash (BR1.7).

    La garantia no es que el tipo lo impida --se borra en ejecucion-- sino que
    **no hay argumento** donde meter texto: la firma pide identificador e idioma.
    """
    (tmp_path / "intake.es.md").write_text("Eres la agente de la aseguradora.\n", encoding="utf-8")

    instruccion = prompts.load_system_instruction("intake", "es", folder=tmp_path)

    assert instruccion.ref.prompt_id == "intake"
    assert instruccion.ref.locale == "es"
    assert len(instruccion.ref.sha256) == 64
    assert "Eres la agente" in instruccion.text

    firma = prompts.load_system_instruction.__annotations__
    assert set(firma) == {"prompt_id", "locale", "folder", "return"}


def test_el_hash_del_prompt_cambia_cuando_cambia_el_archivo(tmp_path: Path) -> None:
    """Editar el archivo mueve el hash, que es lo que dispara la compuerta."""
    ruta = tmp_path / "intake.en.md"
    ruta.write_text("You are the agent.\n", encoding="utf-8")
    antes = prompts.load_system_instruction("intake", "en", folder=tmp_path).ref.sha256

    ruta.write_text("You are the agent. Be brief.\n", encoding="utf-8")
    despues = prompts.load_system_instruction("intake", "en", folder=tmp_path).ref.sha256

    assert antes != despues


def test_un_prompt_que_falta_no_cae_al_otro_idioma(tmp_path: Path) -> None:
    """Falla nombrando la ruta. Un respaldo silencioso responderia en otro idioma."""
    (tmp_path / "intake.es.md").write_text("Eres la agente.\n", encoding="utf-8")

    with pytest.raises(prompts.PromptNotFoundError, match=r"intake\.en\.md"):
        prompts.load_system_instruction("intake", "en", folder=tmp_path)


def test_el_texto_externo_y_la_instruccion_son_tipos_distintos() -> None:
    """Las dos posiciones no se pueden confundir ni por descuido ni por atajo.

    En ejecucion los dos son `str` --`NewType` se borra-- asi que lo que esta
    prueba afirma es lo que **si** se puede afirmar en ejecucion: que la
    instruccion de un prompt solo se construye con el tipo de la instruccion, y
    que el contenido lleva el suyo. Que el comprobador de tipos rechace el cruce
    se comprueba plantandolo, y el experimento queda escrito en `test_gemini.py`.
    """
    parte = PromptPart(role="user", text=ExternalText("me choque ayer"))
    assert parte.text == "me choque ayer"

    # Los roles tambien son cerrados: `system` no es uno de ellos, porque el
    # rango de sistema no se pide con una etiqueta en el contenido.
    with pytest.raises(ValueError, match="role"):
        PromptPart(role="system", text=ExternalText("x"))

    instruccion = SystemInstruction(
        ref=PromptRef(prompt_id="intake", locale="es", sha256="a" * 64),
        text=InstructionText("Eres la agente."),
    )
    assert instruccion.text == "Eres la agente."
    # Lo unico que se puede afirmar en ejecucion: son dos tipos distintos. Que
    # el cruce no compile se comprobo plantandolo, y el experimento con su
    # salida exacta queda escrito en `test_gemini.py`.
    assert ExternalText.__name__ != InstructionText.__name__
