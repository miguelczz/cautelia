#!/usr/bin/env bash
# Devuelve produccion a una revision anterior del servicio.
#
#   scripts/volver-atras.sh [--simular] <revision-del-servicio> <imagen-del-reinicio>
#
# Los dos datos los imprime `scripts/desplegar.sh` antes de cambiar nada. La
# revision se puede buscar tambien con:
#   gcloud run revisions list --service cautelia --region us-east1 --limit 5
#
# Que hace: manda todo el trafico a esa revision, devuelve el trabajo de reinicio a
# la imagen que tenia y hace la prueba de humo. **No toca la base**: las migraciones
# que subio la version nueva se quedan. Las del proyecto son aditivas (columnas y
# tablas nuevas), asi que el codigo anterior sigue funcionando con ellas; si una
# migracion dejara de serlo, la vuelta atras necesita su propio paso y se escribe
# en `docs/reference/operacion-de-produccion.md` antes de publicar esa version.
set -euo pipefail

REGION="us-east1"
SERVICIO="cautelia"
TRABAJO_DE_REINICIO="cautelia-reset"
AGENTE="cautelia-despliegue/1"

simular=0
posicionales=()
for argumento in "$@"; do
  case "$argumento" in
    --simular) simular=1 ;;
    *) posicionales+=("$argumento") ;;
  esac
done
[ "${#posicionales[@]}" -eq 2 ] || {
  sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//' >&2
  exit 1
}
revision="${posicionales[0]}"
imagen="${posicionales[1]}"

hacer() {
  if [ "$simular" -eq 1 ]; then
    printf '   (simulado) %s\n' "$*"
  else
    "$@"
  fi
}

gcloud run revisions describe "$revision" --region "$REGION" --format='value(metadata.name)' >/dev/null ||
  {
    echo "volver-atras: la revision '$revision' no existe" >&2
    exit 1
  }

# Lo que sirve ahora, para regresar a ello si la revision pedida no arranca. El 2026-10-15
# la primera prueba de la vuelta atras dejo el sitio dos minutos en error: la revision
# anterior no arrancaba sobre la base que la nueva habia migrado, y este guion se limitaba a
# avisarlo con el trafico ya movido.
sirve_ahora="$(gcloud run services describe "$SERVICIO" --region "$REGION" --format='value(status.traffic[0].revisionName)')"
imagen_ahora="$(gcloud run jobs describe "$TRABAJO_DE_REINICIO" --region "$REGION" --format='value(spec.template.spec.template.spec.containers[0].image)')"

printf '\n== El trafico, a %s\n' "$revision"
hacer gcloud run services update-traffic "$SERVICIO" --region "$REGION" --to-revisions "$revision=100" --quiet
printf '\n== El trabajo de reinicio, a %s\n' "$imagen"
hacer gcloud run jobs update "$TRABAJO_DE_REINICIO" --region "$REGION" --image "$imagen" --quiet

printf '\n== Prueba de humo\n'
direccion="$(gcloud run services describe "$SERVICIO" --region "$REGION" --format='value(status.url)')"
if [ "$simular" -eq 1 ]; then
  echo "   (simulado) se probaria $direccion/api/health/ready; si no responde, el trafico vuelve a $sirve_ahora"
else
  # Hasta un minuto: la revision anterior arranca en frio.
  codigo=""
  for _ in $(seq 1 12); do
    codigo="$(curl -s -o /dev/null -w '%{http_code}' -A "$AGENTE" --max-time 10 "$direccion/api/health/ready" || true)"
    [ "$codigo" = "200" ] && break
    sleep 5
  done
  echo "   $codigo  $direccion/api/health/ready"
  [ "$codigo" = "200" ] || {
    echo "volver-atras: $revision no responde; el trafico vuelve a $sirve_ahora" >&2
    gcloud run services update-traffic "$SERVICIO" --region "$REGION" --to-revisions "$sirve_ahora=100" --quiet
    gcloud run jobs update "$TRABAJO_DE_REINICIO" --region "$REGION" --image "$imagen_ahora" --quiet
    echo "volver-atras: produccion sigue en $sirve_ahora; mirar los registros de $revision" >&2
    exit 1
  }
fi
echo
if [ "$simular" -eq 1 ]; then
  echo "Simulado: no se cambio nada."
else
  echo "Produccion sirve $revision. El proximo scripts/desplegar.sh devuelve el trafico a la ultima revision."
fi
