from __future__ import annotations

import dataclasses
import re
import unicodedata

# Valores por defecto: son EXACTAMENTE los que hoy están hardcodeados para el
# bot de venta de cupos, así que una campaña sin `configuracion` (o la
# "Campaña histórica" de una migración) clasifica idéntico a como lo hacía
# antes de que esto fuera configurable. Ver docs/classification-criteria.md.
DEFAULT_BOTON_CUPO = "quiero usar mi cupo"
DEFAULT_BOTON_ASESOR = "hablar con un asesor"
DEFAULT_BOTON_NO_INTERESADO = "no estoy interesado"

DEFAULT_RX_INTERES_CONFIRMADO = r"hemos registrado tu inter"
DEFAULT_RX_ENCUESTA_RECHAZO = r"lamentamos que por ahora no desees"
DEFAULT_RX_BOT_NO_RESOLVIO = r"no cuento con informaci|no tengo acceso|no dispongo de|no puedo consultar"
DEFAULT_RX_AUTORESPONDEDOR = (
    r"gracias por comunicar(te|se) con"
    r"|bienvenid[o@a]\W*\(?a\)?\s"
    r"|c[oó]mo podemos ayudarte"
    r"|nuestro horario (de atenci[oó]n|administrativo)"
    r"|horario administrativo"
    r"|en este momento no podemos responder"
    r"|debido al alto flujo"
    r"|nuestr[oa]s? (nuevas?\s+)?(promociones|servicios|productos|asesores)"
    r"|un asesor.{0,30}te contactar"
)

DEFAULT_CORTESIAS: tuple[str, ...] = (
    "hola",
    "holaa",
    "buenas",
    "buenos dias",
    "buenas tardes",
    "buenas noches",
    "buen dia",
    "gracias",
    "muchas gracias",
    "mil gracias",
    "ok",
    "oki",
    "okay",
    "listo",
    "bueno",
    "si",
    "no",
    "claro",
    "de nada",
    "adios",
    "chao",
)


@dataclasses.dataclass(frozen=True)
class CampanaRulesConfig:
    """Parámetros de detección de señales para UNA campaña.

    `CampanaRulesConfig()` (sin argumentos) reproduce el comportamiento
    hardcodeado original — es el fallback cuando `campanas.configuracion`
    es NULL o le faltan claves.
    """

    boton_cupo: str = DEFAULT_BOTON_CUPO
    boton_asesor: str = DEFAULT_BOTON_ASESOR
    boton_no_interesado: str = DEFAULT_BOTON_NO_INTERESADO
    rx_interes_confirmado: str = DEFAULT_RX_INTERES_CONFIRMADO
    rx_encuesta_rechazo: str = DEFAULT_RX_ENCUESTA_RECHAZO
    rx_bot_no_resolvio: str = DEFAULT_RX_BOT_NO_RESOLVIO
    rx_autorespondedor: str = DEFAULT_RX_AUTORESPONDEDOR
    cortesias: tuple[str, ...] = DEFAULT_CORTESIAS

    def to_json(self) -> dict:
        return {
            "boton_cupo": self.boton_cupo,
            "boton_asesor": self.boton_asesor,
            "boton_no_interesado": self.boton_no_interesado,
            "rx_interes_confirmado": self.rx_interes_confirmado,
            "rx_encuesta_rechazo": self.rx_encuesta_rechazo,
            "rx_bot_no_resolvio": self.rx_bot_no_resolvio,
            "rx_autorespondedor": self.rx_autorespondedor,
            "cortesias": list(self.cortesias),
        }

    @classmethod
    def from_json(cls, data: dict | None) -> CampanaRulesConfig:
        """Construye la config a partir de `campanas.configuracion`.

        `data=None` (o un dict vacío/parcial) usa los defaults para lo que
        falte — así una campaña recién creada, o una fila vieja sin esta
        columna, sigue clasificando como antes.
        """
        if not data:
            return cls()
        campos = dataclasses.fields(cls)
        kwargs = {}
        for campo in campos:
            if campo.name in data and data[campo.name] is not None:
                valor = data[campo.name]
                kwargs[campo.name] = tuple(valor) if campo.name == "cortesias" else valor
        return cls(**kwargs)

    def validar(self) -> str | None:
        """Devuelve un mensaje de error si algún regex no compila, o None si todo bien."""
        for nombre in ("rx_interes_confirmado", "rx_encuesta_rechazo", "rx_bot_no_resolvio", "rx_autorespondedor"):
            patron = getattr(self, nombre)
            try:
                re.compile(patron, re.IGNORECASE)
            except re.error as exc:
                return f"{nombre}: invalid regular expression ({exc})"
        return None


def normalizar(texto: str) -> str:
    t = texto.strip().lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return t.strip(" .,!¡?¿\n\t")


RX_DIGITO_ENCUESTA = re.compile(r"^[1-6]$")


@dataclasses.dataclass(frozen=True)
class CompiledRules:
    """`CampanaRulesConfig` con los regex pre-compilados y los sets de texto
    normalizados una sola vez — se arma una vez por campaña, no por conversación.
    """

    boton_cupo: str
    boton_asesor: str
    boton_no_interesado: str
    botones: frozenset[str]
    cortesias: frozenset[str]
    rx_interes_confirmado: re.Pattern
    rx_encuesta_rechazo: re.Pattern
    rx_bot_no_resolvio: re.Pattern
    rx_autorespondedor: re.Pattern
    rx_digito_encuesta: re.Pattern = RX_DIGITO_ENCUESTA

    def es_ignorable(self, texto: str) -> bool:
        """True si el mensaje no aporta señal (botón ya interpretado, cortesía o
        dígito de encuesta)."""
        t = normalizar(texto)
        if not t:
            return True
        if t in self.botones or t in self.cortesias:
            return True
        if self.rx_digito_encuesta.match(t):
            return True
        return False


def compile_rules(config: CampanaRulesConfig) -> CompiledRules:
    boton_cupo = normalizar(config.boton_cupo)
    boton_asesor = normalizar(config.boton_asesor)
    boton_no_interesado = normalizar(config.boton_no_interesado)
    return CompiledRules(
        boton_cupo=boton_cupo,
        boton_asesor=boton_asesor,
        boton_no_interesado=boton_no_interesado,
        botones=frozenset({boton_cupo, boton_asesor, boton_no_interesado}),
        cortesias=frozenset(normalizar(c) for c in config.cortesias),
        rx_interes_confirmado=re.compile(config.rx_interes_confirmado, re.IGNORECASE),
        rx_encuesta_rechazo=re.compile(config.rx_encuesta_rechazo, re.IGNORECASE),
        rx_bot_no_resolvio=re.compile(config.rx_bot_no_resolvio, re.IGNORECASE),
        rx_autorespondedor=re.compile(config.rx_autorespondedor, re.IGNORECASE),
    )


DEFAULT_COMPILED_RULES = compile_rules(CampanaRulesConfig())
