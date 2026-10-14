# Hallazgos de la tanda 2 — U20 `demo-operations`

Las dos operaciones de verdad. Escrita en la sesión principal el 2026-10-02, porque
el guardián del motor no deja delegar código de una unidad que no es la que él cree
activa (PENDIENTES 1.13).

**Reglas que cierra:** BR1.1, BR1.2, BR1.3, BR1.4, BR2.1, BR2.2, BR2.3, BR2.5,
BR2.6, BR3.1 (contra la base), BR3.2 y BR3.3. Con esto la unidad queda cerrada, y
con ella la última tanda de unidad del proyecto.

También cierra **AC5.6.4**, que estaba diferido aquí desde U7.

## Lo que el cableado dejó al descubierto

Cinco cosas, y **cuatro de ellas eran reglas que el proyecto creía cumplidas**.

### 1. El noveno purgador no existía, y ninguna comprobación podía echarlo de menos

BR2.1 nombra el backend de trazas **aparte** —"tampoco en el backend de trazas"— y
la razón por la que lo nombra aparte es exactamente la razón por la que faltaba: la
comprobación que protege el registro de purgadores le pregunta al **catálogo de la
base** qué tablas llevan la marca de dato de visitante, y el backend no está en la
base. Un registro sin ese purgador pasaba en verde.

Las cinco tablas de trazas sí estaban cubiertas: `trace_summary` cuelga del caso en
cascada y la borra el purgador de U4. Lo que faltaba era lo que **salió** del
proceso.

El purgador nuevo (`telemetry/traces/purge.py`) tiene tres ramas y las tres están
declaradas, porque la diferencia entre ellas es la que el proyecto persigue en
todas partes:

| Transporte | Qué hace | Por qué |
| --- | --- | --- |
| Archivo de la corrida | Reescribe el archivo dejando solo los lotes posteriores al corte | Es lo que hay cuando no hay destino declarado |
| Destino declarado sin exportador | `deleted=0, kept=0` | No salió nada, y es **comprobable**: ese transporte levanta en cada envío |
| Cualquier otro | **Levanta** | La corrida sale `partial` con su alerta, en vez de declarar limpia una retención que nadie acotó |

Lo que este purgador no alcanza queda dicho en su encabezado: los tramos acumulados
en el registrador del proceso. Son del proceso que los acumuló, el reinicio corre en
otro, y la cola es acotada —un `deque` con tope— así que mueren con él.

### 2. BR2.5 no se podía cumplir, y por dos razones a la vez

«Ningún número de caso y ningún enlace firmado se repite después del reinicio.»

- **No había memoria.** El número se acuña al azar en un espacio de un millón por
  aseguradora y se comprobaba contra **los casos que existen**; el reinicio borra
  los del visitante, así que a la mañana siguiente todos los números de anoche
  volvían a estar libres.
- **Y la comprobación no podía coincidir.** El repositorio devolvía la columna
  entera —`STO-123456`— y el acuñador comparaba el serial —`123456`—, así que
  `serial not in taken` era verdad **siempre**. Las pruebas del acuñador le pasaban
  seriales a mano y pasaban; las del repositorio comprobaban que devolvía los
  números y pasaban. La frontera no la cruzaba ninguna.

Es la **forma 15** del catálogo, nueva: *la comprobación que no puede coincidir*.

El arreglo es un libro de seriales emitidos que **sobrevive al reinicio**, y el
nombre de la función dice ahora la forma del dato (`issued_serials`) para que nadie
vuelva a cruzar esa frontera sin verlo.

El enlace firmado no necesitaba nada: su fila se va con el reinicio y su secreto son
32 bytes al azar. Lo que faltaba era la prueba de que un enlace de anoche recibe
**el mismo rechazo** que uno inventado.

### 3. La cola de eventos estaba atada a lo que el reinicio se lleva

BR2.6 pide dos cosas: que la conversación viva reciba el aviso y que su mensaje
siguiente abra un caso nuevo **sin error**. Lo segundo no se cumplía, y el aviso no
era lo que faltaba.

La cola de eventos del chat se guardaba **por conversación**. El flujo lo abre la
pestaña y vive mientras esté abierta; la conversación se la lleva el reinicio. Así
que: el reinicio borraba la conversación, el mensaje siguiente abría una nueva,
buscaba su cola, no la encontraba, y **el visitante no volvía a recibir nada** hasta
recargar la página. El `POST` respondía 202 y el turno se entregaba a una cola sin
consumidor.

