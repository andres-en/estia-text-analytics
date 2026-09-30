from __future__ import annotations

import dataclasses
import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db.models import Campana, Conversation, ConversationAnalysis, Message

SENDER_LABEL = {"CUSTOMER": "Customer", "BOT": "Bot", "SYSTEM": "System"}

CATEGORIA_LABEL = {
    "SIN_RESPUESTA": "No response",
    "INTERESADO": "Interested",
    "RESOLVIO_DUDAS": "Questions answered",
    "NO_INTERESADO": "Not interested",
    "SIN_CLASIFICAR": "Sin clasificar",
}

# Etiquetas de respaldo para ids de indicador que no se resuelven contra el
# esquema de ninguna campaña (ej. `senales` de conversaciones analizadas antes
# de que existiera `EsquemaClasificacion`, o una campaña ya borrada) — ver
# `_resolver_indicador_label`. Cubre los 6 nombres que usaba el motor fijo de
# Acme antes de tener esquema propio.
INDICADOR_LABEL = {
    "interes_declarado": "Declared interest",
    "interes_confirmado": "Confirmed interest",
    "busco_informacion": "Sought information",
    "rechazo_explicito": "Explicit rejection",
    "bot_no_resolvio": "Bot could not help",
    "es_autorespondedor": "Business auto-reply",
}

DEFAULT_PAGE_SIZE = 50


def _resolver_categoria_label(session: Session):
    """Devuelve una función `(campana_id, categoria) -> label`, resuelta por el
    esquema propio de la campaña de esa conversación (o el esquema por defecto
    de Acme si no tiene uno propio — mismo criterio que usa la clasificación,
    ver `analysis/schema.py`). Cachea por campaña dentro de esta sesión: no
    repite la resolución en cada fila de una lista paginada."""
    # Import diferido: `analysis.schema_engine` importa `ConversationTranscript`
    # de este módulo, así que importar `analysis.*` al tope de este archivo
    # crearía un import circular.
    from .analysis.repository import get_campana_esquema
    from .analysis.schema import DEFAULT_ESQUEMA

    cache: dict[int | None, dict[str, str]] = {}

    def resolver(campana_id: int | None, categoria: str | None) -> str | None:
        if categoria is None:
            return None
        if campana_id not in cache:
            esquema = get_campana_esquema(session, campana_id) or DEFAULT_ESQUEMA
            cache[campana_id] = {c.id: c.label for c in esquema.categorias}
        return cache[campana_id].get(categoria, CATEGORIA_LABEL.get(categoria, categoria))

    return resolver


def _resolver_subcategoria_label(session: Session):
    """`(campana_id, subcategoria) -> label`, por el esquema de la campaña (mismo
    patrón que `_resolver_categoria_label`)."""
    from .analysis.repository import get_campana_esquema

    cache: dict[int | None, dict[str, str]] = {}

    def resolver(campana_id: int | None, subcategoria: str | None) -> str | None:
        if subcategoria is None:
            return None
        if campana_id not in cache:
            esquema = get_campana_esquema(session, campana_id)
            cache[campana_id] = {c.id: c.label for c in esquema.subcategorias} if esquema else {}
        return cache[campana_id].get(subcategoria, subcategoria)

    return resolver


def _resolver_indicador_label(session: Session):
    """Igual que `_resolver_categoria_label`, pero para los ids de `senales` —
    usado por el reporte Excel para poner una columna con nombre legible por
    cada indicador presente, en vez de la lista fija de 6 columnas de antes
    (ver `reports.build_conversations_xlsx`)."""
    from .analysis.repository import get_campana_esquema
    from .analysis.schema import DEFAULT_ESQUEMA

    cache: dict[int | None, dict[str, str]] = {}

    def resolver(campana_id: int | None, indicador_id: str) -> str:
        if campana_id not in cache:
            esquema = get_campana_esquema(session, campana_id) or DEFAULT_ESQUEMA
            cache[campana_id] = {i.id: i.label for i in esquema.indicadores}
        return cache[campana_id].get(indicador_id) or INDICADOR_LABEL.get(
            indicador_id, indicador_id.replace("_", " ").capitalize()
        )

    return resolver


