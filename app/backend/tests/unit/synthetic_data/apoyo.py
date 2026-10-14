"""Lo que comparten las pruebas de U7: un repositorio minimo y fuentes que se rompen a mano.

Cada prueba monta **su propio** arbol en un directorio temporal: la configuracion
de aseguradoras se copia de la versionada --asi la prueba ve las mismas tres que
el aplicativo, con sus prefijos y su tipo--, y los textos fuente se escriben aqui,
minimos, para poder romper una regla cada vez. Nunca se usan los textos fuente
reales para romper algo.

Los textos de estas pruebas son de relleno y lo dicen: no son redaccion de
poliza ni se parecen a la de ningun formulario.
"""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from untangle import paths
from untangle.base import ProviderName, Use
from untangle.providers.ceiling import CeilingGate
from untangle.providers.ports import SpendGate, UsageReport, UsageSink
from untangle.providers.transport import ProviderRequest, ProviderResponse, Transport
from untangle.synthetic_data.generator import (
    Composer,
    Composition,
    CompositionContext,
    CorpusOutput,
)
from untangle.synthetic_data.models import ClauseFile, ClauseRecord, IssuedPolicyRecord, SourceKind
from untangle.telemetry.spend import budget
from untangle.telemetry.spend.models import WINDOW_DAYS, WINDOW_START, BudgetState, BudgetWindow

RAIZ_REAL = paths.repo_root()

#: Una fecha de revision fija: ninguna prueba depende del reloj.
REVISADO = "2026-09-21"


