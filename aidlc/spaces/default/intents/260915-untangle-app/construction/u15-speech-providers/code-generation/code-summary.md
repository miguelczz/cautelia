# Resumen del código — U15 `speech-providers`

U15 deja el motor de voz del aplicativo:
- **Transcripción:** Deepgram `nova-3` en modo `multi`, por WebSocket.
- **Voz principal:** Catalina, en Cartesia `sonic-3.6`, por WebSocket.
- **Voz de respaldo:** Aura-2 de Deepgram, por HTTP en streaming.

Cada proveedor queda detrás de su interfaz, sin SDK. La configuración de voz es
por aseguradora, y la voz queda conectada en la raíz de composición, lista para
U16. Hay dos comandos a mano: uno para oír a Catalina y otro para medir la
latencia contra el proveedor real. Se construyó por la rama determinista, en dos
tandas: los pasos 1 a 7 en `11fec51` y los pasos 8 a 11 en `e840358`.

## Resultados

| Compuerta | Resultado |
| --- | --- |
| `mise run test:u15` | 113 pruebas en verde; una guardia comprueba que ninguna abre conexión de red |
| Integración de U15 | 3 pruebas de la restricción del libro de gasto |
| `mise run cov` | **88,05 %** agregado, sin exclusiones nuevas; `voice_cli` al 85 % |
| `mise run lint` | En verde, 26 contratos de importación; los 5 avisos de ESLint en `app/frontend/vite.config.ts` ya estaban |
| `mise run types`, `schema:check`, `migrate:check` | En verde |
| `mise run contracts:check` | En verde después del commit de cada tanda |
| GitHub Actions (`verify`) | En verde sobre `11fec51` (pasos 1 a 7) y sobre `e840358` (pasos 8 a 11), con los 9 pasos de `scripts/verify.sh` |

## Medido en vivo

**Latencia al primer audio (TECH-U15.2).** Salió de la captura única del 2026-09-21,
con un texto fijo y contando la apertura de la conexión. No tiene umbral propio:
la meta del turno es NFR1, de U16.

| Voz | Español | Inglés |
| --- | --- | --- |
| Catalina (Cartesia `sonic-3.6`) | 841 ms | 697 ms |
| Aura-2 (`aura-2-celeste-es` / `aura-2-thalia-en`) | 666 ms | 549 ms |

`voice:say` tardó 993 ms al primer audio con la conexión en frío. Esa cifra
incluye leer el techo en el registro temporal.

**Confianza por palabra (PA-2).** Deepgram la manda en streaming: llegó en 11 de
11 palabras en español y en 9 de 9 en inglés. El idioma detectado coincidió en
los dos casos.

**Gasto de la unidad, a precio de lista**, calculado con la misma tabla del libro
de gasto:

| Corrida | Consumo | USD |
| --- | --- | --- |
| Captura única (`voice:contract-live --record`) | Cartesia 148 caracteres, Aura-2 94 caracteres, transcripción 6,16 s | 0,011165 |
| `voice:say --no-play` (Catalina, Stonecroft, español) | Cartesia 54 caracteres | 0,002700 |

La consola de Deepgram muestra **0,07526 USD** gastados entre el 2026-09-14 y el
2026-09-21, todo dentro de la ventana de 90 días que empieza el 2026-09-16. Esa
cifra suma los experimentos anteriores y la captura, y la leyó Miguel en
*Billing → Spend*. Es la que alimenta el registro permanente de la pasada de
publicación.

## Decisiones del conductor durante la generación

1. **Nombres de las claves:** `UNTANGLE_VOICE_DEEPGRAM_API_KEY` y
   `UNTANGLE_VOICE_CARTESIA_API_KEY`. Las dos pertenecen al uso `voice` y se leen
   solo por `Settings`. El `.env` local se renombró cambiando solo el nombre de
   la variable, sin que ningún valor saliera en pantalla. El guion
   `scripts/poner-claves-de-voz.py` ya escribe los nombres nuevos.
2. **La voz de Catalina está en los tres `tenant.yaml`** (CG-U15-5). Nada lee ya
   la línea `CARTESIA_VOICE_ID` del `.env`.
3. **La voz de respaldo en inglés es `aura-2-thalia-en`** (CG-U15-2). Se comprobó
   contra la lista de modelos de Deepgram el 2026-09-21. Es femenina y clara, el
   perfil más cercano a `aura-2-celeste-es`. Ninguna voz de Aura-2 habla los dos
   idiomas, así que aplica la excepción D17.
4. **Ningún audio de voz entra al repositorio.** Las 15 respuestas grabadas
   conservan la forma exacta de los mensajes, con 20 ms de silencio en lugar del
   audio, y no llevan clave ni identificador de cuenta. Ocho son capturadas y
   siete están armadas con la forma documentada del proveedor; estas llevan en su
   cabecera la marca `documented-not-captured`.
