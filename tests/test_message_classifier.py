from __future__ import annotations

import datetime as dt

from clasificador.message_classifier import classify_session_rows
from clasificador.pipeline_types import PreparedRow

SID = "573001000002.botco-4402-acme_venta.1001"


def _row(
    source_row,
    date,
    conn_id,
    customer_query=None,
    routing_answer=None,
    session_pattern="REAL",
):
    return PreparedRow(
        source_row=source_row,
        session_id=SID,
        session_pattern=session_pattern,
        channel="whatsapp",
        rp_id="61095",
        date=date,
        customer_name="Cliente",
        customer_email=None,
        customer_phone="573001000002",
        customer_query=customer_query,
        routing_answer=routing_answer,
        conn_id=conn_id,
        classification_warning=None,
    )


def test_normal_interaction_emits_customer_then_bot():
    rows = [
        _row(1, dt.datetime(2026, 8, 1, 9, 15, 52), "186111799", "Quiero usar mi cupo", "Claro, puedes utilizarlo..."),
    ]
    drafts = classify_session_rows(rows)
    assert [d.sender for d in drafts] == ["CUSTOMER", "BOT"]
    assert drafts[0].message == "Quiero usar mi cupo"
    assert drafts[1].message == "Claro, puedes utilizarlo..."


def test_bot_only_response_no_artificial_customer_message():
    rows = [
        _row(1, dt.datetime(2026, 8, 1, 9, 0, 0), "186111845", None, "¡Hola! Espero que estés teniendo un buen día...")
    ]
    drafts = classify_session_rows(rows)
    assert len(drafts) == 1
    assert drafts[0].sender == "BOT"


def test_proactive_broadcast_row_emits_bot_proactive_not_customer():
    rows = [
        _row(
            1,
            dt.datetime(2026, 8, 1, 12, 51, 9),
            None,
            "👋 Hola, *Aicardo*...",
            None,
            session_pattern="BROADCAST_LONG_NUMERIC",
        )
    ]
    drafts = classify_session_rows(rows)
    assert len(drafts) == 1
    assert drafts[0].sender == "BOT"
    assert drafts[0].message_type == "PROACTIVE"


def test_end_exit_chat_becomes_system_event_not_bot_text():
    rows = [_row(1, dt.datetime(2026, 8, 1, 9, 18, 0), "186111799", None, "end_exit_chat")]
    drafts = classify_session_rows(rows)
    assert len(drafts) == 1
    assert drafts[0].sender == "SYSTEM"
    assert drafts[0].message_type == "SYSTEM_EVENT"
    assert drafts[0].message == "end_exit_chat"


def test_adjacent_duplicate_customer_query_before_end_exit_chat_is_deduped():
    # Caso real observado (hallazgo 3): misma fecha/conn_id/query en dos filas
    # consecutivas, una con la respuesta real del bot y otra con end_exit_chat.
    ts = dt.datetime(2026, 8, 1, 13, 49, 43)
    rows = [
        _row(1, ts, "186111799", "Sí", "✅ Hemos registrado tu interés..."),
        _row(2, ts, "186111799", "Sí", "end_exit_chat"),
    ]
    drafts = classify_session_rows(rows)
    senders_and_types = [(d.sender, d.message_type, d.message) for d in drafts]
    assert senders_and_types == [
        ("CUSTOMER", "TEXT", "Sí"),
        ("BOT", "TEXT", "✅ Hemos registrado tu interés..."),
        ("SYSTEM", "SYSTEM_EVENT", "end_exit_chat"),
    ]
    # Solo un mensaje CUSTOMER, no dos.
    assert sum(1 for d in drafts if d.sender == "CUSTOMER") == 1


def test_non_adjacent_repeated_customer_reply_is_not_deduped():
    # "Sí" puede repetirse legítimamente más adelante en una conversación larga;
    # el dedup solo debe aplicar a filas realmente adyacentes.
    rows = [
        _row(1, dt.datetime(2026, 8, 1, 9, 0, 0), "186111799", "Sí", "Primera respuesta del bot"),
        _row(2, dt.datetime(2026, 8, 1, 9, 5, 0), "186111799", "Otra pregunta", "Otra respuesta"),
        _row(3, dt.datetime(2026, 8, 1, 9, 10, 0), "186111799", "Sí", "Segunda respuesta del bot"),
    ]
    drafts = classify_session_rows(rows)
    customer_messages = [d.message for d in drafts if d.sender == "CUSTOMER"]
    assert customer_messages == ["Sí", "Otra pregunta", "Sí"]


def test_multiple_conn_id_segments_within_same_session_all_processed():
    rows = [
        _row(1, dt.datetime(2026, 8, 1, 13, 47, 2), "186111799", "Quiero usar mi cupo", "respuesta 1"),
        _row(2, dt.datetime(2026, 8, 1, 13, 49, 43), "186111799", "Sí", "end_exit_chat"),
        _row(3, dt.datetime(2026, 8, 1, 13, 52, 53), "186111818", "Mi correo es x@y.com", "respuesta 2"),
        _row(4, dt.datetime(2026, 8, 1, 13, 56, 58), "186111818", "Sí", "end_exit_chat"),
    ]
    drafts = classify_session_rows(rows)
    system_events = [d for d in drafts if d.sender == "SYSTEM"]
    assert len(system_events) == 2
    assert {d.conn_id for d in system_events} == {"186111799", "186111818"}
