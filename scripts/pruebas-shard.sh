#!/usr/bin/env bash
# Una tanda de las pruebas del servidor con su cobertura, para el reparto en paralelo
# del flujo. Uso: scripts/pruebas-shard.sh K/N
#
# Deja sus datos de cobertura en app/backend/coverage/data/.coverage.<K>-<N>; el
# piso se calcula despues sobre los datos combinados de todas las tandas (`mise run
# cov:gate`). Una tanda sola nunca declara verde ni mide el piso.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

TANDA="${1:?uso: pruebas-shard.sh K/N}"
K="${TANDA%/*}"
N="${TANDA#*/}"

mkdir -p app/backend/coverage/data
mapfile -t ARCHIVOS < <(python3 scripts/shard-pruebas.py "$K" "$N")
echo "tanda $K/$N: ${#ARCHIVOS[@]} archivos de prueba"

COVERAGE_FILE="$PWD/app/backend/coverage/data/.coverage.$K-$N" \
  uv run --project app/backend pytest -c app/backend/pyproject.toml "${ARCHIVOS[@]}" \
  --cov --cov-config=app/backend/pyproject.toml --cov-report=
