# Pólizas ficticias con estructura colombiana (fase 4 del plan 09)

Decisión de Miguel del 2026-11-02: las pólizas de ejemplo se reescriben con la
estructura de una póliza de automóviles colombiana, sin copiar texto de ninguna
aseguradora ni nombrar aseguradoras reales. Hoy siguen la póliza estadounidense
de ISO (Partes A a F), que quien conoce el mercado colombiano no reconoce.

## Lo que no cambia

- **Los identificadores internos de cláusula** (`A.INS`, `A.EXCL.A.3`,
  `D.INS.COLLISION`, `E.DUTIES.A.1`, `F.FRAUD`, `DEF.COVERED_AUTO`…). Son letras y
  números neutros, y los citan los golden sets, las reglas, las pruebas y la
  pestaña de pólizas. Cambiarlos movería todo sin que nadie lo vea. Excepción:
  cuatro claves cuyo nombre contradecía su contenido nuevo (ver «Claves de
  cláusula renombradas»).
- Las ocho ranuras (acuerdo, definiciones, partes A a F), los endosos (cinco por
  aseguradora), la versión 2025, los distractores y las diferencias a propósito
  entre las dos aseguradoras.
- Los montos se guardan en miles de pesos, como desde el 2026-10-07.
- Los números de póliza (POL-11…, POL-21…, POL-31…, POL-50) y las personas.

## Lo que cambia: qué es cada ranura

| Ranura | Hoy (ISO) | Con estructura colombiana |
| --- | --- | --- |
| Acuerdo | Agreement | Objeto del seguro y vigencia |
| Definiciones | you, we, covered auto… | Tomador, asegurado, beneficiario, vehículo asegurado, valor comercial (guía de valores de Fasecolda), siniestro, deducible, tercero, conductor autorizado, pérdida total, SMMLV |
| Parte A | Liability | Responsabilidad civil extracontractual: daños a bienes de terceros, muerte o lesiones a una persona, a dos o más personas; en exceso del SOAT; la defensa y los costos del proceso como pago adicional |
| Parte B | Medical payments | Gastos médicos de los ocupantes, en exceso del SOAT |
| Parte C | Uninsured motorists | Accidentes personales del conductor (muerte o incapacidad permanente del conductor autorizado) |
| Parte D | Damage to your auto | Pérdida parcial y total por daños (`D.INS.COLLISION`) y por hurto (`D.INS.OTC`); gastos de transporte por pérdida total (`D.TRANSPORT`); el valor asegurado es el valor comercial según la guía de Fasecolda; pérdida total cuando la reparación cuesta el 75 % o más de ese valor |
| Parte E | Duties after a loss | Obligaciones en caso de siniestro: aviso dentro de los tres días hábiles siguientes a conocerlo, denuncia ante la autoridad en caso de hurto, no reconocer responsabilidad ni conciliar sin autorización, pruebas del siniestro, permitir la inspección |
| Parte F | General provisions | Condiciones generales: revocación, terminación automática por mora en el pago de la prima, prescripción, pago de la indemnización, subrogación, salvamento, declaración del estado del riesgo, coexistencia de seguros, territorio, notificaciones |
| Jurisdicción | Endoso de jurisdicción ficticia | Marco legal: el contrato se rige por la ley colombiana (Código de Comercio). Se cita la ley, que es pública; nunca se dice que la póliza «cumple con» nada |

Cada parte trae su título visible con el nombre colombiano. Las aseguradoras
siguen siendo ficticias y el texto, propio.

## Tres claves de límite que cambian de nombre

Su significado cambia, y una clave que dice una cosa y guarda otra confunde a
quien lee el repositorio (hecho en el paso 3):

| Antes | Después | Qué guarda |
| --- | --- | --- |
| `c.uninsured_per_person`, `c.uninsured_per_accident` | `c.driver_personal_accident` | El valor asegurado de accidentes personales del conductor |
| `d.collision_deductible` | `d.damage_deductible` | El deducible de pérdida parcial por daños |
| `d.other_than_collision_deductible` | `d.theft_deductible` | El deducible de pérdida parcial por hurto |

Las de la Parte A y la B conservan su nombre: su significado no cambia.

## Golden sets

- DS-3: las preguntas que nombran conceptos que ya no existen (motorista sin
  seguro, colisión y «otros que no son colisión») se reescriben con el concepto
  colombiano, y las que cambian de concepto cambian de identificador, anotado en
  este documento. Ningún caso se retira y el total no baja.
- DS-2 y los sondeos de datos rígidos: se ajustan a las claves nuevas.
- La corrida de citas contra el modelo (`evals:citas`, centavos) se hace una vez,
  al final.

## Orden

1. Referencia de estructura en `docs/reference/estructura-poliza-autos-colombia.md`,
   solo nombres de partes y fuentes públicas (Código de Comercio, guía de valores
   de Fasecolda). La de ISO queda como antecedente.
2. Seguros Aburrá en español (sus fuentes son en español). Revisión.
3. Autos Poblado en inglés, las traducciones de las dos, las claves de límite,
   los golden sets, la pestaña de pólizas, el README y la landing.
4. Regenerar el corpus y las pólizas emitidas, ingesta local, `evals:citas`.
5. Miguel prueba en local. Producción solo después.

## Claves de cláusula renombradas (paso 3)

El plan decía que los identificadores no cambian. Cuatro quedaron con un nombre que contradice su contenido nuevo y tienen pocas referencias, así que se renombraron; el resto se conserva y se anota.

