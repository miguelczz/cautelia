"""BR5.5, FD-U11-7: dos versiones se guardan las dos, sin juzgar y sin reemplazar.

**FD-U11-7** (decision de Miguel del 2026-09-27): el valor del caso es **el
primero confirmado**; una version que lo contradice se anota aparte, con su
turno y su hora. La razon: con la ultima version ganando, quien se corrige de
buena fe (RT-7 de DS-6, "dos versiones de lo que paso") podria acabar con el
dato bueno reemplazado por uno peor -- por ejemplo una fecha anterior a la
vigencia de la poliza, el patron clasico de querer reportar un siniestro viejo
como si fuera reciente.

**Como se anota "aparte".** `case_record.api` ya expone `record_change` como una
de sus operaciones de C-12 -- "anexar al historial", solo anexar, sin editar ni
borrar (SEC-U4.11) -- y una entrada se puede construir sin que el campo
autoritativo cambie: se construye un `CaseField` que **nunca se persiste** (nunca
pasa por `repository.save_field`), solo para sellar el valor y su hora, y se
anexa la entrada sola. El campo de verdad -- el que lee la completitud y el que
compone la lectura de confirmacion -- no se toca.

**La entrada lleva su propia clase, `FIELD_VERSION_ALTERNATE`**, y esto se
corrigio en la revision de la tanda 2: se anotaba como `FIELD_SET`, que en el
historial significa "el campo se fijo a este valor". Con esa clase, la linea de
tiempo del caso mostraba el segundo valor como el vigente -- lo contrario de lo
que FD-U11-7 decide. Es el argumento con el que U4 justifico
`transition_rejected`, leido al reves: una version que no se acepto y se anota
como aceptada es indistinguible de un cambio real
(`u11_intake_0002_alt_version`).

**Lo que esta unidad NO decide.** Que una contradiccion dispare la derivacion
del caso es una regla de U9 (o de U19), en el ritmo de fondo, que mira si
**existe** una version alterna -- nunca el valor del campo, que sigue siendo
el primero confirmado. Escribir esa regla no es de aqui (`functional-spec.md`,
"Una consecuencia de FD-U11-7 que no es de esta unidad").

**`is_contradiction` vive en `versions.py` y se reexporta aqui.** Es la mitad
pura de esta regla -- sin ningun import de `case_record` -- para que el
corredor de evaluaciones la pueda medir sin arrastrar `case_record.api` ni
`tenancy.session`, que su propio contrato de importacion prohibe
(`acyclic_siblings`, "el corredor de evaluaciones no importa la raiz de
composicion ni la sesion").
"""

from __future__ import annotations

from datetime import datetime

from untangle.case_record import api as case_record
from untangle.case_record import history
from untangle.case_record.crypto import Cipher
from untangle.case_record.models import Actor, Channel, FieldStatus
from untangle.case_record.models import CaseField as _CaseField
from untangle.orchestration.nodes.intake.versions import is_contradiction as is_contradiction
from untangle.tenancy.models import TenantId


async def record_alternate_version(  # noqa: PLR0913 -- nueve datos de la version alterna, ninguno derivable de otro
    tenant_id: TenantId,
    *,
    case_id: str,
    field_key: str,
    text: str,
    evidence_turn_id: str,
    now: datetime,
    cipher: Cipher,
    actor: Actor,
    channel: Channel | None = None,
) -> None:
    """BR5.5, FD-U11-7: anota la version alterna, sin tocar el campo autoritativo.

    `text` ya viene normalizado y redactado cuando aplica -- esta funcion no
    normaliza ni redacta, solo sella y anexa. El `CaseField` que construye
    aqui dentro nunca se guarda: existe solo para que `history.field_set`
    derive de el la entrada del historial, con su turno y su hora.
    """
    fantasma = _CaseField(
        case_id=case_id,
        field_key=field_key,
        value=cipher.seal(text),
        status=FieldStatus.STATED,
        evidence_turn_id=evidence_turn_id,
        updated_at=now,
    )
    cambio = history.field_version_alternate(fantasma, actor=actor, channel=channel)
    await case_record.record_change(tenant_id, cambio, cipher=cipher)


__all__ = ["is_contradiction", "record_alternate_version"]
