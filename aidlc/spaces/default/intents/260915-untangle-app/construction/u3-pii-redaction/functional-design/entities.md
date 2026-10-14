# Modelo de datos — U3 `pii-redaction`

**Esta unidad no crea ninguna tabla y no guarda nada.** Su propia ficha lo dice
en una línea: *"Redacta sin guardar datos"*. Todo lo de abajo son objetos de
valor que viven en memoria durante una llamada y desaparecen con ella.

Eso no es un detalle de implementación: es el control. Un detector que guardara
lo que detecta se convertiría en el único sitio del sistema donde los datos
personales están juntos y en claro, que es exactamente lo que este componente
existe para evitar.

**Fuentes consumidas.** `../../../inception/units-generation/unit-of-work.md`
(U3), `../../../inception/units-generation/unit-of-work-story-map.md` (los nueve
criterios de US4.12 y US4.13),
`../../../inception/requirements-analysis/requirements.md` (FR7.3, FR12.3,
NFR11), `../../../inception/domain-design/components.md` (`PiiRedaction`) y
`../../../inception/contract-design/contract-summary.md` (C-13, y C-14 para el
punto único de salida del turno).

## Objetos de valor

```yaml
entities:
  - name: RedactionRequest
    persisted: false
    description: >
      Lo que entra al detector. No se registra en ningún sitio: si se registrara,
      el registro contendría el texto sin redactar.
    attributes:
      - name: text
        type: string
        required: true
        constraints: "Texto de origen externo. Nunca se concatena a un prompt (RT-1, RT-2)."
      - name: language
        type: enum
        required: true
        allowed_values: [es, en]
        constraints: >
          El idioma de la conversación, no el de quien lee. Decide **en qué
          idioma se escribe la etiqueta**, y nada más. NO elige qué reconocedores
          corren: corren los de los dos idiomas siempre, porque si solo corriera
          el juego del turno, una cédula dictada en español dentro de un turno en
          inglés saldría en claro y BR2.3 —que es compuerta dura— fallaría por
          construcción.
      - name: surface
        type: enum
        required: true
        allowed_values: [transcript, log, trace, export, report, live_partial]
        constraints: >
          De qué punto de salida viene. No cambia qué se tapa; cambia qué se
          mide y cómo se reporta un fallo.

  - name: DetectedEntity
    persisted: false
    description: >
      Un hallazgo del detector. Lleva dónde estaba, no qué era: el valor
      detectado nunca viaja fuera de la llamada.
    attributes:
      - name: entity_type
        type: EntityType
        required: true
      - name: start
        type: integer
        required: true
        min: 0
        constraints: "Desplazamiento en caracteres dentro de `text`."
      - name: end
        type: integer
        required: true
        constraints: "Mayor que `start`. Dos hallazgos del mismo tipo no se solapan."
      - name: recognizer_id
        type: string
        required: true
        references: Recognizer.id
        constraints: >
          Qué reconocedor lo encontró. Es lo que permite medir por reconocedor y
          no solo por tipo, y lo que hace visible que el respaldo esté tapando lo
          que a un reconocedor se le escapa.
      - name: confidence
        type: decimal
        required: true
        min: 0
        max: 1
    constraints:
      - "NUNCA lleva el valor detectado. Un hallazgo que cargara su valor convertiría cualquier registro de diagnóstico en una fuga."

  - name: Redacted
    persisted: false
    description: >
      El texto ya tapado, y el tipo que los puntos de salida exigen. Es **la
      mitad declarativa** del mecanismo de US4.12: un punto de salida que acepte
      `str` es un punto de salida sin redacción, y por eso no acepta `str`. La
      mitad que lo hace cumplir es el chequeo de BR1.8.
    attributes:
      - name: value
        type: string
        required: true
        constraints: >
          Lo construye el punto de redacción, y un chequeo de análisis estático
          prohíbe invocar su constructor en cualquier otro archivo (BR1.8). Los
          dos hacen falta: el tipo por sí solo **no** impide fabricar un
          `Redacted` falso, porque `NewType` no existe en tiempo de ejecución y
          `Redacted(texto_sin_tapar)` es una llamada que el comprobador de tipos
          acepta. Decirlo así es el hallazgo R-02 de la revisión; dejarlo en
          "no compila" habría sido escribir un control que no existe.
    constraints:
      - "Es irreversible: no existe ninguna vía para recuperar el original a partir de él. No hay bóveda de tokens y no se guarda correspondencia."
      - "El dato real que el caso necesita vive en sus campos estructurados (AC4.12.1), no aquí."

  - name: RedactionReport
    persisted: false
    description: >
      El conteo que alimenta la medición de NFR11. Se produce aparte del texto
      redactado, para que medir nunca obligue a conservar lo medido.
    attributes:
      - name: language
        type: enum
        required: true
        allowed_values: [es, en]
      - name: counts_by_type
        type: map<EntityType, integer>
        required: true
        constraints: >
          Una entrada por tipo, también con cero. Un tipo ausente del informe y
          un tipo con cero hallazgos son cosas distintas, y confundirlas esconde
          un reconocedor que dejó de cargar.
      - name: counts_by_recognizer
        type: map<string, integer>
        required: true
      - name: fallback_count
        type: integer
        required: true
        constraints: >
          Los hallazgos de la regla de respaldo, en su propia cifra. Nunca se
          suman a la de un tipo: un respaldo que dispara mucho es la señal de que
          un reconocedor se rompió, y sumarlo la borraría.
    constraints:
      - "NUNCA se publica como promedio combinado de los dos idiomas (P12, AC4.13.3)."

  - name: EntityType
    persisted: false
    description: >
      El conjunto cerrado de lo que se tapa. Cerrado a propósito: la etiqueta que
      ve una persona sale del catálogo de textos, y una clave sin valor la
      detecta el chequeo de paridad del catálogo.
    allowed_values:
      - license_plate      # placa; reconocedor propio de esta unidad
      - national_id        # cédula o documento; reconocedor propio
      - phone              # teléfono; reconocedor propio
      - policy_number      # número de póliza; reconocedor propio
      - person             # nombre de persona; del detector de base
      - email              # del detector de base
      - location           # dirección o lugar; del detector de base
      - unclassified       # lo que solo atrapó la regla de respaldo (Q3)

  - name: Recognizer
    persisted: false
    description: >
      La declaración de un reconocedor. Versionada en configuración, no escrita
      en el código, para que añadir un formato no sea un cambio de lógica.
    attributes:
      - name: id
        type: string
        required: true
        unique: true
      - name: entity_type
        type: EntityType
        required: true
      - name: language
        type: enum
        required: true
        allowed_values: [es, en]
        constraints: "Un reconocedor sirve a un idioma. Uno que dijera servir a los dos escondería que en uno de ellos no funciona."
      - name: mechanism
        type: enum
        required: true
        allowed_values: [pattern, context, checksum, model]
        constraints: >
          Declarado, porque U21 exige que el segundo detector no comparta
          mecanismo con este (AC4.14.1). Sin esta declaración esa comprobación no
          se puede hacer.
      - name: source
        type: string
        required: true
        constraints: "De dónde salió el formato, con su referencia. Un reconocedor sin procedencia no se puede revisar."
    location: >
      `app/backend/src/untangle/compliance/redaction/recognizers/<idioma>.yaml`,
      un archivo por idioma, versionado y en YAML porque lo escribe una persona
      (CD-4). La ruta es parte del contrato y no un detalle: U21 la lee **como
      archivo** para comprobar AC4.14.1, sin importar este módulo (BR4.6).

  - name: OutputSink
    persisted: false
    description: >
      Un punto de salida declarado. La lista completa vive en un solo sitio, que
      es lo que hace comprobable el criterio AC4.12.2.
    attributes:
      - name: name
        type: string
        required: true
        unique: true
      - name: surface
        type: enum
        required: true
        allowed_values: [transcript, log, trace, export, report, live_partial]
      - name: owning_unit
        type: string
        required: true
        constraints: "U3 declara la lista; cada unidad dueña implementa el suyo exigiendo `Redacted`."
    constraints:
      - "Un punto de salida que no esté en esta lista y escriba hacia afuera hace fallar la regla de importación (AC4.12.2)."

relationships:
  - "Un RedactionRequest produce exactamente un Redacted y, si se pide, un RedactionReport."
  - "Un Redacted resume cero o más DetectedEntity; las entidades no sobreviven a la llamada."
  - "Un DetectedEntity nombra al Recognizer que lo encontró."
  - "Un OutputSink solo acepta Redacted; es la única relación que esta unidad impone al resto del sistema."
```