5. **Registro de gasto de los comandos a mano:** `voice:contract-live` y
   `voice:say` corren con `--ledger ephemeral`, un registro temporal que empieza
   en cero y lo dice al arrancar. El corte real lo hace el proveedor: saldo
   prepagado sin recarga en Deepgram y cupo gratuito mensual en Cartesia. Sin
   base, el aplicativo sigue fallando cerrado. El registro permanente quedó en
   `inception/delivery-planning/pasada-de-publicacion.md`.
6. **`ProviderName.FALLBACK_TTS`, retirado.** Era la reserva de U5 antes de que
   ADR-008 eligiera Aura-2. La migración `u15_speech_0001_provider_check`
   comprueba primero que ninguna fila lo use y después estrecha la restricción.
   Una prueba de integración compara esa restricción con el enum.
7. **Filas de tope (PA-9.2):**
   - **Deepgram, `prepaid_balance`:** comprobada el 2026-09-21, todavía sin cifra
     de saldo.
   - **Cartesia, `monthly_cap`:** 20.000 créditos al mes del plan gratuito,
     según su página pública de precios.

   `schema:check` ahora exige que todo proveedor de voz tenga su fila vigente.

## Desviaciones declaradas

- **El protocolo de voz salía del adaptador.** El comando de voz armaba la
  consulta de voces con el protocolo de los dos proveedores. Esa consulta pasó a
  un `catalog.py` en cada adaptador, y un contrato de importación nuevo,
  `protocolo-de-voz-solo-en-su-adaptador`, lo prohíbe. Cada contrato nuevo se
  probó con una violación plantada y retirada.
- **Excepción en un contrato de importación.** En `sdk-solo-en-su-adaptador` se
  exceptuó solo la arista `adapters.wire -> websockets`, con aviso si esa
  excepción deja de coincidir. No se usó `allow_indirect_imports`, que dejaría
  de comprobar por cadena los demás SDK.
- **El techo corta por el tope absoluto del proyecto:** 5 USD, una llamada sin
  valorar o un acumulado ilegible. Los carriles del público y la elección entre
  la voz principal y la de respaldo son de U17.
- **Menores:**
  - Se usa `httpx2`, el cliente HTTP de ejecución del proyecto.
  - La transcripción recibe PCM de 16 bits, mono, a 24 kHz, el mismo formato
    que entrega la síntesis.
  - Se piden parciales (`interim_results`).
  - El idioma de una transcripción es nulo si el proveedor no lo dice.
  - `ProviderEntry` ganó `voices`, y `VoiceRef` y `Transcript` se ampliaron; no
    tenían consumidores.
  - `voice:say` guarda WAV (la misma muestra con cabecera) y acepta `--no-play`
    y `--out-dir`.
- **`voice:contract-live` imprime la latencia y no la escribe en un archivo.**
  Las cifras de este resumen salen de su corrida.
- **Captura sobre una base efímera.** La base que nombra el `.env` no es la del
  aplicativo, así que la captura pasó por el techo y el registro reales montados
  sobre una base efímera con las mismas migraciones.

## Lo que queda abierto

- **Cifra del saldo de Deepgram, resuelta el 2026-09-21:** Miguel leyó en
  *Billing → Overview* 199,92 USD de crédito con la recarga automática apagada,
  y la cifra quedó en `cap_value` de la fila de Deepgram en
  `app/config/providers/prices.yaml`.
- **Topes de Gemini:** se comprobaron el 2026-09-17, así que `schema:check` se
  pondrá rojo el 2026-10-18 si nadie vuelve a mirarlos. Es la compuerta
  funcionando, no un fallo.
- **`FALLBACK_TTS` sigue nombrado** en `u5-provider-platform/functional-design/entities.md`,
  un documento de U5, que ya está cerrada. El código ya no lo tiene.
- **Demostración audible de B18, hecha el 2026-09-21:** Miguel corrió
  `mise run voice:say -- --tenant stonecroft` y confirmó que suena como Catalina.
  Fueron 54 caracteres, 0,0027 USD, y 909 ms al primer audio.

## Archivos

79 rutas del espacio de trabajo, listadas en `source-manifest.json`:
- los adaptadores `providers/adapters/{deepgram,cartesia}/`;
- las piezas comunes de transporte y techo;
- la plataforma de voz y los comandos en `server/`;
- una migración;
- la configuración de voz de las tres aseguradoras, los precios y topes, y el
  catálogo de copy con su espejo en la interfaz;
- 11 módulos de prueba con 15 respuestas grabadas;
- `mise.toml`, `.env.example` y los dos guiones de voz.

## Trazabilidad

`traceability.json` cubre 28 identificadores:
- los 9 criterios de US5.10 y US5.11;
- las 15 reglas;
- los 4 `NFRx.y` de U15.

24 apuntan a un archivo que existe. AC5.11.1, AC5.11.2, AC5.11.3 y AC5.11.5 son
`N/A` porque son historias de U17, que va completa a la pasada de publicación.
U15 aporta el adaptador de respaldo que usan (BR4.2).
