# Resumen del código — U7 `synthetic-data`

U7 deja el generador de datos sintéticos del proyecto:
- textos fuente redactados una vez con Gemini, revisados y versionados;
- un generador determinista que compone, siempre con los mismos bytes, el corpus
  de Stonecroft Mutual en español y el de Sunmeadow Auto en inglés, las copias de
  Knotwell, las pólizas emitidas, los casos sembrados, DS-8 y los valores
  personales ficticios;
- la compuerta por huellas que impide texto de formularios de terceros;
- la carga de los casos sembrados en la base por la API de U4.

Se construyó por la rama determinista, en tres tandas y dos commits más:
- pasos 1 a 6 en `139bac4`;
- pasos 7 y 8 en `6156282`;
- pasos 9 a 13 en `ae2062d`;
- el arreglo del reconocedor de correos, en `3b4de46`;
- el veredicto de Miguel sobre las muestras, en `609f951`.

## Resultados

| Compuerta | Resultado |
| --- | --- |
| `mise run test:u7` | 286 pruebas en verde |
| Suites que U7 tocó | `test:u2` 75, `test:u3` 270, `test:u4` 165 y `test:u15` 113, todas en verde |
| `mise run cov` | **88,79 %** agregado, sin exclusiones nuevas. Módulos críticos: aislamiento 93,61 %, redacción 94,64 %, esquema del caso 94,14 % |
| `mise run lint` | En verde, con 30 contratos de importación. Los 5 avisos de ESLint en `app/frontend/vite.config.ts` ya estaban |
| `types`, `schema:check`, `content:check`, `tenancy:literals` | En verde |
| `mise run synthetic:check` | En verde, 0,16 s. Lo corre `scripts/verify.sh` en el paso de chequeos de contenido (TECH-U7.1, TECH-U7.4) |
| `mise run contracts:check` | En verde después del commit de cada tanda |
| GitHub Actions (`verify`) | En verde sobre `139bac4` y sobre `609f951`, con los 9 pasos de `scripts/verify.sh`; en rojo sobre `ae2062d` (incidente 5, abajo) |

## El corpus

| | Stonecroft (es) | Sunmeadow (en) | Knotwell |
| --- | --- | --- | --- |
| Formularios | 8 | 8 | 16, copias exactas |
| Cláusulas | 104 | 103 | 207 |
| Endosos | 5, sin el de transporte | 5, con el de transporte | 10 |
| Distractores | 8 (3 de versión anterior y 5 casi duplicados) | 8 | 16 |
| Relaciones entre cláusulas | 35 | 30 | 65 |
| Pólizas emitidas | 6 | 6 | 6, cada una con su emisora declarada |
| Casos sembrados | 28 | 26 | 18 |

- **Valores personales ficticios:** 188, de 7 tipos en los 2 idiomas.
- **Manifiesto:** 33 entradas y 159 salidas.

**Las cinco diferencias declaradas**, cada una comprobada contra el corpus:
1. Solo Sunmeadow tiene el endoso que amplía los gastos de transporte.
2. Solo Stonecroft reabre la exclusión de la Parte A para viajes por plataforma
   registrada.
3. Solo Stonecroft define el vehículo sustituto temporal.
4. Solo Sunmeadow reabre la exclusión de llantas.
5. Solo Sunmeadow tiene un endoso que cambia la definición de vehículo cubierto,
   y el plazo base es distinto: 10 días en una y 20 en la otra.

## Redacción y revisión

- **Llamadas a Gemini:** las 20 partes se redactaron con Gemini en plan
  gratuito. Hubo 28 llamadas: 20 correctas, 7 cortadas por espera y 1 rechazada.
  Cada parte cortada se repitió una sola vez.
- **Gasto:** se facturaron 0 USD. A precio de lista habrían sido unos 0,028
  USD, más 0,0026 USD de tres llamadas de diagnóstico.
- **Límites:** no hubo límite de ritmo ni cuota agotada, así que CG-U7-7 no se
  activó.
- **Revisión contra P8:** los borradores en inglés calcaban giros de formulario.
  El agente reescribió a mano 90 de las 103 cláusulas de Sunmeadow y 31 de las
  104 de Stonecroft, y cambió las cifras de la póliza de referencia por otras
  propias.
- **Huellas:**
  - 7.848 secuencias distintas, sacadas de la edición 1994 del PP 00 01 (Maine
    Bureau of Insurance) y de la edición 2018 (copia de CURE Auto Insurance).
  - **Cero cláusulas coinciden**, sobre las 414 del corpus. No hubo nada que
    reescribir.
  - En el repositorio solo hay hashes; los specimens quedan en `tmp/specimens/`,
    ignorado por git.
- **Muestra humana (AC5.4.5 y AC5.5.6):** Miguel leyó el 2026-09-21 las diez
  cláusulas de cada emisora y las dos pasaron (`own_text_structure_ok`, commit
  `ae2062d`). El veredicto está en el manifiesto.

## Decisiones del conductor durante la generación

