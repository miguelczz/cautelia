# Entidades — U13 `chat`

U13 no inventa el caso ni la transcripción: los dos existen desde U4, y el registro
de la divulgación desde U10. Lo que esta unidad añade es **la conversación del
navegador** —la pieza que ata un visitante anónimo a un caso sin pedirle una cuenta—
y los contadores que impiden que esa puerta pública agote la cuota.

## Lo que U13 crea

### `chat_session` — la conversación de un navegador

Una fila por conversación. Es lo que hace posible retomar sin credencial y lo que
hace imposible retomar el caso de otro.

| Campo | Por qué está |
| --- | --- |
| `chat_session_id` | La fila |
| `tenant_id` | La aseguradora. Con su política de fila, como toda tabla del aplicativo |
| `visitor_key_digest` | **El resumen** de la clave del navegador, nunca la clave. Es lo que ata la conversación a ese navegador y a ningún otro (BR6.2), y guardar el resumen en vez del valor es lo que hace que un volcado de la base no sirva para hacerse pasar por nadie |
| `case_id` | El caso, cuando ya se abrió. Nulo antes: una conversación existe desde el primer mensaje, y el caso solo cuando hay algo que registrar |
| `language` | El idioma en que responde la agente ahora mismo (BR2.1). Vive aquí y no en el navegador porque el selector tiene que mostrar lo que de verdad pasa |
| `origin_digest` | El resumen del origen, para el límite por origen (BR3.1) |
| `message_count` | Los mensajes de esta sesión, para el límite por sesión |
| `last_message_at` | Para el intervalo mínimo entre mensajes (BR3.2) |
| `created_at` | Su nacimiento, y la ventana del reinicio nocturno |

La llave foránea hacia el caso es **compuesta** `(tenant_id, case_id)` con cascada,
como todas las de este proyecto desde la lección de U8: una llave de una sola columna
dejaría a una aseguradora escribir una fila suya que nombrara el caso de otra.

Lleva la marca `visitor-data` y entra en el purgador de U2, porque una conversación
es exactamente lo que el borrado nocturno tiene que llevarse.

### `chat_rate_window` — los contadores de los límites

Una fila por ámbito y ventana: el origen y el día. El límite por sesión ya vive en
`chat_session.message_count`, así que esta tabla solo lleva los dos que cruzan
sesiones.

| Campo | Por qué está |
| --- | --- |
| `scope` | Conjunto cerrado escrito literalmente en la restricción: `origin`, `site_day` |
| `scope_key` | El resumen del origen, o la fecha del día |
| `window_start` | El inicio de la ventana, para que el reinicio sea una comparación y no un borrado |
| `count` | Los mensajes contados |

No lleva `case_id` ni datos de la persona: son contadores. Lleva `tenant_id` con su
política igual, porque una aseguradora no tiene por qué ver el tráfico de otra.

## Lo que U13 compone y no persiste

- **El primer mensaje con su divulgación.** Se compone del catálogo por idioma y de
  las capacidades de la aseguradora (BR1.1, BR1.3). Lo que se persiste es su
  registro en `disclosure_record`, que ya existe, no el texto.
- **La cita expandible y el resumen de su traza.** Los dos se leen de lo que U8 y U5
  ya guardaron; esta unidad los presenta y no los copia. Copiarlos sería tener dos
  versiones de la misma cláusula, y la segunda envejece.

## Lo que U13 lee

| De quién | Qué |
| --- | --- |
| U12 `graph-runtime` | `handle_turn`, `resume_case` y `preload` con la forma de C-14, y sus eventos tipados |
| U4 `case-record` | El caso, su transcripción por turno con el canal, y sus transiciones |
| U2 `tenancy` | La clave del navegador, el enlace firmado, la póliza de ejemplo y la sesión con la aseguradora fijada |
| U5 `provider-platform` | El resumen de la traza y el registro de uso por turno |
| U10 `compliance` | La guardia de salida, por la que pasa todo texto, incluido el aviso de la decisión |
| U1 `workspace` | El catálogo por idioma y el conductor de texto del corredor de evaluaciones |
| U6 `web-shell` | El armazón visual, el enrutador y el selector de idioma |

## Por qué la conversación es una tabla y no una cookie con estado

Podría bastar una cookie firmada que llevara el caso dentro. No basta por dos
razones, y las dos son de esta unidad:

1. **El límite por sesión tiene que sobrevivir a que el visitante borre la cookie.**
   Si el contador vive en el cliente, el límite no existe: se reinicia solo.
2. **El aviso de la decisión del ajustador llega cuando el navegador no está.**
   Alguien tiene que saber a qué conversación pertenece un caso decidido, y ese
   alguien es una fila.
