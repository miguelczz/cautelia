# Despliegue

> **Lo que corre hoy (2026-10-06):** el aplicativo en **Google Cloud Run**
> (`us-east1`, servicio `cautelia`, imagen en Artifact Registry etiquetada por
> commit); la base en Neon; y delante de todo **Cloudflare Pages** (proyecto
> `cautelia`): sirve la landing como archivo estático en la raíz `cautelia.app`
> y reenvía todo lo demás a Cloud Run con la función `site/functions/[[path]].js`,
> así que el inicio del aplicativo vive en `cautelia.app/home` y sus demás rutas
> cuelgan del mismo dominio. Se despliega **desde
> `site/`** con `wrangler pages deploy . --project-name cautelia` (desde la raíz
> del repositorio no se compila la función). `app.cautelia.app` sigue mapeado
> directo a Cloud Run. El resto de este archivo describe el plan sobre
> una instancia de Oracle, que **no se ejecutó**: Oracle no dio capacidad en doce
> horas de intentos. Se conserva como procedimiento de referencia y porque
> `compose.yaml` y el túnel siguen valiendo para cualquier máquina propia. El
> registro de la publicación real está en `docs/PENDIENTES-MIGUEL.md`.

Lo que se planeó para una instancia propia, pieza por pieza:

| Pieza | Dónde | Por qué ahí |
| --- | --- | --- |
| El aplicativo | Instancia ARM gratuita de Oracle, en Bogotá | Encendida siempre, así que no hay arranque en frío. Es la región de menor latencia |
| La base de datos | Neon, en Virginia | Fuera de la máquina: una base dentro de la instancia se perdería con ella |
| El certificado y la entrada | Túnel de Cloudflare | Gratis, aguanta WebSockets, y no exige ni IP pública ni puerto abierto |
| La landing | Vercel, en `cautelia.app` | Ya estaba, y no comparte tubería con el aplicativo (D-013). Se queda con el dominio raíz: publicarla no puede depender de que la instancia esté viva, y el aplicativo vive en `app.cautelia.app` |

## Por qué no hay ningún puerto abierto

El túnel abre una conexión **desde la instancia hacia Cloudflare**, y el tráfico
entra por ella. La máquina no necesita nada escuchando desde internet: ni 80, ni
443, ni 8080. El único puerto abierto es el 22, que viene de fábrica y es por
donde se administra.

Eso no es una comodidad, es la propiedad de seguridad más barata de todo el
despliegue: lo que no está expuesto no se puede atacar desde fuera.

## Alta, la primera vez

1. **Preparar la máquina.** Desde el Mac:

   ```
   scp deploy/instalar-en-la-instancia.sh ubuntu@<ip>:
   ssh ubuntu@<ip> 'bash instalar-en-la-instancia.sh'
   ```

   Instala Docker, crea `/opt/cautelia/` y deja un servicio que levanta todo
   cuando la máquina arranca. Es idempotente: correrlo dos veces no rompe nada.

   Después hay que **salir y volver a entrar** por SSH: el grupo `docker` no
   tiene efecto en la sesión que lo creó.

2. **Publicar la imagen.** `bash deploy/publicar-imagen.sh`. Se niega a correr si
   hay cambios sin commitear, porque entonces la etiqueta mentiría sobre qué está
   corriendo. Escribe `deploy/deploy.env` con la imagen y el commit.

3. **Copiar la configuración:**

   ```
   scp deploy/compose.yaml deploy/deploy.env ubuntu@<ip>:/opt/cautelia/
   ```

   Y el archivo de entorno del aplicativo a `/opt/cautelia/env/aplicativo.env`.
   Ese archivo lleva las claves de proveedor y la dirección de la base; **no está
   en el repositorio y no debe estarlo**.

4. **Crear el túnel.** Desde la instancia, y necesita una autorización en el
   navegador:

   ```
   docker run -it --rm -v /opt/cautelia/cloudflared:/home/nonroot/.cloudflared \
     cloudflare/cloudflared:latest tunnel login
   docker run -it --rm -v /opt/cautelia/cloudflared:/home/nonroot/.cloudflared \
     cloudflare/cloudflared:latest tunnel create cautelia
   ```

   Lo que sale es un `.json` con las credenciales. Se renombra a
   `credenciales.json`, se copia `cloudflared-config.yml` como `config.yml` y se
   reemplaza en él el identificador del túnel.

   Después se apunta el dominio al túnel:

   ```
   docker run -it --rm -v /opt/cautelia/cloudflared:/home/nonroot/.cloudflared \
     cloudflare/cloudflared:latest tunnel route dns cautelia app.cautelia.app
   ```

5. **Arrancar:** `sudo systemctl start cautelia`.

6. **Comprobar que está vivo de verdad**, no que el contenedor existe:

   ```
   curl -sS https://app.cautelia.app/api/health/ready
   ```

   Tiene que responder `200` y traer en `version` el mismo commit que publicaste.
   Un despliegue no está hecho hasta que una prueba de humo lo confirma vivo.

## Actualizar

```
bash deploy/publicar-imagen.sh
scp deploy/deploy.env ubuntu@<ip>:/opt/cautelia/
ssh ubuntu@<ip> 'cd /opt/cautelia && docker compose --env-file deploy.env pull && docker compose --env-file deploy.env up -d'
```

Compose levanta el contenedor nuevo y retira el viejo. Durante el cambio hay unos
segundos sin servicio: con una sola instancia no hay forma de evitarlo, y
fingir lo contrario sería peor que decirlo.

## Volver atrás

Cada despliegue lleva escrito su paso de vuelta atrás, y este es el de todos:
**la imagen anterior sigue en el registro con su etiqueta**, que es un commit.
Para volver, se edita `CAUTELIA_IMAGEN` y `CAUTELIA_COMMIT` en
`/opt/cautelia/deploy.env` con los del commit anterior y se repiten los dos
comandos de arriba. No hace falta reconstruir nada.

La base de datos es la excepción que hay que mirar antes: si el despliegue que se
retira subió una migración, volver atrás con el código viejo lo deja hablando con
un esquema nuevo. Las migraciones de este proyecto son aditivas, así que el código
viejo sigue funcionando; una migración que borrara o renombrara algo rompería esa
propiedad y tendría que decirlo en su propio commit.

## Qué mirar cuando algo falla

```
ssh ubuntu@<ip> 'cd /opt/cautelia && docker compose --env-file deploy.env logs --tail 100'
```

- **El aplicativo no pasa a sano.** Casi siempre es la base: `ready` no responde
  hasta que las migraciones suben. Mire los registros del servicio `aplicativo`.
- **El sitio no carga pero el contenedor está sano.** Es el túnel. Sus registros
  dicen si no encuentra sus credenciales o si el identificador del `config.yml` no
  es el del túnel creado.
- **Muere y vuelve a arrancar solo.** Es el tope de memoria. Está en 1 GB porque
  con 512 MB el aplicativo muere al cargar los detectores de datos personales,
  medido el 2026-10-03.
