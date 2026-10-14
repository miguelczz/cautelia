"""El unico punto que lee variables de entorno.

Ningun modulo lee variables por su cuenta (SEC-U1.2). La razon no es de estilo:
la validacion vive en la construccion de este objeto, que es lo primero que hace
la raiz de composicion, y eso es lo que permite que una corrida sin clave falle
**antes** de construir ningun cliente de proveedor, con la cuota intacta y sin
la mitad de los casos ya ejecutados (BR1.2, REL-U1.4).

En desarrollo, la carga de un `.env` local la hace el archivo de tareas al
invocar el comando, no este codigo: asi el aplicativo no tiene una ruta distinta
en la maquina de quien desarrolla y en la tuberia.
"""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: La variable que necesita un caso que llama al modelo durante una evaluacion.
#: Las claves estan separadas por uso (voz, chat, evaluaciones) para que una
#: cuota agotada no tumbe las otras dos ni una clave filtrada agote el
#: presupuesto entero.
EVALS_MODEL_API_KEY_VAR = "UNTANGLE_EVALS_MODEL_API_KEY"

#: Las **otras tres** claves de modelo, una por uso, que anade U5. Son cuatro y
#: no una porque el proveedor limita por proyecto: cada clave vive en su propio
#: proyecto, y por eso una cuota agotada en el chat no apaga la voz (ADR-018,
#: enmienda del 2026-09-17). El proyecto **no** se declara aparte: la clave se
#: emite dentro del suyo y lo lleva consigo, y una segunda declaracion seria una
#: fuente de verdad que puede discrepar de la primera.
VOICE_MODEL_API_KEY_VAR = "UNTANGLE_VOICE_MODEL_API_KEY"
CHAT_MODEL_API_KEY_VAR = "UNTANGLE_CHAT_MODEL_API_KEY"
OPERATIONS_MODEL_API_KEY_VAR = "UNTANGLE_OPERATIONS_MODEL_API_KEY"

#: La clave del uso `corpus` (U8, PASO 0 de `u8-tanda-3`): embeddings de la
#: ingesta y de la consulta de recuperacion. Separada de las cuatro de arriba
#: por la misma razon que ellas lo estan entre si: una cuota agotada en el
#: corpus no debe apagar la voz, el chat, las evaluaciones ni la operacion.
CORPUS_MODEL_API_KEY_VAR = "UNTANGLE_CORPUS_MODEL_API_KEY"

#: La clave de Anthropic del uso `chat_reply` (2026-10-07).
CHAT_REPLY_API_KEY_VAR = "UNTANGLE_ANTHROPIC_API_KEY_CHAT"

#: La clave de Anthropic de las evaluaciones de la comprension (2026-10-07).
#: Separada de la del chat: una corrida de evaluaciones no gasta el saldo que
#: atiende a los visitantes, ni una clave filtrada en una corrida lo agota.
EVALS_ANTHROPIC_API_KEY_VAR = "UNTANGLE_ANTHROPIC_API_KEY_EVALS"

#: Las **dos** claves de los proveedores de voz, que anade U15. Son del **uso
#: `voice`** y de nadie mas: la fabrica construye con ellas los adaptadores de
#: voz y nunca con la clave de otro uso (BR1.3, SEC-U15.2). Son dos y no una
#: porque son dos cuentas: Deepgram transcribe y habla con la voz de respaldo
#: (Aura-2), y Cartesia habla con Catalina, la voz principal. Cada una lleva su
#: propio tope en su proveedor (PA-9.2).
VOICE_DEEPGRAM_API_KEY_VAR = "UNTANGLE_VOICE_DEEPGRAM_API_KEY"
VOICE_CARTESIA_API_KEY_VAR = "UNTANGLE_VOICE_CARTESIA_API_KEY"

#: Las **dos** claves de firma de U2, una por uso. No es ceremonia: tienen
#: radios de dano distintos. La de enlaces abre casos cuyo identificador ya se
#: conozca; la de bandeja fabrica un ajustador en cualquier aseguradora. Que
#: esten separadas no se declara, se **prueba**: hay un caso que presenta lo
#: firmado con una clave al verificador de la otra y exige rechazo (NFR-U2-1).
STAFF_CREDENTIAL_SIGNING_KEY_VAR = "UNTANGLE_STAFF_CREDENTIAL_SIGNING_KEY"
CASE_LINK_SIGNING_KEY_VAR = "UNTANGLE_CASE_LINK_SIGNING_KEY"

#: La tercera, de U16: el token que ata un socket a una llamada. Hasta el
#: 2026-10-03 la voz firmaba con la del enlace de caso, y eso ataba dos
#: superficies a un solo secreto: rotar la clave del enlace invalidaba los
#: sockets vivos, y un compromiso de esa clave abarcaba las dos. Son dos
#: familias de token con vidas, formatos y radios de dano distintos, asi que
#: son dos claves.
VOICE_SOCKET_SIGNING_KEY_VAR = "UNTANGLE_VOICE_TOKEN_SIGNING_KEY"

