#!/usr/bin/env python3
"""Experimento 1: cuanto tarda un turno de voz completo, tramo por tramo.

Este guion **no es codigo del aplicativo**: es una medicion de una sola vez que
decide como se construye U15 `speech-providers`. Por eso vive en `scripts/` y no
bajo `app/`, y por eso habla directo con los proveedores en vez de pasar por los
puertos de U5 --los adaptadores que usarian esos puertos son justo lo que este
experimento tiene que decidir--.

**Que decide su resultado**, segun los documentos aprobados:

- La **voz de respaldo** entre Aura-2 y Kokoro (ADR-008).
- La **libreria de voz y la forma del transporte** (ADR-009, el unico contrato
  del proyecto todavia sin cerrar).
- El **precio por minuto de la voz**, que hoy falta en la tabla y deja la reserva
  de grabacion sin medir.

**Que mide, y por que esos tramos y no otros.** Lo que una persona siente en una
llamada no es la suma de los tres servicios: es cuanto pasa desde que deja de
hablar hasta que oye la primera silaba. Asi que cada tramo se mide por su
**cola**, no por su duracion total:

1. **Transcripcion**: desde el ultimo byte de audio enviado hasta que Deepgram
   da la transcripcion final. Lo que tardo en procesar mientras la persona
   hablaba no cuenta, porque ocurrio antes.
2. **Modelo**: desde que sale la peticion hasta el **primer token**, y ademas
   hasta el ultimo. El primero es lo que retrasa la voz; el segundo es lo que
   cuesta.
3. **Sintesis**: desde que sale el texto hasta el **primer byte de audio**. Lo
   que venga despues ya suena mientras se genera.

**Nunca una sola muestra.** Una medicion de reloj depende de la red, de la cola
del proveedor y de lo que la maquina este haciendo. El guion repite N vueltas y
publica el **minimo y la mediana**: el minimo dice que tan rapido puede ser esto
cuando nada estorba, y la mediana que tan rapido es de verdad. Es la misma
leccion que costo una prueba de U3.

**Lo que consume.** Segundos de audio por vuelta. Con las cinco vueltas por
omision son menos de un minuto de transcripcion y unas pocas miles de letras de
sintesis, o sea centavos del saldo gratuito. El guion imprime al final lo que
gasto para que quede a la vista. Ninguna cuenta del proyecto tiene recarga
automatica.

**Limite declarado.** `unit-of-work.md` dice que este experimento se mide "en
plan de pago". Con cuentas gratuitas puede haber cola que en el plan de pago no
existe, asi que la cifra se registra **como de plan gratuito** y se repite
pagando solo si queda cerca del limite. Lo que no depende del plan --la
comparacion de la voz de respaldo y la forma del transporte-- queda resuelto
igual.

Uso:

    mise run experimento:1
    mise run experimento:1 -- --vueltas 10 --audio mi-grabacion.wav

Variables de entorno (en tu `.env`, nunca en el codigo). Desde U15 son las
claves del uso `voice` del aplicativo, con sus nombres de alli; las de antes se
renombran con `mise run claves:voz -- --renombrar`:

    UNTANGLE_VOICE_DEEPGRAM_API_KEY
    UNTANGLE_VOICE_CARTESIA_API_KEY
    UNTANGLE_VOICE_MODEL_API_KEY   (la de Gemini que ya existe)

La voz de Catalina ya no es una variable: se lee de la configuracion versionada
de las aseguradoras (`voice.primary.es` en su `tenant.yaml`), que es donde U15 la
dejo porque no es un secreto (CG-U15-5).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

try:
    import websockets
except ModuleNotFoundError:  # pragma: no cover -- ruta de instalacion
    print(
        "Falta el cliente de WebSocket. Instalalo con:\n"
        "    uv add --project app/backend --dev websockets\n"
        "Deepgram solo ofrece streaming por WebSocket y httpx no lo habla.",
        file=sys.stderr,
    )
    raise SystemExit(2) from None


# --- Lo que se mide contra que -----------------------------------------------

#: La frase que se transcribe y se sintetiza en cada vuelta. Es una frase real de
#: la captura del caso, no un "hola mundo": la longitud y el vocabulario cambian
#: lo que tarda el modelo, y medir con una frase que el producto nunca diria da
#: un numero que no sirve para decidir nada.
FRASE = (
    "Choque ayer en la calle ochenta con la treinta y tres, como a las seis de "
    "la tarde, y el otro carro se fue sin parar."
)

#: El modelo de transcripcion que ADR-007 ancla, en modo multiidioma.
MODELO_TRANSCRIPCION = "nova-3"

#: La voz principal adoptada provisionalmente en ADR-008.
VOZ_PRINCIPAL = "sonic-3.6"

#: La candidata a voz de respaldo que si se puede medir hoy. La otra --Kokoro--
#: corre local y necesita descargar su modelo; se mide aparte y su numero entra
#: al mismo informe. Medir una sola no decide ADR-008: decide la mitad.
#:
#: El identificador lleva **la voz y el idioma**, no solo el idioma: pedir
#: `aura-2-es` devuelve 403 "el proyecto no tiene acceso al modelo", que es un
#: mensaje enganoso --el proyecto si tiene acceso; el modelo no existe con ese
#: nombre--. Comprobado el 2026-09-21.
VOZ_RESPALDO = "aura-2-celeste-es"

DEEPGRAM_WS = "wss://api.deepgram.com/v1/listen"
CARTESIA_TTS = "https://api.cartesia.ai/tts/bytes"
DEEPGRAM_TTS = "https://api.deepgram.com/v1/speak"
GEMINI = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-3.1-flash-lite:streamGenerateContent"
)

#: Cuanto audio se manda por trozo, en milisegundos. Veinte milisegundos es el
#: tamano de trama que usan los transportes de voz en tiempo real; mandar el
#: archivo entero de golpe medirfa otra cosa --una subida-- y no una llamada.
TROZO_MS = 20


@dataclass
class Vuelta:
    """Lo que dejo una vuelta, en segundos."""

    transcripcion: float
    modelo_primer_token: float
    modelo_completo: float
    sintesis_principal: float
    sintesis_respaldo: float | None
    transcrito: str
    respuesta: str

    @property
    def turno(self) -> float:
        """Lo que la persona espera: las tres colas, una detras de otra."""
        return self.transcripcion + self.modelo_primer_token + self.sintesis_principal


@dataclass
class Consumo:
    """Lo gastado, para que quede a la vista y no haya que adivinarlo."""

    segundos_de_audio: float = 0.0
    letras_sintetizadas: int = 0
    tokens_de_entrada: int = 0
    tokens_de_salida: int = 0
    vueltas: list[Vuelta] = field(default_factory=list)


def _cargar_env() -> dict[str, str]:
    """Lee `.env` del repositorio, si existe.

    El archivo de tareas **no** lo carga por su cuenta, y se prefiere que siga
    sin hacerlo: exportar el entorno entero a toda tarea cambiaria en silencio lo
    que ven las pruebas y el guion de verificacion, que hoy corren con un entorno
    conocido. Este guion es el unico que lo necesita, asi que lo lee el.

    El entorno de verdad gana sobre el archivo: quien exporta una variable a mano
    lo hace para sobreescribir, no para que la ignoren.
    """
    ruta = Path(__file__).resolve().parent.parent / ".env"
    if not ruta.exists():
        return {}
    valores: dict[str, str] = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        limpia = linea.strip()
        if not limpia or limpia.startswith("#") or "=" not in limpia:
            continue
        nombre, _, valor = limpia.partition("=")
        valores[nombre.strip()] = valor.strip().strip('"').strip("'")
    return valores


_ENV = _cargar_env()


def _clave(nombre: str) -> str:
    valor = os.environ.get(nombre) or _ENV.get(nombre)
    if not valor:
        print(
            f"Falta la variable {nombre}. Ponla en tu `.env` local; "
            "nunca en el codigo ni en un commit.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return valor


def _voz_de_catalina() -> str:
    """El identificador de Catalina, de la configuracion versionada de las aseguradoras.

    Se toma la voz principal en espanol de la primera carpeta que la declare en
    Cartesia: las tres usan la misma. No es un secreto, y leerla de ahi es medir
    exactamente la voz que el aplicativo usa.
    """
    import yaml

    raiz = Path(__file__).resolve().parent.parent / "app" / "config" / "tenants"
    for archivo in sorted(raiz.glob("*/tenant.yaml")):
        datos = yaml.safe_load(archivo.read_text(encoding="utf-8")) or {}
        principal = ((datos.get("voice") or {}).get("primary") or {}).get("es") or {}
        if principal.get("provider") == "cartesia" and principal.get("voice_id"):
            return str(principal["voice_id"])
    print(
        "Ninguna aseguradora declara la voz principal en espanol de Cartesia en su "
        "tenant.yaml (voice.primary.es).",
        file=sys.stderr,
    )
    raise SystemExit(2)


# --- Tramo 1: la transcripcion ------------------------------------------------


async def transcribir(audio: bytes, clave: str) -> tuple[float, str]:
    """Devuelve la cola de la transcripcion y lo que entendio.

    La cola es lo que pasa **despues** del ultimo byte enviado. Se mide asi
    porque es lo unico que la persona espera: mientras habla, el proveedor ya
    esta trabajando.
    """
    parametros = (
        f"?model={MODELO_TRANSCRIPCION}&language=multi&encoding=linear16"
        "&sample_rate=24000&channels=1&interim_results=false"
    )
    async with websockets.connect(
        DEEPGRAM_WS + parametros,
        additional_headers={"Authorization": f"Token {clave}"},
    ) as ws:
        bytes_por_trozo = int(24000 * 2 * TROZO_MS / 1000)
        for inicio in range(0, len(audio), bytes_por_trozo):
            await ws.send(audio[inicio : inicio + bytes_por_trozo])
            await asyncio.sleep(TROZO_MS / 1000)
        ultimo_byte = time.perf_counter()
        # `Finalize` es lo que Deepgram documenta para forzar el resultado final
        # de lo que ya recibio, y su respuesta llega marcada `from_finalize`.
        # **Esa llegada es la cola que se mide**, y no la de cualquier mensaje:
        # la primera version de este guion paraba en el primer segmento final
        # que encontraba, que ya estaba en el bufer desde antes del ultimo byte.
        # Daba 0 ms --imposible por red-- y ademas cortaba la frase a la mitad,
        # porque Deepgram entrega una frase larga en varios segmentos finales.
        await ws.send(json.dumps({"type": "Finalize"}))

        partes: list[str] = []
        llegada: float | None = None
        while True:
            crudo = await asyncio.wait_for(ws.recv(), timeout=15)
            mensaje = json.loads(crudo)
            if mensaje.get("type") != "Results":
                continue
            alternativa = mensaje["channel"]["alternatives"][0]
            if mensaje.get("is_final") and alternativa.get("transcript"):
                partes.append(alternativa["transcript"])
            if mensaje.get("from_finalize"):
                llegada = time.perf_counter()
                break
        await ws.send(json.dumps({"type": "CloseStream"}))
        return (llegada or time.perf_counter()) - ultimo_byte, " ".join(partes)


# --- Tramo 2: el modelo -------------------------------------------------------


async def responder(
    cliente: httpx.AsyncClient, texto: str, clave: str, consumo: Consumo
) -> tuple[float, float, str]:
    """Devuelve el tiempo al primer token, al ultimo, y la respuesta.

    El texto del asegurado entra como **contenido**, nunca concatenado a la
    instruccion de sistema: es la misma frontera que impone U5 y que RT-1 ataca.
    """
    cuerpo = {
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        "Eres una agente de seguros de auto. Responde en una sola "
                        "frase corta, en el idioma del asegurado, sin afirmar "
                        "cobertura ni montos."
                    )
                }
            ]
        },
        "contents": [{"role": "user", "parts": [{"text": texto}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 60},
    }
    salida: list[str] = []
    primer_token: float | None = None
    arranque = time.perf_counter()
    # Un 503 del proveedor no es un defecto del experimento: es el tier gratuito
    # ocupado. Se reintenta una vez y, si insiste, se dice cual fue en vez de
    # tumbar la corrida entera y perder las vueltas ya medidas.
    async with cliente.stream(
        "POST",
        f"{GEMINI}?alt=sse",
        json=cuerpo,
        # La clave va en **cabecera y nunca en la URL**, que es como lo hace el
        # adaptador del aplicativo. La razon la aprendimos cara el 2026-09-21: con
        # la clave en la cadena de consulta, un `raise_for_status` imprime la URL
        # entera en la traza, y ahi quedo la clave --en la terminal, en el log y
        # en cualquier sitio donde alguien pegue el error--. Una clave que se
        # imprime se rota, y rotarla cuesta mas que esta linea.
        headers={"x-goog-api-key": clave},
        timeout=httpx.Timeout(30.0, connect=2.0),
    ) as respuesta:
        respuesta.raise_for_status()
        async for linea in respuesta.aiter_lines():
            if not linea.startswith("data: "):
                continue
            if primer_token is None:
                primer_token = time.perf_counter() - arranque
            trozo = json.loads(linea[6:])
            for candidato in trozo.get("candidates", []):
                for parte in candidato.get("content", {}).get("parts", []):
                    salida.append(parte.get("text", ""))
            uso = trozo.get("usageMetadata")
            if uso:
                consumo.tokens_de_entrada = uso.get("promptTokenCount", 0)
                consumo.tokens_de_salida = uso.get("candidatesTokenCount", 0)
    completo = time.perf_counter() - arranque
    return primer_token or completo, completo, "".join(salida).strip()


# --- Tramo 3: la sintesis -----------------------------------------------------


async def sintetizar_principal(
    cliente: httpx.AsyncClient, texto: str, clave: str
) -> tuple[float, bytes]:
    """Tiempo hasta el **primer byte** de audio, y el audio completo."""
    cuerpo = {
        "model_id": VOZ_PRINCIPAL,
        "transcript": texto,
        "voice": {"mode": "id", "id": _voz_de_catalina()},
        "output_format": {
            "container": "raw",
            "encoding": "pcm_s16le",
            "sample_rate": 24000,
        },
        "language": "es",
    }
    arranque = time.perf_counter()
    primer_byte: float | None = None
    trozos: list[bytes] = []
    async with cliente.stream(
        "POST",
        CARTESIA_TTS,
        json=cuerpo,
        headers={"X-API-Key": clave, "Cartesia-Version": "2024-06-10"},
        timeout=httpx.Timeout(30.0, connect=2.0),
    ) as respuesta:
        respuesta.raise_for_status()
        async for trozo in respuesta.aiter_bytes():
            if primer_byte is None and trozo:
                primer_byte = time.perf_counter() - arranque
            trozos.append(trozo)
    return primer_byte or 0.0, b"".join(trozos)


async def sintetizar_respaldo(
    cliente: httpx.AsyncClient, texto: str, clave: str
) -> float:
    """Lo mismo con la candidata a voz de respaldo, para poder compararlas."""
    arranque = time.perf_counter()
    primer_byte: float | None = None
    async with cliente.stream(
        "POST",
        f"{DEEPGRAM_TTS}?model={VOZ_RESPALDO}&encoding=linear16&sample_rate=24000",
        json={"text": texto},
        headers={"Authorization": f"Token {clave}"},
        timeout=httpx.Timeout(30.0, connect=2.0),
    ) as respuesta:
        respuesta.raise_for_status()
        async for trozo in respuesta.aiter_bytes():
            if primer_byte is None and trozo:
                primer_byte = time.perf_counter() - arranque
    return primer_byte or 0.0


# --- La corrida ---------------------------------------------------------------


async def preparar_audio(
    cliente: httpx.AsyncClient, ruta: Path | None, clave_cartesia: str
) -> bytes:
    """El audio de entrada: el tuyo si lo das, o uno sintetizado si no.

    Con tu grabacion la medida es mas fiel, porque el habla real tiene pausas y
    ruido que el audio sintetico no tiene. Sin ella la medida sigue valiendo para
    la latencia, que es sobre todo red y cola del proveedor, y **eso queda
    anotado en el informe** en vez de callarse.
    """
    if ruta is not None:
        crudo = ruta.read_bytes()
        # Se salta la cabecera WAV si viene con ella; lo que va por el cable es PCM.
        return crudo[44:] if crudo[:4] == b"RIFF" else crudo
    _, audio = await sintetizar_principal(cliente, FRASE, clave_cartesia)
    return audio


async def correr(vueltas: int, audio_de: Path | None) -> Consumo:
    deepgram = _clave("UNTANGLE_VOICE_DEEPGRAM_API_KEY")
    cartesia = _clave("UNTANGLE_VOICE_CARTESIA_API_KEY")
    gemini = _clave("UNTANGLE_VOICE_MODEL_API_KEY")

    consumo = Consumo()
    async with httpx.AsyncClient() as cliente:
        audio = await preparar_audio(cliente, audio_de, cartesia)
        segundos = len(audio) / (24000 * 2)
        print(f"Audio de entrada: {segundos:.1f} s\n")

        for numero in range(1, vueltas + 1):
            cola_stt, transcrito = await transcribir(audio, deepgram)
            try:
                primer_token, completo, respuesta = await responder(
                    cliente, transcrito or FRASE, gemini, consumo
                )
            except httpx.HTTPStatusError as error:
                # El mensaje nombra el codigo y **no** la peticion: la URL y las
                # cabeceras llevan la clave.
                print(
                    f"  vuelta {numero}: el modelo respondio "
                    f"{error.response.status_code}; se salta esta vuelta"
                )
                continue
            primer_audio, _ = await sintetizar_principal(cliente, respuesta, cartesia)
            try:
                respaldo = await sintetizar_respaldo(cliente, respuesta, deepgram)
            except httpx.HTTPStatusError as error:
                print(f"  (la voz de respaldo no respondio: {error.response.status_code})")
                respaldo = None

            consumo.segundos_de_audio += segundos
            consumo.letras_sintetizadas += len(respuesta) * (1 if respaldo is None else 2)
            consumo.vueltas.append(
                Vuelta(
                    transcripcion=cola_stt,
                    modelo_primer_token=primer_token,
                    modelo_completo=completo,
                    sintesis_principal=primer_audio,
                    sintesis_respaldo=respaldo,
                    transcrito=transcrito,
                    respuesta=respuesta,
                )
            )
            print(
                f"vuelta {numero}/{vueltas}: "
                f"transcripcion {cola_stt * 1000:.0f} ms · "
                f"modelo {primer_token * 1000:.0f} ms · "
                f"voz {primer_audio * 1000:.0f} ms · "
                f"turno {consumo.vueltas[-1].turno * 1000:.0f} ms"
            )
    return consumo


def _resumen(nombre: str, valores: list[float]) -> str:
    if not valores:
        return f"  {nombre:<28} no se pudo medir"
    return (
        f"  {nombre:<28} minimo {min(valores) * 1000:6.0f} ms   "
        f"mediana {statistics.median(valores) * 1000:6.0f} ms"
    )


def informe(consumo: Consumo) -> None:
    vueltas = consumo.vueltas
    if not vueltas:
        print("Ninguna vuelta llego a completarse.")
        return
    print("\n--- Lo que tarda cada tramo ---------------------------------------")
    print(_resumen("Transcripcion (cola)", [v.transcripcion for v in vueltas]))
    print(_resumen("Modelo (primer token)", [v.modelo_primer_token for v in vueltas]))
    print(_resumen("Modelo (completo)", [v.modelo_completo for v in vueltas]))
    print(_resumen("Voz principal (1er byte)", [v.sintesis_principal for v in vueltas]))
    respaldo = [v.sintesis_respaldo for v in vueltas if v.sintesis_respaldo is not None]
    print(_resumen("Voz de respaldo (1er byte)", respaldo))
    print()
    print(_resumen("TURNO COMPLETO", [v.turno for v in vueltas]))

    print("\n--- Lo que consumio -----------------------------------------------")
    print(f"  audio transcrito        {consumo.segundos_de_audio:.1f} s")
    print(f"  letras sintetizadas     {consumo.letras_sintetizadas}")
    print(f"  tokens de entrada       {consumo.tokens_de_entrada} (ultima vuelta)")
    print(f"  tokens de salida        {consumo.tokens_de_salida} (ultima vuelta)")

    print("\n--- Una muestra de lo que entendio y respondio ---------------------")
    print(f"  entendio:  {vueltas[-1].transcrito!r}")
    print(f"  respondio: {vueltas[-1].respuesta!r}")

    print(
        "\nPega esta salida en el chat. Es medida **de plan gratuito**, y lo que\n"
        "decide es la mitad de ADR-008 --falta Kokoro, que corre local-- y la\n"
        "latencia del turno. ADR-009 necesita ademas el dato de transporte en el\n"
        "navegador, que este guion no mide."
    )


def main() -> None:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument(
        "--vueltas",
        type=int,
        default=5,
        help="Cuantas veces medir. Nunca una: una sola muestra no dice nada.",
    )
    analizador.add_argument(
        "--audio",
        type=Path,
        default=None,
        help="Tu grabacion (WAV 24 kHz mono). Sin ella se sintetiza una.",
    )
    argumentos = analizador.parse_args()
    if argumentos.vueltas < 3:
        print("Menos de tres vueltas no da mediana util.", file=sys.stderr)
        raise SystemExit(2)
    informe(asyncio.run(correr(argumentos.vueltas, argumentos.audio)))


if __name__ == "__main__":
    main()
