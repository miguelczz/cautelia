"""Si una primera frase dice a que viene la persona, por reglas y sin modelo (2026-10-13).

«Queria consultar sobre...», «tengo una pregunta», «necesito ayuda»: la persona **anuncia**
que va a decir algo y todavia no lo dice. Decidir con eso un tipo de caso es adivinar, y lo
que se adivinaba era el reporte de un accidente.

**Vive en el nucleo porque lo usan los dos canales.** La llamada lo usa para decidir su
primer turno (`voice/first_turn.py`) y el chat, en el respaldo por reglas de su primer
mensaje --cuando el modelo que entiende falla o tarda-- (`chat/case_opening.py`). El chat y
la voz son canales y no se importan entre si, y el nucleo no importa canales: el vocabulario
en un solo sitio que los dos pueden importar es la unica forma de que no se tenga que
mantener dos veces. Es el mismo criterio que ya aplica el desvio de cobertura
(`coverage_detour`) y la cotizacion (`quote_reply`).

Esta funcion no sabe de casos ni de tipos: dice si la frase **no dice nada todavia**. Que se
hace entonces --preguntar a que viene-- es de cada canal.
"""

from __future__ import annotations

import re
import unicodedata

from untangle.base import Locale

#: Las palabras de una frase que **solo anuncia** que se quiere consultar o preguntar algo,
#: ya plegadas (sin tildes ni apostrofes). Una frase es vaga si **todas** sus palabras estan
#: en esta lista y al menos una es de las que anuncian: basta una palabra de contenido --
#: «poliza», «choque», «ayer», «mi»-- para que ya no lo sea y siga por donde iba. La lista es
#: deliberadamente corta y se lee en un diff: ampliarla es decidir que otra frase se
#: pregunta en vez de atenderse como reporte.
#:
#: «Hablar» y «ayuda» anuncian y no dicen de que; «persona», «ajustador» o «asesor» no estan
#: a proposito: pedir uno es otra cosa, y la resuelve el grafo.
_ANUNCIAN_ES = frozenset(
    """consultar consulta consultas preguntar pregunta preguntas duda dudas saber averiguar
    ayuda ayudita informacion hablar tema temas asunto asuntos cosa cosas algo""".split()
)
_RELLENO_ES = frozenset(
    """hola buenas buenos dias tardes noches bueno mire oiga disculpe perdon pues entonces si eh
    este ah queria quisiera quiero necesito necesitaba tengo tenia llamo llamaba llamando estoy
    vengo venia gustaria me te le les hacer hacerle hacerte hacerles poder podria podrias puedo
    ayudarme ayudar un una unas unos algun alguna algunas algunos sobre de del acerca por con
    para a que el la lo y o mas poco ustedes usted ti ud""".split()
)
_ANUNCIAN_EN = frozenset(
    """question questions ask asking inquire inquiry help something anything information info
    talk speak know check thing things topic""".split()
)
_RELLENO_EN = frozenset(
    """hi hello hey good morning afternoon evening yes yeah okay ok well um uh so sorry excuse me
    i id ive im want wanted would like need needed have had got calling called am was to
    wondering hoping looking trying can could you please find out about regarding concerning on
    for a an the few couple of some quick just with""".split()
)

#: Una frase de mas palabras que esto ya cuenta algo, aunque cada una este en la lista.
_MAXIMO_DE_PALABRAS_VAGAS = 9


def _palabras(text: str) -> list[str]:
    """Las palabras de una frase, en minusculas y sin tildes ni signos."""
    plegado = "".join(
        c for c in unicodedata.normalize("NFD", text.casefold()) if not unicodedata.combining(c)
    )
    return re.findall(r"[a-z0-9]+", plegado.replace("'", "").replace("\u2019", ""))


def says_nothing_about_purpose(text: str, *, language: Locale) -> bool:
    """Si la frase solo anuncia que se quiere consultar o preguntar algo, sin decir que.

    **Conservadora a proposito**: es verdadera solo cuando *cada* palabra es del anuncio o del
    relleno. Una frase con cualquier palabra de contenido (un objeto, un hecho, un «mi») sigue
    como siempre. El error que prefiere es dejar pasar una frase vaga al reporte --lo de antes--
    y no preguntar de mas a quien ya dijo a que llama.

    Un saludo a secas («hola, buenas tardes») tampoco cuenta: no anuncia nada, y cada canal ya
    tiene su propia regla para el saludo.
    """
    palabras = _palabras(text)
    if not palabras or len(palabras) > _MAXIMO_DE_PALABRAS_VAGAS:
        return False
    anuncian, relleno = (
        (_ANUNCIAN_ES, _RELLENO_ES) if language == "es" else (_ANUNCIAN_EN, _RELLENO_EN)
    )
    if not all(p in anuncian or p in relleno for p in palabras):
        return False
    return any(p in anuncian for p in palabras)


__all__ = ["says_nothing_about_purpose"]
