"""La configuracion versionada del ajustador de IA: `app/config/adjuster/adjuster.yaml`.

Cinco decisiones del proyecto y no mas --cuanto busca, donde, cuantos casos por dia, cuantas
veces reintenta y cuanto espera a una corrida que no avanza-- mas el rango en que un valor de vehiculo es creible. El modelo, la clave y el
precio no estan aqui: viven en `providers.yaml` y `prices.yaml` con todos los demas usos, y una
cifra escrita en dos archivos acaba diciendo cosas distintas.

Ninguna cifra lleva valor por defecto en el codigo, por la misma razon que los limites de la
voz: un limite que el archivo no escriba seria un limite que nadie decidio, y este archivo es
el que se lee cuando hay que explicar por que un caso no se atendio hoy.
"""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, ValidationError, field_validator

from untangle import paths
from untangle.base import Frozen

CONFIG_FILE = "adjuster.yaml"

#: Un dominio pelado: etiquetas en minuscula separadas por puntos, sin esquema, ruta, puerto ni
#: espacios. El servidor de busqueda acepta una ruta, pero aqui se abre un sitio entero o no se
#: abre: una ruta en la lista de permitidos es un permiso a medias que nadie sabria leer.
_DOMINIO = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$")


class AdjusterConfigError(RuntimeError):
    """El archivo de configuracion del ajustador no se pudo leer o no valida."""


class AdjusterConfig(Frozen):
    """El archivo `adjuster.yaml` entero, ya validado."""

    config_version: Literal[1]
    #: Cuantas busquedas web puede hacer la investigacion de un caso. Se pasa tal cual al
    #: parametro `max_uses` de la herramienta del servidor.
    max_searches: int = Field(ge=1, le=10)
    #: Donde puede buscar. No puede estar vacia: sin dominios la busqueda es abierta.
    allowed_domains: tuple[str, ...] = Field(min_length=1)
    #: Casos que el ajustador puede decidir hoy en toda la demo.
    daily_case_cap: int = Field(ge=1)
    #: Intentos por caso antes de dejarlo fallido.
    attempts: int = Field(ge=1, le=10)
    #: Segundos sin avanzar tras los que una corrida `running` se da por perdida (el proceso que
    #: la llevaba se cayo) y el siguiente arranque la reabre. Mas que lo que tarda un caso sano.
    running_stale_seconds: int = Field(ge=60, le=3600)
    #: Minimo y maximo plausibles del valor de un vehiculo, en pesos colombianos.
    vehicle_value_range_cop: tuple[int, int]

    @field_validator("allowed_domains")
    @classmethod
    def _dominios_pelados_y_sin_repetir(cls, dominios: tuple[str, ...]) -> tuple[str, ...]:
        malos = sorted(d for d in dominios if not _DOMINIO.match(d))
        if malos:
            msg = (
                f"estos dominios no son un dominio pelado en minusculas (sin esquema, ruta, "
                f"puerto ni espacios): {', '.join(repr(d) for d in malos)}"
            )
            raise ValueError(msg)
        repetidos = sorted({d for d in dominios if dominios.count(d) > 1})
        if repetidos:
            msg = f"estos dominios estan repetidos: {', '.join(repetidos)}"
            raise ValueError(msg)
        return dominios

    @field_validator("vehicle_value_range_cop")
    @classmethod
    def _el_rango_tiene_sentido(cls, rango: tuple[int, int]) -> tuple[int, int]:
        minimo, maximo = rango
        if minimo <= 0 or minimo >= maximo:
            msg = (
                "el rango del valor del vehiculo va de un minimo positivo a un maximo mayor, en "
                f"pesos colombianos; llego [{minimo}, {maximo}]"
            )
            raise ValueError(msg)
        return rango

    @property
    def running_stale_after(self) -> timedelta:
        return timedelta(seconds=self.running_stale_seconds)

    def is_plausible_vehicle_value(self, valor_cop: int) -> bool:
        """Si un valor encontrado en la web cae dentro del rango creible, extremos incluidos."""
        minimo, maximo = self.vehicle_value_range_cop
        return minimo <= valor_cop <= maximo


def default_path() -> Path:
    return paths.adjuster_dir() / CONFIG_FILE


def load(path: Path | None = None) -> AdjusterConfig:
    """`adjuster.yaml`, validado. El fallo nombra el archivo y la clave rota."""
    archivo = path if path is not None else default_path()
    try:
        crudo = archivo.read_text(encoding="utf-8")
    except OSError as error:
        msg = f"no se pudo leer '{archivo}': {error}"
        raise AdjusterConfigError(msg) from error
    try:
        datos = yaml.safe_load(crudo)
    except yaml.YAMLError as error:
        msg = f"'{archivo}' no es YAML valido: {error}"
        raise AdjusterConfigError(msg) from error
    if not isinstance(datos, dict):
        msg = f"'{archivo}' no contiene un mapa en su raiz, sino {type(datos).__name__}"
        raise AdjusterConfigError(msg)
    try:
        return AdjusterConfig.model_validate(datos)
    except ValidationError as error:
        problemas = "; ".join(
            f"{'.'.join(str(parte) for parte in p['loc']) or '(raiz)'}: "
            f"{p['msg'].removeprefix('Value error, ')}"
            for p in error.errors()
        )
        msg = f"'{archivo}' no valida su esquema; {problemas}"
        raise AdjusterConfigError(msg) from error