#: La clave de cifrado en reposo de los campos del caso (PA-8, U4). Separada de
#: las dos de firma por la misma razon que ellas lo estan entre si: sus radios de
#: dano son distintos. Una clave de firma filtrada deja fabricar credenciales
#: desde hoy; esta deja leer todo lo guardado hasta hoy.
CASE_FIELD_ENCRYPTION_KEY_VAR = "UNTANGLE_CASE_FIELD_ENCRYPTION_KEY"


class Settings(BaseSettings):
    """La configuracion del proceso, leida del entorno una sola vez."""

    model_config = SettingsConfigDict(
        env_prefix="UNTANGLE_",
        extra="ignore",
        frozen=True,
        # Un valor que no valida **no se repite en el error**. Sin esto, pydantic
        # incluye `input_value=...` en el mensaje, y una clave demasiado corta
        # acabaria en la salida de arranque: justo el secreto que se quiere
        # proteger, en el registro del despliegue.
        hide_input_in_errors=True,
    )

    #: Donde corre. Solo cambia lo que se registra, nunca una regla de negocio.
    env: Literal["local", "ci"] = "local"

    #: Clave del proveedor de modelo para las evaluaciones. Ausente a proposito
    #: en el camino de arranque: el subconjunto `smoke` no la necesita.
    evals_model_api_key: str | None = None

    #: Las tres claves de modelo restantes, una por uso (U5, BR1.3). Las cuatro
    #: son opcionales por la misma razon que la de evaluaciones: hay un camino
    #: --del clon al reporte-- que llega hasta el final sin cuenta en ningun
    #: proveedor. Quien exige una la exige al arrancar, por uso y por su nombre:
    #: `providers.factory.ProviderClients.require(...)`.
    voice_model_api_key: str | None = None
    chat_model_api_key: str | None = None
    operations_model_api_key: str | None = None

    #: La clave del uso `corpus` (U8). Opcional por la misma razon que las
    #: otras cuatro: `providers.factory.ProviderClients.require(Use.CORPUS)`
    #: es quien la exige, y solo cuando algo de verdad la necesita (la ingesta
    #: o el nodo `policy_verification`).
    corpus_model_api_key: str | None = None

    #: La clave de Anthropic del uso `chat_reply`, la redaccion natural del chat
    #: (2026-10-07). Opcional: sin ella el chat responde con las frases del
    #: catalogo, que es lo que hacia antes, y nada mas cambia.
    anthropic_api_key_chat: str | None = None

    #: La clave de Anthropic de las evaluaciones de la comprension (2026-10-07).
    #: Opcional: sin ella esos casos quedan no medidos con su causa.
    anthropic_api_key_evals: str | None = None

    #: Las dos claves de los proveedores de voz del uso `voice` (U15). Opcionales
    #: por la misma razon que las de modelo: el camino del clon al reporte no
    #: habla con ningun proveedor de voz. Sin ellas la voz no se construye, y
    #: pedirla falla nombrando la variable que falta; el chat no las necesita.
    voice_deepgram_api_key: str | None = None
    voice_cartesia_api_key: str | None = None

    #: Backend de trazas. Dependencia **opcional**: sin el, el reporte se genera
    #: igual y los enlaces salen marcados como no disponibles (BR1.3).
    traces_endpoint: str | None = None

    #: Langfuse Cloud, el backend de trazas del proyecto (2026-10-14). Las tres
    #: juntas o ninguna: sin las tres no se instala el transporte, no corre la
    #: exportacion periodica y nada se manda a ningun lado. Un proyecto de Langfuse
    #: por entorno (local y produccion), asi que las claves de uno no sirven en el
    #: otro y el reinicio nocturno de uno no toca las trazas del otro.
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None

    #: La base de datos del aplicativo. La lee la raiz de composicion y se la
    #: pasa al punto unico de sesion; ningun otro modulo la ve. Ausente en el
    #: camino de arranque: `mise run bootstrap` llega al reporte sin base.
    database_url: str | None = None

    #: Firma la credencial de la bandeja (doce horas de vida).
    staff_credential_signing_key: str | None = None

    #: Firma el enlace de caso (una hora de vida). **Distinta de la anterior**.
    case_link_signing_key: str | None = None

    #: Firma el token de socket de la voz (un minuto de vida). **Distinta de las
    #: dos anteriores**: el enlace de caso es un portador que viaja en una URL y
    #: se canjea, este no viaja en ninguna URL y se usa una sola vez. Opcional
    #: como las demas, y quien la exige es el token al emitirse, nombrandola.
    voice_token_signing_key: str | None = None

    #: Cifra en reposo los datos personales del caso (PA-8). Es la tercera clave
    #: y la unica que **no** es de firma: las dos de arriba autentican algo que
    #: ya paso, esta protege algo guardado. Sin ella el proceso no arranca, pero
    #: el tipo la declara opcional porque quien decide es `case_record.crypto`,
    #: que falla cerrado con un mensaje que dice como generarla; un `str` a secas
    #: aqui haria fallar tambien el camino de arranque, que no toca casos.
    case_field_encryption_key: str | None = None

    #: El despliegue vivo contra el que corre el escenario adversarial RT-4
    #: (NFR10.3). Ausente, sus casos quedan **no medidos** con su causa: una
    #: compuerta que no se pudo ejecutar jamas se da por verde.
    live_target_url: str | None = None

    #: El commit que corre, para la salud de listo (C-02, `version`). Lo pone el
    #: despliegue; sin el, la salud dice `unknown`, que es verdad, en vez de
    #: inventar uno. Ningun modulo pregunta a git: en el despliegue no hay
    #: repositorio.
    commit_sha: str | None = None

    #: Los dos enlaces externos del inicio y de la pagina "no disponible"
    #: (CG-U6-6, BR4.4). Opcionales: sin variable no hay enlace, y mientras el
    #: repositorio sea privado (D-017) la del README se deja vacia. Solo se
    #: aceptan direcciones `https` con servidor: un enlace publico que no lo es
    #: no deberia llegar a la pagina de un visitante.
    readme_url: str | None = None
    video_url: str | None = None

    #: Que frase de emergencia dice la agente (U10, BR3.3, CG-U10-2). `public`
    #: --la de por omision-- dice que es una demostracion y que no puede enviar
    #: ayuda; `local` dice que se llame al 911 y es la que comprueban los golden
    #: sets. Lo seguro cuando nadie dijo nada es la publica: la demo que se ve
    #: desde fuera no puede enviar a nadie.
    emergency_phrase: Literal["public", "local"] = "public"

    @field_validator("emergency_phrase", mode="before")
    @classmethod
    def _vacia_es_la_publica(cls, valor: object) -> object:
        # Una plantilla copiada tal cual deja la variable vacia, y vacia tiene que
        # significar lo seguro, no un arranque fallido.
        return "public" if valor in (None, "") else valor

    @field_validator("langfuse_public_key", "langfuse_secret_key", mode="before")
    @classmethod
    def _clave_vacia_es_ausente(cls, valor: object) -> object:
        # Una plantilla copiada tal cual deja la variable vacia. Vacia es "no
        # configurada", nunca una clave de cero caracteres que armaria la cabecera
        # de autenticacion con nada dentro.
        return None if valor in (None, "") else valor

    @field_validator("langfuse_host", mode="before")
    @classmethod
    def _direccion_de_langfuse(cls, valor: object) -> object:
        if valor in (None, ""):
            return None
        if not isinstance(valor, str):
            return valor
        # Sin barra final: las rutas de la API se anaden con la suya, y una doble
        # barra es una ruta distinta para algunos servidores.
        direccion = valor.strip().rstrip("/")
        partes = urlsplit(direccion)
        # `https` y con servidor, y nada mas: las claves viajan en una cabecera de
        # cada peticion, y por http irian a la vista de quien mire la red. Sin ruta
        # ni consulta, porque la raiz de la API es la del servidor.
        if partes.scheme != "https" or not partes.netloc or partes.path or partes.query:
            msg = (
                "UNTANGLE_LANGFUSE_HOST tiene que ser la direccion https del servidor "
                "sin ruta, por ejemplo https://us.cloud.langfuse.com"
            )
            raise ValueError(msg)
        return direccion

    @field_validator("readme_url", "video_url")
    @classmethod
    def _enlace_publico(cls, valor: str | None) -> str | None:
        if valor is None or valor == "":
            return None
        partes = urlsplit(valor)
        if partes.scheme != "https" or not partes.netloc:
            msg = (
                f"un enlace publico tiene que ser una direccion https con servidor; llego '{valor}'"
            )
            raise ValueError(msg)
        return valor

    @property
    def traces_available(self) -> bool:
        return bool(self.traces_endpoint)

    @property
    def langfuse_configured(self) -> bool:
        """Las tres variables de Langfuse estan puestas. Con una sola no se hace nada."""
        return bool(self.langfuse_public_key and self.langfuse_secret_key and self.langfuse_host)


#: Los nombres que este codigo lee. `env_check` los compara contra
#: `.env.example` en las dos direcciones: una variable que el codigo exige y la
#: plantilla no lista es un fallo, y una listada que nadie lee, tambien.
def variable_names() -> tuple[str, ...]:
    prefijo = Settings.model_config.get("env_prefix", "")
    return tuple(sorted(f"{prefijo}{campo}".upper() for campo in Settings.model_fields))
