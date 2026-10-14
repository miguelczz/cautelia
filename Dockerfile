# La imagen del aplicativo (intent `infra`).
#
# **Tres etapas y ninguna de adorno.** La interfaz se compila con Node, el backend
# se instala con uv, y la imagen que se publica no lleva ninguno de los dos: lleva
# Python, el entorno virtual ya resuelto y los estaticos compilados. Lo que no esta
# en la imagen final no se puede explotar en produccion.
#
# **La instalacion es reproducible, no libre.** `uv sync --locked` falla si el
# lockfile no coincide, que es la practica afirmada del equipo: una imagen que
# resolviera dependencias al construirse seria una imagen distinta cada vez.
#
# Los modelos de spaCy entran por el extra `models`, fijados por URL con su hash en
# el lockfile --nunca con `spacy download`, que es resolucion libre--. Son el grueso
# del peso y la razon por la que esta imagen no es pequena.

# --- 1. La interfaz compilada -------------------------------------------------
FROM node:22-slim AS interfaz
WORKDIR /app
RUN corepack enable
COPY app/frontend/package.json app/frontend/pnpm-lock.yaml app/frontend/pnpm-workspace.yaml ./
# `--frozen-lockfile` por la misma razon que `--locked` abajo.
RUN pnpm install --frozen-lockfile
COPY app/frontend/ ./
COPY app/contracts/ ../contracts/
RUN pnpm exec vite build

# --- 2. Las dependencias de Python --------------------------------------------
FROM python:3.13-slim AS dependencias
COPY --from=ghcr.io/astral-sh/uv:0.12.16 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY app/backend/pyproject.toml app/backend/uv.lock ./app/backend/
# Sin el codigo todavia: asi esta capa se reutiliza mientras el lockfile no cambie,
# que es lo que hace que un cambio de una linea no vuelva a bajar los modelos.
RUN uv sync --locked --project app/backend --extra models --no-install-project

# --- 3. Lo que se publica -----------------------------------------------------
FROM python:3.13-slim AS aplicativo

# `tini` como pid 1: sin el, el proceso de Python recibe las senales de parada como
# pid 1 y no las reenvia a sus hijos, asi que un despliegue que pide parar espera el
# tiempo maximo y lo mata. Los contenedores que escalan a cero paran a menudo.
RUN apt-get update \
 && apt-get install --no-install-recommends -y tini \
 && rm -rf /var/lib/apt/lists/*

# **No corre como root**, y no es ceremonia: esta es una superficie publica que
# recibe texto de visitantes. Un proceso que no es root no puede escribir donde no
# le toca aunque algo salga mal.
RUN useradd --create-home --uid 10001 untangle
WORKDIR /app

COPY --from=interfaz /app/dist ./app/frontend/dist
COPY app/backend/ ./app/backend/
COPY app/config/ ./app/config/
COPY app/data/ ./app/data/
COPY app/contracts/ ./app/contracts/
# El resumen de la ultima evaluacion completa: lo lee `GET /api/quality` para la
# pestana Calidad. Solo ese archivo; los casos y el corredor no corren en produccion.
# Sin el, el tablero publicado salia vacio aunque en local se viera (2026-10-11).
COPY app/evals/last-run.json ./app/evals/last-run.json
# El marcador de la raiz del repositorio. El aplicativo lo busca para resolver
# `app/config` y `app/data`, y **comprueba que exista incluso cuando la raiz se
# declara**: declarar una raiz equivocada y descubrirlo al primer caso es peor que
# no arrancar. Viaja la lista de tareas entera porque es un archivo de texto; lo que
# importa es que este donde dice la variable.
COPY mise.toml ./mise.toml
COPY scripts/servidor.py ./scripts/servidor.py

# **La venv va la ultima, y el orden es la defensa.** `uv sync --project
# app/backend` crea el entorno junto al proyecto, asi que vive donde el
# `COPY app/backend/` de arriba escribe. Copiarla antes dejaba que el
# contexto la pisara con la de la maquina de quien construye --con sus
# enlaces a `/Users/...`-- y el contenedor arrancaba sin poder importar nada.
# El `.dockerignore` ya lo impide; este orden lo impide tambien.
COPY --from=dependencias /app/app/backend/.venv /app/app/backend/.venv

# **La raiz del repositorio, declarada.** Fuera del repositorio el aplicativo no
# puede deducirla --busca `mise.toml` subiendo-- y lo dice con un error que nombra
# esta variable. Aqui la raiz es `/app`, que es donde estan `app/config` y
# `app/data`: la configuracion de las aseguradoras y el corpus de polizas.
ENV UNTANGLE_REPO_ROOT=/app \
    PATH="/app/app/backend/.venv/bin:${PATH}" \
    PYTHONPATH="/app/app/backend/src" \
    PYTHONUNBUFFERED=1 \
    PORT=8080

USER untangle
EXPOSE 8080

# La salud la decide el aplicativo, no el contenedor: `/api/health/ready` responde 503
# mientras la base no este migrada, que es justo lo que quien orquesta tiene que
# esperar antes de mandarle trafico.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,os,sys; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",8080)}/api/health/ready', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "scripts/servidor.py"]
