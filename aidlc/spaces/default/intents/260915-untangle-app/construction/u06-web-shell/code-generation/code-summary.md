# Resumen del código — U6 `web-shell`

U6 deja la primera interfaz visible de Untangle y la parte servida del proceso
que la sostiene. Se construyó en dos tandas sobre el plan aprobado (pasos 1 a 13
y 14 a 24), por la rama determinista, capa por capa, y todas las compuertas
quedaron en verde.

## Qué se ve

- **Inicio**, en el idioma del dispositivo (español si lo es, si no inglés) y en
  el modo del dispositivo, con las tres aseguradoras en filas: monograma con su
  acento, nombre, carácter y póliza de ejemplo. Sin canales montados muestra una
  sola línea honesta; los botones de chat y voz aparecen solos cuando esas
  unidades monten su superficie.
- **Selectores** de idioma (Español / English) y de modo (Claro / Oscuro) en la
  barra superior de todas las pantallas.
- **Páginas de estado:** despertando, no disponible, enlace no válido, enlace
  vencido, datos reiniciados, no encontrada y servicio no disponible.

## Resultados

| Compuerta | Resultado |
| --- | --- |
| `mise run test:u6` | Servidor: 122 pruebas en verde. Interfaz: 160 pruebas en 19 archivos, en verde |
| Suite completa del servidor tras la primera tanda | 782 en verde (677 antes de U6, sin regresiones) |
| `mise run a11y` | 67 pruebas en verde en 23,7 s; el guion publica 26 s para el paso (presupuesto 240 s) |
| NFR16.3 — página de espera en teléfono emulado | **952 ms** (meta: menos de 3 s) |
| PERF-U6.1 — bytes antes de la página de espera | **148.564** comprimidos (meta: 200.000 o menos) |
| PERF-U6.2 — inicio con sus tres filas | **1.856 ms** (meta: 4 s o menos) |
| `mise run cov` | Servidor 90,36 %, interfaz 66,29 %, **agregado 86,53 %** (piso 80 %), sin exclusiones nuevas |
| `mise run supply:check`, `mise run audit` | En verde; ninguna vulnerabilidad conocida |
| `scripts/verify.sh` | 9 de 9 en verde |

El arnés se comprobó a sí mismo: al achicar a propósito los botones de los
selectores, falló nombrando los cuatro con sus medidas.

## Decisiones de implementación

Las ocho del plan (CG-U6-1 a CG-U6-8) se aplicaron como se aprobaron. Además:

- **El vocabulario de superficies vive en `untangle/surface_spec.py`** y el
  registro en `server/surfaces.py`: las unidades que montan superficies están por
  debajo de `server` en el contrato de capas y no pueden importarlo.
- **El esquema OpenAPI se exporta desde `server/openapi_export.py`**, porque
  `workspace` no puede importar la raíz de composición.
- **Listo en 503 usa `provider_unavailable` con `Retry-After: 5`**: C-01 no
  tiene un código para "todavía no está listo" y no se inventó uno.
- **Ya no se publican `/docs`, `/redoc` ni `/openapi.json`**: cargan scripts de
  un tercero que la política de contenido bloquea. El esquema sigue en
  `app/contracts/openapi.json`.
- **`UNTANGLE_COMMIT_SHA`** alimenta el campo `version` de la salud; sin ella
  dice `unknown`.
- **La activación exige declarar su origen** (`source`), para que el chequeo y
  el corredor no cuenten (BR8.4); U13 y U14 lo pasarán.
- **Estáticos comprimidos:** la compilación deja versiones `.br` y `.gz`, y el
  proceso sirve la que el navegador acepta. Sin eso viajaban 419.977 bytes antes
  de la página de espera. La API nunca se comprime.
- **`Select` nativo en vez del de Radix:** el de Radix inyecta etiquetas de
  estilo que la política `style-src 'self'` bloquea. Las primitivas se
  escribieron siguiendo el patrón de shadcn/ui, sin correr su herramienta.
- **El enrutador se carga después de la página de espera**, para que lo que
  viaja antes de ella sea poco.
- **El carácter de cada aseguradora, sin claves armadas en ejecución:** una
  tabla generada desde los `tenant.yaml` (`tenant-characters.ts`) lleva cada
  clave escrita literal, sin ningún `tenant_id` en el código.
- **`copy:check` quedó más estricto:** los módulos generados ya no cuentan como
  consumidores —un agujero heredado de U1 que dejaba pasar claves muertas—, el
  `character_key` de cada aseguradora sí cuenta, se detectan claves armadas con
  plantillas, y el chequeo de texto en línea se extendió a la interfaz.
- **`js-yaml` 4.3.2 por una sustitución acotada en pnpm:** el generador del
  cliente trae 4.2.0, con tres avisos altos y sin versión corregida.
- **Regla de seguridad apagada solo en el cliente HTTP empaquetado** por el
  generador (`client/` y `core/`): `detect-object-injection`, con sus 21
  hallazgos revisados uno por uno y la razón escrita al lado en
  `app/frontend/eslint.config.ts`. Lo generado desde nuestro esquema la conserva.
- **"Despertando" y "no disponible" son estados de la espera, no rutas:**
  `/status/$kind` admite los cinco tipos a los que se llega navegando.

## Desviaciones del plan

- **El selector de idioma en el teléfono muestra los nombres completos**, como
  M1 y U-04, en lugar del código compacto de `frontend-components.md`.
- **El zoom al 200 % (BR7.6) no tiene prueba propia**: lo cubre la comprobación
  a 360 px de ancho, que equivale a 200 % sobre 720 px.
- **La cobertura de la interfaz es 66,29 %**: el código escrito a mano está entre
  94 % y 100 %, y lo que la baja es el cliente HTTP empaquetado, que cuenta en el
  cálculo por NFR18.4. El agregado cumple con margen.
- Se crearon **`scripts/servidor-del-arnes.py`** (el proceso real sobre una base
  efímera para el arnés) y **`app/contracts/examples/site-directory.json`**
  (generado desde la configuración real, para que las pruebas del inicio no
  inventen datos).

## Cómo verlo en local

Con Docker abierto:

```bash
mise run web:build
uv run --project app/backend python scripts/servidor-del-arnes.py --port 8765
```

y abrir `http://localhost:8765`. La base es efímera: se crea al arrancar y
desaparece al cerrar.

## Archivos

179 rutas del espacio de trabajo, listadas una por una en
`source-manifest.json`. Por área: 12 módulos nuevos del servidor
(`server/`, `telemetry/activation/`, `surface_spec.py`, el reporte de
activación) y 1 migración; unos 70 archivos de la interfaz entre código,
pruebas, estilos y arnés; el cliente y el esquema generados; y los cambios en
`mise.toml`, `scripts/verify.sh`, el flujo de GitHub Actions, el catálogo de
textos y las tres configuraciones de aseguradora.

## Trazabilidad

`traceability.json` cubre 68 identificadores: los 12 criterios de US1.33 y
US5.16, las 44 reglas y los 12 objetivos medibles `NFRx.y`. 64 apuntan a un
archivo que existe; 4 quedan diferidos al intent `infra`, que es dueño del
chequeo periódico, su alerta, la disponibilidad mensual y el checklist del
segundo día (AC5.16.2, AC5.16.3, AC5.16.5 y NFR16.1).
