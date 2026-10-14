# Requisitos de calidad — U3 `pii-redaction`

Los objetivos medibles de la unidad y los controles que los sostienen. Esta es la
unidad cuyo fallo no se ve: una redacción rota no rompe ninguna pantalla, no
levanta ningún error y no aparece en ninguna prueba de funcionamiento. Se nota
cuando alguien lee una traza, que es tarde.

**Fuentes consumidas.** `../functional-design/functional-spec.md` y
`../functional-design/rules.md` (las 28 reglas),
`../../../inception/requirements-analysis/requirements.md` (FR7.3, FR12.3,
NFR11), `../../../inception/contract-design/contract-summary.md` (C-13),
`../../../../codekb/untangle/technology-stack.md`, y las respuestas de
`nfr-requirements-questions.md`.

## Qué puede salir mal

| Categoría | Cómo se materializa aquí | Controles |
| --- | --- | --- |
| Divulgación de información | Un dato personal llega a una traza, un log, una exportación o el reporte porque alguien escribió hacia afuera sin pasar por la redacción, porque se trató un dato ficticio como si no hiciera falta taparlo, o porque el reporte imprimió el valor al describir una diferencia | SEC-U3.1, SEC-U3.2, SEC-U3.3, SEC-U3.13, SEC-U3.14 |
| Manipulación | El texto se construye para evadir al detector: se dicta el dato en el otro idioma, se separa con espacios o se usa un formato que nadie previó | SEC-U3.4, SEC-U3.5, SEC-U3.6 |
| Divulgación por el propio control | El detector guarda lo que detecta, o existe una vía para deshacer el tapado, y se convierte en el único sitio con todos los datos personales juntos | SEC-U3.7, SEC-U3.8 |
| Repudio | Un dato se escapa y no hay forma de saber qué reconocedor falló ni en qué idioma | SEC-U3.9 |
| Denegación de servicio | El detector no carga, o tarda tanto que el turno se queda sin presupuesto | SEC-U3.10, SEC-U3.11 |
| Divulgación hacia un tercero | El texto con datos personales viaja a un proveedor para ser analizado | SEC-U3.12 |
| Fallo común de los dos detectores | Los dos detectores comparten mecanismo o biblioteca, así que un mismo error los tumba a la vez y el segundo deja de ser una comprobación independiente del primero | SEC-U3.15 |

## Objetivos medibles

Cada uno con su identificador estable, su valor esperado y **el comando que
produce su valor real**, para que aparezca como fila propia en la matriz de
verificación de `build-and-test`.

**Cuatro de esos comandos todavía no existen**: `test:u3`, `models:install`,
`redaction:constructor` y `redaction:report` los crea la generación de código de
esta unidad, y su reparto en el archivo de tareas está en
`../infrastructure-design/cicd-pipeline.md`. Se nombran aquí porque un objetivo
sin el comando que lo mide es una intención, pero conviene saber que hoy no se
pueden correr.

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| NFR11 | Datos personales en trazas, logs y exportaciones, hallados por el segundo detector | **Exactamente 0**, en cada idioma. Compuerta dura: un solo hallazgo detiene la entrega | `mise run evals:run -- --subset rt14` (el segundo detector es de U21) |
| NFR11.1 | Detección sobre los casos sembrados de RT-14 y RT-15, **por idioma y por tipo de entidad** | **100 %** en los cuatro tipos propios del dominio; nunca un promedio combinado | `mise run test:u3` |
| NFR11.2 | Proporción de datos tapados por la regla de respaldo frente al total de tapados | **1 de cada 10 o menos**, por idioma. No detiene la entrega; abre trabajo | `mise run redaction:report` |
| NFR11.3 | Coste de la pasada de redacción sobre un fragmento parcial | **100 ms o menos** por fragmento | `mise run test:u3`, cronometrando la llamada real al detector con el **reloj del sistema** |
| NFR11.4 | Tiempo que la consola puede dejar un fragmento oculto **sin avisar** de que viene texto | **1 s o menos**; pasado ese punto muestra su indicador | `mise run test:u3` con el **reloj controlado**, que es lógica de temporización y no coste |
| NFR21.1 | Que el camino del clon al reporte siga sin necesitar esta unidad cargada | Sin cambio respecto a la cifra vigente | `mise run lint` (contrato de importación) |

**NFR11.1 pide el 100 % y eso es deliberado.** No es una meta de detección en
texto libre, que sería irreal: se mide sobre **casos sembrados**, con formatos
conocidos, escritos a propósito para ejercitar cada tipo en cada idioma. Un
reconocedor que falle en su propio caso sembrado está roto, no imperfecto. La
detección sobre texto real no tiene meta aquí: la cubre NFR11, que mide lo que
se escapa y no lo que se atrapa.

