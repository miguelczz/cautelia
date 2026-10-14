# Decisiones de herramientas — U6 `web-shell`

El lenguaje, el framework y las herramientas de la interfaz ya los fijó ADR-002:
TypeScript estricto sobre Node 24, pnpm con lockfile congelado, React con Vite,
TanStack Router y Query, Tailwind con shadcn/ui, cliente generado desde el
esquema OpenAPI, Vitest con Testing Library y Playwright con axe. U1 dejó
instalado solo lo necesario para el módulo tipado de claves. Esta etapa decide
**qué paquetes concretos entran con U6**, con qué licencia, y dos reglas que las
herramientas tienen que cumplir para no romper objetivos ya afirmados.

**Ninguna versión se escribe aquí.** La versión exacta de cada paquete la fija el
lockfile al generar el código, con la espera de tres días que ya exige la cadena
de suministro (SEC-U1.4, `mise run supply:check`), y la auditoría la revisa en
cada corrida. Escribir versiones en este documento produciría una segunda fuente
que se desactualiza en la primera actualización.

## Paquetes que entran con U6

### Ejecución (llegan al navegador)

| Paquete | Para qué | Licencia |
| --- | --- | --- |
| `react`, `react-dom` | Framework de interfaz (ADR-002) | MIT |
| `@tanstack/react-router` | Rutas tipadas y filtros en la URL (ADR-002) | MIT |
| `@tanstack/react-query` | Datos del servidor en memoria, sin capa persistente (BR3.5) | MIT |
| Primitivas de Radix que genera shadcn/ui, `class-variance-authority`, `clsx`, `tailwind-merge` | Componentes accesibles tematizados con los tokens; shadcn/ui copia el código al repositorio en vez de instalarse como paquete | MIT; `class-variance-authority` Apache-2.0 |
| `@phosphor-icons/react` | Íconos del sistema de diseño | MIT (ya registrado en `site/PHOSPHOR-LICENSE.txt`) |
| Fuentes de Fontsource para Bricolage Grotesque, IBM Plex Sans y JetBrains Mono | Las tres familias servidas desde el propio origen (FD-U6-4) | Fuentes SIL OFL 1.1; código del paquete MIT |

### Desarrollo y pruebas (no llegan al navegador)

| Paquete | Para qué | Licencia |
| --- | --- | --- |
| `vite`, `@vitejs/plugin-react` | Compilación a estáticos | MIT |
| `tailwindcss` y su complemento de Vite | Estilos a partir de los tokens | MIT |
| `@hey-api/openapi-ts` | Generador del cliente tipado, en versión exacta (C-28) | MIT |
| `@testing-library/react`, `@testing-library/user-event`, `jsdom` | Pruebas de componentes con Vitest | MIT |
| `@playwright/test` | Arnés de extremo a extremo en los tres motores (Q1) | Apache-2.0 |
| `@axe-core/playwright` | Analizador automático de accesibilidad dentro del arnés | MPL-2.0 |
| `eslint-plugin-react`, `eslint-plugin-react-hooks`, `eslint-plugin-boundaries` | Reglas de React (incluida la que prohíbe insertar HTML, SEC-U6.8) y la frontera que obliga a usar solo el cliente generado (BR3.1) | MIT |

**Sobre MPL-2.0.** Es la única licencia de la lista que no es permisiva sin
condiciones: obliga a publicar los cambios que uno haga **a los archivos de esa
librería**. El proyecto no la modifica ni la distribuye —corre solo en las
pruebas—, así que no impide publicar el repositorio (D-017). Queda registrada con
esa nota para la revisión de licencias de la semana 12.

**Dónde se registra cada licencia.** En Python, cada dependencia lleva al lado,
en `app/backend/pyproject.toml`, un comentario con qué hace, por qué no alcanza
la biblioteca estándar y su licencia. El manifiesto de la interfaz es JSON y no
admite comentarios, así que la misma línea por dependencia va en un archivo
nuevo, `app/frontend/DEPENDENCIES.md`, que se crea con la generación de código de
esta unidad.