def repo(tmp_path: Path) -> Path:
    """Un repositorio minimo con la configuracion de aseguradoras versionada."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "mise.toml").write_text("# raiz de prueba\n", encoding="utf-8")
    shutil.copytree(
        RAIZ_REAL / "app" / "config" / "tenants", tmp_path / "app" / "config" / "tenants"
    )
    (tmp_path / "app" / "data").mkdir(parents=True)
    return tmp_path


def entrada(**cambios: Any) -> dict[str, Any]:
    """Una clausula valida de Stonecroft; `cambios` la rompe o la ajusta.

    Pasar un valor `None` **quita** la clave, que es como se simula olvidarla.
    """
    base: dict[str, Any] = {
        "source_id": "STO-PAP-2026-A.INS",
        "kind": "clause",
        "clause_key": "A.INS",
        "part": "Parte A — Responsabilidad civil",
        "version": "2026.1",
        "text": "Texto de relleno de una prueba, sin redaccion de poliza.",
        "reviewed_at": REVISADO,
        "reviewed_by": "conductor",
        "drafted_with": "hand",
    }
    base.update(cambios)
    return {clave: valor for clave, valor in base.items() if valor is not None}


def escribir_fuente(
    raiz: Path,
    textos: list[dict[str, Any]],
    *,
    tenant: str = "stonecroft",
    idioma: str = "es",
    parte: str = "part_a",
) -> Path:
    """Escribe un archivo de parte en `app/data/sources/` y devuelve su ruta."""
    datos: dict[str, Any] = {
        "format_version": 1,
        "tenant_id": tenant,
        "language": idioma,
        "part_key": parte,
        "texts": textos,
    }
    destino = raiz / "app" / "data" / "sources" / tenant / idioma / f"{parte}.yaml"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return destino


def persona(**cambios: Any) -> dict[str, Any]:
    """Una persona ficticia valida."""
    base: dict[str, Any] = {
        "persona_id": "sto-per-001",
        "full_name": "Persona De Prueba",
        "phone": "310 555 0142",
        "national_id": "1020304050",
        "email": "persona.prueba@example.com",
    }
    base.update(cambios)
    return base


#: Un VIN de prueba cuyo digito de control (posicion 9) **falla**.
VIN_FICTICIO = "1M8GDM9A1KP042788"


def vehiculo(**cambios: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "plate": "ABC123",
        "make_model_year": "Sedan de prueba 2021",
        "vin": VIN_FICTICIO,
    }
    base.update(cambios)
    return base


def poliza(**cambios: Any) -> dict[str, Any]:
    """Una poliza emitida valida de Stonecroft."""
    base: dict[str, Any] = {
        "policy_number": "POL-100042",
        "tenant_id": "stonecroft",
        "issuer_tenant": "stonecroft",
        "form_id": "STO-PAP-2026",
        "form_version": "2026.1",
        "endorsement_ids": ["STO-PAP-2026-END-1"],
        "period_start": "2026-01-01",
        "period_end": "2027-01-01",
        "named_insured": persona(),
        "vehicles": [vehiculo()],
        "limits_and_deductibles": {"a.bodily_injury_per_person": 50000, "d.collision": 500},
    }
    base.update(cambios)
    return {clave: valor for clave, valor in base.items() if valor is not None}


# --- Compositores de prueba ---------------------------------------------------
# La composicion del corpus llega en el paso 8. Las pruebas del nucleo reciben
# estos dos, minimos, que hacen lo que hace cualquier compositor: leer las fuentes
# revisadas y elegir con el azar sembrado de su salida.


def _clausulas(contexto: CompositionContext) -> Composition:
    """Un archivo de clausulas por formulario, desde las fuentes revisadas."""
    por_formulario: dict[tuple[str, str], list[ClauseRecord]] = defaultdict(list)
    for texto in contexto.sources.texts:
        if texto.kind is not SourceKind.CLAUSE or texto.form_id is None:
            continue
        aseguradora = contexto.tenants.get(texto.tenant_id)
        assert aseguradora is not None
        assert texto.clause_key is not None
        assert texto.part is not None
        por_formulario[(texto.tenant_id, texto.form_id)].append(
            ClauseRecord(
                clause_id=texto.source_id,
                form_id=texto.form_id,
                form_version=texto.version,
                clause_key=texto.clause_key,
                part=texto.part,
                language=texto.language,
                text=texto.text,
                issuer_label=aseguradora.display_name,
            )
        )
    salidas = tuple(
        CorpusOutput(
            f"tenants/{tenant}/clauses/{form_id}.json",
            ClauseFile(form_id=form_id, clauses=tuple(sorted(c, key=lambda x: x.clause_id))),
        )
        for (tenant, form_id), c in sorted(por_formulario.items())
    )
    return Composition(outputs=salidas)


def poliza_con_azar(numero: str) -> Composer:
    """Una poliza cuyos datos personales salen del azar sembrado de su salida."""

    def componer(contexto: CompositionContext) -> Composition:
        ruta = f"tenants/stonecroft/issued_policies/{numero}.json"
        elegidor = contexto.chooser.for_output(ruta)
        datos = poliza(
            policy_number=numero,
            named_insured=persona(
                phone=f"310 555 01{elegidor.digits(2)}", national_id=elegidor.digits(10)
            ),
        )
        return Composition(outputs=(CorpusOutput(ruta, IssuedPolicyRecord.model_validate(datos)),))

    return componer


COMPOSITORES: tuple[Composer, ...] = (_clausulas, poliza_con_azar("POL-100042"))


def fuentes_minimas(raiz: Path) -> Path:
    """Dos clausulas revisadas de Stonecroft, una con tilde y raya para ver el UTF-8."""
    return escribir_fuente(
        raiz,
        [
            entrada(),
            entrada(
                source_id="STO-PAP-2026-A.EXCL.3",
                clause_key="A.EXCL.3",
                text="Relleno de prueba con tilde y raya — para ver UTF-8 sin escapar.",
            ),
        ],
    )


# --- Dobles de la redaccion ---------------------------------------------------
# El transporte doble es lo unico que se sustituye: la fabrica, el adaptador de
# Gemini y el techo son los de verdad. Asi lo que se prueba es el camino del
# aplicativo, sin red y sin gastar nada.


def respuesta_de_gemini(clausulas: list[dict[str, Any]]) -> ProviderResponse:
    """Una respuesta con la forma de Gemini y salida estructurada."""
    texto = json.dumps({"clauses": clausulas}, ensure_ascii=False)
    return ProviderResponse(
        status_code=200,
        body={
            "candidates": [{"content": {"parts": [{"text": texto}]}}],
            "usageMetadata": {"promptTokenCount": 900, "candidatesTokenCount": 1200},
        },
    )


def clausula_redactada(**cambios: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "kind": "clause",
        "clause_key": "A.INS",
        "part": "Parte A — Responsabilidad civil",
        "text": "Relleno de una respuesta de prueba, no redaccion de poliza.",
    }
    base.update(cambios)
    return base


class TransporteDoble:
    """Un transporte que anota lo que se le envia y contesta siempre lo mismo."""

    def __init__(self, respuesta: ProviderResponse, eventos: list[str]) -> None:
        self._respuesta = respuesta
        self._eventos = eventos
        self.enviadas: list[ProviderRequest] = []

    async def send(self, request: ProviderRequest) -> ProviderResponse:
        self._eventos.append("envio")
        self.enviadas.append(request)
        return self._respuesta


class FabricaDoble:
    """El doble de la fabrica de transportes: anota que clave recibio cada uso."""

    def __init__(self, respuesta: ProviderResponse, eventos: list[str] | None = None) -> None:
        self._respuesta = respuesta
        self.eventos: list[str] = eventos if eventos is not None else []
        self.creados: dict[Use, TransporteDoble] = {}
        self.claves: dict[Use, str] = {}

    def create(self, *, api_key: str, use: Use) -> Transport:
        transporte = TransporteDoble(self._respuesta, self.eventos)
        self.creados[use] = transporte
        self.claves[use] = api_key
        return transporte

    @property
    def enviadas(self) -> list[ProviderRequest]:
        return [p for t in self.creados.values() for p in t.enviadas]


def foto_del_presupuesto(*, gastado: str = "0") -> BudgetState:
    """La foto del presupuesto con el acumulado **forzado**, con la aritmetica de U5.

    Las pruebas del techo no consumen el presupuesto que protegen (regla de
    `project.md`): el acumulado se fuerza aqui.
    """
    ventana = BudgetWindow(
        window_start=WINDOW_START,
        window_end=WINDOW_START + timedelta(days=WINDOW_DAYS),
        billable_spent_usd=Decimal(gastado),
        unmeasured_billable_calls=0,
        updated_at=datetime(2026, 9, 21, 12, 0, tzinfo=UTC),
    )
    return budget.state(ventana)


class TechoAnotado(SpendGate):
    """El techo de verdad sobre una foto forzada, que ademas anota cuando se consulto."""

    def __init__(self, eventos: list[str], *, gastado: str = "0") -> None:
        estado = foto_del_presupuesto(gastado=gastado)

        async def leer() -> BudgetState:
            return estado

        self._techo = CeilingGate(leer)
        self._eventos = eventos

    async def ensure_open(self, *, provider: ProviderName, use: Use) -> None:
        self._eventos.append(f"techo:{provider.value}:{use.value}")
        await self._techo.ensure_open(provider=provider, use=use)


class RegistroAnotado(UsageSink):
    """El registro de gasto doble: anota cada reporte, no escribe en ninguna base."""

    def __init__(self) -> None:
        self.reports: list[UsageReport] = []

    async def report(self, usage: UsageReport) -> None:
        self.reports.append(usage)
