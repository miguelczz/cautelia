"""Si el mensaje respalda anotar el dato de heridos (2026-10-10).

"Nadie salio herido" es el dato de seguridad del reporte: decide si hay una
emergencia y a quien se le pasa el caso. El modelo que entiende el mensaje lo anoto
una vez sin que la persona lo dijera --un choque por detras en un semaforo "suena"
leve-- y el caso quedo con sus datos completos sin haberlo preguntado. Las
instrucciones del modelo ya lo prohiben; esto lo comprueba en codigo, porque una
instruccion se puede desobedecer y una comparacion no.

Es un reconocedor bilingue y determinista, como los demas del proyecto: ancho a
proposito. Equivocarse dejando pasar de mas solo devuelve la conducta de antes;
equivocarse hacia el otro lado cuesta volver a preguntar, que es el lado seguro.
"""

from __future__ import annotations

import re

from untangle.compliance.controls.normalization import fold

#: Palabras con las que alguien habla de heridos o de como quedaron las personas,
#: plegadas (sin tildes, en minusculas). Los dos idiomas corren siempre: quien
#: escribe en espanol puede decir "estamos ok".
_HABLA_DE_HERIDOS = re.compile(
    r"\b("
    r"herid\w*|lesion\w*|lastim\w*|golpead\w*|golpe[os]?\b|dolor\w*|duele\w*|sangr\w*|"
    r"fractur\w*|quebr\w*|hospital\w*|clinica|ambulancia\w*|urgencias|medic[oa]s?|"
    r"paramedic\w*|iles[oa]s?|a salvo|sal(io|imos|ieron) bien|"
    r"(esta|estoy|estamos|estan|quedo|quedamos|quedaron) (todos? |todas? )?bien|"
    r"tod[oa]s bien|nadie|ningun[oa]?|solo (fue )?(el|un) susto|sin novedad|"
    r"injur\w*|hurt\w*|pain\w*|bleed\w*|blood|broken|whiplash|ambulance\w*|"
    r"emergency room|\ber\b|unharmed|unhurt|nobody|no one|"
    r"(is|are|am|was|were|everyone'?s?|everybody'?s?) (all )?(ok|okay|fine|safe|alright)"
    r")\b"
)


def mentions_injuries(text: str) -> bool:
    """El texto habla de heridos, de dolor, de atencion medica o de que estan bien."""
    return _HABLA_DE_HERIDOS.search(fold(text)) is not None


__all__ = ["mentions_injuries"]
