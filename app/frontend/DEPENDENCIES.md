# Dependencias de la interfaz

Una línea por cada dependencia de `package.json`: qué hace, por qué no alcanza
la plataforma (el navegador, Node o lo que ya está instalado) y su licencia. El
manifiesto es JSON y no admite comentarios, así que esta tabla cumple el papel
de los comentarios de `app/backend/pyproject.toml` (TECH-U6.1, `team.md`,
Secretos y cadena de suministro).

`mise run supply:check` compara esta tabla con `package.json` en las dos
direcciones y falla **nombrando** la dependencia que no tiene su línea, o la
línea que ya no tiene dependencia. La versión exacta de cada paquete la fija
`pnpm-lock.yaml`, con su huella de integridad, y no se repite aquí: una segunda
fuente de versiones se desactualiza en la primera actualización.

La lista se revisa una vez antes de la decisión de publicar el repositorio de
la semana 12 (D-017).

## Ejecución (llegan al navegador)

| Paquete                           | Qué hace                                                                           | Por qué no alcanza la plataforma                                                | Licencia                       |
| --------------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------ |
| `react`                           | El modelo de componentes de la interfaz (ADR-002)                                  | El DOM no trae componentes con estado ni reconciliación                         | MIT                            |
| `react-dom`                       | Dibuja los componentes de React en el documento                                    | Es la otra mitad de React; sin él no se monta nada                              | MIT                            |
| `@tanstack/react-router`          | Rutas tipadas: el inicio, las páginas de estado y "no encontrada" (ADR-002)        | El navegador tiene historial, no rutas tipadas ni una ruta por defecto          | MIT                            |
| `@tanstack/react-query`           | Caché de datos del servidor **solo en memoria** y reintento a pedido (BR3.5)       | `fetch` no guarda ni comparte respuestas entre pantallas                        | MIT                            |
| `@radix-ui/react-slot`            | Deja que `Button` dibuje un enlace con su aspecto (patrón de shadcn/ui)            | React no pasa propiedades a un hijo arbitrario sin envolverlo                   | MIT                            |
| `@radix-ui/react-collapsible`     | Primitiva accesible del plegable (`Disclosure`)                                    | `<details>` no permite controlar el estado ni animar solo la opacidad           | MIT                            |
| `@radix-ui/react-tabs`            | Primitiva accesible de las pestañas, con su teclado (`Tabs`)                       | El navegador no tiene pestañas con roles ni flechas                             | MIT                            |
| `class-variance-authority`        | Las variantes de cada primitiva (tono, tamaño) sobre los tokens                    | Escribirlas a mano repite la misma tabla en cada componente                     | Apache-2.0                     |
| `clsx`                            | Arma la lista de clases de un componente                                           | Sin él cada componente concatena cadenas a mano                                 | MIT                            |
| `tailwind-merge`                  | Resuelve clases de Tailwind en conflicto para que una variante sobrescriba la base | Tailwind no decide entre dos clases de la misma propiedad                       | MIT                            |
| `@phosphor-icons/react`           | Los íconos del sistema de diseño, siempre decorativos junto a su texto (BR7.7)     | El navegador no trae íconos; dibujarlos a mano rompe la consistencia            | MIT                            |
| `@fontsource/ibm-plex-sans`       | La fuente del cuerpo de texto, servida desde el propio origen (FD-U6-4)            | Cargarla de un servicio externo le habla a un tercero en cada visita (SEC-U6.2) | OFL-1.1 (la fuente; ver abajo) |
| `@fontsource/bricolage-grotesque` | La fuente del título del inicio, desde el propio origen                            | La misma razón: cero peticiones a terceros                                      | OFL-1.1 (la fuente; ver abajo) |
| `@fontsource/jetbrains-mono`      | La fuente de los datos (pólizas, identificadores), desde el propio origen          | La misma razón: cero peticiones a terceros                                      | OFL-1.1 (la fuente; ver abajo) |

## Desarrollo y pruebas (no llegan al navegador)

