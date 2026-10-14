# Requisitos de seguridad — U20 `demo-operations`

Versión corta. Cuatro requisitos, y esta unidad **es** un requisito de seguridad: su
trabajo entero es que la retención esté acotada.

| # | Requisito | Cómo se comprueba |
| --- | --- | --- |
| SEC-U20.1 | Tras el reinicio no queda ningún dato de visitante, **tampoco en el backend de trazas** | Prueba contra una base sembrada con casos, transcripciones, enlaces, llamadas y trazas de visitante, y una consulta después por cada tabla marcada. El backend de trazas se comprueba aparte porque no está en la base (AC5.15.1, BR2.1) |
| SEC-U20.2 | El registro de gasto sobrevive | La misma prueba, mirando la ventana y el libro mayor antes y después (BR2.2) |
| SEC-U20.3 | Ningún número de caso ni enlace firmado se repite después del reinicio | Prueba que emite antes y después y compara. Un número repetido haría que un enlace viejo abriera el caso de otra persona: es una fuga con forma de coincidencia (AC5.15.4, BR2.5) |
| SEC-U20.4 | Sin reinicio exitoso en 24 horas, las superficies públicas dejan de aceptar casos nuevos | Prueba con el reloj inyectado y el último éxito forzado, incluida la que comprueba que **tres intentos fallidos no reinician el contador** (AC5.15.5, BR3.2) |

**El audio no se borra porque nunca se guardó.** Comprobarlo antes y después del
reinicio es lo que demuestra que no hay un archivo esperando a que alguien lo encuentre.

**El aprovisionamiento no publica ninguna credencial.** Siembra las de la bandeja por
aseguradora y rol, que son para Miguel, el despliegue local y las pruebas.

## Sources

- `../functional-design/rules.md` — BR2.1, BR2.2, BR2.5, BR3.2
- `../../../inception/user-stories/stories.md` — AC5.15.1 a AC5.15.5

## Assumptions & Open Questions

None.
