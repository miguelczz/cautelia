"""La carpeta versionada de proveedores (BR1.3, BR1.4, BR3.6, BR5.8).

Lo que estas pruebas defienden no es el formato de dos archivos: es que las tres
cosas del proyecto que pueden costar dinero --a que modelo se llama, bajo que
plan, y que lo detiene del lado del proveedor-- no puedan quedar a medio declarar
sin que el arranque lo diga.

Los cuatro rechazos que se comprueban tienen en comun que su fallo es
**silencioso**: un alias movil sigue respondiendo, un uso sin plan sigue
llamando, un tope declarado sin sustituto se lee como un control, y una fecha de
comprobacion vieja se ve igual que una fresca. Ninguno rompe una pantalla.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from untangle import paths
from untangle.base import Use
from untangle.providers import config
from untangle.workspace import schema_check

PROVIDERS_VALIDO = """
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

PRECIOS_VALIDOS = """
config_version: 1
list_version: "0"
effective_date: 2026-09-17
entries: []
caps:
  - provider: gemini
    use: voice
    cap_kind: none_available
    substitute: Saldo prepagado sin recarga automatica, al publicar la voz.
    last_checked_at: 2026-09-17
"""


def _escribir(raiz: Path, providers: str = PROVIDERS_VALIDO, prices: str = PRECIOS_VALIDOS) -> Path:
    """Una carpeta de proveedores en un arbol temporal."""
    carpeta = raiz / "providers"
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / config.PROVIDERS_FILE).write_text(providers, encoding="utf-8")
    (carpeta / config.PRICES_FILE).write_text(prices, encoding="utf-8")
    return carpeta


# --- La carga feliz, sobre los archivos de verdad -----------------------------


def test_la_carpeta_versionada_del_repositorio_carga() -> None:
    """Los dos archivos que se publican, no una fixture.

    Es la unica prueba de este archivo que mira el repositorio: si los que se
    despliegan no cargan, el resto de la suite estaria comprobando una forma que
    nadie usa.
    """
    cargada = config.load(paths.providers_dir())

    #: Todos los usos declaran plan, y facturan la voz y la redaccion natural del
    #: chat, que desde el 2026-10-07 va con saldo prepagado de Anthropic (ADR-006,
    #: BR3.6). Lo demas sigue en plan gratuito.
    facturables = {uso.use for uso in cargada.providers.uses if uso.billable}
    assert facturables == {Use.VOICE, Use.CHAT_REPLY, Use.EVALS_CHAT}

    #: Anclado por identificador exacto, con su dimension de vector.
    modelos = {m.id: m for entrada in cargada.providers.providers for m in entrada.models}
    assert modelos["gemini-embedding-001"].dimensions == 768

    #: Los limites del enlace publico de FR3.9, y la reserva en minutos.
    assert cargada.providers.voice_limits.max_call_seconds == 240
    assert cargada.providers.voice_limits.site_daily_cap == 15
    assert cargada.providers.recording_reserve.minutes == 45

    #: Los limites del chat (FR4.6, RT-13): valor de arranque que U13 confirma.
    assert cargada.providers.chat_limits.messages_per_session == 30
    assert cargada.providers.chat_limits.messages_per_day == 60

    #: El dia de una cuota se cierra en la zona declarada, no en la del servidor
    #: (BR5.2). La demostracion es colombiana y la voz es paisa.
    assert cargada.providers.quota_timezone == "America/Bogota"


def test_la_conexion_es_la_misma_en_los_cinco_usos_y_la_lectura_no() -> None:
    """Los tiempos maximos son **por uso**, y cada mitad dice algo distinto.

    La conexion es igual en los cinco a proposito: un apreton de manos que no
    cierra en dos segundos no es lentitud del modelo, es que la red no esta, y
    eso no depende de para que se llame. La lectura si cambia, porque lo que
    cambia es quien espera: el turno de voz pierde el turno a los dos segundos,
    una corrida de evaluaciones no tiene a nadie mirando, y el uso `corpus`
    (U8) tolera la misma cola del plan gratuito tanto en la ingesta por lotes
    como en la consulta que hace el nodo en su ritmo de fondo.

    Se comprueba sobre el archivo del repositorio y no sobre una fixture: lo que
    importa es que los valores **desplegados** sean estos.
    """
    usos = {uso.use: uso for uso in config.load(paths.providers_dir()).providers.uses}

    assert {uso.connect_timeout_ms for uso in usos.values()} == {2000}
    assert usos[Use.VOICE].read_timeout_ms == 2000
    assert usos[Use.CHAT].read_timeout_ms == 12000
    assert usos[Use.EVALS].read_timeout_ms == 30000
    assert usos[Use.OPERATIONS].read_timeout_ms == 60000
    assert usos[Use.CORPUS].read_timeout_ms == 60000

    #: La voz es el unico que no puede esperar mas que su propio presupuesto de
    #: turno: pasados dos segundos, lo que corresponde es la frase de espera.
    assert usos[Use.VOICE].read_timeout_ms < usos[Use.CHAT].read_timeout_ms


