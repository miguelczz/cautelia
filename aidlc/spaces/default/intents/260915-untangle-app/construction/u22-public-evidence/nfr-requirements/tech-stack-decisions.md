# Decisiones de stack — U22 `public-evidence`

Versión corta: esta unidad **no introduce ninguna tecnología nueva**, y eso es la
decisión.

| # | Qué | Por qué |
| --- | --- | --- |
| TECH-U22.1 | Las dos pantallas son del aplicativo, en `app/frontend/src/pages/`, con la base visual, el selector de idioma y el tema que ya existen | Respuesta 3A. Una página aparte tendría que repetir los tres o verse distinta, y verse distinta es lo que hace dudar a quien evalúa |
| TECH-U22.2 | Las cifras se sirven por una ruta del servidor que lee la línea base, no leyendo el archivo desde el navegador | El archivo vive en el repositorio y no en lo que se publica; además una ruta puede decir "no medida" con su causa, y un archivo ausente solo puede dar un 404 |
| TECH-U22.3 | El comando del README es una tarea más del archivo de tareas, con su modo comprobación, igual que los contratos generados | Un solo archivo de tareas es el contrato entre lo local y la tubería |
| TECH-U22.4 | Ninguna biblioteca de gráficos | Cinco cifras y cuatro totales no necesitan una: una dependencia nueva de runtime hay que justificarla en una línea, y esta no se justifica |

## Lo diferido a la pasada de publicación

Nada de esta unidad se publica hasta cerrar la pasada. Lo que queda **dentro** de
esta unidad es construir las dos pantallas, el comando y sus pruebas; lo que queda
fuera es servirlas al público, que va con el checklist del segundo día.
