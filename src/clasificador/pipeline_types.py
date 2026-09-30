from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True)
class PreparedRow:
    """Una fila del Excel ya normalizada (teléfono, fecha, "-" -> None) y clasificada."""

    source_row: int
    session_id: str
    session_pattern: str  # REAL / BROADCAST_LONG_NUMERIC / BROADCAST_DOTTED
    channel: str | None
    rp_id: str | None
    date: dt.datetime
    customer_name: str | None
    customer_email: str | None
    customer_phone: str | None
    customer_query: str | None
    routing_answer: str | None
    conn_id: str | None
    classification_warning: str | None


@dataclass(frozen=True)
class MessageDraft:
    source_row: int
    conn_id: str | None
    timestamp: dt.datetime
    sender: str  # CUSTOMER / BOT / SYSTEM
    message_type: str  # TEXT / PROACTIVE / SYSTEM_EVENT
    message: str
    sequence_number: int | None = None
