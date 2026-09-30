from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable
from typing import Protocol

from sqlalchemy.orm import sessionmaker

from ..conversation_view import ConversationTranscript, get_transcript
from . import repository
from .rules import clasificar_por_reglas, derive_categoria
from .rules_config import DEFAULT_COMPILED_RULES, CompiledRules, compile_rules
from .schema_engine import EsquemaCompilado, clasificar_por_esquema, resolver_clasificacion
from .types import AnalysisFlags, AnalysisResult

logger = logging.getLogger(__name__)


class ClasificadorIA(Protocol):
    """Contrato mínimo de la capa de IA, para poder sustituirla en pruebas."""

    modelo: str

    def clasificar(self, transcript: ConversationTranscript) -> tuple[AnalysisFlags, str, dict]:
        """Devuelve (señales, justificación, respuesta cruda)."""
        ...


class ClasificadorIAEsquema(Protocol):
    """Igual que `ClasificadorIA`, pero para una campaña con `EsquemaClasificacion`
    propio: las señales de IA son un dict genérico, no un `AnalysisFlags` fijo."""

    modelo: str

    def clasificar(
        self, transcript: ConversationTranscript, compilado: EsquemaCompilado
    ) -> tuple[dict[str, bool], str, dict]:
        """Devuelve (señales, justificación, respuesta cruda)."""
        ...


@dataclasses.dataclass
class ErrorAnalisis:
    session_id: str
    mensaje: str


@dataclasses.dataclass
class AnalysisReport:
    total_evaluadas: int = 0
    resueltas_por_regla: int = 0
    resueltas_por_ia: int = 0
    pendientes_de_ia: int = 0  # zona gris no resuelta por falta de cliente de IA
    nuevas: int = 0
    actualizadas: int = 0
    por_categoria: dict[str, int] = dataclasses.field(default_factory=dict)
    errores: list[ErrorAnalisis] = dataclasses.field(default_factory=list)


def analizar_conversacion(
    transcript: ConversationTranscript,
    ai_client: ClasificadorIA | None,
    rules: CompiledRules = DEFAULT_COMPILED_RULES,
) -> tuple[AnalysisResult | None, str | None]:
    """Aplica la cascada a una conversación.

    `rules` son los parámetros de detección (botones, regex) de la campaña de
    esta conversación — ver `analysis/rules_config.py`.

    Devuelve (resultado, error). Si la conversación cae en la zona gris y no hay
    cliente de IA disponible, devuelve (None, None): queda pendiente, no es un error.
    """
    outcome = clasificar_por_reglas(transcript, rules)

    if not outcome.requiere_ia:
        return (
            AnalysisResult(
                session_id=transcript.session_id,
                categoria_final=outcome.categoria,
                flags=outcome.flags,
                metodo="RULE",
                regla_aplicada=outcome.regla_aplicada,
            ),
            None,
        )

    if ai_client is None:
        return None, None

    try:
        flags_ia, justificacion, raw = ai_client.clasificar(transcript)
    except Exception as exc:  # un fallo puntual no debe abortar el lote
        return None, f"{type(exc).__name__}: {exc}"

    # Las reglas son el piso; la IA solo puede sumar señales, nunca apagarlas.
    flags = outcome.flags.merge(flags_ia)
    uso = getattr(ai_client, "ultimo_uso", None) or {}

    return (
        AnalysisResult(
            session_id=transcript.session_id,
            categoria_final=derive_categoria(flags, outcome.tiene_respuesta_cliente),
            flags=flags,
            metodo="AI",
            regla_aplicada=None,
            modelo_ia=ai_client.modelo,
            justificacion=justificacion,
            raw_response=raw,
            tokens_prompt=uso.get("tokens_prompt"),
            tokens_completion=uso.get("tokens_completion"),
        ),
        None,
    )


def analizar_conversacion_esquema(
    transcript: ConversationTranscript,
    compilado: EsquemaCompilado,
    ai_client: ClasificadorIAEsquema | None,
    rules: CompiledRules = DEFAULT_COMPILED_RULES,
) -> tuple[AnalysisResult | None, str | None]:
    """Igual que `analizar_conversacion`, pero para una campaña con
    `EsquemaClasificacion` propio (ver `analysis/schema_engine.py`) en vez del
    motor fijo hardcodeado para Acme."""
    outcome = clasificar_por_esquema(transcript, compilado, rules)

    if not outcome.requiere_ia:
        return (
            AnalysisResult(
                session_id=transcript.session_id,
                categoria_final=outcome.categoria,
                subcategoria=outcome.subcategoria,
                senales=outcome.senales,
                metodo="RULE",
                regla_aplicada="esquema",
            ),
            None,
        )

    if ai_client is None:
        return None, None

    try:
        senales_ia, justificacion, raw = ai_client.clasificar(transcript, compilado)
    except Exception as exc:  # un fallo puntual no debe abortar el lote
        return None, f"{type(exc).__name__}: {exc}"

    # Las reglas son el piso; la IA solo puede sumar señales de tipo "ia", nunca
    # apagar las que ya calculó `clasificar_por_esquema`.
    senales = {**outcome.senales, **{k: bool(v) for k, v in senales_ia.items()}}
    categoria, subcategoria = resolver_clasificacion(senales, compilado.esquema)
    uso = getattr(ai_client, "ultimo_uso", None) or {}

    return (
        AnalysisResult(
            session_id=transcript.session_id,
            categoria_final=categoria,
            subcategoria=subcategoria,
            senales=senales,
            metodo="AI",
            regla_aplicada=None,
            modelo_ia=ai_client.modelo,
            justificacion=justificacion,
            tokens_prompt=uso.get("tokens_prompt"),
            tokens_completion=uso.get("tokens_completion"),
            raw_response=raw,
        ),
        None,
    )


