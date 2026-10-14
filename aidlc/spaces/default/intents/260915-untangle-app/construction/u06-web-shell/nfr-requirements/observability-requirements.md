# Requisitos de observabilidad — U6 `web-shell`

Tres cosas de U6 se tienen que poder ver sin abrir el código: si el proceso está
listo y qué superficies están de pie, cuántas sesiones llegan a cada hito, y cuánto
tarda y qué encuentra el arnés en cada entrega. Y una que se tiene que poder
**no** ver: nada de lo que U6 registra apunta a una persona.

**`mise run test:u6`, `mise run a11y` y `mise run activation:report` no existen
todavía**: los crea la generación de código de esta unidad.

## Objetivos medibles

| ID | Qué se observa | Valor esperado | Comando |
| --- | --- | --- | --- |
| OBS-U6.1 | La salud de listo informa versión, estado de la base, aseguradoras cargadas y cada superficie montada con su resultado y su duración | **Todas** las superficies montadas, **ninguna** inventada | `mise run test:u6` |
| OBS-U6.2 | Toda respuesta lleva el identificador de traza de C-01 | **100 %** de las respuestas recorridas | `mise run test:u6` |
| OBS-U6.3 | Conteo de activación por día, aseguradora e hito, legible sin consultar la base a mano | **Una tabla por día**, sin identificadores de sesión | `mise run activation:report` |
| OBS-U6.4 | Una falla al registrar un hito deja un evento en la traza con el hito y el tipo de error de la taxonomía cerrada | **Siempre** | `mise run test:u6` |
| OBS-U6.5 | El reporte del arnés nombra pantalla, idioma, modo, regla y elemento de cada hallazgo, y la duración del paso | **Siempre** | `mise run a11y` |
| OBS-U6.6 | Datos personales o identificadores del navegador en logs, trazas y reportes de U6 | **Exactamente 0** (NFR11, dueña U3) | `mise run test:u6` y el segundo detector de U21 cuando exista |

## Qué no se registra, y por qué

- **Cada chequeo de salud exitoso** no deja log: son 8.640 al mes y no dicen nada
  que el chequeo mismo no guarde. Sí deja log una salud que responde 503 o una
  sonda `down`, con la superficie y la duración.
- **Los errores del navegador** no se envían al servidor. La interfaz los deja en
  la consola del navegador (BR3.2). Enviarlos exigiría una ruta nueva que recibe
  texto de visitantes, con su redacción y su límite, para una demo donde quien
  depura es Miguel con el navegador abierto.
- **La sesión** no se registra: la activación guarda el conteo, y el avance que
  permite contarlo una vez se borra cada noche (BR8.2).

## Alertas

U6 no emite alertas propias. La alerta de dos chequeos fallidos seguidos y su
canal son del intent `infra` (PA-10). Lo que U6 garantiza es que el chequeo
tenga algo inequívoco que mirar: 503 cuando el proceso no puede atender, 200
con la superficie `down` cuando solo una parte falla (NFR16.2).

## Sources

- `../functional-design/functional-spec.md` — F7 y F10.
- `../functional-design/rules.md` — BR3.2, BR5.3, BR6.4, BR8.2, BR8.3 y BR8.5.
- `../../../inception/contract-design/contract-summary.md` — C-01 (correlación) y
  C-02.
- `aidlc/spaces/default/memory/team.md` — convención 8d (rastro doble de toda
  falla).

## Assumptions & Open Questions

- **El canal y el umbral de las alertas** quedan en el intent `infra`; si ese
  intent decide alertar por superficie, la salud ya trae el dato.
