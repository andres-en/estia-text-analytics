from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select

from clasificador.conversation_builder import ConversationDraft
from clasificador.db.engine import create_all_tables, create_db_engine, make_session_factory
from clasificador.db.models import Conversation, ConversationAnalysis, Message, StagingMessage
from clasificador.db.repository import (
    finish_import,
    insert_staging_messages,
    save_conversation_with_messages,
    start_import,
)
from clasificador.excel_reader import RawRow
from clasificador.pipeline_types import MessageDraft

SID = "573001000002.botco-4402-acme_venta.1001"


@pytest.fixture
def session_factory():
    engine = create_db_engine("sqlite:///:memory:")
    create_all_tables(engine)
    return make_session_factory(engine)


def _draft(messages, phone="573001000002", warnings=None):
    return ConversationDraft(
        session_id=SID,
        session_pattern="REAL",
        customer_phone=phone,
        customer_name="Cliente",
        customer_email=None,
        channel="whatsapp",
        rp_id="61095",
        started_at=min(m.timestamp for m in messages),
        ended_at=max(m.timestamp for m in messages),
        conn_id_count=1,
        messages=messages,
        iniciada_por=messages[0].sender if messages else "SYSTEM",
        contiene_array=any("Array" in m.message for m in messages),
        warnings=warnings or [],
    )


def _msg(source_row, ts, sender, message, message_type="TEXT", conn_id="186111799"):
    return MessageDraft(source_row, conn_id, ts, sender, message_type, message)


def test_save_creates_conversation_and_messages(session_factory):
    with session_factory() as session:
        imp = start_import(session, "file.xlsx", "hash1", rows_received=2)
        draft = _draft(
            [
                _msg(1, dt.datetime(2026, 8, 1, 9, 0, 0), "CUSTOMER", "hola"),
                _msg(1, dt.datetime(2026, 8, 1, 9, 0, 0), "BOT", "respuesta"),
            ]
        )
        result = save_conversation_with_messages(session, draft, imp.id)
        session.commit()

        assert result.conversation_created is True
        assert result.messages_created == 2
        assert result.messages_skipped_duplicate == 0

        conv = session.execute(select(Conversation).where(Conversation.session_id == SID)).scalar_one()
        assert conv.message_count == 2
        messages = session.execute(select(Message).where(Message.conversation_id == conv.id)).scalars().all()
        assert {m.sequence_number for m in messages} == {1, 2}


def test_rerunning_same_file_is_idempotent(session_factory):
    with session_factory() as session:
        imp1 = start_import(session, "file.xlsx", "hash1", rows_received=2)
        draft = _draft(
            [
                _msg(1, dt.datetime(2026, 8, 1, 9, 0, 0), "CUSTOMER", "hola"),
                _msg(1, dt.datetime(2026, 8, 1, 9, 0, 0), "BOT", "respuesta"),
            ]
        )
        save_conversation_with_messages(session, draft, imp1.id)
        session.commit()

        # Reprocesar exactamente el mismo archivo (mismos mensajes)
        imp2 = start_import(session, "file.xlsx", "hash1", rows_received=2)
        result2 = save_conversation_with_messages(session, draft, imp2.id)
        session.commit()

        assert result2.conversation_created is False
        assert result2.messages_created == 0
        assert result2.messages_skipped_duplicate == 2

        conv = session.execute(select(Conversation).where(Conversation.session_id == SID)).scalar_one()
        assert conv.message_count == 2  # no se duplicó
        total_messages = session.execute(select(Message)).scalars().all()
        assert len(total_messages) == 2


def test_new_messages_in_later_file_continue_sequence_numbers(session_factory):
    with session_factory() as session:
        imp1 = start_import(session, "file1.xlsx", "hash1", rows_received=2)
        draft1 = _draft(
            [
                _msg(1, dt.datetime(2026, 8, 1, 9, 0, 0), "CUSTOMER", "hola"),
                _msg(1, dt.datetime(2026, 8, 1, 9, 0, 0), "BOT", "respuesta"),
            ]
        )
        save_conversation_with_messages(session, draft1, imp1.id)
        session.commit()

        # Un archivo posterior trae mensajes NUEVOS para la misma conversación.
        imp2 = start_import(session, "file2.xlsx", "hash2", rows_received=2)
        draft2 = _draft(
            [
                _msg(2, dt.datetime(2026, 8, 2, 9, 0, 0), "CUSTOMER", "otra pregunta"),
                _msg(2, dt.datetime(2026, 8, 2, 9, 0, 1), "BOT", "otra respuesta"),
            ]
        )
        result2 = save_conversation_with_messages(session, draft2, imp2.id)
        session.commit()

        assert result2.conversation_created is False
        assert result2.messages_created == 2

        conv = session.execute(select(Conversation).where(Conversation.session_id == SID)).scalar_one()
        assert conv.message_count == 4
        messages = (
            session.execute(select(Message).where(Message.conversation_id == conv.id).order_by(Message.sequence_number))
            .scalars()
            .all()
        )
        assert [m.sequence_number for m in messages] == [1, 2, 3, 4]