**NFR11.2 no bloquea, y esa es la decisión.** Tapar de más es el lado seguro del
error. Pero un respaldo que dispara mucho significa una de dos cosas, las dos
accionables: un reconocedor se rompió, o hay un formato frecuente sin
reconocedor propio. Por eso se mide y abre trabajo en lugar de detener la
entrega.

## Controles

| ID | Control | Cómo se comprueba que existe |
| --- | --- | --- |
| SEC-U3.1 | Un solo punto de salida hacia las seis superficies, y solo acepta contenido ya redactado | `mise run lint`: el contrato de importación falla ante un escritor plantado fuera del registro |
| SEC-U3.2 | El constructor del tipo redactado solo se invoca dentro de su módulo | `mise run redaction:constructor`: análisis estático que falla ante esa llamada plantada en cualquier otro archivo |
| SEC-U3.3 | La redacción ocurre antes de persistir, no solo antes de exportar | `mise run test:u3`: se siembra un turno con los cuatro tipos y se lee lo guardado |
| SEC-U3.4 | Los reconocedores de los dos idiomas corren en cada llamada | `mise run test:u3`: el caso de RT-15, dato dictado en un idioma dentro de un turno del otro |
| SEC-U3.5 | Se detectan las formas dictada, con espacios y con guiones | `mise run test:u3`: las tres formas del mismo dato |
| SEC-U3.6 | Regla de respaldo por contexto para lo que ningún reconocedor reclama | `mise run test:u3`: un formato inventado junto a una frase de contexto declarada |
| SEC-U3.7 | El detector no guarda nada: ni el texto, ni los hallazgos, ni su valor | `mise run redaction:constructor`: el mismo análisis falla ante cualquier estructura que relacione un hallazgo con su valor |
| SEC-U3.8 | El tapado es irreversible; no hay bóveda ni correspondencia | El mismo análisis estático, más la ausencia de numeración entre turnos |
| SEC-U3.9 | Cada hallazgo declara qué reconocedor lo encontró, y el informe cuenta por reconocedor | `mise run redaction:report` |
| SEC-U3.10 | Si el detector no carga, no sale texto: sale la frase de degradación | `mise run test:u3`: se rompe la carga a propósito y se exige silencio |
| SEC-U3.11 | El coste de la redacción sobre un parcial está acotado, y la consola avisa en vez de quedarse congelada | Dos métodos distintos, y la distinción importa: el coste se cronometra con el **reloj del sistema** alrededor de la llamada real; el aviso se prueba con el **reloj controlado** |
| SEC-U3.12 | Sin red y sin modelo de lenguaje: el texto no sale del proceso | `mise run lint`: contrato de importación que prohíbe cualquier SDK de proveedor dentro de este módulo |
| SEC-U3.13 | Los datos ficticios se tapan igual que los reales | `mise run test:u3` sobre las trazas exportadas de una corrida de DS-2 |
| SEC-U3.14 | El reporte describe la diferencia sin imprimir el valor | `mise run test:u3`: un caso que falla en un campo con dato personal |
| SEC-U3.15 | Esta unidad no comparte mecanismo ni biblioteca con el segundo detector | `mise run lint`: contrato de importación; y cada reconocedor declara su mecanismo, que U21 lee como archivo |

**Dos comandos nuevos entran en el guion de verificación**, en su paso 6, junto
a los siete que ya están: `redaction:constructor` y `redaction:report`. El guion
sigue teniendo nueve pasos.

**`test:u3` no entra**, y eso sigue el precedente de `test:u1` y `test:u2`: son
comandos de uso local acotados a su unidad, y la compuerta ya ejecuta esas
mismas pruebas en el paso 5, donde `mise run cov` corre la suite completa con su
cobertura. Meterlo también en el paso 6 las correría dos veces en la misma
corrida. Por eso los objetivos de arriba citan `mise run test:u3` como el
comando que produce su valor: es el que se corre a mano para ver esa cifra, no
un paso añadido a la compuerta.

## Decisiones de esta etapa

