#!/usr/bin/env bash
#
# El guion unico de verificacion.
#
# Todo control automatico vive aqui. El flujo de GitHub Actions lo **invoca**; no
# mantiene su propia lista de pasos, y el intent `infra` lo invocara tambien en
# vez de crear un segundo juego de chequeos. Se puede correr en local con el
# mismo comando: `mise run verify`.
#
# Nueve pasos, de barato a caro. Quien rompio el formato lo sabe en segundos
# aunque el guion siga corriendo, y el unico paso que puede gastar cuota es el
# ultimo.
#
# **Todo corre hasta el final menos el primero.** Una corrida dice todo lo que
# hay que arreglar, en vez de descubrir un problema por vuelta. El escaneo de
# secretos es la excepcion porque una clave filtrada es un incidente, y lo ultimo
# que se quiere es seguir trabajando y publicando registros encima.
#
# Uso:
#   scripts/verify.sh                 los nueve pasos
#   scripts/verify.sh --only secrets  solo el paso 1
#   scripts/verify.sh --skip secrets  del 2 al 9

set -Eeuo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

SOLO=""
SALTAR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --only)
      SOLO="${2:-}"
      shift 2
      ;;
    --skip)
      SALTAR="${2:-}"
      shift 2
      ;;
    -h | --help)
      sed -n '3,25p' "${BASH_SOURCE[0]}"
      exit 0
      ;;
    *)
      echo "opcion desconocida: $1" >&2
      exit 64
      ;;
  esac
done

# --- Presentacion -------------------------------------------------------------

if [[ -t 1 ]]; then
  ROJO=$'\033[31m'; VERDE=$'\033[32m'; NEGRITA=$'\033[1m'; FIN=$'\033[0m'
else
  ROJO=""; VERDE=""; NEGRITA=""; FIN=""
fi

FALLIDOS=()

encabezado() {
  printf '\n%s== %s%s\n' "$NEGRITA" "$1" "$FIN"
}

# Corre un paso, registra su fallo y **sigue**. La lista sale al final.
paso() {
  local nombre="$1"; shift
  encabezado "$nombre"
  if "$@"; then
    printf '%sok%s  %s\n' "$VERDE" "$FIN" "$nombre"
  else
    printf '%sfalla%s  %s\n' "$ROJO" "$FIN" "$nombre"
    FALLIDOS+=("$nombre")
  fi
}

mise_run() {
  mise run "$@"
}

# --- Paso 1: escaneo de secretos ---------------------------------------------
#
# El unico paso que detiene la corrida en el acto, y el primer trabajo del flujo.
# Hoy es ademas el **unico** escaneo de secretos del proyecto: la proteccion de
# insercion de GitHub no existe en un repositorio privado de cuenta personal, y
# se activa cuando el repositorio se haga publico.

escaneo_de_secretos() {
  encabezado "1/9 escaneo de secretos"

  if ! command -v gitleaks >/dev/null 2>&1; then
    cat >&2 <<'AVISO'
gitleaks no esta instalado y este paso no se puede saltar en silencio: es el
unico escaneo de secretos del proyecto. Instalelo con `brew install gitleaks` o
deje que el flujo de GitHub Actions lo corra.
AVISO
    return 1
  fi

  # Dos pasadas, y la segunda existe por un rojo real en `main` el 2026-09-20.
  #
  #   1. El historial completo. `gitleaks git` escanea **commits**: es lo que
  #      protege al repositorio, que es candidato a publicarse (D-017).
  #   2. Los archivos nuevos. Un archivo que todavia no esta en ningun commit es
  #      invisible para la pasada anterior. Por eso aquel dia la corrida local
  #      dio verde y la tuberia la puso roja dos minutos despues, ya con el
  #      commit dentro: el archivo se creo, se verifico, y solo entonces se
  #      commiteo.
  #
  # La lista de la segunda pasada sale de `git ls-files`, no del sistema de
  # archivos. Asi, lo que git ignora --`.env`, `spikes/.env`, `review/`-- queda
  # fuera por construccion: no puede llegar a un commit, y apuntar el escaner al
  # arbol de trabajo a secas devuelve 80 falsos positivos de esos mismos sitios.
  local fallo=0

  if ! gitleaks git --no-banner --redact --exit-code 1 .; then
    fallo=1
  fi

  local nuevo
  while IFS= read -r nuevo; do
    [[ -n "$nuevo" ]] || continue
    # Una ruta por invocacion: con dos o mas, gitleaks ignora los argumentos y
    # escanea el directorio actual entero, que es peor que no escanear.
    if ! gitleaks dir --no-banner --redact --exit-code 1 "$nuevo"; then
      fallo=1
    fi
  done < <(git ls-files --others --exclude-standard)

  if (( fallo == 0 )); then
    printf '%sok%s  1/9 escaneo de secretos\n' "$VERDE" "$FIN"
    return 0
  fi

  cat >&2 <<'INCIDENTE'

Se encontro un secreto.

Una clave que llego a un commit se considera comprometida: **rotela en el
proveedor** antes de cerrar el incidente. Borrarla del archivo no lo cierra.
INCIDENTE
  return 1
}

