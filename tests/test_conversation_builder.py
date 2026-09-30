from __future__ import annotations

import datetime as dt

from clasificador.conversation_builder import build_conversations
from clasificador.excel_reader import RawRow

SID = "573001000002.botco-4402-acme_venta.1001"


def _raw(source_row, date, conn_id, customer_query="-", routing_answer="-", session_id=SID, phone=573001000002):
    return RawRow(
        source_row=source_row,
        session_id=session_id,
        channel="whatsapp",
        rp_id=61095,
        date=date,
        customer_name="Cliente Prueba",
        customer_email="-",
        customer_phone=phone,
        customer_query=customer_query,
        routing_answer=routing_answer,
        customer_id="-",
        conn_id=conn_id,
        bsuid="---",
    )


def test_single_conversation_sequence_numbers_and_counts():
    rows = [
        _raw(10, dt.datetime(2026, 8, 1, 9, 15, 52), 186111799, "Quiero usar mi cupo", "Claro..."),
        _raw(11, dt.datetime(2026, 8, 1, 9, 18, 0), 186111799, "-", "end_exit_chat"),
    ]
    conversations, errors = build_conversations(rows)
    assert errors == []
    assert len(conversations) == 1
    conv = conversations[0]
    assert conv.session_pattern == "REAL"
    assert conv.customer_phone == "573001000002"
    assert [m.sequence_number for m in conv.messages] == [1, 2, 3]
    assert conv.messages[-1].sender == "SYSTEM"


def test_ended_at_covers_multiple_conn_id_segments_finding_2():
    # Ejemplo real: 4 CONN_ID / 3 end_exit_chat dentro de la misma SESSION_ID,
    # a lo largo de varias horas. ended_at debe ser el máximo de TODAS las filas.
    rows = [
        _raw(1, dt.datetime(2026, 8, 1, 13, 47, 2), 186111799, "Quiero usar mi cupo", "respuesta 1"),
        _raw(2, dt.datetime(2026, 8, 1, 13, 49, 43), 186111799, "Sí", "end_exit_chat"),
        _raw(3, dt.datetime(2026, 8, 1, 13, 52, 53), 186111818, "correo@x.com", "respuesta 2"),
        _raw(4, dt.datetime(2026, 8, 1, 13, 56, 58), 186111818, "Sí", "end_exit_chat"),
        _raw(5, dt.datetime(2026, 8, 1, 13, 57, 37), 186111838, "Requiero un asesor", "respuesta 3"),
        _raw(6, dt.datetime(2026, 8, 1, 13, 59, 42), 186111838, "Sí", "end_exit_chat"),
        _raw(7, dt.datetime(2026, 8, 1, 15, 56, 2), 186111845, "-", "no olvides responder"),
    ]
    conversations, errors = build_conversations(rows)
    assert errors == []
    assert len(conversations) == 1
    conv = conversations[0]
    assert conv.started_at == dt.datetime(2026, 8, 1, 13, 47, 2)
    assert conv.ended_at == dt.datetime(2026, 8, 1, 15, 56, 2)
    assert conv.conn_id_count == 4
    system_events = [m for m in conv.messages if m.sender == "SYSTEM"]
    assert len(system_events) == 3


def test_phone_collision_within_same_session_id_generates_warning_finding_4():
    rows = [
        _raw(
            1,
            dt.datetime(2026, 8, 1, 13, 46, 14),
            None,
            "👋 Hola, *A*...",
            "-",
            session_id="100000000000000000000000000000001",
            phone=573009990001,
        ),
        _raw(
            2,
            dt.datetime(2026, 8, 1, 13, 51, 18),
            None,
            "👋 Hola, *B*...",
            "-",
            session_id="100000000000000000000000000000001",
            phone=573009990002,
        ),
    ]
    conversations, errors = build_conversations(rows)
    assert errors == []
    assert len(conversations) == 1
    conv = conversations[0]
    assert conv.session_pattern == "BROADCAST_LONG_NUMERIC"
    assert conv.customer_phone == "573009990001"  # se conserva el primero
    assert any("distinct CUSTOMER_PHONE" in w for w in conv.warnings)


def test_row_with_invalid_date_becomes_error_not_exception():
    rows = [_raw(1, None, 186111799, "hola", "respuesta")]
    conversations, errors = build_conversations(rows)
    assert conversations == []
    assert len(errors) == 1
    assert errors[0].error_type == "MISSING_DATE"


def test_broadcast_rows_each_form_their_own_single_message_conversation():
    rows = [
        _raw(
            1,
            dt.datetime(2026, 8, 1, 12, 51, 9),
            "-",
            "👋 Hola, *Aicardo*...",
            "-",
            session_id="100000000000000000000000000000002",
        ),
        _raw(
            2,
            dt.datetime(2026, 8, 1, 12, 51, 9),
            "-",
            "👋 Hola, *Marisol*...",
            "-",
            session_id="100000000000000000000000000000003",
        ),
    ]
    conversations, errors = build_conversations(rows)
    assert errors == []
    assert len(conversations) == 2
    for conv in conversations:
        assert conv.session_pattern == "BROADCAST_LONG_NUMERIC"
        assert len(conv.messages) == 1
        assert conv.messages[0].sender == "BOT"
        assert conv.messages[0].message_type == "PROACTIVE"