def run_analysis(
    session_factory: sessionmaker,
    ai_client: ClasificadorIA | None = None,
    limit: int | None = None,
    force: bool = False,
    on_progress: Callable[[AnalysisReport, int], None] | None = None,
    commit_every: int = 100,
    ai_client_esquema: ClasificadorIAEsquema | None = None,
) -> AnalysisReport:
    """Clasifica las conversaciones pendientes (o todas, con force=True).

    Hace `commit()` cada `commit_every` conversaciones (no solo al final): en
    lotes largos, si el proceso se interrumpe a medio camino, el progreso ya
    guardado no se pierde y una corrida posterior retoma donde quedó.

    `on_progress`, si se pasa, se llama tras cada conversación evaluada con
    `(report, total)` — pensado para que quien orquesta el análisis (ej. un
    hilo de fondo en el servidor web) pueda exponer una barra de progreso.

    `ai_client_esquema` clasifica las conversaciones de campañas con
    `EsquemaClasificacion` propio (ver `analysis/schema.py`); `ai_client` sigue
    siendo el de siempre, para las campañas sin esquema (motor fijo de Acme).
    Una campaña sin cliente de IA para su camino simplemente deja sus
    conversaciones de zona gris pendientes, igual que hoy.
    """
    report = AnalysisReport()
    # Una campaña por conversación, pero muchas conversaciones por campaña —
    # se compila una vez por campaña y no en cada iteración.
    rules_por_campana: dict[int | None, CompiledRules] = {}
    esquema_por_campana: dict[int | None, EsquemaCompilado | None] = {}

    with session_factory() as session:
        session_ids = repository.session_ids_pendientes(session, incluir_analizadas=force)
        if limit is not None:
            session_ids = session_ids[:limit]
        total = len(session_ids)

        for i, sid in enumerate(session_ids, start=1):
            transcript = get_transcript(session, sid)
            if transcript is None:
                report.errores.append(ErrorAnalisis(sid, "Conversation not found"))
                continue

            if transcript.campana_id not in rules_por_campana:
                config = repository.get_campana_config(session, transcript.campana_id)
                rules_por_campana[transcript.campana_id] = compile_rules(config)
                esquema_por_campana[transcript.campana_id] = repository.get_campana_esquema_compilado(
                    session, transcript.campana_id
                )
            rules = rules_por_campana[transcript.campana_id]
            compilado = esquema_por_campana[transcript.campana_id]

            report.total_evaluadas += 1
            if compilado is not None:
                result, error = analizar_conversacion_esquema(transcript, compilado, ai_client_esquema, rules)
            else:
                result, error = analizar_conversacion(transcript, ai_client, rules)

            if error is not None:
                logger.warning("Error analizando %s: %s", sid, error)
                report.errores.append(ErrorAnalisis(sid, error))
                continue

            if result is None:
                report.pendientes_de_ia += 1
                continue

            if result.metodo == "RULE":
                report.resueltas_por_regla += 1
            else:
                report.resueltas_por_ia += 1

            if repository.guardar_analisis(session, result):
                report.nuevas += 1
            else:
                report.actualizadas += 1

            report.por_categoria[result.categoria_final] = report.por_categoria.get(result.categoria_final, 0) + 1

            if i % commit_every == 0:
                session.commit()

            if on_progress is not None:
                on_progress(report, total)

        session.commit()

    return report


@dataclasses.dataclass
class RecalculoReport:
    revisadas: int = 0
    cambiadas: int = 0
    sin_esquema: int = 0


def recalcular_categorias(session_factory: sessionmaker, commit_every: int = 1000) -> RecalculoReport:
    """Reaplica el árbol de decisión (categoría + subcategoría) de cada campaña
    sobre las `senales` ya guardadas, SIN volver a llamar a la IA ni a las
    reglas — para cuando cambia la jerarquía o las categorías de un esquema
    (ver `derive_categoria`: "si el negocio cambia la jerarquía baste
    recalcular"). Las conversaciones de campañas sin esquema propio no se tocan.
    """
    from sqlalchemy import select

    from ..db.models import Conversation, ConversationAnalysis

    report = RecalculoReport()
    with session_factory() as session:
        esquemas: dict[int | None, EsquemaCompilado | None] = {}
        stmt = (
            select(ConversationAnalysis, Conversation.campana_id)
            .join(Conversation, Conversation.id == ConversationAnalysis.conversation_id)
            .execution_options(yield_per=500)
        )
        pendientes = 0
        for analisis, campana_id in session.execute(stmt):
            if campana_id not in esquemas:
                esquemas[campana_id] = repository.get_campana_esquema_compilado(session, campana_id)
            compilado = esquemas[campana_id]
            if compilado is None:
                report.sin_esquema += 1
                continue

            report.revisadas += 1
            senales = analisis.senales or {}
            if not senales:
                # Sin respuesta del cliente: no hay señales que evaluar.
                categoria, subcategoria = compilado.esquema.categoria_sin_respuesta, None
            else:
                categoria, subcategoria = resolver_clasificacion(senales, compilado.esquema)

            if analisis.categoria_final != categoria or analisis.subcategoria != subcategoria:
                analisis.categoria_final = categoria
                analisis.subcategoria = subcategoria
                report.cambiadas += 1
                pendientes += 1
                if pendientes >= commit_every:
                    session.commit()
                    pendientes = 0
        session.commit()
    return report
