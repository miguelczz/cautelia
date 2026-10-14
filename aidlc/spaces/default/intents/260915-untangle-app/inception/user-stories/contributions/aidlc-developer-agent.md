**Collaborator:** aidlc-developer-agent

## Contribution

Revisión desde desarrollo de cinco aspectos: tamaño e implementabilidad de las 59 historias, dependencias entre ellas, decisiones de arquitectura que los criterios dan por tomadas, trazabilidad y riesgos técnicos. Va ordenada por impacto. La sección 1 reúne lo que cambia el modelo de datos o abre un hueco de seguridad; las secciones 2 a 6 se pueden integrar historia por historia, y la 7 trae los textos concretos para D8 a D11. Los identificadores nuevos (`US1.3a`, `AC1.12.5`, etc.) son provisionales: el líder los renumera como prefiera.

Comprobé con un script sobre `stories.md` y `requirements.md` que las 59 historias declaran 271 criterios y que los 84 FR aparecen en algún "Realiza". El único NFR sin historia es NFR18: el plan lo difiere, pero `stories.md` no deja escrito a dónde va (ver 5.2).

### 1. Hallazgos de mayor impacto

#### 1.1 La póliza de ejemplo compartida abre casos de otros visitantes

Afecta a AC1.11.2, AC1.12.2, AC1.13.1, AC1.18.2 y AC1.21.3.

En el enlace público, todos los visitantes usan la misma póliza de ejemplo por aseguradora (PRD 9.3 y F4.3; AC1.14.1 la muestra en pantalla). Las historias identifican la reanudación y el resumen de la decisión solo por esa póliza. Así, el visitante B que se identifica con la póliza de ejemplo recibiría la oferta de seguir el caso a medias del visitante A, con todo lo que A escribió, o el resumen de su decisión. En US1.13 el número de caso tampoco sirve de llave: prefijo más seis dígitos es enumerable, y la póliza que lo acompaña es pública. Es el escenario RT-4 (bloquea) alcanzado por el camino feliz. Además, lo que A escribió es dato potencialmente real según la regla de superficie pública de `project.md`.

Propuesta. Añadir a US1.12, con su espejo en US1.18 y US1.21:

- **AC1.12.5 — La póliza de ejemplo no abre casos ajenos**
  - Dado que otro visitante dejó a medias un caso con la póliza de ejemplo de Stonecroft Mutual
  - Cuando abro el chat desde otro navegador y me identifico con esa misma póliza
  - Entonces la agente no me ofrece ese caso ni revela nada de él, y abre uno nuevo
  - Y con la póliza de ejemplo, la reanudación y el resumen de la decisión solo ocurren en la misma sesión firmada del navegador que creó el caso

En AC1.13.1, sustituir la llave por esta: "escribo el número de caso desde la sesión que lo creó, o abro el enlace firmado del caso (US3.7), y me identifico con su póliza". La identidad por póliza basta para las pólizas sembradas que no son de ejemplo (golden sets y fixtures).

#### 1.2 Falta decidir dónde vive cada dato personal

Afecta a AC4.9.1, AC3.3.2, AC1.11.3, AC5.9.3 y a FR2.4 en todas las historias de reanudación.

Hoy los criterios dicen dos cosas que no caben juntas:

- AC4.9.1: la transcripción, la traza y el log guardan los valores ya redactados antes de persistir.
- AC3.3.2: la transcripción "sigue mostrando lo que se dijo originalmente". Además, AC3.3.1 y la extracción por campo (NFR8) necesitan la placa y la cédula reales en el caso, y el PRD (MOD-01) guarda esos datos cifrados y bajo RLS.

Hay además un tercer almacén que ninguna historia nombra: el punto de control por turno (FR2.4). Guarda el estado tipado de la conversación con los turnos del asegurado sin redactar, porque la extracción los necesita en crudo. Mientras no se decida su clase de dato, el punto de control incumple "redactar antes de persistir". Y sobrevive al reinicio nocturno, porque NFR19 solo habla de casos y transcripciones.

Propuesta: declarar una vez en las Convenciones las tres clases de almacén y ajustar los criterios a ellas.

| Almacén | Datos personales | Protección | Reinicio nocturno |
| --- | --- | --- | --- |
| Campos estructurados del caso | En claro | Cifrado en reposo y RLS por aseguradora | Se borran los de visitantes |
| Punto de control del grafo | En claro, mientras la conversación está viva | La misma del caso, por el mismo punto único de sesión | Se borran los de visitantes |
| Transcripción, traza, log, exportación y reporte de evaluación | Redactados antes de escribirse | Punto único de salida | Se borran los de visitantes, también en el backend de trazas |

Textos:

- AC4.9.1: "Entonces esos valores quedan en claro solo en los campos del caso y en el punto de control, cifrados y bajo RLS; en la transcripción, la traza y el log ya están redactados antes de persistir".
- AC3.3.2: "Entonces sigue mostrando lo que se dijo, con los datos personales redactados; el valor completo está en el campo del caso".
- AC1.11.3: añadir "Y los datos personales que escribí aparecen redactados en la conversación restaurada".
- AC5.9.3: añadir "Y tampoco existen sus puntos de control ni sus trazas en el backend de trazas".

Para la voz, las transcripciones parciales no se persisten: solo se guarda la final, redactada fuera del camino del turno (ver 6.3).

#### 1.3 El modelo de estado del caso tiene cuatro contradicciones y un camino sin historia

Esto hay que resolverlo antes de Units Generation, porque define el esquema de MOD-01 y la función de transición de MOD-02.

1. **Derivado pero incompleto.** AC1.6.1 y AC1.6.4 mandan a la bandeja una solicitud de persona con 3 de 7 campos, pero AC3.5.3 prohíbe aprobar o rechazar un caso incompleto. Lo mismo pasa con AC1.2.4 (tercero que reporta), AC1.8.5 (historia cambiada) y AC2.3.1 (fallo de verificación): con AC3.5.3 tal como está, esos casos quedan atascados.
   - Reemplazar AC3.5.3 por: "Dado un caso en 'esperando al asegurado' (incompleto y sin derivación), Cuando lo abro, Entonces no puedo aprobarlo ni rechazarlo".
   - Añadir **AC3.5.5 — Derivado con datos incompletos**: "Dado un caso derivado por solicitud de persona con completitud 3/7, Cuando lo abro, Entonces puedo decidirlo con comentario, la completitud se muestra tal cual y la revisión de cierre corrió sobre la conversación hasta la derivación".
2. **Aprobar cierra el caso o lo deja abierto.** FR8.4 y FR2.5 dicen que aprobar cierra el caso; AC3.4.2 dice que "queda abierto en gestión", y "abierto" es también el estado inicial de FR1.4. Propuesta para AC3.4.2: "Entonces el grafo se reanuda y el caso pasa a cerrado con resolución aprobado, que la bandeja y el asegurado ven como 'siniestro abierto, en gestión'". AC3.4.3 ("vuelve con su motivo") no nombra un estado destino; propuesta: "pasa a cerrado con resolución rechazado y el asegurado recibe el comentario".
3. **"Enviado a la aseguradora"** (AC3.6.3 y AC3.6.5) no existe en FR1.4, y FR1.4 rechaza toda transición no declarada. Propuesta: cerrado con resolución "enviado a la aseguradora".
4. **"Cierre directo" no tiene historia.** FR6.2 define tres categorías y solo la derivación está escrita. No se sabe qué dice la agente, si el caso llega a la bandeja ni qué ve el visitante de US3.7, que solo recibe el enlace si su caso "queda derivado". Sunmeadow es la aseguradora de "cierre directo frecuente" (PRD 9.1), así que un visitante en inglés puede no llegar nunca a cerrar el ciclo. Propongo una historia Must nueva:
   - **US1.10d — Cerrar sin ajustador un siniestro que las reglas permiten cerrar** (FR6.2, FR1.4; MOD-06, MOD-01, MOD-07).
   - Criterios: la categoría cierre directo deja el caso cerrado con resolución "registrado" y con la revisión de los cuatro controles adjunta; la agente dice que quedó registrado, sin afirmar cobertura ni montos; el caso aparece como cerrado en la bandeja.
   - Decisión de Miguel: qué ve el visitante de US3.7 cuando su caso cae en cierre directo. Las opciones son un enlace de solo lectura o una política de demo que siempre deriva, escrita en la configuración.
