#!/usr/bin/env bash
# Publica una version del aplicativo en produccion (Cloud Run), paso a paso.
#
#   scripts/desplegar.sh [--simular] [<commit>]
#
# Sin <commit> publica el ultimo de `origin/main`. Con `--simular` hace las
# comprobaciones y **solo imprime** los comandos que cambian algo.
#
# Por que existe: hasta el 2026-10-13 publicar dependia de la memoria de quien lo
# hacia. El procedimiento completo, con lo que este guion no cubre (claves, base,
# corpus), esta en `docs/reference/operacion-de-produccion.md`.
#
# Lo que hace, en orden, y por que en ese orden:
#   1. Comprueba que el commit esta en `origin/main` y que su revision de GitHub
#      Actions termino en verde: la compuerta es GitHub, no esta maquina.
#   2. Anota la revision que esta sirviendo ahora y la imagen del trabajo de
#      reinicio: es a lo que se vuelve si algo sale mal.
#   3. Construye la imagen **desde `git archive`**, no desde el directorio: asi
#      lleva exactamente lo que esta en el commit, sin archivos sueltos ni
#      cambios sin guardar.
#   4. Despliega el servicio y actualiza el trabajo de reinicio a la misma imagen.
#   5. Prueba de humo contra la direccion directa del servicio.
#   6. Corre el reinicio de la demostracion: es el ultimo paso de todo despliegue
#      (sin un reinicio exitoso en 24 horas las superficies publicas cierran).
#
# No crea ni cambia ninguna clave: las variables del servicio se conservan tal
# como estan. Solo actualiza `UNTANGLE_COMMIT_SHA`.
set -euo pipefail

REGION="us-east1"
SERVICIO="cautelia"
TRABAJO_DE_REINICIO="cautelia-reset"
REGISTRO="us-central1-docker.pkg.dev"
REPOSITORIO_DE_IMAGENES="cautelia"
FLUJO_DE_REVISION="verify.yml"
CUENTA_DE_GITHUB="miguelczz"
DOMINIO="https://cautelia.app"
AGENTE="cautelia-despliegue/1"

simular=0
commit=""
for argumento in "$@"; do
  case "$argumento" in
    --simular) simular=1 ;;
    -h | --help)
      sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) commit="$argumento" ;;
  esac
done

dice() { printf '\n== %s\n' "$*"; }
falla() {
  printf 'desplegar: %s\n' "$*" >&2
  exit 1
}
# Lo que cambia algo pasa por aqui: con --simular se imprime y no se ejecuta.
hacer() {
  if [ "$simular" -eq 1 ]; then
    printf '   (simulado) %s\n' "$*"
  else
    "$@"
  fi
}

for herramienta in git gh gcloud docker curl; do
  command -v "$herramienta" >/dev/null 2>&1 || falla "falta '$herramienta' en esta maquina"
done

dice "1. El commit y su revision en GitHub"
git fetch --quiet origin main
commit="$(git rev-parse --verify "${commit:-origin/main}^{commit}")" || falla "ese commit no existe"
git merge-base --is-ancestor "$commit" origin/main || falla "el commit $commit no esta en origin/main"
corto="$(git rev-parse --short=7 "$commit")"

activa="$(gh api user --jq .login 2>/dev/null || true)"
[ "$activa" = "$CUENTA_DE_GITHUB" ] || falla "la cuenta activa de gh es '${activa:-ninguna}', no '$CUENTA_DE_GITHUB' (gh auth switch)"
conclusion="$(gh run list --commit "$commit" --workflow "$FLUJO_DE_REVISION" --limit 1 --json conclusion --jq '.[0].conclusion // "sin corrida"')"
[ "$conclusion" = "success" ] || falla "la revision de GitHub de $corto esta en '$conclusion': no se publica nada que no este en verde"
echo "   $corto esta en origin/main y su revision termino en verde"

proyecto="$(gcloud config get-value project 2>/dev/null)"
[ -n "$proyecto" ] || falla "gcloud no tiene proyecto configurado"
imagen="$REGISTRO/$proyecto/$REPOSITORIO_DE_IMAGENES/$SERVICIO:$corto"

dice "2. A que se vuelve si algo sale mal"
revision_anterior="$(gcloud run services describe "$SERVICIO" --region "$REGION" --format='value(status.latestReadyRevisionName)')"
imagen_anterior="$(gcloud run jobs describe "$TRABAJO_DE_REINICIO" --region "$REGION" --format='value(spec.template.spec.template.spec.containers[0].image)')"
echo "   revision que sirve ahora: $revision_anterior"
echo "   imagen del reinicio ahora: $imagen_anterior"
echo "   para volver atras: scripts/volver-atras.sh $revision_anterior $imagen_anterior"

dice "3. La imagen, desde git archive ($imagen)"
# linux/amd64 a proposito: Cloud Run no corre la arquitectura de una Mac con Apple Silicon.
if [ "$simular" -eq 1 ]; then
  echo "   (simulado) git archive $commit | docker buildx build --platform linux/amd64 --push -t $imagen -"
else
  git archive --format=tar "$commit" | docker buildx build --platform linux/amd64 --push -t "$imagen" -
fi

dice "4. El servicio y el trabajo de reinicio"
hacer gcloud run deploy "$SERVICIO" --region "$REGION" --image "$imagen" \
  --update-env-vars "UNTANGLE_COMMIT_SHA=$corto" --quiet
# Si un despliegue anterior se devolvio a una revision fija, el trafico sigue ahi.
hacer gcloud run services update-traffic "$SERVICIO" --region "$REGION" --to-latest --quiet
hacer gcloud run jobs update "$TRABAJO_DE_REINICIO" --region "$REGION" --image "$imagen" --quiet

dice "5. Prueba de humo"
direccion="$(gcloud run services describe "$SERVICIO" --region "$REGION" --format='value(status.url)')"
probar() {
  # Hasta un minuto: el arranque sube las migraciones antes de responder que esta listo.
  local camino="$1" intento codigo
  for intento in $(seq 1 12); do
    codigo="$(curl -s -o /dev/null -w '%{http_code}' -A "$AGENTE" --max-time 10 "$camino" || true)"
    [ "$codigo" = "200" ] && { echo "   200  $camino"; return 0; }
    sleep 5
  done
  falla "$camino responde $codigo. Para volver atras: scripts/volver-atras.sh $revision_anterior $imagen_anterior"
}
if [ "$simular" -eq 1 ]; then
  echo "   (simulado) se probarian $direccion/api/health/ready, $direccion/api/quality y $DOMINIO/"
else
  probar "$direccion/api/health/ready"
  probar "$direccion/api/quality"
  probar "$DOMINIO/"
fi

dice "6. El reinicio de la demostracion (ultimo paso de todo despliegue)"
hacer gcloud run jobs execute "$TRABAJO_DE_REINICIO" --region "$REGION" --wait

if [ "$simular" -eq 1 ]; then
  dice "Simulado: no se publico nada"
else
  dice "Publicado $corto"
fi
echo "   Si hay que volver atras: scripts/volver-atras.sh $revision_anterior $imagen_anterior"
