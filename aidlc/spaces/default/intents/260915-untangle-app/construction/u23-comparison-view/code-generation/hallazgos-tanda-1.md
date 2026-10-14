# Hallazgos — U23 `comparison-view`, tanda 1

Sesión en la nube, rama `claude/new-session-tx5v1e`, sobre `origin/main` en `ad7791f`.

## Qué se construyó

| Pieza | Dónde |
| --- | --- |
| Estado puro por columna (`idle`, `loading`, `answered`, `failed`, `rejected`) | `app/frontend/src/pages/comparison/comparison-state.ts` |
| Pantalla: divulgación, sugerencias, fuera de propósito, tres columnas | `comparison-page.tsx` |
| Ruta `/compare` (la que el inicio ya enlaza) | `comparison-routes.tsx`, `src/app/router.tsx` |
| Costura de la tanda 2 (`askInsurer`, `exampleIssuerName`) | `comparison-port.ts` |
| Textos, en español e inglés, con paridad | `app/config/copy/{es,en}.yaml` + generados |
| Entrada del arnés, pantalla de **visitante**, con directorio tipado `SiteDirectory` | `e2e/visitable-routes.ts` |

## Roturas: cada regla rota y qué se cayó

| Rotura | Se cayó |
| --- | --- |
| `rejected` se guarda como `failed` (colapso) | 3 pruebas: estado puro, "failed y rejected no se dibujan igual", rechazo con su frase |
| La vista espera a las tres (`Promise.all`) | 5 pruebas, entre ellas "una columna que responde aparece sin esperar" |
| Un fallo cierra también las otras | 6 pruebas |
| La agencia no nombra su emisor | "la columna de la agencia nombra a quien emitió su póliza" |
| Campo de pregunta antes de la divulgación | "aparece antes de que exista el campo" (y 13 más por etiqueta duplicada) |
| "No encuentro una cláusula" dibujado como fallo | "se dice distinto de 'no se pudo revisar'" |
| El rechazo no dice su límite | "el rechazo por límite dice cuál fue…" |
| El rechazo usa el aviso de fallo | 2 pruebas |
| La vista redacta una frase sobre la diferencia | "no escribe nada propio sobre la diferencia" |
| Se puede preguntar con una columna cargando | "no manda una segunda pregunta mientras alguna columna carga" |
| La pregunta fuera de propósito se manda igual | "se explica, enlaza el chat… y no se manda" |
| Se ofrece la pregunta sin emisor de la agencia | 3 pruebas |
| Las sugerencias no desaparecen | **no cayó nada** → se añadió la prueba "las sugerencias se quitan…" y ahora cae |
| Frase en línea entre comillas | `copy:check` (BR3.3 de U1) |
| Frase en línea como **texto suelto de JSX** | **no cayó nada**: `copy:check` solo ve literales entre comillas → se añadió `comparison-copy.test.ts`, que sí cae |

## Hallazgos que necesitan decisión

1. **El emisor de la póliza de la agencia no sale de ningún contrato.** BR1.2 pide que la
   columna de Knotwell diga quién emitió su póliza. El dato existe (`issuer_tenant`, en
   `data/tenants/knotwell/issued_policies/POL-200341.json`: `sunmeadow`) pero
   `TenantPresentation` / `GET /api/site` no lo traen. No lo resolví: es decidir si el
   emisor es **configuración** (campo en `tenant.yaml`, que duplica lo que el generador
   deriva por idioma en `synthetic_data/policies.py`) o un **dato derivado** que el
   directorio lee del corpus. Lo que hice: la divulgación falla **cerrada**: si una
   agencia llega sin emisor, no se ofrece el campo de pregunta y se muestra un aviso. La
   pantalla es completa y está probada con el emisor presente.
   **Consecuencia para el arnés:** como el contrato no lo trae, el cuerpo tipado de
   `/api/site` no puede incluirlo, así que el arnés mide hoy el estado "divulgación
   incompleta" y **no la vista llena**. El día que el contrato crezca, `tsc` rompe en
   `DIRECTORIO_DE_EJEMPLO` y obliga a completarlo. Hasta entonces, la vista llena no está
   medida por el arnés.
2. **Quién decide que una pregunta es "fuera de propósito" (AC2.9.6).** La pantalla recibe
   un `scope` y, sin él, toda pregunta es de cobertura. No inventé una heurística en el
   cliente. Tanda 2: ¿lo decide el servidor al abrir el caso, o un clasificador
   determinista? Sin esto, "escribo el reporte de un siniestro" no llega a mostrar el
   texto de fuera de propósito en producción.
3. **El idioma de la pregunta (BR2.1)** no está en el puerto `AskInsurer(tenantId, question)`:
   es de la tanda 2, y habrá que ampliar la firma.
4. **Hueco en `copy:check`:** no ve texto suelto en JSX. Lo cubrí solo para esta pantalla.
   Vale la pena una tarea aparte que lo cierre para todo `src/pages/`.

## Lo que no pude correr

- `scripts/verify.sh` entero, `mise run cov`, pruebas de integración y el arnés de
  accesibilidad/Playwright: no hay base, contenedores ni navegadores. **La revisión local
  tiene que correr `mise run a11y`** para `comparison` (dos idiomas, dos modos, 360 px).
  Lo que escribí pensando en él: un solo `h1`, `label` en el campo, objetivos de 44 px
  (los botones de ejemplo usan `min-h-11` y se parten en líneas), estado también en texto
  y no solo en color, región `aria-live` por columna.
