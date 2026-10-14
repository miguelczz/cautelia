# Requisitos de seguridad — U16 `voice-call`

Una superficie pública nueva por la que entra **voz de personas reales**, aunque
el corpus sea sintético. Es la entrada más cruda que tiene el aplicativo: quien
habla no ve una pantalla que le recuerde que no dé datos reales, y hablar es más
rápido que pensar.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| SEC-U16.1 | Audio persistido en cualquier punto del camino | **Cero**: ni archivo, ni campo, ni búfer sin techo | Tarea nueva `mise run test:u16` más un chequeo de árbol sobre el módulo |
| SEC-U16.2 | Transcripción que sale por el socket sin redactar, parciales incluidos | **Cero** | Tarea nueva `mise run test:u16` con casos sembrados por tipo de entidad |
| SEC-U16.3 | Un caso de otro navegador ofrecido o mencionado al identificarse con la póliza de ejemplo (AC1.27.3) | **Cero** `[bloquea]` | Tarea nueva `mise run test:u16`; también contra el despliegue vivo por hito, con RT-4 |
| SEC-U16.4 | Un socket admitido sin cuadro de autenticación válido | **Cero** | Tarea nueva `mise run test:u16` con las cuatro formas de token malo |
| SEC-U16.5 | Turnos atendidos antes de que la divulgación esté registrada (AC1.22.1) | **Cero** `[bloquea]` | Tarea nueva `mise run test:u16` |
| SEC-U16.6 | Texto de origen externo en posición de instrucción del prompt | **Cero** | Heredado de U11 y U12; la voz no arma prompts |
| SEC-U16.7 | Filas de llamada que sobreviven al borrado nocturno | **Cero** | Tarea nueva `mise run test:u16`, prueba del contrato de borrado de U2 (UG-3) |

## El audio no se guarda, y eso se comprueba mirando

SEC-U16.1 es la más fácil de romper sin querer. La forma en que se rompe es
siempre la misma: alguien acumula el audio de un turno "para depurar", o guarda
el último segundo "por si hace falta reintentar". Por eso la comprobación no es
solo una prueba de conducta:

- `CallSession` **no tiene campo de audio** (entidad), así que no hay dónde
  ponerlo sin una migración que alguien tendría que escribir;
- el chequeo de árbol busca en `untangle/voice/` escrituras a disco y
  acumuladores de `bytes` sin límite declarado;
- la prueba corre una llamada completa y comprueba que la memoria del trozo no
  crece con la duración.

## Lo que entra por voz es dato personal potencialmente real

La regla del proyecto ya lo dice para toda superficie pública, y aquí toma dos
formas concretas:

1. **La redacción va antes de persistir y en cada punto de salida**, incluidos
   los parciales que pinta la consola (BR7.2). Un teléfono redactado en el final
   pero visible medio segundo en un parcial ya salió a la pantalla —y en una
   demostración que se graba, a la grabación.
2. **La apertura lo dice en voz alta** antes de cualquier pregunta: que es una
   inteligencia artificial, que es una demostración con pólizas de ejemplo y que
   la llamada queda transcrita. Es la compuerta BR2.1.

## El aislamiento, en su forma hablada

SEC-U16.3 es el criterio `[bloquea]` AC1.27.3 y merece decirse con sus
consecuencias: la póliza de ejemplo es pública y la comparten todos los
visitantes de una aseguradora. Si la retoma buscara por póliza, cualquiera que
dijera ese número en voz alta abriría el caso de otra persona —su nombre, su
dirección, lo que contó del accidente.

Por eso la búsqueda es **solo** por el resumen de la clave del visitante (BR6.3),
la misma que usa el chat, y la prueba planta un caso de otro navegador con la
misma póliza y comprueba que ni se ofrece ni se menciona.

Por hito, el escenario RT-4 se corre además contra el despliegue vivo, porque las
fallas de aislamiento son tan a menudo configuración del despliegue como código.

## El token del socket

No es una credencial del visitante: a quién pertenece la conexión ya lo dice la
galleta en el apretón de manos. El token ata el socket a **una** llamada, vive
poco, viaja en el primer cuadro y nunca en la URL (BR1.4).

Las cuatro formas de token malo que prueba SEC-U16.4: ausente, vencido, de otra
llamada y alterado. Las cuatro se responden igual, sin decir cuál fue (BR1.5):
distinguirlas le diría a quien prueba cuál acertó a medias.

## Claves de proveedor

Ninguna llega al navegador, y esa es la razón de que exista el paso de crear
sesión en C-08. Las de voz son `UNTANGLE_VOICE_DEEPGRAM_API_KEY` y
`UNTANGLE_VOICE_CARTESIA_API_KEY`, ya existentes desde U15, del uso `voice`, y
las lee solo `Settings`. Esta unidad no añade ninguna.

## Lo que no es de esta unidad

- **Los límites por visitante, por sitio y por día** y el techo de gasto: U17.
  Hasta entonces la voz se sirve con lo que declare la configuración de la
  aseguradora, y el enlace **no se publica**: la prohibición de publicar una
  superficie que invoca al modelo sin límites probados sigue en pie.
- **El borrado nocturno en sí**: es de U2 y de U20; esta unidad implementa su
  contrato y lo prueba.
