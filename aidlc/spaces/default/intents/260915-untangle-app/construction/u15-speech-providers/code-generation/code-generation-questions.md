# Preguntas — Generación de código de U15 `speech-providers`

## Plan Approval

Cubre `code-generation-plan.md` con su contrato de pruebas embebido, y
`unit-test-instructions.md`.

**Qué se construye:** el motor de voz del aplicativo. Transcribir con Deepgram,
hablar con Catalina de Cartesia y con Aura-2 de respaldo, cada uno detrás de su
interfaz, con la configuración de voz por aseguradora, sus pruebas de contrato y
el comando para oír a Catalina. Trece pasos por la rama determinista.

**Lo que gasta:** dos cosas llaman a los proveedores reales, y ninguna corre en
GitHub Actions. La captura única de las respuestas grabadas y el comando para oír
a Catalina, cada uno con unos pocos caracteres o segundos del saldo gratuito,
que quedan en el registro de gasto.

**Cinco decisiones que el plan toma**, en el modo ligero:

- **CG-U15-1** — Las dos voces entregan el mismo formato de audio: PCM de 16
  bits, mono, 24 kHz.
- **CG-U15-2** — La voz de respaldo en inglés se elige entre las de Aura-2 en
  inglés, comprobada contra la lista del proveedor.
- **CG-U15-3** — Las respuestas grabadas se capturan una sola vez.
- **CG-U15-4** — Los campos nuevos de voz son opcionales: si faltan, la voz de
  esa aseguradora se apaga con su motivo y el chat sigue.
- **CG-U15-5** — El identificador de la voz de Catalina pasa del `.env` a la
  configuración versionada, porque no es un secreto.

[Approval Fingerprint]: sha256:v3:3b2e97bc288c6ce7ade044ca7f4b2b40dfdc78f3a3f04df5d76216484bcdd23f
[Planned Source]: 47913a840a3927f8e46c6a84b48ec68dc80e9e5df4c0697b3af10492b7714f8d

- "Approve Plan" — proceed to code generation
- "Request Changes" — revise the plan

[Answer]: Approve Plan
