# Hallazgos de la tanda 4 — U14 `inbox`

Las tres pantallas, los casos de evaluación de la unidad y el cierre.

La revisión rompió **veintinueve** puntos, uno por regla, y se cayó una prueba en
veintisiete. **Dos no tumbaron nada**, y las dos resultaron ser la misma forma con
dos caras distintas: una aserción que no podía distinguir, y una prueba que faltaba.

## 1. Una frase con dos mitades no se puede comprobar entera

**Qué se rompió.** `decidedByMessage` devolvía cadena vacía en lugar de "pendiente
de decisión" (BR2.4).

**Qué se cayó.** Nada.

**Por qué.** El encabezado dibujaba las dos mitades en un solo elemento —
`{quién}( · ){cuándo}` — y la prueba miraba su texto junto:

```ts
expect(quien.textContent).toContain(t("inbox.explanation.pending"));
```

Con una de las dos vacía, la otra seguía diciendo la frase, así que el texto junto
la **contenía** igual. Es la aserción que no puede distinguir, la forma que más
veces ha acertado en este proyecto.

**Qué se hizo.** Las dos mitades pasan a dos elementos con su propio identificador
(`case-decided-by` y `case-decided-at`) y la prueba las compara **por separado y
por igualdad**, no por contención. Se volvió a romper las dos, una cada vez, y las
dos tumbaron su prueba.

Lo que hay detrás no es la maquetación: es que **una aserción sobre texto concatenado
no puede decir cuál de las partes habló**. Cada vez que una pantalla junta dos datos
en una frase, la prueba que la mire entera pierde la mitad de su poder.

## 2. Cuatro combinaciones de una regla, y la prueba cubría una

**Qué se rompió.** La pantalla del visitante traducía `not_found` a "servicio no
disponible" en lugar de dejarlo pasar como el resto (BR5.2 `[bloquea]`).

**Qué se cayó.** Nada.

**Por qué.** El enlace se rechaza por **dos puertas** —el canje y la lectura del
caso— y con **dos códigos** —`link_invalid` y `not_found`—: cuatro combinaciones que
tienen que mostrar exactamente la misma página. Las pruebas cubrían dos, las del
canje. Por la otra puerta se podía distinguir la causa, y "servicio no disponible"
frente a "enlace no válido" ya le dice a quien prueba enlaces que ese caso existe.

**Qué se hizo.** La prueba recorre **las cuatro** combinaciones y compara la página
entera —su tipo y su texto— exigiendo que todas den la misma. Se volvió a romper y
se cayó.

La forma: **una regla que se aplica en más de un camino necesita una prueba por
camino.** Contarlos es la parte fácil y es la que se salta; aquí eran dos puertas por
dos códigos, y el producto de los dos es lo que había que medir.

## 3. Dos claves del catálogo sin consumidor, y cada una por una razón distinta

El chequeo de claves sin consumidor las encontró las dos. Son la misma señal con dos
causas opuestas, y por eso se resolvieron al revés una de la otra:

- **`inbox.decision.cancel` estaba muerta.** Se escribió pensando en un diálogo con
  botón de cancelar, y el formulario de decisión no tiene nada que cancelar: está
  siempre a la vista dentro del encabezado. **Se borró del catálogo.** Un catálogo que
  acumula claves muertas es el fallo que ya muestra la landing.
- **`visitor.expired_with_comment` era una regla que faltaba.** BR5.4 pide que, si el
  enlace vence mientras se escribe el comentario, se diga **que el texto se conserva
  para copiarlo**. La pantalla mostraba el mensaje genérico de enlace no válido, que
  es correcto y hace que alguien cierre la pestaña y pierda lo escrito. **Se
  construyó**: en esa pantalla y solo para las dos causas del enlace, el mensaje se
  cambia por esa frase.

La lección es del chequeo, no de las claves: **una clave sin consumidor no dice
"bórrala", dice "mira por qué"**. La mitad de las veces sobra la frase y la otra
mitad falta la conducta, y desde el chequeo las dos se ven igual.

