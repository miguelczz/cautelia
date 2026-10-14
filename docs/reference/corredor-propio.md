# El corredor propio de GitHub Actions

**Opción documentada, sin usar.** El 2026-10-12 la compuerta (`.github/workflows/verify.yml`)
se pasó unas horas a un corredor en la Mac de Miguel, porque la cuenta iba en el 90 % de
los minutos del mes. Miguel la descartó ese mismo día: la corrida calienta la Mac entre 10
y 15 minutos cada vez. La compuerta volvió a los servidores de GitHub, con una subida al
día como mucho.

Este documento queda por si hace falta otra vez. Para usarlo se crea la variable del
repositorio `RUNS_ON` con el valor `["self-hosted","macOS","ARM64"]`
(`Settings → Secrets and variables → Actions → Variables`); borrarla vuelve a GitHub.

## Qué cambia con un corredor propio

- Lo que corre es lo mismo: `scripts/verify.sh`, con los tres navegadores y el tope del
  arnés, porque GitHub pone `CI=true` también en un corredor propio.
- No descuenta minutos del plan, y la corrida tarda unos 10 a 15 minutos en vez de 37.
- La máquina trabaja a fondo durante la corrida.
- Si la Mac está apagada, dormida o con el corredor detenido, la corrida espera en cola
  hasta 24 horas.
- Docker tiene que estar abierto: la suite levanta su propia base de datos.

## Instalarlo (una sola vez)

El programa es el oficial de GitHub. Versión usada: `2.338.0`, 122 MB,
`actions-runner-osx-arm64-2.338.0.tar.gz`, de
`https://github.com/actions/runner/releases`. Su huella SHA-256 publicada es
`df4cebda25c86a886ed204e49fee63f5c2e7cec5f447b5c98440a826bbdf9df2`.

1. Descargar y descomprimir en `~/actions-runner` (fuera del repositorio):

   ```bash
   mkdir -p ~/actions-runner && cd ~/actions-runner && curl -fsSLO https://github.com/actions/runner/releases/download/v2.338.0/actions-runner-osx-arm64-2.338.0.tar.gz && echo "df4cebda25c86a886ed204e49fee63f5c2e7cec5f447b5c98440a826bbdf9df2  actions-runner-osx-arm64-2.338.0.tar.gz" | shasum -a 256 -c && tar xzf actions-runner-osx-arm64-2.338.0.tar.gz
   ```

2. Registrarlo en el repositorio. **Este paso lo corre Miguel**: pide a GitHub una clave
   de un solo uso, que vence en una hora, y la entrega al programa sin mostrarla.

   ```bash
   cd ~/actions-runner && ./config.sh --unattended --url https://github.com/miguelczz/cautelia --name mac-de-miguel --token "$(gh api -X POST repos/miguelczz/cautelia/actions/runners/registration-token --jq .token)"
   ```

3. Dejarlo corriendo. Como servicio del usuario (arranca solo al iniciar sesión, sin
   contraseña de administrador):

   ```bash
   cd ~/actions-runner && ./svc.sh install && ./svc.sh start
   ```

   O solo mientras haya una terminal abierta: `cd ~/actions-runner && ./run.sh`.

Para ver que quedó: en GitHub, `Settings → Actions → Runners` muestra `mac-de-miguel`
en verde («Idle»).

## Detenerlo, quitarlo y volver a los servidores de GitHub

- Pausar: `cd ~/actions-runner && ./svc.sh stop`. Reanudar: `./svc.sh start`.
- Quitarlo del todo: `./svc.sh uninstall`, y luego
  `./config.sh remove --token "$(gh api -X POST repos/miguelczz/cautelia/actions/runners/remove-token --jq .token)"`.
- Volver a los servidores de GitHub: borrar la variable `RUNS_ON` del repositorio.

## Lo que hay que saber de seguridad

- El corredor ejecuta, con el usuario de Miguel, lo que se suba a `main` de este
  repositorio. Mientras el repositorio sea privado y solo Miguel suba, es lo mismo que
  correr `scripts/verify.sh` a mano.
- **Antes de hacer público el repositorio hay que quitar el corredor** y borrar la
  variable `RUNS_ON`. En un repositorio público, quien proponga un cambio
  desde una copia puede hacer que su código corra en esta máquina.
- La corrida trabaja en su propia carpeta (`~/actions-runner/_work`), no en la carpeta
  de trabajo de Miguel: no ve su `.env` ni sus claves, igual que en GitHub.
- La caché de herramientas de la acción de `mise` está apagada en el corredor propio
  para que no pise las herramientas ya instaladas en la Mac.
