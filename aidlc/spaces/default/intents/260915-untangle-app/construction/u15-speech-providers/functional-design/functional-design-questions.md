# Preguntas — Diseño funcional de U15 `speech-providers`

U15 es el motor de voz: transcribir con Deepgram `nova-3` en modo `multi` y
sintetizar con Catalina de Cartesia, con Aura-2 de Deepgram de respaldo. Las
interfaces ya las fija C-16 (`SpeechToText.stream` y `TextToSpeech.synthesize`);
los proveedores, ADR-007 y ADR-008; el gasto y el techo, U5. Quedan tres huecos.

**Cómo se respondieron.** Miguel delegó las decisiones de construcción en la
recomendación el 2026-09-21. Cada respuesta es la recomendada, con su razón.

---

## Q1 — Con qué se habla con cada proveedor

- A. **(Recomendada)** Con el protocolo que cada proveedor documenta como
  principal para streaming —WebSocket para transcribir y para sintetizar, HTTP
  para listar voces—, usando `websockets` y `httpx`, que el repositorio ya tiene
  y auditó. Es exactamente el camino que midió el experimento 1, y deja controlar
  el tiempo de cada byte, que es lo que decide NFR1.
- B. Los SDK oficiales de Deepgram y Cartesia. Son reconocibles, pero agregan
  dos dependencias de ejecución con sus propias capas de reintento y de tiempo,
  justo en el camino donde cada milisegundo cuenta, y no las midió nadie.
- X. Other (please specify)

**Por qué la A.** La regla del proyecto pide la forma documentada por el
proyecto oficial, y para streaming esa forma es el WebSocket: los dos
proveedores lo documentan como su API principal. Y es el único camino con
números propios.

[Answer]: A

---

## Q2 — Dónde vive la configuración de voz de cada aseguradora

- A. **(Recomendada)** En el bloque `voice` que ya tiene cada `tenant.yaml`
  (C-25), ampliado con proveedor, modelo y voz por idioma, principal y de
  respaldo. Un solo archivo por aseguradora, validado al arrancar.
- B. En una carpeta aparte, `app/config/tenants/<aseguradora>/voice/`, como
  sugería el catálogo de unidades. Parte la configuración de una aseguradora en
  dos sitios para cuatro campos.
- X. Other (please specify)

**Por qué la A.** C-25 ya puso la voz en `tenant.yaml`; abrir una segunda fuente
haría que quien cambie una voz tenga que buscar dónde.

[Answer]: A

---

## Q3 — Cómo se oye a Catalina al terminar la unidad (DP-14)

- A. **(Recomendada)** Un comando nuevo, `mise run voice:say`, que sintetiza una frase
  con la voz configurada de una aseguradora a través del propio adaptador del
  aplicativo, guarda el audio en `tmp/voice/` y lo reproduce si la máquina tiene
  reproductor. Gasta unos pocos caracteres del saldo gratuito y queda en el
  registro de gasto como cualquier otra llamada.
- B. Solo la prueba de contrato con respuesta grabada. No se oye nada.
- X. Other (please specify)

**Por qué la A.** Es la demostración que Miguel aprobó en DP-14, y prueba el
camino real: configuración, fábrica, adaptador, gasto y audio.

[Answer]: A
