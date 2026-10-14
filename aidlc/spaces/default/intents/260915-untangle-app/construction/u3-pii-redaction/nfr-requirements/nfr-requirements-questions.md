# Preguntas — Requisitos de calidad de U3 `pii-redaction`

Tres cifras que los documentos aprobados dejaban abiertas y que esta etapa tiene
que fijar con su comando de medición.

## Q1 — Qué tamaño de modelo de spaCy

ADR-013 fijó "modelos de spaCy en español e inglés" sin elegir tamaño, y anotó
entre sus consecuencias negativas que "pesan en el despliegue". Esa consecuencia
era la decisión que faltaba.

- A. Pequeño en los dos idiomas
- B. Mediano en los dos idiomas
- C. Grande en los dos idiomas

[Answer]: B

**Miguel delegó pidiendo que se estudiara el caso primero**, y el estudio cambió
la recomendación que yo mismo había puesto en la pregunta, que era la A.

Las cifras salen de los metadatos que publica el propio proyecto spaCy para la
versión 3.8.0, que es la misma fuente del paquete que se instala:

| Modelo | Tamaño | Acierto en entidades |
| --- | --- | --- |
| `es_core_news_sm` | 12 MB | 88,97 % |
| `es_core_news_md` | 40 MB | 89,29 % |
| `es_core_news_lg` | 541 MB | 89,70 % |
| `en_core_web_sm` | 12 MB | 84,33 % |
| `en_core_web_md` | 31 MB | 84,73 % |
| `en_core_web_lg` | 382 MB | 85,54 % |

Presidio documenta `en_core_web_lg` como su modelo por defecto, pero sin dar
ninguna razón de acierto frente a tamaño. Medido: los dos modelos grandes pesan
**923 MB** juntos frente a los 24 MB de los dos pequeños, es decir **899 MB más**,
y eso compra **0,73 puntos en español y 1,21 en inglés**, sobre un despliegue que
se duerme y reinicia cada noche.

Y el pequeño se descarta por algo que la tabla no muestra: **los modelos `sm` de
spaCy no traen vectores de palabra y los `md` sí**. Los bancos de prueba se
miden con nombres frecuentes; el chat público recibe nombres que el modelo no
vio nunca, y ahí es donde los vectores cambian el resultado.

Acota el riesgo de haberse equivocado: los cuatro tipos que esta unidad existe
para tapar los encuentran reconocedores propios por formato, que no usan el
modelo. El modelo solo aporta nombres, lugares y organizaciones.

## Q2 — Techo para lo que tapa la regla de respaldo

- A. Techo medido que abre trabajo
- B. Se mide y se publica, sin techo

[Answer]: A

Delegada por Miguel junto con la anterior. Rige **1 de cada 10 o menos**, por
idioma, y **no detiene la entrega**: tapar de más es el lado seguro del error.
Pero pasarse significa una de dos cosas, las dos accionables —un reconocedor se
rompió, o hay un formato frecuente sin reconocedor propio— y por eso abre
trabajo en lugar de quedarse en una cifra que nadie mira.

## Q3 — Presupuesto para el retraso de la transcripción en vivo

- A. Tope declarado y medido
- B. Sin tope, solo se mide

[Answer]: A

Decisión de Miguel, que además pidió investigar cuál es el mejor tope. **El
estudio cambió el objetivo, no solo el número.**

La primera versión fijaba 300 ms de "retraso añadido", tomados prestados de la
parada ante interrupción (NFR2). Era **inalcanzable por construcción**, que es
el mismo error que la revisión del diseño funcional encontró en otra regla:
debajo de ese único número conviven dos retrasos de naturaleza distinta.

1. **Lo que cuesta nuestro código**, la pasada de redacción sobre el fragmento
   acumulado. Eso lo controlamos.
2. **Lo que el fragmento tarda en poder mostrarse**, que lo fija quien está
   dictando. Un teléfono de diez dígitos recitado despacio mantiene el texto
   oculto varios segundos, y eso no es un incumplimiento: es exactamente lo que
   BR3.5 exige. Un tope de 300 ms sobre esto solo se cumpliría enseñando
   dígitos.

Los umbrales salen de los tres límites de respuesta de Nielsen, que es la
referencia estándar y no un número a ojo: 0,1 s para sentirse instantáneo, 1 s
para no interrumpir el hilo de pensamiento, 10 s para el límite de la atención.

| Objetivo | Umbral |
| --- | --- |
| NFR11.3 — coste de la pasada de redacción sobre un parcial | 100 ms o menos |
| NFR11.4 — ocultar un fragmento sin avisar de que viene texto | 1 s o menos |

Lo que **no** se acota es cuánto puede estar oculto un fragmento, porque su
duración pertenece a quien habla. Lo que se acota es que nadie se quede mirando
una pantalla quieta sin saber por qué.
