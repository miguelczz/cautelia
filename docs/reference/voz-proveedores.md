# Una sola voz paisa en dos idiomas: viabilidad y proveedores

**Pregunta de Miguel (2026-09-15):** ¿se puede tener exactamente la misma voz femenina con acento paisa en español y en inglés, dentro de los tiers gratuitos? Si no, se miran alternativas.
**Respuesta corta:** sí se puede, en dos proveedores comerciales y en un modelo abierto. Lo que no cabe en los tiers gratuitos es el volumen: alcanzan para las evals de audio, las demos y el video, no para iterar a diario con la voz paisa. Detalle y plan abajo.

## 1. Lo que se verificó

| Proveedor | Misma voz en ES y EN | Voz paisa disponible | Tier gratuito | Restricciones del gratuito | Plan de pago mínimo |
| --- | --- | --- | --- | --- | --- |
| **ElevenLabs** | Sí. Multilingual v2, v3 y Flash v2.5 conservan identidad y acento original de la voz en 28 a 70+ idiomas; una voz de Medellín habla inglés con acento colombiano [E1][E2] | Sí, en la Voice Library (comunidad): "Valentina - Conversational Medellin" (`J4vZAFDEcpenkMp3f3R9`), "Sofía - Soft & Warm" (acento suave de Medellín, `b2htR0pMe28pYwCY9gnP`), "Marcela" (`KoIf2KgeJA8uoGcgKIao`, `ebdrtet3LErOzR0r2i60`), "Medellin - Conversational" (`3Fx71T889APcHRu4VtQf`) [E3] | 10.000 créditos al mes: unos 20 minutos con Flash v2.5 (0,5 créditos por carácter) o 10 con Multilingual v2 [E4] | Uso no comercial con atribución. **"Las voces de la Voice Library no están disponibles por API para usuarios del tier gratuito"** [E5]; algunas voces exigen plan de pago | Starter: 6 USD al mes, 30.000 créditos, licencia comercial, clonado instantáneo, voces de biblioteca por API [E4] |
| **Cartesia** | Sí. Las voces de Sonic son nativamente multilingües (44 idiomas) y hay localización que conserva identidad [C1] | Probable: en enero de 2026 añadió 9 voces en español (mexicano, colombiano, castellano) y filtros de locale como `es-CO` [C2]. Falta escuchar si hay una femenina que suene paisa | 20.000 créditos al mes (unos 27 minutos de TTS) y 1 USD de saldo para agentes; sin tarjeta [C3] | No comercial; sin clonado. Falta confirmar que las voces de biblioteca se usen por API en el gratuito | Pro: 5 USD al mes, 100.000 créditos (unos 133 minutos), licencia comercial, clonado instantáneo [C3] |
| **Chatterbox Multilingual** (abierto, Resemble) | Sí, por diseño: clonado zero-shot desde 5 a 20 segundos de referencia en 23 idiomas, español incluido [O1] | Solo si se clona a una mujer paisa que dé consentimiento escrito (la licencia exige permiso sobre la referencia) [O1] | Gratis, MIT, sin topes | Corre en la máquina del autor (GPU recomendada; unos 200 ms de latencia); Miguel prefiere no depender de modelos locales | Ninguno |
| **Kokoro** (abierto) | No: no clona; tres voces en español latinoamericano genérico, distintas de las de inglés | No (latinoamericano genérico) | Gratis, CPU, Apache 2.0 | No sirve para "misma voz"; sirve para iterar barato | Ninguno |

## 2. Qué significa para el proyecto

**Volumen.** En una llamada de 4 minutos la agente habla unos 2 minutos, unos 1.800 caracteres. Con ElevenLabs gratuito (Flash) caben unas 11 llamadas al mes; con Cartesia gratuito, unas 11 a 13. Sumados, unas 20 a 25 llamadas al mes con la voz paisa. Eso cubre el golden set de audio (20 grabaciones), las validaciones del día 30 y el video, pero no la iteración diaria de desarrollo.

**Licencia.** Ambos gratuitos son no comerciales; ElevenLabs exige atribución. Un portafolio que no vende nada encaja; el README y el video llevan la atribución.

**El obstáculo real.** La voz paisa que ya existe está en ElevenLabs, y su tier gratuito no la expone por API. Cartesia sí tiene voces colombianas y su gratuito probablemente sí las expone, pero hay que escucharlas.

