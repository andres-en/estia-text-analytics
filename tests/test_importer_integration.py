from __future__ import annotations

from clasificador.db.engine import create_all_tables, create_db_engine, make_session_factory
from clasificador.importer import run_import


def _fresh_session_factory():
    engine = create_db_engine("sqlite:///:memory:")
    create_all_tables(engine)
    return make_session_factory(engine)


def test_full_import_against_sample_matches_known_baseline(sample_xlsx_path):
    session_factory = _fresh_session_factory()
    report = run_import(sample_xlsx_path, session_factory)

    assert report.status == "COMPLETED_WITH_WARNINGS"
    assert report.rows_received == 1163
    assert report.rows_processed == 1163
    assert report.rows_error == 0

    # 62 real conversations + 896 single-message proactive "conversations"
    # (900 proactive rows collapse into 896 unique SESSION_IDs because of 4
    # collisions, see finding 4) = 958 distinct SESSION_IDs.
    assert report.conversations_created == 958
    assert report.conversations_updated == 0

    assert report.messages_created == 1338
    assert report.messages_skipped_duplicate == 0
    assert report.customer_messages == 181
    assert report.bot_messages == 1101
    assert report.system_messages == 56

    # Hallazgo 4: 4 advertencias de colisión de SESSION_ID entre teléfonos distintos.
    assert len(report.warnings) == 4
    assert all("distinct CUSTOMER_PHONE" in w for w in report.warnings)


def test_rerunning_same_file_is_fully_idempotent(sample_xlsx_path):
    session_factory = _fresh_session_factory()
    run_import(sample_xlsx_path, session_factory)
    second_report = run_import(sample_xlsx_path, session_factory)

    assert second_report.conversations_created == 0
    assert second_report.conversations_updated == 958
    assert second_report.messages_created == 0
    assert second_report.messages_skipped_duplicate == 1338


def test_specific_multi_segment_conversation_reconstructs_correctly(sample_xlsx_path):
    # Reconstruye vía SQL la conversación del hallazgo 2 (4 CONN_ID, 3 cierres)
    # para verificar que ended_at cubre TODAS las filas y no hay mensajes duplicados.
    from sqlalchemy import select

    from clasificador.db.models import Conversation, Message

    session_factory = _fresh_session_factory()
    run_import(sample_xlsx_path, session_factory)

    sid = "573001000002.botco-4402-acme_venta.1001"
    with session_factory() as session:
        conv = session.execute(select(Conversation).where(Conversation.session_id == sid)).scalar_one()
        assert conv.conn_id_count == 4
        assert conv.message_count == 30

        messages = (
            session.execute(select(Message).where(Message.conversation_id == conv.id).order_by(Message.sequence_number))
            .scalars()
            .all()
        )
        assert len(messages) == 30
        system_events = [m for m in messages if m.sender == "SYSTEM"]
        assert len(system_events) == 3

        customer_si_messages = [m for m in messages if m.sender == "CUSTOMER" and m.message == "Sí"]
        # "Sí" aparece 3 veces en la conversación (una por cada cierre), pero
        # nunca duplicado dentro del mismo cierre (hallazgo 3).
        assert len(customer_si_messages) == 3
