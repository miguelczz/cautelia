"""El punto único de salida (paso 7 de U12, BR2.5): todo texto hacia una persona pasa por aquí.

**Por qué una sola pieza y no una convención.** BR2.5 dice "todo texto hacia la
persona", y el camino que más fácil se salta la guardia es el de error: una
excepción capturada dos capas más arriba, que compone su frase directo porque
"total, es solo el mensaje de error". Esta clase existe para que ese atajo no
exista -- no hay ninguna otra función en esta unidad que produzca el `text` de
un `TurnEvent` (`turn.py`) sin pasar por `ExitGate.send`.

**Qué aplica, y qué no.** Aplica el paso de la guardia (`compliance.controls.api.
guard_output`), que es lo que puede sustituir o rechazar una frase antes de que
salga (C-20). No repite las dos detecciones de senal (peticion de persona,
emergencia): esas leen el texto **entrante** de la persona y ya corrieron una
vez por turno, al principio, con `orchestration.rhythm.run_turn_controls`;
llamarlas otra vez sobre una frase **saliente** no tiene con que comparar.

**Una instancia por turno.** `GuardTurn` recuerda, dentro de un turno, que
categorias ya sustituyo (BR1.4 de la guardia): la segunda frase de la misma
categoria en el mismo turno se descarta en vez de repetir la sustitucion. Una
instancia nueva por turno, reutilizada para cada evento que ese turno emita
--incluidos los de degradacion y de error--, es lo que hace eso cierto.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from untangle import observability
from untangle.base import Locale
from untangle.compliance.controls.api import GuardTurn, guard_output
from untangle.copy_catalog.api import CopyKey
from untangle.tenancy.models import TenantId


@dataclass
class ExitGate:
    """La puerta de salida de un turno. Una instancia por turno (BR1.4, BR2.5)."""

    tenant_id: TenantId
    language: Locale
    case_id: str | None = None
    case_number: str | None = None
    _turn: GuardTurn = field(default_factory=GuardTurn)

    async def send(self, text: str) -> tuple[str, tuple[CopyKey, ...]]:
        """El texto seguro para emitir, y las claves de lo que la guardia sustituyó.

        Se llama para **cada** texto que un evento de este turno vaya a llevar,
        sin excepción -- incluida una frase de degradación o de error que ya
        sale del catálogo. Si la guardia no puede evaluar, `guard_output` ya
        resuelve su propia frase de degradación (C-20, BR1.5); esta puerta no
        decide nada más, solo garantiza que nadie la esquive.
        """
        resultado = await guard_output(
            text,
            tenant_id=self.tenant_id,
            language=self.language,
            case_id=self.case_id,
            case_number=self.case_number,
            turn=self._turn,
        )
        texto = resultado.text_out if resultado.text_out is not None else ""
        return texto, tuple(CopyKey(clave) for clave in resultado.copy_keys)


async def send_rewrite_or_base(gate: ExitGate, rewrite: str | None, base: str) -> tuple[str, bool]:
    """La version natural si la guardia la deja pasar entera; si no, la frase base.

    Devuelve el texto y si salio del catalogo. Antes, cuando la guardia rechazaba la
    version natural, salia su frase de seguridad en lugar de la del turno y se perdia
    la pregunta ("¿Es usted?"): la persona contestaba a algo que nunca vio (visto el
    2026-10-08). La frase base es del catalogo y tambien pasa por la guardia.
    """
    if rewrite is None:
        texto, _ = await gate.send(base)
        return texto, True
    texto, sustituidas = await gate.send(rewrite)
    if not sustituidas:
        return texto, False
    observability.emit("chat.reply_guarded_fallback", tenant_id=gate.tenant_id)
    texto, _ = await gate.send(base)
    return texto, True


__all__ = ["ExitGate", "send_rewrite_or_base"]