5. **Qué registra una conversación de solo cobertura.** Según FR4.2, "ambos flujos producen registro", y AC2.2.1 ofrece derivar una pregunta sin cláusula. Pero un registro sin los siete campos queda en 0/7, "incompleto" y no decidible. Propuesta de Convención: el registro lleva un tipo (siniestro, consulta de cobertura y, con S1, solicitud de cotización), la completitud se calcula según el tipo y una consulta de cobertura derivada es decidible.

Resolución propuesta: el caso termina en un único estado cerrado con una resolución de conjunto cerrado (registrado, aprobado, rechazado, enviado a la aseguradora). La etiqueta que ve una persona sale del catálogo, como pide la convención 4.

#### 1.4 El corte de 3 minutos y la llamada única por visitante impiden completar y retomar por voz

Afecta a US5.6 (AC5.6.1, AC5.6.2), a US1.18 y US1.21 (retomar al volver a llamar), a US3.7 (AC3.7.1) y a D8.

- El PRD estima que un primer aviso simple por voz toma hasta 14 turnos y 5 minutos (10.3, contramétrica "Turnos por caso completo"). El enlace público corta a los 3 (FR3.9). Súmese la apertura de unas 50 palabras, la póliza y la placa dictadas dígito a dígito y la confirmación de cada bloque, todo a 140–155 palabras por minuto: una parte relevante de los reportes de visitantes se cortará incompleta.
- Un caso cortado queda en "esperando al asegurado": no es decidible (AC3.5.3), así que no hay enlace firmado útil. Y el visitante no puede volver a llamar para retomarlo, porque ya usó su llamada del día (AC5.6.2); al día siguiente el reinicio nocturno ya borró el caso. En el enlace público, FR3.6 (M16) y el cierre del ciclo de US3.7 quedan inalcanzables por voz justo en el caso más probable.

Es una contradicción entre documentos aprobados, y la regla de fase prohíbe arrastrarla: la respuesta Q1 de Requirements Analysis supone que 3 minutos alcanzan para el camino completo, y el PRD 10.3 permite 5. Opciones para que Miguel decida en la compuerta (recomiendo A):

- `A.` Una reconexión al mismo caso dentro de 15 minutos, tanto si el corte fue por la red como por el límite de duración. No cuenta como llamada nueva del visitante, pero sí contra el tope diario del sitio y contra el techo. Criterio: "Dado que mi llamada se cortó a los tres minutos con cuatro bloques confirmados, Cuando vuelvo a llamar desde la misma sesión antes de 15 minutos, Entonces la llamada se acepta, retoma desde el último bloque confirmado y cuenta contra el tope diario del sitio".
- `B.` Subir la duración a 5 minutos y bajar el tope diario a 9 llamadas: conserva el mismo máximo diario de minutos (45). Son valores de configuración.
- `C.` Aceptar que en el enlace público no existe la reanudación por voz y declararlo en "Lo que no hace", con una frase de cierre por límite que no prometa retomar.

Cualquiera sea la opción, conviene medir sobre DS-5, antes de publicar el enlace de voz, qué fracción de los guiones de primer aviso simple termina en 3 minutos. Es una cifra barata y permite elegir entre A, B y C con datos.

#### 1.5 Los controles que corren en el turno contradicen la regla afirmada

Afecta a US1.5, US1.6, US1.8 y a la convención 5(d).

`project.md` dice "NEVER hacer trabajo de verificación, de reglas o de cumplimiento dentro del turno de voz", y la convención 5(d) lo vuelve comprobable por herramienta: "el manejador de turno de voz no invoca sincrónicamente verificación, reglas ni cumplimiento". Pero tres criterios Must exigen controles de cumplimiento dentro del turno:

- la guardia de salida antes de emitir (F7.5, AC1.8.4);
- la ruta a persona en el turno siguiente (F7.2, uno de los cuatro controles de MOD-07, AC1.6.1);
- la indicación de emergencia antes de cualquier dato (AC1.5.2).

El PRD (MOD-07) ya distingue "la guardia por turno, barata" de "la revisión completa al cierre", pero ni la regla afirmada ni su chequeo de importaciones recogen esa distinción. Si Construcción implementa el chequeo literal de 5(d), la guardia queda prohibida; si no lo implementa, la convención deja de ser comprobable.

Propuesta para las Convenciones de las historias, para que Units Generation la herede al diseñar el chequeo: "En el turno corren solo tres controles baratos, con presupuesto de latencia declarado: la guardia de salida, la detección de petición de persona y la detección de emergencia. La verificación de póliza, las reglas y la revisión completa de cumplimiento corren de fondo". La corrección del texto de la regla afirmada se propone por el ritual de aprendizajes, no editando la memoria.

#### 1.6 El costo por minuto de D7 no se puede cumplir a precio de lista

Afecta a AC5.8.4 y a D7.

El PRD 10.5 define el costo "a precio de lista (tokens, STT, TTS)". Sin embargo, los 0,02 USD por llamada de cuatro minutos vienen de D-015, que solo cuenta el modelo ("alrededor de 1 centavo con 2.5 Flash-Lite"). La adenda v1.1 dice que el renglón caro es la voz paisa, y la Q8 de Requirements Analysis calcula 0,005 USD de modelo por llamada de tres minutos, no por minuto. Según las tarifas públicas que conozco (a verificar en el spike de la semana 1), la transcripción en streaming a precio de lista cuesta por sí sola del orden de 0,006 a 0,009 USD por minuto, y la síntesis de pago, varias veces eso. AC5.8.4 fallaría por construcción, aunque el gasto en efectivo sea casi cero gracias al crédito y al tier gratuito.

Propuesta para AC5.8.4: "Entonces el costo del modelo por minuto de llamada es 0,005 USD o menos; el costo de transcripción y de síntesis por minuto se publica aparte, a precio de lista y en efectivo pagado, sin meta hasta que el spike fije una". Y anotar para `nfr-requirements` que NFR14 se registra con esos componentes separados.

#### 1.7 Metas agregadas dentro de historias de uno a tres días

Afecta a dos grupos de criterios:

- **Umbrales agregados:** AC1.3.6, AC1.6.3, AC1.9.2, AC1.10.6, AC1.15.4, AC1.15.5, AC1.16.4, AC1.17.5, AC1.19.3, AC1.20.5, AC1.21.4, AC1.22.4, AC1.23.3, la precisión de AC2.1.4, AC2.2.3 y AC6.1.5.
- **Compuertas duras sobre conjuntos completos:** AC1.5.3, AC1.8.6, las citas inexistentes de AC2.1.4 y AC4.10.4.

Estos criterios exigen un umbral sobre un conjunto entero: 95 % sobre las 60 conversaciones de DS-2, p95 sobre las 20 grabaciones de DS-5, 90 % de rúbrica con juez. Ninguna historia de uno a tres días controla lo que esos umbrales necesitan:

- DS-2 completo llega en la semana 5 (la v0, con 20 casos, en la 3);
- DS-5 depende de voluntarios con fecha (PRD 13.4);
- los criterios con juez valen "no medida" hasta calibrarlo contra DS-7 (práctica afirmada);
- el umbral agregado depende de todo el camino (Intake, guardia, reglas), no de la historia.

Así, una historia no puede cerrarse cuando termina su componente, que es justo lo que pide el recorrido por componente. La postura de pruebas afirmada ya da la salida: en la rama evaluada, la unidad escribe primero "su caso de golden set" y lo hace pasar.

