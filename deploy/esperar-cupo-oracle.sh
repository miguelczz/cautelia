#!/usr/bin/env bash
#
# Pide la instancia ARM gratuita hasta que Oracle tenga cupo.
#
# **Por que existe un guion para esto.** El nivel gratuito de Oracle reparte un
# grupo de maquinas ARM entre todo el que lo usa, y en una region pequena como
# Bogota se ocupa y se libera en ventanas de minutos. Un intento aislado no dice
# nada; pedir a mano durante media hora cansa y es el patron que mas se parece a
# un abuso. Un guion que pide una vez por minuto cubre la ventana y genera menos
# trafico que recargar una pagina.
#
# **Por que pide dos tamanos.** El cupo no es "hay o no hay": la memoria y los
# nucleos salen del mismo anfitrion, asi que una peticion mas pequena cabe donde
# una grande no. Se alterna entre la comoda y la justa, y con eso cada vuelta
# tiene dos oportunidades en vez de una. El aplicativo necesita 1 GB --medido el
# 2026-10-03, con 512 MB muere al cargar los detectores-- asi que 2 GB ya sobran;
# los 6 GB son holgura, no necesidad, y no vale la pena esperar por ellos.
#
# Para de inmediato ante cualquier error que NO sea falta de cupo: un permiso que
# falta o un identificador malo no se arreglan reintentando, y seguir seria
# esconderlos.

set -u

AD="CoFM:SA-BOGOTA-1-AD-1"
SUBRED="ocid1.subnet.oc1.sa-bogota-1.aaaaaaaamdymiopwab4n6wm32tv3vs7hxtx5g7mdj2srcw7rnbowaymbb3tq"
IMAGEN="ocid1.image.oc1.sa-bogota-1.aaaaaaaau4civup7jbj3d4lbze36ld6kjlgtg6vfotydzvl4jzmgi7hc4lha"
LLAVE="$HOME/Proyectos/documentos/cautelia/ssh-key-2026-10-03.key.pub"
NOMBRE="cautelia"
ESPERA=60
BITACORA="$HOME/Proyectos/documentos/cautelia/cupo-oracle.log"

# Los dos tamanos que se alternan: el comodo y el justo.
TAMANOS=('{"ocpus":1,"memoryInGBs":6}' '{"ocpus":1,"memoryInGBs":2}')

anotar() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$BITACORA"; }

COMPARTIMENTO=$(grep '^tenancy' "$HOME/.oci/config" | cut -d= -f2)
ERRORES=$(mktemp)
trap 'rm -f "$ERRORES"' EXIT

# Guardia: si ya existe una instancia viva con ese nombre, no se crea otra. Es lo
# que hace que arrancar el guion dos veces --o que el servicio de arranque lo
# levante tras un reinicio-- no acabe con dos maquinas.
VIVAS=$(oci compute instance list -c "$COMPARTIMENTO" \
    --display-name "$NOMBRE" \
    --query 'length(data[?"lifecycle-state"!=`TERMINATED` && "lifecycle-state"!=`TERMINATING`])' \
    --raw-output 2>/dev/null)
if [ "${VIVAS:-0}" != "0" ]; then
    anotar "ya existe una instancia '$NOMBRE' viva; no se pide otra"
    exit 0
fi

INTENTO=0
while true; do
    INTENTO=$((INTENTO + 1))
    TAMANO=${TAMANOS[$((INTENTO % ${#TAMANOS[@]}))]}

    # `--no-retry`: sin el, la herramienta reintenta por dentro con su propia
    # espera y la cadencia deja de ser la nuestra. Medido: cada intento pasaba de
    # un minuto y la espera de aqui se sumaba encima.
    if oci --no-retry compute instance launch \
        --availability-domain "$AD" \
        --compartment-id "$COMPARTIMENTO" \
        --shape "VM.Standard.A1.Flex" \
        --shape-config "$TAMANO" \
        --image-id "$IMAGEN" \
        --subnet-id "$SUBRED" \
        --assign-public-ip true \
        --display-name "$NOMBRE" \
        --ssh-authorized-keys-file "$LLAVE" \
        >/dev/null 2>"$ERRORES"; then
        anotar "CONSEGUIDA en el intento $INTENTO con $TAMANO"
        exit 0
    fi

    if grep -qi "out of capacity\|out of host capacity" "$ERRORES"; then
        # Solo una de cada diez, para que la bitacora no crezca sin freno cuando
        # esto pase dias corriendo.
        if [ $((INTENTO % 10)) -eq 0 ]; then
            anotar "intento $INTENTO: sigue sin cupo"
        fi
        sleep "$ESPERA"
        continue
    fi

    anotar "intento $INTENTO: fallo por una causa distinta a la falta de cupo; se para"
    grep -v "SyntaxWarning\|INSTANCE_CONSOLE" "$ERRORES" | head -20 | tee -a "$BITACORA"
    exit 1
done
