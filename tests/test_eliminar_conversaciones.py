from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select

from clasificador.analysis.repository import guardar_analisis
from clasificador.analysis.types import AnalysisResult
from clasificador.control_db.permissions import ROL_ADMIN, ROL_SUPER_ADMIN
from clasificador.conversation_builder import ConversationDraft
from clasificador.db.engine import create_all_tables, create_db_engine, make_session_factory
from clasificador.db.models import AIUsage, Conversation, ConversationAnalysis, Message
from clasificador.db.repository import (
    eliminar_conversaciones_por_fecha,
    save_conversation_with_messages,
    start_import,
)
from clasificador.pipeline_types import MessageDraft

from .test_admin_multicliente import _crear_usuario_control, _login_as
from .test_api import _make_app


def _draft(session_id, dia: dt.date, mensajes):
    return ConversationDraft(
        session_id=session_id,
        session_pattern="REAL",
        customer_phone="573001000002",
        customer_name="Cliente",
        customer_email=None,
        channel="whatsapp",
        rp_id="61095",
        started_at=dt.datetime.combine(dia, dt.time(9, 0)),
        ended_at=dt.datetime.combine(dia, dt.time(9, 5)),
        conn_id_count=1,
        messages=mensajes,
        iniciada_por=mensajes[0].sender,
        contiene_array=False,
        warnings=[],
    )


def _msg(source_row, dia: dt.date, sender, message):
    return MessageDraft(source_row, "186111799", dt.datetime.combine(dia, dt.time(9, 0)), sender, "TEXT", message)


@pytest.fixture
def session_factory():
    engine = create_db_engine("sqlite:///:memory:")
    create_all_tables(engine)
    return make_session_factory(engine)


def _crear_conversacion_completa(session_factory, session_id: str, dia: dt.date):
    """Conversación con mensajes + análisis + uso de IA — para probar que el
    borrado por fecha arrastra lo primero y lo segundo, pero conserva lo tercero."""
    with session_factory() as session:
        imp = start_import(session, "file.xlsx", f"hash-{session_id}", rows_received=2)
        draft = _draft(session_id, dia, [_msg(1, dia, "CUSTOMER", "hola"), _msg(2, dia, "BOT", "respuesta")])
        save_conversation_with_messages(session, draft, imp.id)
        guardar_analisis(
            session,
            AnalysisResult(
                session_id=session_id,
                categoria_final="INTERESADO",
                metodo="AI",
                modelo_ia="gpt-4o-mini",
                tokens_prompt=100,
                tokens_completion=20,
            ),
        )
        session.commit()
        conv_id = session.execute(select(Conversation.id).where(Conversation.session_id == session_id)).scalar_one()
    return conv_id


def test_eliminar_por_fecha_borra_solo_esa_fecha(session_factory):
    conv_5 = _crear_conversacion_completa(session_factory, "sid-5-sep", dt.date(2026, 9, 5))
    conv_6 = _crear_conversacion_completa(session_factory, "sid-6-sep", dt.date(2026, 9, 6))

    with session_factory() as session:
        resultado = eliminar_conversaciones_por_fecha(session, dt.date(2026, 9, 5))
        session.commit()

    assert resultado.conversaciones_eliminadas == 1
    assert resultado.mensajes_eliminados == 2

    with session_factory() as session:
        assert session.get(Conversation, conv_5) is None
        assert session.execute(select(Message).where(Message.conversation_id == conv_5)).first() is None
        assert (
            session.execute(select(ConversationAnalysis).where(ConversationAnalysis.conversation_id == conv_5)).first()
            is None
        )
        # El uso de IA se conserva como historial de gasto, solo se desvincula
        # de la conversación borrada — la del 6 de septiembre sigue con su conv_id.
        uso = session.execute(select(AIUsage)).scalars().all()
        assert len(uso) == 2
        uso_conv_5 = next(u for u in uso if u.conversation_id != conv_6)
        assert uso_conv_5.conversation_id is None
        assert uso_conv_5.tokens_prompt == 100
        uso_conv_6 = next(u for u in uso if u.conversation_id == conv_6)
        assert uso_conv_6.tokens_prompt == 100

        # La del 6 de septiembre queda intacta.
        assert session.get(Conversation, conv_6) is not None
        assert len(session.execute(select(Message).where(Message.conversation_id == conv_6)).all()) == 2


