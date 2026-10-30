# Datos de ejemplo simples y conversaciones sin etiquetas (2026-10-30)

Pedido de Miguel el 2026-10-30, al ver la llamada de Autos Poblado y un caso de
ejemplo en Casos:

> «es complicado para que las personas lo usen, deberia ser algo mas simple tanto
> los numeros como los nombres […] deberian quedar algo como Marco, poliza 23 y
> los mismo para los casos, esta bien que tenga iniciales pero deberian ser la de
> la empresa, por ejemplo AP-29 con un contador […] quite esa censura que solo hace
> que se complique todo»

## Lo que queda (respuestas de Miguel del 2026-10-30)

| # | Pedido | Hoy | Queda |
| --- | --- | --- | --- |
| 1 | Ninguna etiqueta en la conversación | «Soy [NOMBRE 1], póliza [PÓLIZA 1]» | La conversación se **guarda** tal como se escribió («nadie va a poner ningún supuesto dato real, quita eso») |
| 2 | Número de caso con las iniciales de la empresa y un contador | `SUN-063911` | `SA-1`, `AP-29`, `AC-7` |
| 3 | Pólizas fáciles de decir, conservando `POL` | `POL-200117` | `POL-23` |
| 4 | Nombres cómodos para cualquiera, según el idioma | «Natalia Henao Rendón» | Nombre y un apellido: «Natalia Henao» en español, «Marco Parker» en inglés |

## Valores elegidos

- **Pólizas por decenas, una decena por aseguradora** (Miguel lo dejó a criterio),
  para que el número diga de quién es: Seguros Aburrá `POL-11` a `POL-16`, Autos
  Poblado `POL-21` a `POL-26`, Agencia Castilla `POL-31` a `POL-36`. La de ejemplo
  es la primera de cada decena. La póliza que comparten a propósito Seguros Aburrá
  y Autos Poblado (la prueba de que un inquilino no ve la del otro) pasa a ser
  `POL-50` en las dos.
- **Nombres**: el español pierde el segundo apellido; el inglés ya tenía nombre y
  apellido.
- **Prefijos de caso**: Seguros Aburrá `SA`, Autos Poblado `AP`, Agencia Castilla
  `AC`. **El contador** empieza en 1 por aseguradora y nunca repite un número,
  ni después del borrado nocturno. El número nunca fue credencial: el acceso lo
  da el navegador o el enlace firmado, así que adivinar `AP-30` no abre nada.
- **Al publicar**, los casos que ya existen cambian de número una sola vez.

## La redacción, después del cambio

- **Se quita** de la conversación guardada del caso: todas las pantallas la
  muestran como se escribió.
- **Se conserva** en los logs, las trazas, las exportaciones y el reporte de
  evaluaciones. Ahí es donde la miden las compuertas duras y los golden sets.

## Tandas

1. Conversación de los casos de ejemplo sin etiquetas en la vista del caso.
2. Número de caso, pólizas y titulares: configuración, generador de datos
   sembrado, corpus, casos de ejemplo, golden sets, reconocedores de la redacción
   y del número dictado, migración que renumera los casos existentes.
3. La conversación se guarda sin redactar; recorrido de todas las pantallas
   buscando `[NOMBRE`, `[PÓLIZA`, `[PLACA`.

Cada tanda se sube a GitHub cuando su revisión queda en verde; nada se publica a
producción hasta que Miguel lo pruebe en la demo local.

## Estado

| Tanda | Estado |
| --- | --- |
| 1 | Hecha en la rama `datos-de-ejemplo-simples` (sin subir) |
| 2 | En curso |
| 3 | Pendiente |

## Servidor siempre encendido (2026-10-30)

Miguel encendió una instancia permanente del servidor (`--min-instances=1`,
revisión `cautelia-00054-z2c`) después de ver que cada arranque en frío tardaba
unos 40 segundos. Cuesta unos 45–50 USD al mes a precio de lista (estimación, no
cotización). **No cuenta para el tope de 40 USD** (decisión de Miguel): lo cubre el
crédito de prueba de Google, que vence el 2027-01-05 y no es dinero suyo. Antes de esa fecha se vuelve a `--min-instances=0` o se cambia de
cuenta. Vuelta atrás:

    gcloud run services update cautelia --region us-east1 --project vocal-tempo-510815-c2 --min-instances=0
