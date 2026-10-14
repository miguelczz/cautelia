# Requisitos de fiabilidad — U13 `chat`

Una superficie pública falla delante de alguien. Lo que esta unidad tiene que
garantizar no es que nada falle: es que cuando algo falle, la persona reciba una
frase honesta y su caso siga existiendo.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| REL-U13.1 | Turnos que terminan sin uno de los tres eventos finales de C-14 | **Exactamente 0** | Tarea nueva `mise run test:u13` |
| REL-U13.2 | Casos perdidos al llegar a un límite (el caso tiene que quedar guardado) | **Exactamente 0** | Tarea nueva `mise run test:u13` |
| REL-U13.3 | Reinicio de los límites a la hora configurada, probado un minuto antes y un minuto después | **En verde** | Tarea nueva `mise run test:u13` |
| REL-U13.4 | Avisos de una decisión que tardan más de un minuto con la conversación abierta | **Exactamente 0** | Tarea nueva `mise run test:u13` |
| REL-U13.5 | Resúmenes de traza que responden "no encontrado" mientras la traza se está registrando | **Exactamente 0** | Tarea nueva `mise run test:u13` |
| REL-U13.6 | Conversaciones que sobreviven al reinicio nocturno de los datos de demostración | **Exactamente 0**: se borran todas | Tarea nueva `mise run test:u13` |

## Por qué REL-U13.1 es cero

El flujo de C-14 termina siempre en texto final, derivación o error. Un turno que
acaba sin ninguno de los tres deja a la persona mirando una pantalla que no dice
nada, y es el modo de fallo más probable de un canal con streaming: el primer evento
parcial llega, el segundo no, y nadie cierra la secuencia.

## Por qué REL-U13.5 es cero y no "casi siempre"

Porque "no encontrado" ya significa otra cosa en esta unidad: es la respuesta
correcta cuando alguien pide el resumen de una conversación que no es la suya
(BR4.3). Si una traza en curso respondiera lo mismo, el caso legítimo y el caso de
aislamiento se volverían indistinguibles —para la persona y, peor, para quien lea la
prueba.

## El modo degradado, probado y no descrito

Las tres formas en que esta unidad degrada, cada una con su frase del catálogo y
ninguna con un error genérico:

1. **Límite alcanzado** (sesión, origen o día): se dice cuál y cuándo se puede seguir.
2. **El proveedor del modelo no responde**: la política de fallo es de U12; esta
   unidad emite lo que U12 le devuelve por el punto único.
3. **La verificación de póliza no volvió todavía**: la frase de espera, que es la
   clave del canal chat y no la de la voz.

Ninguna de las tres cierra el caso ni lo categoriza: eso lo prohíbe BR3.3 de U12 y
esta unidad no tiene por dónde hacerlo.
