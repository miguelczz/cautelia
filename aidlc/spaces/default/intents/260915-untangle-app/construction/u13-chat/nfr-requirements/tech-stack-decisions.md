# Decisiones de stack — U13 `chat`

El lenguaje, el runtime, el gestor y el comprobador de tipos los fijó ADR-002 y no se
vuelven a discutir. El transporte HTTP y el armazón visual los fijó U6. Esta unidad
añade **una** dependencia de runtime y toma **dos** decisiones sobre piezas que ya
existen.

## La dependencia nueva: el detector de idioma

BR2.1 responde en el idioma del mensaje y BR2.2 exige que un "ok", una placa o un
nombre propio **no** cambien el idioma de la conversación. Eso segundo es el requisito
que decide la elección: la precisión sobre texto corto, no la precisión media.

Se consultaron tres candidatos el 2026-09-28, con su versión y su licencia leídas del
índice de paquetes y no supuestas:

| Paquete | Versión | Licencia | Por qué sí o por qué no |
| --- | --- | --- | --- |
| `lingua-language-detector` | 2.2.0 | Apache-2.0 | **Elegido.** Su propio resumen declara que está pensado para texto corto y mezcla de idiomas, que es exactamente el caso de BR2.2 |
| `langdetect` | 1.0.9 | Declara MIT en un campo y Apache en su clasificador | Rechazado por dos razones: la contradicción de licencia es un problema para un repositorio candidato a publicarse (D-017), y es un puerto de una biblioteca vieja con mala precisión en frases de dos palabras |
| `py3langid` | 0.4.0 | BSD-3-Clause | Rechazado: precisión buena en texto largo, pero no declara el caso de texto corto, que es el que aquí importa |

**Su justificación en una línea, como pide la práctica del equipo:** detecta el idioma
de un turno de chat; no la escribe la biblioteca estándar porque requiere un modelo
estadístico por idioma; Apache-2.0, que ya está en la lista de licencias admitidas.

Su licencia la verifica `mise run licenses:check` en cada corrida del guion de
verificación, y su atribución queda registrada en
`docs/reference/licencias-de-terceros.md` al añadirla. No se da por buena aquí: se
comprueba allí.

**Se usa en dos sitios y con dos umbrales distintos**, y conviene no confundirlos:
dentro del turno para elegir el idioma de la respuesta (BR2.1, BR2.2), y en el
corredor de evaluaciones para medir la adherencia de idioma de la agente (AC1.2.4).
El segundo uso no admite el respaldo del primero: si no hay señal, el turno conserva
su idioma, pero la métrica cuenta el turno como no medido antes que adivinarlo.

## Decisión 1 — El streaming va por SSE, no por WebSocket

Ya estaba escrito en el catálogo de unidades y se confirma con su razón: el chat es
unidireccional mientras la respuesta llega —la persona no manda nada a mitad de un
turno—, SSE viaja sobre HTTP normal sin un segundo protocolo que asegurar, y el
transporte de U6 ya lo sirve. Un WebSocket añadiría una superficie con su propia
autenticación y su propio modo de fallo para un caso que no lo necesita.

La voz sí necesita bidireccional, y por eso U16 tiene su propio transporte. Que el
chat no lo comparta es deliberado: la cuota, la clave y el modo de fallo de cada canal
quedan separados.

## Decisión 2 — Los contadores de los límites viven en la base, no en memoria

Podrían vivir en memoria del proceso, que sería más rápido. No lo hacen por dos
razones que son de esta unidad:

1. **Un reinicio del proceso reiniciaría el límite**, y el reinicio es un evento
   normal en el hospedaje gratuito que este proyecto usa. Un límite que se cae solo no
   es un límite.
2. **La regla dura pide el tope también en el proveedor** (BR3.3) precisamente porque
   un límite que vive solo en la aplicación falla abierto cuando lo que falla es la
   aplicación. Ponerlo además en memoria sería la versión más débil de las tres.

El costo es una consulta por mensaje, y PERF-U13.1 es el objetivo que vigila que esa
consulta no crezca: un milisegundo para los tres límites sumados.

## La tarea que esta unidad crea

`mise run test:u13` no existe todavía: **la crea esta unidad**, en el mismo commit que
su primera prueba, igual que hicieron las anteriores con la suya. Corre las pruebas
unitarias del canal y las de integración con la base efímera, y es el comando que
aparece en la columna de verificación de los objetivos de las tres tablas de esta
etapa. No entra en el guion de verificación: ese ya corre la suite entera.

## Lo que esta unidad no decide

- **El modelo y sus parámetros**: configuración versionada de U5 (ADR-006 fija el plan
  gratuito de Gemini para el chat público).
- **El armazón, el enrutador y el selector de idioma**: son de U6.
- **El hospedaje y la tubería de despliegue**: son del intent `infra` (D-014).