if [[ -z "$SALTAR" || "$SALTAR" != "secrets" ]]; then
  if ! escaneo_de_secretos; then
    printf '\n%sla corrida se detiene aqui%s: una clave filtrada es un incidente.\n' \
      "$NEGRITA" "$FIN" >&2
    exit 1
  fi
fi

if [[ "$SOLO" == "secrets" ]]; then
  exit 0
fi

# --- Pasos 2 a 9 --------------------------------------------------------------
# Corren hasta el final y reportan juntos.

paso "2/9 formato"                    mise_run fmt:check
paso "3/9 lint y contratos de importacion" mise_run lint
paso "4/9 chequeo de tipos"           mise_run types
# La preparacion del paso 5, no un paso del guion: el guion sigue teniendo
# nueve. Es lo mismo que levantar la base efimera para las pruebas de U2. Va
# aqui y no en `deps:install` porque a ese lo corre tambien `bootstrap`, que es
# el camino del clon al reporte, y ahi es justo donde no queremos los 72 MB de
# modelos (INF-U3-2, INF-U3-7).
mise_run models:install

# El paso 5 son las pruebas con su piso de cobertura y, despues, el arnes de
# accesibilidad y de tiempos (U6, F9): el mismo paso, no uno nuevo, porque el
# arnes tambien es una prueba determinista del producto. Corre despues de las
# pruebas porque es el mas caro, y **cronometrado**: su duracion se publica en
# cada corrida y tiene un presupuesto de seis minutos (PERF-U6.3). Pasarlo no
# autoriza a recortar idiomas ni modos; se paraleliza o se sube el presupuesto
# con una decision escrita.
#
# **360 s desde el 2026-10-07, por decision de Miguel** (antes 240). Ese dia ocho
# corridas en GitHub, todas con las pruebas en verde, duraron entre 189 y 328 s: lo
# que variaba era la velocidad del corredor de dos nucleos, no el arnes. Con 240 el
# paso fallaba cada vez que el corredor iba lento. 360 cubre la mas lenta medida con
# un 10 % de margen y sigue fallando si el arnes duplica su tiempo. Se eligio sobre
# repartirlo en dos trabajos porque cada uno repite la instalacion y gasta minutos
# del plan gratuito.
PRESUPUESTO_ARNES_S=360

