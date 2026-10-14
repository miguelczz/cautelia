# Reglas de negocio — U15 `speech-providers`

Son 15 reglas en seis familias: interfaces y adaptadores, configuración,
transcripción, síntesis, gasto y pruebas de contrato.

## Reglas

El bloque siguiente es la fuente de verdad; la tabla resumen se deriva de él.

```yaml
rules:

  - id: BR1.1
    statement: El protocolo de cada proveedor de voz solo se usa dentro de su adaptador.
    category: constraint
    applies_to: "providers/adapters/deepgram, providers/adapters/cartesia"
    trigger: "En cada corrida del guion de verificación."
    logic: "SI un archivo fuera del adaptador abre un WebSocket o llama a la API de un proveedor de voz ENTONCES el contrato forbidden de import-linter falla."
    violation: "El paso de reglas de importación falla nombrando el archivo."
    source: AC5.10.2, ADR-018, C-16

  - id: BR1.2
    statement: La voz depende de una sola interfaz de sintetizar y transmitir, y de una sola de transcribir.
    category: constraint
    applies_to: "TextToSpeech, SpeechToText (C-16)"
    trigger: "Siempre."
    logic: "Los dos adaptadores de síntesis (Cartesia y Aura-2) implementan TextToSpeech; el de Deepgram implementa SpeechToText. Nadie más los importa: la raíz de composición los inyecta."
    violation: "El comprobador de tipos y la regla de importación fallan."
    source: AC5.10.2, C-16

  - id: BR1.3
    statement: Los clientes de voz se construyen en la fábrica por uso, con la clave y el proyecto del uso voice.
    category: policy
    applies_to: "Fábrica de U5"
    trigger: "Al arrancar."
    logic: "SI se pide un adaptador de voz ENTONCES la fábrica lo construye con las variables del uso voice, nunca con las de otro uso."
    violation: "La prueba de la fábrica falla."
    source: ADR-018, project.md (claves separadas por uso)

  - id: BR1.4
    statement: Todo error del proveedor sale traducido a la taxonomía cerrada, y el saldo agotado sale como parada explícita sin reintento.
    category: constraint
    applies_to: "Adaptadores"
    trigger: "Cualquier fallo del proveedor."
    logic: "SI falla ENTONCES sale ProviderError con timeout, rate_limited, unavailable o invalid_response; SI el saldo o la cuota se agotaron ENTONCES BudgetExhausted. Ningún tipo del proveedor cruza al núcleo."
    violation: "Las pruebas con respuestas grabadas de error fallan."
    source: C-16, team.md convención 8a

  - id: BR2.1
    statement: Proveedor, modelo y voz por idioma, principal y de respaldo, viven en el bloque voice de cada tenant.yaml.
    category: policy
    applies_to: "TenantVoiceConfig"
    trigger: "Al arrancar."
    logic: "SI se cambia el bloque y se despliega ENTONCES la llamada siguiente usa lo nuevo, sin tocar ningún archivo de lógica."
    violation: "La prueba que cambia la configuración y comprueba la voz usada falla."
    source: AC5.10.1, Q2, C-25

  - id: BR2.2
    statement: Una configuración de voz rota apaga la voz de esa aseguradora con un motivo del catálogo; el proceso y el chat siguen vivos.
    category: validation
    applies_to: "VoiceAvailability"
    trigger: "Al arrancar."
    logic: "SI el proveedor es desconocido, la voz no existe o el modelo no está en la lista del adaptador ENTONCES available es falso con su reason_key, y el resto arranca."
    violation: "La prueba con una configuración rota comprueba voz apagada y chat vivo."
    source: AC5.10.4, FR3.7

  - id: BR2.3
    statement: Solo se puede activar un proveedor cuya prueba de contrato existe y pasa.
    category: constraint
    applies_to: "Configuración de voz"
    trigger: "Al validar la configuración."
    logic: "SI la configuración nombra un proveedor sin adaptador registrado o sin su respuesta grabada ENTONCES no se activa y cae en BR2.2."
    violation: "La prueba con un proveedor sin respuesta grabada falla."
    source: AC5.10.3

  - id: BR3.1
    statement: La transcripción entrega parciales y finales, con cada palabra y su confianza, y el idioma detectado en modo multi.
    category: calculation
    applies_to: "Transcript"
    trigger: "Cada mensaje del proveedor."
    logic: "SI el proveedor manda la confianza de una palabra ENTONCES se conserva; SI no la manda ENTONCES va nula, nunca cero."
    violation: "La prueba contra la respuesta grabada falla."
    source: PA-2, ADR-007

  - id: BR3.2
    statement: El audio no se persiste nunca, y ni el audio ni el texto transcrito salen a un log o a una traza desde el adaptador.
    category: constraint
    applies_to: "Adaptadores"
    trigger: "Siempre."
    logic: "El adaptador devuelve el texto al turno en memoria; guardarlo, ya redactado, es de U4."
    violation: "La prueba que inspecciona los eventos emitidos falla."
    source: NFR19, project.md (redactar antes de persistir)

  - id: BR4.1
    statement: Los dos adaptadores de síntesis entregan el mismo formato de audio.
    category: constraint
    applies_to: "AudioFormat"
    trigger: "Cada síntesis."
    logic: "SI se sintetiza con cualquier voz ENTONCES sale PCM de 16 bits, mono, a la tasa única configurada."
    violation: "La prueba de contrato comprueba el formato."
    source: AC5.10.3

  - id: BR4.2
    statement: La voz de respaldo se atiende por la misma interfaz y produce las mismas claves del catálogo que la principal.
    category: constraint
    applies_to: "TextToSpeech"
    trigger: "Siempre."
    logic: "Cambiar de voz no cambia qué se dice: el texto y sus claves vienen de antes del adaptador."
    violation: "La prueba que corre el mismo texto con las dos voces compara las claves."
    source: AC5.11.4, D17

  - id: BR5.1
    statement: Cada llamada de voz pasa por el registro de gasto y el techo de U5 antes de salir, con su unidad de precio.
    category: policy
    applies_to: "Adaptadores"
    trigger: "Antes de cada llamada."
    logic: "SI el techo está cerrado ENTONCES no se llama y sale BudgetExhausted; SI NO, la llamada se registra en segundos de audio para la transcripción y en caracteres para la síntesis, con el precio de lista de prices.yaml."
    violation: "La prueba con el acumulado forzado al borde falla."
    source: C-17, project.md (pruebas de gasto sin consumir el presupuesto)

  - id: BR6.1
    statement: Cada proveedor tiene su prueba de contrato contra una respuesta grabada, que corre en cada entrega.
    category: policy
    applies_to: "Pruebas de contrato"
    trigger: "Cada entrega."
    logic: "La respuesta grabada se captura una sola vez con una llamada real y se versiona; la prueba comprueba el formato y la forma de la respuesta."
    violation: "La compuerta de pruebas falla."
    source: AC5.10.3

  - id: BR6.2
    statement: La prueba contra el proveedor real mide la latencia al primer audio con un texto fijo y corre a mano, en cada hito.
    category: policy
    applies_to: "Pruebas de contrato"
    trigger: "Por comando, en cada hito."
    logic: "Nunca corre en la tubería: gasta saldo y depende de la red."
    violation: "Revisión del flujo de GitHub Actions."
    source: AC5.10.3, team.md (lo que no corre en cada corrida)

  - id: BR6.3
    statement: Un comando sintetiza una frase con la voz de una aseguradora por el camino real del aplicativo y la deja oír.
    category: policy
    applies_to: "Tarea nueva mise run voice:say, que se crea con la generación de código"
    trigger: "Por comando."
    logic: "Configuración, fábrica, adaptador y gasto; el audio queda en tmp/voice/ y se reproduce si hay reproductor."
    violation: "La demostración de B18 no se puede correr."
    source: Q3, DP-14
```

## Resumen

| ID | Regla |
| --- | --- |
| BR1.1 | El protocolo del proveedor, solo en su adaptador |
| BR1.2 | Una interfaz de síntesis y una de transcripción |
| BR1.3 | Clientes por uso, con la clave de voz |
| BR1.4 | Errores en la taxonomía cerrada; saldo agotado sin reintento |
| BR2.1 | Proveedor, modelo y voz en `tenant.yaml` |
| BR2.2 | Configuración rota: voz apagada, chat vivo |
| BR2.3 | Sin prueba de contrato, no se activa |
| BR3.1 | Parciales y finales con confianza nula si falta, nunca cero |
| BR3.2 | El audio no se guarda ni se loguea |
| BR4.1 | Un solo formato de audio |
| BR4.2 | El respaldo dice lo mismo |
| BR5.1 | Gasto y techo antes de cada llamada |
| BR6.1 | Respuesta grabada en cada entrega |
| BR6.2 | Proveedor real a mano, en cada hito |
| BR6.3 | Oír a Catalina por un comando nuevo |