def test_new_messages_invalidate_existing_analysis(session_factory):
    with session_factory() as session:
        imp1 = start_import(session, "file1.xlsx", "hash1", rows_received=2)
        draft1 = _draft(
            [
                _msg(1, dt.datetime(2026, 8, 1, 9, 0, 0), "CUSTOMER", "hola"),
                _msg(1, dt.datetime(2026, 8, 1, 9, 0, 0), "BOT", "respuesta"),
            ]
        )
        save_conversation_with_messages(session, draft1, imp1.id)
        session.commit()

        conv = session.execute(select(Conversation).where(Conversation.session_id == SID)).scalar_one()
        session.add(
            ConversationAnalysis(
                conversation_id=conv.id,
                categoria_final="NO_INTERESADO",
                metodo="RULE",
                analyzed_at=dt.datetime(2026, 8, 1, 10, 0, 0),
            )
        )
        session.commit()

        # Un archivo posterior trae mensajes NUEVOS para una conversación ya
        # analizada: el análisis viejo (calculado sobre historial incompleto)
        # debe invalidarse para que vuelva a quedar pendiente.
        imp2 = start_import(session, "file2.xlsx", "hash2", rows_received=2)
        draft2 = _draft(
            [
                _msg(2, dt.datetime(2026, 8, 2, 9, 0, 0), "CUSTOMER", "sí me interesa"),
                _msg(2, dt.datetime(2026, 8, 2, 9, 0, 1), "BOT", "perfecto"),
            ]
        )
        save_conversation_with_messages(session, draft2, imp2.id)
        session.commit()

        analysis = session.execute(
            select(ConversationAnalysis).where(ConversationAnalysis.conversation_id == conv.id)
        ).scalar_one_or_none()
        assert analysis is None


def test_rerunning_same_file_does_not_invalidate_analysis(session_factory):
    with session_factory() as session:
        imp1 = start_import(session, "file.xlsx", "hash1", rows_received=2)
        draft = _draft(
            [
                _msg(1, dt.datetime(2026, 8, 1, 9, 0, 0), "CUSTOMER", "hola"),
                _msg(1, dt.datetime(2026, 8, 1, 9, 0, 0), "BOT", "respuesta"),
            ]
        )
        save_conversation_with_messages(session, draft, imp1.id)
        session.commit()

        conv = session.execute(select(Conversation).where(Conversation.session_id == SID)).scalar_one()
        session.add(
            ConversationAnalysis(
                conversation_id=conv.id,
                categoria_final="NO_INTERESADO",
                metodo="RULE",
                analyzed_at=dt.datetime(2026, 8, 1, 10, 0, 0),
            )
        )
        session.commit()

        # Reprocesar exactamente el mismo archivo no aporta mensajes nuevos,
        # así que el análisis existente no debería invalidarse.
        imp2 = start_import(session, "file.xlsx", "hash1", rows_received=2)
        save_conversation_with_messages(session, draft, imp2.id)
        session.commit()

        analysis = session.execute(
            select(ConversationAnalysis).where(ConversationAnalysis.conversation_id == conv.id)
        ).scalar_one_or_none()
        assert analysis is not None


def test_phone_collision_flagged_but_first_phone_kept(session_factory):
    with session_factory() as session:
        imp = start_import(session, "file.xlsx", "hash1", rows_received=2)
        draft = _draft(
            [_msg(1, dt.datetime(2026, 8, 1, 9, 0, 0), "BOT", "hola", message_type="PROACTIVE", conn_id=None)],
            phone="573009990001",
            warnings=[
                "SESSION_ID 'x' appears with more than one distinct CUSTOMER_PHONE: "
                "['573009990001', '573009990002']. Keeping '573009990001'."
            ],
        )
        result = save_conversation_with_messages(session, draft, imp.id)
        session.commit()
        assert result.phone_collision is True
        conv = session.execute(select(Conversation).where(Conversation.session_id == SID)).scalar_one()
        assert conv.customer_phone == "573009990001"


def test_staging_messages_get_fresh_rows_on_every_import(session_factory):
    raw = RawRow(
        source_row=9,
        session_id=SID,
        channel="whatsapp",
        rp_id=61095,
        date=dt.datetime(2026, 8, 1, 9, 0, 0),
        customer_name="Cliente",
        customer_email="-",
        customer_phone=573001000002,
        customer_query="hola",
        routing_answer="respuesta",
        customer_id="-",
        conn_id=186111799,
        bsuid="---",
    )
    with session_factory() as session:
        imp1 = start_import(session, "file.xlsx", "hash1", rows_received=1)
        insert_staging_messages(session, imp1.id, [raw])
        finish_import(
            session,
            imp1,
            status="COMPLETED",
            rows_processed=1,
            rows_error=0,
            conversations_created=1,
            conversations_updated=0,
            messages_created=2,
            messages_skipped_duplicate=0,
            error_summary=None,
            warning_summary=None,
        )
        session.commit()

        imp2 = start_import(session, "file.xlsx", "hash1", rows_received=1)
        insert_staging_messages(session, imp2.id, [raw])
        session.commit()

        all_staging = session.execute(select(StagingMessage)).scalars().all()
        assert len(all_staging) == 2  # una copia fiel por cada import, sin deduplicar
