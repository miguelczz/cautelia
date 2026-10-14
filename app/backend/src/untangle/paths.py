"""Donde estan los archivos versionados del aplicativo.

Un solo lugar resuelve las rutas. Si cada modulo las calculara por su cuenta, dos
de ellos acabarian buscando el catalogo en sitios distintos segun desde donde se
invoque el comando, y eso es una diferencia entre dos corridas del mismo commit.

La raiz se busca por el archivo de tareas, que es el unico archivo que esta
siempre en la raiz del repositorio y en ningun subdirectorio. `UNTANGLE_REPO_ROOT`
la sobreescribe: es lo que usan las pruebas para trabajar sobre un arbol
temporal.
"""

from __future__ import annotations

import os
from pathlib import Path

_MARCADOR_DE_RAIZ = "mise.toml"


class RepoRootNotFoundError(RuntimeError):
    """No se encontro la raiz del repositorio."""


def repo_root() -> Path:
    """La raiz del repositorio, o un fallo que dice donde se busco."""
    override = os.environ.get("UNTANGLE_REPO_ROOT")
    if override:
        raiz = Path(override).resolve()
        if not (raiz / _MARCADOR_DE_RAIZ).is_file():
            msg = f"UNTANGLE_REPO_ROOT apunta a '{raiz}', que no contiene '{_MARCADOR_DE_RAIZ}'"
            raise RepoRootNotFoundError(msg)
        return raiz

    aqui = Path(__file__).resolve()
    for candidata in aqui.parents:
        if (candidata / _MARCADOR_DE_RAIZ).is_file():
            return candidata

    msg = (
        f"no se encontro '{_MARCADOR_DE_RAIZ}' subiendo desde '{aqui}'; "
        "defina UNTANGLE_REPO_ROOT si el aplicativo corre fuera del repositorio"
    )
    raise RepoRootNotFoundError(msg)


def app_dir() -> Path:
    """El prefijo unico del aplicativo (convencion 1 del equipo)."""
    return repo_root() / "app"


def copy_dir() -> Path:
    """Los archivos del catalogo de textos, uno por idioma."""
    return app_dir() / "config" / "copy"


def config_dir() -> Path:
    """Los archivos de configuracion versionados del aplicativo."""
    return app_dir() / "config"


def tenants_dir() -> Path:
    """Una carpeta por aseguradora (C-25).

    Anadir una cuarta aseguradora es anadir un directorio aqui: quien las carga
    recorre este arbol y no una lista escrita a mano (FR9.3).
    """
    return config_dir() / "tenants"


def providers_dir() -> Path:
    """Los dos archivos que declaran proveedores, planes, precios y topes.

    Vive fuera de las carpetas de aseguradora porque no es una diferencia entre
    aseguradoras: el techo es uno solo para el proyecto, y el gasto que no tiene
    aseguradora ninguna --evaluaciones, generacion, operacion-- se paga del mismo
    bolsillo.
    """
    return config_dir() / "providers"


def prompts_dir() -> Path:
    """Un archivo por nodo y por idioma, con su identificador y su hash (BR1.7).

    Fuera de las carpetas de aseguradora: el prompt de un nodo es el mismo para
    las tres, y lo que cambia entre ellas --reglas, politicas, voz, corpus-- vive
    en su carpeta. Un prompt por aseguradora multiplicaria por tres lo que hay
    que volver a evaluar cada vez que se toca una palabra.
    """
    return config_dir() / "prompts"


def compliance_dir() -> Path:
    """Los patrones versionados de los controles de cumplimiento (U10, CG-U10-1).

    Un directorio por idioma y un archivo por familia: la guardia de salida, la
    peticion de persona, la pregunta de identidad y la emergencia. Fuera de las
    carpetas de aseguradora porque ningun criterio distingue aseguradoras aqui
    (FD-U10-5): un patron por aseguradora multiplicaria por tres lo que hay que
    volver a evaluar cada vez que se toca una expresion.
    """
    return config_dir() / "compliance"


def intake_dir() -> Path:
    """La tabla de deletreo versionada del nodo `intake` (U11, BR2.4, BR2.5).

    Un solo archivo, fuera de las carpetas de aseguradora: leer una placa o una
    poliza en voz alta no cambia entre aseguradoras, y reconocerla dictada
    tampoco (convencion 9 del equipo).
    """
    return config_dir() / "intake"


def role_permissions_path() -> Path:
    """La tabla versionada de rol y accion.

    Vive fuera de las carpetas de aseguradora a proposito: los permisos no son
    una diferencia entre aseguradoras, y ponerlos ahi dejaria que una se conceda
    a si misma la aprobacion (decision Q4 del diseno funcional de U2).
    """
    return config_dir() / "role-permissions.yaml"


def backend_dir() -> Path:
    """El proyecto del servidor."""
    return app_dir() / "backend"


