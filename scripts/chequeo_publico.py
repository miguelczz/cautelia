#!/usr/bin/env python3
"""Chequeo diario del sitio publicado: lee tres datos publicos y falla si algo esta mal.

    python3 scripts/chequeo_publico.py [--base-url https://cautelia.app] [--tolerar-agotado]
    mise run ops:check

Existe para que alguien se entere. Dos cosas pasaban en silencio: el reinicio
nocturno de la demo puede fallar (a las 24 horas del ultimo exitoso la demo deja
de aceptar casos nuevos) y la alerta de gasto de los proveedores solo dejaba un
evento en la salida del servidor. Este guion corre una vez al dia en un servidor
de GitHub (`.github/workflows/chequeo-publico.yml`) y **sale con codigo distinto
de cero** cuando algo esta mal; GitHub le manda un correo al dueno del repositorio
cuando un flujo programado falla. Sin servicio nuevo, sin costo fijo, sin un
correo que configurar.

Lo que lee, todo con `GET`, sin credencial y sin escribir nada en el sitio:

- `GET /api/health/ready`: que el sitio responda y este listo, y dentro de su
  cuerpo `checks.demo_reset`, el estado del reinicio nocturno.
- `GET /api/spend`: el estado del presupuesto de los proveedores y cuando se cruzo
  su alerta.

**Solo biblioteca estandar**, para correr con el `python3` que ya trae un servidor
de GitHub sin instalar nada. La logica esta en funciones puras que reciben lo ya
leido (los JSON y la hora actual) y devuelven veredictos; la unica que toca la red
es `leer`.

Cada comprobacion imprime una linea: `bien`, `FALLA` o `no medida`, con su razon.
"No medida" no falla: es lo que se dice cuando el dato no existe todavia (la
version publicada no trae el campo, o no hay ventana de presupuesto), porque
confundirlo con "bien" esconderia que no se miro, y con "FALLA" haria sonar la
alarma por algo que no esta roto.
"""

from __future__ import annotations

import argparse
import http.client
import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum

BASE_POR_OMISION = "https://cautelia.app"

#: Quien llama, para que se vea en los registros del sitio. Es la unica cabecera
#: propia: nada de galletas ni de credenciales.
AGENTE = "cautelia-chequeo-publico/1"

#: Cuanto se espera una respuesta. La instancia duerme y despertarla da hasta 40 s,
#: asi que 45 s por intento.
PLAZO_POR_INTENTO_S = 45.0

#: Un intento y un reintento, con una pausa en medio.
INTENTOS = 2
ESPERA_ENTRE_INTENTOS_S = 10.0

#: Cuanto cuenta una alerta de gasto como "nueva". El chequeo corre cada 24 horas;
#: 26 deja margen para el retraso del programador de GitHub, de modo que una alerta
#: haga fallar al chequeo una vez (a veces dos si la hora cae pegada a una corrida)
#: y no todos los dias. Pasado ese margen ya se aviso y se dice en una linea.
ALERTA_RECIENTE = timedelta(hours=26)

# Los estados que el sitio publica, con el nombre exacto de su enum. Una prueba del
# repositorio los compara contra `DemoResetStatus` y `BudgetStatus`.
REINICIO_AL_DIA = "current"
REINICIO_VENCIDO = "overdue"
REINICIO_ILEGIBLE = "unreadable"
GASTO_OK = "ok"
GASTO_ALERTA = "alerted"
GASTO_AGOTADO = "exhausted"
GASTO_SIN_MEDIR = "unmeasured"


class Resultado(Enum):
    BIEN = "bien"
    FALLA = "FALLA"
    NO_MEDIDA = "no medida"


@dataclass(frozen=True)
class Veredicto:
    """Lo que dice una comprobacion: su nombre, su resultado y la razon."""

    nombre: str
    resultado: Resultado
    razon: str

    def linea(self) -> str:
        return f"{self.resultado.value:<9} {self.nombre}: {self.razon}"


@dataclass(frozen=True)
class Lectura:
    """Lo que devolvio una direccion: un cuerpo JSON, o la razon por la que no hay.

    Exactamente una de las dos. `problema` cubre todo lo que no es un 200 con JSON:
    sin conexion, tiempo agotado, otro codigo de estado, cuerpo que no es JSON.
    """

    cuerpo: object = None
    problema: str | None = None