## 4. Una prueba que pasaba con una clave que no existe

No salió de romper el código de esta tanda, sino de apoyarse en una prueba ajena. Al
añadir las etiquetas de los ocho campos del caso, la comprobación de paridad de U4
(`test_labels.py`) tenía que ser la que avisara si una clave faltaba en un idioma. No
podía:

```python
try:
    frase = copy_api.t(clave, locale=idioma)
except KeyError:
    faltantes.append(clave)
else:
    if not frase.strip():
        faltantes.append(clave)
```

El catálogo **nunca lanza y nunca devuelve vacío**: cuando la entrada falta devuelve
**la clave misma** y emite su evento. Así que ninguna de las dos ramas se cumplía
nunca y la prueba pasaba con ocho claves inexistentes.

Corregida: se compara la frase **contra la clave**. Es de nuevo la aserción que no
puede distinguir, esta vez por confiar en un contrato que el módulo no tiene —y el
módulo lo dice en su propio docstring, tres líneas más arriba de donde estaba el
error.

## 5. Tres defectos que solo vio el arnés, corriendo el proceso real

Las pruebas de pantalla pasaban las ochenta y dos. El arnés de accesibilidad, que
abre las pantallas **contra el proceso real en un navegador de verdad**, encontró tres
cosas que ninguna de ellas podía ver.

**Un `500` que era un oráculo.** El proceso del arnés corre sin claves de firma —no
las necesita para dibujar— y la bandeja respondía `500` a cualquier ruta, porque
`_credencial` levantaba una excepción cuando la clave no estaba enchufada. Eso
distingue "no configurado" de "no válido", y esta unidad tiene **una sola forma de
rechazar** precisamente para no distinguir nada: un `500` le dice a quien prueba
credenciales que ahí hay una bandeja mal configurada. Corregido: un despliegue sin
clave es un despliegue **sin bandeja**, así que responde igual que ante una credencial
ilegible, con su causa en el rastro. Lo mismo del lado del enlace. Dos pruebas nuevas
lo fijan, con el control positivo delante y comparando **los cuerpos enteros** menos
el rastro.

Nadie había escrito una prueba de eso, y por una razón que vale anotar: **la
configuración incompleta no aparece en ningún criterio de aceptación**. Los criterios
describen lo que pasa cuando el sistema está bien montado.

**Un grupo de radios era una trampa de teclado y un objetivo táctil de 13 píxeles.** El
formulario de decisión usaba `input type="radio"` más un botón de confirmar. Un radio
mide 13 x 13 y la regla del arnés de U6 exige 44 x 44 en cualquier control táctil; y un grupo de radios es
**una sola parada de tabulación** —eso es correcto y es lo que hace el navegador—, así
que el recorrido con Tab no llegaba a las demás opciones y el arnés lo leyó como una
trampa.

La primera respuesta fue estrechar el arnés para que tratara un grupo de radios como
una parada. **Se descartó y se revirtió.** La forma correcta era otra: **un botón por
acción**, que es la pieza que el proyecto ya tiene probada (`Button` garantiza 44 x 44),
cada uno su propia parada, y sin nada preseleccionado —que en un formulario de decisión
significa no dejar "aprobar" elegido por omisión—. La acción intentada queda destacada,
así que "la decisión elegida sigue en pantalla" de BR4.1 se sigue viendo y se sigue
midiendo.

Lo que hay detrás: **estrechar un chequeo para que pase un diseño es debilitarlo, aunque
la reducción sea técnicamente correcta.** El grupo de radios habría sido una excepción
escrita en el arnés que nadie más necesitaba; el día que un radio de verdad fuera una
trampa, el arnés ya no lo vería. Cambió el diseño, no la compuerta.

Dos claves quedaron muertas al cambiarlo —`inbox.decision.cancel` y
`inbox.decision.submit`— y el chequeo del catálogo las encontró las dos. Se borraron.

