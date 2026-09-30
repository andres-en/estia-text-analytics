from __future__ import annotations

import dataclasses
import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import AIUsage, Campana, Conversation, ConversationAnalysis
from .rules_config import CampanaRulesConfig
from .schema import EsquemaClasificacion
from .schema_engine import EsquemaCompilado, compilar_esquema
from .types import AnalysisResult


def session_ids_pendientes(session: Session, incluir_analizadas: bool = False) -> list[str]:
    """SESSION_IDs por analizar. Por defecto omite las que ya tienen análisis (idempotencia)."""
    stmt = select(Conversation.session_id).order_by(Conversation.started_at)
    if not incluir_analizadas:
        ya = select(ConversationAnalysis.conversation_id)
        stmt = stmt.where(Conversation.id.not_in(ya))
    return list(session.execute(stmt).scalars().all())


def get_campana_config(session: Session, campana_id: int | None) -> CampanaRulesConfig:
    """Config de reglas de una campaña. `campana_id=None` (conversación sin
    campaña asignada, ej. datos previos a esta funcionalidad) usa los defaults."""
    if campana_id is None:
        return CampanaRulesConfig()
    campana = session.get(Campana, campana_id)
    if campana is None:
        return CampanaRulesConfig()
    return CampanaRulesConfig.from_json(campana.configuracion)


def get_campana_esquema(session: Session, campana_id: int | None) -> EsquemaClasificacion | None:
    """`EsquemaClasificacion` propio de la campaña, o `None` si no tiene (en cuyo
    caso el llamador debe usar el motor fijo de `analysis/rules.py`)."""
    if campana_id is None:
        return None
    campana = session.get(Campana, campana_id)
    if campana is None or not campana.configuracion:
        return None
    return EsquemaClasificacion.from_json(campana.configuracion.get("esquema_clasificacion"))


def get_campana_esquema_compilado(session: Session, campana_id: int | None) -> EsquemaCompilado | None:
    esquema = get_campana_esquema(session, campana_id)
    return compilar_esquema(esquema) if esquema is not None else None


def guardar_analisis(session: Session, result: AnalysisResult) -> bool:
    """Inserta o actualiza el análisis de una conversación. Devuelve True si fue nuevo."""
    conv = session.execute(select(Conversation).where(Conversation.session_id == result.session_id)).scalar_one()

    existente = session.execute(
        select(ConversationAnalysis).where(ConversationAnalysis.conversation_id == conv.id)
    ).scalar_one_or_none()

    campos = dict(
        categoria_final=result.categoria_final,
        subcategoria=result.subcategoria,
        metodo=result.metodo,
        regla_aplicada=result.regla_aplicada,
        modelo_ia=result.modelo_ia,
        justificacion=result.justificacion,
        raw_response=result.raw_response,
        analyzed_at=dt.datetime.now(),
    )

    # `senales` es el JSON genérico (ver `ConversationAnalysis.senales`) — se
    # guarda siempre, sea cual sea el camino. Las 6 columnas booleanas legadas
    # solo existen para campañas con el motor fijo (`result.flags` viene
    # poblado); una campaña con `EsquemaClasificacion` propio las deja en False.
    if result.flags is not None:
        campos.update(
            interes_declarado=result.flags.interes_declarado,
            interes_confirmado=result.flags.interes_confirmado,
            busco_informacion=result.flags.busco_informacion,
            rechazo_explicito=result.flags.rechazo_explicito,
            bot_no_resolvio=result.flags.bot_no_resolvio,
            es_autorespondedor=result.flags.es_autorespondedor,
        )
        campos["senales"] = dataclasses.asdict(result.flags)
    else:
        campos["senales"] = result.senales or {}

    if result.tokens_prompt is not None and result.modelo_ia is not None:
        registrar_uso_ia(
            session,
            modelo=result.modelo_ia,
            tipo="clasificacion",
            tokens_prompt=result.tokens_prompt,
            tokens_completion=result.tokens_completion or 0,
            conversation_id=conv.id,
            campana_id=conv.campana_id,
        )

    if existente is None:
        session.add(ConversationAnalysis(conversation_id=conv.id, **campos))
        return True

    for k, v in campos.items():
        setattr(existente, k, v)
    return False


