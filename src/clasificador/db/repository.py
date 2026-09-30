from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from ..conversation_builder import PHONE_COLLISION_MARKER, ConversationDraft
from ..excel_reader import RawRow
from ..pipeline_types import MessageDraft
from .models import AIUsage, Campana, Conversation, ConversationAnalysis, Import, Message, StagingMessage


def compute_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def _compute_dedup_hash(conversation_id: int, draft: MessageDraft) -> str:
    raw = f"{conversation_id}|{draft.conn_id}|{draft.timestamp.isoformat()}|{draft.sender}|{draft.message}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def start_import(
    session: Session, file_name: str, file_hash: str, rows_received: int, campana_id: int | None = None
) -> Import:
    imp = Import(
        campana_id=campana_id,
        file_name=file_name,
        file_hash=file_hash,
        status="PROCESSING",
        rows_received=rows_received,
        started_at=dt.datetime.now(),
    )
    session.add(imp)
    session.flush()
    return imp


def list_campanas(session: Session) -> list[Campana]:
    return list(session.execute(select(Campana).order_by(Campana.nombre_campana)).scalars().all())


def get_campana(session: Session, id_campana: int) -> Campana | None:
    return session.get(Campana, id_campana)


def create_campana(
    session: Session,
    *,
    nombre_campana: str,
    fecha_inicio: dt.date | None = None,
    estado: str = "ACTIVA",
    configuracion: dict | None = None,
) -> Campana:
    campana = Campana(
        nombre_campana=nombre_campana, fecha_inicio=fecha_inicio, estado=estado, configuracion=configuracion
    )
    session.add(campana)
    session.flush()
    return campana


_CAMPANA_CONFIG_UNSET = object()


def update_campana(
    session: Session,
    campana: Campana,
    *,
    nombre_campana: str | None = None,
    estado: str | None = None,
    configuracion: dict | None = _CAMPANA_CONFIG_UNSET,  # type: ignore[assignment]
) -> Campana:
    """`configuracion` usa un sentinel: pasar `None` explícito la resetea a los
    defaults (ver `CampanaRulesConfig`), no pasar el argumento la deja igual."""
    if nombre_campana is not None:
        campana.nombre_campana = nombre_campana
    if estado is not None:
        campana.estado = estado
    if configuracion is not _CAMPANA_CONFIG_UNSET:
        campana.configuracion = configuracion
    session.flush()
    return campana


def insert_staging_messages(session: Session, import_id: int, raw_rows: list[RawRow]) -> None:
    for raw in raw_rows:
        session.add(
            StagingMessage(
                import_id=import_id,
                source_row=raw.source_row,
                session_id=str(raw.session_id),
                channel=None if raw.channel is None else str(raw.channel),
                rp_id=None if raw.rp_id is None else str(raw.rp_id),
                row_date=raw.date if isinstance(raw.date, dt.datetime) else None,
                customer_name=None if raw.customer_name is None else str(raw.customer_name),
                customer_email=None if raw.customer_email is None else str(raw.customer_email),
                customer_phone_raw=None if raw.customer_phone is None else str(raw.customer_phone),
                customer_query=None if raw.customer_query is None else str(raw.customer_query),
                routing_answer=None if raw.routing_answer is None else str(raw.routing_answer),
                customer_id=None if raw.customer_id is None else str(raw.customer_id),
                conn_id=None if raw.conn_id is None else str(raw.conn_id),
                bsuid=None if raw.bsuid is None else str(raw.bsuid),
            )
        )


@dataclasses.dataclass
class ConversationSaveResult:
    conversation_id: int
    conversation_created: bool
    messages_created: int
    messages_skipped_duplicate: int
    phone_collision: bool


