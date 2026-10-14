# Preguntas de generación de código — U16 `voice-call`

Ninguna nueva. Las ocho decisiones de diseño están en
`../functional-design/functional-design-questions.md` y cubren lo que esta etapa
habría preguntado: el transporte (D1), el proceso (D2), dónde va el token (D3),
la definición del fin del habla (D4), cómo se corta el audio (D5), cómo se
distingue una interrupción del ruido (D6), por dónde se busca un caso al retomar
(D7) y dónde vive la consola (D8).

Quedan dos cosas para Miguel, ninguna bloqueante, las dos ya planteadas en ese
documento: cómo se ve la consola (Q1) y cuándo se mide en vivo contra los
proveedores (Q2).

## Una decisión que aparece al escribir el código

**El token de la llamada no reutiliza el enlace firmado de caso de U2.** Los dos
firman con HMAC y la tentación es compartir el camino, pero son cosas distintas:

- el enlace de caso (C-07) es un **portador en una URL**, con fila en la base,
  contador de canjes y revocación, y vive una hora;
- el token de la llamada no va en ninguna URL (BR1.4), no se guarda, no se canjea
  más de una vez por definición —el socket se abre una sola vez— y vive lo que
  tarda el navegador en conectar.

Reutilizar el primero para el segundo significaría una fila y una revocación que
nadie necesita, y —peor— un token de llamada que un día alguien pudiera pegar en
una barra de direcciones. `voice/tokens.py` firma con la misma clave y la misma
primitiva, y dice en su cabecera por qué es un módulo aparte.

## Sources

- `../functional-design/functional-design-questions.md`
- `app/backend/src/untangle/tenancy/visitor_access.py` — el enlace firmado de C-07

## Assumptions & Open Questions

None.
