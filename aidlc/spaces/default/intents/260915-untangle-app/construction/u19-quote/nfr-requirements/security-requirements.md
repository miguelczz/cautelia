# Requisitos de seguridad — U19 `quote`

Versión corta. Cuatro requisitos, y ninguno introduce un mecanismo nuevo: los cuatro
son la aplicación a la cotización de controles que ya existen.

| # | Requisito | Cómo se comprueba |
| --- | --- | --- |
| SEC-U19.1 | Solo el rol `underwriter` decide una solicitud de cotización, comprobado **en el servidor**. Una credencial de ajustador o de agente de cuenta recibe un rechazo y la solicitud no cambia | Prueba de integración con las tres credenciales contra la API, no solo contra la pantalla (AC6.3.3, BR4.1) |
| SEC-U19.2 | La lista del suscriptor se filtra en el servidor y por aseguradora: no ve siniestros, no ve solicitudes no derivadas, y no ve nada de otra aseguradora | Prueba de aislamiento con dos aseguradoras sembradas y colisiones detectables, como las que ya existen para la bandeja (AC6.3.1, BR4.2) |
| SEC-U19.3 | Los datos personales de la solicitud —nombre, fecha de nacimiento, VIN— se redactan antes de persistir y en cada punto de salida, con los reconocedores que ya existen | La comprobación de redacción que ya corre, con casos de la solicitud añadidos por idioma y por tipo de entidad |
| SEC-U19.4 | El texto de quien pregunta entra como campo delimitado del estado tipado, nunca concatenado al prompt de sistema; la elegibilidad y la derivación las deciden las reglas, no el modelo | El mismo mecanismo de delimitación que ya usa la captura; y las reglas son datos con sus casos de prueba |

**Ninguna credencial de suscriptor se publica.** Es la misma decisión que rige para los
otros dos roles: las credenciales por aseguradora y rol son para Miguel, el despliegue
local y las pruebas.

## Sources

- `../functional-design/rules.md` — BR4.1, BR4.2
- `../../../inception/user-stories/stories.md` — AC6.3.1, AC6.3.3

## Assumptions & Open Questions

None.
