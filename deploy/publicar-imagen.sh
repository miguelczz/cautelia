#!/usr/bin/env bash
#
# Construye la imagen y la publica, para que la instancia solo tenga que bajarla.
#
# **Por que no se construye en la instancia.** La maquina gratuita tiene 1 nucleo;
# construir ahi esta imagen --que descarga los modelos de los detectores-- toma
# decenas de minutos cada vez. El Mac es `arm64` y la instancia tambien, asi que
# la imagen que sale aqui corre alli sin traducir nada.
#
# **Por que a un registro y no por SSH.** `docker save` por la red son 1,74 GB
# cada vez. El registro manda solo las capas que cambiaron, que en la practica
# son las ultimas y pesan poco.

set -euo pipefail

REGISTRO="ghcr.io"
DUENO="miguelczz"
NOMBRE="cautelia"

cd "$(dirname "$0")/.."

# La etiqueta es el commit, no `latest`: `latest` no dice **que** esta corriendo,
# y el dia de un incidente la pregunta es exactamente esa. El aplicativo publica
# ese mismo valor en su propia salud (`/api/health/ready`, campo `version`).
COMMIT=$(git rev-parse --short HEAD)
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "hay cambios sin commitear: la etiqueta mentiria sobre que corre" >&2
    exit 1
fi

IMAGEN="$REGISTRO/$DUENO/$NOMBRE:$COMMIT"

echo "==> Construyendo $IMAGEN"
docker build -t "$IMAGEN" .

echo "==> Publicando"
docker push "$IMAGEN"

# El archivo que la instancia necesita, escrito y no dictado: copiarlo a mano
# es donde la etiqueta y el commit acaban diciendo cosas distintas.
DESTINO="$(dirname "$0")/deploy.env"
cat >"$DESTINO" <<FIN
# Generado por publicar-imagen.sh. No editar a mano.
CAUTELIA_IMAGEN=$IMAGEN
CAUTELIA_COMMIT=$COMMIT
FIN

echo
echo "Publicada: $IMAGEN"
echo "Escrito:   $DESTINO"
echo "Copielo a /opt/cautelia/deploy.env en la instancia."
