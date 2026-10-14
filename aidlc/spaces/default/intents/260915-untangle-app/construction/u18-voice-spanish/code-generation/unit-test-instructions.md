# Instrucciones de pruebas — U18 `voice-spanish`

U18 es de la **rama evaluada**: realiza M15 (la paridad entre idiomas) y M6 (la
divulgación y la redacción, en el segundo idioma). Sus casos previos son las
grabaciones de DS-5 en español con al menos tres voces paisas.

**DS-5 en español no existe todavía** —llega en la semana 9, con voluntarios y su
consentimiento— así que lo que sostiene la unidad en cada entrega es su rama
determinista con los dobles de U16, y lo que se mide por hito se declara **no
medido** hasta entonces. Nunca se rellena con la cifra del inglés.

Estrategia `Standard`: de cinco a ocho pruebas por componente, unitarias más
integración en las fronteras.

## Cómo correr solo lo de U18

| Qué | Comando | Lo que corre por debajo |
| --- | --- | --- |
| Pruebas de la unidad | `mise run test:u18` (tarea nueva de la tanda 3) | `pytest app/backend/tests/unit/voice app/backend/tests/integration/u18` |
| El recorrido en español contra los proveedores reales, a mano y por hito | `mise run voice:call-live` (ya existe, de U16) | Inyecta una grabación en español por el transporte |

`mise run test:u18` **no abre ninguna conexión de red**. `voice:call-live` sí
llama, gasta saldo, no corre en GitHub Actions y **no corre sin que Miguel lo
diga**.

## El orden de las capas

| Capa | Qué se prueba | En qué tanda |
| --- | --- | --- |
| Lógica de negocio | El detector movido, sin cambiar una aserción | 1 |
| Lógica de negocio | La petición, la detección, la escalera del tercer idioma | 2 |
| Acceso a datos | Que el cambio escriba la llamada y **no** el caso | 2 |
| API | El cuerpo de abrir con `language` opcional | 3 |
| Interfaz | Que la consola omita el idioma cuando nadie lo eligió | 3 |
| Contenido | El registro en español sobre el catálogo | 3 |

## Lo que esta unidad se puede hacer mal, y es específico

La forma de defecto que más se le parece **no es el doble permisivo** —esos son de
U16 y ya están escritos— sino **la prueba que afirma el mecanismo en vez de la
regla**. Es la que U16 encontró al cerrar: una prueba decía "el bloque siguiente
no es `safety`" cuando la regla era "no se le vuelve a preguntar", y pasaba en
verde con el defecto puesto.

Casi todas las pruebas de la tanda 3 comprueban que **algo sigue comportándose
igual en el otro idioma**, y "igual" es fácil de escribir de manera que pase
siempre. Tres formas de que eso salga mal aquí:

1. **Comparar contra sí mismo.** Una prueba que corra el recorrido en español y
   afirme que la respuesta está en español, usando el mismo detector que el código
   usó para elegirla, no comprueba nada: comprueba que el detector es consistente
   consigo mismo. Lo que hay que afirmar es la **frase del catálogo** que toca.
2. **Afirmar que "no falla".** Una prueba del recorrido en español que solo mire
   que no hay excepción pasa con la agente contestando en inglés.
3. **Contar en vez de mirar.** "El caso tiene siete campos" pasa igual con los
   siete campos escritos en el idioma equivocado. Lo que dice si la paridad se
   cumple es qué frase se dijo en cada paso, no cuántas.

## Los dos números que no se tocan

El detector sube de `chat/` con **sus dos umbrales tal cual**: 0,75 para el de dos
idiomas y 0,5 para el amplio, más el piso de cuatro palabras. No son elecciones:
son medidas de U13 —"Bom dia, preciso reportar um acidente" da 0,726 en portugués;
"Marcela Rios" da 0,168— y la tanda 1 es un movimiento, no un ajuste.

Si alguna prueba de U13 hay que tocarla al mover el módulo, **es señal de que el
movimiento cambió algo** y hay que mirar qué, no cambiar la aserción.

## Lo que corre por hito y no por entrega

Las tres metas de tiempo en español (NFR1, NFR2, NFR3) y el eje de idioma mixto de
AC1.32.3. Necesitan las grabaciones. Hasta que existan, el reporte dice **no
medida** con su causa, que es lo que la práctica del equipo exige: una compuerta
que no se pudo ejecutar se declara, jamás se omite.

## Sources

- `code-generation-plan.md` — las tres tandas
- `../functional-design/rules.md` — las veintiuna reglas
- `aidlc/spaces/default/memory/team.md` — la postura de pruebas afirmada
- `../../u16-voice-call/code-generation/code-summary.md` — lo que U18 no vuelve a probar

## Assumptions & Open Questions

None.
