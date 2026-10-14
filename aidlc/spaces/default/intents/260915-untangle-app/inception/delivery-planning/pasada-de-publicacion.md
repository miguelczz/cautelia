# Pasada de publicación

La lista única de lo que se construye **antes de abrir la demo al público** y no
antes (DP-14 de `bolt-plan.md`, decisión de Miguel del 2026-09-21). Existe para
que nada de lo diferido se pierda: cada entrada lleva su identificador, la unidad
de la que sale y por qué es de publicación.

**Regla que no cambia:** nada se publica —ni el chat, ni la bandeja, ni la voz—
hasta que esta lista esté cerrada. Lo prohíben dos reglas de `project.md`: no
publicar una superficie que invoque al modelo sin límites por sesión, origen y
día probados también en el proveedor, y no publicar el enlace de la voz sin su
reconciliación de alcance y de tope.

**Lo que nunca entra aquí:** una compuerta dura de lo que ya se construyó
(aislamiento entre aseguradoras, datos personales, promesas de cobertura o de
culpa, citas inexistentes), las pruebas, el piso de cobertura del 80 % y
`scripts/verify.sh`.

## Unidades completas

| Unidad | Qué es | Por qué es de publicación |
| --- | --- | --- |
| U17 `voice-public-link` | El enlace público de la voz con límite por visitante y por día | Solo existe para visitantes públicos |
| U20 `demo-operations` | Reinicio nocturno, aprovisionamiento y muestreo del chat en vivo | Los datos de visitantes reales aparecen al publicar |
| U22 `public-evidence` | Panel de cifras y panel de gasto públicos | Muestran la demo a quien la visita |

## Criterios diferidos de otras unidades

Cada unidad agrega aquí los suyos al cerrar su diseño funcional, y en su
`traceability.json` los marca `Deferred` con destino a esta pasada.

