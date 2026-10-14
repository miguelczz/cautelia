"""La redaccion con el modelo: por la fabrica, con el uso `operations`, el techo y el gasto.

Reglas: BR2.1 (redaccion aparte, a borrador no versionado), BR2.3 (el prompt
nunca lleva texto de terceros) y SEC-U7.4 (un borrador no llega al corpus).

**Nada sale a la red** (guardia del `conftest.py`). Lo unico que se sustituye es
el transporte: la fabrica de clientes por uso, el adaptador de Gemini y el techo
son los de verdad, y el techo lee un acumulado **forzado** en vez de gastar el
presupuesto que protege (regla de `project.md`). Ninguna clave es real: cada
prueba genera la suya.
"""

from __future__ import annotations

import json
import secrets
import shutil
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from untangle import paths
from untangle.base import Use
from untangle.providers import config as provider_config
from untangle.providers.ports import BudgetExhausted, ProviderError, ProviderErrorKind
from untangle.providers.transport import ProviderResponse
from untangle.server import manual_ledger, synthetic_draft
from untangle.settings import Settings
from untangle.synthetic_data import drafting, generator
from untangle.synthetic_data.canonical import sha256_hex
from untangle.synthetic_data.models import DraftText, PolicyPart
from untangle.telemetry.spend import api as spend
from untangle.tenancy import config as tenancy_config

from .apoyo import (
    COMPOSITORES,
    FabricaDoble,
    RegistroAnotado,
    TechoAnotado,
    clausula_redactada,
    foto_del_presupuesto,
    fuentes_minimas,
    repo,
    respuesta_de_gemini,
)

#: Un texto que no puede aparecer en ningun prompt: si aparece, salio de tmp/.
CENTINELA = "CENTINELA-DE-SPECIMEN-7731 texto de un formulario de terceros"


def _clave() -> str:
    """Una clave distinta en cada prueba, generada y nunca escrita a mano."""
    return f"test-{secrets.token_urlsafe(16)}"


def _pedido(part: PolicyPart = PolicyPart.PART_A, **opciones: Any) -> drafting.DraftRequest:
    aseguradora = tenancy_config.load().get("stonecroft")
    assert aseguradora is not None
    return drafting.request_for(aseguradora, part=part, **opciones)


def _referencia() -> str:
    return drafting.read_structure_reference(
        paths.policy_structure_reference_path(), repo_root=paths.repo_root()
    )


def _plataforma(
    respuesta: ProviderResponse, *, gastado: str = "0"
) -> tuple[synthetic_draft.DraftPlatform, FabricaDoble, TechoAnotado, RegistroAnotado, str]:
    eventos: list[str] = []
    fabrica = FabricaDoble(respuesta, eventos)
    techo = TechoAnotado(eventos, gastado=gastado)
    registro = RegistroAnotado()
    clave = _clave()
    plataforma = synthetic_draft.build_draft_platform(
        Settings(operations_model_api_key=clave),
        provider_config.load(),
        transports=fabrica,
        gate=techo,
        usage=registro,
    )
    return plataforma, fabrica, techo, registro, clave


def _borradores(carpeta: Path) -> list[Path]:
    """Los borradores escritos. Fuera de las pruebas asincronas: lee el disco."""
    return sorted(carpeta.rglob("*.yaml"))


async def _redactar(
    plataforma: synthetic_draft.DraftPlatform, destino: Path, pedido: drafting.DraftRequest
) -> drafting.DraftResult:
    return await drafting.draft_part(
        pedido,
        model=plataforma.model,
        reference=_referencia(),
        template=drafting.load_template(),
        drafts_dir=destino,
    )


# --- BR2.1: por la fabrica, con el uso operations, el techo y el gasto ---------