def registrar_uso_ia(
    session: Session,
    *,
    modelo: str,
    tipo: str,
    tokens_prompt: int,
    tokens_completion: int,
    conversation_id: int | None = None,
    campana_id: int | None = None,
) -> None:
    """Un renglón de `ai_usage` por cada llamada a OpenAI — ver `db/models.py::AIUsage`
    y `analysis/pricing.py` para convertir tokens a costo estimado."""
    session.add(
        AIUsage(
            modelo=modelo,
            tipo=tipo,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            conversation_id=conversation_id,
            campana_id=campana_id,
        )
    )


def _filtro_fecha_uso_ia(stmt, date_from: dt.date | None, date_to: dt.date | None):
    if date_from is not None:
        stmt = stmt.where(AIUsage.ocurrido_en >= dt.datetime.combine(date_from, dt.time.min))
    if date_to is not None:
        stmt = stmt.where(AIUsage.ocurrido_en < dt.datetime.combine(date_to + dt.timedelta(days=1), dt.time.min))
    return stmt


def resumen_uso_ia(session: Session, date_from: dt.date | None = None, date_to: dt.date | None = None) -> list[dict]:
    """Tokens/llamadas agrupados por modelo y tipo — lo consume el panel de
    "Uso de IA" del frontend."""
    stmt = _filtro_fecha_uso_ia(
        select(
            AIUsage.modelo,
            AIUsage.tipo,
            func.count(),
            func.sum(AIUsage.tokens_prompt),
            func.sum(AIUsage.tokens_completion),
        ).group_by(AIUsage.modelo, AIUsage.tipo),
        date_from,
        date_to,
    )

    return [
        {
            "modelo": modelo,
            "tipo": tipo,
            "llamadas": llamadas,
            "tokens_prompt": int(tokens_prompt or 0),
            "tokens_completion": int(tokens_completion or 0),
        }
        for modelo, tipo, llamadas, tokens_prompt, tokens_completion in session.execute(stmt).all()
    ]


def resumen_uso_ia_mensual(
    session: Session, date_from: dt.date | None = None, date_to: dt.date | None = None
) -> list[dict]:
    """Igual que `resumen_uso_ia`, pero agrupado por mes (`AAAA-MM`) además de
    por modelo — para el desglose mensual de gasto. Se agrupa en Python (no en
    SQL) para no depender de la función de formato de fecha de cada dialecto
    (MySQL vs. SQLite difieren acá) — la tabla es pequeña (un renglón por
    llamada a OpenAI, no por mensaje), así que no hay problema de volumen."""
    stmt = _filtro_fecha_uso_ia(
        select(AIUsage.ocurrido_en, AIUsage.modelo, AIUsage.tokens_prompt, AIUsage.tokens_completion),
        date_from,
        date_to,
    )

    por_mes: dict[tuple[str, str], dict] = {}
    for ocurrido_en, modelo, tokens_prompt, tokens_completion in session.execute(stmt).all():
        mes = ocurrido_en.strftime("%Y-%m")
        acumulado = por_mes.setdefault(
            (mes, modelo), {"mes": mes, "modelo": modelo, "llamadas": 0, "tokens_prompt": 0, "tokens_completion": 0}
        )
        acumulado["llamadas"] += 1
        acumulado["tokens_prompt"] += tokens_prompt
        acumulado["tokens_completion"] += tokens_completion

    return sorted(por_mes.values(), key=lambda f: (f["mes"], f["modelo"]))


def resumen_por_categoria(session: Session) -> list[tuple[str, int]]:
    filas = session.execute(
        select(ConversationAnalysis.categoria_final, func.count())
        .group_by(ConversationAnalysis.categoria_final)
        .order_by(func.count().desc())
    ).all()
    return [(c, n) for c, n in filas]


def resumen_por_metodo(session: Session) -> list[tuple[str, int]]:
    filas = session.execute(
        select(ConversationAnalysis.metodo, func.count())
        .group_by(ConversationAnalysis.metodo)
        .order_by(func.count().desc())
    ).all()
    return [(m, n) for m, n in filas]
