from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# BIGINT en MySQL, pero INTEGER en SQLite: SQLite solo trata una PK autoincremental
# como alias de rowid (y por tanto la autogenera) si su tipo declarado es INTEGER puro.
PkBigInteger = BigInteger().with_variant(Integer(), "sqlite")


ImportStatus = Enum(
    "PROCESSING",
    "COMPLETED",
    "COMPLETED_WITH_WARNINGS",
    "ERROR",
    name="import_status",
)

SessionPattern = Enum(
    "REAL",
    "BROADCAST_LONG_NUMERIC",
    "BROADCAST_DOTTED",
    name="session_pattern",
)

MessageSender = Enum("CUSTOMER", "BOT", "SYSTEM", name="message_sender")

MessageType = Enum("TEXT", "PROACTIVE", "SYSTEM_EVENT", name="message_type")

MetodoAnalisis = Enum("RULE", "AI", name="metodo_analisis")


class Campana(Base):
    __tablename__ = "campanas"

    id_campana: Mapped[int] = mapped_column(PkBigInteger, primary_key=True, autoincrement=True)
    nombre_campana: Mapped[str] = mapped_column(String(150), nullable=False)
    fecha_inicio: Mapped[dt.date | None] = mapped_column(DateTime, nullable=True)
    estado: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVA")
    # Parámetros de detección de señales para esta campaña; NULL = defaults.
    # Ver analysis/rules_config.py.
    configuracion: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class AIUsage(Base):
    """Un renglón por cada llamada a la API de OpenAI — para poder sumar tokens
    y estimar costo (ver `analysis/pricing.py`). `conversation_id` va poblado
    para clasificaciones, NULL para llamadas que no son por conversación (ej.
    generar un esquema de campaña con IA)."""

    __tablename__ = "ai_usage"

    id: Mapped[int] = mapped_column(PkBigInteger, primary_key=True, autoincrement=True)
    ocurrido_en: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    modelo: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # "clasificacion" | "generar_esquema"
    tokens_prompt: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_completion: Mapped[int] = mapped_column(Integer, nullable=False)
    conversation_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("conversations.id"), nullable=True)
    campana_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("campanas.id_campana"), nullable=True)


class Import(Base):
    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(PkBigInteger, primary_key=True, autoincrement=True)
    campana_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("campanas.id_campana"), nullable=True, index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(ImportStatus, nullable=False, default="PROCESSING", index=True)

    rows_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_error: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conversations_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conversations_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    messages_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    messages_skipped_duplicate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    started_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    error_summary: Mapped[list | None] = mapped_column(JSON, nullable=True)
    warning_summary: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class StagingMessage(Base):
    __tablename__ = "staging_messages"

    id: Mapped[int] = mapped_column(PkBigInteger, primary_key=True, autoincrement=True)
    import_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("imports.id"), nullable=False, index=True)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)

    session_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    channel: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rp_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    row_date: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_phone_raw: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    customer_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    routing_answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    conn_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bsuid: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("session_id", name="uq_conversations_session_id"),)

    id: Mapped[int] = mapped_column(PkBigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    session_pattern: Mapped[str] = mapped_column(SessionPattern, nullable=False)
    # Se fija al crear la conversación (a partir del campana_id del import que
    # la originó) y nunca se reescribe, igual que first_import_id.
    campana_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("campanas.id_campana"), nullable=True, index=True
    )

    customer_phone: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rp_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    started_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, index=True)
    ended_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conn_id_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Quién mandó el primer mensaje de la sesión. Se fija una sola vez al crear
    # la conversación y nunca se reescribe (igual que session_pattern/campana_id).
    iniciada_por: Mapped[str] = mapped_column(MessageSender, nullable=False, index=True)
    # El texto literal "Array" apareció en algún mensaje (bug conocido de
    # renderizado del bot: un array sin serializar se muestra tal cual). A
    # diferencia de iniciada_por, si una carga posterior agrega mensajes que sí
    # lo contienen, se actualiza a True (nunca vuelve a False).
    contiene_array: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    first_import_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("imports.id"), nullable=False)
    last_import_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("imports.id"), nullable=False)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list[Message]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("dedup_hash", name="uq_messages_dedup_hash"),)

    id: Mapped[int] = mapped_column(PkBigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("conversations.id"), nullable=False, index=True)
    conn_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    message_timestamp: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)

    sender: Mapped[str] = mapped_column(MessageSender, nullable=False)
    message_type: Mapped[str] = mapped_column(MessageType, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    source_import_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("imports.id"), nullable=False)
    dedup_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class ConversationAnalysis(Base):
    """Clasificación de una conversación. Criterios en docs/classification-criteria.md"""

    __tablename__ = "conversation_analysis"
    __table_args__ = (UniqueConstraint("conversation_id", name="uq_analysis_conversation"),)

    id: Mapped[int] = mapped_column(PkBigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(PkBigInteger, ForeignKey("conversations.id"), nullable=False)

    # String, no Enum: cada campaña puede definir sus propias categorías (ver
    # `analysis/schema.py`) — antes de esto era un ENUM fijo de MySQL con las 5
    # categorías hardcodeadas de Acme (migración: scripts/migrate_categoria_final_varchar.py).
    categoria_final: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # Segundo nivel opcional (ej. el motivo del interés) — solo lo calculan las
    # campañas cuyo esquema declara `subcategorias` (ver `analysis/schema.py`);
    # NULL para el resto y para las categorías a las que no aplica.
    subcategoria: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    # Señales genéricas por indicador (ver `analysis/schema.py` / `schema_engine.py`),
    # siempre poblado. Las 6 columnas booleanas de abajo son la vista legada,
    # específica de Acme — se conservan por compatibilidad con SQL/reportes
    # existentes, pero una campaña con esquema propio las deja en False.
    senales: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    interes_declarado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    interes_confirmado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # El cliente obtuvo información del producto, la haya preguntado explícitamente
    # o la haya conseguido avanzando en el flujo guiado del bot.
    busco_informacion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rechazo_explicito: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    bot_no_resolvio: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # El número de la campaña pertenece a una empresa, no a una persona.
    es_autorespondedor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    metodo: Mapped[str] = mapped_column(MetodoAnalisis, nullable=False, index=True)
    regla_aplicada: Mapped[str | None] = mapped_column(String(100), nullable=True)
    modelo_ia: Mapped[str | None] = mapped_column(String(100), nullable=True)
    justificacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    analyzed_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