Había un evento que lo decía —`chat.message_without_stream`— y su comentario decía
«esto solo pasa si se cayó». Pasaba todas las noches.

Es la **forma 16** del catálogo, nueva: *el registro indexado por lo que desaparece
primero*. Re-indexar la cola por el navegador cerró el defecto y además dejó el
sitio donde publicar el aviso.

### 4. A AC5.6.4 le faltaba su mitad, y la siembra no la podía poner

«El reinicio borra solo los casos de visitantes **y devuelve los sembrados a su
estado sembrado**.»

La primera mitad estaba: el purgador de U4 conserva los casos con origen
`generator`. La segunda no, y quien los mueve es la bandeja: decidir un caso lo
cierra y no vuelve a derivado —la prueba de humo lo dice con esas palabras—. La
siembra no lo arregla y hace bien: se detiene nombrando el caso que está en otro
estado, que es lo correcto para un comando a mano y no sirve para una corrida que
nadie está mirando.

El paso nuevo tiene tres caminos: el que está en su estado **no se toca**, el que
falta se siembra, y el que está en otro estado se borra y se vuelve a sembrar.

### 5. `accepts_new_cases` no tenía quién la llamara

La tanda 1 lo dejó escrito: «su cumplimiento real es de la tanda 2». Es la forma 13
otra vez —la decisión pura que producción no llama— y esta vez el cableado tenía una
trampa propia, que es la decisión 3 de abajo.

## Decisiones que tomé y Miguel debería ver

1. **Un serial sin dueño sobrevive a la noche.** Es el precio de BR2.5 y está
   escrito en la revisión que crea la tabla: o el libro de seriales emitidos
   sobrevive al reinicio, o los números se repiten. Lo que guarda son seis dígitos y
   su aseguradora: no nombra a nadie, no se puede atar a ninguna persona —el caso ya
   no existe— y lo único que revela es **cuántos casos ha tenido la demostración**,
   que es un recuento que el panel público ya publica. Por eso **no lleva la marca de
   dato de visitante**: con ella, el registro de purgadores exigiría un dueño que la
   borrara y BR2.5 volvería a ser imposible.

2. **La cola de eventos del chat es del navegador y no de la conversación.** Cambia
   una decisión de U13 («una cola por conversación»), y la cambia porque el reinicio
   nocturno la obligó: ver el hallazgo 3.

3. **La puerta de la ventana no tiene valor por omisión.** El chat no puede importar
   `demo_operations` —está por encima en el contrato de capas— así que recibe la
   puerta enchufada, igual que recibe el grafo. Un valor por omisión «acepta» dejaría
   la regla declarada y sin cumplir en cualquier proceso que monte el chat sin
   enchufarla, y nadie se enteraría: el chat seguiría abriendo casos para siempre y
   el tablero en verde. **Sin base, la puerta cierra.**

4. **La frase de la demo cerrada se escribe en tres sitios y una prueba lo sostiene.**
   U20, la voz y el chat no se pueden importar entre sí; cada uno escribe su literal
   —que es lo que el chequeo de claves sin consumidor necesita— y una prueba de U20
   comprueba que las tres nombran la misma clave.

5. **El tercer rechazo del chat lleva `kind`.** Los otros dos traen `copy_key` y el
   cliente los distingue **por su forma**, porque el cliente generado no entrega el
   código de estado. Sin un campo propio, la pantalla diría «esa no es una pregunta
   de cobertura» cuando lo que pasa es que la demo se estrechó.

6. **Un caso sembrado restaurado estrena número.** Se borra y se vuelve a sembrar,
   y el libro de seriales no repite el anterior. Es la consecuencia de dos reglas
   correctas y el precio es pequeño: solo cambia el número del caso que alguien
   había movido.

7. **La corrida de ensayo no deja registro.** Es la regla con la consecuencia más
   fea de la unidad: una corrida de ensayo guardada como exitosa diría que la demo
   está limpia habiendo borrado exactamente nada, y reiniciaría el contador de 24
   horas.

8. **El aprovisionamiento exige al menos un caso sembrado, y lo comprueba antes de
   ingerir.** Ingerir ya es crear: dejar el corpus indexado y la bandeja vacía es la
   mitad de aseguradora que BR1.1 prohíbe.