## En palabras

Siete objetos, ninguno guardado. El que hace el trabajo estructural es
**`Redacted`**: no es una envoltura decorativa sino la forma de convertir una
regla de disciplina —"acuérdate de redactar antes de escribir"— en algo que una
herramienta comprueba sola. Un punto de salida pide `Redacted`, y un chequeo de
análisis estático impide fabricar uno fuera del punto de redacción.

**Hacen falta los dos, y esto es lo que la revisión corrigió.** El tipo solo no
basta: `NewType` se borra en tiempo de ejecución, así que
`Redacted(texto_sin_tapar)` compila sin queja. Un diseño que dejara la garantía
apoyada en el tipo estaría escribiendo un control que no existe, que es
exactamente el error que U1 cometió con la espera de tres días.

Los otros seis existen para que la medición sea honesta. **`DetectedEntity` no
lleva el valor que detectó**, porque un hallazgo que cargue su valor convierte
cualquier volcado de diagnóstico en la fuga que el componente evita.
**`RedactionReport` cuenta el respaldo aparte**, porque el respaldo tapando
mucho es la señal de que un reconocedor dejó de funcionar, y sumarlo a su tipo
borraría justo esa señal. Y **`Recognizer` declara su mecanismo**, porque U21
tiene que poder comprobar que su detector no comparte mecanismo con este; sin la
declaración, esa comprobación sería una afirmación en un documento.

Una consecuencia que conviene tener presente al leer una conversación de la
demostración: el nombre del asegurado aparece **tapado en la transcripción** y
**en claro en los campos del caso**. No es una inconsistencia, es AC4.12.1: la
transcripción es texto libre que sale hacia logs, trazas y reportes, y el campo
estructurado es el dato que el caso necesita, guardado donde la tabla de
almacenes fija su protección.