def categorias_disponibles(session: Session) -> list[dict]:
    """Catálogo de categorías de este cliente: la unión de las categorías de
    todas sus campañas (cada una con su propio esquema, o el de Acme por
    defecto si no tiene uno), más la entrada sintética `SIN_ANALIZAR`. Primera
    definición de un id gana si dos campañas coinciden en un mismo id. Lo usa
    el frontend para resolver colores/etiquetas sin tenerlos hardcodeados
    (dashboard, tabla de conversaciones, gráficas, filtro)."""
    from .analysis.repository import get_campana_esquema
    from .analysis.schema import DEFAULT_ESQUEMA

    vistas: dict[str, dict] = {}
    ids_campana = [c.id_campana for c in session.execute(select(Campana)).scalars().all()]
    for campana_id in ids_campana or [None]:
        esquema = get_campana_esquema(session, campana_id) or DEFAULT_ESQUEMA
        for cat in esquema.categorias:
            vistas.setdefault(
                cat.id,
                {
                    "id": cat.id,
                    "label": cat.label,
                    "color": cat.color,
                    "orden": cat.orden,
                    "ocultar_en_dashboard": cat.ocultar_en_dashboard,
                },
            )

    resultado = sorted(vistas.values(), key=lambda c: c["orden"])
    resultado.append(
        {"id": "SIN_ANALIZAR", "label": "Not analyzed", "color": "#eda100", "orden": 999, "ocultar_en_dashboard": False}
    )
    return resultado


def subcategorias_disponibles(session: Session) -> dict:
    """Catálogo de subcategorías (segundo nivel, ej. motivo del interés) de este
    cliente: unión de las de todas sus campañas con esquema propio. `items`
    vacío si ninguna define subcategorías."""
    from .analysis.repository import get_campana_esquema

    vistas: dict[str, dict] = {}
    etiqueta = "Subcategory"
    for campana in session.execute(select(Campana)).scalars().all():
        esquema = get_campana_esquema(session, campana.id_campana)
        if esquema is None or not esquema.subcategorias:
            continue
        etiqueta = esquema.subcategoria_etiqueta
        for sub in esquema.subcategorias:
            vistas.setdefault(sub.id, {"id": sub.id, "label": sub.label, "color": sub.color, "orden": sub.orden})
    return {"etiqueta": etiqueta, "items": sorted(vistas.values(), key=lambda c: c["orden"])}


def _started_at_from(date_from: dt.date):
    """Límite inferior sargable (usa el índice de `started_at`, a diferencia de
    envolver la columna en `func.date()`, que MySQL no puede indexar)."""
    return Conversation.started_at >= dt.datetime.combine(date_from, dt.time.min)


def _started_at_to(date_to: dt.date):
    """Límite superior sargable: `< día siguiente` en vez de `<= date_to` para
    incluir todo el día sin depender de la resolución de segundos/microsegundos."""
    return Conversation.started_at < dt.datetime.combine(date_to + dt.timedelta(days=1), dt.time.min)


@dataclasses.dataclass(frozen=True)
class ConversationSummary:
    session_id: str
    customer_phone: str | None
    customer_name: str | None
    started_at: dt.datetime
    ended_at: dt.datetime
    message_count: int
    session_pattern: str
    iniciada_por: str
    contiene_array: bool
    categoria: str | None = None
    categoria_label: str | None = None
    subcategoria: str | None = None
    subcategoria_label: str | None = None


@dataclasses.dataclass(frozen=True)
class TranscriptMessage:
    sequence_number: int
    timestamp: dt.datetime
    sender: str
    sender_label: str
    message_type: str
    message: str


@dataclasses.dataclass(frozen=True)
class ConversationTranscript:
    session_id: str
    customer_phone: str | None
    customer_name: str | None
    started_at: dt.datetime
    ended_at: dt.datetime
    conn_id_count: int
    messages: list[TranscriptMessage]
    iniciada_por: str | None = None
    contiene_array: bool | None = None
    campana_id: int | None = None
    categoria: str | None = None
    categoria_label: str | None = None
    subcategoria: str | None = None
    subcategoria_label: str | None = None
    metodo: str | None = None
    justificacion: str | None = None
    # Indicadores resueltos de la campaña de ESTA conversación (propios o los
    # 6 de Acme por defecto — ver `analysis/schema.py`), listos para mostrar:
    # [{"id": ..., "label": ..., "valor": bool}, ...]. Vacío si aún no se analizó.
    indicadores: tuple[dict, ...] = ()