| Paquete                       | Qué hace                                                                                                              | Por qué no alcanza la plataforma                                                         | Licencia            |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | ------------------- |
| `typescript`                  | El comprobador de tipos: una clave del catálogo que no existe es un error (BR2.3)                                     | Node ejecuta JavaScript, no comprueba tipos                                              | Apache-2.0          |
| `vite`                        | Compila la interfaz a estáticos con huella en el nombre (BR6.3)                                                       | El navegador no resuelve paquetes ni JSX                                                 | MIT                 |
| `@vitejs/plugin-react`        | Transforma JSX para Vite                                                                                              | Vite no transforma JSX de React por sí solo                                              | MIT                 |
| `tailwindcss`                 | Genera los estilos a partir de los tokens (BR1.5)                                                                     | Escribir cada utilidad a mano pierde la escala de tokens                                 | MIT                 |
| `@tailwindcss/vite`           | Integra Tailwind en la compilación de Vite                                                                            | Sin él Tailwind no entra en la compilación                                               | MIT                 |
| `@hey-api/openapi-ts`         | Genera el cliente tipado desde el esquema OpenAPI, en versión exacta (C-28, BR3.1)                                    | Un cliente escrito a mano se separa del esquema sin que nadie lo note                    | MIT                 |
| `vitest`                      | El corredor de las pruebas de componentes                                                                             | Node trae un corredor, pero no transforma TypeScript ni JSX con la configuración de Vite | MIT                 |
| `@vitest/coverage-v8`         | La cobertura de la interfaz en el formato común con Python (NFR18)                                                    | Vitest no mide cobertura sin su proveedor                                                | MIT                 |
| `jsdom`                       | El documento en el que corren las pruebas de componentes                                                              | Node no tiene DOM                                                                        | MIT                 |
| `@testing-library/react`      | Dibuja componentes y los busca como los encuentra una persona (por rol y nombre)                                      | Las pruebas contra la estructura interna prueban la implementación, no la conducta       | MIT                 |
| `@testing-library/dom`        | La base de consultas que exige `@testing-library/react` como dependencia par                                          | Es un requisito de la anterior                                                           | MIT                 |
| `@testing-library/user-event` | Simula teclado y puntero como una persona (Tab, flechas, clic)                                                        | Disparar eventos sueltos no reproduce el foco ni el orden real                           | MIT                 |
| `@playwright/test`            | El arnés de extremo a extremo en Chromium, Firefox y WebKit (F9)                                                      | Ninguna herramienta instalada maneja tres motores reales ni emula red y CPU lentas       | Apache-2.0          |
| `@axe-core/playwright`        | El analizador automático de accesibilidad dentro del arnés (BR7.2)                                                    | No hay otra forma automática de medir contraste, roles y nombres en cada pantalla        | MPL-2.0 (ver abajo) |
| `eslint`                      | El linter, con sus reglas de seguridad como compuerta dura                                                            | TypeScript no detecta patrones inseguros ni de accesibilidad                             | MIT                 |
| `@eslint/js`                  | Las reglas recomendadas de JavaScript para ESLint                                                                     | Es la configuración base de ESLint 10                                                    | MIT                 |
| `typescript-eslint`           | Reglas de ESLint con información de tipos                                                                             | ESLint solo no entiende TypeScript                                                       | MIT                 |
| `eslint-plugin-security`      | Las reglas de seguridad del linter (`team.md`, Code Style)                                                            | Ni ESLint ni TypeScript las traen                                                        | Apache-2.0          |
| `eslint-plugin-react`         | Reglas de React, incluida la que prohíbe insertar HTML desde datos (SEC-U6.8)                                         | ESLint no conoce React                                                                   | MIT                 |
| `eslint-plugin-react-hooks`   | Las reglas de los ganchos de React                                                                                    | ESLint no conoce los ganchos                                                             | MIT                 |
| `eslint-plugin-jsx-a11y`      | Reglas de accesibilidad de JSX: etiquetas, roles, íconos (BR7.7)                                                      | ESLint no revisa la accesibilidad del marcado                                            | MIT                 |
| `eslint-plugin-boundaries`    | La frontera: solo `src/shared/api-client/` usa el cliente generado y ninguna pantalla trae otra librería HTTP (BR3.1) | Las reglas de ESLint no expresan dependencias entre carpetas                             | MIT                 |
| `prettier`                    | El formateador del proyecto                                                                                           | Node no formatea código                                                                  | MIT                 |
| `jiti`                        | Deja que ESLint lea su configuración escrita en TypeScript                                                            | ESLint solo carga configuración en JavaScript                                            | MIT                 |
| `@types/node`                 | Los tipos de Node para las configuraciones y el arnés                                                                 | TypeScript no trae los tipos de Node                                                     | MIT                 |
| `@types/react`                | Los tipos de React                                                                                                    | React no publica sus tipos en su paquete                                                 | MIT                 |
| `@types/react-dom`            | Los tipos de React DOM                                                                                                | La misma razón                                                                           | MIT                 |

## Sustituciones de versión

| Paquete         | Sustitución                                                                       | Razón                                                                                                                                                                                                                                                                                                                                                                 | Licencia     |
| --------------- | --------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| `js-yaml`       | 4.3.2 para `@hey-api/json-schema-ref-parser` (`pnpm-workspace.yaml`, `overrides`) | El lector de esquemas del generador fija 4.2.0, con tres avisos altos de consumo de CPU al leer YAML (GHSA-52cp-r559-cp3m, GHSA-5p4m-2wfm-xmqj, GHSA-2883-xcg3-v3hh), corregidos en 4.3.2 de la misma rama. Solo corre al generar el cliente, nunca en el navegador                                                                                                   | MIT          |
| `source-map-js` | >=1.2.2 para todo el árbol (`pnpm-workspace.yaml`, `overrides`)                   | Las versiones anteriores bloquean el bucle de eventos al leer un mapa de fuentes indexado con desplazamientos absurdos (GHSA-68fv-2mgg-jv7q). Llega por veinticuatro caminos de compilación —vite, postcss, el generador del cliente— y ninguno del navegador; hay versión corregida de la misma rama, publicada el 2026-09-30, y por eso se fija en vez de excusarse | BSD-3-Clause |
| `handlebars`    | >=4.7.10 para todo el árbol (`pnpm-workspace.yaml`, `overrides`)                  | Hasta la 4.7.9 una plantilla puede inyectar código al compilarse (GHSA-8r5x-fm3f-whwj y GHSA-p8wg-vrv2-v86f, críticos, avisados el 2026-10-11). Llega solo por `eslint-plugin-boundaries`, la cadena del linter: corre sobre este repositorio y nunca en el navegador; hay versión corregida de la misma rama, y por eso se fija en vez de excusarse                  | MIT          |

