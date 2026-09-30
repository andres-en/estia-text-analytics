from __future__ import annotations

import dataclasses

# Categorías (ver docs/classification-criteria.md)
SIN_RESPUESTA = "SIN_RESPUESTA"
INTERESADO = "INTERESADO"
RESOLVIO_DUDAS = "RESOLVIO_DUDAS"
NO_INTERESADO = "NO_INTERESADO"

# Obsoleta: se conserva en el ENUM de la base por compatibilidad con registros
# antiguos, pero ya no se asigna. Tras la validación con el usuario, el caso
# "respondió pero sin ninguna señal" se clasifica como NO_INTERESADO.
SIN_CLASIFICAR = "SIN_CLASIFICAR"


@dataclasses.dataclass(frozen=True)
class AnalysisFlags:
    """Señales detectadas en una conversación, independientes entre sí.

    Se conservan por separado para no perder información al colapsar la jerarquía
    en una sola categoría (ver sección 2.1 del documento de criterios).
    """

    # Expresó intención inicial (p. ej. pulsó "Quiero usar mi cupo"). Informativo:
    # NO determina la categoría, porque declarar intención no es adquirir el cupo.
    interes_declarado: bool = False
    # Concretó la adquisición: aceptó avanzar con la compra o el bot registró su
    # solicitud. Esta es la señal que produce la categoría INTERESADO.
    interes_confirmado: bool = False
    # El cliente obtuvo información del producto/cupo/condiciones, ya sea porque lo
    # preguntó o porque la consiguió respondiendo al bot dentro del flujo guiado.
    busco_informacion: bool = False
    rechazo_explicito: bool = False
    bot_no_resolvio: bool = False
    # El "cliente" es en realidad el autorespondedor de otra empresa: el número
    # de la base de campaña no corresponde a una persona.
    es_autorespondedor: bool = False

    def merge(self, other: AnalysisFlags) -> AnalysisFlags:
        """Combina dos conjuntos de señales con OR lógico.

        Las reglas son el piso (alta precisión) y la IA suma lo que las reglas no
        pueden ver; ninguna de las dos puede *desactivar* una señal de la otra.
        """
        return AnalysisFlags(
            interes_declarado=self.interes_declarado or other.interes_declarado,
            interes_confirmado=self.interes_confirmado or other.interes_confirmado,
            busco_informacion=self.busco_informacion or other.busco_informacion,
            rechazo_explicito=self.rechazo_explicito or other.rechazo_explicito,
            bot_no_resolvio=self.bot_no_resolvio or other.bot_no_resolvio,
            es_autorespondedor=self.es_autorespondedor or other.es_autorespondedor,
        )


@dataclasses.dataclass(frozen=True)
class AnalysisResult:
    session_id: str
    categoria_final: str
    metodo: str  # RULE | AI
    # Exactamente uno de los dos: `flags` cuando la campaña usa el motor fijo
    # (`rules.py`, hardcodeado para Acme), `senales` cuando usa un
    # `EsquemaClasificacion` propio (ver `analysis/schema_engine.py`). Ambos se
    # guardan siempre como el mismo JSON genérico en `ConversationAnalysis.senales`
    # — ver `repository.guardar_analisis`.
    flags: AnalysisFlags | None = None
    senales: dict[str, bool] | None = None
    # Segundo nivel opcional (ver `EsquemaClasificacion.subcategorias`).
    subcategoria: str | None = None
    regla_aplicada: str | None = None
    modelo_ia: str | None = None
    justificacion: str | None = None
    raw_response: dict | None = None
    # Tokens de la llamada a OpenAI que produjo este resultado — None si se
    # resolvió por regla (no hubo llamada) o si el cliente de IA no reporta
    # uso (ej. un fake de test). Ver `analysis/pricing.py` para el costo.
    tokens_prompt: int | None = None
    tokens_completion: int | None = None
