# Experimentos de la semana 1

Cuatro experimentos de tres días que el PRD pone en paralelo con la Incepción
(Segmento 13, semana 1). Existen para que las decisiones de arquitectura de
Domain Design se tomen con cifras y no con opinión.

**Son desechables.** No son código del aplicativo, no siguen sus convenciones y
no se reutilizan en Construcción. Usan solo la biblioteca estándar de Python, así
que no hay nada que instalar. Lo que sí se conserva son sus resultados: cada
experimento escribe un JSON en su carpeta `results/`, que se versiona como
evidencia de la decisión.

## Qué responde cada uno

| Experimento | Pregunta | Riesgo o supuesto del PRD | Qué necesita de ti | Estado |
| --- | --- | --- | --- | --- |
| [01-voice-graph](01-voice-graph/README.md) | ¿La voz se integra con un grafo explícito cediendo el turno en menos de 300 ms, y aguanta una llamada en hospedaje gratuito? | R10, R2, A1 | Nada todavía | Plan escrito; el código viene después |
| [02-flash-lite](02-flash-lite/README.md) | ¿Qué Flash-Lite extrae bien y responde rápido, y cuánto costaría por llamada? | R3, A2 | Nada | Corrido cuatro veces; tabla de decisión en su README |
| [03-spanish-stt](03-spanish-stt/README.md) | ¿Deepgram entiende español paisa y los datos dictados (placas, cédulas, teléfonos)? | R4 | Nada | Corrido con la voz de Miguel; tabla de decisión en su README |
| [04-paisa-voices](04-paisa-voices/README.md) | ¿Qué voz suena de Medellín y real, en los dos idiomas, y con qué latencia? | R4, A3, D-016 | Opcional: dos personas más de Medellín que escuchen | Con una persona: Catalina (Cartesia) pasa la regla y conserva su identidad en inglés; ElevenLabs bloqueado en el plan gratuito |

## Lo que tienes que hacer tú

1. **Hecho el 2026-09-16.** **Abrir las cuentas gratuitas** y crear una clave
   nueva en cada una, solo para estos experimentos:
   - Google AI Studio (`aistudio.google.com`): clave de la API de Gemini. Usa un
     proyecto **sin facturación activada**; con facturación, las llamadas se
     cobran. Las claves nuevas empiezan con `AQ.`: es el formato vigente.
   - Deepgram (`console.deepgram.com`): trae crédito gratuito para empezar.
   - Cartesia (`play.cartesia.ai`).
   - ElevenLabs (`elevenlabs.io`): opcional. Confirmado el 2026-09-16: el plan
     gratuito no deja usar por API las voces de su biblioteca (error 402, sin
     cobro).
2. **Hecho el 2026-09-16.** **Copiar `spikes/.env.example` como `spikes/.env`** y
   pegar ahí las claves. Ese archivo no se versiona.
3. **Hecho el 2026-09-16.** **Grabar** las frases del experimento 3 (unos 15
   minutos) y, si puedes, pedirle a una o dos personas de Medellín que graben
   también.
4. **Hecho el 2026-09-16, con una persona.** **Escuchar a ciegas** las voces del
   experimento 4, idealmente con tres personas de Medellín.

## Reglas

- **Las claves viven solo en `spikes/.env`.** Nunca en el chat, en el código ni en
  los resultados. Al terminar los experimentos, bórralas o rótalas en cada
  proveedor.
- **Sin cobros ni renovaciones.** Todo corre en planes gratuitos, sin tarjeta
  guardada, sin recarga automática, sin excedentes y sin suscripción. Si un
  proveedor pide tarjeta o muestra un cobro, se detiene el experimento y se
  decide antes de seguir.
- **Si algo se acaba, se para.** Cuando se agota una cuota o un saldo, el script
  no reintenta: muestra un aviso `alto:` con lo que se acabó y el mensaje del
  proveedor. Se revisa qué fue y se decide si vale la pena recargar; nunca se
  recarga solo.
- **Ningún audio entra a git.** Las grabaciones son voz de personas reales y las
  muestras sintetizadas pueden tener restricciones de licencia: sus carpetas
  están ignoradas. Si grabas a otra persona, pídele permiso para enviar su voz a
  Deepgram.
- **Los datos son ficticios.** Nombres, placas, cédulas y pólizas del guion son
  inventados; los teléfonos usan el rango 555-01XX reservado para ficción.

## Cómo quedan las cuentas

Estos ajustes los haces tú en cada proveedor. Revisados en su documentación el
2026-09-16.

| Proveedor | Cómo debe quedar | Dónde se revisa | Si se acaba |
| --- | --- | --- | --- |
| Google AI Studio | Proyecto en nivel gratuito: sin cuenta de facturación, sin prepago y sin recarga automática. Un proyecto gratuito no se puede cobrar | `aistudio.google.com`, página Projects, columna Billing Tier | Error 429 de cuota diaria; la cuota vuelve al día siguiente |
| Deepgram | Sin método de pago guardado. En Pay As You Go la recarga automática viene activada por defecto | `console.deepgram.com`, sección Billing | La petición se rechaza. El crédito gratuito vence un año después del registro |
| Cartesia | Plan Free, sin tarjeta y con Overages apagado: con Overages encendido las peticiones siguen y se cobran aparte | `play.cartesia.ai/subscription` | Las peticiones fallan hasta que se renuevan los créditos del mes |
| ElevenLabs | Plan Free, sin Pay As You Go ni Auto Top Up, y la clave con permisos mínimos, límite de créditos y vencimiento | `elevenlabs.io`, Subscription y la página de la clave | Error de cuota; los créditos gratuitos se renuevan cada mes |

## Cómo se usan los resultados

Cuando corras un experimento, avísame. Leo su JSON y escribo la tabla de decisión
con las cifras, que entra a Domain Design como evidencia de la decisión de
arquitectura correspondiente.
