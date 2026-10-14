#!/bin/sh
#
# Crea el rol del aplicativo, **sin privilegio de salto** (BR1.7, C-10).
#
# Un rol que pueda saltarse las politicas de fila hace que las pruebas de
# aislamiento pasen sin que exista aislamiento: es el fallo que no avisa, y por
# eso el aplicativo nunca se conecta con el superusuario del contenedor.
#
# Este archivo lo ejecutan **los dos** caminos y por eso hay uno solo: el
# `docker-compose.yml` del entorno local lo monta en el directorio de arranque
# de la imagen, y la base efimera de las pruebas monta el mismo directorio. Lo
# que corre en la maquina de quien desarrolla es literalmente lo que corre en la
# tuberia.
#
# La contrasena entra por variable de entorno y se pasa a psql como **variable
# de psql**, no concatenada al SQL: `:'var'` la cita como literal y `:"var"` como
# identificador, que es la forma documentada de no construir SQL con texto.

set -eu

: "${POSTGRES_USER:?la imagen no definio POSTGRES_USER}"
: "${POSTGRES_DB:?la imagen no definio POSTGRES_DB}"
: "${UNTANGLE_POSTGRES_APP_USER:?defina UNTANGLE_POSTGRES_APP_USER}"
: "${UNTANGLE_POSTGRES_APP_PASSWORD:?defina UNTANGLE_POSTGRES_APP_PASSWORD}"

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  -v app_user="$UNTANGLE_POSTGRES_APP_USER" \
  -v app_password="$UNTANGLE_POSTGRES_APP_PASSWORD" <<'SQL'
-- NOBYPASSRLS es el punto entero de este archivo: es lo que hace que una prueba
-- de aislamiento signifique algo. NOSUPERUSER y NOCREATEROLE por lo mismo de
-- siempre: el aplicativo solo necesita sus tablas.
CREATE ROLE :"app_user" LOGIN PASSWORD :'app_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;

-- El rol crea sus propias tablas y por lo tanto las posee. Un dueno se saltaria
-- sus politicas, y por eso cada tabla lleva ademas FORCE ROW LEVEL SECURITY en
-- la revision que la crea (C-30).
GRANT CREATE, USAGE ON SCHEMA public TO :"app_user";
SQL
