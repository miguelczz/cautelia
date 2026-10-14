"""Valida los archivos versionados contra su esquema (paso 6 del guion).

Los esquemas se generan desde los modelos (C-28), asi que validar contra el
modelo y validar contra el esquema son la misma comprobacion. Lo que este
comando anade es **nombrar el archivo**: cargar todo de golpe diria que algo esta
mal sin decir que, y a las seis semanas eso cuesta una tarde.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from untangle import paths
from untangle.base import UnitKind, Use
from untangle.compliance.controls import patterns as compliance_patterns
from untangle.compliance.redaction.recognizers import loading as recognizer_loading
from untangle.copy_catalog.loading import CatalogLoadError, load_catalog
from untangle.evals import loading
from untangle.evals.gates import loading as gates_loading
from untangle.providers import config as provider_config
from untangle.rules import loading as rules_loading
from untangle.rules.conditions import ConditionError
from untangle.rules.models import RuleValidationError
from untangle.synthetic_data import fingerprints as corpus_fingerprints
from untangle.synthetic_data import manifest as corpus_manifest
from untangle.synthetic_data import sources as corpus_sources
from untangle.tenancy import config as tenant_config
from untangle.tenancy.models import TenantConfig, TenantConfigError
from untangle.tenancy.staff_identity import load_permissions

#: Cuanto puede llevar un tope sin comprobarse antes de dejar de contar como
#: control (BR5.8). El valor real de un tope vive **fuera** del aplicativo --en
#: la consola del proveedor-- y solo se puede afirmar mirandolo; a los treinta
#: dias, lo que la tabla dice de el es una creencia.
#:
#: La comprobacion vive aqui y no como restriccion del esquema porque se mide
#: contra la fecha de hoy: ningun JSON Schema la expresa, y una configuracion no
#: puede caducar sola mientras esta quieta en disco.
CAP_MAX_AGE_DAYS = 30


def run_all(root: Path | None = None) -> list[str]:
    """Devuelve un problema por archivo invalido, con su ruta."""
    base = root if root is not None else paths.repo_root()
    problemas: list[str] = []

    # Los casos, uno por uno, para poder nombrar el que falla.
    directorio = base / "app" / "evals" / "cases"
    casos = []
    for archivo in sorted(directorio.rglob("*.yaml"), key=lambda p: p.as_posix()):
        try:
            casos.append(loading.load_case(archivo))
        except loading.LoadError as error:
            problemas.append(str(error))

    # El manifiesto, y su recuento contra los archivos que hay (BR1.9).
    try:
        manifiesto = loading.load_manifest(base / "app" / "evals" / "manifest.yaml")
        problemas.extend(loading.check_manifest_counts(manifiesto, tuple(casos)))
    except loading.LoadError as error:
        problemas.append(str(error))

    # La paridad por idioma: todo caso tiene su pareja en el otro idioma (P12,
    # NFR20.2). Sin ella, una metrica se publicaria de un solo lado.
    problemas.extend(loading.check_language_parity(tuple(casos)))

    # Los subconjuntos, y que cada identificador exista como archivo.
    subconjuntos = base / "app" / "evals" / "subsets"
    for archivo in sorted(subconjuntos.glob("*.yaml"), key=lambda p: p.as_posix()):
        try:
            definicion = loading.load_subset(archivo.stem, subconjuntos)
            loading.resolve_subset_cases(definicion, tuple(casos))
        except loading.LoadError as error:
            problemas.append(str(error))

    # El catalogo.
    try:
        load_catalog(base / "app" / "config" / "copy")
    except CatalogLoadError as error:
        problemas.append(str(error))

    problemas.extend(_revisar_memoria_entre_corridas(base))
    problemas.extend(_revisar_configuracion_por_aseguradora(base))
    problemas.extend(_revisar_reconocedores())
    problemas.extend(revisar_patrones_de_cumplimiento(base / "app" / "config" / "compliance"))
    problemas.extend(revisar_proveedores(base / "app" / "config" / "providers"))
    problemas.extend(revisar_corpus(base))

    return problemas


def revisar_corpus(base: Path) -> list[str]:
    """Las fuentes del generador y el arbol de `app/data/` contra su manifiesto (U7).

    Dos preguntas distintas (TECH-U7.2, BR2.2). Las fuentes se validan en cuanto
    existen, con o sin corpus: un texto sin marca de revision se nombra el dia que
    se escribe, no el dia que alguien intenta generar. El arbol se compara con el
    manifiesto en cuanto hay uno; antes de la primera generacion no hay nada que
    comparar, y `main` lo dice como "no medido".
    """
    problemas = corpus_manifest.verify_tree(base)
    problemas.extend(revisar_huellas(base))
    fuentes = base / "app" / "data" / "sources"
    if fuentes.is_dir():
        try:
            aseguradoras = tenant_config.load(base / "app" / "config" / "tenants")
            corpus_sources.load_sources(fuentes, repo_root=base, tenants=aseguradoras)
        except corpus_sources.SourceLoadError as error:
            problemas.extend(error.problems)
        except TenantConfigError as error:
            problemas.append(str(error))
    return problemas


def revisar_huellas(base: Path) -> list[str]:
    """El archivo de huellas de terceros contra su modelo, si existe (U7, SEC-U7.2).

    Que exista lo exige `content:check`, que sin el declara "no medido" y falla
    (BR5.3); aqui se comprueba su **forma**: solo hashes, ordenados y sin repetir,
    y ningun campo de mas donde pudiera caber una secuencia legible.
    """
    archivo = base / "app" / "config" / "content" / "third-party-shingles.json"
    if not archivo.is_file():
        return []
    try:
        corpus_fingerprints.load_fingerprint_set(archivo)
    except corpus_fingerprints.FingerprintError as error:
        return [str(error)]
    return []


def stale_caps(prices: provider_config.PricesConfig, today: date) -> list[str]:
    """Los topes que llevan demasiado sin comprobarse, nombrando cada uno.

    Se devuelve una linea por tope y no un recuento: quien lo lee tiene que ir a
    la consola de ese proveedor, y para eso necesita saber cual.
    """
    problemas: list[str] = []
    for tope in prices.caps:
        antiguedad = (today - tope.last_checked_at).days
        if antiguedad > CAP_MAX_AGE_DAYS:
            problemas.append(
                f"el tope de '{tope.provider}' para el uso '{tope.use}' se comprobo el "
                f"{tope.last_checked_at}, hace {antiguedad} dias: por encima de "
                f"{CAP_MAX_AGE_DAYS} deja de contar como control. Mirelo en la consola "
                "del proveedor y actualice 'last_checked_at'"
            )
    return problemas


def missing_speech_caps(config: provider_config.ProviderPlatformConfig) -> list[str]:
    """Los proveedores de voz que no declaran su tope del uso `voice` (PA-9.2).

    Un proveedor de voz sin fila de tope es un gasto que nada detiene del lado del
    proveedor cuando lo que falla es la aplicacion, y se lee igual de bien que uno
    que si la tiene: por eso se exige su presencia y no solo su vigencia. Una
    linea por proveedor, con el uso y el archivo donde escribirla.
    """
    declarados = {(tope.provider, tope.use) for tope in config.prices.caps}
    return [
        f"el proveedor de voz '{proveedor.value}' no declara su tope del uso 'voice' en "
        f"{provider_config.PRICES_FILE}: todo proveedor con modelo de transcripcion o de "
        "sintesis dice que lo detiene del lado del proveedor y cuando se comprobo (PA-9.2)"
        for proveedor in config.providers.speech_providers()
        if (proveedor, Use.VOICE) not in declarados
    ]


def unpriced_call_reserve(config: provider_config.ProviderPlatformConfig) -> list[str]:
    """Los componentes de la reserva por llamada que la tabla no sabe valorar.

    La reserva es la suma de tres consumos --transcripcion, sintesis y modelo-- y
    si a cualquiera le falta su linea, la reserva **no se sabe**: el cupo diario del
    sitio sale cero y el enlace publico de voz no abre ninguna llamada. Eso paso
    hasta la tanda 2 de U17, y durante semanas se leyo como "todavia no hay precio
    de la voz" en vez de como lo que era.
    """
    consumo = config.providers.call_reserve
    componentes = (
        (consumo.transcription.provider, consumo.transcription.model, UnitKind.AUDIO_SECONDS),
        (consumo.synthesis.primary.provider, consumo.synthesis.primary.model, UnitKind.CHARACTERS),
        (
            consumo.synthesis.fallback.provider,
            consumo.synthesis.fallback.model,
            UnitKind.CHARACTERS,
        ),
        (consumo.model.provider, consumo.model.model, UnitKind.INPUT_TOKENS),
        (consumo.model.provider, consumo.model.model, UnitKind.OUTPUT_TOKENS),
    )
    declarados = {
        (linea.provider.value, linea.model, linea.unit_kind)
        for linea in config.prices.price_entries()
    }
    return [
        f"la reserva por llamada declara '{proveedor} / {modelo}' en "
        f"'{clase.value}' y {provider_config.PRICES_FILE} no lo valora: sin ese precio "
        "la reserva no se sabe, el cupo diario del sitio sale cero y el enlace "
        "publico de voz no abre ninguna llamada"
        for proveedor, modelo, clase in componentes
        if (proveedor, modelo, clase) not in declarados
    ]


def revisar_proveedores(folder: Path, today: date | None = None) -> list[str]:
    """Los dos archivos de la carpeta de proveedores, la presencia de los topes de
    la voz y la vigencia de todos.

    `today` se inyecta para poder probar la caducidad sin esperar un mes ni
    mover el reloj de la maquina.
    """
    try:
        configuracion = provider_config.load(folder)
    except provider_config.ProviderConfigError as error:
        return [str(error)]

    fecha = today if today is not None else datetime.now(UTC).date()
    return (
        missing_speech_caps(configuracion)
        + stale_caps(configuracion.prices, fecha)
        + unpriced_call_reserve(configuracion)
    )


def _revisar_linea_base(base: Path) -> list[str]:
    """La linea base vigente y las publicadas por hito, si existen (U21, BR2.1)."""
    problemas: list[str] = []
    directorio = base / "app" / "evals" / "baselines"

    vigente = directorio / "current.json"
    if vigente.is_file():
        try:
            gates_loading.load_baseline(vigente)
        except loading.LoadError as error:
            problemas.append(str(error))

    for archivo in sorted(directorio.glob("*.json")):
        if archivo.name == "current.json":
            continue
        try:
            gates_loading.load_baseline(archivo)
        except loading.LoadError as error:
            problemas.append(str(error))

    return problemas


def _revisar_resumen_de_la_ultima_corrida(base: Path) -> list[str]:
    """El resumen de la ultima corrida completa, si existe (U22, FD-U22-10)."""
    try:
        gates_loading.load_last_run_digest(base / "app" / "evals" / "last-run.json")
    except loading.LoadError as error:
        return [str(error)]
    return []


def _revisar_inestables_y_explicaciones(base: Path) -> list[str]:
    """Los casos inestables y las explicaciones de regresion (U21, BR2.2, BR2.4)."""
    problemas: list[str] = []

    try:
        gates_loading.load_unstable_cases(base / "app" / "evals" / "unstable-cases.yaml")
    except loading.LoadError as error:
        problemas.append(str(error))

    # La compuerta trata un archivo de explicaciones roto como "sin
    # explicaciones" (REL-U21.5, "el fallo es hacia el lado seguro"); aqui se
    # audita aparte, con la version que si propaga el error, porque
    # `schema:check` es la unica compuerta que nombra un archivo roto.
    archivo_explicaciones = base / "app" / "evals" / "regressions.yaml"
    if archivo_explicaciones.is_file():
        try:
            gates_loading.validate_regression_explanations_file(archivo_explicaciones)
        except loading.LoadError as error:
            problemas.append(str(error))

    return problemas


def _revisar_etiquetas(base: Path) -> list[str]:
    """Las etiquetas de DS-7 y su cola de turnos por etiquetar (U21, FD-U21-3)."""
    problemas: list[str] = []
    directorio_etiquetas = base / "app" / "evals" / "labels"

    for idioma in ("es", "en"):
        if (directorio_etiquetas / f"{idioma}.yaml").is_file():
            try:
                gates_loading.load_labels(idioma, directorio_etiquetas)
            except loading.LoadError as error:
                problemas.append(str(error))

    cola = directorio_etiquetas / "queue.yaml"
    if cola.is_file():
        try:
            gates_loading.load_labeling_queue(cola)
        except loading.LoadError as error:
            problemas.append(str(error))

    return problemas


def _revisar_calibracion(base: Path) -> list[str]:
    """Los veredictos grabados del juez y sus calibraciones (U21, BR3.1, BR3.2)."""
    problemas: list[str] = []

    directorio_veredictos = base / "app" / "evals" / "judge-verdicts"
    if directorio_veredictos.is_dir():
        for archivo in sorted(directorio_veredictos.glob("*.yaml")):
            try:
                gates_loading.validate_judge_verdicts_file(archivo)
            except loading.LoadError as error:
                problemas.append(str(error))

    directorio_calibraciones = base / "app" / "evals" / "calibrations"
    if directorio_calibraciones.is_dir():
        for archivo in sorted(directorio_calibraciones.glob("*.json")):
            try:
                gates_loading.load_calibration_file(archivo)
            except loading.LoadError as error:
                problemas.append(str(error))

    return problemas


def _revisar_memoria_entre_corridas(base: Path) -> list[str]:
    """La memoria entre corridas de U21: linea base, inestables, explicaciones,
    etiquetas y calibracion del juez (CG-U21-1).

    Todos son opcionales al principio de un proyecto -- sin hito publicado no
    hay linea base, sin regresion no hay explicacion, sin etiquetado local no
    hay calibracion -- asi que un archivo ausente no es un problema; uno
    presente y roto si lo es, nombrado.
    """
    return (
        _revisar_linea_base(base)
        + _revisar_resumen_de_la_ultima_corrida(base)
        + _revisar_inestables_y_explicaciones(base)
        + _revisar_etiquetas(base)
        + _revisar_calibracion(base)
    )


def _revisar_reconocedores() -> list[str]:
    """Los dos juegos de reconocedores de la redaccion (BR2.6, BR2.7).

    Uno por idioma, validado por separado para poder nombrar el que falla. Se
    valida aqui y no solo al arrancar porque un juego roto **no se manifiesta**:
    el aplicativo sigue emitiendo texto, solo que con el dato dentro.
    """
    problemas: list[str] = []
    for idioma in recognizer_loading.LOCALES:
        try:
            recognizer_loading.load_recognizer_set(idioma)
        except recognizer_loading.RecognizerLoadError as error:
            problemas.append(str(error))
    return problemas


def revisar_patrones_de_cumplimiento(folder: Path) -> list[str]:
    """Los ocho archivos de patrones de los controles de cumplimiento (U10, TECH-U10.1).

    Se validan uno por uno para nombrar el que falla, y despues juntos, porque
    dos propiedades son del conjunto y no de un archivo: que cada idioma cubra
    las siete categorias de la guardia y que los dos eximan las mismas claves.
    Se valida aqui y no solo al arrancar por la misma razon que los
    reconocedores: un patron que nunca coincide **no se manifiesta**, la frase
    sale igual.
    """
    problemas: list[str] = []
    for familia in compliance_patterns.PatternFamily:
        for idioma in compliance_patterns.LOCALES:
            try:
                compliance_patterns.load_pattern_set(idioma, familia, folder)
            except compliance_patterns.PatternLoadError as error:
                problemas.append(str(error))
    if problemas:
        return problemas
    try:
        compliance_patterns.load_library(folder)
    except compliance_patterns.PatternLoadError as error:
        problemas.append(str(error))
    return problemas


def _revisar_significado_de_reglas(carpeta: Path) -> list[str]:
    """El significado de `rules/triage.yaml`, no solo su forma (BR1.1 a BR1.4).

    `tenant_config.load_tenant` ya valido la forma del archivo con
    `RuleSet.model_validate`; lo que falta es lo que decide U9: el conteo de
    10 a 20, los operadores cerrados, la regla por defecto y las pruebas de
    cada regla. Se revalida aqui en vez de reusar `rules.loading.load_rulesets`
    porque ese cargador lee la lista de aseguradoras de la configuracion **ya
    instalada** del proceso (`tenancy_config.loaded()`), que no tiene por que
    coincidir con `base` cuando este comando corre sobre un arbol de prueba.
    """
    archivo = carpeta / tenant_config.RULES_DIR / rules_loading.RULESET_FILE
    if not archivo.is_file():
        return []
    try:
        crudo = tenant_config.load_ruleset(archivo)
        rules_loading.validate_ruleset(crudo, tenant_id=carpeta.name)
    except (TenantConfigError, ConditionError, RuleValidationError) as error:
        return [str(error)]
    return []


def _revisar_configuracion_por_aseguradora(base: Path) -> list[str]:
    """Las carpetas de aseguradora y la tabla de permisos (C-25, BR4.1).

    Cada carpeta se valida **por separado** a proposito: una rota tiene que poder
    nombrarse sin que las otras dos desaparezcan del informe.
    """
    problemas: list[str] = []

    directorio = base / "app" / "config" / "tenants"
    if directorio.is_dir():
        for carpeta in sorted(p for p in directorio.iterdir() if p.is_dir()):
            try:
                aseguradora = tenant_config.load_tenant(carpeta)
            except TenantConfigError as error:
                problemas.append(str(error))
                continue
            problemas.extend(_revisar_significado_de_reglas(carpeta))
            problemas.extend(_revisar_emisor_de_la_poliza_de_ejemplo(base, aseguradora))

    try:
        load_permissions(base / "app" / "config" / "role-permissions.yaml")
    except TenantConfigError as error:
        problemas.append(str(error))

    return problemas


def _revisar_emisor_de_la_poliza_de_ejemplo(base: Path, tenant: TenantConfig) -> list[str]:
    """Lo declarado contra el `issuer_tenant` de la poliza versionada (Q2 de U23).

    Es la mitad que hacia dudar de poner el emisor en la configuracion: dos fuentes
    que pueden discrepar. Con el chequeo, discrepar **falla**, que es la diferencia
    entre declarar y adivinar. La alternativa era que el inicio leyera un archivo del
    corpus, y eso cruzaba una frontera que su docstring declara a proposito.

    Comprueba las dos direcciones: que la agencia nombre a quien de verdad emitio, y
    que la poliza de una emisora diga que la emitio ella.
    """
    archivo = (
        base
        / "app"
        / "data"
        / "tenants"
        / tenant.tenant_id
        / "issued_policies"
        / f"{tenant.example_policy}.json"
    )
    if not archivo.is_file():
        # Que la poliza de ejemplo exista entre las emitidas ya lo comprueba el
        # generador, que tiene el conjunto; aqui no se repite el aviso.
        return []

    try:
        datos = json.loads(archivo.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"'{archivo}': no se puede leer ({error})"]

    emisor_real = datos.get("issuer_tenant")
    esperado = tenant.example_policy_issuer or tenant.tenant_id
    if emisor_real != esperado:
        declarado = (
            f"declara 'example_policy_issuer: {tenant.example_policy_issuer}'"
            if tenant.example_policy_issuer is not None
            else "no declara 'example_policy_issuer', asi que emite sus polizas"
        )
        return [
            f"'app/config/tenants/{tenant.tenant_id}/tenant.yaml': {declarado}, pero "
            f"'{archivo.name}' dice que la emitio '{emisor_real}'"
        ]
    return []


def main() -> int:
    problemas = run_all()
    aviso = corpus_manifest.corpus_notice(paths.data_dir())
    if aviso is not None:
        print(aviso)
    for problema in problemas:
        print(problema, file=sys.stderr)
    if problemas:
        print(f"\n{len(problemas)} archivo(s) versionado(s) no validan", file=sys.stderr)
        return 1
    print("aserciones de esquema: los archivos versionados validan")
    return 0


if __name__ == "__main__":
    sys.exit(main())