- No verifiqué contraste con herramienta: usé solo tokens semánticos.

## Entorno

- `mise run deps:install` / `models:install` **fallaron**: el túnel rechazó la descarga de
  Python. Usé `uv python install 3.13` → **Python 3.13.15** (la versión anclada) y corrí
  los comandos de `mise.toml` directamente. Los modelos de spaCy sí bajaron.
- En verde: `ruff format --check`, `prettier --check`, `ruff check`, `lint-imports`,
  `eslint` (0 errores; 17 avisos que ya existían), `mypy`, `tsc`, `copy:check`,
  `content:check`, regeneración de contratos sin deriva (solo cambiaron los dos módulos
  de copy generados, que van en el commit) y `vitest` completo del frontend (366 pruebas).

---

## La revisión local de la tanda 1

Escrita en la sesión local el 2026-09-30. Corrí las 29 pruebas de la pantalla, las siete
compuertas baratas que esta tanda puede mover, **y el arnés de accesibilidad para
`comparison`**, que la nube no podía: las cuatro combinaciones de idioma y modo más la de
dibujo, las cinco en verde. Y rompí tres reglas más.

### Lo que la tanda hizo bien, y conviene no perder

- **Un estado por columna y ninguno para la vista**, con el tipo cerrado y los cinco
  valores en una unión discriminada. Con eso `settleColumn` no puede tocar una columna
  ajena sin que se caiga una prueba.
- **«No encuentro una cláusula» es un valor propio** y no una lista de citas vacía. Esa
  distinción es la que el proyecto sostiene en todas partes, y aquí llega hasta el tipo.
- **El puerto declara la costura en un módulo aparte** y mientras tanto hace lo honesto:
  `askInsurer` dice que no pudo revisar la póliza y `exampleIssuerName` dice que no sabe
  quién emitió. Nada finge funcionar.
- **Fallar cerrado en la divulgación**: sin emisor, no se ofrece el campo de pregunta.
  Una póliza de agencia sin emisor afirmaría algo falso, y la tanda prefirió no preguntar
  antes que afirmarlo.
- **Encontró un hueco de `copy:check` y lo cerró donde podía**: el chequeo solo ve cadenas
  entre comillas, así que texto suelto dentro de JSX se le escapa. Añadió
  `comparison-copy.test.ts` para esta pantalla y **dejó dicho que el hueco sigue abierto
  para las demás**, que es exactamente lo que había que hacer con un hallazgo más grande
  que la tanda.

### Lo que se corrigió aquí

**Una rotura que no caía nada: el puerto podía inventar un emisor.** Cambiar
`exampleIssuerName` para que devolviera el nombre de la propia agencia —«la póliza de
Knotwell la emitió Knotwell», que es falso— dejaba las 29 pruebas en verde. Es el atajo
que un cableado apurado tomaría, y la honestidad de la divulgación entera dependía de una
función que nada constreñía.

Se añadió `comparison-port.test.ts` con el invariante que **sobrevive a la tanda 2**: el
emisor nunca es el nombre de la propia agencia, y mientras el contrato no lo traiga es
`null` y no una adivinanza. Más una tercera: preguntar sin cablear da `failed` y no una
respuesta vacía, que se dibujaría como «no encuentro una cláusula» —un resultado
verificado— en vez de como un fallo.

Las otras dos roturas propias sí cayeron: considerar completa una divulgación sin emisor
(dos pruebas) y hacer que el fallo de una columna tocara a las demás (cuatro).

### Las dos preguntas, decididas

Están escritas como Q2 y Q3 en `functional-design-questions.md`. En corto:

- **El emisor va a la configuración**, `example_policy_issuer` al lado de
  `example_policy`, obligatorio cuando la aseguradora es una agencia, **más un chequeo que
  lo compara con `issuer_tenant` del archivo versionado de la póliza**. El dato existe en
  los datos versionados, pero `presentation()` construye la respuesta del inicio solo con
  lo que la carpeta trae —su docstring lo dice— y leer corpus desde ahí cruzaría esa
  frontera. Declarar y comprobar, en vez de duplicar o acoplar.
- **«Fuera de propósito» lo decide el reconocedor determinista que ya existe**,
  `coverage_detour.is_coverage_question`, el mismo que usa la apertura de caso del chat.
  Corre en el servidor sobre la superficie de la comparación: un mensaje que no es
  pregunta de cobertura no se admite ahí, y la respuesta es el texto del catálogo. Sin eso,
  una pregunta fuera de propósito abriría **tres casos de siniestro** desde una vista que
  compara coberturas.

### Un hallazgo que no es de esta unidad

**El arnés mide hoy la pantalla incompleta.** Como el emisor no existe en el contrato, la
divulgación nunca se completa y el campo de pregunta no se ofrece: la línea base de
accesibilidad de `comparison` está tomada sobre ese estado. No es un defecto de la tanda
—no podía ser de otra forma— y se corrige solo: cuando la tanda 2 lleve el emisor al
contrato, la respuesta declarada del arnés podrá traerlo y la medición pasará a ser la de
la pantalla llena. Queda dicho para que nadie lea esa línea base como la definitiva.
