# Licencias de terceros

El repositorio es candidato a publicarse (D-017), así que la licencia de cada
dependencia tiene que estar decidida antes de esa fecha, no revisada por encima.
Este documento es el registro de esa decisión. El control que la hace cumplir es
`mise run licenses:check`, dentro del paso 8 de `scripts/verify.sh`.

## Cómo se controla

El control recorre el **árbol resuelto** de los dos gestores —transitivas
incluidas— y compara la licencia de cada uno contra la lista de
admitidas de `[tool.untangle.licenses]` en `app/backend/pyproject.toml`, donde
cada entrada lleva su razón escrita.

Tres decisiones que son el control y no adorno:

- **Exige que lo instalado sea lo que fija el lockfile.** Si falta un paquete, el
  control falla diciendo cuál, en vez de revisar medio árbol en silencio. Esa es
  la grieta por la que el hallazgo de abajo pasó desapercibido.
- **Lista de admitidas, no de bloqueadas.** Una lista de bloqueadas se queda
  corta con la primera licencia que nadie previó; una de admitidas, como máximo,
  pide una decisión escrita.
- **No adivina una familia.** "BSD" no dice si son dos cláusulas o tres, así que
  el paquete pasa a necesitar su entrada declarada con la fuente donde se leyó.

Lo que el control **no** cubre: los recursos que no son paquetes —voces, corpus,
tipografías sueltas— se registran a mano junto al recurso, como
`site/PHOSPHOR-LICENSE.txt`. Las tipografías que entran por npm las ve como
cualquier otro paquete.

## La revisión del 2026-09-27

Ninguna licencia impide publicar el repositorio. De los paquetes del árbol
resuelto —el control imprime cuántos son en cada corrida, y esa es la cifra buena—
las más restrictivas son:

| Licencia | Dónde | Qué obliga |
| --- | --- | --- |
| LGPL-3.0 | `psycopg`, el driver de PostgreSQL | Permitir sustituir la biblioteca, no liberar el programa que la usa. Se enlaza, no se deriva |
| MPL-2.0 | `certifi`, `pathspec`, `tqdm`, `axe-core`, `lightningcss` | Publicar los cambios **a esos archivos**. Ninguno se modifica aquí |
| OFL-1.1 | Las tres tipografías de `@fontsource/*` | Conservar el nombre reservado; prohíbe vender la fuente sola |
| GPL-3.0 | `es_core_news_md`, el modelo de español de spaCy | Ver abajo |

No hay AGPL ni SSPL en ninguno de los dos árboles.

## El modelo de español es GPL-3.0

`es_core_news_md` —el modelo de spaCy con el que el detector de datos personales
reconoce nombres de persona y de lugar en español— es **GPL-3.0**, y no por el
modelo: su corpus de entrenamiento, UD Spanish AnCora, lo es, y el propio archivo
de metadatos del modelo lo declara. El de inglés, `en_core_web_md`, es MIT.

Se le escapó a la revisión a mano porque los dos modelos no entran por el árbol
de dependencias que uno lee: entran por un extra, con su URL anclada por hash
(INF-U3-1). El control los ve porque pregunta al paquete instalado.

**Decisión de Miguel del 2026-09-27: se queda, y se dice por escrito.**

Por qué no bloquea publicar: el modelo **no está en el repositorio**. Se descarga
de su URL al instalar, y lo que se publica es código fuente que no lo contiene ni
deriva de él. La obligación de la GPL nace al distribuir el trabajo.

Qué sí toca, y es lo que hay que decir: **quien empaquete el aplicativo con el
modelo dentro** —una imagen de contenedor, un binario— sí distribuye un trabajo
combinado y hereda esa obligación.

### La frase que el README tiene que llevar

El README lo construye **U22** (`unit-of-work.md`). Esta frase entra tal cual, en
el idioma del README:

> El detector de datos personales usa el modelo `es_core_news_md` de spaCy para
> español, que es GPL-3.0 por su corpus de entrenamiento. El modelo no está en
> este repositorio: se descarga al instalar. Si empaquetas este aplicativo con el
> modelo dentro —una imagen o un binario—, estás distribuyendo un trabajo
> combinado y esa licencia te aplica.

> The PII detector uses spaCy's `es_core_news_md` model for Spanish, which is
> GPL-3.0 because of its training corpus. The model is not in this repository: it
> is downloaded at install time. If you package this application with the model
> inside — an image or a binary — you are distributing a combined work and that
> licence applies to you.

La alternativa que se descartó: cambiar a un modelo de español permisivo. Los
corpus de dependencias del español en Universal Dependencies arrastran la misma
licencia, y el detector es uno de los cinco módulos críticos con compuerta dura,
así que cambiarlo obliga a volver a medir la redacción por idioma y por tipo de
entidad. Costo alto, beneficio nulo mientras no exista una imagen.