async def test_el_borrador_sale_por_la_fabrica_con_el_uso_operations_y_queda_en_tmp(
    tmp_path: Path,
) -> None:
    plataforma, fabrica, _, registro, clave = _plataforma(
        respuesta_de_gemini([clausula_redactada()])
    )

    resultado = await _redactar(plataforma, tmp_path / "borradores", _pedido())

    # Un solo cliente, el del uso operations, con su clave y ninguna otra.
    assert set(fabrica.creados) == {Use.OPERATIONS}
    assert fabrica.claves[Use.OPERATIONS] == clave
    (enviada,) = fabrica.enviadas
    assert enviada.path == "models/gemini-3.1-flash-lite:generateContent"
    # El techo se consulta antes de llamar, no despues.
    assert fabrica.eventos == ["techo:gemini:operations", "envio"]
    # El gasto va al registro, del uso operations y con lo que el proveedor conto.
    (reporte,) = registro.reports
    assert (reporte.use, reporte.model) == (Use.OPERATIONS, "gemini-3.1-flash-lite")
    assert [u.units for u in reporte.units] == [Decimal(900), Decimal(1200)]
    # El borrador, en tmp/, con su aviso y con el modelo exacto que lo redacto.
    assert resultado.path == tmp_path / "borradores/stonecroft/es/part_a.yaml"
    contenido = resultado.path.read_text(encoding="utf-8")
    assert contenido.startswith("# Borrador del modelo: NO es texto fuente.")
    releido = DraftText.model_validate(yaml.safe_load(contenido))
    assert releido == resultado.draft
    assert releido.model == "gemini-3.1-flash-lite"


# --- BR2.3: el prompt sale de la plantilla y de la referencia, y de nada mas ---


async def test_el_prompt_sale_solo_de_la_plantilla_versionada_y_de_la_referencia(
    tmp_path: Path,
) -> None:
    plataforma, fabrica, *_ = _plataforma(respuesta_de_gemini([clausula_redactada()]))

    resultado = await _redactar(plataforma, tmp_path, _pedido())

    cuerpo: Any = fabrica.enviadas[0].body
    instruccion = (drafting.TEMPLATE_DIR / "synthetic_draft.es.md").read_bytes()
    assert cuerpo["systemInstruction"] == {"parts": [{"text": instruccion.decode("utf-8").strip()}]}
    (turno,) = cuerpo["contents"]
    pedido = turno["parts"][0]["text"]
    # La raya de la referencia es una raya corta (U+2013), tal como esta escrita.
    assert "**Part A \u2013 Liability Coverage**" in pedido
    assert "**Part B" not in pedido
    assert "Encabezado de la parte (campo part): Parte A — Responsabilidad civil" in pedido
    assert "Aseguradora ficticia: Seguros Aburrá" in pedido
    assert "Distractores de esta parte" in pedido
    assert cuerpo["generationConfig"]["temperature"] == 0
    assert "responseSchema" in cuerpo["generationConfig"]
    plantilla = (drafting.TEMPLATE_DIR / "parts.yaml").read_bytes()
    assert resultado.draft.prompt_version == (
        f"synthetic_draft.es sha256:{sha256_hex(instruccion)}; "
        f"parts.yaml sha256:{sha256_hex(plantilla)}"
    )


def test_la_referencia_nunca_se_lee_desde_tmp(tmp_path: Path) -> None:
    for carpeta in ("specimens", "synthetic-drafts"):
        plantada = tmp_path / "tmp" / carpeta / "estructura-poliza-iso-pap.md"
        plantada.parent.mkdir(parents=True)
        plantada.write_text(CENTINELA, encoding="utf-8")

        with pytest.raises(drafting.DraftError, match="esta bajo tmp/"):
            drafting.read_structure_reference(plantada, repo_root=tmp_path)


def _repo_para_el_comando(tmp_path: Path) -> Path:
    """Un repositorio con configuracion y referencia de verdad, y un specimen plantado."""
    raiz = repo(tmp_path)
    shutil.copytree(paths.repo_root() / "app/config/providers", raiz / "app/config/providers")
    referencia = raiz / "docs/reference/estructura-poliza-iso-pap.md"
    referencia.parent.mkdir(parents=True)
    shutil.copy(paths.policy_structure_reference_path(), referencia)
    for nombre in ("pp-00-01.txt", "estructura-poliza-iso-pap.md"):
        specimen = raiz / "tmp/specimens" / nombre
        specimen.parent.mkdir(parents=True, exist_ok=True)
        specimen.write_text(CENTINELA, encoding="utf-8")
    return raiz