# --- Pura: lo ya leido -> veredictos -------------------------------------------


def _objeto(valor: object) -> dict[str, object] | None:
    return valor if isinstance(valor, dict) else None


def _hora(valor: object) -> datetime | None:
    """Una hora ISO 8601 **con zona**, o `None`: sin zona no se puede comparar."""
    if not isinstance(valor, str):
        return None
    try:
        hora = datetime.fromisoformat(valor)
    except ValueError:
        return None
    return hora if hora.tzinfo is not None else None


def _hace(transcurrido: timedelta) -> str:
    horas = transcurrido.total_seconds() / 3600
    if horas < 0:
        return "en el futuro"
    if horas < 1:
        return "hace menos de 1 hora"
    if horas < 2:
        return "hace 1 hora"
    if horas < 48:
        return f"hace {int(horas)} horas"
    return f"hace {int(horas // 24)} dias"


def _cuando(hora: datetime, ahora: datetime) -> str:
    return f"{hora.astimezone(UTC):%Y-%m-%d %H:%M} UTC ({_hace(ahora - hora)})"


def _checks_de(salud: Lectura) -> dict[str, object] | None:
    cuerpo = _objeto(salud.cuerpo)
    return None if cuerpo is None else _objeto(cuerpo.get("checks"))


def _bien(nombre: str, razon: str) -> Veredicto:
    return Veredicto(nombre, Resultado.BIEN, razon)


def _falla(nombre: str, razon: str) -> Veredicto:
    return Veredicto(nombre, Resultado.FALLA, razon)


def _no_medida(nombre: str, razon: str) -> Veredicto:
    return Veredicto(nombre, Resultado.NO_MEDIDA, razon)


def comprobar_salud(salud: Lectura) -> Veredicto:
    """El sitio responde 200 y dice que esta listo."""
    nombre = "salud"
    if salud.problema is not None:
        return _falla(nombre, f"GET /api/health/ready: {salud.problema}")
    cuerpo = _objeto(salud.cuerpo)
    if cuerpo is None:
        return _falla(nombre, "la respuesta no es un objeto JSON")
    if cuerpo.get("status") != "ready":
        return _falla(nombre, f"el campo status dice {cuerpo.get('status')!r}, no 'ready'")
    if _objeto(cuerpo.get("checks")) is None:
        return _falla(nombre, "a la respuesta le falta el campo checks")
    return _bien(nombre, f"el sitio responde y esta listo (version {cuerpo.get('version')})")


def reinicio_ilegible(salud: Lectura) -> bool:
    """Si el sitio dijo que no pudo leer el reinicio: la unica lectura que se repite."""
    checks = _checks_de(salud)
    reinicio = None if checks is None else _objeto(checks.get("demo_reset"))
    return reinicio is not None and reinicio.get("status") == REINICIO_ILEGIBLE


def comprobar_reinicio(salud: Lectura, *, ahora: datetime) -> Veredicto:
    """El reinicio nocturno esta al dia, segun la propia regla de 24 horas del sitio.

    El guion **no** recalcula la ventana: lee el estado que el sitio ya decidio con
    la regla que tambien cierra el chat, para que el aviso y el cierre no discrepen.
    """
    nombre = "reinicio nocturno"
    checks = _checks_de(salud)
    if checks is None:
        return _no_medida(nombre, "no se pudo leer la salud, asi que el reinicio no se miro")
    if "demo_reset" not in checks:
        return _no_medida(nombre, "la version publicada todavia no trae el campo checks.demo_reset")
    reinicio = _objeto(checks["demo_reset"])
    estado = None if reinicio is None else reinicio.get("status")
    if reinicio is None or not isinstance(estado, str):
        return _falla(nombre, "el campo checks.demo_reset no tiene la forma esperada")
    return _reinicio_segun(estado, _hora(reinicio.get("last_successful_at")), ahora)


