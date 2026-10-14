"""Como se arma la peticion, y por que la instruccion no puede tocar el contenido.

Este archivo es donde vive el control `SEC-U5.16` --la capa 7 del diseno de
seguridad-- y su forma es tan importante como lo que hace.

## La separacion es nativa, no una convencion nuestra

La API del proveedor distingue `systemInstruction` de `contents`. El adaptador
usa **esa** separacion en vez de armar una sola cadena, asi que no existe ningun
punto del codigo donde las dos se junten: no hay concatenacion que revisar.

Encima de eso, el tipo cierra la puerta por los dos lados:

- `Prompt.instruction.text` es `InstructionText` y lo produce solo el cargador de
  prompts, leyendo su archivo versionado. Pasar ahi un `ExternalText` no compila.
- `PromptPart.text` es `ExternalText`. Pasar ahi un `str` cualquiera tampoco
  compila, asi que no hay forma de meter en el contenido algo que nadie marco
  como de origen externo.

Lo que esta capa **no** hace, dicho: no impide que el modelo obedezca una
instruccion inyectada. Eso lo deciden la guardia de salida (U10) y las reglas
(U9), y lo mide DS-6. Lo que garantiza es mas estrecho y mas comprobable: que la
instruccion inyectada **nunca llego con el rango de una instruccion del sistema**.

## Determinismo

`temperature: 0`, que es lo que el equipo fija para que dos corridas del mismo
commit comparen algo. La **semilla** va "donde el proveedor lo permita", y cual
es exactamente ese campo en esta version de la API no se confirma sin una
respuesta real: entra con la prueba de contrato contra el proveedor de verdad,
que corre por hito (BR1.6). Inventar el nombre del campo ahora daria peticiones
rechazadas o, peor, un campo ignorado en silencio que haria creer que la corrida
es reproducible.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from untangle.base import UnitKind, Use
from untangle.providers.adapters.gemini.errors import PROVIDER
from untangle.providers.ports import (
    Prompt,
    ProviderError,
    ProviderErrorKind,
    UsageUnits,
    Vector,
)

__all__ = [
    "build_embed_body",
    "build_generate_body",
    "embed_path",
    "generate_path",
    "read_embeddings",
    "read_text",
    "read_usage",
    "response_schema",
]


def generate_path(model: str) -> str:
    """La ruta de una generacion. El modelo va anclado por identificador exacto."""
    return f"models/{model}:generateContent"


def embed_path(model: str) -> str:
    """La ruta de un lote de embeddings."""
    return f"models/{model}:batchEmbedContents"


#: Lo que el JSON Schema de Pydantic escribe y el campo `responseSchema` de la API
#: rechaza con `400 INVALID_ARGUMENT` ("Unknown name ... Cannot find field"),
#: observado en la primera llamada real de U7 el 2026-09-21. `$ref` no esta en la
#: lista porque no se quita: se reemplaza por su definicion.
_CLAVES_QUE_EL_PROVEEDOR_NO_ADMITE = frozenset({"$defs", "additionalProperties"})

#: Donde Pydantic deja las definiciones que referencia con `$ref`.
_PREFIJO_DE_REFERENCIA = "#/$defs/"


def response_schema(schema: type[BaseModel]) -> dict[str, Any]:
    """El esquema de la respuesta en la forma que admite `responseSchema`.

    Pydantic publica cada modelo anidado y cada enum como una definicion en
    `$defs` y la usa con `$ref`; el proveedor no admite ninguna de las dos, ni
    `additionalProperties`. Aqui cada referencia se sustituye por su definicion y
    se quitan esas claves. **Nada se pierde en la validacion**: la respuesta se
    sigue validando contra el modelo completo al volver (`_validar`), y el
    modelo si rechaza campos de mas.

    Un esquema recursivo no se puede aplanar, y se dice en vez de enviarlo roto.
    """
    completo = schema.model_json_schema()
    definiciones = completo.get("$defs", {})
    aplanado: dict[str, Any] = _sin_referencias(completo, definiciones, (), nombre=schema.__name__)
    return aplanado


def _sin_referencias(
    nodo: Any, definiciones: Mapping[str, Any], camino: tuple[str, ...], *, nombre: str
) -> Any:
    if isinstance(nodo, list):
        return [_sin_referencias(v, definiciones, camino, nombre=nombre) for v in nodo]
    if not isinstance(nodo, dict):
        return nodo
    resultado: dict[str, Any] = {}
    referencia = nodo.get("$ref")
    if referencia is not None:
        definicion = referencia.removeprefix(_PREFIJO_DE_REFERENCIA)
        if not referencia.startswith(_PREFIJO_DE_REFERENCIA) or definicion not in definiciones:
            msg = f"el esquema de '{nombre}' referencia '{referencia}', que no esta en $defs"
            raise ValueError(msg)
        if definicion in camino:
            msg = (
                f"el esquema de '{nombre}' es recursivo en '{definicion}': responseSchema no "
                "admite referencias y un esquema recursivo no se puede aplanar"
            )
            raise ValueError(msg)
        resultado.update(
            _sin_referencias(
                definiciones[definicion], definiciones, (*camino, definicion), nombre=nombre
            )
        )
    for clave, valor in nodo.items():
        if clave == "$ref" or clave in _CLAVES_QUE_EL_PROVEEDOR_NO_ADMITE:
            continue
        if clave == "properties" and isinstance(valor, dict):
            # Los nombres de campo son datos, no claves del esquema: un campo que
            # se llamara `additionalProperties` no se puede perder aqui.
            resultado[clave] = {
                campo: _sin_referencias(sub, definiciones, camino, nombre=nombre)
                for campo, sub in valor.items()
            }
        else:
            resultado[clave] = _sin_referencias(valor, definiciones, camino, nombre=nombre)
    return resultado


def build_generate_body(prompt: Prompt, *, schema: type[BaseModel] | None) -> dict[str, Any]:
    """El cuerpo de una generacion: **dos posiciones separadas**.

    La instruccion en `systemInstruction`, el texto de origen externo en
    `contents`, y ninguna operacion que junte las dos.
    """
    configuracion: dict[str, Any] = {"temperature": 0}
    if schema is not None:
        configuracion["responseMimeType"] = "application/json"
        configuracion["responseSchema"] = response_schema(schema)

    return {
        "systemInstruction": {"parts": [{"text": prompt.instruction.text}]},
        "contents": [
            {"role": parte.role, "parts": [{"text": parte.text}]} for parte in prompt.parts
        ],
        "generationConfig": configuracion,
    }


def build_embed_body(model: str, texts: Sequence[str], *, dimensions: int | None) -> dict[str, Any]:
    """El cuerpo de un lote de embeddings.

    La dimension sale de la configuracion versionada y no del codigo: cambiarla
    invalida el indice entero, y eso tiene que verse en un diff.
    """
    peticion: list[dict[str, Any]] = []
    for texto in texts:
        una: dict[str, Any] = {
            "model": f"models/{model}",
            "content": {"parts": [{"text": texto}]},
        }
        if dimensions is not None:
            una["outputDimensionality"] = dimensions
        peticion.append(una)
    return {"requests": peticion}


def read_text(body: Mapping[str, object], *, use: Use, attempt: int) -> str:
    """El texto de la primera candidata.

    Una respuesta sin candidatas o sin texto es `invalid_response`: el proveedor
    contesto, pero no lo que el contrato dice. No es un fallo de salud y por eso
    no abre el circuito.
    """
    candidatas = body.get("candidates")
    if not isinstance(candidatas, list) or not candidatas:
        raise _invalida(use, attempt)

    primera = candidatas[0]
    if not isinstance(primera, Mapping):
        raise _invalida(use, attempt)

    contenido = primera.get("content")
    if not isinstance(contenido, Mapping):
        raise _invalida(use, attempt)

    partes = contenido.get("parts")
    if not isinstance(partes, list) or not partes:
        raise _invalida(use, attempt)

    trozos: list[str] = []
    for parte in partes:
        if isinstance(parte, Mapping):
            texto = parte.get("text")
            if isinstance(texto, str):
                trozos.append(texto)
    if not trozos:
        raise _invalida(use, attempt)
    return "".join(trozos)


def read_usage(body: Mapping[str, object]) -> tuple[UsageUnits, ...]:
    """Las unidades que el proveedor dice haber cobrado.

    Dos clases y no una --entrada y salida-- porque se cobran a precios
    distintos, y convertirlas a una unidad comun perderia el precio con el que se
    calculo cada una.

    Una respuesta sin este bloque devuelve la tupla **vacia**, no ceros: un cero
    reportado se valora como un costo medido de cero dolares, y eso es
    exactamente la cifra que el proyecto prohibe escribir cuando lo cierto es que
    no se supo.
    """
    metadatos = body.get("usageMetadata")
    if not isinstance(metadatos, Mapping):
        return ()

    unidades: list[UsageUnits] = []
    for clave, clase in (
        ("promptTokenCount", UnitKind.INPUT_TOKENS),
        ("candidatesTokenCount", UnitKind.OUTPUT_TOKENS),
    ):
        contado = metadatos.get(clave)
        # `bool` es subclase de `int` y aqui seria un dato mal formado, no un
        # recuento de cero.
        if isinstance(contado, int) and not isinstance(contado, bool) and contado >= 0:
            unidades.append(UsageUnits(unit_kind=clase, units=Decimal(contado)))
    return tuple(unidades)


def read_embeddings(
    body: Mapping[str, object], *, expected: int, use: Use, attempt: int
) -> list[Vector]:
    """Los vectores del lote, **en el mismo orden y en la misma cantidad**.

    Que el numero coincida no es celo: los vectores se guardan contra sus
    clausulas por posicion, y un lote que devolviera uno de menos desplazaria
    todas las asociaciones siguientes sin que nada fallara.
    """
    crudos = body.get("embeddings")
    if not isinstance(crudos, list) or len(crudos) != expected:
        raise _invalida(use, attempt)

    vectores: list[Vector] = []
    for crudo in crudos:
        if not isinstance(crudo, Mapping):
            raise _invalida(use, attempt)
        valores = crudo.get("values")
        if not isinstance(valores, list) or not valores:
            raise _invalida(use, attempt)
        if not all(
            isinstance(valor, int | float) and not isinstance(valor, bool) for valor in valores
        ):
            raise _invalida(use, attempt)
        vectores.append(tuple(float(valor) for valor in valores))
    return vectores


def _invalida(use: Use, attempt: int) -> ProviderError:
    """El mismo error para todas las formas de "contesto algo que no es esto".

    No dice **que** venia mal, y es deliberado: decirlo exigiria citar el cuerpo,
    que es donde esta el texto del asegurado. Lo que se sabe de la respuesta
    queda en el tramo como tipo de error y numero de intento, que es lo que
    permite contarlos sin leerlos.
    """
    return ProviderError(
        ProviderErrorKind.INVALID_RESPONSE, provider=PROVIDER, use=use, attempt=attempt
    )