pruebas_deterministas() {
  local fallo=0
  mise_run cov || fallo=1

  local inicio=$SECONDS
  mise_run a11y || fallo=1
  local duracion=$((SECONDS - inicio))

  # **La cifra dice con que se midio.** Desde el 2026-09-29 el arnes corre con los
  # tres motores solo en la tuberia y con Chromium en local (decision de Miguel), asi
  # que una duracion local y una de la tuberia **no son el mismo numero**. El
  # presupuesto de PERF-U6.3 es el de la corrida completa, y la que manda es la de la
  # tuberia; imprimir los dos sin decir cual es cual es como una cifra publicada
  # acaba saliendo de la medicion barata.
  local motores="3 motores"
  local vigilado="si"
  if [[ -z ${CI:-} ]]; then
    motores="1 motor (Chromium)"
    vigilado="no: la corrida completa es la de la tuberia"
  fi
  printf 'arnes de accesibilidad: %d s con %s (presupuesto %d s, PERF-U6.3; cuenta: %s)\n' \
    "$duracion" "$motores" "$PRESUPUESTO_ARNES_S" "$vigilado"

  # El presupuesto solo bloquea donde se mide entero. En local sobraria siempre --con
  # un motor cabe de largo-- y un limite que nunca puede fallar no vigila nada.
  if [[ -n ${CI:-} ]] && (( duracion > PRESUPUESTO_ARNES_S )); then
    printf '%sel arnes de accesibilidad paso su presupuesto%s\n' "$ROJO" "$FIN" >&2
    fallo=1
  fi
  return "$fallo"
}

paso "5/9 pruebas deterministas"      pruebas_deterministas
# El paso 6 crece por dentro, no de lista: U2 anade sus tres comprobaciones aqui
# --el aislamiento contra el catalogo vivo, las migraciones y los identificadores
# de aseguradora literales-- y U3 anade las dos suyas --quien produce el tipo
# redactado y el informe por reconocedor--; el guion sigue teniendo nueve pasos.
paso "6/9 aserciones de esquema"      bash -c 'mise run schema:check && mise run contracts:check && mise run env:check && mise run supply:check && mise run rls:check && mise run migrate:check && mise run tenancy:literals && mise run redaction:constructor && mise run redaction:report && mise run case:constructor && mise run case:transitions'
# El paso 7 tambien crece por dentro: U7 anade la regeneracion del corpus, que
# compara byte a byte lo versionado en `app/data/` con lo que produce el generador
# (CG-U7-4, TECH-U7.1). Va aqui y no en el 6 porque protege el contenido que se
# publica --un JSON corregido a mano que nadie reviso--, no la forma de un
# archivo. No llama a ningun modelo ni lee ninguna clave (BR1.5). U22 anade el
# README: sus dos secciones generadas tienen que coincidir con la linea base
# vigente (BR4.2), y corre en cada entrega porque entre hitos es cuando envejece.
paso "7/9 chequeos de contenido"      bash -c 'mise run copy:check && mise run chat:frases && mise run voice:frases && mise run content:check && mise run synthetic:check && mise run readme:check'
# El paso 8 crece por dentro como el 6 y el 7: la licencia de cada dependencia se
# comprueba aqui, junto a sus vulnerabilidades, porque las dos leen el mismo arbol
# resuelto. El guion sigue teniendo nueve pasos.
paso "8/9 auditoria de dependencias"  bash -c 'mise run audit && mise run licenses:check'
# La compuerta, no el corredor a secas (U21, BR5.1): compara contra la linea
# base, aplica los inestables y las explicaciones, y corre el segundo detector
# sobre el reporte. Un cambio en un archivo de reglas no tiene un camino
# aparte -- corre aqui igual que cualquier otro, porque el filtro del flujo de
# GitHub Actions nunca excluye estos nueve pasos (`verify.yml`, "la compuerta
# de evaluaciones"). DS-5 no se invoca aqui: solo en el comando por hito.
# `captura-con-redaccion` va aparte de `smoke` porque necesita los modelos de la
# redaccion, que el camino del clon al reporte no instala; aqui si estan (los
# instala la preparacion del paso 5).
paso "9/9 golden sets de texto"       bash -c 'mise run evals:gate -- --subset smoke && mise run evals:gate -- --subset captura-con-redaccion'

# --- Una sola lista al final --------------------------------------------------

echo
if [[ ${#FALLIDOS[@]} -eq 0 ]]; then
  printf '%sverificacion en verde%s\n' "$VERDE" "$FIN"
  exit 0
fi

printf '%s%d paso(s) en rojo:%s\n' "$ROJO" "${#FALLIDOS[@]}" "$FIN" >&2
for nombre in "${FALLIDOS[@]}"; do
  printf '  - %s\n' "$nombre" >&2
done
exit 1
