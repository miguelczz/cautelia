# Decisiones de herramienta — U3 `pii-redaction`

Lo que esta unidad añade al stack, y lo que no. El ADR-013 ya fijó **Presidio con
modelos de spaCy en español e inglés, reconocedores propios por formato, sin red
y sin modelo de lenguaje**. Aquí solo se resuelve lo que dejó abierto: qué
tamaño de modelo.

## El tamaño del modelo de spaCy

ADR-013 dice "modelos de spaCy en español e inglés" sin elegir tamaño, y anota
entre sus consecuencias negativas que "los modelos de spaCy pesan en el
despliegue". Esa consecuencia es la decisión que faltaba.

**Cifras medidas, no estimadas.** Salen de los metadatos que publica el propio
proyecto spaCy para la versión 3.8.0
(`explosion/spacy-models`, archivo `meta/<modelo>-3.8.0.json`), que es la misma
fuente de la que sale el paquete que se instala.

| Modelo | Tamaño en disco | Acierto en entidades (`ents_f`) |
| --- | --- | --- |
| `es_core_news_sm` | 12 MB | 88,97 % |
| `es_core_news_md` | 40 MB | 89,29 % |
| `es_core_news_lg` | 541 MB | 89,70 % |
| `en_core_web_sm` | 12 MB | 84,33 % |
| `en_core_web_md` | 31 MB | 84,73 % |
| `en_core_web_lg` | 382 MB | 85,54 % |

**Decisión: `es_core_news_md` y `en_core_web_md`.** 71 MB entre los dos.

### Por qué no el grande, que es lo que Presidio documenta

La documentación de Presidio dice que viene "con un modelo de código abierto (el
modelo `en_core_web_lg` de spaCy)" y lo usa en todos sus ejemplos. Apartarse de
lo que documenta el proyecto oficial necesita una razón medida, y aquí la hay:

- Los dos modelos grandes pesan **923 MB** juntos (541 y 382), frente a los
  24 MB de los dos pequeños: el incremento es de **899 MB**, y compra **0,73
  puntos en español y 1,21 en inglés**. Es el peor cambio por megabyte de los
  tres saltos.
- El despliegue gratuito **se duerme y reinicia cada noche**. Casi un gigabyte de modelos
  dominaría la imagen y el arranque en frío, y el arranque en frío ya es la
  cifra que NFR21 publica.
- La propia documentación de Presidio **no da ninguna razón** de acierto frente a
  tamaño para su elección. No es una recomendación argumentada que estemos
  contradiciendo: es su ejemplo por defecto.

### Por qué no el pequeño, que es lo barato

**Confirmado midiendo el 2026-09-20**, después de que la memoria real obligara a
reabrir la decisión. Se bajó a `sm`, se corrió, y se volvió a subir:

| Modelos | Nombres atrapados | Falsos positivos sobre prosa corriente |
| --- | --- | --- |
| `md` | 14 de 14 | **0** |
| `sm` | 13 de 14 | **3** |

Los tres que inventa el pequeño son `salia` y `Iba` marcados como lugar y
`Quiero` como persona, sobre diez frases de conversación normal. En una
transcripción de la demostración eso es texto salpicado de etiquetas donde no
hay ningún dato, que es justo lo que la norma de legibilidad prohíbe.

La razón de fondo por la que falla: **los modelos `sm` de spaCy no traen vectores de palabra** y los `md` sí.
La tabla de arriba no lo refleja —los bancos de prueba se miden con nombres
frecuentes— pero el chat público recibe nombres que el modelo no vio nunca, y es
ahí donde los vectores cambian el resultado. Por 47 MB adicionales, es el lado
correcto donde equivocarse.

### Qué **no** depende de esta elección

Conviene decirlo, porque acota el riesgo de haber elegido mal: **los cuatro
tipos que esta unidad existe para tapar —placa, cédula, teléfono y número de
póliza— no los encuentra el modelo.** Los encuentran reconocedores propios por
formato, que no usan spaCy. El modelo aporta nombres de persona, lugares y
organizaciones. Un modelo peor degrada esa parte; no abre un agujero en los
cuatro tipos del dominio ni en la compuerta dura de NFR11.

## Dependencias nuevas

| Qué | Por qué, y por qué no la biblioteca estándar | Licencia |
| --- | --- | --- |
| `presidio-analyzer` | El motor de reconocedores y la resolución de solapes. Escribirlo a mano sería rehacer un componente de seguridad probado | MIT |
| `presidio-anonymizer` | La sustitución por etiqueta, con los desplazamientos ya resueltos. Sustituir a mano sobre índices es donde se cuelan los errores de un carácter | MIT |
| `es_core_news_md` | Modelo de spaCy para español, nombres y lugares | MIT |
| `en_core_web_md` | Modelo de spaCy para inglés | MIT |

Las licencias se registran con su atribución, como toda dependencia, porque el
repositorio es candidato a publicarse (D-017).

## Lo que esta unidad no añade al stack

- **Ningún cliente de red y ningún modelo de lenguaje** (ADR-013). Es lo que hace
  que la redacción sea determinista y que no envíe datos personales a un
  tercero.
- **Nada del segundo detector**: vive en U21, con mecanismo distinto, y esta
  unidad no lo importa (BR4.6).