def _reinicio_segun(estado: str, ultimo: datetime | None, ahora: datetime) -> Veredicto:
    nombre = "reinicio nocturno"
    if estado == REINICIO_AL_DIA:
        cuando = "sin hora" if ultimo is None else _cuando(ultimo, ahora)
        return _bien(nombre, f"el ultimo reinicio exitoso fue {cuando}")
    if estado == REINICIO_VENCIDO:
        desde = (
            "no hay ningun reinicio exitoso registrado"
            if ultimo is None
            else f"el ultimo exitoso fue {_cuando(ultimo, ahora)}"
        )
        return _falla(
            nombre, f"el reinicio esta vencido y la demo ya no acepta casos nuevos: {desde}"
        )
    if estado == REINICIO_ILEGIBLE:
        return _falla(nombre, "el sitio no pudo leer el registro de reinicios")
    return _falla(
        nombre,
        f"estado de reinicio desconocido: {estado!r} (el guion conoce "
        f"{REINICIO_AL_DIA}, {REINICIO_VENCIDO} y {REINICIO_ILEGIBLE})",
    )


def comprobar_gasto(gasto: Lectura, *, ahora: datetime, tolerar_agotado: bool = False) -> Veredicto:
    """El presupuesto de los proveedores y su alerta.

    Una alerta cruzada hace fallar solo si se envio hace menos de `ALERTA_RECIENTE`:
    un correo, no uno diario. Agotado falla salvo `tolerar_agotado`, que silencia a
    conciencia un estado ya decidido.
    """
    nombre = "gasto"
    if gasto.problema is not None:
        return _falla(nombre, f"GET /api/spend: {gasto.problema}")
    cuerpo = _objeto(gasto.cuerpo)
    if cuerpo is None or "window" not in cuerpo:
        return _falla(nombre, "a la respuesta le falta el campo window")
    if cuerpo["window"] is None:
        return _no_medida(nombre, "todavia no hay ventana de presupuesto que medir")
    ventana = _objeto(cuerpo["window"])
    estado = None if ventana is None else ventana.get("status")
    if ventana is None or not isinstance(estado, str):
        return _falla(nombre, "el campo window no tiene la forma esperada")
    return _gasto_segun(estado, cuerpo.get("alert_sent_at"), ahora, tolerar_agotado)


def _gasto_segun(
    estado: str, alerta_enviada: object, ahora: datetime, tolerar_agotado: bool
) -> Veredicto:
    nombre = "gasto"
    if estado == GASTO_OK:
        return _bien(nombre, "el gasto esta por debajo de la alerta")
    if estado == GASTO_ALERTA:
        return _alerta(alerta_enviada, ahora=ahora)
    if estado == GASTO_AGOTADO:
        if tolerar_agotado:
            return _bien(nombre, "el presupuesto esta agotado (tolerado con --tolerar-agotado)")
        return _falla(
            nombre, "el presupuesto de los proveedores esta agotado: la voz ya no acepta llamadas"
        )
    if estado == GASTO_SIN_MEDIR:
        return _falla(
            nombre, "el gasto no se pudo medir: falta un precio o una llamada quedo sin valorar"
        )
    return _falla(
        nombre,
        f"estado de gasto desconocido: {estado!r} (el guion conoce "
        f"{GASTO_OK}, {GASTO_ALERTA}, {GASTO_AGOTADO} y {GASTO_SIN_MEDIR})",
    )


def _alerta(enviada: object, *, ahora: datetime) -> Veredicto:
    nombre = "gasto"
    hora = _hora(enviada)
    if hora is None:
        # Con la alerta cruzada el sitio siempre guarda cuando la marco; sin esa hora
        # no se puede probar que ya se aviso, y callar seria perder el aviso.
        return _falla(
            nombre, "la alerta de gasto esta cruzada pero no trae una hora de envio legible"
        )
    if ahora - hora < ALERTA_RECIENTE:
        return _falla(nombre, f"el gasto cruzo la alerta: se marco {_cuando(hora, ahora)}")
    return _bien(
        nombre,
        f"el gasto sigue sobre la alerta, que se marco {_cuando(hora, ahora)}; ya se aviso",
    )