def migrations_dir() -> Path:
    """La historia unica de migraciones (C-30).

    Una sola para las once unidades que crean tablas: dos cabezas son un
    conflicto que la compuerta rechaza, no algo que se resuelva en produccion.
    """
    return backend_dir() / "migrations"


def db_init_dir() -> Path:
    """El arranque de la base: el rol del aplicativo, sin privilegio de salto.

    El mismo directorio lo monta el entorno local y la base efimera de las
    pruebas, para que haya **un solo camino** y no dos que se parezcan.
    """
    return repo_root() / "scripts" / "db-init"


def data_dir() -> Path:
    """El corpus y las fixtures generadas (C-26)."""
    return app_dir() / "data"


def fixtures_dir() -> Path:
    """Las fixtures versionadas, entre ellas las colisiones de DS-8."""
    return data_dir() / "fixtures"


def synthetic_sources_dir() -> Path:
    """Los textos fuente revisados de los que sale todo el corpus (U7, FD-U7-3).

    Viven junto a la salida, en `app/data/`, pero son **entrada**: el manifiesto
    los cuenta como tales y el generador nunca escribe aqui.
    """
    return data_dir() / "sources"


def synthetic_manifest_path() -> Path:
    """El manifiesto de la generacion del corpus (C-26, BR1.4)."""
    return data_dir() / "manifest.json"


def corpus_tenants_dir() -> Path:
    """Una carpeta por aseguradora dentro del corpus generado (C-26, U8).

    No es `tenants_dir()`: esa es la configuracion de U2 en `app/config/`, y
    esta es el corpus de polizas de U7 en `app/data/`. Los dos se llaman
    "aseguradora" y viven en arboles distintos por razones distintas.
    """
    return data_dir() / "tenants"


def synthetic_drafts_dir() -> Path:
    """Los borradores que devuelve el modelo al redactar (U7, BR2.1).

    En `tmp/`, que git ignora: un borrador no es dato del proyecto hasta que
    alguien lo revisa y lo promueve a `app/data/sources/`. **Solo el comando de
    redaccion** usa esta ruta; ningun modulo de la composicion la conoce, y una
    prueba lo comprueba.
    """
    return repo_root() / "tmp" / "synthetic-drafts"


def specimens_dir() -> Path:
    """Donde Miguel deja los specimens publicos para sacar sus huellas (U7, BR5.1).

    En `tmp/`, que git ignora: el texto de un formulario de terceros no entra al
    repositorio ni siquiera como material de comparacion (SEC-U7.2). Lo lee solo
    el comando de huellas; la redaccion no tiene ninguna ruta hacia aqui (BR2.3).
    """
    return repo_root() / "tmp" / "specimens"


def policy_structure_reference_path() -> Path:
    """La estructura de la poliza de referencia: partes y numeracion, sin texto (P8).

    Es la unica fuente del prompt de redaccion, ademas de la plantilla versionada
    del paquete (BR2.3).
    """
    return repo_root() / "docs" / "reference" / "estructura-poliza-iso-pap.md"


def cases_dir() -> Path:
    """Los casos de golden set, un archivo por caso."""
    return app_dir() / "evals" / "cases"


def subsets_dir() -> Path:
    """Las listas versionadas de subconjuntos."""
    return app_dir() / "evals" / "subsets"


def manifest_path() -> Path:
    """El manifiesto de los ocho conjuntos de datos (BR1.9)."""
    return app_dir() / "evals" / "manifest.yaml"


def baselines_dir() -> Path:
    """Las lineas base publicadas por hito, una por archivo (U21, TECH-U21.4)."""
    return app_dir() / "evals" / "baselines"


def current_baseline_path() -> Path:
    """La linea base vigente: la que usa la compuerta para comparar (U21)."""
    return baselines_dir() / "current.json"


def last_run_digest_path() -> Path:
    """El resumen de la ultima corrida completa, versionado (U22, FD-U22-10).

    Vive junto a las lineas base y **no** en `tmp/`: ahi estan los artefactos que
    cada corrida del guion de verificacion regenera (ver `reports_dir`), y este
    resumen no es uno. Solo lo escribe `evals:baseline`, que corre la corrida
    completa.
    """
    return app_dir() / "evals" / "last-run.json"


def calibrations_dir() -> Path:
    """Las calibraciones del juez, una por modelo y version de rubrica (U21)."""
    return app_dir() / "evals" / "calibrations"


def unstable_cases_path() -> Path:
    """Los casos que cambian de veredicto entre corridas identicas (U21, BR2.4)."""
    return app_dir() / "evals" / "unstable-cases.yaml"


def regressions_path() -> Path:
    """Las explicaciones que desbloquean una regresion (U21, BR2.2)."""
    return app_dir() / "evals" / "regressions.yaml"


def labels_dir() -> Path:
    """Las etiquetas humanas de DS-7, un archivo por idioma (U21, FD-U21-3)."""
    return app_dir() / "evals" / "labels"


