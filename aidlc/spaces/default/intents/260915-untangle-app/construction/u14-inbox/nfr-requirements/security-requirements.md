# Requisitos de seguridad — U14 `inbox`

Aquí vive la única credencial del aplicativo y el único enlace que abre un caso
sin credencial. **Las tres compuertas duras de la unidad son de seguridad** y las
tres dicen lo mismo por tres puertas distintas: nadie ve un caso que no es suyo.

## Objetivos medibles

| ID | Qué mide | Valor esperado | Comando |
| --- | --- | --- | --- |
| SEC-U14.1 | Casos de otra aseguradora visibles con una credencial, por la interfaz o por la API (BR1.4, `[bloquea]`) | **Exactamente 0** | Tarea nueva `mise run test:u14` |
| SEC-U14.2 | Diferencias —código y cuerpo— entre la respuesta de la cola a una sesión de enlace y a quien no tiene credencial (BR5.1, `[bloquea]`) | **Exactamente 0** | Tarea nueva `mise run test:u14` |
| SEC-U14.3 | Diferencias entre la respuesta a un enlace con firma alterada y la respuesta a un caso que no existe (BR5.2, `[bloquea]`) | **Exactamente 0** | Tarea nueva `mise run test:u14` |
| SEC-U14.4 | Decisiones tomadas con enlace atribuidas a una persona de la aseguradora (BR5.5) | **Exactamente 0** | Tarea nueva `mise run test:u14` |
| SEC-U14.5 | Apariciones del token del enlace en la dirección visible, en `Referer` o en cualquier registro (BR5.6) | **Exactamente 0** | Tarea nueva `mise run test:u14` + `mise run content:check` |
| SEC-U14.6 | Datos personales sin redactar en la tabla de avisos y en la vista de caso (BR2.3, BR6.3) | **Exactamente 0**, por idioma y por tipo de entidad | `mise run redaction:report` |
| SEC-U14.7 | Correcciones o decisiones aplicadas sobre un caso cerrado (BR3.4, BR4.4) | **Exactamente 0** | Tarea nueva `mise run test:u14` |
| SEC-U14.8 | Tablas de esta unidad sin política de aislamiento | **Exactamente 0** | `mise run rls:check` |
| NFR10 | Fuga entre aseguradoras sobre las colisiones sembradas de DS-8 (dueña U2) | **En verde** | `mise run evals:gate` |

## Cómo se miden las tres compuertas duras

Las tres se miden **comparando dos respuestas enteras**, no comprobando que un
dato no aparezca. Es la lección que U12 dejó escrita y que U13 aplicó: la
filtración no es el dato, es la distinción. Una respuesta distinta de la que
recibe un desconocido ya confirma que ese caso existe, aunque la frase sea
inofensiva.

En las tres, el **control positivo va delante**: la credencial legítima tiene que
recibir su cola real, y el enlace legítimo su caso real, antes de comprobar que
el ajeno no recibe nada. Sin ese control, las aserciones pasan igual con una
implementación que no entregue nunca nada.

## La aseguradora sale de la credencial, nunca de la dirección

SEC-U14.1 no se satisface filtrando por el `tenant` de la ruta. La aseguradora
sale de la credencial y la ruta solo tiene que **coincidir** con ella; si no
coincide, se rechaza. La política de fila es la segunda capa y no la primera: un
fallo en el código de la ruta no puede convertirse en una consulta a la tabla de
otra aseguradora.

## Lo que esta unidad no protege

La emisión y la validación del enlace firmado y de la credencial son de U2
(C-07). Aquí se canjean y se consumen; los objetivos de la firma, su vigencia y
su clave viven en los requisitos de seguridad de esa unidad.
