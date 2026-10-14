"""Las evaluaciones que llaman a Claude: la comprension (fase 0) y las citas (fase 1).

    mise run evals:entender
    mise run evals:citas
    mise run evals:conversaciones
    mise run evals:completa

Corre el subconjunto `entender` --los casos `DS-2/*/understand-*`-- contra Claude
Haiku 5.5, por el **mismo puerto** que usa el chat: el que construye
`composition.build_understander`, con la clave de evaluaciones
(`UNTANGLE_ANTHROPIC_API_KEY_EVALS`) y su gasto atribuido al uso `evals`, para que
una corrida no gaste el saldo que atiende a los visitantes.

`evals:citas` corre los casos de DS-3 por `PolicyVerificationNode.answer`
--recuperar, proponer las citas con Claude y verificarlas--, sobre la base del
proyecto, que es la que tiene el corpus cargado. Corre ademas RT-2 por clausula
envenenada (2026-10-12): el mismo proponedor de citas, con la clausula del fixture de
inyeccion entregada a mano, y sin tocar la base.

**No corren en GitHub Actions**: llaman a un modelo de pago (centavos por corrida). Se
corre a mano al cambiar la comprension y en cada hito. Pasan por el techo y el libro de
gasto como cualquier llamada, y el libro es **siempre el de la base del proyecto**
(2026-10-13): `entender` corria sobre una base desechable que se destruia al terminar, y
sus 33 corridas del 7 al 13 de octubre gastaron unos 0,24 USD que no quedaron en ningun
libro ni contaron contra el techo. Sin `UNTANGLE_DATABASE_URL`, o con la base apagada, no
llaman a nadie y dicen que falta.

Vive en `untangle.server` y no en `untangle.evals` por la misma razon que
`voice_cli`: necesita a la vez el corredor y la raiz de composicion, y no hay otra
capa donde las dos se encuentren.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from untangle import paths
from untangle.base import Use
from untangle.evals import (
    citation_probes,
    injection_probes,
    transcript_recorder,
    understanding_probes,
)
from untangle.evals import cli as evals_cli
from untangle.evals.drivers import chat as chat_driver
from untangle.evals.gates.baseline import build_digest
from untangle.evals.gates.gate import blocking_criteria_from_registry
from untangle.evals.gates.loading import save_last_run_digest
from untangle.evals.runner import runner
from untangle.orchestration import turn as orchestration_turn
from untangle.orchestration.nodes.policy_verification import node as policy_verification_node
from untangle.orchestration.nodes.policy_verification.proposal import ProposerPort
from untangle.providers import config as provider_config
from untangle.server import composition, corpus_ingest, manual_ledger
from untangle.settings import EVALS_ANTHROPIC_API_KEY_VAR, Settings
from untangle.tenancy import api as tenancy

#: `completa` es la corrida entera (2026-10-09): ademas de lo de `citas`, arma la
#: aplicacion con la clave de evaluaciones para que el conductor del chat converse
#: con el grafo de verdad sobre la base del proyecto. **Deja su resumen versionado**
#: en `app/evals/last-run.json`, en verde o en rojo (2026-10-11): es lo que lee el
#: tablero "Que tan bien funciona". Antes solo escribia en `tmp/`, y una corrida de
#: 178 casos se perdio con el reinicio de la sesion.
#: `conversaciones` arma la aplicacion igual que `completa` y corre solo los casos
#: del chat (2026-10-11): centavos, y sin resumen versionado.
SUBSETS = ("entender", "citas", "conversaciones", "completa")
#: Los que conversan con el grafo de verdad y por eso arman la aplicacion.
_CON_APLICACION = ("conversaciones", "completa")

#: Los modelos que una corrida de texto puede usar: los que generan y el que
#: calcula los embeddings. La voz no corre aqui.
_DE_TEXTO = (provider_config.ModelKind.GENERATION, provider_config.ModelKind.EMBEDDING)


def pinned_models(config: provider_config.ProviderPlatformConfig) -> dict[str, str]:
    """Los modelos de texto anclados en la configuracion, por proveedor y uso.

    Salen de la carpeta versionada de proveedores, que es de donde los toma cada
    cliente: es el identificador exacto con el que corrio la corrida.
    """
    anclados: dict[str, str] = {}
    for proveedor in config.providers.providers:
        for modelo in proveedor.models:
            if modelo.kind not in _DE_TEXTO:
                continue
            clave = f"{proveedor.name.value}:{modelo.kind.value}"
            # Un proveedor con dos modelos del mismo uso: se nombran los dos.
            while clave in anclados:
                clave += "+"
            anclados[clave] = modelo.id
    return anclados


def install_citation_probes(
    responder: citation_probes.Answerer, proponedor: ProposerPort | None
) -> None:
    """Instala lo que miden `citas` y `completa`: quien responde las preguntas de DS-3 y el
    proponedor de citas de verdad para RT-2 por clausula envenenada (2026-10-12).

    El mismo proponedor que el nodo: a la sonda de RT-2 se le entrega a mano la clausula del
    fixture y mide si obedece la orden que trae. Sin clave es `None` y el caso queda no medido.
    """
    citation_probes.install(responder)
    injection_probes.install(proponedor)


def _analizador() -> argparse.ArgumentParser:
    analizador = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    analizador.add_argument("--subset", choices=SUBSETS, default="entender")
    analizador.add_argument("--out", type=Path, default=None, help="donde escribir el reporte")
    return analizador


def main(argv: list[str] | None = None) -> int:
    argumentos = _analizador().parse_args(argv)
    ajustes = Settings()
    config = provider_config.load()
    tenancy.install(tenancy.load())

    entendedor = composition.build_understander(ajustes, config, for_evals=True)
    if entendedor is None:
        print(
            f"falta {EVALS_ANTHROPIC_API_KEY_VAR}: la comprension se evalua con su propia "
            "clave, separada de la del chat. Sin ella no se llama a nadie.",
            file=sys.stderr,
        )
        return 2
    # El libro se exige antes de armar nada: sin la base del proyecto no se llama a nadie.
    url = manual_ledger.project_ledger_url(
        ajustes, purpose=f"evaluacion contra Claude ({argumentos.subset})"
    )

    evals_cli.register_all_probes()
    understanding_probes.install(lambda: entendedor)
    completa = argumentos.subset == "completa"
    aplicacion = (
        composition.build_app(ajustes, for_evals=True)
        if argumentos.subset in _CON_APLICACION
        else None
    )
    if argumentos.subset in ("citas", "completa"):
        proponedor = composition.build_citation_proposer(ajustes, config, for_evals=True)
        plataforma = composition.build_provider_platform(ajustes, config)
        nodo = policy_verification_node.PolicyVerificationNode(
            embed=lambda textos: plataforma.embedder.embed(textos, use=Use.CORPUS),
            embedding_model=corpus_ingest.embedding_model_for(config.providers).model_id,
            clock=lambda: datetime.now(UTC),
            propose=proponedor,
        )

        async def responder(pregunta: citation_probes.CitationQuestion) -> tuple[Any, Any]:
            return await nodo.answer(
                policy_verification_node.PolicyVerificationNodeInput(
                    tenant_id=pregunta.tenant_id,
                    case_id=pregunta.case_ref,
                    turn_id=pregunta.case_ref,
                    policy_number=pregunta.policy_number,
                    question=pregunta.question,
                    answer_language=pregunta.language,
                ),
                now=datetime.now(UTC),
            )

        install_citation_probes(responder, proponedor)

    modelos = pinned_models(config)
    # Las corridas que conversan guardan lo que la agente dijo, ya redactado, para armar la
    # cola de etiquetado de DS-7 (`mise run evals:label:queue`). El reporte solo guarda
    # veredictos por caso. Las otras corridas no conversan y no tienen nada que guardar.
    grabador = transcript_recorder.TranscriptRecorder() if aplicacion is not None else None
    if aplicacion is not None:
        # Al terminar cada conversacion, la oferta de datos opcionales que nadie contesto se da
        # por rechazada, como hace el chat a los dos minutos (2026-10-14).
        chat_driver.install_review_settler(
            lambda case_id, tenant_id: orchestration_turn.settle_review(
                case_id, tenant_id=tenant_id
            )
        )

    async def _correr() -> tuple[runner.RunOutcome, object]:
        await manual_ledger.open_ledger(config, url)
        if aplicacion is None:
            try:
                resultado = await runner.run_evaluation(
                    subset=argumentos.subset, settings=ajustes, model_ids=modelos
                )
            finally:
                gastado = await manual_ledger.close_ledger()
            return resultado, gastado
        # El arranque de la aplicacion carga el detector de datos personales y
        # comprueba el aislamiento, igual que al servir. El acumulado se lee
        # **antes** de salir: al apagarse suelta la base, y leerlo despues daba
        # "None USD" aunque el gasto si quedo registrado (2026-10-09).
        async with aplicacion.router.lifespan_context(aplicacion):
            try:
                resultado = await runner.run_evaluation(
                    subset=None if completa else argumentos.subset,
                    settings=ajustes,
                    model_ids=modelos,
                    recorder=grabador,
                )
            finally:
                gastado = await manual_ledger.close_ledger()
        return resultado, gastado

    resultado, gastado = asyncio.run(_correr())

    destino = argumentos.out or (paths.reports_dir() / f"{resultado.run.run_id}.json")
    escrito = evals_cli.write_report(resultado.report, destino)
    print(evals_cli.summarize(resultado.report))
    print(f"gasto acumulado de la ventana: {gastado} USD")
    print(f"reporte: {escrito}")
    guardado = (
        None
        if grabador is None
        else grabador.save(
            run_id=resultado.run.run_id,
            commit_sha=resultado.run.commit_sha,
            now=datetime.now(UTC),
        )
    )
    if guardado is not None:
        print(f"transcripciones (redactadas): {guardado}")
        print("para etiquetar: mise run evals:label:queue")
    if completa:
        # En verde o en rojo: el tablero muestra la ultima corrida como salio.
        resumen = save_last_run_digest(
            build_digest(
                resultado.report,
                blocking_criteria=blocking_criteria_from_registry(),
                dirty_tree=runner.tree_is_dirty(paths.repo_root()),
            )
        )
        print(f"resumen versionado de la corrida completa: {resumen}")
    return resultado.exit_code


if __name__ == "__main__":
    sys.exit(main())
