# Datos de ejemplo simples y conversaciones sin etiquetas (2026-10-30)

Pedido de Miguel el 2026-10-30, al ver la llamada de Autos Poblado y un caso de
ejemplo en Casos:

> «es complicado para que las personas lo usen, deberia ser algo mas simple tanto
> los numeros como los nombres […] deberian quedar algo como Marco, poliza 23 y
> los mismo para los casos, esta bien que tenga iniciales pero deberian ser la de
> la empresa, por ejemplo AP-29 con un contador […] quite esa censura que solo hace
> que se complique todo»

## Las peticiones

| # | Pedido | Hoy | Queda |
| --- | --- | --- | --- |
| 1 | Ninguna etiqueta en la conversación de un caso de ejemplo | «Soy [NOMBRE 1], póliza [PÓLIZA 1]» en Casos | La conversación tal como se escribió |
| 2 | Número de caso con las iniciales de la empresa y un contador | `SUN-063911` (letras internas, seis cifras al azar) | `AP-29`: iniciales de la aseguradora y un contador por aseguradora |
| 3 | Pólizas fáciles de decir | `POL-200117`, seis cifras | Un número de dos cifras: «póliza 23» |
| 4 | Nombres fáciles de decir | «Marco Parker», «Natalia Henao Rendón» | Solo el nombre: «Marco», «Natalia» |

## Valores elegidos

- **Pólizas por decenas, una decena por aseguradora**, para que el número diga
  de quién es: Seguros Aburrá 11 a 16, Autos Poblado 21 a 26, Agencia Castilla
  31 a 36. La póliza que comparten a propósito Seguros Aburrá y Autos Poblado
  (la prueba de que un inquilino no ve la del otro) pasa a ser la 50 en las dos.
- **Prefijos de caso**: Seguros Aburrá `SA`, Autos Poblado `AP`, Agencia
  Castilla `AC`. Distintos entre sí, como exige el arranque.
- **El contador** empieza en 1 por aseguradora. Antes el número era al azar
  para no revelar cuántos casos hay; ese dato no importa en una demostración, y
  el número nunca fue credencial: el acceso lo da el navegador o el enlace
  firmado, así que adivinar `AP-30` no abre nada.

## Por qué la base sigue guardando tapado

La regla de redactar antes de guardar existe porque el chat público recibe lo
que escriba cualquiera, y eso puede ser real. No se toca. Lo que cambia es lo
que se pinta:

- **Casos de ejemplo**: su conversación es sintética y está en el repositorio
  (`app/data/tenants/*/cases`). La pantalla la lee de ahí, sin etiquetas.
- **El caso propio**: ya se repone desde lo que este navegador escribió (chat,
  llamada, «Ver mi caso», Casos, vista de ajustador).
- **El caso de otro visitante**, visto con credenciales de la aseguradora: sigue
  con etiquetas. Es el único lugar donde deben verse.

## Tandas

1. Conversación de los casos de ejemplo sin etiquetas, y recorrido de todas las
   pantallas buscando `[NOMBRE`, `[PÓLIZA`, `[PLACA`.
2. Número de caso: prefijo de la empresa y contador.
3. Pólizas y titulares: generador de datos sembrado, corpus, casos de ejemplo,
   golden sets, reconocedores de la redacción y del número dictado, textos de
   ayuda («¿Qué póliza digo?»).

Cada tanda se sube a GitHub cuando su revisión queda en verde; nada se publica a
producción hasta que Miguel lo pruebe en la demo local.

## Estado

| Tanda | Estado |
| --- | --- |
| 1 | Hecha en la rama `datos-de-ejemplo-simples` (sin subir) |
| 2 | Esperando que Miguel confirme los valores elegidos |
| 3 | Esperando que Miguel confirme los valores elegidos |

## Excepción de gasto: servidor siempre encendido (2026-10-30)

Miguel encendió una instancia permanente del servidor (`--min-instances=1`,
revisión `cautelia-00054-z2c`) después de ver que cada arranque en frío tardaba
unos 40 segundos. Cuesta unos 45–50 USD al mes a precio de lista (estimación, no
cotización), por encima del tope de 40 USD en 90 días. **Es una excepción escrita
a ese tope**: lo cubre el crédito de prueba de Google, que vence el 2027-01-05 y no
es dinero real. Antes de esa fecha se vuelve a `--min-instances=0` o se cambia de
cuenta. Vuelta atrás:

    gcloud run services update cautelia --region us-east1 --project vocal-tempo-510815-c2 --min-instances=0
