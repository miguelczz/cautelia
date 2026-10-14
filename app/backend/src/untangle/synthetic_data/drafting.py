"""La redaccion de un borrador con el modelo (F1; BR2.1, BR2.3, SEC-U7.4).

Es el **unico** modulo del paquete que habla con un modelo, y lo hace solo por
los puertos de U5 (C-16): recibe un `TextGenerator` y un `SpendGate` ya
construidos. Quien los construye es la raiz de composicion
(`untangle.server.synthetic_draft`), con la fabrica, el uso `operations`, el
techo y el registro de gasto; un contrato de importacion deja que solo ella
importe este modulo, y que este sea el unico del paquete que importa
`untangle.providers`.

## De que sale el prompt, y de que no puede salir

De dos cosas, y solo de dos (BR2.3):

1. **La plantilla versionada** de `draft_template/`: la instruccion de sistema
   por idioma, que carga el cargador de prompts de U5 (sin huecos ni variables),
   y `parts.yaml`, que dice que se pide en cada parte.
2. **La referencia de estructura** (`docs/reference/estructura-poliza-iso-pap.md`):
   nombres de parte y numeracion, nunca texto de clausula (P8).

La referencia se lee con `read_structure_reference`, que se niega a leer nada de
`tmp/`: ahi viven los specimens de terceros y los borradores, y ninguno de los
dos puede llegar a un prompt. El comando no acepta otra ruta de referencia.

## Lo que se escribe

Un borrador por parte, aseguradora e idioma en
`tmp/synthetic-drafts/<aseguradora>/<idioma>/<parte>.yaml`, que git ignora. No es
texto fuente: pasa a `app/data/sources/` solo despues de revisarlo contra la
referencia y P8, con su marca de revision (F2, BR2.2). Nada de la composicion
lee esa carpeta.

## Lo que no se hace

- **No se reintenta.** Un error del proveedor sale como tal, y una cuota o un
  saldo agotados detienen el comando: se retoma otro dia, sin cambiar de plan ni
  de clave (CG-U7-7).
- **No se corrige lo que devuelve el modelo.** Lo que no cuadra con el pedido
  --un encabezado distinto, un distractor de mas-- se devuelve como nota para la
  revision; decidir que se queda es trabajo de quien revisa.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, Self

import yaml
from pydantic import Field, ValidationError, model_validator

from untangle.base import Frozen, Locale, ProviderName, Use
from untangle.providers.ports import (
    ExternalText,
    Prompt,
    PromptPart,
    SpendGate,
    TextGenerator,
    UsageReport,
)
from untangle.providers.prompts import load_system_instruction
from untangle.synthetic_data.canonical import sha256_hex, write_atomic
from untangle.synthetic_data.models import (
    DistractorReason,
    DraftClauseKind,
    DraftResponse,
    DraftText,
    PolicyPart,
)
from untangle.tenancy.models import TenantConfig, TenantKind

__all__ = [
    "DRAFT_PROMPT_ID",
    "TEMPLATE_DIR",
    "DraftError",
    "DraftModel",
    "DraftRequest",
    "DraftResult",
    "DraftTemplate",
    "build_prompt",
    "draft_part",
    "draft_path",
    "load_template",
    "read_structure_reference",
    "reference_items",
    "request_for",
    "review_notes",
]

#: El identificador de la instruccion de sistema: `synthetic_draft.<idioma>.md`.
DRAFT_PROMPT_ID: Final = "synthetic_draft"

#: La plantilla versionada, dentro del paquete.
TEMPLATE_DIR: Final = Path(__file__).parent / "draft_template"
PARTS_FILE: Final = "parts.yaml"

#: En `parts.yaml`, "toda la lista de secciones de la referencia".
ALL_REFERENCE_ITEMS: Final = "*"

#: La seccion de la referencia que trae las partes y su numeracion.
_SECCION_DE_PARTES: Final = "## Secciones del formulario"
_ELEMENTO = re.compile(r"^\d+\.\s+\*\*(?P<nombre>[^*]+)\*\*")

#: Que tipos admite cada parte. Los repertorios de datos ficticios no se redactan
#: con el modelo: se escriben a mano (CG-U7-2).
_TIPOS_POR_PARTE: Final[dict[PolicyPart, frozenset[DraftClauseKind]]] = {
    PolicyPart.ENDORSEMENTS: frozenset({DraftClauseKind.ENDORSEMENT, DraftClauseKind.DISTRACTOR}),
    PolicyPart.JURISDICTION: frozenset({DraftClauseKind.JURISDICTION, DraftClauseKind.DISTRACTOR}),
}
_TIPOS_DE_UNA_PARTE: Final = frozenset({DraftClauseKind.CLAUSE, DraftClauseKind.DISTRACTOR})

#: La primera linea de cada borrador, para quien lo abra.
_CABECERA_DEL_BORRADOR: Final = (
    "# Borrador del modelo: NO es texto fuente. Reviselo contra la referencia de estructura\n"
    "# y P8 antes de promoverlo a app/data/sources/ con su marca de revision (F2, BR2.2).\n"
)


class DraftError(ValueError):
    """El pedido no se puede armar: se dice por que, y no se llama al modelo."""


# --- La plantilla -------------------------------------------------------------


class DraftLabels(Frozen):
    """Las etiquetas del pedido en un idioma. Van en la plantilla, no en el codigo."""

    reference: str = Field(min_length=1)
    no_reference: str = Field(min_length=1)
    request: str = Field(min_length=1)
    insurer: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=1)
    language: str = Field(min_length=1)
    part: str = Field(min_length=1)
    heading: str = Field(min_length=1)
    write: str = Field(min_length=1)
    distractors: str = Field(min_length=1)
    endorsements: str = Field(min_length=1)


def _dos_idiomas(valor: dict[Locale, str], que: str) -> None:
    if set(valor) != {"es", "en"}:
        msg = f"{que} va en los dos idiomas (es y en), y trae: {', '.join(sorted(valor))}"
        raise ValueError(msg)


class PartSpec(Frozen):
    """Lo que se pide al redactar una parte."""

    #: Que elementos de la referencia se citan: el nombre con que empieza cada uno
    #: (`Part A`), `*` para toda la lista, o ninguno si la referencia no la trae.
    reference: tuple[str, ...]
    heading: dict[Locale, str]
    distractors: int = Field(ge=0)
    endorsements: int = Field(default=0, ge=0)
    ask: dict[Locale, str]
    variants: dict[str, dict[Locale, str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _completa(self) -> Self:
        _dos_idiomas(self.heading, "el encabezado")
        _dos_idiomas(self.ask, "el pedido")
        for nombre, variante in self.variants.items():
            _dos_idiomas(variante, f"la variante '{nombre}'")
        return self


class DraftTemplateSpec(Frozen):
    """`parts.yaml`, validado: las diez partes y las etiquetas en los dos idiomas."""

    format_version: Literal[1]
    labels: dict[Locale, DraftLabels]
    parts: dict[PolicyPart, PartSpec]

    @model_validator(mode="after")
    def _completa(self) -> Self:
        if set(self.labels) != {"es", "en"}:
            msg = "las etiquetas van en los dos idiomas (es y en)"
            raise ValueError(msg)
        faltan = sorted(p.value for p in PolicyPart if p not in self.parts)
        if faltan:
            msg = f"parts.yaml no dice que pedir en: {', '.join(faltan)}"
            raise ValueError(msg)
        return self


@dataclass(frozen=True)
class DraftTemplate:
    """La plantilla cargada, con el hash de `parts.yaml` y la carpeta de las instrucciones."""

    spec: DraftTemplateSpec
    sha256: str
    folder: Path


def load_template(folder: Path = TEMPLATE_DIR) -> DraftTemplate:
    """La plantilla versionada, validada, o un `DraftError` que nombra el archivo."""
    archivo = folder / PARTS_FILE
    try:
        crudo = archivo.read_bytes()
        spec = DraftTemplateSpec.model_validate(yaml.safe_load(crudo.decode("utf-8")))
    except (OSError, yaml.YAMLError, ValidationError) as error:
        msg = f"la plantilla de redaccion '{archivo}' no se pudo cargar: {error}"
        raise DraftError(msg) from None
    return DraftTemplate(spec=spec, sha256=sha256_hex(crudo), folder=folder)


# --- La referencia de estructura ----------------------------------------------


def read_structure_reference(path: Path, *, repo_root: Path) -> str:
    """La referencia de estructura, que **nunca** puede venir de `tmp/` (BR2.3).

    En `tmp/` viven los specimens de terceros y los borradores del modelo. Leer de
    ahi seria la forma mas corta de meter texto ajeno en un prompt, asi que se
    rechaza por la ruta, antes de abrir nada.
    """
    prohibida = (repo_root / "tmp").resolve()
    if path.resolve().is_relative_to(prohibida):
        msg = (
            f"'{path}' esta bajo tmp/, donde viven los specimens y los borradores: el prompt "
            "de redaccion solo sale de la referencia de estructura y de la plantilla (BR2.3)"
        )
        raise DraftError(msg)
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        msg = f"no se pudo leer la referencia de estructura '{path}': {error}"
        raise DraftError(msg) from None


def reference_items(reference: str, names: tuple[str, ...]) -> tuple[str, ...]:
    """Los elementos de la lista de partes de la referencia que empiezan por esos nombres.

    Falla si la referencia ya no trae una parte que la plantilla pide: un prompt
    armado sin su referencia seria un prompt distinto sin que nadie lo decidiera.
    """
    elementos: list[str] = []
    dentro = False
    for linea in reference.splitlines():
        if linea.startswith("## "):
            dentro = linea.strip() == _SECCION_DE_PARTES
            continue
        if dentro and _ELEMENTO.match(linea):
            elementos.append(linea.strip())
    if not elementos:
        msg = f"la referencia de estructura no tiene la seccion '{_SECCION_DE_PARTES}'"
        raise DraftError(msg)
    if ALL_REFERENCE_ITEMS in names:
        return tuple(elementos)
    elegidos: list[str] = []
    for nombre in names:
        encontrados = [
            e for e in elementos if (m := _ELEMENTO.match(e)) and m["nombre"].startswith(nombre)
        ]
        if not encontrados:
            msg = f"la referencia de estructura no trae '{nombre}', que la plantilla pide"
            raise DraftError(msg)
        elegidos.extend(encontrados)
    return tuple(elegidos)


# --- El pedido ------------------------------------------------------------------


@dataclass(frozen=True)
class DraftRequest:
    """Una parte, de una emisora, en un idioma."""

    tenant_id: str
    display_name: str
    jurisdiction: str
    language: Locale
    part: PolicyPart
    variant: str | None = None


def request_for(
    tenant: TenantConfig,
    *,
    part: PolicyPart,
    language: Locale | None = None,
    variant: str | None = None,
) -> DraftRequest:
    """El pedido de una parte. Solo una emisora tiene textos propios (BR4.2)."""
    if tenant.kind is not TenantKind.CARRIER:
        msg = (
            f"'{tenant.tenant_id}' es una agencia: no se redactan textos para ella, sus copias "
            "salen de los textos de sus emisoras (BR4.2)"
        )
        raise DraftError(msg)
    return DraftRequest(
        tenant_id=tenant.tenant_id,
        display_name=tenant.display_name,
        jurisdiction=tenant.jurisdiction,
        language=language if language is not None else tenant.default_language,
        part=part,
        variant=variant,
    )


def _variante(request: DraftRequest, spec: PartSpec) -> str | None:
    """El texto de la variante pedida, o un `DraftError` si falta o sobra."""
    if not spec.variants:
        if request.variant is not None:
            msg = f"la parte '{request.part.value}' no tiene variantes; sobra --variant"
            raise DraftError(msg)
        return None
    opciones = ", ".join(sorted(spec.variants))
    if request.variant is None:
        msg = f"la parte '{request.part.value}' pide --variant: {opciones}"
        raise DraftError(msg)
    if request.variant not in spec.variants:
        msg = f"la variante '{request.variant}' no existe en '{request.part.value}': {opciones}"
        raise DraftError(msg)
    return spec.variants[request.variant][request.language]


def expected_heading(request: DraftRequest, template: DraftTemplate) -> str:
    """El encabezado que tiene que llevar cada clausula del borrador."""
    encabezado = template.spec.parts[request.part].heading[request.language]
    return encabezado.replace("{jurisdiction}", request.jurisdiction.capitalize())


def _contenido(request: DraftRequest, template: DraftTemplate, reference: str) -> str:
    spec = template.spec.parts[request.part]
    etiquetas = template.spec.labels[request.language]
    jurisdiccion = request.jurisdiction.capitalize()
    elementos = reference_items(reference, spec.reference) if spec.reference else ()
    variante = _variante(request, spec)

    lineas = [
        "<structure_reference>",
        f"# {etiquetas.reference}",
        *(elementos or (etiquetas.no_reference,)),
        "</structure_reference>",
        "",
        "<request>",
        f"# {etiquetas.request}",
        f"{etiquetas.insurer}: {request.display_name}",
        f"{etiquetas.jurisdiction}: {jurisdiccion}",
        f"{etiquetas.language}: {request.language}",
        f"{etiquetas.part}: {request.part.value}",
        f"{etiquetas.heading}: {expected_heading(request, template)}",
        f"{etiquetas.write}: {spec.ask[request.language].replace('{jurisdiction}', jurisdiccion)}",
    ]
    if variante is not None:
        lineas.append(variante)
    if spec.endorsements:
        lineas.append(f"{etiquetas.endorsements}: {spec.endorsements}")
    if spec.distractors:
        lineas.append(f"{etiquetas.distractors}: {spec.distractors}")
    lineas.append("</request>")
    return "\n".join(lineas)


def build_prompt(request: DraftRequest, *, reference: str, template: DraftTemplate) -> Prompt:
    """El prompt de una parte: la instruccion versionada y el pedido como contenido.

    El pedido va en la posicion de **contenido**, que en el tipo de U5 es
    `ExternalText`: es la posicion delimitada, separada de la instruccion en la
    propia peticion al proveedor. Lo que llena ese contenido sale solo de la
    plantilla y de la referencia de estructura.
    """
    instruccion = load_system_instruction(DRAFT_PROMPT_ID, request.language, folder=template.folder)
    contenido = ExternalText(_contenido(request, template, reference))
    return Prompt(instruction=instruccion, parts=(PromptPart(role="user", text=contenido),))


# --- La llamada y el borrador -------------------------------------------------


@dataclass(frozen=True)
class DraftModel:
    """Los dos puertos que la raiz de composicion construye para la redaccion."""

    generator: TextGenerator
    gate: SpendGate
    #: A que proveedor habla el uso `operations`: el techo lo pide para nombrarlo.
    provider: ProviderName


@dataclass(frozen=True)
class DraftResult:
    """Un borrador escrito, lo que costo y lo que la revision tiene que mirar."""

    path: Path
    draft: DraftText
    usage: UsageReport
    notes: tuple[str, ...]


def draft_path(drafts_dir: Path, request: DraftRequest) -> Path:
    """`<borradores>/<aseguradora>/<idioma>/<parte>.yaml`."""
    return drafts_dir / request.tenant_id / request.language / f"{request.part.value}.yaml"


def _version_del_prompt(prompt: Prompt, template: DraftTemplate) -> str:
    ref = prompt.instruction.ref
    return f"{ref.prompt_id}.{ref.locale} sha256:{ref.sha256}; parts.yaml sha256:{template.sha256}"


def _yaml(borrador: DraftText) -> bytes:
    cuerpo = yaml.safe_dump(
        borrador.model_dump(mode="json", exclude_none=True),
        allow_unicode=True,
        sort_keys=False,
        width=100,
    )
    return (_CABECERA_DEL_BORRADOR + cuerpo).encode("utf-8")


async def draft_part(
    request: DraftRequest,
    *,
    model: DraftModel,
    reference: str,
    template: DraftTemplate,
    drafts_dir: Path,
) -> DraftResult:
    """Pide el borrador de una parte y lo escribe. Si algo falla, no escribe nada.

    El orden importa: se arma el prompt (que puede fallar sin gastar), se consulta
    el techo **antes** de llamar, se llama una sola vez con el uso `operations`, y
    solo con la respuesta ya validada se escribe el archivo.
    """
    prompt = build_prompt(request, reference=reference, template=template)
    await model.gate.ensure_open(provider=model.provider, use=Use.OPERATIONS)
    resultado = await model.generator.generate(prompt, schema=DraftResponse, use=Use.OPERATIONS)
    respuesta = resultado.parsed_as(DraftResponse)
    borrador = DraftText(
        tenant_id=request.tenant_id,
        language=request.language,
        part=request.part,
        model=resultado.usage.model,
        prompt_version=_version_del_prompt(prompt, template),
        clauses=respuesta.clauses,
    )
    destino = draft_path(drafts_dir, request)
    write_atomic(destino, _yaml(borrador))
    return DraftResult(
        path=destino,
        draft=borrador,
        usage=resultado.usage,
        notes=review_notes(borrador, request, template),
    )


def review_notes(
    draft: DraftText, request: DraftRequest, template: DraftTemplate
) -> tuple[str, ...]:
    """Lo que no cuadra con el pedido. No se corrige: se le dice a quien revisa."""
    spec = template.spec.parts[draft.part]
    encabezado = expected_heading(request, template)
    permitidos = _TIPOS_POR_PARTE.get(draft.part, _TIPOS_DE_UNA_PARTE)
    notas: list[str] = []
    for clausula in draft.clauses:
        if clausula.part != encabezado:
            notas.append(
                f"{clausula.clause_key}: encabezado '{clausula.part}', se pidio '{encabezado}'"
            )
        if clausula.kind not in permitidos:
            notas.append(
                f"{clausula.clause_key}: tipo '{clausula.kind.value}' en la parte '{draft.part.value}'"
            )

    distractores = [c for c in draft.clauses if c.kind is DraftClauseKind.DISTRACTOR]
    if len(distractores) != spec.distractors:
        notas.append(f"{len(distractores)} distractor(es); se pidieron {spec.distractors}")
    claves = {c.clause_key for c in draft.clauses if c.kind is not DraftClauseKind.DISTRACTOR}
    for distractor in distractores:
        if distractor.distractor_of_key not in claves:
            notas.append(
                f"{distractor.clause_key}: se confunde con '{distractor.distractor_of_key}', "
                "que no esta en el borrador"
            )

    if spec.endorsements:
        numeros = sorted(
            c.endorsement_number for c in draft.clauses if c.endorsement_number is not None
        )
        if sorted(set(numeros)) != list(range(1, spec.endorsements + 1)):
            notas.append(f"endosos numerados {numeros}; se pidieron del 1 al {spec.endorsements}")

    # Dos clausulas con la misma numeracion en el mismo formulario chocarian al
    # promoverlas; solo la version anterior de un distractor la repite a proposito.
    propias = Counter(
        (c.endorsement_number, c.clause_key)
        for c in draft.clauses
        if c.distractor_reason is not DistractorReason.SUPERSEDED_VERSION
    )
    repetidas = sorted(clave for (_, clave), veces in propias.items() if veces > 1)
    if repetidas:
        notas.append(f"numeracion repetida: {', '.join(repetidas)}")
    return tuple(notas)