## 3. Plan propuesto (D-016)

1. **Semana 1 del esqueleto: prueba ciega.** Generar la apertura y dos confirmaciones (español e inglés) con: las cinco voces de Medellín de ElevenLabs desde la interfaz web (gratis, sin API), las voces `es-CO` femeninas de Cartesia, y, si Miguel tiene una voluntaria paisa, un clon con Chatterbox. Tres personas de Medellín califican de 1 a 5 "suena de Medellín" y "suena real". Se adopta la primera que promedie 4 o más.
2. **Si gana una voz de Cartesia:** se usa el tier gratuito de Cartesia por API. Costo cero. Los créditos se reservan para evals de audio, demos y video.
3. **Si gana una voz de ElevenLabs:** hace falta Starter (6 USD al mes) durante los dos meses en que la voz importa (golden set de audio y video): unos 12 USD, por encima del tope de 5 USD. Decisión de Miguel: subir el tope a unos 20 USD en total (LLM más voz) o quedarse con la mejor voz de Cartesia.
4. **En cualquier caso, iteración diaria con TTS barato:** Kokoro en local (CPU, gratis) o una voz genérica del proveedor, para no gastar créditos de la voz paisa en pruebas. La voz paisa entra solo en evals, demos y video. Esto se escribe como regla en el playbook de construcción.
5. **Plan C:** clonado de una voz paisa con consentimiento escrito, con Chatterbox (gratis, local) o con Cartesia Pro / ElevenLabs Starter (5 a 6 USD), si ninguna voz de biblioteca pasa la prueba ciega.
6. **Modelo de TTS por proveedor:** en ElevenLabs, Flash v2.5 (latencia y mitad de créditos); en Cartesia, Sonic (40 a 90 ms al primer audio). Ambos conservan la identidad al cambiar de idioma con el parámetro `language`.

## 4. Verificaciones pendientes (semana 1)

- Escuchar las voces `es-CO` femeninas en play.cartesia.ai/voices y confirmar acceso por API en el plan gratuito.
- Confirmar en ElevenLabs cuáles de las cinco voces de Medellín son de uso libre en planes de pago (algunas exigen plan).
- Confirmar que Chatterbox Multilingual clona una referencia en español y la hace hablar inglés con la misma identidad (cross-lingual) en la máquina del autor.

## Fuentes

- [E1] ElevenLabs, "Eleven Multilingual v2" (misma voz en cerca de 30 idiomas, conserva acento): https://elevenlabs.io/blog/elevenlabs-comes-out-of-beta-and-releases-eleven-multilingual-v2-a-foundational-ai-speech-model-for-nearly-30-languages
- [E2] Deepgram, "Languages vs Accents in ElevenLabs: Supported Models 2026" (el acento original se mantiene entre idiomas): https://deepgram.com/learn/elevenlabs-languages-vs-accents-support
- [E3] json2video, catálogo de voces de ElevenLabs en español con IDs (voces de Medellín): https://json2video.com/ai-voices/elevenlabs/languages/spanish/
- [E4] ElevenLabs, "Pricing" (Free 10k créditos; Starter 6 USD, 30k créditos, licencia comercial, clonado): https://elevenlabs.io/pricing ; TextToLab, créditos por carácter por modelo: https://texttolab.com/blog/elevenlabs-pricing
- [E5] ElevenLabs, "Voice Library" (documentación: voces de biblioteca no disponibles por API en el tier gratuito; no consumen slots): https://elevenlabs.io/docs/eleven-creative/voices/voice-library
- [C1] Cartesia, "All languages" y "Sonic" (44 idiomas, localización conservando identidad): https://cartesia.ai/all-languages , https://www.cartesia.ai/sonic
- [C2] Cartesia, "Changelog 2026" (9 voces en español incluidas colombianas; alias de locale): https://docs.cartesia.ai/changelog/2026 ; biblioteca: https://play.cartesia.ai/voices
- [C3] Cartesia, "Pricing" (Free 20k créditos, 1 USD agentes, no comercial, sin clonado; Pro 5 USD, 100k créditos, comercial, clonado): https://cartesia.ai/pricing
- [O1] Resemble AI, "Chatterbox" (MIT, 23 idiomas, clonado zero-shot 5 a 20 s, ~200 ms, permiso sobre la referencia): https://www.resemble.ai/learn/models/chatterbox
