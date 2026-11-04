"""Las frases que el navegador no necesita: solo las usa el servidor (PERF-U6.1).

El catalogo que viaja al navegador es lo mas pesado de lo que se descarga antes de la
pagina de espera, y el umbral de esa prueba (200.000 bytes) no se toca. Muchas frases
las compone y emite el servidor ya resueltas, en el idioma del turno: las de la captura,
las de la voz hablada, las de las reglas, los pasos del ajustador. El navegador nunca las
pide por clave, asi que llevarlas es peso muerto.

**El criterio es uno y se comprueba** (`check_server_only_keys`, regla `SO-1`, dentro de
`mise run copy:check`): una clave solo puede estar aqui si ningun archivo de la interfaz la
escribe como literal. Eso cubre las dos formas en que una clave llega a una pantalla:
`t("clave")` directo y las tablas de claves que el servidor manda como dato
(`chat-copy.ts`, `voice-copy.ts`, `inbox-labels.ts`, `tenant-characters.ts`), que tambien
las escriben literales (BR3.4). Y el reves: una excepcion que la interfaz ya no escribe es
una excepcion vencida y el chequeo tambien la nombra.

Una clave solo-servidor deja de ser parte de `CopyKey` en `copy-keys.ts`: escribirla en la
interfaz es ademas un error de tipos antes de compilar. Si una pantalla nueva necesita una
de estas frases, se quita su prefijo (o se agrega la clave a `BROWSER_KEY_EXCEPTIONS`) en el
mismo cambio, y el modulo generado la vuelve a llevar.

En la duda, la familia se queda fuera de esta lista: solo entra la que se comprobo.
"""

from __future__ import annotations

from types import MappingProxyType

#: Prefijo de clave -> por que solo la usa el servidor. Un prefijo casa la clave igual a el o las que cuelgan de el (`prefijo.`).
SERVER_ONLY_PREFIXES = MappingProxyType(
    {
        # La captura (U6..U12): el servidor elige la pregunta, el acuse, la lectura de
        # confirmacion y el cierre, y los manda como `text` del evento del turno.
        "intake.question": "pregunta que el servidor elige y manda como texto del turno",
        "intake.closing": "cierre del reporte que el servidor compone",
        "intake.readback": "lectura de confirmacion que el servidor compone",
        "intake.policy": "frases de la poliza dentro de la captura, compuestas en el servidor",
        "intake.block": "bloques de la captura compuestos en el servidor",
        "intake.claim_item": "renglones del reclamo compuestos en el servidor",
        "intake.social": "respuestas sociales del nodo de captura",
        "intake.ack": "acuses del nodo de captura",
        "intake.transition": "transiciones del nodo de captura",
        "intake.unfinished": "frase del caso sin terminar compuesta en el servidor",
        "intake.emergency": "frase de emergencia que el servidor emite en la captura",
        "intake.identity": "frase de identidad del nodo de captura",
        "intake.correction": "frase de correccion del nodo de captura",
        # El motor de reglas y la cobertura: el servidor escribe la explicacion.
        "rules.explain": "explicacion de una regla que escribe el motor, no la pantalla",
        # Pasos del ajustador de IA: el servidor escribe el texto del paso; el panel
        # solo resuelve el titulo (ver BROWSER_KEY_EXCEPTIONS).
        "adjuster.step": "texto de cada paso que escribe el proceso del ajustador",
        # El chat: respuestas fijas que el servidor emite ya resueltas.
        "chat.rigid": "respuestas rigidas del recorrido por reglas",
        "chat.decision": "frases de la decision que el servidor emite",
        "chat.resume": "frases de reanudacion que el servidor emite",
        "chat.offer": "ofertas que el servidor emite",
        "chat.closed_case": "frase del caso cerrado que el servidor emite",
        "chat.off_topic": "frases de fuera de tema que el servidor emite",
        # La cotizacion y la redaccion: texto de salida del servidor.
        "quote.band": "frases de la cotizacion compuestas en el servidor",
        "quote.reply": "respuestas de la cotizacion compuestas en el servidor",
        "quote.value": "valores de la cotizacion compuestos en el servidor",
        "redaction.spoken": "frases de la redaccion dichas por voz",
        "redaction.label": "etiquetas que la redaccion escribe en el texto guardado",
        "redaction.degraded": "frase de la redaccion degradada",
        "compliance.finding": "hallazgos de cumplimiento que escribe el servidor",
        "compliance.identity": "frase de identidad del cumplimiento",
        "orchestration.turn": "frases del ritmo del turno que emite el servidor",
        # La voz hablada: el servidor la sintetiza, la consola no la resuelve.
        "voice.answer": "frase hablada de la voz",
        "voice.barge_in": "frase hablada de la voz",
        "voice.closing": "cierre hablado de la voz",
        "voice.decision": "decision dicha por voz",
        "voice.duration": "duracion dicha por voz",
        "voice.filler": "frases de espera habladas",
        "voice.first_turn": "primer turno hablado",
        "voice.hold": "frase de espera hablada",
        "voice.languages": "frase hablada sobre idiomas",
        "voice.offer": "oferta hablada",
        "voice.opening": "apertura hablada",
        "voice.quote": "cotizacion dicha por voz",
        "voice.readback": "lectura de confirmacion dicha por voz",
        "voice.resume": "reanudacion hablada",
        "voice.retry": "frase hablada de reintento",
        "voice.silence": "frase hablada ante el silencio",
        "voice.spoken": "frase hablada de la voz",
        "voice.time": "hora dicha por voz",
        # Dentro de `policy_rag.coverage` casi todo lo escribe el servidor.
        "policy_rag.coverage": "respuesta de cobertura que el servidor compone con la clausula",
    }
)

#: Claves bajo un prefijo de arriba que la interfaz SI resuelve, y quien las lee.
BROWSER_KEY_EXCEPTIONS = MappingProxyType(
    {
        "adjuster.step.case_read.title": "titulo del paso en el panel (adjuster-panel.tsx)",
        "adjuster.step.policy_read.title": "titulo del paso en el panel (adjuster-panel.tsx)",
        "adjuster.step.clauses.title": "titulo del paso en el panel (adjuster-panel.tsx)",
        "adjuster.step.rules.title": "titulo del paso en el panel (adjuster-panel.tsx)",
        "adjuster.step.vehicle_value.title": "titulo del paso en el panel (adjuster-panel.tsx)",
        "adjuster.step.decision.title": "titulo del paso en el panel (adjuster-panel.tsx)",
        "policy_rag.coverage.no_clause_found": "frase de cobertura sin clausula (chat-copy.ts)",
        "policy_rag.coverage.unverifiable": "frase de cobertura no verificable (chat-copy.ts)",
    }
)


def is_server_only(key: str) -> bool:
    """Si la clave se queda fuera de los modulos que viajan al navegador."""
    if key in BROWSER_KEY_EXCEPTIONS:
        return False
    return any(key == p or key.startswith(p + ".") for p in SERVER_ONLY_PREFIXES)