FLAG_CONDITIONS = {
    "interesados_confirmados": lambda: ConversationAnalysis.interes_confirmado.is_(True),
    "declararon_sin_concretar": lambda: (
        ConversationAnalysis.interes_declarado.is_(True) & ConversationAnalysis.interes_confirmado.is_(False)
    ),
    "autorespondedores": lambda: ConversationAnalysis.es_autorespondedor.is_(True),
    "bot_no_resolvio": lambda: ConversationAnalysis.bot_no_resolvio.is_(True),
    "resolvio_dudas": lambda: ConversationAnalysis.categoria_final == "RESOLVIO_DUDAS",
}


def _conversation_filters(
    query: str | None,
    categorias: list[str] | None,
    date_from: dt.date | None,
    date_to: dt.date | None,
    flag: str | None = None,
    iniciada_por: str | None = None,
    contiene_array: bool | None = None,
) -> list:
    """Condiciones WHERE compartidas por el conteo total y la página de resultados."""
    conditions = []

    if flag is not None:
        condicion = FLAG_CONDITIONS.get(flag)
        if condicion is not None:
            conditions.append(condicion())

    if iniciada_por is not None:
        conditions.append(Conversation.iniciada_por == iniciada_por)

    if contiene_array is not None:
        conditions.append(Conversation.contiene_array.is_(contiene_array))

    if query:
        query = query.strip()
        if query.isdigit():
            conditions.append(Conversation.customer_phone.like(f"%{query}%"))
        else:
            conditions.append(Conversation.session_id.like(f"%{query}%"))

    if date_from is not None:
        conditions.append(_started_at_from(date_from))
    if date_to is not None:
        conditions.append(_started_at_to(date_to))

    if categorias:
        quiere_sin_analizar = "SIN_ANALIZAR" in categorias
        reales = [c for c in categorias if c != "SIN_ANALIZAR"]
        if quiere_sin_analizar and reales:
            conditions.append(
                ConversationAnalysis.categoria_final.in_(reales) | ConversationAnalysis.categoria_final.is_(None)
            )
        elif quiere_sin_analizar:
            conditions.append(ConversationAnalysis.categoria_final.is_(None))
        else:
            conditions.append(ConversationAnalysis.categoria_final.in_(reales))

    return conditions


