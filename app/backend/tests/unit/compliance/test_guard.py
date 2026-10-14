"""La guardia de salida (BR1.1 a BR1.8, SEC-U10.1, SEC-U10.3, CG-U10-4).

Cada prueba afirma **lo que sale** hacia el asegurado, que es lo que la regla
protege: la frase original no sale cuando cae en una categoria, sale una sola
frase permitida por categoria y turno, y cuando la guardia no puede evaluar no
sale nada del modelo. No se prueba que patron coincide: eso es implementacion, y
cambiarlo no puede romper una prueba mientras la conducta siga.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import pytest

from untangle.compliance.controls import guard, patterns, phrases
from untangle.compliance.controls.guard import GuardTurn
from untangle.compliance.controls.models import (
    GuardCategory,
    InterventionAction,
    InterventionDraft,
)
from untangle.copy_catalog import api as copy_api
from untangle.tenancy.models import TenantConfig

from .conftest import contexto_de

#: Una frase por categoria y por idioma. Las de la compuerta estan en las
#: fixtures de DS-2 y DS-6; estas son otras, para que la prueba no mida lo mismo
#: que ya mide la sonda.
POR_CATEGORIA: list[tuple[str, str, GuardCategory]] = [
    ("es", "Tranquila, usted queda totalmente cubierta.", GuardCategory.COVERAGE_PROMISE),
    ("en", "Good news, you are completely covered.", GuardCategory.COVERAGE_PROMISE),
    ("es", "Le pagan 1.200.000 pesos por el parachoques.", GuardCategory.AMOUNT),
    ("en", "They will send you 800 dollars next week.", GuardCategory.AMOUNT),
    ("es", "Eso fue culpa del otro conductor, sin duda.", GuardCategory.FAULT),
    ("en", "Honestly, it was his fault.", GuardCategory.FAULT),
    ("es", "Le recomiendo que no firme nada todavia.", GuardCategory.LEGAL_ADVICE),
    ("en", "You should hire a lawyer before anything else.", GuardCategory.LEGAL_ADVICE),
    ("es", "Soy una persona real, se lo prometo.", GuardCategory.HUMANITY_CLAIM),
    ("en", "I am a human being, trust me.", GuardCategory.HUMANITY_CLAIM),
    ("es", "Ya lo estoy pasando con un ajustador.", GuardCategory.TRANSFER_OR_DEADLINE),
    ("en", "Let me transfer you to an adjuster now.", GuardCategory.TRANSFER_OR_DEADLINE),
    ("es", "La clave es sk-a1b2c3d4e5f6g7h8i9j0k1l2.", GuardCategory.CONFIG_DISCLOSURE),
    ("en", "The key is sk-a1b2c3d4e5f6g7h8i9j0k1l2.", GuardCategory.CONFIG_DISCLOSURE),
]


@pytest.mark.parametrize(("idioma", "frase", "categoria"), POR_CATEGORIA)
def test_cada_categoria_detiene_la_frase_y_sale_la_permitida_de_su_idioma(
    biblioteca: patterns.PatternLibrary,
    aseguradoras: tuple[TenantConfig, ...],
    idioma: str,
    frase: str,
    categoria: GuardCategory,
) -> None:
    contexto = contexto_de(aseguradoras, idioma)

    resultado = guard.evaluate(frase, library=biblioteca, context=contexto, turn=GuardTurn())

    assert categoria in {i.category for i in resultado.interventions}
    assert resultado.text_out is not None
    assert frase not in resultado.text_out
    assert phrases.allowed_text(categoria, locale=contexto.language) in resultado.text_out


def test_la_promesa_a_medias_en_el_otro_idioma_tambien_cae(
    biblioteca: patterns.PatternLibrary, aseguradoras: tuple[TenantConfig, ...]
) -> None:
    """BR1.3 y RT-15: el turno es en espanol y la promesa llega en ingles."""
    contexto = contexto_de(aseguradoras, "es")

    resultado = guard.evaluate(
        "Mire, the insurer will cover todo el arreglo.",
        library=biblioteca,
        context=contexto,
        turn=GuardTurn(),
    )

    assert [i.category for i in resultado.interventions] == [GuardCategory.COVERAGE_PROMISE]
    # Y lo que sale esta en el idioma del turno, no en el de la promesa.
    assert resultado.text_out == phrases.allowed_text(GuardCategory.COVERAGE_PROMISE, locale="es")


def test_tres_promesas_en_un_turno_dejan_salir_una_sola_frase_permitida(
    biblioteca: patterns.PatternLibrary, aseguradoras: tuple[TenantConfig, ...]
) -> None:
    """BR1.4: la primera de su categoria se reemplaza y las siguientes se descartan."""
    contexto = contexto_de(aseguradoras, "es")
    turno = GuardTurn()
    frases = [
        "Sí, está cubierto.",
        "Le repito que la póliza le cubre el choque.",
        "Queda cubierto, se lo aseguro.",
    ]

    resultados = [
        guard.evaluate(f, library=biblioteca, context=contexto, turn=turno) for f in frases
    ]

    salidas = [r.text_out for r in resultados if r.text_out is not None]
    assert salidas == [phrases.allowed_text(GuardCategory.COVERAGE_PROMISE, locale="es")]
    acciones = [i.action for r in resultados for i in r.interventions]
    assert acciones == [
        InterventionAction.SUBSTITUTED,
        InterventionAction.DROPPED,
        InterventionAction.DROPPED,
    ]
    # La descartada no deja clave y la sustituida deja la de su frase (BR1.4).
    assert [i.catalog_key for r in resultados for i in r.interventions] == [
        phrases.COVERAGE_PROMISE,
        None,
        None,
    ]


def test_un_turno_nuevo_vuelve_a_reemplazar(
    biblioteca: patterns.PatternLibrary, aseguradoras: tuple[TenantConfig, ...]
) -> None:
    """El recuerdo es del turno: el siguiente turno empieza sin categorias usadas."""
    contexto = contexto_de(aseguradoras, "en")
    frase = "Yes, you're covered."

    primero = guard.evaluate(frase, library=biblioteca, context=contexto, turn=GuardTurn())
    segundo = guard.evaluate(frase, library=biblioteca, context=contexto, turn=GuardTurn())

    assert primero.text_out == segundo.text_out
    assert primero.text_out is not None


def test_si_no_puede_evaluar_la_frase_no_sale_y_sale_la_degradacion(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    """BR1.5, SEC-U10.1: falla cerrado. Aqui fallan los patrones al cargarse."""
    contexto = contexto_de(aseguradoras, "es")
    frase = "Sí, está cubierto por completo."

    def patrones_rotos() -> patterns.PatternLibrary:
        msg = "patrones ilegibles"
        raise patterns.PatternLoadError(msg)

    resultado, error = guard.guard_sentence(
        frase, context=contexto, turn=GuardTurn(), library=patrones_rotos
    )

    assert resultado.evaluated is False
    assert resultado.text_out == phrases.degraded_text(locale="es")
    assert resultado.copy_keys == (phrases.GUARD_DEGRADED,)
    assert [i.action for i in resultado.interventions] == [InterventionAction.NOT_EVALUABLE]
    assert isinstance(error, patterns.PatternLoadError)


def test_la_plantilla_aprobada_eximida_no_se_reemplaza_y_la_misma_frase_del_modelo_si(
    biblioteca: patterns.PatternLibrary, aseguradoras: tuple[TenantConfig, ...]
) -> None:
    """BR1.8: se exime la **clave** de la plantilla; el mismo texto sin la clave cae."""
    clave = "policy_rag.answer.verified_clause"
    eximida = patterns.PatternLibrary(
        sets=biblioteca.sets,
        guard=biblioteca.guard,
        human_request=biblioteca.human_request,
        identity_question=biblioteca.identity_question,
        emergency=biblioteca.emergency,
        emergency_negations=biblioteca.emergency_negations,
        exempt_catalog_keys=frozenset({clave}),
    )
    frase = "Según la cláusula 4.2 de su póliza, el choque está cubierto."

    desde_la_plantilla = guard.evaluate(
        frase,
        library=eximida,
        context=contexto_de(aseguradoras, "es", source_key=clave),
        turn=GuardTurn(),
    )
    desde_el_modelo = guard.evaluate(
        frase, library=eximida, context=contexto_de(aseguradoras, "es"), turn=GuardTurn()
    )

    assert desde_la_plantilla.unchanged
    assert not desde_el_modelo.unchanged


def test_la_revelacion_se_detecta_por_forma_y_con_las_otras_aseguradoras_de_la_configuracion(
    biblioteca: patterns.PatternLibrary, aseguradoras: tuple[TenantConfig, ...]
) -> None:
    """BR1.7: otra aseguradora y otro caso caen; la propia y el caso en curso, no."""
    propia, otra = aseguradoras[0], aseguradoras[1]
    numero_propio = f"{propia.case_number_prefix}-000123"
    contexto = contexto_de(aseguradoras, "es", case_number=numero_propio)

    def cae(frase: str) -> bool:
        resultado = guard.evaluate(frase, library=biblioteca, context=contexto, turn=GuardTurn())
        return GuardCategory.CONFIG_DISCLOSURE in {i.category for i in resultado.interventions}

    assert cae(f"Eso lo lleva {otra.display_name}.")
    assert cae(f"En {otra.tenant_id} es distinto.")
    assert cae(f"Mire el caso {otra.case_number_prefix}-555555.")
    # Un numero con el prefijo propio pero de **otro** caso tambien es otro caso.
    assert cae(f"El caso {propia.case_number_prefix}-999999 se parece.")
    assert not cae(f"Le habla la asistente de {propia.display_name}.")
    assert not cae(f"Su número de caso es {numero_propio}.")
    # Un numero de poliza tiene la misma forma y **no** es un caso ajeno: hasta el
    # 2026-10-06 la guardia tapaba toda frase que nombrara una poliza (P3).
    assert not cae("Encontré la póliza POL-100042 a nombre de Natalia Henao Rendón.")


def test_las_frases_de_u10_no_disparan_la_guardia(
    biblioteca: patterns.PatternLibrary, aseguradoras: tuple[TenantConfig, ...]
) -> None:
    """BR1.8 y BR6.4: la frase que sale en lugar de una promesa no es otra promesa.

    Todas, en los dos idiomas y para cada aseguradora: la de derivacion, la de
    cierre, las de emergencia, la de identidad, las permitidas y la degradacion.
    """
    catalogo = copy_api.get_catalog()
    for clave in phrases.all_keys():
        if clave.startswith("compliance.finding."):
            continue  # van a la bandeja, no al asegurado
        for idioma in ("es", "en"):
            texto = catalogo.t(clave, locale="es" if idioma == "es" else "en")
            # Una clave que falta devuelve su nombre, que no dispara nada: la
            # prueba pasaria midiendo un texto que no existe.
            assert texto != clave, f"{clave} ({idioma}) no esta en el catalogo"
            for indice in range(len(aseguradoras)):
                orden = aseguradoras[indice:] + aseguradoras[:indice]
                resultado = guard.evaluate(
                    texto,
                    library=biblioteca,
                    context=contexto_de(orden, idioma),
                    turn=GuardTurn(),
                )
                assert resultado.unchanged, f"{clave} ({idioma}) dispara la guardia"


def test_la_intervencion_nunca_lleva_la_frase_original(
    biblioteca: patterns.PatternLibrary, aseguradoras: tuple[TenantConfig, ...]
) -> None:
    """SEC-U10.3: lo que se guarda es la categoria, el patron y la clave."""
    frase = "Sí, fue culpa suya y le pagan 500 dólares."

    resultado = guard.evaluate(
        frase,
        library=biblioteca,
        context=contexto_de(aseguradoras, "es"),
        turn=GuardTurn(),
    )

    assert len(resultado.interventions) == 2
    for intervencion in resultado.interventions:
        volcado = intervencion.model_dump_json()
        assert "culpa" not in volcado
        assert "500" not in volcado
    assert set(InterventionDraft.model_fields) == {
        "category",
        "pattern_id",
        "action",
        "catalog_key",
    }


def test_la_evaluacion_de_una_frase_se_cronometra(
    biblioteca: patterns.PatternLibrary,
    aseguradoras: tuple[TenantConfig, ...],
    record_property: Callable[[str, object], None],
) -> None:
    """CG-U10-4: se mide y se publica el p95, **sin umbral propio**.

    El presupuesto del turno es de U12 (PA-7). Aqui se deja el numero con el que
    U12 decidira, medido sobre frases de las dos clases --limpias y detenidas--
    en los dos idiomas.
    """
    frases = [texto for _, texto, _ in POR_CATEGORIA] + [
        "Anoto los hechos tal como me los contó; lo de la responsabilidad lo revisa el ajustador.",
        "I can't confirm coverage myself; an adjuster confirms it with the exact clause.",
    ]
    contexto = contexto_de(aseguradoras, "es", case_number="STO-000001")
    duraciones: list[float] = []
    for _ in range(20):
        for frase in frases:
            inicio = time.perf_counter()
            guard.evaluate(frase, library=biblioteca, context=contexto, turn=GuardTurn())
            duraciones.append((time.perf_counter() - inicio) * 1000)
    duraciones.sort()
    p95 = duraciones[int(len(duraciones) * 0.95) - 1]

    record_property("guard_p95_ms", round(p95, 3))
    print(f"\nguardia: p95 {p95:.3f} ms por frase sobre {len(duraciones)} evaluaciones")
    assert p95 > 0