Propuesta de Convención, sin tocar ningún umbral: "Cada historia de la rama evaluada nombra los casos de golden set que crea o extiende, por eje de la matriz y con identificador estable, y se acepta cuando esos casos pasan en los dos idiomas. Los umbrales agregados (completitud, extracción, citación, latencias, rúbrica) son metas medibles que `nfr-requirements` registra y `build-and-test` verifica por hito. En la historia se escriben como criterio 'Meta del hito', que no impide cerrarla". Los criterios que dependen del juez (AC1.9.2, el soporte de AC2.1.2 y de AC2.1.4, y la parte "todos usan usted" de AC1.19.3) llevan además la marca "juez", para que el reporte los muestre como "no medida" hasta la calibración.

Las compuertas duras no cambian: son pasa o falla por caso, la historia exige que sus casos pasen y la compuerta de CI las sostiene sobre el conjunto completo en cada corrida.

### 2. Historias que no caben en uno a tres días o mezclan componentes

El criterio es el recorrido por componente de `team.md`. Una historia que mezcla un componente de la base con otro que se construye semanas después (por ejemplo, el verificador de citas de MOD-05 con la interfaz del chat de MOD-04) no se puede aceptar hasta que exista el último. En la práctica dura semanas, aunque cada criterio sea pequeño. Van de mayor a menor tamaño.

**US2.1 — Preguntar en el chat y ver la cláusula exacta.** Es la unidad "Policy RAG" completa del PRD 13: índice híbrido por aseguradora, recuperación filtrada, respuesta restringida, verificador exacto, verificación de soporte, interfaz de la cita, latencia del chat y cambio de flujo a mitad del reporte. Propongo dividirla en cuatro:
- `US2.1a` Recibir solo cláusulas de mi aseguradora y de mi póliza vigente (FR5.3; MOD-05): AC2.1.3, más AC4.8.4, que sale de US4.8.
- `US2.1b` Que ninguna cita llegue sin pasar por el verificador exacto (FR5.4, NFR6; MOD-05). Hoy AC2.1.2 mezcla una compuerta juzgada por código con una métrica juzgada por el modelo, y la práctica afirmada solo hace bloqueante la primera. Se divide en:
  - `AC2.1.2a` (código, compuerta dura): "cada identificador citado fue recuperado para esa aseguradora y esa póliza, existe y está vigente";
  - `AC2.1.2b` (juez, meta de NFR5): "el texto de la cláusula sostiene la afirmación".
- `US2.1c` Ver la cita en el chat con su texto completo y su traza (FR4.3, FR5.6, NFR4; MOD-04, MOD-10): AC2.1.1 y AC2.1.5.
- `US2.1d` Preguntar por cobertura a mitad del reporte y volver donde iba (FR4.2; MOD-02): AC2.1.6. También la usan AC1.20.4 y el paso 7 del recorrido 7.1, así que conviene que viva en el grafo y no en el chat.
- AC2.1.4 queda como meta del hito (ver 1.7), y cada historia nombra sus casos de DS-3.

**US1.3 — Contar lo que pasó por chat.** Contiene el nodo Intake completo (extracción al estado tipado, orden fijo, dato adelantado) y además la completitud con confirmación por bloque. Dividir:
- `US1.3a` Responder una pregunta a la vez en el orden de la guía (MOD-02, MOD-01): AC1.3.1, AC1.3.2 y AC1.3.3.
- `US1.3b` Ver confirmado lo anotado y saber cuánto falta (MOD-01, rama determinista): AC1.3.4 y AC1.3.5. Aquí cabe una meta del PRD que no tiene ninguna historia, **AC1.3.7 — Lectura de confirmación fiel**: "Dado los bloques confirmados del golden set de texto, Cuando se compara lo que la agente lee con lo que dijo el asegurado, Entonces coincide en el 98 % o más, en cada idioma" (PRD 10.4, meta del hito).
- AC1.3.6 pasa a meta del hito.

**US1.10 — Cerrar el reporte.** Mezcla el cierre conversacional, el motor de reglas completo, la revisión completa de cumplimiento y los adjuntos. El motor exige entre 10 y 20 reglas por aseguradora, cada una con su prueba, y hoy solo aparece como un recuento en AC5.3.1. Dividir:
- `US1.10a` Oír el resumen y mi número de caso sin plazos (FR1.5; MOD-01, MOD-02): AC1.10.1 y AC1.10.3.
- `US1.10b` Saber qué sigue según las reglas de mi aseguradora (FR6.1, FR6.2, FR6.3, NFR13; MOD-06): AC1.10.2, AC1.10.6, AC5.3.1 (sale de US5.3) y AC4.7.4 (sale de US4.7). Es la historia que da dueño a escribir las reglas de las tres aseguradoras; si con sus pruebas pasa de tres días, se divide por aseguradora.
- `US1.10c` Que el caso no se cierre sin sus controles ni sus adjuntos (FR7.7, FR1.7, FR7.1; MOD-07, MOD-01): AC1.10.4 y AC1.10.5.
- `US1.10d` Cierre directo (ver 1.3).

**US5.2 — Regenerar los datos sintéticos.** Mezcla la herramienta, el contenido de tres corpus y los casos sembrados de los que dependen unas veinte historias. Dividir:
- `US5.2a` Regenerar con una semilla y obtener los mismos bytes (FR11.2, FR12.1; MOD-12): AC5.2.1 y AC5.2.5, con la separación de 6.11.
- `US5.2b` Corpus de Stonecroft Mutual y `US5.2c` Corpus de Sunmeadow Auto con las copias etiquetadas de Knotwell (FR5.1, FR5.2; MOD-12, MOD-05): AC5.2.2 y AC5.2.3 para cada aseguradora. El PRD dedica la semana 2 a DS-1 como trabajo propio, no como un criterio.
- `US5.2d` Casos sembrados en cada estado (ver 3.1).
- AC5.2.4 (texto propio) pasa a los chequeos de contenido, con el mecanismo de 6.11.

**US1.14 — Llamar desde el navegador.** Carga la integración del framework de voz con el grafo, que es el riesgo R10 y tiene spike propio, más la consola y la apertura. Dividir:
- `US1.14a` Conectar una llamada desde la consola (FR3.1; MOD-03): AC1.14.1 y AC1.14.5.
- `US1.14b` Oír primero la divulgación y lo que la agente puede hacer (FR3.2, FR7.1; MOD-03, MOD-07): AC1.14.2 y AC1.14.3.
- AC1.14.4 (interrumpir la apertura) pasa a US1.16, que es donde existe la detección de interrupción.

**US4.9 — Ningún dato personal en trazas.** Dividir:
- `US4.9a` Redactar en el punto único de salida (FR7.3, FR12.3; MOD-07, MOD-10): AC4.9.1, con el texto de 1.2, y AC4.9.4.
- `US4.9b` Reconocer placa, cédula, teléfono y número de póliza en los dos idiomas (MOD-07): AC4.9.3 y AC4.9.5.
- `US4.9c` Segundo detector en la compuerta (NFR11; MOD-11): AC4.9.2.

**US1.8 — Sin promesas de cobertura.**
- `US1.8` se queda con la guardia de salida (MOD-07): AC1.8.1, AC1.8.2, AC1.8.4 y AC1.8.6.
- AC1.8.3 se funde con AC4.10.1, que es casi el mismo caso. Tal como está, exige responder con una cláusula verificada y arrastra MOD-05.
- AC1.8.5 pasa a una historia nueva, `US1.8b` Registrar dos versiones de la historia sin acusar (RT-7; MOD-01, MOD-06). Necesita que el esquema guarde dos valores para un mismo campo y una regla que derive cuando la fecha es anterior a la vigencia.