9. **El orden del reinicio: primero barrer, después la vitrina.** Sin la clave de
   cifrado los casos sembrados se quedan como estaban y el comando sale distinto de
   cero, pero **los datos del visitante ya se fueron**. Lo que no puede faltar es el
   barrido.

10. **Una llamada que retoma un caso abierto se admite con la ventana cerrada**
    (BR3.3), y la disponibilidad lo dice igual: si la consola escondiera el botón con
    una retoma viva, quien dejó su reporte a medias no tendría forma de volver.

## Roturas: cada regla rota, y qué prueba se cae

Doce roturas, todas con conducta rota y ninguna con `ImportError`. Ninguna prueba
hubo que corregir.

| Rotura | Prueba que cae |
| --- | --- |
| La corrida de ensayo deja registro | `test_una_corrida_de_ensayo_cuenta_y_no_deja_registro` |
| La consulta devuelve la última corrida en vez de la última exitosa | `test_un_purgador_caido_deja_la_corrida_parcial_con_su_registro` |
| El purgador del backend declara limpio un transporte que no sabe barrer | `test_un_transporte_que_no_sabe_barrerse_levanta` |
| El registro de la corrida se guarda sin sus filas de purgador | tres de `u20/test_reset.py` |
| El noveno purgador sale del registro | `test_los_nueve_purgadores_corren_en_el_orden_del_registro` y la de completitud de U2 |
| Se ingiere antes de validar la carpeta | tres de `u20/test_provision.py` |
| El identificador del caso sembrado deja de ser estable | `test_correrlo_dos_veces_deja_el_mismo_estado` |
| La puerta de la ventana corta también las conversaciones con caso | `test_una_conversacion_con_caso_sigue_entera_con_la_ventana_cerrada` |
| La voz ignora la retoma al aplicar la ventana | las dos de la retoma de `u20/test_window.py` |
| La puerta siempre acepta | las tres del chat cerrado |
| La cola vuelve a ser de la conversación | las dos de `u20/test_notice.py` |
| El aviso del reinicio se publica siempre | `test_el_aviso_no_sale_en_la_primera_conversacion_de_un_navegador` |
| La restauración borra y siembra siempre | `test_el_que_ya_esta_en_su_estado_no_se_toca` |
| El borrado de un sembrado pierde su `origin` | `test_el_borrado_de_un_sembrado_no_puede_tocar_un_caso_de_visitante` |
| La comprobación de unicidad vuelve a comparar la columna entera | `test_un_serial_emitido_no_se_vuelve_a_dar_despues_del_reinicio` |

## La batería de humo, y lo que no cubre

La cuarta aseguradora vive en las fixtures (`tests/fixtures/cuarta-aseguradora/`) y
**no se publica**: ninguna corrida del aplicativo carga su carpeta. Es la única
prueba del proyecto que responde AC5.1.1 de verdad —*¿añadir una aseguradora es
añadir una carpeta?*—, porque las tres de siempre podrían funcionar por estar
nombradas en algún sitio.

Pasa chat, bandeja y aislamiento. **La pregunta de cobertura no está**, y decirlo es
parte del resultado: necesita el corpus indexado por el proveedor de embeddings, que
es gasto. Eso lo comprueba `mise run smoke` contra el aplicativo vivo.

## Lo que no se corrió aquí

- **`scripts/verify.sh` y la suite completa no**: la regla del proyecto es que no
  corren en la máquina de Miguel. Lo que se corrió en cada commit: las pruebas de la
  unidad, las de las unidades que el cambio toca (U4, U13, U17, U23, U2) y **las once
  compuertas baratas, sin recortes**. Más `rls:check` y `migrate:check`, por las tres
  tablas nuevas.
- **La compuerta autoritativa es GitHub Actions sobre `main`**, como siempre.

## Nota del entorno

Las dos revisiones de esquema de esta tanda (`u20_demo_0001_reset_runs` y
`u20_demo_0002_case_numbers`) suben, bajan y vuelven a subir contra una base virgen:
`migrate:check` en verde. Las dos tablas de la primera entran en la lista de
exclusión del aislamiento con su razón; la de la segunda lleva su aislamiento y su
política, como cualquier tabla con aseguradora.