def test_un_uso_sin_tiempo_maximo_declarado_no_carga(tmp_path: Path) -> None:
    """Ninguno lleva valor por defecto, por la misma razon que los limites de la
    voz: un tiempo maximo que el archivo no escribe es un tiempo maximo que nadie
    decidio, y este es el archivo que se lee cuando hay que explicar por que se
    corto una llamada."""
    sin_lectura = PROVIDERS_VALIDO.replace("    read_timeout_ms: 2000\n", "", 1)
    carpeta = _escribir(tmp_path, providers=sin_lectura)

    with pytest.raises(config.ProviderConfigError) as error:
        config.load(carpeta)

    assert "read_timeout_ms" in str(error.value)


def test_una_zona_horaria_que_no_existe_no_carga(tmp_path: Path) -> None:
    """BR5.2. Un nombre mal escrito no se manifiesta: el dia se cerraria donde
    la biblioteca decidiera, y eso no se nota hasta que alguien mira el corte del
    dia y le faltan o le sobran llamadas."""
    mal_escrita = PROVIDERS_VALIDO.replace(
        "quota_timezone: America/Bogota", "quota_timezone: America/Bogotaa"
    )
    carpeta = _escribir(tmp_path, providers=mal_escrita)

    with pytest.raises(config.ProviderConfigError) as error:
        config.load(carpeta)

    assert "America/Bogotaa" in str(error.value)


def test_la_tabla_de_precios_lleva_su_version_y_su_fecha(tmp_path: Path) -> None:
    """Sin las dos, una cifra publicada no se puede reproducir meses despues,
    cuando el precio del proveedor ya cambio (AC4.8.4). Van en la tabla y no en
    la linea: una tabla donde cada linea trajera su fecha permitiria mezclar
    precios de dos momentos y publicar una cifra que no corresponde a ninguno."""
    precios = PRECIOS_VALIDOS.replace(
        "entries: []",
        "entries:\n  - provider: gemini\n    model: alguno-001\n"
        '    unit_kind: input_tokens\n    unit_price_usd: "0.25"',
    )
    carpeta = _escribir(tmp_path, prices=precios)

    tabla = config.load(carpeta).prices.price_entries()

    assert len(tabla) == 1
    assert tabla[0].list_version == "0"
    assert tabla[0].effective_date == date(2026, 9, 17)

    sin_version = precios.replace('list_version: "0"\n', "")
    with pytest.raises(config.ProviderConfigError) as error:
        config.load_prices(_escribir(tmp_path / "otra", prices=sin_version) / config.PRICES_FILE)
    assert "list_version" in str(error.value)


# --- Los cuatro rechazos ------------------------------------------------------


def test_un_modelo_declarado_con_alias_movil_no_carga(tmp_path: Path) -> None:
    """BR1.4. Un alias lo mueve el proveedor sin avisar, y entonces dos corridas
    del mismo commit corren modelos distintos: la linea base de evaluaciones deja
    de comparar nada y nadie lo nota, porque el alias sigue respondiendo."""
    con_alias = PROVIDERS_VALIDO.replace("gemini-3.1-flash-lite", "gemini-flash-latest")
    carpeta = _escribir(tmp_path, providers=con_alias)

    with pytest.raises(config.ProviderConfigError) as error:
        config.load(carpeta)

    assert "latest" in str(error.value)


def test_un_uso_sin_plan_declarado_no_carga(tmp_path: Path) -> None:
    """BR3.6 y BR4.2. De la marca de facturable depende el techo: un uso que no
    la declara no puede saber si su costo suma, y el chat en plan gratuito se
    comeria el presupuesto de la voz sin que nadie hubiera pagado nada."""
    sin_operaciones = PROVIDERS_VALIDO.replace(
        "  - use: operations\n"
        "    provider: gemini\n"
        "    model: gemini-3.1-flash-lite\n"
        "    plan: free\n"
        "    billable: false\n"
        "    connect_timeout_ms: 2000\n"
        "    read_timeout_ms: 2000\n",
        "",
    )
    carpeta = _escribir(tmp_path, providers=sin_operaciones)

    with pytest.raises(config.ProviderConfigError) as error:
        config.load(carpeta)

    assert "operations" in str(error.value)


def test_un_plan_gratuito_marcado_como_facturable_no_carga(tmp_path: Path) -> None:
    """El archivo declara las dos cosas y el cargador las confronta. Que se
    escriban por separado es lo que permite leer en un diff el dia que un uso
    pasa a pagarse; que se comprueben es lo que impide que se contradigan."""
    incoherente = PROVIDERS_VALIDO.replace(
        "    plan: free\n    billable: false\n",
        "    plan: free\n    billable: true\n",
        1,
    )
    carpeta = _escribir(tmp_path, providers=incoherente)

    with pytest.raises(config.ProviderConfigError) as error:
        config.load(carpeta)

    assert "billable" in str(error.value)