def list_conversations(
    session: Session,
    query: str | None = None,
    categorias: list[str] | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    flag: str | None = None,
    iniciada_por: str | None = None,
    contiene_array: bool | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> tuple[list[ConversationSummary], int]:
    """Lista conversaciones filtradas y paginadas. Devuelve (items, total).

    - `query`: si son solo dígitos, filtra por teléfono (coincidencia parcial);
      si no, por SESSION_ID (coincidencia parcial).
    - `categorias`: filtra por `categoria_final` (incluye el valor especial
      `"SIN_ANALIZAR"` para las conversaciones que aún no tienen análisis).
    - `date_from`/`date_to`: filtra por `started_at` (inclusive).
    - `flag`: filtra por un indicador de negocio (ver `FLAG_CONDITIONS`; las
      mismas claves que devuelve `business_indicators`).
    - `iniciada_por`: "CUSTOMER" / "BOT" / "SYSTEM" — quién mandó el primer mensaje.
    - `contiene_array`: filtra conversaciones donde apareció el texto "Array".
    """
    conditions = _conversation_filters(query, categorias, date_from, date_to, flag, iniciada_por, contiene_array)

    def _joined(stmt):
        return stmt.outerjoin(ConversationAnalysis, ConversationAnalysis.conversation_id == Conversation.id).where(
            *conditions
        )

    total = session.execute(
        _joined(select(func.count(func.distinct(Conversation.id))).select_from(Conversation))
    ).scalar_one()

    stmt = (
        _joined(select(Conversation, ConversationAnalysis.categoria_final, ConversationAnalysis.subcategoria))
        .order_by(Conversation.started_at.desc())
        .offset(max(page - 1, 0) * page_size)
        .limit(page_size)
    )

    resolver_label = _resolver_categoria_label(session)
    resolver_sub = _resolver_subcategoria_label(session)
    items = [
        ConversationSummary(
            session_id=c.session_id,
            customer_phone=c.customer_phone,
            customer_name=c.customer_name,
            started_at=c.started_at,
            ended_at=c.ended_at,
            message_count=c.message_count,
            session_pattern=c.session_pattern,
            iniciada_por=c.iniciada_por,
            contiene_array=c.contiene_array,
            categoria=categoria,
            categoria_label=resolver_label(c.campana_id, categoria),
            subcategoria=subcategoria,
            subcategoria_label=resolver_sub(c.campana_id, subcategoria),
        )
        for c, categoria, subcategoria in session.execute(stmt).all()
    ]
    return items, total


def get_transcript(session: Session, session_id: str) -> ConversationTranscript | None:
    conv = session.execute(select(Conversation).where(Conversation.session_id == session_id)).scalar_one_or_none()
    if conv is None:
        return None

    rows = (
        session.execute(select(Message).where(Message.conversation_id == conv.id).order_by(Message.sequence_number))
        .scalars()
        .all()
    )
    messages = [
        TranscriptMessage(
            sequence_number=m.sequence_number,
            timestamp=m.message_timestamp,
            sender=m.sender,
            sender_label=SENDER_LABEL.get(m.sender, m.sender),
            message_type=m.message_type,
            message=m.message,
        )
        for m in rows
    ]

    analisis = session.execute(
        select(ConversationAnalysis).where(ConversationAnalysis.conversation_id == conv.id)
    ).scalar_one_or_none()

    indicadores: tuple[dict, ...] = ()
    if analisis is not None:
        from .analysis.repository import get_campana_esquema
        from .analysis.schema import DEFAULT_ESQUEMA

        esquema = get_campana_esquema(session, conv.campana_id) or DEFAULT_ESQUEMA
        # `senales` es NULL en análisis guardados antes de que esta columna
        # existiera — de ahí el respaldo en las 6 columnas booleanas legadas
        # (siguen poblándose, ver `analysis/repository.guardar_analisis`).
        senales = analisis.senales or {
            "interes_declarado": analisis.interes_declarado,
            "interes_confirmado": analisis.interes_confirmado,
            "busco_informacion": analisis.busco_informacion,
            "rechazo_explicito": analisis.rechazo_explicito,
            "bot_no_resolvio": analisis.bot_no_resolvio,
            "es_autorespondedor": analisis.es_autorespondedor,
        }
        indicadores = tuple(
            {"id": ind.id, "label": ind.label, "valor": bool(senales.get(ind.id, False))} for ind in esquema.indicadores
        )

    resolver_label = _resolver_categoria_label(session)
    resolver_sub = _resolver_subcategoria_label(session)
    return ConversationTranscript(
        session_id=conv.session_id,
        customer_phone=conv.customer_phone,
        customer_name=conv.customer_name,
        started_at=conv.started_at,
        ended_at=conv.ended_at,
        conn_id_count=conv.conn_id_count,
        messages=messages,
        iniciada_por=conv.iniciada_por,
        contiene_array=conv.contiene_array,
        campana_id=conv.campana_id,
        categoria=analisis.categoria_final if analisis else None,
        categoria_label=resolver_label(conv.campana_id, analisis.categoria_final) if analisis else None,
        subcategoria=analisis.subcategoria if analisis else None,
        subcategoria_label=resolver_sub(conv.campana_id, analisis.subcategoria) if analisis else None,
        metodo=analisis.metodo if analisis else None,
        justificacion=analisis.justificacion if analisis else None,
        indicadores=indicadores,
    )


def category_counts(
    session: Session, date_from: dt.date | None = None, date_to: dt.date | None = None
) -> dict[str, int]:
    """Cuenta conversaciones por categoría final (incluye 'SIN_ANALIZAR')."""
    stmt = select(ConversationAnalysis.categoria_final, func.count()).join(
        Conversation, Conversation.id == ConversationAnalysis.conversation_id
    )
    if date_from is not None:
        stmt = stmt.where(_started_at_from(date_from))
    if date_to is not None:
        stmt = stmt.where(_started_at_to(date_to))
    stmt = stmt.group_by(ConversationAnalysis.categoria_final)

    counts = {cat: n for cat, n in session.execute(stmt).all()}

    sin_analizar_stmt = (
        select(func.count())
        .select_from(Conversation)
        .outerjoin(ConversationAnalysis, ConversationAnalysis.conversation_id == Conversation.id)
        .where(ConversationAnalysis.id.is_(None))
    )
    if date_from is not None:
        sin_analizar_stmt = sin_analizar_stmt.where(_started_at_from(date_from))
    if date_to is not None:
        sin_analizar_stmt = sin_analizar_stmt.where(_started_at_to(date_to))
    sin_analizar = session.execute(sin_analizar_stmt).scalar_one()
    if sin_analizar:
        counts["SIN_ANALIZAR"] = sin_analizar

    return counts


def subcategory_counts(
    session: Session, date_from: dt.date | None = None, date_to: dt.date | None = None
) -> dict[str, int]:
    """Cuenta conversaciones por subcategoría (segundo nivel, ej. motivo del
    interés). Solo las que tienen una — las demás quedan fuera."""
    stmt = (
        select(ConversationAnalysis.subcategoria, func.count())
        .join(Conversation, Conversation.id == ConversationAnalysis.conversation_id)
        .where(ConversationAnalysis.subcategoria.is_not(None))
    )
    if date_from is not None:
        stmt = stmt.where(_started_at_from(date_from))
    if date_to is not None:
        stmt = stmt.where(_started_at_to(date_to))
    stmt = stmt.group_by(ConversationAnalysis.subcategoria)
    return {sub: n for sub, n in session.execute(stmt).all()}


def method_counts(session: Session) -> dict[str, int]:
    """Cuántas conversaciones se clasificaron por regla (RULE) vs por IA (AI)."""
    stmt = select(ConversationAnalysis.metodo, func.count()).group_by(ConversationAnalysis.metodo)
    return {metodo: n for metodo, n in session.execute(stmt).all()}


def business_indicators(
    session: Session, date_from: dt.date | None = None, date_to: dt.date | None = None
) -> dict[str, int]:
    """Indicadores de negocio, ver docs/classification-criteria.md.

    `date_from`/`date_to` filtran por `Conversation.started_at` (inclusive).
    """

    def _count(*where) -> int:
        stmt = select(func.count()).select_from(ConversationAnalysis).where(*where)
        if date_from is not None or date_to is not None:
            stmt = stmt.join(Conversation, Conversation.id == ConversationAnalysis.conversation_id)
            if date_from is not None:
                stmt = stmt.where(_started_at_from(date_from))
            if date_to is not None:
                stmt = stmt.where(_started_at_to(date_to))
        return session.execute(stmt).scalar_one()

    return {
        "interesados_confirmados": _count(ConversationAnalysis.interes_confirmado.is_(True)),
        "declararon_sin_concretar": _count(
            ConversationAnalysis.interes_declarado.is_(True),
            ConversationAnalysis.interes_confirmado.is_(False),
        ),
        "autorespondedores": _count(ConversationAnalysis.es_autorespondedor.is_(True)),
        "bot_no_resolvio": _count(ConversationAnalysis.bot_no_resolvio.is_(True)),
        "rechazos_explicitos": _count(ConversationAnalysis.rechazo_explicito.is_(True)),
        "resolvio_dudas": _count(ConversationAnalysis.categoria_final == "RESOLVIO_DUDAS"),
    }


def _ventana_actual_y_anterior(
    date_from: dt.date | None, date_to: dt.date | None
) -> tuple[dt.date, dt.date, dt.date, dt.date]:
    """(actual_desde, actual_hasta, anterior_desde, anterior_hasta).

    Si no se pasa `date_from`, el período actual por defecto son los últimos 30
    días (hasta `date_to` o hoy). El período anterior es la ventana inmediatamente
    anterior, de la misma duración en días."""
    current_to = date_to or dt.date.today()
    current_from = date_from or (current_to - dt.timedelta(days=29))
    length = (current_to - current_from).days + 1
    previous_to = current_from - dt.timedelta(days=1)
    previous_from = previous_to - dt.timedelta(days=length - 1)
    return current_from, current_to, previous_from, previous_to


def business_indicators_trend(
    session: Session, date_from: dt.date | None = None, date_to: dt.date | None = None
) -> dict[str, dict[str, int]]:
    """Indicadores del período actual vs. el período anterior de igual duración."""
    current_from, current_to, previous_from, previous_to = _ventana_actual_y_anterior(date_from, date_to)
    return {
        "current": business_indicators(session, current_from, current_to),
        "previous": business_indicators(session, previous_from, previous_to),
    }


def category_counts_trend(
    session: Session, date_from: dt.date | None = None, date_to: dt.date | None = None
) -> dict[str, dict[str, int]]:
    """Igual que `business_indicators_trend`, pero por categoría en vez de por
    indicador de negocio — lo que alimenta las StatCards del dashboard, ahora
    dinámicas según las categorías de cada campaña."""
    current_from, current_to, previous_from, previous_to = _ventana_actual_y_anterior(date_from, date_to)
    return {
        "current": category_counts(session, current_from, current_to),
        "previous": category_counts(session, previous_from, previous_to),
    }


def daily_category_trend(
    session: Session, date_from: dt.date | None = None, date_to: dt.date | None = None
) -> list[dict]:
    """Serie diaria de conteos por categoría, agrupada por date(started_at)."""
    fecha_col = func.date(Conversation.started_at).label("fecha")
    stmt = (
        select(fecha_col, ConversationAnalysis.categoria_final, func.count())
        .select_from(Conversation)
        .join(ConversationAnalysis, ConversationAnalysis.conversation_id == Conversation.id)
    )
    if date_from is not None:
        stmt = stmt.where(_started_at_from(date_from))
    if date_to is not None:
        stmt = stmt.where(_started_at_to(date_to))
    stmt = stmt.group_by(fecha_col, ConversationAnalysis.categoria_final).order_by(fecha_col)
    return [
        {"fecha": str(fecha), "categoria": categoria, "cantidad": cantidad}
        for fecha, categoria, cantidad in session.execute(stmt).all()
    ]


@dataclasses.dataclass(frozen=True)
class ConversationExportRow:
    session_id: str
    customer_phone: str | None
    customer_name: str | None
    campana_nombre: str | None
    started_at: dt.datetime
    ended_at: dt.datetime
    message_count: int
    iniciada_por: str
    categoria: str | None
    categoria_label: str
    metodo: str | None
    subcategoria_label: str | None
    # Señales genéricas de esta conversación (ver `ConversationAnalysis.senales`)
    # — reemplaza a las 6 columnas booleanas fijas que había antes: cada
    # campaña puede tener sus propios indicadores (ver `analysis/schema.py`).
    # `reports.build_conversations_xlsx` arma una columna por cada id presente
    # en la unión de todas las filas exportadas, con la etiqueta que resuelve
    # `indicador_labels`.
    senales: dict | None
    contiene_array: bool
    justificacion: str | None


@dataclasses.dataclass(frozen=True)
class ExportResult:
    rows: list[ConversationExportRow]
    # id de indicador -> etiqueta legible, resuelta por campaña (ver
    # `_resolver_indicador_label`) — para las columnas dinámicas del Excel.
    indicador_labels: dict[str, str]
    # Encabezado de la columna de subcategoría (ej. "Motivo del interés"), o
    # None si ninguna fila exportada tiene subcategoría (no se agrega columna).
    subcategoria_etiqueta: str | None = None


def export_conversations(
    session: Session,
    query: str | None = None,
    categorias: list[str] | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    flag: str | None = None,
    iniciada_por: str | None = None,
    contiene_array: bool | None = None,
) -> ExportResult:
    """Todas las conversaciones que cumplen los filtros (sin paginar), con su
    clasificación completa — para el reporte descargable en Excel. Mismos
    filtros que `list_conversations`."""
    conditions = _conversation_filters(query, categorias, date_from, date_to, flag, iniciada_por, contiene_array)
    stmt = (
        select(Conversation, ConversationAnalysis, Campana.nombre_campana)
        .outerjoin(ConversationAnalysis, ConversationAnalysis.conversation_id == Conversation.id)
        .outerjoin(Campana, Campana.id_campana == Conversation.campana_id)
        .where(*conditions)
        .order_by(Conversation.started_at.desc())
    )

    resolver_label = _resolver_categoria_label(session)
    resolver_indicador = _resolver_indicador_label(session)
    resolver_sub = _resolver_subcategoria_label(session)
    rows = []
    indicador_labels: dict[str, str] = {}
    for c, a, campana_nombre in session.execute(stmt).all():
        senales = a.senales if a else None
        if senales:
            for indicador_id in senales:
                if indicador_id not in indicador_labels:
                    indicador_labels[indicador_id] = resolver_indicador(c.campana_id, indicador_id)
        rows.append(
            ConversationExportRow(
                session_id=c.session_id,
                customer_phone=c.customer_phone,
                customer_name=c.customer_name,
                campana_nombre=campana_nombre,
                started_at=c.started_at,
                ended_at=c.ended_at,
                message_count=c.message_count,
                iniciada_por=c.iniciada_por,
                categoria=a.categoria_final if a else None,
                categoria_label=(resolver_label(c.campana_id, a.categoria_final) or "") if a else "Not analyzed",
                metodo=a.metodo if a else None,
                subcategoria_label=resolver_sub(c.campana_id, a.subcategoria) if a else None,
                senales=senales,
                contiene_array=c.contiene_array,
                justificacion=a.justificacion if a else None,
            )
        )
    hay_subcategoria = any(r.subcategoria_label for r in rows)
    return ExportResult(
        rows=rows,
        indicador_labels=indicador_labels,
        subcategoria_etiqueta=subcategorias_disponibles(session)["etiqueta"] if hay_subcategoria else None,
    )
