"""Los objetos de valor de la redaccion. Ninguno se guarda en ningun sitio.

**Esta unidad no crea ninguna tabla y no persiste nada.** Todo lo de aqui vive en
memoria durante una llamada y desaparece con ella. No es un detalle de
implementacion: es el control. Un detector que guardara lo que detecta se
convertiria en el unico sitio del sistema donde los datos personales estan juntos
y en claro, que es exactamente lo que este componente existe para evitar.

**Por que viven en la capa de abajo y no en un modulo propio.** El contrato de
capas del modulo pone `recognizers` en la base, y `detector` y `labels` --que
estan en el mismo renglon y no pueden importarse entre si-- necesitan los dos
hablar de `EntityType`. La base es el unico sitio desde el que los dos pueden
leerlo sin romper la escalera. Anadir un septimo modulo solo para los tipos
habria sido una pieza mas que el diseno no declara.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from untangle.base import Frozen, Locale


class EntityType(StrEnum):
    """El conjunto cerrado de lo que se tapa.

    Cerrado a proposito: la etiqueta que ve una persona sale del catalogo de
    textos, y una clave sin valor la detecta el chequeo de paridad del catalogo.
    Un tipo abierto haria imposible esa comprobacion.
    """

    #: Placa de vehiculo. Reconocedor propio de esta unidad.
    LICENSE_PLATE = "license_plate"
    #: Cedula o documento de identidad. Reconocedor propio.
    NATIONAL_ID = "national_id"
    #: Telefono. Reconocedor propio.
    PHONE = "phone"
    #: Numero de poliza. Reconocedor propio.
    POLICY_NUMBER = "policy_number"
    #: Nombre de persona. Del detector de base.
    PERSON = "person"
    #: Correo electronico. Del detector de base.
    EMAIL = "email"
    #: Direccion o lugar. Del detector de base.
    LOCATION = "location"
    #: Lo que solo atrapo la regla de respaldo (decision FD-U3-9).
    UNCLASSIFIED = "unclassified"
    #: Numero de identificacion del vehiculo: diecisiete caracteres sin I, O ni
    #: Q (ISO 3779). Reconocedor propio por formato. Entro cuando U7 encontro que
    #: salia con solo su cola de digitos tapada por el respaldo (NFR11.10), y
    #: tapar la cola deja a la vista fabricante, modelo y ano.
    VIN = "vin"

    @property
    def engine_entity(self) -> str:
        """El nombre con el que el motor de reconocedores conoce este tipo."""
        return self.value.upper()


#: Los cuatro tipos propios del dominio, los que esta unidad existe para tapar.
#: Son los que mide NFR11.1 al 100 % sobre casos sembrados: el modelo de lenguaje
#: no los encuentra, los encuentran reconocedores propios por formato.
OWN_DOMAIN_TYPES: frozenset[EntityType] = frozenset(
    {
        EntityType.LICENSE_PLATE,
        EntityType.NATIONAL_ID,
        EntityType.PHONE,
        EntityType.POLICY_NUMBER,
    }
)

#: Todo lo que encuentran los reconocedores propios **por formato**: los cuatro
#: de NFR11.1 y el VIN. Es el escalon mas especifico de un solape y el conjunto
#: que cada idioma tiene que declarar con sus tres formas de escritura.
#:
#: El VIN va aqui y **no** en `OWN_DOMAIN_TYPES` a proposito: esos cuatro son los
#: que nombra NFR11.1, y cambiar el alcance de un requisito aprobado no es una
#: decision de una correccion. El VIN se mide por NFR11.10 (los canarios de U7) y
#: por sus semillas de RT-14.
FORMAT_TYPES: frozenset[EntityType] = OWN_DOMAIN_TYPES | {EntityType.VIN}


class Mechanism(StrEnum):
    """Como encuentra un reconocedor lo que encuentra.

    Declarado, y no deducido, porque U21 exige que el segundo detector **no
    comparta mecanismo** con este (AC4.14.1). U21 lee estos archivos como
    archivos, sin importar este modulo (BR4.6); sin esta declaracion, esa
    comprobacion seria una afirmacion en un documento.
    """

    PATTERN = "pattern"
    CONTEXT = "context"
    CHECKSUM = "checksum"
    MODEL = "model"


class WritingForm(StrEnum):
    """Las tres formas en que se escribe un mismo dato (BR2.2).

    Son datos de configuracion y no ramas de codigo: anadir una forma nueva es
    anadir una entrada al archivo versionado.
    """

    #: Sin separadores: `3005551234`.
    COMPACT = "compact"
    #: Con espacios, guiones o puntos: `300 555 1234`, `79.123.456`.
    SEPARATED = "separated"
    #: Dictado en palabras: `tres cero cero cinco...`.
    SPOKEN = "spoken"


class RecognizerPattern(Frozen):
    """Una forma de escritura de un tipo, con su expresion y su puntaje.

    El puntaje decide dos cosas: si el hallazgo supera el umbral del idioma sin
    ayuda del contexto, y quien gana un solape entre dos hallazgos del mismo
    tamano. Un patron con estructura propia --`POL-######`-- puntua alto; uno
    que es una tira de digitos a secas puntua bajo y depende del contexto.
    """

    form: WritingForm
    regex: str = Field(min_length=1)
    score: float = Field(gt=0.0, le=1.0)

    @model_validator(mode="after")
    def _la_expresion_compila(self) -> Self:
        try:
            re.compile(self.regex)
        except re.error as error:
            msg = f"el patron '{self.form.value}' no es una expresion valida: {error}"
            raise ValueError(msg) from error
        return self


class EngineRecognizer(Frozen):
    """De donde sale un reconocedor que no es nuestro.

    Los de nombre, lugar y correo los aporta el detector de base. Se declaran
    igual que los propios --con sus cinco campos-- porque U21 necesita ver
    **todos** los mecanismos que este detector usa, no solo los que escribimos
    nosotros.
    """

    #: El nombre con el que el motor lo conoce, por ejemplo `SpacyRecognizer`.
    recognizer: str = Field(min_length=1)
    #: La entidad que ese reconocedor emite, por ejemplo `PERSON`.
    entity: str = Field(min_length=1)


class Recognizer(Frozen):
    """La declaracion de un reconocedor (BR2.6, BR2.7, BR2.8).

    Cinco campos obligatorios --identificador, tipo, idioma, mecanismo y
    procedencia-- y uno de los dos modos: patrones propios o reconocedor del
    motor. Si falta cualquiera de los cinco, **no carga y el arranque falla
    nombrandolo**: un reconocedor a medias es un agujero que no avisa.
    """

    id: str = Field(min_length=1, pattern=r"^(es|en)-[a-z0-9-]+$")
    entity_type: EntityType
    language: Locale
    mechanism: Mechanism
    #: De donde salio el formato, con su referencia. Un reconocedor sin
    #: procedencia no se puede revisar, y a las seis semanas nadie sabe si el
    #: formato es el real o el que alguien recordaba.
    source: str = Field(min_length=1)
    #: Las palabras que suben el puntaje cuando aparecen cerca.
    context: tuple[str, ...] = ()
    #: Las tres formas de escritura, cuando el reconocedor es propio.
    patterns: tuple[RecognizerPattern, ...] = ()
    #: El reconocedor del motor, cuando no lo es.
    provided_by: EngineRecognizer | None = None

    @model_validator(mode="after")
    def _el_identificador_empieza_por_su_idioma(self) -> Self:
        # Los identificadores son `<idioma>-<tipo>` y las sondas de RT-15 los
        # componen para exigir que el informe atribuya el hallazgo al juego que
        # lo encontro. Que la forma sea obligatoria evita que un renombrado
        # silencioso deje esa comprobacion midiendo otra cosa (BR2.9).
        if not self.id.startswith(f"{self.language}-"):
            msg = (
                f"el reconocedor '{self.id}' declara el idioma '{self.language}' y "
                f"su identificador no empieza por '{self.language}-'"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _declara_patrones_propios_o_reconocedor_del_motor(self) -> Self:
        if bool(self.patterns) == (self.provided_by is not None):
            msg = (
                f"el reconocedor '{self.id}' tiene que declarar o sus patrones "
                "propios o el reconocedor del motor que lo aporta, y exactamente "
                "uno de los dos"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _no_repite_una_forma_de_escritura(self) -> Self:
        formas = [patron.form for patron in self.patterns]
        repetidas = sorted({f.value for f in formas if formas.count(f) > 1})
        if repetidas:
            msg = f"el reconocedor '{self.id}' repite las formas {repetidas}"
            raise ValueError(msg)
        return self


class FallbackRule(Frozen):
    """La regla de respaldo por contexto (BR2.5, decision FD-U3-9).

    Corre **despues** de los reconocedores y solo reclama lo que ninguno
    reclamo. Cubre el formato que nadie previo, que es por donde se escapan las
    cosas; el costo aceptado es alguna redaccion de mas, que es el lado seguro
    del error.

    Declara los mismos cinco campos que un reconocedor, porque es uno mas a ojos
    de U21: tiene mecanismo propio y sus hallazgos se cuentan aparte (BR4.2).
    """

    id: str = Field(min_length=1, pattern=r"^(es|en)-[a-z0-9-]+$")
    entity_type: EntityType
    language: Locale
    mechanism: Mechanism
    source: str = Field(min_length=1)
    #: Cuantos digitos seguidos hacen falta para que la secuencia cuente.
    min_digits: int = Field(ge=4, le=20)
    #: A cuantos caracteres de la frase de contexto puede estar la secuencia.
    window: int = Field(ge=1, le=200)
    #: Las frases que declaran que lo de al lado es un dato personal. Viven aqui
    #: y no en el catalogo de textos (NFRD-U3-4): el catalogo es para lo que lee
    #: una persona, y estas son patrones de deteccion.
    context_phrases: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _el_respaldo_solo_produce_lo_no_clasificado(self) -> Self:
        # Si el respaldo pudiera producir un tipo del dominio, su cifra se
        # sumaria a la de ese tipo y borraria la senal que BR4.2 protege: un
        # respaldo que dispara mucho significa que un reconocedor se rompio.
        if self.entity_type is not EntityType.UNCLASSIFIED:
            msg = (
                f"la regla de respaldo '{self.id}' declara el tipo "
                f"'{self.entity_type.value}'; el respaldo solo produce "
                f"'{EntityType.UNCLASSIFIED.value}' (BR4.2)"
            )
            raise ValueError(msg)
        return self


class SelfIdentificationRule(Frozen):
    """La regla de autoidentificacion: el nombre que sigue a "me llamo" (U7, NFR11.10).

    Despues de una frase con la que alguien dice quien es --"my name is", "me
    llamo", "soy", "le habla"--, la secuencia de `min_tokens` a `max_tokens`
    palabras con mayuscula que sigue se tapa como nombre, **la etiquete como la
    etiquete el modelo de lenguaje**: `en_core_web_md` llama organizacion a
    "Megan Hughes" en "My name is Megan Hughes.", y el modelo ingles no reconoce un
    nombre espanol dentro de una frase inglesa. Esta regla no depende de ninguno
    de los dos.

    **Corre en los dos idiomas en cada llamada**, sea cual sea el del turno, como
    los reconocedores por formato: no es un modelo de lenguaje, asi que correrla
    sobre el otro idioma no anade el ruido que `PASADA_DEL_OTRO_IDIOMA` evita, y
    decir el nombre con la frase del otro idioma no puede ser la via para sacarlo.

    **Lo que no tapa** esta en `organization_words`: una secuencia con una palabra
    de organizacion ("Auto", "Mutual", "Seguros") es una empresa y no una persona.
    Es la negativa de "This is Ridgeway Mutual calling": U3 no conoce aseguradoras
    --`redact()` recibe texto e idioma, y un identificador de aseguradora aqui
    seria la rama por aseguradora que BR4.2 de U2 prohibe--, asi que la negativa
    se decide por la estructura del nombre y no por una lista de aseguradoras. La
    prueba que recorre los nombres visibles de todas las carpetas de aseguradora
    es la que vuelve comprobable que ninguna se tapa.

    Tapar de mas en el otro lado --"This is Part A" sale como nombre-- es el costo
    aceptado de la decision FD-U3-9.
    """

    id: str = Field(min_length=1, pattern=r"^(es|en)-[a-z0-9-]+$")
    entity_type: EntityType
    language: Locale
    mechanism: Mechanism
    source: str = Field(min_length=1)
    #: Las frases que anuncian un nombre. Se buscan sin distinguir mayusculas; el
    #: apostrofo recto y el tipografico valen igual.
    cues: tuple[str, ...] = Field(min_length=1)
    #: Cuantas palabras con mayuscula seguidas cuentan como nombre.
    min_tokens: int = Field(ge=2, le=8)
    max_tokens: int = Field(ge=2, le=8)
    #: Las palabras que hacen de la secuencia una organizacion y no una persona.
    #: Se comparan sin mayusculas ni tildes.
    organization_words: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _la_regla_solo_produce_nombres(self) -> Self:
        if self.entity_type is not EntityType.PERSON:
            msg = (
                f"la regla de autoidentificacion '{self.id}' declara el tipo "
                f"'{self.entity_type.value}'; solo produce "
                f"'{EntityType.PERSON.value}'"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _el_mecanismo_es_de_contexto(self) -> Self:
        # U21 lee este mecanismo para comprobar que su detector no comparte
        # ninguno con este (AC4.14.1). La regla encuentra el nombre por la frase
        # que lo anuncia, que es contexto; declarar otro seria mentirle a U21.
        if self.mechanism is not Mechanism.CONTEXT:
            msg = (
                f"la regla de autoidentificacion '{self.id}' declara el mecanismo "
                f"'{self.mechanism.value}'; encuentra el nombre por la frase que lo "
                f"anuncia, que es '{Mechanism.CONTEXT.value}'"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _el_minimo_no_pasa_del_maximo(self) -> Self:
        if self.min_tokens > self.max_tokens:
            msg = (
                f"la regla de autoidentificacion '{self.id}' pide entre "
                f"{self.min_tokens} y {self.max_tokens} palabras"
            )
            raise ValueError(msg)
        return self


class RecognizerSet(Frozen):
    """El juego de reconocedores de un idioma, tal como lo declara su archivo."""

    language: Locale
    #: El puntaje minimo para que un hallazgo cuente en este idioma. Un patron
    #: por debajo solo pasa si el contexto lo sube, que es como se pide contexto
    #: sin escribir una rama de codigo.
    score_threshold: float = Field(gt=0.0, le=1.0)
    recognizers: tuple[Recognizer, ...] = Field(min_length=1)
    fallback: FallbackRule
    #: Obligatoria, como el respaldo: un idioma sin ella dejaria salir el nombre
    #: que el modelo no etiqueta como persona, y el fallo no avisaria.
    self_identification: SelfIdentificationRule
    #: Saludos que el modelo de lenguaje toma por nombre cuando llegan en
    #: minuscula, que es como los transcribe el reconocedor de voz («hola tuve un
    #: choque» salia «[NOMBRE 1] tuve un choque», 2026-10-07). Solo se descarta un
    #: hallazgo cuyas palabras son **todas** de esta lista («hola», «hola hola»):
    #: «hola Miguel» se sigue tapando, y por eso no puede destapar un nombre real.
    never_personal: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _todo_sirve_al_idioma_del_archivo(self) -> Self:
        ajenos = sorted(r.id for r in self.recognizers if r.language != self.language)
        if ajenos:
            msg = (
                f"el archivo del idioma '{self.language}' declara los reconocedores "
                f"{ajenos}, que sirven a otro idioma. Un reconocedor sirve a **un** "
                "idioma: uno que dijera servir a los dos esconderia que en uno de "
                "ellos no funciona (BR2.7)"
            )
            raise ValueError(msg)
        if self.fallback.language != self.language:
            msg = (
                f"el archivo del idioma '{self.language}' declara una regla de "
                f"respaldo del idioma '{self.fallback.language}'"
            )
            raise ValueError(msg)
        if self.self_identification.language != self.language:
            msg = (
                f"el archivo del idioma '{self.language}' declara una regla de "
                f"autoidentificacion del idioma '{self.self_identification.language}'"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _los_identificadores_no_se_repiten(self) -> Self:
        vistos = [r.id for r in self.recognizers] + [self.fallback.id, self.self_identification.id]
        repetidos = sorted({i for i in vistos if vistos.count(i) > 1})
        if repetidos:
            msg = f"el juego del idioma '{self.language}' repite los identificadores {repetidos}"
            raise ValueError(msg)
        return self


class DetectedEntity(Frozen):
    """Un hallazgo del detector: donde estaba, no que era.

    **NUNCA lleva el valor detectado.** Un hallazgo que cargara su valor
    convertiria cualquier registro de diagnostico --un volcado, un log de
    depuracion, un mensaje de excepcion-- en la fuga que este componente existe
    para evitar. El valor se queda donde ya estaba: en el texto de entrada, que
    no sobrevive a la llamada.
    """

    entity_type: EntityType
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    #: Que reconocedor lo encontro. Es lo que permite medir por reconocedor y no
    #: solo por tipo, y lo que hace visible que el respaldo este tapando lo que a
    #: un reconocedor se le escapa (SEC-U3.9).
    recognizer_id: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _el_final_va_despues_del_principio(self) -> Self:
        if self.end <= self.start:
            msg = f"el hallazgo de '{self.recognizer_id}' acaba en {self.end} y empieza en {self.start}"
            raise ValueError(msg)
        return self

    def overlaps(self, other: DetectedEntity) -> bool:
        """Si los dos hallazgos comparten aunque sea un caracter."""
        return self.start < other.end and other.start < self.end

    @property
    def length(self) -> int:
        return self.end - self.start


class RedactionReport(Frozen):
    """El conteo que alimenta la medicion de NFR11.

    Se produce **aparte** del texto redactado, para que medir nunca obligue a
    conservar lo medido.
    """

    language: Locale
    #: Una entrada por tipo, tambien con cero. Un tipo ausente del informe y un
    #: tipo con cero hallazgos son cosas distintas, y confundirlas esconde un
    #: reconocedor que dejo de cargar.
    counts_by_type: dict[EntityType, int]
    counts_by_recognizer: dict[str, int]
    #: Los hallazgos del respaldo, en su propia cifra. Nunca se suman a la de un
    #: tipo del dominio: un respaldo que dispara mucho es la senal de que un
    #: reconocedor se rompio, y sumarlo la borraria (BR4.2).
    fallback_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _el_informe_declara_todos_los_tipos(self) -> Self:
        faltan = sorted(t.value for t in EntityType if t not in self.counts_by_type)
        if faltan:
            msg = (
                f"el informe del idioma '{self.language}' no declara los tipos "
                f"{faltan}; un tipo ausente y un tipo con cero hallazgos son cosas "
                "distintas, y confundirlas esconde un reconocedor que dejo de cargar"
            )
            raise ValueError(msg)
        return self

    @property
    def total(self) -> int:
        """Cuantos datos se taparon en total."""
        return sum(self.counts_by_type.values())

    def fallback_share(self) -> float:
        """La proporcion que tapo el respaldo frente al total (NFR11.2).

        Techo de 1 de cada 10, por idioma. No detiene la entrega --tapar de mas
        es el lado seguro del error-- pero pasarse significa una de dos cosas, y
        las dos son trabajo concreto: un reconocedor se rompio, o hay un formato
        frecuente sin reconocedor propio.
        """
        return self.fallback_count / self.total if self.total else 0.0
