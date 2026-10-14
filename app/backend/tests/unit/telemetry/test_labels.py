"""Las etiquetas: que ningun valor de enum se quede sin frase, ni al reves.

Los dos sentidos, porque cada uno falla de una forma distinta y ninguno de los
dos avisa solo:

- **Un valor sin clave** sale vacio en pantalla, o peor, sale como el valor del
  enum: `rate_limited_site` delante de un visitante.
- **Una clave sin valor** es una frase muerta en el catalogo que nadie borra
  porque nadie sabe si se usa. Es el fallo que la landing ya muestra (TD-01).

El catalogo se carga de los archivos **del repositorio**: lo que importa es que
las frases que se despliegan esten, no que una fixture las tenga.
"""

from __future__ import annotations

from untangle.copy_catalog import api as catalogo
from untangle.telemetry.spend import labels as labels_gasto
from untangle.telemetry.spend.models import QuotaReason
from untangle.telemetry.traces import labels as labels_trazas
from untangle.telemetry.traces.models import TraceSummaryStatus

#: La frase que AC5.14.3 fija, **literal**. Se copia del criterio y no se
#: parafrasea: es una de las pocas que un criterio de aceptacion escribe entera,
#: y una prueba que la comprobara "parecida" dejaria de comprobarla.
CORTE_DE_LA_VOZ = (
    "La demostración de voz llegó a su presupuesto y no está recibiendo "
    "llamadas. El chat sigue disponible."
)


def test_los_cuatro_motivos_de_cuota_tienen_clave() -> None:
    """BR5.3: cuatro motivos, cuatro claves, sin componer ninguna."""
    assert set(labels_gasto.QUOTA_REASON_KEYS) == set(QuotaReason)


def test_los_tres_estados_del_resumen_tienen_clave() -> None:
    """BR6.7. Los tres, y no solo 'registrandose': declarar uno dejaria a los
    otros dos saliendo como valor de enum en pantalla."""
    assert set(labels_trazas.SUMMARY_STATUS_KEYS) == set(TraceSummaryStatus)


def test_cada_clave_declarada_existe_en_los_dos_idiomas() -> None:
    """P12: mismas frases en los dos lados, nunca una sola.

    Se resuelven de verdad contra el catalogo cargado en vez de compararse
    contra una lista: una clave presente en el archivo pero mal escrita en el
    codigo pasaria una comparacion de listas y fallaria aqui.
    """
    catalogo.install(catalogo.load())
    try:
        for clave in labels_gasto.all_keys() | labels_trazas.all_keys():
            for idioma in ("es", "en"):
                frase = catalogo.t(clave, locale=idioma)
                assert frase
                assert frase != clave
    finally:
        catalogo.reset()


def test_el_corte_de_la_voz_es_la_frase_literal_del_criterio() -> None:
    """AC5.14.3 escribe la frase entera, y esta es la unica copia.

    Lleva la clave de `budget_exhausted` y no una propia: el mensaje de corte y
    el motivo de cuota son la misma cosa dicha dos veces, y dos entradas con el
    mismo texto es como un dia dejan de decir lo mismo.

    El mes **no se menciona**, y eso tambien se comprueba: el techo es acumulado
    en la ventana de noventa dias y nunca mensual (D11).
    """
    catalogo.install(catalogo.load())
    try:
        clave = labels_gasto.QUOTA_REASON_KEYS[QuotaReason.BUDGET_EXHAUSTED]
        frase = catalogo.t(clave, locale="es")
    finally:
        catalogo.reset()

    assert frase == CORTE_DE_LA_VOZ
    assert "mes" not in frase.lower()
