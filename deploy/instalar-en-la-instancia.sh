#!/usr/bin/env bash
#
# Deja la instancia lista para correr el aplicativo. Se ejecuta **una vez**, por
# SSH, sobre una maquina recien creada con Ubuntu 24.04 Minimal (aarch64).
#
# Es idempotente a proposito: correrlo dos veces no duplica nada ni pisa la
# configuracion que ya este puesta. Un guion de aprovisionamiento que solo
# funciona sobre una maquina virgen es un guion que no se puede usar el dia que
# algo salio a medias.
#
# **Lo que NO hace, y por que**: no abre ningun puerto. El tunel de Cloudflare
# abre una conexion hacia afuera y el trafico entra por ella, asi que la maquina
# no necesita nada escuchando desde internet. El unico puerto abierto es el 22,
# que viene abierto de fabrica y es por donde llega este guion.

set -euo pipefail

RAIZ=/opt/cautelia

decir() { printf '\n==> %s\n' "$*"; }

decir "Paquetes base"
# Ubuntu Minimal no trae ni curl ni ca-certificates, y los dos hacen falta para
# anadir el repositorio de Docker con su llave.
sudo apt-get update -qq
sudo apt-get install -y -qq ca-certificates curl gnupg

if ! command -v docker >/dev/null 2>&1; then
    decir "Docker, desde el repositorio oficial"
    # El repositorio oficial y no el paquete de Ubuntu: el de Ubuntu va por
    # detras y no trae el plugin `compose`, que es lo que usa el despliegue.
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg |
        sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" |
        sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
    sudo apt-get update -qq
    sudo apt-get install -y -qq \
        docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    # Para no escribir `sudo` delante de cada comando de docker. Pide volver a
    # entrar por SSH para que el grupo tenga efecto.
    sudo usermod -aG docker "$USER"
else
    decir "Docker ya estaba instalado"
fi

decir "Carpetas"
sudo mkdir -p "$RAIZ"/{env,cloudflared}
sudo chown -R "$USER:$USER" "$RAIZ"
# El archivo de entorno y las credenciales del tunel son secretos: solo su
# dueno los lee. Si alguna vez entra otro usuario a la maquina, no los ve.
chmod 700 "$RAIZ"/env "$RAIZ"/cloudflared

decir "Servicio de arranque"
# Compose ya reinicia los contenedores si se caen; esto es para el otro caso:
# que se reinicie **la maquina**. Sin esto, un reinicio de Oracle deja el sitio
# caido hasta que alguien entre a levantarlo a mano.
sudo tee /etc/systemd/system/cautelia.service >/dev/null <<UNIDAD
[Unit]
Description=Cautelia
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$RAIZ
ExecStart=/usr/bin/docker compose --env-file $RAIZ/deploy.env -f $RAIZ/compose.yaml up -d
ExecStop=/usr/bin/docker compose --env-file $RAIZ/deploy.env -f $RAIZ/compose.yaml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
UNIDAD

sudo systemctl daemon-reload
sudo systemctl enable cautelia.service

decir "Listo"
cat <<'FIN'
La maquina esta preparada. Lo que falta, en orden:

  1. Copiar a /opt/cautelia/ : compose.yaml, deploy.env
  2. Copiar a /opt/cautelia/env/aplicativo.env el archivo de entorno
  3. Crear el tunel y dejar sus credenciales en /opt/cautelia/cloudflared/
  4. sudo systemctl start cautelia

Si acaba de instalarse Docker, salga y vuelva a entrar por SSH antes del paso 4:
el grupo `docker` no tiene efecto en la sesion que lo creo.
FIN