| Antes | Después | Por qué |
| --- | --- | --- |
| `DEF.TRAILER` | `DEF.COMMERCIAL_VALUE` | Ya no define el remolque: define el valor comercial (guía de Fasecolda). |
| `D.INS.OTC` | `D.INS.THEFT` | «Otros que no son colisión» ya no existe: la cláusula cubre solo el hurto. |
| `A.FIN_RESP` | `A.SOAT` | La responsabilidad financiera de ISO pasó a ser la relación con el SOAT. |
| `A.OUT_OF_STATE` | `A.OUT_OF_COUNTRY` | Ya no hay estados: es la cobertura fuera de Colombia. |

Claves que se conservan aunque el nombre ya no es exacto: `D.INS.COLLISION` (cubre los daños por choque, vuelco, incendio, inundación y otros; el plan la nombra así), `DEF.COVERED_AUTO` («vehículo asegurado»), `DEF.TEMPORARY_SUBSTITUTE` («vehículo de reemplazo»), `DEF.BODILY_INJURY` («lesión personal») y `F.BANKRUPTCY` (insolvencia). Son sinónimos o aproximaciones y tienen muchas referencias.

Las muestras de revisión del 2026-09-21 (`app/data/sources/reviews/*-2026-09-21.yaml`) no se tocaron: son el registro del veredicto de Miguel sobre el texto anterior y citan identificadores que ya no existen (`DEF.TRAILER`, `D.INS.OTC`, `C.*` con otro contenido). Las nuevas, del 2026-11-02, esperan su veredicto.

## Casos renombrados

DS-3, sin retirar ninguno: el total sigue en 23 casos por idioma (46 archivos) y se mantiene la paridad es/en. Cada fila vale para los dos idiomas.

| Antes | Después | Qué cambió |
| --- | --- | --- |
| `coverage-uninsured-limit` | `coverage-driver-accident-limit` | De «conductor sin seguro» a accidentes personales del conductor (`C.LIMIT`). |
| `distractor-uninsured-coverage` | `distractor-driver-accident-coverage` | Ahora pregunta por la incapacidad permanente parcial, que la edición anterior (`C.INS.ALT`) no cubría. |
| `coverage-collision-limit` | `coverage-total-loss-limit` | De «daños a mi vehículo» a la pérdida total, con el valor asegurado de la guía de Fasecolda (`D.LIMIT`). |

Casos que conservan el nombre y cambiaron la pregunta: `distractor-duties-after-loss` (ahora pregunta en cuántos días hay que avisar, que es lo que distingue `E.DUTIES.A.1` de su edición anterior), `coverage-medical-limit`, `knotwell-medical-limit`, `cross-language-other-insurance-liability` y `endorsement-excludes-carrying-for-hire` (en inglés, «medical payments» pasó a «medical expenses»). `knotwell-collision-coverage` conserva el nombre porque `D.INS.COLLISION` sigue cubriendo el choque. Los casos sin cláusula se revisaron contra el texto nuevo y siguen sin cláusula; en `no-clause-loan-payments` se anotó que ahora `DEF.YOU` nombra al banco como posible beneficiario, y esa respuesta la confirma la próxima corrida de `evals:citas`.

## Estado

| Paso | Estado |
| --- | --- |
| 1–3 | Hechos el 2026-11-02. |
| 4 | Hecho el 2026-11-02: corpus regenerado e ingerido en local, `evals:citas` 24 de 24 en español y 24 de 24 en inglés (corrida `run-b0ac5f5a1c8c`). |
| 5 | Pendiente: la prueba de Miguel en local, su veredicto sobre las muestras de revisión del 2026-11-02 y después producción. |

## Lo que encontró la corrida de citas

La primera corrida dio cinco casos que en la línea base pasaban. Ninguno era un
fallo del sistema; eran el texto nuevo frente a casos escritos para el viejo:

| Caso | Causa | Arreglo |
| --- | --- | --- |
| Las cinco, en la primera corrida | La ingesta no borraba las cláusulas cuya clave cambió de nombre, y la recuperación las seguía devolviendo | La ingesta borra lo que salió del corpus (`repository.upsert_reference_data`) |
| `DS-3/es/knotwell-collision-coverage` | `D.INS.COLLISION` se alargó (regla del 75 %, deducible) y perdió contra exclusiones cortas en la búsqueda por significado | La regla del 75 % queda solo en `D.LIMIT`; la cláusula empieza por «Si usted choca…» |
| `DS-3/{es,en}/no-clause-rental-abroad` | `A.OUT_OF_COUNTRY` repetía la regla de territorio y se llevaba la cita | La regla queda en `F.PERIOD_TERRITORY`, explícita: «fuera de Colombia no hay cobertura salvo endoso» |
| `DS-3/en/endorsement-excludes-carrying-for-hire` | `B.INS` decía solo «ocupantes», sin nombrar al asegurado | `B.INS` nombra a usted, al conductor autorizado y a los demás ocupantes |
| `DS-3/{es,en}/coverage-agreement-scope` | La pregunta hablaba del «acuerdo general» de ISO, y `AGREEMENT.1` no decía qué cubre | Pregunta nueva («¿Qué cubre esta póliza según su objeto?») y `AGREEMENT.1` enumera los amparos |

Queda una observación sobre la recuperación, sin arreglar aquí: la búsqueda por
texto exige que todas las palabras de la pregunta estén en la cláusula, así que
casi nunca aporta en preguntas cortas y todo lo carga la búsqueda por
significado.
