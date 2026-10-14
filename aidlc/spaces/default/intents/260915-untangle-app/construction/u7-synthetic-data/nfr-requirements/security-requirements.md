# Requisitos de seguridad — U7 `synthetic-data`

U7 protege cuatro cosas:
- que ningún texto de un formulario de terceros llegue al corpus (P8), ni
  siquiera como material de comparación;
- que todo dato con forma de dato personal sea ficticio y la redacción lo
  encuentre (FR12.3);
- que el modelo nunca escriba directo en los datos versionados;
- que los datos versionados sean exactamente lo que produce el generador, sin
  ediciones a mano que nadie revisó.

**`mise run test:u7` y `mise run synthetic:check` no existen todavía**: son
tareas nuevas que crea la generación de código de esta unidad. Los demás
comandos existen hoy.

## Modelo de amenazas

| Amenaza | Qué podría pasar | Control | Requisito |
| --- | --- | --- | --- |
| Texto ajeno en el corpus | Una cláusula calca un formulario con derechos de ISO y el repositorio no se puede publicar (P8, D-017) | Huellas y umbral cero en cada entrega | SEC-U7.1 |
| Texto ajeno como insumo | El texto de un specimen entra al repositorio "solo para comparar" | Huellas guardadas solo como hashes; `tmp/specimens/` ignorado por git | SEC-U7.2 |
| Dato personal real | Un teléfono, placa o cédula sembrado coincide con el de una persona real | Rangos ficticios y composición desde la semilla | SEC-U7.3 |
| Dato ficticio que la redacción no ve | Un valor sembrado sale sin redactar en una traza y la prueba de fuga no lo detecta | Cada valor sembrado pasa por la redacción de U3 | NFR11.10 |
| Modelo sin revisión | Un borrador del modelo entra al corpus sin que nadie lo lea | Borradores fuera del generador; marca de revisión obligatoria | SEC-U7.4 |
| Datos editados a mano | Alguien corrige un JSON de `app/data/` y la regeneración ya no lo reproduce | Regeneración en cada entrega comparada byte a byte | TECH-U7.1 |
| Aislamiento sin colisiones | DS-8 pierde sus colisiones al regenerarse y la prueba de aislamiento deja de probar algo | DS-8 regenerado con los mismos identificadores | NFR10.7 |

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| SEC-U7.1 | Cláusulas del corpus que comparten al menos una secuencia de ocho palabras con los formularios de terceros, sin encabezados ni numeración (AC5.4.4, AC5.5.5, `[bloquea]`) | **Exactamente 0**. Sin archivo de huellas: "no medido" y falla | `mise run content:check` |
| SEC-U7.2 | Secuencias legibles de un specimen dentro del repositorio | **Exactamente 0**: el archivo de huellas solo tiene hashes, y `tmp/specimens/` está ignorado | Tarea nueva `mise run test:u7` |
| SEC-U7.3 | Datos con forma de dato personal fuera de sus rangos ficticios (teléfonos 555-01XX, correos de example.com o example.org, VIN con dígito de control inválido) | **Exactamente 0** | `mise run test:u7` |
| SEC-U7.4 | Salidas del generador que cambian al plantar un borrador, o textos fuente sin marca de revisión que llegan al corpus | **Exactamente 0** | Tarea nueva `mise run test:u7` |
| SEC-U7.5 | Llamadas a un proveedor, o claves leídas, durante `synthetic:generate` | **Exactamente 0** (contrato de importación y espía en la fábrica) | `mise run lint` y `mise run test:u7` |
| NFR11.10 | Valores personales sembrados que la redacción de U3 no encuentra, por tipo y por idioma | **Exactamente 0** (NFR11, dueña U3) | Tarea nueva `mise run test:u7` |
| NFR10.7 | Filas y colisiones de DS-8 que difieren de las de U2 al regenerarlas | **Exactamente 0**, y las pruebas de aislamiento de U2 siguen en verde sin cambios (NFR10, dueña U2) | `mise run test:u7` y `mise run test:u2` |
| NFR20.4 | Combinaciones de estado y aseguradora con caso sembrado en un idioma y no en el otro | **Exactamente 0** (NFR20, dueña U21) | `mise run test:u7` |

## La muestra humana

AC5.4.5 y AC5.5.6 son criterios humanos:
- Miguel revisa diez cláusulas de Stonecroft y diez de Sunmeadow, elegidas con
  una semilla registrada.
- Su veredicto queda en `app/data/sources/reviews/`, carpeta nueva que se crea
  con la generación de código, con fecha y commit.
- El generador lo copia al manifiesto.

**U7 no se cierra sin los dos veredictos.** El catálogo de unidades declara esta
revisión como dependencia humana de la unidad, y `docs/PENDIENTES-MIGUEL.md` la
lista en 1.1.

## Sources

- `../functional-design/rules.md` — BR1.1 a BR8.1.
- `../functional-design/functional-spec.md` — FD-U7-1 a FD-U7-6.
- `../../../inception/requirements-analysis/requirements.md` — FR12.2, FR12.3,
  NFR10, NFR11 y NFR20.
- `../../../inception/contract-design/contract-summary.md` — C-26.
- `../../../inception/domain-design/decisions.md` — ADR-013 y ADR-016.
- `docs/reference/estructura-poliza-iso-pap.md` — los specimens públicos de
  referencia.

## Assumptions & Open Questions

- **Los specimens los descarga Miguel**, o autoriza la descarga, antes de la
  generación de código. Mientras no estén, SEC-U7.1 queda "no medido" y la
  compuerta no pasa.
- **Una traducción no se detecta por huellas.** Ese riesgo de SEC-U7.1 lo cubre
  la muestra humana.