**El chequeo del catálogo encontró un debilitamiento suyo en mi propia sonda.** La sonda
de las etiquetas de cobertura recorría una tabla de claves y llamaba a `t(clave)` con la
variable. BR3.4 lo prohíbe: una clave que llega como dato no se encuentra con un grep, y
entonces el chequeo de claves sin consumidor se queda ciego. Corregido con las cuatro
claves escritas literales en la llamada. Cuatro líneas repetidas a cambio de que ese
chequeo siga sirviendo, y la regla vale igual para el código que la mide.

## 6. Una bomba de tiempo en el ayudante de credenciales, disparada a mitad de la corrida

La suite entera pasó a las 18:45 y treinta pruebas de U14 estaban rojas a las 00:01.
Nada del código había cambiado en medio.

**Qué pasaba.** `credencial_de` emitía la credencial con `AHORA` —el instante fijo del
2026-09-28 a las doce UTC— y una credencial vive doce horas. Desde la medianoche UTC de
ese día está caducada **para siempre**: la ruta la rechaza con `expired` y toda prueba
que entre por la puerta se cae. No es una prueba inestable, que falla a veces; es un
muro que aparece a una hora fija y no se vuelve a ir.

**Es el mismo defecto que la tanda 3 arregló para los enlaces firmados**, en el mismo
archivo y con la misma forma. Allí se vio porque los enlaces duran una hora y el fallo
llegó el mismo día; aquí duran doce y tardó cinco días en llegar. La mitad arreglada se
arregló y la otra se quedó, porque en ese momento se leyó como un problema de los
enlaces y no como lo que era.

La forma, escrita para la próxima: **un dato con caducidad sembrado con un reloj fijo es
una bomba de tiempo.** Lo que hay que preguntarse al arreglar uno es *cuántos más hay*,
no solo *cómo arreglo este*. Las dos veces se vio primero como un fallo de otra cosa.

Corregido: se emite con el reloj de verdad, y quien necesita un instante concreto —las
pruebas de los bordes— lo pasa por argumento, que es exactamente lo que permite probar
el vencimiento sin esperar doce horas.

## 7. Una compuerta dura que dejé pasar al commit

`tenancy:literals` —la aserción que prohíbe un identificador de aseguradora literal
fuera del cargador de configuración y de las fixtures— encontró **23** en las pruebas de
pantalla nuevas, todas `stonecroft`. Y lo encontró **después** del commit, porque corrí
los pasos 3, 4, 5 y 7 por separado mientras trabajaba y di el paso 6 por bueno sin
correrlo entero.

La convención del proyecto está a la vista en las pruebas del chat, que usan un
identificador **inventado** (`una-aseguradora`): las diferencias entre aseguradoras viven
en su carpeta versionada, y una prueba que nombra una real ata la prueba a que esa
aseguradora exista. Corregido con el identificador inventado y los números de caso a
juego; las 82 pruebas siguen pasando sin tocar ninguna aserción.

Lo que falló no fue la compuerta, que hizo su trabajo: fue **correr pasos sueltos en
lugar del guion**. Los pasos que corrí uno a uno eran los que sabía que había tocado, y
el que falló es el único que crece por dentro —el 6 encadena once comprobaciones— así
que "no toqué nada de eso" era una suposición sobre un paso que no había leído. El guion
existe para no tener que suponerlo.

`main` quedó rojo durante un commit y se arregló hacia adelante, sin apilar nada encima,
que es lo que la práctica del equipo pide.

## Lo que se aplicó de las tandas anteriores

- **La rotura que no tumba nada obliga a decidir si era capa o copia** (lección de la
  tanda 3). Las dos de esta tanda resultaron ser **ninguna de las dos**: eran pruebas
  incompletas. Se añade ese tercer resultado al catálogo, porque la pregunta
  "¿capa o copia?" no lo cubría y las dos veces llevaba a la respuesta equivocada
  (borrar un guardia que sí hacía falta).
- **Romper el punto que impone la regla, no el que la nombra.** Las acciones que
  ofrece un caso se rompieron en `offered_for` —donde se deciden— y no en la pantalla,
  que solo las dibuja; y la atribución de la decisión se rompió en `_quien_decidio`,
  no en la etiqueta.