def test_eliminar_por_fecha_sin_coincidencias_es_no_op(session_factory):
    _crear_conversacion_completa(session_factory, "sid-otra-fecha", dt.date(2026, 9, 6))

    with session_factory() as session:
        resultado = eliminar_conversaciones_por_fecha(session, dt.date(2026, 9, 5))
        session.commit()

    assert resultado.conversaciones_eliminadas == 0
    assert resultado.mensajes_eliminados == 0


def test_reprocesar_despues_de_eliminar_recrea_sin_choques(session_factory):
    sid = "sid-reproceso"
    dia = dt.date(2026, 9, 5)
    _crear_conversacion_completa(session_factory, sid, dia)

    with session_factory() as session:
        eliminar_conversaciones_por_fecha(session, dia)
        session.commit()

    with session_factory() as session:
        imp = start_import(session, "file.xlsx", "hash-reproceso-2", rows_received=2)
        draft = _draft(sid, dia, [_msg(1, dia, "CUSTOMER", "hola"), _msg(2, dia, "BOT", "respuesta")])
        resultado = save_conversation_with_messages(session, draft, imp.id)
        session.commit()

    assert resultado.conversation_created is True
    assert resultado.messages_created == 2
    assert resultado.messages_skipped_duplicate == 0


def _crear_cliente_sqlite(app, tmp_path, *, db_name: str, nombre_cliente: str) -> int:
    from clasificador.control_db import repository as control_repo

    create_all_tables(create_db_engine(f"sqlite:///{tmp_path / (db_name + '.db')}"))
    with app.config["CONTROL_SESSION_FACTORY"]() as session:
        cliente = control_repo.create_cliente(session, nombre_cliente=nombre_cliente, db_name=db_name)
        session.commit()
        return cliente.id_cliente


def test_endpoint_eliminar_conversaciones_requiere_permiso(monkeypatch, tmp_path):
    app = _make_app(tmp_path, monkeypatch)
    id_cliente = _crear_cliente_sqlite(app, tmp_path, db_name="cliente_borrado", nombre_cliente="Cliente Borrado")
    usuario_id = _crear_usuario_control(
        app, nombre_rol=ROL_ADMIN, id_clientes=[id_cliente], email="admin-normal@example.com"
    )

    with app.test_client() as client:
        _login_as(client, usuario_id)
        resp = client.delete("/api/admin/conversaciones", json={"cliente_id": id_cliente, "fecha": "2026-09-05"})
        assert resp.status_code == 403


def test_endpoint_eliminar_conversaciones_borra_y_desaparece_de_la_api(monkeypatch, tmp_path):
    from clasificador.config import build_client_db_url

    app = _make_app(tmp_path, monkeypatch)
    id_cliente = _crear_cliente_sqlite(app, tmp_path, db_name="cliente_borrado2", nombre_cliente="Cliente Borrado 2")
    usuario_id = _crear_usuario_control(
        app, nombre_rol=ROL_SUPER_ADMIN, id_clientes=[id_cliente], email="super@example.com"
    )

    client_url = build_client_db_url(app.config["SETTINGS"].control_db_url, "cliente_borrado2")
    client_session_factory = make_session_factory(create_db_engine(client_url))
    _crear_conversacion_completa(client_session_factory, "sid-endpoint", dt.date(2026, 9, 5))

    with app.test_client() as client:
        _login_as(client, usuario_id)

        antes = client.get("/api/conversations").get_json()
        assert antes["total"] == 1

        resp = client.delete("/api/admin/conversaciones", json={"cliente_id": id_cliente, "fecha": "2026-09-05"})
        assert resp.status_code == 200, resp.get_json()
        body = resp.get_json()
        assert body == {"conversaciones_eliminadas": 1, "mensajes_eliminados": 2}

        despues = client.get("/api/conversations").get_json()
        assert despues["total"] == 0

        # cliente_id/fecha faltantes -> 400
        assert client.delete("/api/admin/conversaciones", json={"cliente_id": id_cliente}).status_code == 400
        # fecha con formato inválido -> 400
        assert (
            client.delete(
                "/api/admin/conversaciones", json={"cliente_id": id_cliente, "fecha": "05-09-2026"}
            ).status_code
            == 400
        )
