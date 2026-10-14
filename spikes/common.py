"""Utilidades comunes de los experimentos de la semana 1.

Solo usa la biblioteca estándar de Python: son experimentos desechables y no
justifican instalar dependencias ni crear un manifiesto.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

SPIKES_DIR = Path(__file__).resolve().parent
USER_AGENT = "untangle-spikes/0.1"

T = TypeVar("T")


class HttpError(Exception):
    """Respuesta HTTP con error, con el cuerpo recortado para diagnóstico."""

    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"HTTP {status}: {body[:400]}")
        self.status = status
        self.body = body


def load_env() -> None:
    """Carga spikes/.env sin pisar variables que ya existan en el entorno."""
    env_file = SPIKES_DIR / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def require_env(name: str, where: str) -> str:
    """Devuelve la variable o termina explicando dónde se obtiene."""
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(
            f"Falta {name}. Créala en {where} y ponla en spikes/.env "
            "(copia spikes/.env.example). No la pegues en el chat."
        )
    return value


def _open(request: urllib.request.Request, timeout: float):
    request.add_header("User-Agent", USER_AGENT)
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise HttpError(exc.code, body) from None


def request_json(
    url: str,
    headers: dict[str, str] | None = None,
    payload: Any = None,
    method: str = "POST",
    timeout: float = 60.0,
) -> tuple[Any, float]:
    """Petición con respuesta JSON. Devuelve (respuesta, segundos)."""
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    all_headers = {"Accept": "application/json", **(headers or {})}
    if data is not None:
        all_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=all_headers)
    start = time.perf_counter()
    with _open(request, timeout) as response:
        body = response.read()
    elapsed = time.perf_counter() - start
    return (json.loads(body) if body else None), elapsed


def post_binary(
    url: str, headers: dict[str, str], body: bytes, timeout: float = 120.0
) -> tuple[Any, float]:
    """Envía un cuerpo binario (audio) y lee una respuesta JSON."""
    request = urllib.request.Request(url, data=body, method="POST", headers=headers)
    start = time.perf_counter()
    with _open(request, timeout) as response:
        raw = response.read()
    return json.loads(raw), time.perf_counter() - start


def stream_bytes(
    url: str,
    headers: dict[str, str],
    payload: Any,
    timeout: float = 60.0,
    chunk_size: int = 4096,
) -> tuple[bytes, float, float]:
    """POST JSON cuya respuesta es audio en streaming.

    Devuelve (audio, segundos hasta el primer byte, segundos totales). El tiempo
    incluye abrir la conexión: por eso los scripts descartan la primera petición.
    """
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, method="POST", headers={"Content-Type": "application/json", **headers}
    )
    chunks: list[bytes] = []
    first: float | None = None
    start = time.perf_counter()
    with _open(request, timeout) as response:
        while True:
            chunk = response.read1(chunk_size)
            if not chunk:
                break
            if first is None:
                first = time.perf_counter() - start
            chunks.append(chunk)
    total = time.perf_counter() - start
    return b"".join(chunks), (first if first is not None else total), total


def stream_sse(
    url: str, headers: dict[str, str], payload: Any, timeout: float = 60.0
) -> tuple[list[Any], float, float]:
    """POST JSON cuya respuesta son Server-Sent Events.

    Devuelve (eventos, segundos hasta el primer evento con datos, segundos totales).
    """
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, method="POST", headers={"Content-Type": "application/json", **headers}
    )
    events: list[Any] = []
    first: float | None = None
    start = time.perf_counter()
    with _open(request, timeout) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if not line.startswith("data:"):
                continue
            if first is None:
                first = time.perf_counter() - start
            events.append(json.loads(line[len("data:") :].strip()))
    total = time.perf_counter() - start
    return events, (first if first is not None else total), total


def provider_message(body: str) -> str:
    """Saca el mensaje legible del cuerpo de error del proveedor."""
    try:
        data = json.loads(body)
    except ValueError:
        return body.strip()[:200]
    if isinstance(data, dict):
        for container in (data.get("error"), data.get("detail"), data):
            if isinstance(container, dict) and isinstance(container.get("message"), str):
                return container["message"][:200]
            if isinstance(container, str):
                return container[:200]
    return body.strip()[:200]


def spend_stop_reason(exc: BaseException) -> str | None:
    """Dice qué se acabó cuando el fallo es de saldo, cuota o plan, y no de red.

    Estos fallos no se reintentan: reintentar no los arregla, y lo que toca es
    revisar la cuenta y decidir antes de recargar nada.
    """
    if not isinstance(exc, HttpError):
        return None
    body = exc.body.lower()
    if exc.status == 402 or "payment_required" in body or "free users" in body:
        return "el proveedor pide un pago o un plan de pago para esto"
    if exc.status == 429 and "perday" in body:
        return "se acabó la cuota diaria gratuita"
    if exc.status in (401, 403) and ("quota" in body or "credit" in body):
        return "se acabaron los créditos de la cuenta o el límite de la clave"
    return None


def with_retries(call: Callable[[], T], attempts: int = 4, base_delay: float = 5.0) -> T:
    """Reintenta ante límites por minuto (429) o caídas pasajeras del proveedor (5xx).

    No reintenta cuando se acabó un saldo o una cuota: avisa qué se acabó y deja
    que el experimento se detenga.
    """
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except HttpError as exc:
            reason = spend_stop_reason(exc)
            if reason:
                print(
                    f"  alto: {reason} ({provider_message(exc.body)}). "
                    "No se reintenta ni se recarga nada: revisa la cuenta y decide.",
                    file=sys.stderr,
                )
                raise
            retryable = exc.status == 429 or exc.status >= 500
            if not retryable or attempt == attempts:
                raise
            delay = base_delay * attempt
            cause = "límite de peticiones por minuto" if exc.status == 429 else "el proveedor está saturado o caído; suele ser pasajero"
            print(f"  aviso: HTTP {exc.status} ({cause}), reintento {attempt} en {delay:.0f} s", file=sys.stderr)
            time.sleep(delay)
    raise RuntimeError("inalcanzable")


def classify_error(exc: BaseException) -> str:
    """Traduce un fallo a la taxonomía cerrada que usarán los adaptadores reales."""
    if isinstance(exc, HttpError):
        if exc.status == 429:
            return "rate_limited"
        if exc.status >= 500:
            return "unavailable"
        return "invalid_response"
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, urllib.error.URLError):
        return "unavailable"
    return "invalid_response"


def percentile(values: Iterable[float], pct: float) -> float | None:
    """Percentil por rango más cercano; alcanza para decenas de muestras."""
    ordered = sorted(values)
    if not ordered:
        return None
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def fold(text: str) -> str:
    """Minúsculas y sin tildes, para comparar texto sin castigar la ortografía."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def ms(seconds: float | None) -> int | None:
    return None if seconds is None else round(seconds * 1000)


def write_results(folder: Path, name: str, data: Any) -> Path:
    """Guarda el resultado en <experimento>/results/<nombre>-<fecha UTC>.json."""
    out_dir = folder / "results"
    out_dir.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    path = out_dir / f"{name}-{stamp}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def markdown_table(headers: list[str], rows: Iterable[Iterable[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join("—" if value is None else str(value) for value in row) + " |")
    return "\n".join(lines)