def labeling_queue_path() -> Path:
    """La cola de turnos pendientes de etiquetar, que Miguel llena aparte."""
    return labels_dir() / "queue.yaml"


def judge_verdicts_dir() -> Path:
    """Los veredictos grabados del juez, uno por modelo y version de rubrica (U21)."""
    return app_dir() / "evals" / "judge-verdicts"


def schemas_dir() -> Path:
    """Los JSON Schema generados desde los modelos (C-28)."""
    return app_dir() / "contracts" / "schemas"


def openapi_path() -> Path:
    """El esquema OpenAPI de la API, generado desde la aplicacion (C-28).

    Lo escribe `mise run contracts:gen` y lo lee el generador del cliente de
    TypeScript; el chequeo de deriva lo compara byte a byte.
    """
    return app_dir() / "contracts" / "openapi.json"


def site_example_path() -> Path:
    """La respuesta real de `GET /api/site` con la configuracion versionada (U6).

    La escribe `mise run contracts:gen` junto al esquema OpenAPI y el chequeo de
    deriva la compara. Las pruebas del inicio la usan en vez de filas escritas a
    mano: si una aseguradora cambia, cambia aqui en el mismo commit.
    """
    return app_dir() / "contracts" / "examples" / "site-directory.json"


def metrics_example_path() -> Path:
    """La respuesta real de `GET /api/metrics` sin linea base publicada (U22).

    La escribe `mise run contracts:gen` junto al ejemplo del sitio y el chequeo de
    deriva la compara. Las pruebas del panel la usan para el estado "sin medir",
    que es el estado con el que nace: una respuesta escrita a mano pasaria aunque
    el servidor mandara otra forma.
    """
    return app_dir() / "contracts" / "examples" / "metrics-snapshot.json"


def frontend_api_dir() -> Path:
    """El cliente de la API generado para la interfaz (C-28, BR3.1)."""
    return app_dir() / "frontend" / "src" / "shared" / "api"


def reports_dir() -> Path:
    """Donde se escribe el reporte de cada corrida.

    Es un directorio de salida, no versionado: el reporte de la tuberia viaja
    como artefacto de la corrida (decision Q4 de observabilidad). Lo versionado
    de las evaluaciones son los casos y las lineas base, que viven en
    `app/evals/cases/` y `app/evals/baselines/` (C-27) y no aqui.

    Cuelga de `tmp/` y no de `app/evals/reports/` por una razon que costo una
    compuerta: el motor del flujo ata el recibo de una revision a una huella de
    todo el arbol de codigo, esa huella no consulta `.gitignore` y si incluye
    todo archivo con extension de codigo --`.json` entre ellas--, pero **salta**
    los directorios llamados `build`, `coverage`, `dist`, `logs`, `target` y
    `tmp`. Como el paso 9 del guion de verificacion corre las evaluaciones,
    cualquier revisor que corra el guion escribia un reporte nuevo aqui y movia
    la huella, y el recibo dejaba de poder registrarse. Un artefacto que se
    regenera en cada corrida no puede vivir donde algo lo confunda con fuente.
    """
    return repo_root() / "tmp" / "evals" / "reports"


def transcripts_dir() -> Path:
    """Donde una corrida con conversaciones deja lo que dijo la agente, ya redactado.

    Hermano de `reports_dir` y por la misma razon: cuelga de `tmp/`, no se versiona
    y cada corrida lo regenera. El reporte no guarda turnos (solo veredictos por
    caso); estos archivos son lo que alimenta la cola de etiquetado de DS-7
    (`mise run evals:label:queue`).
    """
    return repo_root() / "tmp" / "evals" / "transcripts"


def voice_output_dir() -> Path:
    """Donde deja su audio `mise run voice:say`, la demostracion de la voz (BR6.3).

    En `tmp/`, que git ignora, por dos razones: el audio de la voz de Catalina es
    de Cartesia y no se versiona, y el aplicativo servido **no escribe audio en
    ningun sitio** (NFR19.5); este directorio es solo del comando a mano. Cuelga
    de `tmp/` tambien por la razon de `reports_dir`: la huella del arbol de codigo
    salta ese directorio.
    """
    return repo_root() / "tmp" / "voice"


def frontend_copy_dir() -> Path:
    """El modulo tipado de claves que consume la interfaz (C-28)."""
    return app_dir() / "frontend" / "src" / "shared" / "copy"


def readme_path() -> Path:
    """El README de la raiz, cuyas dos secciones generadas regenera `readme:gen` (U22)."""
    return repo_root() / "README.md"


def frontend_dist_dir() -> Path:
    """Los estaticos compilados de la interfaz, que el proceso sirve (CG-U6-5).

    Los deja `mise run web:build`. Si no existen, las rutas de la interfaz
    responden servicio no disponible y la API sigue atendiendo.
    """
    return app_dir() / "frontend" / "dist"
