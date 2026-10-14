"""Abrir, encontrar, atar y terminar una llamada. Y a quien se le ofrece retomar."""

from __future__ import annotations

from datetime import timedelta

import pytest

from untangle.voice import session as llamadas
from untangle.voice.models import CallSession, CallState, EndReason, VoiceMode

from .conftest import AHORA, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u16")

MI_NAVEGADOR = "1" * 64
OTRO_NAVEGADOR = "2" * 64
VENTANA = timedelta(minutes=15)


async def _abrir(tenant_id: str, navegador: str) -> CallSession:
    return await llamadas.open_call(
        tenant_id=tenant_id,
        visitor_key_digest=navegador,
        language="en",
        voice_mode=VoiceMode.PRIMARY,
        now=AHORA,
    )


async def _cortada_con_caso(tenant_id: str, navegador: str) -> str:
    """Una llamada de ese navegador que se corto con su caso confirmado."""
    caso = await nuevo_caso(tenant_id)
    llamada = await _abrir(tenant_id, navegador)
    llamada = await llamadas.attach_case(llamada, case_id=caso.case_id)
    await llamadas.end_call(llamada, reason=EndReason.DROPPED, now=AHORA, resume_window=VENTANA)
    return caso.case_id


async def test_una_llamada_nace_conectando_y_sin_caso(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    llamada = await _abrir(a, MI_NAVEGADOR)
    assert llamada.state is CallState.CONNECTING
    assert llamada.case_id is None
    assert llamada.live


async def test_el_socket_autenticado_la_pone_viva(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    llamada = await llamadas.mark_live(await _abrir(a, MI_NAVEGADOR))
    assert llamada.state is CallState.LIVE
    encontrada = await llamadas.find_live(tenant_id=a, visitor_key_digest=MI_NAVEGADOR)
    assert encontrada is not None
    assert encontrada.state is CallState.LIVE


async def test_el_caso_se_ata_una_sola_vez(dos_aseguradoras: tuple[str, str]) -> None:
    """Una segunda escritura significaria que el grafo abrio otro caso, y eso es
    un fallo que hay que ver, no uno que absorber pisando el primero."""
    a, _ = dos_aseguradoras
    primero = await nuevo_caso(a)
    segundo = await nuevo_caso(a)
    llamada = await _abrir(a, MI_NAVEGADOR)
    llamada = await llamadas.attach_case(llamada, case_id=primero.case_id)
    llamada = await llamadas.attach_case(llamada, case_id=segundo.case_id)
    assert llamada.case_id == primero.case_id
    encontrada = await llamadas.find_live(tenant_id=a, visitor_key_digest=MI_NAVEGADOR)
    assert encontrada is not None
    assert encontrada.case_id == primero.case_id


async def test_una_llamada_terminada_ya_no_esta_viva(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    llamada = await _abrir(a, MI_NAVEGADOR)
    await llamadas.end_call(llamada, reason=EndReason.HANGUP, now=AHORA)
    assert await llamadas.find_live(tenant_id=a, visitor_key_digest=MI_NAVEGADOR) is None


async def test_terminar_dos_veces_no_pisa_el_motivo(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Colgar y que se corte pueden llegar casi a la vez; el que quede escrito
    tiene que ser el que de verdad la termino, no el ultimo en llegar."""
    a, _ = dos_aseguradoras
    llamada = await _abrir(a, MI_NAVEGADOR)
    await llamadas.end_call(llamada, reason=EndReason.HANGUP, now=AHORA)
    with pytest.raises(llamadas.CallNotFoundError):
        await llamadas.end_call(llamada, reason=EndReason.DROPPED, now=AHORA)


async def test_un_corte_deja_la_llamada_retomable(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    case_id = await _cortada_con_caso(a, MI_NAVEGADOR)
    retomable = await llamadas.find_resumable(
        tenant_id=a, visitor_key_digest=MI_NAVEGADOR, now=AHORA + timedelta(minutes=1)
    )
    assert retomable is not None
    assert retomable.case_id == case_id


async def test_fuera_de_la_ventana_no_se_retoma(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    await _cortada_con_caso(a, MI_NAVEGADOR)
    assert (
        await llamadas.find_resumable(
            tenant_id=a,
            visitor_key_digest=MI_NAVEGADOR,
            now=AHORA + VENTANA + timedelta(seconds=1),
        )
        is None
    )


async def test_colgar_no_deja_nada_que_retomar(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Colgar es un final; cortarse es una pausa (BR6.1)."""
    a, _ = dos_aseguradoras
    caso = await nuevo_caso(a)
    llamada = await llamadas.attach_case(await _abrir(a, MI_NAVEGADOR), case_id=caso.case_id)
    await llamadas.end_call(llamada, reason=EndReason.HANGUP, now=AHORA)
    assert (
        await llamadas.find_resumable(
            tenant_id=a, visitor_key_digest=MI_NAVEGADOR, now=AHORA + timedelta(minutes=1)
        )
        is None
    )


async def test_el_caso_cortado_de_otro_navegador_no_se_ofrece(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR6.3, criterio [bloquea] AC1.27.3.

    El caso de otro visitante existe, es de la misma aseguradora y llevaria la
    misma poliza de ejemplo --que es publica--. Lo unico que lo separa de mi es
    el resumen de mi navegador, y esta prueba es la que comprueba que eso basta.
    """
    a, _ = dos_aseguradoras
    ajeno = await _cortada_con_caso(a, OTRO_NAVEGADOR)

    mio = await llamadas.find_resumable(
        tenant_id=a, visitor_key_digest=MI_NAVEGADOR, now=AHORA + timedelta(minutes=1)
    )
    assert mio is None, f"se ofrecio el caso ajeno {ajeno}"


async def test_la_busqueda_de_retoma_no_admite_una_poliza() -> None:
    """La firma es parte de la regla: sin parametro, nadie la pasa por descuido."""
    import inspect

    parametros = set(inspect.signature(llamadas.find_resumable).parameters)
    assert parametros == {"tenant_id", "visitor_key_digest", "now"}


# --- Llamar por otro accidente (BR6.4) ----------------------------------------


async def test_cambiar_de_caso_deja_el_anterior_intacto(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La persona oyo la oferta de retomar y dijo que llama por otro accidente.

    La llamada pasa a trabajar sobre el caso nuevo y el anterior **no se toca**:
    ni se cierra, ni se borra, ni deja de ser retomable. Es lo que distingue
    "otro accidente" de "olvide lo anterior".
    """
    a, _ = dos_aseguradoras
    anterior = await nuevo_caso(a)
    nuevo = await nuevo_caso(a)
    llamada = await llamadas.attach_case(await _abrir(a, MI_NAVEGADOR), case_id=anterior.case_id)

    movida = await llamadas.switch_case(llamada, case_id=nuevo.case_id)

    assert movida.case_id == nuevo.case_id
    viva = await llamadas.find_live(tenant_id=a, visitor_key_digest=MI_NAVEGADOR)
    assert viva is not None
    assert viva.case_id == nuevo.case_id
    # El anterior sigue ahi: se lee por el mismo camino que la bandeja.
    from untangle.case_record import api as casos

    assert await casos.get_case(a, anterior.case_id) is not None


async def test_cambiar_al_mismo_caso_no_escribe_nada(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Pedir lo que ya esta no es un fallo ni una escritura: es un no-op.

    Sin esta rama, una retoma aceptada que pasara por aqui haria una escritura
    que no cambia nada y que en el historial se lee como si el caso hubiera
    cambiado.
    """
    a, _ = dos_aseguradoras
    caso = await nuevo_caso(a)
    llamada = await llamadas.attach_case(await _abrir(a, MI_NAVEGADOR), case_id=caso.case_id)

    assert await llamadas.switch_case(llamada, case_id=caso.case_id) is llamada


async def test_una_llamada_terminada_no_cambia_de_caso(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Mover el caso de una llamada que ya termino reescribiria el pasado.

    La guarda es `state <> 'ended'` y falla nombrando la llamada, no en silencio:
    una escritura de cero filas que se diera por buena dejaria al motor creyendo
    que trabaja sobre un caso que la fila no conoce.
    """
    a, _ = dos_aseguradoras
    caso = await nuevo_caso(a)
    otro = await nuevo_caso(a)
    llamada = await llamadas.attach_case(await _abrir(a, MI_NAVEGADOR), case_id=caso.case_id)
    terminada = await llamadas.end_call(llamada, reason=EndReason.HANGUP, now=AHORA)

    with pytest.raises(llamadas.CallNotFoundError):
        await llamadas.switch_case(terminada, case_id=otro.case_id)


async def test_cambiar_de_idioma_deja_el_nuevo_en_la_fila(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Una llamada que se corta y se retoma lee el idioma de la fila, no el del objeto en
    memoria: por eso se escribe (BR2.3). El del caso no se toca desde aqui."""
    a, _ = dos_aseguradoras
    llamada = await _abrir(a, MI_NAVEGADOR)

    cambiada = await llamadas.set_language(llamada, language="es")

    assert cambiada.language == "es"
    leida = await llamadas.find_live(tenant_id=a, visitor_key_digest=MI_NAVEGADOR)
    assert leida is not None
    assert leida.language == "es"


async def test_cambiar_al_idioma_en_que_ya_esta_no_escribe_nada(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    llamada = await _abrir(a, MI_NAVEGADOR)

    assert await llamadas.set_language(llamada, language="en") is llamada


async def test_una_llamada_terminada_no_cambia_de_idioma(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Cambiar el idioma de una llamada que ya termino reescribiria lo que paso: falla
    nombrando la llamada, igual que mover su caso."""
    a, _ = dos_aseguradoras
    terminada = await llamadas.end_call(
        await _abrir(a, MI_NAVEGADOR), reason=EndReason.HANGUP, now=AHORA
    )

    with pytest.raises(llamadas.CallNotFoundError):
        await llamadas.set_language(terminada, language="es")