def juzgar(
    salud: Lectura, gasto: Lectura, *, ahora: datetime, tolerar_agotado: bool = False
) -> list[Veredicto]:
    """Las tres comprobaciones, en el orden en que se imprimen."""
    return [
        comprobar_salud(salud),
        comprobar_reinicio(salud, ahora=ahora),
        comprobar_gasto(gasto, ahora=ahora, tolerar_agotado=tolerar_agotado),
    ]


def codigo_de_salida(veredictos: Sequence[Veredicto]) -> int:
    """Distinto de cero si alguna comprobacion fallo; `no medida` no cuenta."""
    return 1 if any(v.resultado is Resultado.FALLA for v in veredictos) else 0


# --- La red: lo unico que no es puro -----------------------------------------------


def _leer_una_vez(url: str, plazo_s: float) -> Lectura:
    if not url.startswith(("https://", "http://")):
        return Lectura(problema="la direccion no empieza por https:// ni http://")
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE}, method="GET")  # noqa: S310 -- el esquema se comprueba arriba
    try:
        with urllib.request.urlopen(peticion, timeout=plazo_s) as respuesta:  # noqa: S310 -- el esquema se comprueba arriba
            estado = respuesta.status
            crudo = respuesta.read()
    except urllib.error.HTTPError as error:
        error.close()
        return Lectura(problema=f"respondio HTTP {error.code}")
    except (OSError, http.client.HTTPException) as error:
        return Lectura(problema=f"no se pudo leer ({type(error).__name__}: {str(error)[:120]})")
    if estado != 200:
        return Lectura(problema=f"respondio HTTP {estado}")
    try:
        return Lectura(cuerpo=json.loads(crudo))
    except ValueError:
        return Lectura(problema="respondio 200 pero el cuerpo no es JSON")


def leer(
    url: str,
    *,
    intentos: int = INTENTOS,
    espera_s: float = ESPERA_ENTRE_INTENTOS_S,
    plazo_s: float = PLAZO_POR_INTENTO_S,
    dormir: Callable[[float], None] = time.sleep,
) -> Lectura:
    """`GET` con un reintento: la instancia duerme y la primera pregunta la despierta."""
    lectura = Lectura(problema="no se hizo ningun intento")
    for intento in range(intentos):
        if intento:
            dormir(espera_s)
        lectura = _leer_una_vez(url, plazo_s)
        if lectura.problema is None:
            break
    return lectura


def main(argv: Sequence[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        description="Lee la salud y el gasto del sitio publicado y falla si algo esta mal."
    )
    analizador.add_argument(
        "--base-url",
        default=BASE_POR_OMISION,
        help=f"direccion del sitio (por omision {BASE_POR_OMISION})",
    )
    analizador.add_argument(
        "--tolerar-agotado",
        action="store_true",
        help="no fallar si el presupuesto esta agotado (para silenciarlo a conciencia)",
    )
    args = analizador.parse_args(argv)
    base = str(args.base_url).rstrip("/")
    if not base.startswith(("https://", "http://")):
        analizador.error("--base-url tiene que empezar por https:// o http://")

    salud = leer(f"{base}/api/health/ready")
    if reinicio_ilegible(salud):
        # La primera pregunta despierta la instancia y la base; si el sitio no pudo
        # leer el registro en frio, una segunda lectura ya lo encuentra tibio. Si
        # sigue ilegible, falla como corresponde.
        time.sleep(ESPERA_ENTRE_INTENTOS_S)
        segunda = leer(f"{base}/api/health/ready")
        if segunda.problema is None:
            salud = segunda
    gasto = leer(f"{base}/api/spend")

    veredictos = juzgar(
        salud, gasto, ahora=datetime.now(UTC), tolerar_agotado=bool(args.tolerar_agotado)
    )
    for veredicto in veredictos:
        print(veredicto.linea(), flush=True)
    fallas = sum(1 for v in veredictos if v.resultado is Resultado.FALLA)
    if fallas:
        print(f"resultado: {fallas} de {len(veredictos)} comprobaciones FALLARON", flush=True)
    else:
        print("resultado: todo en orden", flush=True)
    return codigo_de_salida(veredictos)


if __name__ == "__main__":
    sys.exit(main())
