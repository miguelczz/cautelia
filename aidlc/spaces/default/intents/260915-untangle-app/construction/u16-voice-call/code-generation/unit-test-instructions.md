# Instrucciones de pruebas — U16 `voice-call`

U16 es de la **rama evaluada**: realiza M13 (el reporte hablado) y M6 (la
divulgación y la redacción). Sus casos previos son las grabaciones de DS-5 en
inglés. Pero DS-5 corre **por hito** y no por entrega —las grabaciones son de
personas reales, viven fuera del repositorio y medirlas gasta—, así que lo que
sostiene la unidad en cada entrega es su rama determinista, capa por capa, con
dobles.

Estrategia `Standard`: de cinco a ocho pruebas por componente, unitarias más
integración en las fronteras.

## Cómo correr solo lo de U16

| Qué | Comando | Lo que corre por debajo |
| --- | --- | --- |
| Pruebas de la unidad | `mise run test:u16` (tarea nueva de la tanda 6) | `pytest app/backend/tests/unit/voice app/backend/tests/integration/voice` más las pruebas de la consola en Vitest |
| La llamada completa contra los proveedores reales, a mano y por hito | `mise run voice:call-live` (tarea nueva de la tanda 6) | Inyecta una grabación por el transporte, mide los cuatro eventos de latencia y publica las dos variantes del fin del habla |

`mise run test:u16` **no abre ninguna conexión de red**: la guardia que U15 dejó
puesta lo comprueba. `voice:call-live` sí llama, gasta unos pocos segundos del
saldo, no corre en GitHub Actions y **no corre sin que Miguel lo diga**.

## El orden de las capas

| Capa | Qué se prueba | En qué tanda |
| --- | --- | --- |
| Modelo de datos y conducta de la base | `call_session`, su RLS y su llave compuesta | 1 |
| Acceso a datos | `voice/session.py`: abrir, buscar por navegador, atar caso, terminar | 1 |
| Lógica de negocio | Detección de turno, silencios, interrupción, deletreo, retoma | 2, 3, 4 |
| API | Las tres rutas de C-08 y el socket | 5 |
| Interfaz | La consola, los dos `AudioWorklet` y el reductor de cuadros | 6 |

## Los dobles, que es donde esta unidad se puede engañar sola

La forma de defecto que más ha costado en este proyecto es **un doble más
permisivo que la pieza real**: el chat estuvo sin poder atender a nadie con 2.363
pruebas en verde porque sus dobles aceptaban un turno sin caso donde
`handle_turn` lo rechaza. Esta unidad tiene dos dobles grandes y los dos son
fáciles de escribir mal.

1. **Los dobles heredan de los `Protocol` de C-16** (`SpeechToText`,
   `TextToSpeech`), para que el comprobador de tipos los compare con la pieza
   real y no con lo que la prueba necesitaba.
2. **El reconocedor simulado entrega un guion de tiempos**: parciales, finales y
   silencios con sus marcas, no un texto de una vez. Un doble que devuelve el
   transcrito completo de golpe **no puede probar la detección de turno**, que es
   media unidad.
3. **El reconocedor simulado imita lo incómodo del real**: confianza nula cuando
   no la manda, parciales que se corrigen, y una transcripción vacía cuando no se
   entendió. Si el doble siempre trae confianza, BR3.4 nunca se prueba.
4. **La síntesis simulada tarda y se puede interrumpir**: entrega el audio en
   trozos con un reloj inyectado, porque medir una parada contra una síntesis
   instantánea no mide nada.
5. **Al menos una prueba recorre la costura con la pieza real**: la del
   transporte, contra el adaptador de verdad con su respuesta grabada, que es lo
   que U15 ya dejó montado.

## Las tres compuertas duras, y cómo se prueban

| Regla | Prueba |
| --- | --- |
| BR2.1 — nada se pregunta antes de la divulgación | Se entrega un turno con la apertura a medias y se comprueba que se rechaza |
| BR6.3 — la póliza de ejemplo no abre casos ajenos (AC1.27.3) | Se siembra un caso de **otro** `visitor_key_digest` con la misma póliza; la retoma ni lo ofrece ni lo menciona |
| BR7.1 — el audio no se persiste | Prueba de conducta con una llamada completa, más un chequeo del árbol que busca escrituras a disco y acumuladores sin techo en `untangle/voice/` |

Ninguna se cierra con `N/A` y ninguna se relaja para que un paso pase.

## Pruebas de seguridad y de rendimiento, con independencia de la estrategia

Las exige `team.md` aparte del volumen de la estrategia.

- **Seguridad:** aislamiento (SEC-U16.3), redacción en cada salida del socket
  incluidos los parciales (SEC-U16.2), las cuatro formas de token malo
  (SEC-U16.4), y el borrado nocturno (SEC-U16.7).
- **Rendimiento:** PERF-U16.1 a PERF-U16.4, cronometrados con reloj inyectado.
  NFR1, NFR2 y NFR3 son de hito y hasta medirse se reportan **no medidas**, nunca
  en verde.

## El reloj se inyecta, siempre

Toda esta unidad son temporizadores: fin del habla, silencios, parada,
vencimiento del token, ventana de retoma. Ninguna prueba espera tiempo real. El
reloj entra como dependencia, igual que en el resto del proyecto, y una prueba
que duerma es una prueba que un día falla en la tubería por estar la máquina
ocupada.

## Cobertura

**80 % o más agregado** con `mise run cov`, sin exclusiones nuevas. Los dos
`AudioWorklet` son código de navegador que Vitest no ejecuta con audio real: su
lógica pura —la conversión a PCM de 16 bits y el vaciado de la cola— se extrae a
funciones probables, y solo el envoltorio del nodo queda sin cubrir.

## Datos de prueba

Sintéticos, cortos, en inglés en esta unidad (el español es de U18). Las placas y
los números de póliza de las pruebas de deletreo salen de las fixtures que ya
existen; ninguna prueba inventa un dato que parezca real.

## Sources

- `code-generation-plan.md` — las seis tandas
- `../functional-design/rules.md` — las 38 reglas
- `../nfr-requirements/` — los objetivos medibles de esta unidad
- `docs/reference/como-se-revisa-el-codigo.md` — las catorce formas de prueba que no prueba
- `.claude/skills/revisar-tanda/SKILL.md` — el procedimiento de revisión

## Assumptions & Open Questions

None.