1. **La fuga de U3 se corrigió hacia adelante.** La prueba de canarios encontró
   que "My name is Megan Hughes." salía sin redactar, porque el modelo de inglés
   etiqueta ese nombre como organización. Hay dos reglas nuevas en U3:
   - Tras una frase de autoidentificación ("my name is", "me llamo", "soy",
     etc.) se tapan de dos a cuatro palabras con mayúscula, en los dos idiomas a
     la vez, salvo que lleven una palabra de organización declarada.
   - El VIN es un tipo nuevo y se tapa entero.

   Las regresiones se escribieron primero y se vieron fallar: 31 en rojo.
   Ninguna precisión medida bajó; la exhaustividad de nombres en los turnos
   sembrados en español subió de 36/42 a 42/42. El p95 por texto pasó de 6,4 a
   6,7 ms. Enmienda en C-13.
2. **Casos sembrados por criterio (AC5.6.2).** U7 siembra:
   - la matriz de 7 estados por 3 aseguradoras por 2 idiomas;
   - un caso cerrado por resolución;
   - los casos que describen los criterios de las unidades ya construidas: 25
     criterios de U1 a U6, U10 y U15.

   Otros 108 criterios de unidades posteriores mencionan datos sembrados. Cada
   una añadirá su criterio y su caso en `seeded_criteria.yaml` al construirse, y
   BR6.2 lo comprueba en la siguiente generación.
3. **Formulario de 2018 de CURE.** El regulador de Virginia bloquea el acceso
   desde el país de Miguel, así que la edición de 2018 se tomó de la copia que
   publica CURE Auto Insurance. Miguel autorizó las dos descargas.
4. **Tres enmiendas de diseño** (FD-U7-7 a FD-U7-9): los turnos de los casos
   son un tipo de texto fuente, los valores personales tienen su propio archivo,
   y la siembra vive en `untangle.server`.
5. **Incidente: `main` en rojo con `ae2062d`, arreglado en `3b4de46`.**
   - **Qué pasó:** con la caché de `tldextract` vacía, como en GitHub Actions,
     el reconocedor de correos de U3 intentaba descargar la lista pública de
     sufijos de publicsuffix.org la primera vez que validaba un dominio. La
     guardia de red de las pruebas de U7 lo detuvo.
   - **Por qué no se vio antes:** en la máquina de Miguel la caché ya existía.
   - **El arreglo:** el reconocedor lee la lista de la copia que trae el
     paquete, nunca de internet, y `tldextract` pasa a dependencia declarada.
   - **Prueba de regresión:** reproduce la caché vacía con la red bloqueada en
     un proceso aparte. Se comprobó primero que el reconocedor original sí
     intentaba salir.
   - **Orden de los commits:** el arreglo se reordenó antes del commit del
     veredicto de Miguel, para que sobre `main` en rojo lo primero fuera solo la
     corrección.

## Desviaciones declaradas

- **U4, cambio aditivo:** `TransitionContext` gana `derivation_reason`, porque
  sin él ningún consumidor podía derivar un caso por la API. Enmienda en C-12.
- **U5:** el adaptador de Gemini inlinea `$defs` y `$ref` del esquema de salida
  estructurada, que Gemini rechaza con 400. La respuesta se sigue validando
  contra el modelo completo.
- **Modelos ampliados** respecto de `entities.md`: el caso sembrado ganó tipo de
  registro, canal, motivo de derivación, número de póliza y estado por campo;
  hay `differences.yaml` y `seeded_criteria.yaml` en la raíz de las fuentes. La
  fuente de verdad de esas formas pasa a ser
  `app/backend/src/untangle/synthetic_data/models.py`, con sus JSON Schema en
  `app/contracts/schemas/`.
- **Rutas:**
  - los casos viven en `tenants/<aseguradora>/cases/<idioma>/<nombre>.json`,
    porque la clave lleva barras;
  - los distractores de los dos tipos viven en la edición 2025, que ninguna
    póliza usa;
  - `synthetic:fingerprints` vive en `untangle.workspace`, porque el generador
    no puede conocer `tmp/`;
  - la normalización de huellas está una sola vez, en
    `untangle/text_fingerprints.py`.
- **`manifest.schema.json` es ahora el manifiesto del corpus**, como piden C-26
  y C-28; el de conjuntos de datos de U1 pasó a `dataset-manifest.schema.json`.
- **La prueba de la muestra** exigía que siguiera sin veredicto. Ahora comprueba
  que el veredicto, si existe, lleva fecha y commit.

## Lo que queda abierto

- **AC5.6.4** está diferido a U20, en la pasada de publicación: devolver cada
  noche los sembrados a su estado. U7 los entrega con el origen `generator`.
- **Sobre-redacción conocida y aceptada:** "This is Part A" sale como
  `[NAME 1]`. U3 decidió en su diseño funcional (decisión 9, respuesta Q3 de
  Miguel) que alguna redacción de más es el costo aceptado.

## Archivos

287 rutas del espacio de trabajo, listadas en `source-manifest.json`:
- 192 en `app/data/`: fuentes, corpus, casos, DS-8, manifiesto y valores
  personales;
- el paquete `synthetic_data/` con su plantilla de redacción;
- los comandos en `server/` y `workspace/`;
- 14 esquemas;
- los cambios en U3, U4 y U5;
- las pruebas unitarias y de integración.

## Trazabilidad

`traceability.json` cubre 53 identificadores:
- los 20 criterios de US5.3 a US5.6;
- las 30 reglas;
- NFR10.7, NFR11.10 y NFR20.4.

52 apuntan a un archivo que existe; AC5.6.4 queda diferido a U20.