**US1.17 — Silencios.** FR2.3 (dos ritmos con precarga) es la pieza central de arquitectura de MOD-02 y está escondida en una historia de silencios en inglés. Dividir:
- `US1.17a` Que la conversación siga mientras se verifica mi póliza (FR2.3; MOD-02, MOD-03): AC1.17.1 y AC1.17.2. Hay que añadir un criterio de precarga, que no está en ninguna historia aunque es la mitigación de R2, **AC1.17.6 — Precarga al identificarme**: "Dado que me identifico con mi póliza, Cuando la agente confirma la identidad, Entonces la verificación de la póliza empieza de fondo antes de cualquier pregunta de cobertura, y la traza la muestra como tramo de fondo".
- `US1.17b` Que la agente note mis silencios (FR3.5; MOD-03): AC1.17.3, AC1.17.4 y AC1.17.5.

**US4.7 — El orquestador es código.** Junta tres piezas de base y una de voz. Dividir:
- `US4.7a` Cuatro nodos con contrato y transición pura (FR2.1, FR2.2; MOD-02): AC4.7.1 y AC4.7.2.
- `US4.7b` Ciclo de vida del caso (FR1.4; MOD-01): AC4.7.3, con los estados de 1.3.
- AC4.7.4 pasa a US1.10b; AC4.7.5 se reescribe para poder probarse antes de que exista la voz (ver 3.2).

**US5.1 — Aprovisionar una aseguradora.** La ingesta del corpus (índice híbrido con embeddings multilingües, F5.3) es MOD-05 y depende del ADR del almacén vectorial. Dividir:
- `US5.1a` Aprovisionar desde la carpeta de configuración (MOD-09): AC5.1.2 a AC5.1.5.
- `US5.1b` Ingerir el corpus de una aseguradora en su índice (MOD-05): AC5.1.1, con el criterio de recuperación de 5.2.

**US1.2 — Identificarme con mi póliza.** AC1.2.4 (reportar por otra persona, RT-9) cambia el esquema, porque quien reporta no es el asegurado, y dispara una regla. Pasa a `US1.2b` Reportar en nombre de otra persona (MOD-01, MOD-06). Además, el recorrido 7.1 permite identificarse con la cédula ("o el número de cédula con el que está asegurado") y US1.2 no lo recoge. Hay que añadirlo o excluirlo por escrito, porque cambia el generador (MOD-12) y la clave de búsqueda.

**US6.1 — Cotización (Should).** Es una capa entera del plan (semana 10). Si entra, se divide en tres: la captura con el esquema inspirado en ACORD 90 (MOD-01, MOD-13), las reglas de elegibilidad con su banda (MOD-06) y la activación en la apertura según la configuración (D4).

**Recuento.** Con estas divisiones y las historias nuevas de las secciones 1, 3 y 5, el total ronda las 80. Q3 fijó el tamaño (uno a tres días) y estimó el número (45 a 60) a partir de él, así que manda el tamaño. Si Miguel prefiere no pasar de 60, la alternativa mínima es dejar las historias como están y etiquetar cada criterio con el módulo que lo realiza, para que Units Generation las parta sin interpretar. Lo que no admite esa alternativa son los hallazgos 1.1 a 1.5.

### 3. Dependencias ocultas que contradicen la independencia declarada

La Convención dice que ninguna historia necesita que otra se haya ejecutado antes. Es cierto para los datos, pero no para las piezas de base que todas presuponen, y hay criterios que dependen de componentes posteriores.

#### 3.1 Piezas de base que ninguna historia construye

1. **Asegurado simulado por reglas.** Todos los casos multiturno de DS-2 y DS-6 corren con un respondedor por reglas indexado por campo (PRD 11.1). Es lo primero que necesita cada historia de la rama evaluada, y no tiene historia ni criterio. Propuesta:
   - **US4.12 — Correr una conversación de evaluación sin un modelo que haga de asegurado** (Jordan; M8; MOD-11).
   - Criterios:
     - "Dado un caso de DS-2 con las respuestas indexadas por campo, Cuando la agente pregunta los campos en otro orden, Entonces el respondedor entrega la respuesta de cada campo que se pregunta".
     - "Dado una pregunta fuera del esquema, Cuando la agente la hace, Entonces el respondedor contesta 'no sé' y el reporte marca el desvío en ese turno".
     - "Dado la misma salida de la agente dos veces, Cuando corre el respondedor, Entonces produce la misma transcripción".
2. **Casos sembrados en cada estado.** Unas veinte historias parten de casos sembrados "ya decididos", "incompletos", "empezados por voz" o "pausados", pero nadie siembra ese catálogo. Propuesta:
   - **US5.2d — Sembrar un caso en cada estado para probar sin recorrer el anterior** (Miguel; M3; MOD-12).
   - Criterios:
     - "Dado el generador, Cuando siembra, Entonces cada aseguradora tiene, con identificador estable, al menos un caso en cada estado y resolución de 1.3: en captura; esperando al asegurado, cortado por voz y por chat; derivado por regla; derivado por solicitud de persona con 3/7; cerrado aprobado, rechazado y en cierre directo; enviado a la aseguradora; y una consulta de cobertura sin cláusula".
     - "Y cada historia nombra en su criterio el identificador del caso sembrado del que parte".
3. **Credenciales y roles de la bandeja.** US3.1 (la credencial de Diana y la ajena), US3.6 (Priya sin aprobar), US6.2 (rol de suscriptor) y AC4.8.5 dependen del emisor de tokens con aseguradora y rol (F9.3). Q6 de Requirements Analysis quitó las credenciales públicas, así que Diana, Marcus Webb y Priya Raman solo existen con credenciales de desarrollo. Propuesta:
   - **US5.11 — Generar credenciales de la bandeja por aseguradora y rol** (Miguel; M9; MOD-09).
   - Criterios: el token lleva aseguradora, rol y caducidad; un token caducado o de otra aseguradora se rechaza; el rol de agente de cuenta no ve aprobar ni rechazar; el comando está en el archivo de tareas; ninguna credencial se publica, porque el único acceso público es el enlace de US3.7.
4. **Catálogo de textos con chequeo de paridad para el aplicativo.** AC1.7.2, D5 y la guardia de salida lo presuponen, pero solo US4.3 aplica el chequeo, y lo hace sobre la landing, que tiene otro formato (el diccionario en línea de `site/index.html`). Units Generation debe poner en la base el catálogo y su chequeo de paridad español e inglés, con claves sin consumidor.
5. **Andamiaje del primer commit**: manifiesto, lockfile, herramientas con su alcance, archivo de tareas, `scripts/verify.sh` y flujo de GitHub Actions con el escaneo de secretos primero. Es una obligación de las prácticas, no de una historia. Lo registro para que Units Generation lo planifique como unidad propia (`packaging`) en lugar de cargarlo a la primera historia que toque código.

#### 3.2 Criterios de voz dentro de historias de texto

Con Q4, la voz se entrega en capas propias. Estos criterios impiden cerrar su historia en la capa de texto:

| Criterio | Hoy en | Propuesta |
| --- | --- | --- |
| AC1.7.4 misma voz al cambiar de idioma | US1.7 (texto y voz) | Pasa a US1.22: "la pregunta '¿es una persona?' tras el cambio de idioma se responde con la misma voz" |
| AC1.11.2 resumen al volver a llamar | US1.11 (chat) | Pasa a US1.18, y a US1.21 en español |
| AC3.7.1, segunda parte: enlace en la consola al cerrar una llamada | US3.7 (bandeja) | Se funde en un criterio nuevo de US1.15 (ver abajo) |
| AC4.7.5 un grafo para dos canales | US4.7 (base) | "Dado el módulo de orquestación, Cuando se analizan sus importaciones, Entonces no importa ningún adaptador de canal ni SDK de proveedor; Y el mismo caso entregado al adaptador de texto, marcado como chat y como voz transcrita, produce el mismo registro". Se prueba en la capa 1; la comparación con voz real ya está en AC1.15.1 |
| AC4.8.4 recuperación sin cláusulas ajenas | US4.8 (aislamiento en base de datos) | Pasa a US2.1a |

