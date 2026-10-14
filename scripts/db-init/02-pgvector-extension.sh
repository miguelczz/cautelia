#!/bin/sh
#
# Habilita la extension vectorial de la imagen (ADR-010, TECH-U8.1).
#
# La instala U8 `policy-rag`, que es la primera unidad que declara una columna
# `vector`: la base no la trae activa por defecto, solo empaquetada en la
# imagen. Crearla exige el superusuario del contenedor -- el rol del
# aplicativo (`untangle_app`) solo tiene CREATE y USAGE sobre el esquema
# `public`, y una extension se instala contra la base, no contra un esquema --
# asi que este guion corre, como `01-app-role.sh`, con `POSTGRES_USER`.
#
# Mismo guion para los dos caminos: el `docker-compose.yml` del entorno local
# lo monta en el directorio de arranque de la imagen, y la base efimera de las
# pruebas monta el mismo directorio (`untangle.tenancy.ephemeral`). `IF NOT
# EXISTS` la vuelve inofensiva si algun dia la imagen ya la trae instalada.

set -eu

: "${POSTGRES_USER:?la imagen no definio POSTGRES_USER}"
: "${POSTGRES_DB:?la imagen no definio POSTGRES_DB}"

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
SQL
