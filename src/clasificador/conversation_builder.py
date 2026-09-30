from __future__ import annotations

import dataclasses
import datetime as dt
from collections import defaultdict

from .excel_reader import RawRow
from .message_classifier import classify_session_rows
from .normalizer import normalize_date, normalize_phone, normalize_text
from .pipeline_types import MessageDraft, PreparedRow
from .row_classifier import classify_row

# Shared by the warning text below and by `db.repository`, which flags the
# conversation as a phone collision when a warning contains it.
PHONE_COLLISION_MARKER = "distinct CUSTOMER_PHONE"


@dataclasses.dataclass(frozen=True)
class RowProcessingError:
    source_row: int
    error_type: str
    error_message: str
    raw_value: str


@dataclasses.dataclass(frozen=True)
class ConversationDraft:
    session_id: str
    session_pattern: str
    customer_phone: str | None
    customer_name: str | None
    customer_email: str | None
    channel: str | None
    rp_id: str | None
    started_at: dt.datetime
    ended_at: dt.datetime
    conn_id_count: int
    messages: list[MessageDraft]
    iniciada_por: str
    contiene_array: bool
    warnings: list[str]


def prepare_row(raw: RawRow) -> tuple[PreparedRow | None, RowProcessingError | None]:
    try:
        date = normalize_date(raw.date)
        if date is None:
            return None, RowProcessingError(raw.source_row, "MISSING_DATE", "DATE is empty or invalid", str(raw.date))

        session_id = normalize_text(raw.session_id)
        if session_id is None:
            return None, RowProcessingError(
                raw.source_row, "MISSING_SESSION_ID", "SESSION_ID is empty", str(raw.session_id)
            )

        classification = classify_row(session_id, raw.conn_id)

        prepared = PreparedRow(
            source_row=raw.source_row,
            session_id=session_id,
            session_pattern=classification.session_pattern,
            channel=normalize_text(raw.channel),
            rp_id=normalize_text(raw.rp_id),
            date=date,
            customer_name=normalize_text(raw.customer_name),
            customer_email=normalize_text(raw.customer_email),
            customer_phone=normalize_phone(raw.customer_phone),
            customer_query=normalize_text(raw.customer_query),
            routing_answer=normalize_text(raw.routing_answer),
            conn_id=normalize_text(raw.conn_id),
            classification_warning=classification.warning,
        )
        return prepared, None
    except Exception as exc:  # defensa: un error inesperado en una fila no debe abortar el import
        return None, RowProcessingError(raw.source_row, "UNEXPECTED_ERROR", str(exc), repr(raw))


def build_conversations(rows: list[RawRow]) -> tuple[list[ConversationDraft], list[RowProcessingError]]:
    """Agrupa las filas ya normalizadas por SESSION_ID y arma cada conversación.

    Orden dentro de cada sesión: (DATE, source_row) — sección 15 del documento.
    started_at/ended_at se calculan sobre TODAS las filas de la sesión, no solo
    hasta el primer end_exit_chat (hallazgo 2: una sesión puede tener varios
    segmentos/CONN_ID y varios cierres).
    """
    errors: list[RowProcessingError] = []
    grouped: dict[str, list[PreparedRow]] = defaultdict(list)

    for raw in rows:
        prepared, error = prepare_row(raw)
        if error is not None:
            errors.append(error)
            continue
        grouped[prepared.session_id].append(prepared)

    conversations: list[ConversationDraft] = []
    for session_id, session_rows in grouped.items():
        session_rows.sort(key=lambda r: (r.date, r.source_row))

        drafts = classify_session_rows(session_rows)
        sequenced = [dataclasses.replace(d, sequence_number=i) for i, d in enumerate(drafts, start=1)]

        warnings = [r.classification_warning for r in session_rows if r.classification_warning]

        distinct_phones = {r.customer_phone for r in session_rows if r.customer_phone}
        first_with_phone = next((r for r in session_rows if r.customer_phone), session_rows[0])
        if len(distinct_phones) > 1:
            # Hallazgo 4: colisión rara de SESSION_ID entre teléfonos distintos.
            warnings.append(
                f"SESSION_ID '{session_id}' appears with more than one {PHONE_COLLISION_MARKER}: "
                f"{sorted(distinct_phones)}. Keeping '{first_with_phone.customer_phone}'."
            )

        distinct_conn_ids = {r.conn_id for r in session_rows if r.conn_id is not None}

        conversations.append(
            ConversationDraft(
                session_id=session_id,
                session_pattern=session_rows[0].session_pattern,
                customer_phone=first_with_phone.customer_phone,
                customer_name=first_with_phone.customer_name,
                customer_email=first_with_phone.customer_email,
                channel=session_rows[0].channel,
                rp_id=session_rows[0].rp_id,
                started_at=min(r.date for r in session_rows),
                ended_at=max(r.date for r in session_rows),
                conn_id_count=max(len(distinct_conn_ids), 1),
                messages=sequenced,
                iniciada_por=sequenced[0].sender if sequenced else "SYSTEM",
                contiene_array=any("Array" in d.message for d in sequenced if d.message),
                warnings=warnings,
            )
        )

    return conversations, errors