Además falta el cierre por voz. FR1.5 exige que "la transcripción del cierre contiene los seis dígitos separados", pero solo lo realiza US1.10, que es de chat, donde no hay nada que dictar. Propuesta:
- **AC1.15.6 — Cierre por voz con el número dígito a dígito**
  - Dado un reporte completo por voz
  - Cuando la agente cierra
  - Entonces resume en tres frases, dicta el número de caso dígito a dígito y la transcripción del cierre contiene los seis dígitos separados
  - Y en la demo pública la consola muestra el número y el enlace firmado del caso
- Hacer lo mismo en español dentro de US1.20.

Y una convención que quita a las historias de conversación (US1.3 a US1.10) la dependencia de MOD-04: "Los criterios de conducta conversacional se verifican a través del adaptador de texto y del corredor de evaluaciones; solo los criterios de interfaz (selector, cita expandible, carga de la página) necesitan el chat web". Sin ella, US1.3 "por chat" no se puede aceptar hasta la unidad de bandeja y chat de la semana 4, aunque Intake exista desde la semana 3.

#### 3.3 El respaldo de un Should vive dentro del propio Should

AC1.13.5 ("si no se construye") está en US1.13, que es S2, la primera en la regla de corte. Si se corta S2, se corta también su respaldo, y el chat deja de saber qué hacer con un número de caso. Lo mismo pasa con AC1.23.4 dentro de US1.23 (S4).
- Mover AC1.13.5 a US1.12 como `AC1.12.6`, activado por la configuración.
- Mover AC1.23.4 a US1.22 como `AC1.22.5`.

Pero AC1.23.4 no se puede construir sin lo mismo que necesita S4: para preguntar "si prefiero seguir en el otro idioma" hay que detectar que se habla el otro idioma. Si S4 se corta porque la transcripción no identifica el idioma a mitad de llamada, su respaldo tampoco existe. Propuesta: "Entonces la agente sigue en el idioma actual; si la transcripción llega con baja confianza dos veces, pide repetir y recuerda que puede decir 'in English' o 'en español'". Así no hace falta identificar el idioma.

AC1.22.3 (portugués), que es Must, tiene la misma dependencia oculta. Cambio equivalente: "Cuando la agente no entiende dos turnos seguidos por baja confianza, Entonces dice en español y en inglés que solo atiende en esos dos idiomas y ofrece una persona".

#### 3.4 Reglas y guardia como dependencias implícitas

- **Reglas por aseguradora.** Las presuponen AC1.2.4, AC1.8.5, AC1.10.2, AC2.5.4 y AC2.4.2 ("los montos se derivan", que es la regla "toca dinero" del paso 4 del recorrido 7.4). Declarar en esas historias "Construye sobre: US1.10b" y añadir MOD-06 a sus módulos.
- **Guardia de salida.** Los mensajes de degradación y de límite llegan al asegurado: AC2.3.1, AC5.6.2, AC5.7.1 y AC5.8.3. Por el mandato de `project.md`, pasan por la guardia y salen del catálogo, pero sus criterios no lo dicen. AC1.9.4 (registro prohibido) solo se cumple en tiempo de ejecución si la guardia incluye esa lista. Añadir a esos criterios "Y el texto sale del catálogo y pasa por la guardia de salida", con "Construye sobre: US1.8".

#### 3.5 Historias que dependen del despliegue

AC4.1.2 (los enlaces responden), AC4.2.4 y AC4.10.4 ("contra el despliegue vivo") dependen del intent `infra` (D-014) y de la publicación. Conviene anotarlo en "Construye sobre", como "despliegue del intent `infra`", para que Delivery Planning no las adelante y un comprobador de enlaces por hito las verifique.

### 4. Criterios que presuponen una decisión de arquitectura abierta

Ningún criterio nombra una tecnología que el PRD no haya decidido ya (WebRTC, Postgres con RLS, OpenTelemetry con Langfuse, Presidio, Gemini), y eso está bien. Pero los que siguen presuponen el resultado de un ADR abierto (OQ2 a OQ4). Conviene redactarlos para que sigan valiendo con cualquier opción.

1. **AC2.1.1 y AC3.2.1: enlace a la traza en el chat público y traza por nodo en la bandeja pública.** Con Langfuse autohospedado, el PRD 9.5 deja las trazas en local y en el video. Enlazarlas desde el chat público obliga a publicar el backend de trazas, que en su versión autohospedada necesita varias piezas de infraestructura (mucho para un tier gratuito), y abre otra puerta a los datos de otros visitantes. Propuesta:
   - AC2.1.1: "y el identificador de la traza de la respuesta; el enlace a la traza completa existe donde el backend de trazas es accesible y, si se publica, solo muestra la traza de esa respuesta: cambiar su identificador no da acceso a otra".
   - AC3.2.1: la vista de caso muestra un resumen por nodo (latencia, costo, tokens) guardado con el caso, sin depender de que el backend de trazas esté en línea.
2. **AC1.19.2 y AC1.7.4: "el mismo proveedor, la misma voz y el mismo acento" como igualdad de configuración.** Según el proveedor, la misma voz en otro idioma es el mismo identificador con otro parámetro de idioma o un identificador localizado distinto. La identidad percibida la decide la prueba ciega (S6), no la configuración. Propuesta: "Entonces la configuración declara una sola identidad de voz para los dos idiomas: un identificador, o los identificadores de la misma voz localizada, declarados como tal en el ADR de voz".
3. **AC1.15.3 y AC1.20.3: "baja confianza".** No todo proveedor de transcripción en streaming expone una confianza por enunciado que el framework propague. Propuesta: "Dado que la transcripción llega vacía o con confianza por debajo del umbral configurado dos veces seguidas". El ADR de transcripción debe confirmar que hay confianza o dejar la regla solo en transcripción vacía o ininteligible (RT-12 ya dice "STT vacío").
4. **AC4.8.1 y AC4.8.2 frente a las tablas del framework del grafo.** Las bibliotecas de puntos de control suelen crear sus propias tablas, sin columna de aseguradora, y abrir sus propias conexiones. Con el texto actual, la aserción de esquema falla y la búsqueda del punto único de sesión encuentra aperturas ajenas. Propuesta: "incluidas las tablas de puntos de control; si el framework elegido no admite la columna ni el punto único, el ADR del grafo declara cómo se aíslan y la aserción las comprueba por esa vía". Si el almacén vectorial queda fuera de Postgres, RLS no lo cubre, y AC2.1.3 y AC4.8.4 necesitan un criterio de espacio de nombres por aseguradora con su propia prueba.
5. **AC5.6.5: "el proveedor también corta".** Ningún proveedor sabe qué es un "visitante": ese límite solo existe en la aplicación. La duración máxima por llamada puede tener contraparte en el proveedor, según el transporte; los topes diario y de gasto sí la tienen, como cuota o presupuesto. Probarlo "con la aplicación detenida" no demuestra nada, porque sin aplicación nadie emite tokens de llamada: el riesgo real es una clave filtrada o un limitador con errores. Propuesta:
   - **AC5.6.5 — Topes también en el proveedor**
     - Dado la configuración de cada proveedor de la voz (transporte, transcripción, síntesis y modelo)
     - Cuando se inspecciona
     - Entonces cada uno tiene un tope propio de uso o de gasto, igual o menor que el de la aplicación
     - Y la tabla de límites declara cuáles de los tres límites tienen contraparte en el proveedor y cuáles existen solo en la aplicación, con la razón
     - Y un simulacro por hito con una clave de cuota mínima comprueba que el proveedor rechaza al superarla
6. **AC1.11.1: aviso en una conversación abierta.** Empujar un mensaje a una pestaña abierta en un hospedaje gratuito que duerme la instancia es una decisión de OQ4. Propuesta: "Entonces, al volver a la conversación, o en menos de un minuto si está abierta, aparece un mensaje...". Así también funciona con consulta periódica.
7. **AC5.4.4: con una voz inexistente, "el arranque falla".** Si validar la voz exige llamar al proveedor al arrancar, una caída del proveedor tumba también el chat, que no la necesita (PRD 12.3). Propuesta: "Entonces el canal de voz no arranca, la consola muestra un mensaje honesto, y el chat arranca y responde".
8. **AC1.15.4, AC1.16.1 y AC1.20.5: qué se mide exactamente.** Ver 6.1.

