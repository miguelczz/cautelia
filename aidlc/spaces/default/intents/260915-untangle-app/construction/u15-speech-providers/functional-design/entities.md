# Entidades — U15 `speech-providers`

U15 no guarda nada en la base: la transcripción la guarda U4 ya redactada, el
gasto lo registra U5 y **el audio no se persiste nunca** (NFR19). Sus entidades
son la configuración de voz, que vive versionada en cada `tenant.yaml`, y los
objetos de valor que cruzan las interfaces de C-16.

## Entidades

```yaml
entities:

  - name: TenantVoiceConfig
    description: >
      La voz de una aseguradora, en el bloque `voice` de su `tenant.yaml` (C-25,
      Q2). Cambiar proveedor, modelo o voz es cambiar este bloque y nada más
      (AC5.10.1).
    stored_in: "app/config/tenants/<aseguradora>/tenant.yaml"
    attributes:
      - { name: language_default, type: Locale, required: true, allowed_values: [es, en] }
      - { name: stt, type: SpeechModelRef, required: true, constraint: "Proveedor y modelo de transcripción; hoy deepgram nova-3 en modo multi (ADR-007)." }
      - { name: primary, type: "map Locale → VoiceRef", required: true, constraint: "Hoy Catalina de Cartesia sonic-3.6 en los dos idiomas (ADR-008)." }
      - { name: fallback, type: "map Locale → VoiceRef", required: true, constraint: "Hoy Aura-2 de Deepgram; en español aura-2-celeste-es (ADR-008)." }
    relationships:
      - { target: VoiceRef, cardinality: "1 a n", direction: "TenantVoiceConfig contiene VoiceRef" }

  - name: VoiceRef
    description: Una voz concreta que un adaptador sabe sintetizar.
    attributes:
      - { name: provider, type: enum, required: true, allowed_values: [cartesia, deepgram] }
      - { name: model, type: identifier, required: true, constraint: "Identificador exacto, nunca un alias móvil." }
      - { name: voice_id, type: identifier, required: true }
      - { name: language, type: Locale, required: true, allowed_values: [es, en] }

  - name: SpeechModelRef
    description: El modelo de transcripción.
    attributes:
      - { name: provider, type: enum, required: true, allowed_values: [deepgram] }
      - { name: model, type: identifier, required: true }
      - { name: mode, type: enum, required: true, allowed_values: [multi, monolingual] }

  - name: Transcript
    description: >
      Lo que devuelve la transcripción en streaming: parcial o final, con cada
      palabra y su confianza. La forma de la confianza la fija la respuesta
      grabada de la prueba de contrato (PA-2): si el proveedor no la manda, va
      nula, **nunca cero**.
    attributes:
      - { name: is_final, type: boolean, required: true }
      - { name: text, type: string, required: true }
      - { name: words, type: "list WordHypothesis", required: true }
      - { name: language, type: Locale, required: false, constraint: "El idioma detectado en modo multi; nulo si el proveedor no lo dice." }

  - name: WordHypothesis
    attributes:
      - { name: text, type: string, required: true }
      - { name: start_s, type: decimal, required: true }
      - { name: end_s, type: decimal, required: true }
      - { name: confidence, type: decimal, required: false, min: 0, max: 1 }

  - name: AudioFormat
    description: El formato único que entregan los dos adaptadores de síntesis.
    attributes:
      - { name: encoding, type: enum, required: true, allowed_values: [pcm_s16le] }
      - { name: sample_rate_hz, type: integer, required: true }
      - { name: channels, type: integer, required: true, constraint: "1" }

  - name: VoiceAvailability
    description: >
      Si la voz de una aseguradora puede atender, y por qué no. Una
      configuración rota apaga la voz de esa aseguradora sin tumbar el proceso
      ni el chat (AC5.10.4).
    attributes:
      - { name: available, type: boolean, required: true }
      - { name: reason_key, type: CopyKey, required: false, constraint: "Obligatoria si no está disponible; la muestra la consola (U16)." }

  - name: ContractProbeResult
    description: Lo que mide la prueba de contrato de un proveedor (AC5.10.3).
    attributes:
      - { name: provider, type: string, required: true }
      - { name: format_ok, type: boolean, required: true }
      - { name: first_audio_ms, type: integer, required: false, constraint: "Con el texto fijo; nulo contra la respuesta grabada, que no mide red." }
      - { name: source, type: enum, required: true, allowed_values: [recorded, live] }
```

## Resumen

| Entidad | Dónde vive | Para qué |
| --- | --- | --- |
| `TenantVoiceConfig`, `VoiceRef`, `SpeechModelRef` | `tenant.yaml` | Qué proveedor, modelo y voz usa cada aseguradora |
| `Transcript`, `WordHypothesis` | Memoria del turno | Lo que dijo la persona, con confianza por palabra |
| `AudioFormat` | Código | Un solo formato de salida para las dos voces |
| `VoiceAvailability` | Proceso | Voz apagada con motivo, chat vivo |
| `ContractProbeResult` | Pruebas | Formato y latencia al primer audio |