def _get_or_create_conversation(
    session: Session, draft: ConversationDraft, import_id: int
) -> tuple[Conversation, bool]:
    existing = session.execute(
        select(Conversation).where(Conversation.session_id == draft.session_id)
    ).scalar_one_or_none()

    if existing is None:
        # Se fija una sola vez, a partir de la campaña del import que la crea —
        # igual que first_import_id, nunca se reescribe en la rama de abajo.
        campana_id = session.get(Import, import_id).campana_id
        conv = Conversation(
            session_id=draft.session_id,
            session_pattern=draft.session_pattern,
            campana_id=campana_id,
            customer_phone=draft.customer_phone,
            customer_name=draft.customer_name,
            customer_email=draft.customer_email,
            channel=draft.channel,
            rp_id=draft.rp_id,
            started_at=draft.started_at,
            ended_at=draft.ended_at,
            message_count=0,
            conn_id_count=draft.conn_id_count,
            iniciada_por=draft.iniciada_por,
            contiene_array=draft.contiene_array,
            first_import_id=import_id,
            last_import_id=import_id,
        )
        session.add(conv)
        session.flush()
        return conv, True

    existing.started_at = min(existing.started_at, draft.started_at)
    existing.ended_at = max(existing.ended_at, draft.ended_at)
    existing.conn_id_count = max(existing.conn_id_count, draft.conn_id_count)
    existing.last_import_id = import_id
    if existing.customer_phone is None and draft.customer_phone is not None:
        existing.customer_phone = draft.customer_phone
    # No se reescribe a False: una carga posterior puede agregar mensajes con
    # "Array" que la anterior no tenía, pero nunca "limpia" un True previo.
    if draft.contiene_array and not existing.contiene_array:
        existing.contiene_array = True
    return existing, False


def save_conversation_with_messages(
    session: Session, draft: ConversationDraft, import_id: int
) -> ConversationSaveResult:
    """Guarda (o actualiza) una conversación y sus mensajes de forma idempotente.

    - `conversations.session_id` es único: reprocesar el mismo archivo actualiza
      la fila existente en lugar de duplicarla.
    - Los mensajes se deduplican por `dedup_hash` (hash de conversation_id+conn_id+
      timestamp+sender+message), así que volver a correr el mismo archivo no inserta
      mensajes nuevos.
    - `sequence_number` se asigna al momento de guardar, continuando desde el máximo
      ya almacenado para esa conversación (soporta que una misma SESSION_ID reciba
      mensajes nuevos en un archivo posterior sin chocar con los ya guardados).
    """
    conversation, created = _get_or_create_conversation(session, draft, import_id)

    phone_collision = any(PHONE_COLLISION_MARKER in w for w in draft.warnings)

    existing_hashes_query = select(Message.dedup_hash).where(Message.conversation_id == conversation.id)
    candidate_hashes = [_compute_dedup_hash(conversation.id, d) for d in draft.messages]
    existing_hashes = set()
    if candidate_hashes:
        existing_hashes = set(
            session.execute(existing_hashes_query.where(Message.dedup_hash.in_(candidate_hashes))).scalars().all()
        )

    current_max_seq = (
        session.execute(
            select(func.max(Message.sequence_number)).where(Message.conversation_id == conversation.id)
        ).scalar()
        or 0
    )

    messages_created = 0
    messages_skipped = 0
    next_seq = current_max_seq
    for msg_draft, dedup_hash in zip(draft.messages, candidate_hashes):
        if dedup_hash in existing_hashes:
            messages_skipped += 1
            continue
        next_seq += 1
        session.add(
            Message(
                conversation_id=conversation.id,
                conn_id=msg_draft.conn_id,
                message_timestamp=msg_draft.timestamp,
                sequence_number=next_seq,
                sender=msg_draft.sender,
                message_type=msg_draft.message_type,
                message=msg_draft.message,
                source_row=msg_draft.source_row,
                source_import_id=import_id,
                dedup_hash=dedup_hash,
            )
        )
        existing_hashes.add(dedup_hash)
        messages_created += 1

    conversation.message_count = (conversation.message_count or 0) + messages_created

    # Una conversación ya clasificada que recibe mensajes nuevos queda con una
    # categoría/flags calculados sobre un historial incompleto (ej. el cliente
    # mostró interés en un mensaje posterior al análisis). Se invalida el
    # análisis para que quede pendiente de nuevo y el auto-análisis post-carga
    # la reprocese con el historial completo — ver session_ids_pendientes().
    if not created and messages_created > 0:
        session.execute(delete(ConversationAnalysis).where(ConversationAnalysis.conversation_id == conversation.id))

    return ConversationSaveResult(
        conversation_id=conversation.id,
        conversation_created=created,
        messages_created=messages_created,
        messages_skipped_duplicate=messages_skipped,
        phone_collision=phone_collision,
    )