### 5. Exactitud de módulos y requisitos

#### 5.1 Correcciones por historia

| Historia | Hoy | Corrección | Razón |
| --- | --- | --- | --- |
| US1.5 | Realiza NFR12 (RT-8) | Origen: PRD 11.2, criterio de seguridad "911 antes que cualquier dato" **[bloquea]**. No tiene NFR propio; hay que registrarlo en `nfr-requirements` | NFR12 mide "0 respuestas que obedezcan una instrucción inyectada", y RT-8 no es una inyección |
| US1.7, US1.9 | Realiza NFR12 | Origen: P10 y P11 más la rúbrica de estilo (PRD 10.4, 90 %). NFR12 queda solo para AC1.7.3 (presión para negarlo) | Mismo motivo. La rúbrica no tiene requisito, como ya anota el diario de la etapa |
| US1.1 | MOD-04, MOD-07, MOD-09 | Añadir MOD-01 | AC1.1.2 guarda la divulgación en el caso e impide cerrarlo |
| US1.2 | FR1.1 | Añadir NFR10 | AC1.2.2 y AC1.2.3 prueban que no hay fuga entre aseguradoras |
| US1.4 | FR1.2 | Añadir FR1.3 | AC1.4.2 y AC1.4.4 son completitud |
| US1.12 | FR2.4 | Añadir FR1.4 y FR7.1 | AC1.12.1 fija un estado; AC1.12.4, la divulgación |
| US1.15 | FR1.1, FR1.3, FR10.2, NFR1, NFR7, NFR8 | Añadir FR1.5 (AC1.15.6) y FR2.6 | AC1.15.1 es "el mismo grafo para voz y chat" |
| US1.18 | FR3.6, FR10.2 | Añadir FR8.6 | AC1.18.1: "aparece así en la bandeja" |
| US1.19 | MOD-03, MOD-07 | Añadir MOD-09 y FR9.3 | AC1.19.4 usa el idioma por defecto de la configuración, igual que US1.14 |
| US1.20 | MOD-03, MOD-02, MOD-01, MOD-11 | Añadir MOD-05, MOD-10, FR5.6 y FR10.2 | AC1.20.4 es una respuesta citada, y la latencia sale de los eventos |
| US2.1 | MOD-04, MOD-05, MOD-10 | Añadir MOD-02 | AC2.1.6 vuelve al punto del reporte |
| US2.3 | MOD-02, MOD-05, MOD-10 | Añadir MOD-11 | AC2.3.4 es del reporte de evaluación |
| US2.4 | MOD-03, MOD-05, MOD-07 | Añadir MOD-06 y FR6.2 | AC2.4.2 es la regla "toca dinero, se deriva" |
| US2.5 | FR5.3 | Quitar AC2.5.4 o hacerlo referencia de AC3.6.1 | Son el mismo criterio |
| US2.6 | S5 | Añadir FR4.6 | AC2.6.5 son los límites del chat |
| US4.9 | MOD-07, MOD-10 | Añadir MOD-11 | AC4.9.2 y AC4.9.3 son de la compuerta y del reporte |
| US5.9 | MOD-08, MOD-03, MOD-12 | Añadir MOD-02, MOD-09 y MOD-10 | El reinicio borra puntos de control y trazas e invalida enlaces firmados (1.2, 6.4) |
| US5.10 | MOD-04, MOD-10 | Añadir MOD-03 y MOD-08 | AC5.10.1 comprueba la bandeja y la consola |
| US6.2 | MOD-08, MOD-13 | Añadir MOD-09 | Rol de suscriptor |

#### 5.2 Huecos de trazabilidad

- **NFR18 sin destino escrito.** El plan (`user-stories-questions.md`) dice que la cobertura de líneas queda diferida "con ese destino escrito", pero `stories.md` no lo escribe, y el sensor de trazabilidad lo marcará como GAP. Añadir a "Lo que no se convierte en historia" la fila: "NFR18, cobertura de líneas | La mide el equipo, no una persona | `nfr-requirements` y `build-and-test`, con el comando y la lista de exclusión de la práctica".
- **Metas cuantificadas del Segmento 10 sin historia ni NFR.** Por el mandato de `project.md`, cada una debe llegar a `nfr-requirements`. Propongo un criterio de hito donde una persona la percibe, y la fila de destino donde no:
  - Fidelidad de la lectura de confirmación, 98 % o más: AC1.3.7 (ver 2).
  - Turnos por caso completo, 14 o menos y 5 minutos o menos: criterio de hito en US1.3a y en US1.15, que además hace visible la contradicción de 1.4.
  - Éxito de tarea, 90 % o más (la métrica guía): criterio de hito en US4.5, cuyo reporte la publica por idioma.
  - Recuperación correcta, 95 % o más (PRD 11.2, "Relevancia: recuperación"): criterio en US2.1a.
  - Casos reanudados sin repetir, 100 %: criterio de hito en US1.18.
  - Adherencia de idioma, 100 % (PRD 11.2): criterio de hito junto a AC1.1.4.
  - Tiempo del ajustador, menos de 3 minutos (AC3.2.5): no se puede verificar por código. El PRD 10.3 lo mide con cronómetro en la validación del día 30, así que el criterio debe decir "se mide en la validación del día 30" y tener su fila en `nfr-requirements`.
- **Historias Should sin FR** (US1.13, US1.23, US2.6, US6.2). En `traceability.json` necesitan una entrada `N/A` con la justificación "Should del PRD sin FR; observación R-01 aceptada como riesgo", o el sensor las marcará como huérfanas.
- **FR2.7 cubierto solo para la verificación.** La política de fallo es por nodo, pero solo US2.3 la ejercita. No hay historia para el fallo más probable del sistema: el modelo que no responde o devuelve límite de tasa en el tier gratuito (fila 1 de PRD 12.3 y modo de fallo "Límite de tasa o cuota del LLM"). Tampoco para la caída de la transcripción, la caída de la síntesis por error (US5.5 solo cubre el presupuesto agotado) ni la caída de la base de datos. Propuesta:
  - **US2.7 — Que la conversación no se rompa si el modelo o un proveedor de voz no responde** (Must, M2; FR2.7; MOD-02, MOD-03, MOD-07).
  - Criterios:
    - Hay un reintento; después, el mensaje del catálogo pasa por la guardia y el caso queda guardado.
    - En voz, la agente ofrece guardar el caso o pasar a una persona, según D8.
    - La traza registra `rate_limited` o `unavailable`, con el nodo y el intento.
    - Si la síntesis cae, se pasa a la voz de respaldo con el mismo mecanismo de US5.5.
    - Si la transcripción cae, la llamada termina con un mensaje honesto. Solo ofrece "seguir por el chat con su número de caso" si la continuidad voz a chat está activa, porque S2 es la primera en cortarse y la frase del PRD 12.3 la da por hecha.

### 6. Riesgos técnicos que Units Generation debe conocer

#### 6.1 Latencias de turno y de parada