def _sin_base(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """El libro de gasto sin base, y el techo de verdad sobre un acumulado forzado."""
    filas: list[dict[str, Any]] = []

    def registro(*_: Any, **__: Any) -> str:
        return "sin-base"

    async def abrir(*_: Any, **__: Any) -> None:
        return None

    async def cerrar() -> Decimal | None:
        return Decimal(0)

    async def presupuesto(**_: Any) -> Any:
        return foto_del_presupuesto(gastado="0")

    async def libro(**campos: Any) -> None:
        filas.append(campos)

    monkeypatch.setattr(manual_ledger, "project_ledger_url", registro)
    monkeypatch.setattr(manual_ledger, "open_ledger", abrir)
    monkeypatch.setattr(manual_ledger, "close_ledger", cerrar)
    monkeypatch.setattr(spend, "budget_state", presupuesto)
    monkeypatch.setattr(spend, "record_spend", libro)
    return filas


def test_el_comando_entero_no_lleva_nada_de_tmp_specimens_al_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    raiz = _repo_para_el_comando(tmp_path)
    monkeypatch.setenv("UNTANGLE_REPO_ROOT", str(raiz))
    monkeypatch.setenv("UNTANGLE_OPERATIONS_MODEL_API_KEY", _clave())
    filas = _sin_base(monkeypatch)
    fabrica = FabricaDoble(respuesta_de_gemini([clausula_redactada()]))
    monkeypatch.setattr(synthetic_draft, "draft_transports", lambda: fabrica)

    codigo = synthetic_draft.main(["--tenant", "stonecroft", "--part", "part_a"])

    assert codigo == 0
    (enviada,) = fabrica.enviadas
    assert "CENTINELA" not in json.dumps(enviada.body, ensure_ascii=False)
    assert (raiz / "tmp/synthetic-drafts/stonecroft/es/part_a.yaml").is_file()
    # El gasto llego al libro mayor por el camino de verdad: dos filas, entrada y salida.
    assert [f["unit_kind"].value for f in filas] == ["input_tokens", "output_tokens"]
    # Y el acumulado que se imprime es el del libro del proyecto, no el de uno temporal.
    salida = capsys.readouterr().out
    assert "libro de gasto de la base del proyecto" in salida
    assert "Registro temporal" not in salida
    # El libro temporal ya no se ofrece: un gasto que se borra al terminar no cuenta.
    with pytest.raises(SystemExit):
        synthetic_draft.main(
            ["--tenant", "stonecroft", "--part", "part_a", "--ledger", "ephemeral"]
        )
    # Y el comando no ofrece ninguna forma de cambiar la referencia.
    with pytest.raises(SystemExit):
        synthetic_draft.main(
            ["--tenant", "stonecroft", "--part", "part_a", "--reference", "tmp/specimens/x"]
        )


# --- Si algo falla, no se escribe nada y no se reintenta ----------------------


async def test_con_el_techo_cerrado_no_se_llama_al_modelo_ni_se_escribe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plataforma, fabrica, *_ = _plataforma(
        respuesta_de_gemini([clausula_redactada()]), gastado="5.00"
    )

    with pytest.raises(BudgetExhausted):
        await _redactar(plataforma, tmp_path, _pedido())
    codigo = await synthetic_draft.run_drafts(
        plataforma,
        [_pedido()],
        reference=_referencia(),
        template=drafting.load_template(),
        drafts_dir=tmp_path,
    )

    assert codigo == 2
    assert "SE DETUVO" in capsys.readouterr().err
    assert fabrica.enviadas == []
    assert _borradores(tmp_path) == []


async def test_una_respuesta_que_no_cumple_el_esquema_no_deja_borrador(tmp_path: Path) -> None:
    # Un endoso sin su numero: el esquema lo rechaza dentro del adaptador.
    invalida = respuesta_de_gemini([clausula_redactada(kind="endorsement")])
    plataforma, fabrica, *_ = _plataforma(invalida)

    with pytest.raises(ProviderError) as error:
        await _redactar(plataforma, tmp_path, _pedido())

    assert error.value.kind is ProviderErrorKind.INVALID_RESPONSE
    assert len(fabrica.enviadas) == 1
    assert _borradores(tmp_path) == []


@pytest.mark.parametrize(
    ("respuesta", "codigo", "mensaje"),
    [
        (
            ProviderResponse(
                status_code=429,
                body={
                    "error": {
                        "status": "RESOURCE_EXHAUSTED",
                        "details": [{"reason": "QUOTA_EXCEEDED"}],
                    }
                },
            ),
            2,
            "SE DETUVO",
        ),
        (
            ProviderResponse(status_code=429, body={"error": {"status": "RESOURCE_EXHAUSTED"}}),
            1,
            "se retoma otro dia, sin cambiar de plan ni de clave (CG-U7-7)",
        ),
    ],
)
async def test_una_cuota_agotada_detiene_el_comando_sin_reintentar(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    respuesta: ProviderResponse,
    codigo: int,
    mensaje: str,
) -> None:
    plataforma, fabrica, *_ = _plataforma(respuesta)

    resultado = await synthetic_draft.run_drafts(
        plataforma,
        [_pedido(), _pedido(PolicyPart.PART_B)],
        reference=_referencia(),
        template=drafting.load_template(),
        drafts_dir=tmp_path,
    )

    assert resultado == codigo
    assert mensaje in capsys.readouterr().err
    # Una sola llamada: ni reintento ni la parte siguiente.
    assert len(fabrica.enviadas) == 1
    assert _borradores(tmp_path) == []


# --- El pedido: emisoras, variantes y notas para la revision ------------------


def test_una_agencia_o_una_variante_mal_pedida_no_llegan_a_llamar() -> None:
    agencia = tenancy_config.load().get("knotwell")
    assert agencia is not None
    with pytest.raises(drafting.DraftError, match="es una agencia"):
        drafting.request_for(agencia, part=PolicyPart.PART_A)

    plantilla = drafting.load_template()
    with pytest.raises(
        drafting.DraftError, match="pide --variant: with-transport, without-transport"
    ):
        drafting.build_prompt(
            _pedido(PolicyPart.ENDORSEMENTS), reference=_referencia(), template=plantilla
        )
    with pytest.raises(drafting.DraftError, match="no existe"):
        drafting.build_prompt(
            _pedido(PolicyPart.ENDORSEMENTS, variant="con-todo"),
            reference=_referencia(),
            template=plantilla,
        )
    with pytest.raises(drafting.DraftError, match="sobra --variant"):
        drafting.build_prompt(
            _pedido(variant="with-transport"), reference=_referencia(), template=plantilla
        )

    prompt = drafting.build_prompt(
        _pedido(PolicyPart.ENDORSEMENTS, variant="without-transport"),
        reference=_referencia(),
        template=plantilla,
    )
    pedido = prompt.parts[0].text
    assert "Ninguno de los cinco toca los gastos de transporte (D.TRANSPORT)." in pedido
    assert "**Part F" in pedido  # los endosos llevan la lista entera de la referencia


def test_las_notas_de_revision_dicen_lo_que_no_cuadra_con_el_pedido() -> None:
    pedido = _pedido()
    borrador = DraftText.model_validate(
        {
            "tenant_id": "stonecroft",
            "language": "es",
            "part": "part_a",
            "model": "gemini-3.1-flash-lite",
            "prompt_version": "prueba",
            "clauses": [
                clausula_redactada(part="Parte A"),
                clausula_redactada(
                    kind="distractor",
                    clause_key="A.EXCL.A.3.ALT",
                    distractor_of_key="A.EXCL.A.3",
                    distractor_reason="near_duplicate",
                ),
            ],
        }
    )

    notas = drafting.review_notes(borrador, pedido, drafting.load_template())

    assert notas == (
        "A.INS: encabezado 'Parte A', se pidio 'Parte A — Responsabilidad civil'",
        "1 distractor(es); se pidieron 2",
        "A.EXCL.A.3.ALT: se confunde con 'A.EXCL.A.3', que no esta en el borrador",
    )


# --- SEC-U7.4: un borrador plantado no cambia lo que se genera ------------------


def test_un_borrador_plantado_en_tmp_no_cambia_la_salida_del_generador(tmp_path: Path) -> None:
    raiz = repo(tmp_path / "repo")
    fuentes_minimas(raiz)
    solicitud = generator.GenerationRequest(
        repo_root=raiz, data_dir=tmp_path / "antes", composers=COMPOSITORES
    )
    generator.generate(solicitud)

    plantado = raiz / "tmp/synthetic-drafts/stonecroft/es/part_a.yaml"
    plantado.parent.mkdir(parents=True)
    plantado.write_text(
        yaml.safe_dump(
            {
                "tenant_id": "stonecroft",
                "language": "es",
                "part": "part_a",
                "model": "gemini-3.1-flash-lite",
                "prompt_version": "prueba",
                "clauses": [clausula_redactada(text="Texto del modelo que nadie reviso.")],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    generator.generate(
        generator.GenerationRequest(
            repo_root=raiz, data_dir=tmp_path / "despues", composers=COMPOSITORES
        )
    )

    antes = {
        p.relative_to(tmp_path / "antes"): p.read_bytes()
        for p in (tmp_path / "antes").rglob("*")
        if p.is_file()
    }
    despues = {
        p.relative_to(tmp_path / "despues"): p.read_bytes()
        for p in (tmp_path / "despues").rglob("*")
        if p.is_file()
    }
    assert antes == despues
    assert b"nadie reviso" not in b"".join(despues.values())