**Las fuentes, distinto de la landing.** La landing carga estas mismas tres
familias desde Google Fonts, por hoja de estilos remota y sin versión fijada
(`aidlc/spaces/default/codekb/untangle/technology-stack.md`, stack de la
landing). El aplicativo no copia ese patrón: las sirve desde su propio origen
con versión fijada en el lockfile (FD-U6-4, SEC-U6.2), para que ninguna visita
le hable a un tercero y para que la página de espera no dependa de él.

**Servidor: ninguna dependencia nueva.** Servir los estáticos, el retorno a la
aplicación y las cabeceras se hacen con lo que ya trae FastAPI sobre Starlette.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| NFR18.4 | El código de la interfaz de U6 entra al cálculo agregado de cobertura sin exclusiones nuevas | **80 % o más agregado**, con la misma lista de exclusión de NFR18.3 | `mise run cov` |
| NFR21.3 | Los navegadores del arnés se instalan con una tarea propia y **no** en el camino del clon al reporte, igual que los modelos de lenguaje de U3, que tampoco van en ese camino | **Cero** descargas de navegadores en `mise run bootstrap` | `mise run bootstrap`, cronometrado por NFR21.2 |
| TECH-U6.1 | Cada dependencia de `app/frontend/package.json` tiene su línea en `app/frontend/DEPENDENCIES.md`: qué hace, por qué no alcanza la plataforma, y su licencia | **Todas**; la comprobación nueva que se añade a `mise run supply:check` falla nombrando la que falte | `mise run supply:check` |
| TECH-U6.2 | El cliente de la API se regenera en el mismo commit que cambia el esquema | **Sin deriva** | `mise run contracts:check` |

**NFR18.4, con una decisión explícita.** El cliente generado desde el esquema es
código, y **cuenta** en la cobertura. Excluirlo sería agregar una entrada a una
lista que existe para lo que no es código del aplicativo (la landing, los datos
generados y las migraciones), y agrandar esa lista es relajar el piso. Si algún
día el cliente generado baja el agregado del 80 %, se le lleva a Miguel como
decisión; no se excluye en silencio.

## Motores del arnés (Q1)

| Motor | Qué corre | Por qué |
| --- | --- | --- |
| Chromium | Todo: analizador, 360 × 640, teclado, movimiento reducido, peticiones de red, tiempos de NFR16.3 y PERF-U6.1 | Es el que permite emular red y CPU lentas desde el arnés |
| Firefox | Prueba de dibujo de cada pantalla registrada: carga sin errores de consola, sin desplazamiento horizontal y con el título visible | Diferencias reales de motor (fuentes, CSS) sin repetir lo que no cambia |
| WebKit | La misma prueba de dibujo | Safari en escritorio y en iOS |

## Navegadores declarados (PA-4, Q1)

Las dos últimas versiones mayores de Chrome, Edge, Firefox y Safari en
escritorio; Safari en iOS y Chrome en Android en sus dos últimas versiones
mayores. Es la lista de U6, que no usa WebRTC. **La condición de WebRTC pasa a
`nfr-requirements` de U16**, que abre el micrófono y puede medirla; hasta
entonces ADR-009 sigue pendiente de ese dato.

## Sources

- `../../../inception/domain-design/decisions.md` — ADR-002 (herramientas de la
  interfaz; scripts de instalación bloqueados; cliente generado).
- `../../../inception/contract-design/contract-summary.md` — C-28 (generador en
  versión exacta, frontera con `eslint-plugin-boundaries`).
- `../../../inception/refined-mockups/design-system-mapping.md` — familias
  tipográficas, íconos y sus licencias.
- `../functional-design/functional-spec.md` — FD-U6-4 y FD-U6-7.
- `mise.toml` — tareas `bootstrap`, `deps:install`, `models:install`, `cov`,
  `contracts:check` y `supply:check`.
- `aidlc/spaces/default/codekb/untangle/technology-stack.md` — stack de la
  landing (fuentes remotas sin versión) y del aplicativo.

## Assumptions & Open Questions

- **shadcn/ui no se instala como dependencia**: su herramienta copia el código de
  cada componente al repositorio. Las primitivas que ese código importa sí son
  dependencias y entran al lockfile con su licencia.
- **Las fuentes y los íconos son recursos, no solo paquetes**: su atribución va
  también en `app/frontend/DEPENDENCIES.md`, con la licencia de la fuente (SIL
  OFL 1.1) aparte de la del paquete que la trae (MIT).