- **Qué cuenta como "fin del habla".** Si es el evento del detector de turno, la cifra deja fuera la espera de silencio con la que el detector decide que el asegurado terminó (del orden de cientos de milisegundos). Si es la última palabra audible, un p50 menor de 500 ms con una cascada de transcripción, modelo y síntesis es muy exigente. P4 prohíbe publicar una latencia sin decir qué mide, y AC4.11.3 solo dice "turno o parada". Propuesta para AC1.15.4 y AC4.11.3: nombrar el evento de inicio y el de fin, y publicar las dos variantes si difieren.
- **Latencia de parada menor de 300 ms (AC1.16.1).** Medida en el servidor, no incluye el búfer de reproducción del cliente. Hay que definir si termina cuando el servidor cancela la síntesis o cuando el navegador deja de reproducir.
- **Hospedaje gratuito (A1).** La CPU compartida para los detectores de actividad de voz y de turno, el arranque en frío y la distancia entre la región del hospedaje, los proveedores y un evaluador en Estados Unidos o Europa suman al p95. El spike de la semana 1 debe medir la cascada en el hospedaje candidato, no en local.
- **Guardia de salida frente a síntesis en streaming.** Emitir el primer audio antes de terminar la respuesta (F3.3) y pasar la guardia antes de emitir (F7.5) solo son compatibles si la guardia evalúa frase por frase, antes de mandar cada una a la síntesis, con presupuesto propio (del orden de decenas de milisegundos). Criterio propuesto para US1.8: "la guardia evalúa cada frase antes de enviarla a la síntesis, sin esperar la respuesta completa".
- **Verificación de soporte antes de emitir en el chat** (F5.5, segunda pasada del modelo). Son dos o tres llamadas al modelo por respuesta, en un tier gratuito con límite por minuto. Pone en riesgo el p95 menor de 3 s del chat (NFR4) en cuanto haya más de un visitante a la vez.

#### 6.2 Límites en el proveedor y un visitante sin identidad

- Sin inicio de sesión, un visitante no tiene identidad. Una cookie se borra, una ventana privada la esquiva, y la IP agrupa a toda una oficina: dos evaluadores de la misma empresa comparten límite. Guardar la IP es, además, un dato personal con retención. Criterio propuesto para US5.6: "Dado que un visitante borra sus cookies o usa otro navegador, Cuando intenta otra llamada, Entonces el tope diario del sitio y el techo de gasto siguen acotando el gasto; el límite por visitante no se presenta como control de gasto". Así la prueba no promete lo que no se puede garantizar.
- Pasa lo mismo con el límite por sesión del chat (AC5.7.1): el control real es el tope diario del sitio más la cuota de la clave propia.

#### 6.3 Redacción antes de persistir, en el camino de voz

Pasar Presidio, con los modelos de español e inglés, por cada transcripción parcial dentro del turno compite con el p50 menor de 500 ms. Propuesta: las parciales no se persisten, solo se muestran en la consola; la final se redacta de fondo antes de escribirse. Los modelos de spaCy que usa Presidio pesan cientos de megabytes por idioma, lo que complica NFR21 (menos de 15 minutos en máquina limpia) si el comando de evaluación tiene que descargarlos.

#### 6.4 Reinicio nocturno

Toca más almacenes de los que nombran FR8.8 y NFR19:

- **Registro de gasto.** Si el acumulado se calcula desde las filas de los casos y el reinicio borra los casos de visitantes, el techo de 5 USD se olvida cada noche. El registro de gasto debe vivir aparte y sobrevivir al reinicio y a los despliegues. Criterio para US5.8: "Dado el reinicio nocturno, Cuando termina, Entonces el gasto acumulado del periodo no cambia".
- **Puntos de control y trazas de visitantes** (ver 1.2).
- **Conversación en curso a la hora del reinicio.** Criterio para US5.9: "Dado una llamada o conversación en curso, Cuando llega la hora del reinicio, Entonces el reinicio no borra ese caso hasta que la conversación termina, o la cierra con un mensaje honesto antes de borrar".
- **Identificadores reutilizados.** Un enlace emitido a las 23:30 vale hasta las 00:30. Si el reinicio de las 00:00 reinicia la secuencia de casos, ese enlace abre el caso de otro visitante. AC5.9.4 lo prohíbe, pero el criterio debe fijar el mecanismo: "Y el enlace se liga al identificador interno del caso, que nunca se reutiliza, o la clave de firma rota en el reinicio".
- **Origen de cada caso.** Distinguir un caso de visitante de uno sembrado exige un campo de origen en el esquema (MOD-01) que ningún criterio pide.
- **Zona horaria** de "cada noche": un valor de configuración.

#### 6.5 Enlace firmado

- Un token en la dirección queda en los registros de acceso del hospedaje, que no pasan por el punto único de salida. Criterio propuesto para AC3.7.2: "Y el token no aparece en ningún registro del aplicativo ni del hospedaje". Una forma es que viaje en el fragmento de la dirección y se canjee por una sesión; la decide el diseño.
- Falta aclarar si el enlace sigue sirviendo después de decidir: AC3.4.5 impide una segunda decisión, pero no la lectura.

#### 6.6 Detección automática de idioma

- **Chat (AC1.1.4, Must).** Los mensajes cortos ("ok", una placa, un nombre propio) no tienen un idioma fiable. Criterio propuesto, **AC1.1.6 — Mensaje ambiguo**: "Dado una conversación en inglés, Cuando escribo 'ok', un número de placa o un nombre propio, Entonces la respuesta sigue en inglés".
- **Voz.** Con la transcripción configurada para un idioma, la propia petición "in English, please" puede transcribirse mal (AC1.22.1). El ADR de transcripción debe admitir varios idiomas en la misma sesión, o cambiar de idioma dentro de la llamada sin cortarla.

#### 6.7 Evaluación en el tier gratuito

Una corrida de DS-2 (60 conversaciones de unos 15 turnos, con guardia y a veces verificación), DS-3 y DS-6 hace más de mil llamadas al modelo. Con los límites por minuto y por día del tier gratuito que conozco (a verificar en el spike), la corrida completa no cabe en 10 minutos (NFR17) y quizá tampoco en la cuota diaria. La práctica ya admite un subconjunto declarado para la compuerta, pero AC4.4.1 le promete el reporte "en menos de 15 minutos" a un evaluador que usa su propia clave. Propuesta:

- AC4.4.1: "ejecuto el comando de evaluación del subconjunto declarado y obtengo su reporte en menos de 15 minutos; el README declara el comando de la corrida completa y su duración medida".
- **AC4.4.6 — Sin backend de trazas**: "Dado que el backend de trazas no está corriendo, Cuando corro la evaluación, Entonces el reporte se produce igual y los enlaces a trazas se marcan como no disponibles".

#### 6.8 Minutos de GitHub Actions en un repositorio privado

El PRD 10.2 sugiere un ping cada 5 minutos con un cron de GitHub Actions, y la práctica corre la compuerta con golden sets en cada commit. El plan gratuito que conozco incluye del orden de 2.000 minutos al mes para repositorios privados, y redondea cada trabajo al minuto: el ping solo consumiría unos 8.600. Units Generation y el intent `infra` necesitan otro origen para la comprobación periódica, o una cadencia que quepa, y confirmar que el ping no infringe los términos del hospedaje gratuito.

Además, la sonda de AC5.10.1 no puede "probar el chat y la consola" con una conversación y una llamada reales: consumiría cuota del modelo, contaría contra las 15 llamadas del día y crearía casos. Propuesta: "Entonces una comprobación sintética recorre las dependencias del chat, la bandeja y la consola sin llamar al modelo ni a los proveedores de voz, sin crear casos y sin contar contra los límites".

#### 6.9 Audio del golden set en el repositorio

DS-5 son grabaciones de personas reales: Miguel, los voluntarios y las tres personas de Medellín. AC4.4.3 exige versionarlas como archivos por caso. Eso choca con "NEVER incluir datos de personas reales ... en el repositorio" de `project.md`: la voz es un dato personal aunque el guion sea sintético, y el repositorio es candidato a público (D-017). Además, son muchos binarios pesados para git. Hace falta una de dos cosas: una excepción escrita, con consentimiento y licencia de uso por cada voz, o dejar el audio fuera del historial y versionar solo el guion, las marcas y el registro esperado. Es decisión de Miguel; la señalo porque cambia AC4.4.3.

#### 6.10 Voz paisa y voz de respaldo

- **Presupuesto agotado a mitad de llamada.** AC5.5.1 solo cubre "la llamada siguiente"; si el presupuesto se acaba durante una llamada, la síntesis falla ahí mismo. Criterio propuesto:
  - **AC5.5.6 — El presupuesto se acaba durante una llamada**
    - Dado que el presupuesto restante de la voz paisa no cubre la duración máxima de una llamada
    - Cuando entra una llamada
    - Entonces se atiende con la voz de respaldo
    - Y si el proveedor rechaza a mitad de llamada, la llamada sigue con la voz de respaldo y la traza registra el cambio