def test_un_tope_sin_figura_disponible_y_sin_sustituto_no_carga(tmp_path: Path) -> None:
    """BR5.8 y PA-9. Declarar que no hay tope y no decir que lo sustituye deja el
    hueco abierto con nombre propio, que se lee igual de bien que un control."""
    sin_sustituto = PRECIOS_VALIDOS.replace(
        "    substitute: Saldo prepagado sin recarga automatica, al publicar la voz.\n",
        "",
    )
    carpeta = _escribir(tmp_path, prices=sin_sustituto)

    with pytest.raises(config.ProviderConfigError) as error:
        config.load(carpeta)

    assert "substitute" in str(error.value)


# --- La vigencia, que no es una restriccion del esquema -----------------------


def test_un_tope_comprobado_hace_mas_de_treinta_dias_falla_el_chequeo(tmp_path: Path) -> None:
    """Se mide contra la fecha de hoy, asi que ningun JSON Schema la expresa: una
    configuracion no caduca sola mientras esta quieta en disco. El reloj se
    inyecta para no tener que esperar un mes ni mover el de la maquina."""
    carpeta = _escribir(tmp_path)

    al_dia = schema_check.revisar_proveedores(carpeta, today=date(2026, 10, 17))
    vencido = schema_check.revisar_proveedores(carpeta, today=date(2026, 10, 18))

    # Se mira **lo que cambia con la fecha** y no el total: la tabla de precios de
    # esta fixture esta vacia a proposito, asi que el chequeo de la reserva por
    # llamada reporta sus cinco componentes en las dos corridas. Comparar contra
    # cero obligaba a darle precios a una fixture que no habla de precios, y
    # comparar contra cinco se rompe cada vez que la reserva gane un componente.
    nuevos = [problema for problema in vencido if problema not in al_dia]
    assert len(nuevos) == 1
    #: El mensaje nombra el proveedor y el uso: quien lo lee tiene que ir a esa
    #: consola, y para eso necesita saber a cual.
    assert "gemini" in nuevos[0]
    assert "voice" in nuevos[0]


def test_una_carpeta_rota_se_reporta_por_su_ruta_y_su_clave(tmp_path: Path) -> None:
    """El chequeo del guion no levanta la excepcion: devuelve un problema por
    archivo, con su ruta, para que el paso nombre lo que esta mal en vez de
    detenerse en el primero."""
    carpeta = _escribir(tmp_path, providers="config_version: 1\n")

    problemas = schema_check.revisar_proveedores(carpeta, today=date(2026, 9, 20))

    assert len(problemas) == 1
    assert config.PROVIDERS_FILE in problemas[0]


# --- U17, BR4.1: una fila sin fecha no carga, y el mensaje nombra la fila ------

DOS_FILAS = """
config_version: 1
list_version: "0"
effective_date: 2026-09-17
entries: []
caps:
  - provider: gemini
    use: voice
    cap_kind: none_available
    substitute: Saldo prepagado sin recarga automatica, al publicar la voz.
    last_checked_at: 2026-09-17
  - provider: deepgram
    use: voice
    cap_kind: prepaid_balance
    cap_value: 10 USD de saldo, sin recarga automatica
"""


def test_una_fila_de_tope_sin_fecha_no_carga_y_el_mensaje_nombra_la_fila(tmp_path: Path) -> None:
    """La fecha de comprobacion es una columna obligatoria, y el error dice **cual**
    fila la omite: con `caps.1` habria que contar filas en el archivo para saber
    que es la de Deepgram. Es la segunda fila a proposito: nombrar solo la primera
    pasaria igual con un mensaje fijo."""
    carpeta = _escribir(tmp_path, prices=DOS_FILAS)

    with pytest.raises(config.ProviderConfigError) as error:
        config.load(carpeta)

    mensaje = str(error.value)
    assert "last_checked_at" in mensaje
    assert "'deepgram'" in mensaje
    assert "'gemini'" not in mensaje


def test_las_filas_de_topes_del_repositorio_traen_fecha_y_la_voz_de_pago_tiene_la_suya() -> None:
    """Sobre el archivo desplegado: cada fila tiene fecha, y cada proveedor de voz
    tiene su tope del uso `voice` (BR4.1). La presencia la exige `schema:check`; aqui
    se fija que lo desplegado hoy cumple, para que romperlo falle en una prueba."""
    cargada = config.load(paths.providers_dir())

    assert cargada.prices.caps
    assert all(tope.last_checked_at is not None for tope in cargada.prices.caps)
    assert schema_check.missing_speech_caps(cargada) == []