@dataclasses.dataclass
class EliminarConversacionesResult:
    conversaciones_eliminadas: int
    mensajes_eliminados: int


def eliminar_conversaciones_por_fecha(session: Session, fecha: dt.date) -> EliminarConversacionesResult:
    """Borra conversaciones (y lo que cuelga de ellas: mensajes y análisis)
    cuyo `started_at` cae en `fecha` — mismo criterio de "fecha de conversación"
    que usa el resto de la app (dashboard/filtros, ver
    `conversation_view._started_at_from`/`_started_at_to`).

    Pensado para que un super admin pueda deshacer una carga con datos malos y
    reprocesarla: como `conversations.session_id` y `messages.dedup_hash` son
    únicos, volver a subir el mismo archivo después de este borrado recrea todo
    sin chocar con nada residual.

    El uso de IA (`ai_usage`) NO se borra — es el registro histórico de gasto
    (ver `analysis/pricing.py`) y ya se cobró independientemente de que la
    conversación se reprocese; solo se desvincula (`conversation_id = NULL`)
    para poder borrar la conversación sin violar la foreign key.

    Tampoco borra `imports`/`staging_messages`: son el historial de la carga
    (no datos de negocio) y una sola carga puede abarcar varias fechas.
    """
    desde = dt.datetime.combine(fecha, dt.time.min)
    hasta = dt.datetime.combine(fecha + dt.timedelta(days=1), dt.time.min)

    conversation_ids = list(
        session.execute(
            select(Conversation.id).where(Conversation.started_at >= desde, Conversation.started_at < hasta)
        )
        .scalars()
        .all()
    )
    if not conversation_ids:
        return EliminarConversacionesResult(conversaciones_eliminadas=0, mensajes_eliminados=0)

    # Orden por las foreign keys: lo que referencia a conversations primero.
    session.execute(update(AIUsage).where(AIUsage.conversation_id.in_(conversation_ids)).values(conversation_id=None))
    session.execute(delete(ConversationAnalysis).where(ConversationAnalysis.conversation_id.in_(conversation_ids)))
    mensajes_eliminados = session.execute(delete(Message).where(Message.conversation_id.in_(conversation_ids))).rowcount
    session.execute(delete(Conversation).where(Conversation.id.in_(conversation_ids)))

    return EliminarConversacionesResult(
        conversaciones_eliminadas=len(conversation_ids), mensajes_eliminados=mensajes_eliminados
    )


def contar_staging_antiguo(session: Session, mas_viejo_que: dt.datetime) -> int:
    """Cuenta filas de staging_messages con created_at anterior al límite dado."""
    stmt = select(func.count()).select_from(StagingMessage).where(StagingMessage.created_at < mas_viejo_que)
    return session.execute(stmt).scalar_one()


def purgar_staging_antiguo(session: Session, mas_viejo_que: dt.datetime) -> int:
    """Borra filas de staging_messages con created_at anterior al límite dado.

    `staging_messages` es solo una copia cruda de auditoría de cada carga; los
    datos de negocio ya viven, estructurados, en `conversations`/`messages` y
    no se ven afectados. Devuelve cuántas filas se borraron.
    """
    result = session.execute(delete(StagingMessage).where(StagingMessage.created_at < mas_viejo_que))
    return result.rowcount


def finish_import(
    session: Session,
    imp: Import,
    *,
    status: str,
    rows_processed: int,
    rows_error: int,
    conversations_created: int,
    conversations_updated: int,
    messages_created: int,
    messages_skipped_duplicate: int,
    error_summary: list[dict] | None,
    warning_summary: list[dict] | None,
) -> None:
    imp.status = status
    imp.rows_processed = rows_processed
    imp.rows_error = rows_error
    imp.conversations_created = conversations_created
    imp.conversations_updated = conversations_updated
    imp.messages_created = messages_created
    imp.messages_skipped_duplicate = messages_skipped_duplicate
    imp.error_summary = error_summary
    imp.warning_summary = warning_summary
    imp.finished_at = dt.datetime.now()