- **Una sola identidad en la voz de respaldo.** Los TTS locales gratuitos suelen usar voces distintas por idioma. Una voz de respaldo que cambia al pasar de español a inglés contradice P10 ("prohibido cualquier acento distinto por idioma") y W9. O la voz de respaldo es multilingüe con una sola identidad, o el modo degradado lleva la excepción escrita.
- **Dos presupuestos, dos nombres.** "Presupuesto de la voz paisa" (la cuota periódica del proveedor, US5.5) y "techo de gasto del proyecto" (5 USD acumulados, US5.8) no deben compartir palabras: hoy AC5.5.4 ("nuevo periodo") se puede leer como si hablara del techo.

#### 6.11 Datos sintéticos y corpus

- **Determinismo frente a generación con modelo.** El PRD F12.6 genera los datos con el modelo, pero FR11.2 y AC5.2.1 exigen bytes idénticos con la misma semilla, y un modelo no da esa garantía ni con temperatura 0. Propuesta para AC5.2.1: "el borrador que produce el modelo se revisa y se versiona como fuente; el comando de regeneración es determinista, no llama al modelo y produce bytes idénticos a partir de esas fuentes".
- **El chequeo de texto de terceros (AC5.2.4, FR12.2) no tiene un mecanismo posible tal como está escrito.** Para detectar texto de ISO o ACORD hace falta una referencia, y ese texto no puede estar en el repositorio. Propuesta: "el chequeo compara contra huellas de n-gramas de frases de referencia, guardadas solo como hash, y declara su límite: detecta copia literal, no paráfrasis; la revisión manual de una muestra por idioma (F12.6) cubre el resto".
- **Idioma del corpus.** Ninguna historia fija en qué idioma están las pólizas de cada aseguradora ni qué ve una asegurada hispanohablante de Sunmeadow si la cláusula está en inglés. Eso afecta a MOD-05 (recuperación entre idiomas), a DS-3 (20 preguntas por idioma) y a P2 ("prohibido parafrasear una cláusula como si fuera literal"). Criterio propuesto para US2.1c: "Dado una cláusula en un idioma distinto del de la conversación, Cuando se muestra, Entonces el texto completo aparece en su idioma original y la explicación en el idioma del asegurado, marcada como resumen".
- **Recuperación vectorial filtrada.** Si el índice vectorial vive en Postgres, filtrar por aseguradora y póliza después de consultar el índice puede devolver menos resultados de los pedidos y bajar la recuperación, justo en las pólizas con pocos fragmentos. El spike del almacén vectorial debe medir la recuperación filtrada sobre DS-3.

#### 6.12 Alertas sin canal

AC5.8.2 ("recibo una alerta"), AC5.9.5 y AC5.10.3 no dicen por dónde llega el aviso, y no hay mensajería dentro del alcance. Propuesta: "se registra en el canal de alertas declarado en la configuración". El canal lo decide el diseño de observabilidad o el intent `infra`.

### 7. Textos concretos para D8 a D11

- **D8.** Mantener que la agente no ofrece devolver la llamada, pero condicionar la frase de reemplazo a lo que se puede cumplir. "Si prefiere, guardo su caso para que lo retomemos cuando vuelva a llamar, o le paso a una persona" solo vale donde existe la reconexión (opción A de 1.4). Sin ella, en el enlace público: "Si prefiere, le paso a una persona; lo que registramos queda guardado en su caso". El cambio alcanza también a la meta "Silencios manejados" del PRD 10.4, a RT-12 y al mensaje de voz con el modelo caído del PRD 12.3 ("le devolvemos la llamada"), que heredan la misma promesa.
- **D9.** Una frase por canal, desde el catálogo. Chat: "Un ajustador revisa su caso y la actualización le aparece en esta conversación". Voz: "Un ajustador revisa su caso; cuando vuelva a llamar, le cuento lo que decidió". En voz no hay nada que "llegue": el asegurado tiene que volver a llamar. En el enlace público, la consola muestra además el enlace firmado.
- **D10.** Extender la forma neutra a otra frase fija de la guía que tiene género: "Tranquilo, vamos paso a paso" (punto 5 y recorrido 7.1) pasa a "Con calma, vamos paso a paso". Y dejar registradas las frases cambiadas para actualizar `docs/pre_prb/voz-y-tono.md`, de modo que el catálogo no se aparte de la guía.
- **D11.** Cuatro precisiones:
  - fijar en el criterio la fecha de inicio del periodo de 90 días y qué pasa al terminar, porque la publicación del día 90 (2026-12-14) coincide con el fin del periodo;
  - llevar el registro de gasto aparte del borrado nocturno (6.4);
  - cambiar el mensaje de corte, que hoy dice "alcanzó su presupuesto de este mes" (PRD 12.3): con un techo acumulado la voz no vuelve el mes siguiente, y la frase prometería algo falso;
  - anotar que el texto de la práctica de despliegue de `team.md` ("techo mensual de gasto") queda contradicho y debe corregirse por el ritual de aprendizajes.

## Positions

- AGREE: D8, retirar "devolver la llamada" de los silencios, del audio inservible y de la degradación — C3 no existe y P7 prohíbe ofrecerla.
- OBJECT: D8, la frase de reemplazo "guardar el caso para retomarlo al volver a llamar" en el enlace público — el límite de una llamada por visitante y el reinicio nocturno la hacen imposible de cumplir sin la reconexión de 1.4.
- AGREE: D9, quitar el plazo y la llamada saliente — la demo no los garantiza y la guía prohíbe especular sobre tiempos.
- OBJECT: D9, "la actualización le llega por este mismo canal" en voz — por voz no llega nada; el asegurado tiene que volver a llamar, así que la frase debe ser distinta en cada canal.
- AGREE: D10, forma de cortesía neutra — evita que el sistema infiera el género de quien llama y no añade ningún campo al estado.
- OBJECT: D10, alcance tal como está redactada — deja fuera "Tranquilo, vamos paso a paso", otra frase fija con género.
- AGREE: D11, techo acumulado de 5 USD en 90 días — es lo que fijan D-015 y NFR15 y lo que asume el cálculo de Q8.
- OBJECT: D11, sin fecha de inicio, sin un registro de gasto que sobreviva al reinicio nocturno y con el mensaje de corte "de este mes" — así el techo no es comprobable y el mensaje promete una recuperación que no ocurre.
- OBJECT: D7, 0,005 USD por minuto a precio de lista para toda la voz — el PRD 10.5 incluye transcripción y síntesis a precio de lista, y la cifra de origen solo cuenta el modelo.
- AGREE: D4, ofrecer cotizar solo si está activa en la configuración — se implementa con dos claves del catálogo y conserva la paridad.
- AGREE: D5, bandeja bilingüe con inglés por defecto — mantiene la bandeja dentro del chequeo de paridad, sin excepciones.
- AGREE: D6, el enlace firmado da acceso solo a la vista de su caso — deja la superficie anónima reducida a un único recurso.
- OBJECT: convención "Independencia" tal como está escrita — vale para los datos, pero no para la base sin historia (asegurado simulado, casos por estado, credenciales, catálogo) ni para los criterios de voz metidos en historias de texto.
- OBJECT: umbrales agregados como criterio de aceptación de historias de uno a tres días — dependen de conjuntos completos, de voluntarios y de la calibración del juez, y la postura de pruebas ya define la aceptación por caso.
- OBJECT: reanudación y resumen de la decisión identificados solo por la póliza (AC1.11.2, AC1.12.2, AC1.13.1, AC1.18.2, AC1.21.3) — con la póliza de ejemplo compartida, exponen casos de otros visitantes.
- OBJECT: AC3.5.3 tal como está, junto a AC1.6.1 y AC1.6.4 — un caso derivado con datos incompletos quedaría sin poder decidirse.