- **Nada se decide dos veces.** Las acciones disponibles, si se puede corregir un
  campo y el estado de la explicación **llegan resueltos del servidor**. Una pantalla
  que preguntara "¿es una agencia?" o "¿está cerrado?" escribiría esas reglas por
  segunda vez en otro lenguaje. Es la misma razón por la que se borraron dos guardias
  en la tanda 3, leída al revés: allí sobraba una copia, aquí se evitó crearla.

## Las veintinueve roturas

| # | Qué se rompió | Qué se cayó |
| --- | --- | --- |
| 1 | La cola ordena por prioridad en la pantalla (BR1.1) | 2 pruebas |
| 2 | El filtro vacío dice lo mismo que la bandeja vacía (BR1.3) | 1 |
| 3 | La fila pierde su tiempo de espera (BR1.2) | 1 |
| 4 | El encabezado deja de quedarse arriba (BR2.1) | 1 |
| 5 | Las acciones salen del encabezado (BR2.1) | 4 |
| 6 | El resumen de traza deja de estar plegado (BR2.2) | 3 |
| 7 | El titular de los controles deja de distinguir (BR2.2) | 1 |
| 8 | El titular de la traza pierde el costo (BR2.2) | 1 |
| 9 | La transcripción no dice dónde está el valor completo (BR2.3) | 1 |
| 10 | "Pendiente de decisión" se vuelve un hueco (BR2.4) | **0 → 1** tras corregir la prueba |
| 11 | El "cuándo" pendiente se vuelve un hueco (BR2.4) | 1 |
| 12 | "Sin cláusula" y "no pude verificar" dicen lo mismo (BR2.5) | 3 |
| 13 | La cita deja de decir quién la emitió (BR2.6) | 1 |
| 14 | El formulario pierde la nota al ser rechazado (BR4.1) | 3 |
| 15 | La pantalla añade una acción por su cuenta (BR4.5) | 1 |
| 16 | Un caso cerrado ofrece corregir igual (BR3.4) | 1 |
| 17 | La decisión del visitante se atribuye a la aseguradora (BR5.5) | 1 |
| 18 | El token se queda en la barra (BR5.6) | 1 |
| 19 | El visitante distingue la causa del rechazo (BR5.2) | **0 → 1** tras completar la prueba |
| 20 | Sin token ni caso se dibuja el caso igual (BR5.1) | 1 |
| 21 | El vencimiento no dice que la nota se queda (BR5.4) | 1 |
| 22 | El caso decidido se queda en la cola (BR6.1) | 2 |
| 23 | La bandeja deja de recordar el idioma (BR1.6) | 1 |
| 24 | Las acciones ignoran el estado del caso (BR4.3) | 2 integración + 1 caso de eval |
| 25 | Las acciones ignoran el tipo de aseguradora (BR4.5) | 3 integración |
| 26 | El cable dice que un caso cerrado se corrige (BR3.4) | 1 |
| 27 | "Pendiente" se colapsa con "no había" (BR2.4) | 2 |
| 28 | Quién decidió sale de la primera transición (BR2.4) | 1 |
| 29 | El campo viaja con su clave interna como etiqueta (BR2.1) | 1 |

Además, cuatro roturas contra los **casos de evaluación** de la unidad, que son los
que la compuerta corre en cada entrega: la explicación diciendo "hay" a todo, las
acciones ignorando el estado, dos salidas de cobertura con el mismo texto en el
catálogo y un identificador de aseguradora escrito en el código de decisión. Las
cuatro tumbaron su criterio nombrando la fila.

## Nada se debilitó

Tres pruebas existentes se tocaron y las tres quedaron **más estrictas**, no menos:
la paridad de claves de U4 (arriba), el registro de pantallas visitables (cuatro
rutas más que vigilar) y una fixture de U13 que gana el campo nuevo de la cita.
Ningún umbral, ningún piso de cobertura, ninguna compuerta y ninguna supresión del
linter.