## Avisos de seguridad aceptados

Un aviso alto que la auditoría no bloquea **solo** cuando no hay versión que lo
arregle, y siempre con su fecha de revisión. `mise run supply:check` falla si un
aviso ignorado no tiene su fila aquí, o si su fecha ya pasó: una excepción sin
caducidad es una excepción que nadie vuelve a mirar. Vale para las dos
auditorías: `ignoreGhsas` de pnpm (`pnpm-workspace.yaml`) y `--ignore-vuln` de
`pip-audit` (tarea `audit` de `mise.toml`).

| Aviso               | Paquete                                                             | Por dónde llega                                      | Por qué no bloquea                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Revisar    |
| ------------------- | ------------------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------- |
| GHSA-vfj7-8cjw-p6xm | `braces` <=3.0.3 (sin parche publicado)                             | `eslint-plugin-boundaries > micromatch > braces`     | Es la cadena del linter: corre sobre los archivos de este repositorio con nuestros propios patrones, en la máquina de quien desarrolla y en la tubería. No llega al navegador, no procesa nada que escriba un visitante y no está en el camino de ninguna petición                                                                                                                                                                                                                                                             | 2026-11-03 |
| CVE-2026-104873     | `langgraph-sdk` 0.3.15 (la corregida, 0.4.4, exige `websockets<17`) | `langgraph > langgraph-sdk`, del aplicativo (Python) | La falla está en los decoradores de autorización personalizada de un servidor de la API de LangGraph (`@auth.on.threads` y compañía); el aplicativo no importa `langgraph_sdk` ni levanta ese servidor, así que el código vulnerable no se ejecuta. La versión corregida necesita `websockets<17` y el adaptador de voz necesita `websockets>=17.1` (FD-U15-5): hoy no hay resolución que la incluya. Se revisa cuando `langgraph-sdk` admita websockets 17 o `langgraph` deje de arrastrarla. Un aviso nuevo sigue bloqueando | 2026-11-13 |

## Recursos: fuentes e íconos

Los paquetes de Fontsource declaran la licencia de la **fuente** que traen; sus
hojas de estilos las genera el proyecto Fontsource, cuyo código es MIT. La
licencia de cada fuente va aparte, con su atribución, porque es la que obliga al
redistribuirla junto al aplicativo.

| Recurso             | Licencia                  | Atribución                                                                                                                           |
| ------------------- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| IBM Plex Sans       | SIL Open Font License 1.1 | Copyright 2019 IBM Corp.                                                                                                             |
| Bricolage Grotesque | SIL Open Font License 1.1 | Copyright 2022 The Bricolage Grotesque Project Authors (https://github.com/ateliertriay/bricolage)                                   |
| JetBrains Mono      | SIL Open Font License 1.1 | Copyright 2020 The JetBrains Mono Project Authors (https://github.com/JetBrains/JetBrainsMono)                                       |
| Phosphor Icons      | MIT                       | Copyright (c) 2020 Phosphor Icons (también en `site/PHOSPHOR-LICENSE.txt`)                                                           |
| Lucide (la marca)   | ISC                       | Copyright (c) 2026 Lucide Icons and Contributors: el ícono `audio-waveform`, que es la marca de Cautelia (`site/LUCIDE-LICENSE.txt`) |

La OFL permite usar, empaquetar y servir las fuentes con el aplicativo; lo que
prohíbe es venderlas solas y usar su nombre reservado en una versión modificada.
Aquí se sirven sin modificar.

**Sobre MPL-2.0.** `@axe-core/playwright` (y `axe-core`, que trae) es la única
licencia de la lista que no es permisiva sin condiciones: obliga a publicar los
cambios hechos **a los archivos de esa librería**. El proyecto no la modifica ni
la distribuye --corre solo en el arnés--, así que no impide publicar el
repositorio (D-017).

**Sobre shadcn/ui.** No se instala como dependencia: es un patrón cuyo código se
copia al repositorio (`src/shared/ui/`) y se tematiza con los tokens. Las
primitivas de Radix que ese código importa sí son dependencias y están arriba.
El `Select` es el nativo del navegador y no el menú de Radix: el de Radix inyecta
estilos en línea que la política de contenido (`style-src 'self'`, CG-U6-2)
bloquea.