| # | Decisión | Por qué | Quién |
| --- | --- | --- | --- |
| NFR-U3-1 | Modelos `md` de spaCy en los dos idiomas, no `sm` ni `lg` | Medido: de pequeño a grande cuesta 923 MB y compra menos de 1,3 puntos. Los `sm` no traen vectores de palabra y el chat público trae nombres que el modelo no vio. Ver `tech-stack-decisions.md` | Claude, con la investigación que pidió Miguel |
| NFR-U3-2 | NFR11.1 exige 100 %, medido solo sobre casos sembrados | Un reconocedor que falla en su propio caso sembrado está roto. La detección en texto libre la mide NFR11, que cuenta lo que se escapa | Claude |
| NFR-U3-3 | NFR11.2 tiene techo (1 de cada 10) pero no detiene la entrega | Tapar de más es el lado seguro; pero pasarse señala un reconocedor roto o un formato frecuente sin reconocedor, y las dos cosas son trabajo concreto | Miguel (delegada), aplicada por Claude |
| NFR-U3-4 | El retraso se parte en dos objetivos: 100 ms de coste propio y 1 s antes de avisar | Ver abajo. La versión anterior de esta decisión fijaba 300 ms de "retraso añadido", tomados de la parada ante interrupción, y era un objetivo inalcanzable por construcción | Miguel pidió el tope; el reparto lo fijó Claude tras investigarlo |
| NFR-U3-5 | El informe cuenta por reconocedor, no solo por tipo | Sin esa columna, un reconocedor roto se esconde detrás del respaldo, que tapa el mismo dato y suma al mismo tipo | Claude |

## Por qué el retraso son dos objetivos y no uno

Miguel pidió un tope declarado y medido para el retraso de la transcripción en
vivo, y la primera versión de este documento fijó 300 ms, tomados prestados de
la parada ante interrupción (NFR2). Al estudiarlo, ese objetivo era **imposible
de cumplir por construcción**, que es el mismo error que la revisión del diseño
funcional encontró en otra regla.

La razón: bajo ese único número conviven dos retrasos que no tienen la misma
naturaleza.

1. **Lo que cuesta nuestro código.** La pasada de redacción sobre el fragmento
   acumulado. Eso lo controlamos nosotros y debe sentirse instantáneo, porque
   ocurre con cada fragmento mientras alguien habla.
2. **Lo que el fragmento tarda en poder mostrarse.** Eso **no lo controlamos**:
   lo fija la persona que está dictando. Quien recita un teléfono de diez
   dígitos despacio mantiene el texto oculto varios segundos, y eso no es un
   incumplimiento sino exactamente lo que BR3.5 exige. Un tope de 300 ms sobre
   esto solo se podría cumplir enseñando dígitos, que es lo que la regla
   prohíbe.

**Los umbrales salen de los tres límites de respuesta de Nielsen**, que es la
referencia estándar para esto y no un número elegido a ojo: 0,1 s es el límite
para que el sistema se sienta instantáneo; 1 s es el límite para que no se
interrumpa el hilo de pensamiento, y por debajo de él no hace falta avisar de
nada; 10 s es el límite de la atención.

| Objetivo | Umbral | De dónde sale |
| --- | --- | --- |
| NFR11.3 — coste de la pasada de redacción | 100 ms | El límite de lo instantáneo. Ocurre con cada fragmento, así que es donde ese límite aplica |
| NFR11.4 — ocultar sin avisar | 1 s | El límite del hilo de pensamiento. Por debajo no hace falta indicador; por encima, una pantalla congelada hace pensar que el sistema se cayó |

**Lo que NO se acota es cuánto puede estar oculto un fragmento**, porque su
duración pertenece a quien habla. Lo que se acota es que nadie se quede mirando
una pantalla quieta sin saber por qué.

## Un hueco que esta etapa deja señalado

**La redacción de datos personales es compuerta dura y no está en la lista de
módulos críticos del piso de cobertura.** `team.md` fija el 80 % por módulo para
"motor de reglas, verificador de citas, aislamiento por tenant y esquema del
caso". La redacción no aparece, pese a que su fallo es silencioso y su compuerta
es de las que detienen la entrega con un solo hallazgo.

No se añadió por iniciativa propia: cambiar la lista de módulos críticos es
cambiar una práctica afirmada del equipo. Se llevó a Miguel y **el 2026-09-20
decidió que la redacción entra a la lista**.

Aplicado en los cinco sitios donde esa lista vive: `team.md` (la práctica
afirmada), `project.md` (la regla `ALWAYS`), `requirements.md` (la definición de
NFR18), `unit-of-work.md` (las unidades dueñas de piso propio, que pasan de
cuatro a cinco) y el comentario de `coverage_gate.py`, que también decía cuatro.

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| NFR18.2 | Cobertura de líneas del módulo de redacción, ahora módulo crítico | **80 % o más** | `mise run cov` |

La entrada de configuración de la compuerta **no se añade todavía**: la
declaración lleva una ruta, y esa ruta no existe hasta que la generación de
código de esta unidad la cree. Entra en ese mismo paso, igual que `tenancy`
entró con U2.