| Identificador | Unidad | Qué queda para la pasada |
| --- | --- | --- |
| AC4.15.4 (mitad en vivo) y NFR12.3 | U10 `compliance` | Correr DS-6 contra el despliegue público en cada hito. La mitad que corre en cada entrega por GitHub Actions es del núcleo y se construye en U10 |
| AC5.6.4 | U7 `synthetic-data` | Que el reinicio nocturno borre solo los casos de visitantes y devuelva los sembrados a su estado sembrado. Es conducta de U20. U7 ya entrega los sembrados con el origen `generator`, que el borrado de U4 no toca |
| Registro de gasto permanente de la voz | U15 `speech-providers` | Una base permanente con la fila de `budget_window` sembrada con el gasto real acumulado desde el 2026-09-16, que Miguel lee en las consolas de Deepgram y Cartesia. Hasta entonces, `voice:contract-live` y `voice:say` corren con un registro temporal que empieza en cero, y el corte real lo hace el proveedor (saldo prepagado sin recarga, cupo gratuito mensual). El techo del aplicativo está construido y probado; lo que se difiere es su registro permanente, porque solo protege al público |
| NFR1, NFR2 y NFR3 (medición en vivo) | U16 `voice-call` | Medir las tres metas de tiempo contra los proveedores de verdad y el despliegue, por hito. Lo que esta unidad vigila en cada entrega es su propia contribución --PERF-U16.1, medida en 3,9 ms sobre un presupuesto de 60-- y los dos presupuestos de sus rutas. La meta de punta a punta se la comen el reconocedor, el modelo y la síntesis, que esta unidad no escribe |
| Corredor del conjunto DS-5 | U16 `voice-call` | `mise run voice:call-live` corre **una** grabación por el transporte real. El corredor de las veinte llega con las grabaciones, que son de personas reales, viven fuera del repositorio y se graban en las semanas 6 y 9: hoy sería una pieza sin datos y sin llamador |
| Enlace a la corrida de cada cifra (AC4.16.2, mitad) | U22 `public-evidence` | Cada cifra del panel lleva su fecha y su commit; el **enlace** a la corrida viaja en nulo, porque el repositorio es privado y no hay adónde llevar. Un enlace a algo que no existe es peor que ninguno (P7). Se llena en la semana 12, cuando se decide publicar el repositorio (D-017), y el panel ya tiene el campo y quien lo construye |
| Latencia del chat en el panel (AC4.16.3, mitad) | U22 `public-evidence` | El panel nombra los dos extremos --envío y primera palabra-- y declara la cifra "no medida" con la causa «la fuente todavía no existe»: el chat no emite hoy ninguno de los dos eventos. Construirlos no es de esta unidad |
| Los tres enlaces del párrafo del README (AC4.1.1, mitad) | U22 `public-evidence` | El párrafo de arriba tiene que enlazar el chat en vivo, la consola de voz y el vídeo. Ninguno de los tres está publicado, así que el párrafo dice que sus enlaces entran al cerrar esta pasada y no se inventa ninguno (P7). Lo que la unidad sí entrega es el párrafo, los ocho encabezados en el orden que fija AC4.1.1 y las dos secciones que se regeneran; el enlace es un dato que solo existe cuando hay adónde llevar |
| **`quote_enabled` de Sunmeadow, bloqueante** | U19 `quote` | La captura de la solicitud está construida y probada, pero **nadie la termina**: el cableado del grafo de fondo y la bandeja del suscriptor (tanda 2) no existen, así que `compose_eligibility_reply` está escrita y su único consumidor es el conductor de evaluaciones. Hoy no se nota porque nada está publicado; el día que se publique, un visitante de Sunmeadow contaría diecisiete campos y no recibiría respuesta nunca. **`quote_enabled` no puede estar en `true` al publicar** sin la tanda 2 y el cableado |
| **El cupo mensual de la voz principal, bloqueante** | U17 `voice-public-link` | El plan gratuito de Cartesia da 20.000 caracteres al mes y `providers.yaml` reserva 1.300 por llamada: son unas **quince llamadas al mes**, que es lo que `site_daily_cap` admite en **un día**. El cupo del día se deriva del presupuesto en dólares y de los días que faltan (BR5.6), y ese cálculo no mira un cupo mensual de caracteres, así que la voz principal se agotaría mucho antes que el presupuesto y la consola diría que queda presupuesto mientras Cartesia responde 402. **No se publica el enlace de voz sin resolverlo**: o la voz de respaldo (Aura-2, con saldo prepagado) sirve el enlace público y Catalina se reserva para el vídeo y la escucha, o el cupo mensual entra al cálculo del cupo del día. Leído en la consola el 2026-10-02 |
| Carriles diarios de la llamada | U16 `voice-call` y U17 `voice-public-link` | `GET /voice/availability` sirve `calls_per_visitor_day` y `calls_per_site_day` en **nulo** a propósito: hoy no los aplica nadie, y servir un número que nada hace cumplir es la promesa que P7 prohíbe. U17 los llena y los hace cumplir |

## El último paso del despliegue

**`mise run demo:reset` se corre al final de cada despliegue**, y no es una
excepción a ninguna regla: es la consecuencia de una.

Sin ningún reinicio exitoso conocido, las superficies públicas dejan de aceptar
casos nuevos (BR3.2 de U20). Eso es correcto y es a propósito: tratar «ninguna
corrida» como abierto sería indistinguible de «el reinicio lleva tres días sin
correr», que es justo el caso que la regla existe para atrapar. La consecuencia es
que un despliegue nuevo **no acepta un solo caso** hasta que haya corrido un
reinicio.

Sobre una base recién creada no hay nada que borrar: la corrida sale `succeeded`
en milisegundos y deja el reloj de las 24 horas en marcha. En una base con datos,
borra lo de antes del despliegue, que es lo que hay que hacer igual.

Su código de salida es lo único que mira quien lo dispara: distinto de cero cuando
la corrida no terminó limpia. Un despliegue que termine con el reinicio en rojo
deja la demo cerrada y la alerta ya salió con el identificador de la corrida.

## Antes de la pasada, fuera de este intent

El hospedaje, el chequeo periódico con su alerta y el **disparador nocturno** son
del intent `infra` (OQ4 y PA-10), igual que antes de esta decisión. Lo que U20
entrega es el comando y su registro; lo que `infra` pone es la hora a la que se
llama y el último paso del despliegue que lo invoca.
