from __future__ import annotations

import dataclasses

from ..conversation_view import ConversationTranscript
from .rules_config import DEFAULT_COMPILED_RULES, CompiledRules, normalizar
from .types import (
    INTERESADO,
    NO_INTERESADO,
    RESOLVIO_DUDAS,
    SIN_RESPUESTA,
    AnalysisFlags,
)

__all__ = [
    "RuleOutcome",
    "detectar_senales",
    "derive_categoria",
    "clasificar_por_reglas",
]


@dataclasses.dataclass(frozen=True)
class RuleOutcome:
    flags: AnalysisFlags
    categoria: str | None  # None => indeterminado por reglas, pasa a IA
    regla_aplicada: str | None
    requiere_ia: bool
    tiene_respuesta_cliente: bool


def detectar_senales(
    transcript: ConversationTranscript, rules: CompiledRules = DEFAULT_COMPILED_RULES
) -> AnalysisFlags:
    """Detecta las señales que las reglas pueden afirmar con certeza."""
    cliente = [m for m in transcript.messages if m.sender == "CUSTOMER"]
    bot = [m for m in transcript.messages if m.sender == "BOT"]
    textos_cliente = {normalizar(m.message) for m in cliente}

    # El bot registró la solicitud y la escaló a un asesor: el cliente concretó.
    interes_confirmado = any(rules.rx_interes_confirmado.search(m.message) for m in bot)
    # Pulsar el botón es declarar intención, NO adquirir el cupo: informativo.
    interes_declarado = interes_confirmado or rules.boton_cupo in textos_cliente or rules.boton_asesor in textos_cliente
    rechazo = rules.boton_no_interesado in textos_cliente or any(
        rules.rx_encuesta_rechazo.search(m.message) for m in bot
    )
    bot_no_resolvio = any(rules.rx_bot_no_resolvio.search(m.message) for m in bot)
    # Se busca solo en los mensajes del "cliente": es su autorespondedor el que delata
    # que el número pertenece a una empresa.
    es_autorespondedor = any(rules.rx_autorespondedor.search(m.message) for m in cliente)

    return AnalysisFlags(
        interes_declarado=interes_declarado,
        interes_confirmado=interes_confirmado,
        # busco_informacion NO se determina por reglas: solo el 6% usa signo '?' y
        # además cuenta la información obtenida sin preguntar. Requiere criterio
        # semántico (IA).
        busco_informacion=False,
        rechazo_explicito=rechazo,
        bot_no_resolvio=bot_no_resolvio,
        es_autorespondedor=es_autorespondedor,
    )


def derive_categoria(flags: AnalysisFlags, tiene_respuesta_cliente: bool) -> str:
    """Aplica la jerarquía INTERESADO > RESOLVIO_DUDAS > NO_INTERESADO.

    Se calcula siempre en Python (nunca la pide la IA), de modo que si el negocio
    cambia la jerarquía baste recalcular, sin volver a llamar a la API.

    INTERESADO exige `interes_confirmado` (el cliente adquirió/concretó el cupo).
    Declarar intención sin concretar NO basta: si además preguntó será
    RESOLVIO_DUDAS y, si no, NO_INTERESADO.
    """
    if not tiene_respuesta_cliente:
        return SIN_RESPUESTA
    if flags.interes_confirmado:
        return INTERESADO
    if flags.busco_informacion:
        return RESOLVIO_DUDAS
    # Respondió sin concretar ni preguntar (incluye rechazos explícitos y a los
    # autorespondedores de empresas): no es un interesado.
    return NO_INTERESADO


def clasificar_por_reglas(
    transcript: ConversationTranscript, rules: CompiledRules = DEFAULT_COMPILED_RULES
) -> RuleOutcome:
    """Capas 0-2 de la cascada. Determina si hace falta consultar a la IA.

    Determinístico y sin efectos secundarios: no toca la base de datos ni la red.
    `rules` son los parámetros de detección de la campaña de esta conversación
    (botones, regex, cortesías) — ver `analysis/rules_config.py`. El default
    reproduce el comportamiento original si no se pasa ninguno.
    """
    cliente = [m for m in transcript.messages if m.sender == "CUSTOMER"]

    # Capa 0 — el cliente nunca escribió.
    if not cliente:
        return RuleOutcome(
            flags=AnalysisFlags(),
            categoria=SIN_RESPUESTA,
            regla_aplicada="sin_mensajes_cliente",
            requiere_ia=False,
            tiene_respuesta_cliente=False,
        )

    flags = detectar_senales(transcript, rules)

    # Capa 1 — el bot registró la solicitud: el cliente concretó la adquisición.
    # Por la jerarquía INTERESADO gana, así que no hace falta consultar a la IA.
    if flags.interes_confirmado:
        return RuleOutcome(
            flags=flags,
            categoria=INTERESADO,
            regla_aplicada="interes_confirmado_por_bot",
            requiere_ia=False,
            tiene_respuesta_cliente=True,
        )

    # Texto del cliente que aún no está explicado por un botón, una cortesía, un
    # dígito de encuesta o el autorespondedor de la empresa.
    residual = [
        m for m in cliente if not rules.es_ignorable(m.message) and not rules.rx_autorespondedor.search(m.message)
    ]

    # Capa 2 — contestó el autorespondedor de una empresa y nadie más escribió:
    # no hay una persona real que evaluar.
    # OJO: si después del autorespondedor sí escribió un humano (queda texto residual),
    # NO se corta aquí — esa persona puede preguntar y debe evaluarla la IA.
    if flags.es_autorespondedor and not residual:
        return RuleOutcome(
            flags=flags,
            categoria=NO_INTERESADO,
            regla_aplicada="autorespondedor_de_empresa",
            requiere_ia=False,
            tiene_respuesta_cliente=True,
        )

    # Capa 3 — todos los mensajes del cliente son botones, cortesías o dígitos de
    # encuesta: no hay texto libre que interpretar, la IA no aportaría nada.
    if not residual:
        return RuleOutcome(
            flags=flags,
            categoria=NO_INTERESADO,
            regla_aplicada="sin_texto_libre_que_interpretar",
            requiere_ia=False,
            tiene_respuesta_cliente=True,
        )

    # Capa 4 — zona gris: hay texto libre que solo se puede interpretar semánticamente.
    return RuleOutcome(
        flags=flags,
        categoria=None,
        regla_aplicada=None,
        requiere_ia=True,
        tiene_respuesta_cliente=True,
    )
